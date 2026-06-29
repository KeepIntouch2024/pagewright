#!/usr/bin/env bash
# Build Pagewright.app (macOS). Produces dist/Pagewright.app — double-click to run.
set -e
cd "$(dirname "$0")/.."

python3 -m venv .build-venv
source .build-venv/bin/activate
pip install -U pip
pip install -e ".[desktop,extract,anthropic,openai]" pyinstaller

rm -rf build dist
pyinstaller --clean --noconfirm packaging/pagewright.spec

echo
echo "✅ Built dist/Pagewright.app"
echo "   First launch: right-click → Open (unsigned app; Gatekeeper asks once)."
echo "   To distribute without the warning, code-sign + notarize (see packaging/README.md)."
