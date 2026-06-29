#!/usr/bin/env bash
# Reproduce the North Face 1996 Retro Nuptse detail page from its ProductSpec.
# Requires the product photos in assets/products/ (see ASSETS.md — not committed).
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"
SCALE="${1:-1.8}"

pagewright compose product_spec.json --theme theme.toml -o page.html
pagewright render page.html -o output --scale "$SCALE"
echo "done → $DIR/output/full.png"
