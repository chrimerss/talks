# Talks

Zhi Li's presentation decks, served with GitHub Pages at <https://chrimerss.github.io/talks/>.
Each folder is one talk; `index.html` at the root is the landing page that links to them.

| Folder | Talk | Source |
|---|---|---|
| `aih2026/` | When AI Meets Flood Simulation (AIH 2026) | `~/Documents/talk/AIH2026` (Slidev) |
| `flood-ed/` | Floods and Emergency Department Visits in California, 2014–2023 | `~/Documents/talk/flood_ed_interim_slides.html` |

Only the built decks live here. The sources stay where they are.

## Update a talk

Slidev deck (multi-file build, so videos load on demand):

```bash
scripts/build-slidev.sh ../AIH2026 aih2026
```

Single HTML file:

```bash
cp ../flood_ed_interim_slides.html flood-ed/index.html
```

Then commit and push; Pages republishes in about a minute.

```bash
git add -A && git commit -m "Update aih2026" && git push
```

## Add a talk

1. Put the deck in a new folder: `scripts/build-slidev.sh <source-dir> <folder>` for Slidev,
   or copy a single HTML file to `<folder>/index.html`.
2. Add an entry to the `TALKS` list near the bottom of `index.html` (newest first).
3. Commit and push.

## Draft or final

Each entry in `TALKS` has `status: 'draft'` or `status: 'final'`, which sets the badge on the
landing page. Drafts are still public to anyone with the link.
