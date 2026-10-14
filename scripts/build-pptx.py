#!/usr/bin/env python3
"""Publish a PowerPoint deck as a slide-viewer page in one talk folder.

    scripts/build-pptx.py <deck.pptx> <talk-folder> --title "Talk title"

1. Export the deck to PDF with Microsoft PowerPoint (or reuse --pdf).
2. Render each PDF page to slides/NNN.webp (1920 px) and thumbs/NNN.webp.
3. Find the videos and animated GIFs on the slides. A PDF keeps only their
   first frame, so they are transcoded into media/ (shared by every talk, one
   file per distinct source) and laid back over the slide where they sat.
4. Copy the PDF in for download and write <talk-folder>/index.html.

Hidden slides are skipped, as PowerPoint's PDF export does.
Needs pdftoppm, cwebp, gif2webp and ffmpeg on PATH.
"""
import argparse, hashlib, html, json, os, posixpath, re, shutil, subprocess, sys, tempfile, zipfile
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NS = {
    'p': 'http://schemas.openxmlformats.org/presentationml/2006/main',
    'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
    'p14': 'http://schemas.microsoft.com/office/powerpoint/2010/main',
}
R = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
REL = '{http://schemas.openxmlformats.org/package/2006/relationships}Relationship'
SLIDE_W, THUMB_W = 1920, 480


def run(*cmd):
    subprocess.run(cmd, check=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


# ---------------------------------------------------------------- pptx media

def part_rels(z, part):
    d, f = posixpath.split(part)
    path = posixpath.join(d, '_rels', f + '.rels')
    out = {}
    if path in z.namelist():
        for r in ET.fromstring(z.read(path)).iter(REL):
            external = r.get('TargetMode') == 'External'
            tgt = r.get('Target') if external else posixpath.normpath(posixpath.join(d, r.get('Target')))
            out[r.get('Id')] = (tgt, external)
    return out


def is_animated_gif(data):
    return data[:3] == b'GIF' and data.count(b'\x21\xf9\x04') > 1


def find_media(z):
    """Videos and animated GIFs per visible slide: {slide_no: [{kind, part, box}]}."""
    pres = ET.fromstring(z.read('ppt/presentation.xml'))
    size = pres.find('p:sldSz', NS)
    W, H = int(size.get('cx')), int(size.get('cy'))
    prels = part_rels(z, 'ppt/presentation.xml')
    found, n = {}, 0
    for sid in pres.find('p:sldIdLst', NS):
        part = prels[sid.get(R + 'id')][0]
        root = ET.fromstring(z.read(part))
        if root.get('show') == '0':
            continue
        n += 1
        rels = part_rels(z, part)

        def walk(el, tf):
            for ch in el:
                tag = ch.tag.rsplit('}', 1)[-1]
                if tag == 'grpSp':
                    x = ch.find('p:grpSpPr/a:xfrm', NS)
                    if x is None:
                        walk(ch, tf)
                        continue
                    off, ext, coff, cext = (x.find(f'a:{k}', NS) for k in ('off', 'ext', 'chOff', 'chExt'))
                    sx = int(ext.get('cx')) / (int(cext.get('cx')) or 1)
                    sy = int(ext.get('cy')) / (int(cext.get('cy')) or 1)
                    a, b, c, d = tf
                    walk(ch, (a * sx, a * (int(off.get('x')) - int(coff.get('x')) * sx) + b,
                              c * sy, c * (int(off.get('y')) - int(coff.get('y')) * sy) + d))
                elif tag == 'pic':
                    x = ch.find('p:spPr/a:xfrm', NS)
                    if x is None:
                        continue
                    nv = ch.find('p:nvPicPr/p:nvPr', NS)
                    blip = ch.find('p:blipFill/a:blip', NS)
                    m14 = nv.find('.//p14:media', NS) if nv is not None else None
                    vid = nv.find('a:videoFile', NS) if nv is not None else None
                    rid = (m14.get(R + 'embed') if m14 is not None else None) or \
                          (vid.get(R + 'link') if vid is not None else None)
                    item = None
                    if rid in rels and not rels[rid][1]:
                        item = {'kind': 'video', 'part': rels[rid][0]}
                    elif blip is not None and blip.get(R + 'embed') in rels:
                        tgt, external = rels[blip.get(R + 'embed')]
                        if not external and tgt.lower().endswith('.gif') and is_animated_gif(z.read(tgt)):
                            item = {'kind': 'gif', 'part': tgt}
                    if item:
                        off, ext = x.find('a:off', NS), x.find('a:ext', NS)
                        a, b, c, d = tf
                        item['box'] = [round((a * int(off.get('x')) + b) / W, 5), round((c * int(off.get('y')) + d) / H, 5),
                                       round(a * int(ext.get('cx')) / W, 5), round(c * int(ext.get('cy')) / H, 5)]
                        found.setdefault(n, []).append(item)

        walk(root.find('p:cSld/p:spTree', NS), (1, 0, 1, 0))
    return W / H, n, found


# ------------------------------------------------------------- transcoding

def gif_has_alpha(path):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-frames:v', '3', '-f', 'rawvideo', '-pix_fmt', 'rgba', '-'],
                         check=True, stdin=subprocess.DEVNULL, capture_output=True).stdout
    return any(raw[i] != 255 for i in range(3, len(raw), 4 * 7))


def transcode(z, item, tmp):
    """Write the web copy into media/ once per distinct source. Returns (kind, repo-relative path)."""
    data = z.read(item['part'])
    digest = hashlib.sha1(data).hexdigest()[:12]
    src = os.path.join(tmp, digest + os.path.splitext(item['part'])[1])
    media = os.path.join(REPO, 'media')
    os.makedirs(media, exist_ok=True)
    scale = "scale='trunc(min(1920,iw)/2)*2':-2:flags=lanczos"

    if item['kind'] == 'video':
        out = os.path.join(media, digest + '.mp4')
        if not os.path.exists(out):
            open(src, 'wb').write(data)
            part = os.path.join(tmp, 'out.mp4')
            run('ffmpeg', '-nostdin', '-y', '-v', 'error', '-i', src, '-vf', scale, '-fpsmax', '30', '-c:v', 'libx264', '-crf', '26',
                '-preset', 'slow', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '96k', '-movflags', '+faststart', part)
            shutil.move(part, out)
        return 'video', 'media/' + digest + '.mp4'

    open(src, 'wb').write(data)
    if gif_has_alpha(src):
        # Transparent GIFs stay images so whatever sits behind them still shows.
        out = os.path.join(media, digest + '.webp')
        if not os.path.exists(out):
            part = os.path.join(tmp, 'out.webp')
            run('gif2webp', '-quiet', '-lossy', '-q', '75', '-m', '6', '-mt', src, '-o', part)
            shutil.move(part, out)
        return 'image', 'media/' + digest + '.webp'
    out = os.path.join(media, digest + '.mp4')
    if not os.path.exists(out):
        part = os.path.join(tmp, 'out.mp4')
        run('ffmpeg', '-nostdin', '-y', '-v', 'error', '-i', src, '-vf', scale + ',format=yuv420p', '-fpsmax', '30', '-c:v', 'libx264',
            '-crf', '24', '-preset', 'slow', '-an', '-movflags', '+faststart', part)
        shutil.move(part, out)
    return 'loop', 'media/' + digest + '.mp4'


# ------------------------------------------------------------------- pages

def export_pdf(pptx, out):
    """Save the deck as PDF from PowerPoint. PowerPoint may only write where it
    has been granted access, so the export lands in _export/ inside this repo."""
    script = f'''
with timeout of 1800 seconds
tell application "Microsoft PowerPoint"
  open (POSIX file {json.dumps(pptx)})
  delay 3
  set p to active presentation
  save p in (POSIX file {json.dumps(out)}) as save as PDF
  close p saving no
end tell
end timeout'''
    subprocess.run(['osascript', '-e', script], check=True)


def render(pdf, folder, tmp):
    pages = os.path.join(tmp, 'pages')
    os.makedirs(pages)
    run('pdftoppm', '-png', '-scale-to-x', str(SLIDE_W), '-scale-to-y', '-1', pdf, os.path.join(pages, 'p'))
    pngs = sorted(os.listdir(pages), key=lambda f: int(re.findall(r'\d+', f)[-1]))
    for sub in ('slides', 'thumbs'):
        shutil.rmtree(os.path.join(folder, sub), ignore_errors=True)
        os.makedirs(os.path.join(folder, sub))

    def one(i_f):
        i, f = i_f
        src = os.path.join(pages, f)
        run('cwebp', '-quiet', '-q', '82', '-m', '6', src, '-o', os.path.join(folder, 'slides', f'{i:03d}.webp'))
        run('cwebp', '-quiet', '-q', '70', '-resize', str(THUMB_W), '0', src, '-o', os.path.join(folder, 'thumbs', f'{i:03d}.webp'))

    with ThreadPoolExecutor(os.cpu_count() or 4) as ex:
        list(ex.map(one, enumerate(pngs, 1)))
    return len(pngs)


PAGE = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='6' fill='%23CFB87C'/%3E%3C/svg%3E">
<link rel="stylesheet" href="../viewer/deck.css">
</head>
<body>
<noscript><p style="padding:24px">This deck needs JavaScript. <a style="color:#cfb87c" href="{pdf}">Download the PDF</a> instead.</p></noscript>
<script>window.DECK = {deck}</script>
<script src="../viewer/deck.js"></script>
</body>
</html>
'''


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('pptx')
    ap.add_argument('folder', help='talk folder name, e.g. csu2026-rethinking-flood')
    ap.add_argument('--title', required=True)
    ap.add_argument('--pdf', help='use this PDF instead of exporting from PowerPoint')
    args = ap.parse_args()
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]*', args.folder):
        sys.exit('Talk folder must be lowercase letters, digits and dashes')

    pptx = os.path.abspath(args.pptx)
    folder = os.path.join(REPO, args.folder)
    os.makedirs(folder, exist_ok=True)
    pdf = args.pdf
    if not pdf:
        os.makedirs(os.path.join(REPO, '_export'), exist_ok=True)
        pdf = os.path.join(REPO, '_export', args.folder + '.pdf')
        export_pdf(pptx, pdf)

    z = zipfile.ZipFile(pptx)
    aspect, visible, found = find_media(z)
    with tempfile.TemporaryDirectory() as tmp:
        count = render(pdf, folder, tmp)
        if count != visible:
            print(f'warning: PDF has {count} pages but the deck shows {visible} slides; video positions may be off',
                  file=sys.stderr)
        media = {}
        for n, items in sorted(found.items()):
            for item in items:
                kind, rel = transcode(z, item, tmp)
                media.setdefault(str(n), []).append({'kind': kind, 'src': '../' + rel, 'box': item['box']})

    pdf_name = args.folder + '.pdf'
    shutil.copyfile(pdf, os.path.join(folder, pdf_name))
    deck = {'title': args.title, 'pdf': pdf_name, 'aspect': round(aspect, 5), 'count': count, 'media': media}
    with open(os.path.join(folder, 'index.html'), 'w') as f:
        f.write(PAGE.format(title=html.escape(args.title), pdf=pdf_name,
                            deck=json.dumps(deck, ensure_ascii=False).replace('</', '<\\/')))
    n_media = sum(len(v) for v in media.values())
    print(f'Built {args.folder}/: {count} slides, {n_media} video(s) or animation(s)')


if __name__ == '__main__':
    main()
