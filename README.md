# Talks

Zhi Li's presentation decks, served with GitHub Pages at <https://chrimerss.github.io/talks/>.
Each folder is one talk; `index.html` at the root is the landing page that links to them.

There are three kinds of talk folder:

- **Slidev decks** (`aih2026/`): a hosted build of a Slidev project, made with
  `scripts/build-slidev.sh`. The source stays in `~/Documents/talk/<talk>/`.
- **Single HTML decks** (`flood-ed/`): one self-contained file copied in as `index.html`.
- **PowerPoint decks** (everything else): slide images in a shared viewer, with the deck's
  videos and animated GIFs playing where they sat on the slide, and the PDF for download.
  Made with `scripts/build-pptx.py`. The `.pptx` stays in `~/Documents/talk/<venue>/`.

Shared pieces: `viewer/` is the slide viewer for PowerPoint decks, and `media/` holds their
videos and animations, one file per distinct source, so a video used in several decks is
stored once.

## Update a talk

Run these from this folder, then commit and push; Pages republishes in about a minute.

Slidev deck (multi-file build, so videos load on demand):

```bash
scripts/build-slidev.sh ../AIH2026 aih2026
```

Single HTML file:

```bash
cp ../flood_ed_interim_slides.html flood-ed/index.html
```

PowerPoint deck. This opens the deck in PowerPoint, saves a PDF into `_export/` (ignored by
git), and rebuilds the folder:

```bash
scripts/build-pptx.py "../CSU2026/Rethinking Flood.pptx" csu2026-rethinking-flood --title "Rethinking Flood Research: From Living Systems to Foundation Models"
```

```bash
git add -A && git commit -m "Update talks" && git push
```

## Add a talk

1. Build it into a new folder with one of the commands above.
2. Add an entry to the `TALKS` list near the bottom of `index.html` (newest first, with its `year`).
3. Commit and push.

## Notes on PowerPoint decks

- Hidden slides are left out, as in PowerPoint's own PDF export.
- Animations and transitions are not kept; each slide shows its final state.
- Videos start muted with controls. Animated GIFs become small looping videos, or stay
  animated images when they have transparent areas.
- PowerPoint's sandbox only lets it write where it has been granted access. Saving into
  `_export/` works; if PowerPoint shows a "Grant File Access" dialog, grant this folder.

## Draft or final

Each entry in `TALKS` has `status: 'draft'` or `status: 'final'`, which sets the badge on the
landing page. Drafts are still public to anyone with the link.
