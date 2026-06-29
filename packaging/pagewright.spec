# PyInstaller spec — builds a standalone Pagewright desktop app.
#   macOS:   pyinstaller packaging/pagewright.spec        → dist/Pagewright.app
#   Windows: pyinstaller packaging/pagewright.spec        → dist/Pagewright/Pagewright.exe
#
# The end user double-clicks it. No Python, no Docker. Rendering uses the user's installed
# Chrome/Edge (not bundled). LLM SDKs are bundled so any provider works once a key is entered.
import sys
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

hiddenimports = []
for pkg in ("uvicorn", "fastapi", "starlette", "anyio", "pydantic", "jinja2",
            "anthropic", "openai", "webview"):
    try:
        hiddenimports += collect_submodules(pkg)
    except Exception:
        pass

# Bundle Pagewright's package data (templates, themes, web UI static files).
datas = collect_data_files("pagewright", includes=[
    "compose/base.html", "compose/blocks/*", "compose/themes/*", "app/static/*",
])
# certifi CA bundle (httpx / SDK TLS)
try:
    datas += collect_data_files("certifi")
except Exception:
    pass

a = Analysis(
    ["launch.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "PyQt5", "PySide6"],
    noarchive=False,
)
pyz = PYZ(a.pure)

# Spec runs with cwd = packaging/, where the icon files live.
_win_icon = "Pagewright.ico"
_mac_icon = "Pagewright.icns"

exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True,
    name="Pagewright", console=False, disable_windowed_traceback=False,
    icon=(_mac_icon if sys.platform == "darwin" else _win_icon),
)
coll = COLLECT(exe, a.binaries, a.datas, name="Pagewright")

# macOS: wrap into a .app bundle
if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="Pagewright.app",
        icon=_mac_icon,
        bundle_identifier="com.pagewright.app",
        info_plist={
            "CFBundleName": "Pagewright",
            "CFBundleDisplayName": "Pagewright",
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "11.0",
        },
    )
