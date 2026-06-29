#!/usr/bin/env bash
# Package dist/Pagewright.app into a distributable drag-to-Applications .dmg (macOS).
# Run build_macos.sh first (or this will build the app if a venv with deps is active).
set -e
cd "$(dirname "$0")/.."

APP="dist/Pagewright.app"
if [ ! -d "$APP" ]; then
  echo "→ $APP not found; building it first…"
  pyinstaller --clean --noconfirm packaging/pagewright.spec
fi

STAGE="$(mktemp -d)/Pagewright"
mkdir -p "$STAGE"
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"   # drag-to-install target

rm -f dist/Pagewright.dmg
hdiutil create -volname "Pagewright" -srcfolder "$STAGE" -ov -format UDZO dist/Pagewright.dmg

echo
echo "✅ dist/Pagewright.dmg  — share this. Users open it and drag Pagewright → Applications."
echo "   Unsigned: first launch needs right-click → Open. Sign+notarize to remove the warning"
echo "   (see packaging/README.md)."
