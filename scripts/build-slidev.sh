#!/usr/bin/env bash
# Rebuild a Slidev deck as a hosted, multi-file site inside one talk folder.
#
# The deck's own vite.config.ts folds everything into one portable HTML file,
# which is right for a USB stick and slow on the web. This builds a copy of the
# source with a plain config instead, so figures and videos load on demand.
# The deck source is never modified.
#
# Usage: scripts/build-slidev.sh <deck-source-dir> <talk-folder>
#   e.g. scripts/build-slidev.sh ../AIH2026 aih2026
set -euo pipefail

if [ $# -ne 2 ]; then
  echo "Usage: $0 <deck-source-dir> <talk-folder>" >&2
  exit 1
fi
case "$2" in
  ""|.|..|*/*|.*) echo "Talk folder must be a plain name such as aih2026" >&2; exit 1 ;;
esac

src=$(cd "$1" && pwd)
repo=$(cd "$(dirname "$0")/.." && pwd)
dest="$repo/$2"

[ -f "$src/slides.md" ] || { echo "No slides.md in $src" >&2; exit 1; }
[ -d "$src/node_modules" ] || (cd "$src" && npm ci --no-audit --no-fund)

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

rsync -a --exclude node_modules --exclude dist --exclude '/*.html' --exclude '/*.pdf' "$src/" "$work/"
ln -s "$src/node_modules" "$work/node_modules"
cat > "$work/vite.config.ts" <<'EOF'
import { defineConfig } from 'vite'

export default defineConfig({
  // Slidev's UnoCSS layer emits a rule lightningcss rejects; see the deck's own config.
  build: { cssMinify: false, chunkSizeWarningLimit: 100000 },
})
EOF

(cd "$work" && npx slidev build --base ./ --out "$work/dist")
rm -rf "$dest"
mv "$work/dist" "$dest"
echo "Built $2/ ($(du -sh "$dest" | cut -f1))"
