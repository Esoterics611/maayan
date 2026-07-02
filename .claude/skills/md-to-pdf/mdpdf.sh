#!/usr/bin/env bash
# Convert a Markdown file to a polished PDF, then strip any blank pages.
# Hebrew/RTL-aware, readable code blocks, white background. Run with `bash mdpdf.sh`.
#
#   bash mdpdf.sh input.md [output.pdf]
#
set -euo pipefail

IN="${1:?usage: bash mdpdf.sh input.md [output.pdf]}"
OUT="${2:-${IN%.*}.pdf}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# nvm-installed node/npm may not be on a non-interactive PATH.
if ! command -v node >/dev/null 2>&1; then
  for d in "$HOME"/.nvm/versions/node/*/bin; do [ -d "$d" ] && PATH="$d:$PATH"; done
  export PATH
fi

# Puppeteer needs a Chromium. Prefer an explicit env var, else find one (snap/system).
CHROME="${PUPPETEER_EXECUTABLE_PATH:-}"
[ -z "$CHROME" ] && CHROME="$(command -v chromium || command -v chromium-browser || command -v google-chrome || command -v google-chrome-stable || true)"
[ -n "$CHROME" ] && export PUPPETEER_EXECUTABLE_PATH="$CHROME"

# md-to-pdf is a global npm bin; invoke via node to dodge a missing exec bit.
run_mdpdf() {
  if command -v md-to-pdf >/dev/null 2>&1; then md-to-pdf "$@";
  else node "$(npm root -g)/md-to-pdf/dist/cli.js" "$@"; fi
}

run_mdpdf "$IN" \
  --stylesheet "$HERE/style.css" \
  --launch-options '{"args":["--no-sandbox","--disable-dev-shm-usage"]}' \
  --pdf-options '{"format":"A4","printBackground":true,"margin":{"top":"20mm","bottom":"18mm","left":"18mm","right":"18mm"}}'

# md-to-pdf writes "<input without ext>.pdf"; normalize to the requested output path.
GEN="${IN%.*}.pdf"
[ "$GEN" != "$OUT" ] && mv -f "$GEN" "$OUT"

python3 "$HERE/strip_blank_pages.py" "$OUT"
echo "PDF: $OUT"
