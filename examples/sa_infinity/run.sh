#!/usr/bin/env bash
# Reproduce the SA Infinity 详情页 from its ProductSpec using the generic engine.
# No network, no API key — pure compose + render. Output lands in ./output/.
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"
SCALE="${1:-1.8}"   # 1.8× keeps the full height under Chrome's ~16384px screenshot cap

pagewright compose product_spec.json --theme theme.toml -o page.html
pagewright render page.html -o output --scale "$SCALE"
echo "done → $DIR/output/full.png"
