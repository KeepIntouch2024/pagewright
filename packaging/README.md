# Packaging Pagewright as a double-click desktop app

End users get a single icon they double-click — **no Python, no Docker, no terminal**. They
paste their own LLM API key in the in-app Settings screen on first run.

## What's bundled vs. relied upon
- **Bundled:** Python runtime, Pagewright, the web UI, FastAPI/uvicorn, the native webview
  (pywebview → OS WebKit/WebView2), and the LLM SDKs (anthropic + openai).
- **Relied upon (not bundled):** the user's installed **Google Chrome or Microsoft Edge** for
  rendering. Edge ships with Windows, so Windows always has a renderer; on macOS, Chrome is the
  common case (the app shows a friendly prompt if none is found).
- **Not included:** Playwright/Chromium (tier-2/3 URL scraping) and rembg (cut-outs). The
  primary "upload photos + description → poster" flow doesn't need them. Power users can
  `pip install pagewright[browser,cutout]` in a CLI install.

## Build

### App icon
The icon is generated from the brand mark: edit `icon/icon.html`, re-render to
`icon/icon_1024.png` (a headless-Chrome screenshot with a transparent background), then rebuild
`Pagewright.icns` (macOS, via `iconutil`) and `Pagewright.ico` (Windows, via Pillow). Both files
live in `packaging/` and are wired into `pagewright.spec` (`BUNDLE(icon=…)` / `EXE(icon=…)`).

### macOS → `dist/Pagewright.app` and `dist/Pagewright.dmg`
```bash
bash packaging/build_macos.sh      # → dist/Pagewright.app
bash packaging/build_dmg.sh        # → dist/Pagewright.dmg (drag-to-Applications installer)
open dist/Pagewright.dmg
```
First launch is unsigned, so Gatekeeper warns once: **right-click → Open**. To ship it without
the warning, code-sign + notarize **before** making the dmg:
```bash
codesign --deep --force --options runtime --sign "Developer ID Application: <you>" dist/Pagewright.app
xcrun notarytool submit dist/Pagewright.app --apple-id <id> --team-id <team> --password <app-pw> --wait
xcrun stapler staple dist/Pagewright.app
bash packaging/build_dmg.sh        # package the signed app
```
Distribute the `.dmg`.

### Windows → `dist\Pagewright\Pagewright.exe`
Run on a Windows machine (a Mac can't produce a `.exe`):
```bat
packaging\build_windows.bat
```
Zip `dist\Pagewright` and share it. WebView2 runtime ships with current Windows; Edge provides
the renderer. For a signed installer, wrap with Inno Setup / NSIS and an Authenticode cert.

## Notes
- The app stores the user's settings (provider, key, model) in `~/.pagewright/settings.json`.
- Uploads and rendering happen entirely on the user's machine; only the LLM calls they
  configured leave it.
