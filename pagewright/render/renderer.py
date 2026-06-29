"""HTML → PNG.

Two engines, auto-selected:
  - Playwright (preferred): full-page screenshot at a chosen device-scale.
  - Headless Chrome CLI (fallback, no extra deps): mirrors the original render.sh
    (`--headless --screenshot --force-device-scale-factor`), with a kill-guard.

Chrome refuses screenshots taller than ~16384 device px. We measure the content height
first; if height*scale would exceed the cap we transparently lower the effective scale to
fit and warn (this is exactly why the original render.sh defaulted to 1.8×). The raw PNG is
then handed to slice.finalize for crop + panel slicing.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from . import slice as _slice

_CHROME_CANDIDATES = [
    # macOS
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    # Windows (Edge ships with Windows 10/11 → a renderer is always present there)
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    # PATH (Linux / anything)
    shutil.which("google-chrome"),
    shutil.which("chromium"),
    shutil.which("chromium-browser"),
    shutil.which("microsoft-edge"),
    shutil.which("brave-browser"),
    shutil.which("chrome"),
]


def _find_chrome() -> Optional[str]:
    for c in _CHROME_CANDIDATES:
        if c and os.path.exists(c):
            return c
    return None


def _fit_scale(content_h: int, scale: float, cap: int) -> float:
    if content_h <= 0:
        return scale
    if content_h * scale <= cap:
        return scale
    fitted = max(1.0, cap / content_h)
    return fitted


def render_with_playwright(html_path: str, raw_png: str, *, width: int, scale: float, cap: int) -> float:
    from playwright.sync_api import sync_playwright

    url = Path(html_path).resolve().as_uri()
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--force-color-profile=srgb"])
        page = browser.new_page(viewport={"width": width, "height": 1000}, device_scale_factor=1)
        page.goto(url, wait_until="networkidle")
        page.wait_for_timeout(400)  # let fonts/icons settle
        content_h = page.evaluate("document.body.scrollHeight")
        eff = _fit_scale(int(content_h), scale, cap)
        if eff != scale:
            print(f"[render] content {content_h}px × scale {scale} exceeds {cap}px cap → using scale {eff:.2f}")
        page.close()
        page = browser.new_page(viewport={"width": width, "height": 1000}, device_scale_factor=eff)
        page.goto(url, wait_until="networkidle")
        page.wait_for_timeout(400)
        page.screenshot(path=raw_png, full_page=True)
        browser.close()
    return eff


def render_with_chrome_cli(
    html_path: str, raw_png: str, *, width: int, scale: float, cap: int, timeout: int = 90
) -> float:
    chrome = _find_chrome()
    if not chrome:
        raise RuntimeError(
            "No renderer available: install Playwright ('pip install pagewright[browser]' "
            "&& playwright install chromium) or Google Chrome."
        )
    # We can't easily measure height without a browser, so honor the requested scale but keep a
    # generous window; slice.finalize crops trailing blank rows afterwards.
    win_h = min(int(cap / max(scale, 1.0)), 30000)
    url = Path(html_path).resolve().as_uri()
    prof = tempfile.mkdtemp()
    cmd = [
        chrome, "--headless", "--disable-gpu", "--no-sandbox", "--no-first-run",
        "--no-default-browser-check", "--hide-scrollbars",
        f"--force-device-scale-factor={scale}", "--virtual-time-budget=8000",
        f"--user-data-dir={prof}", f"--screenshot={raw_png}",
        f"--window-size={width},{win_h}", url,
    ]
    try:
        subprocess.run(cmd, timeout=timeout, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        pass  # kill-guard: a partial screenshot is usually still written
    if not os.path.exists(raw_png):
        raise RuntimeError("Chrome did not produce a screenshot.")
    return scale


def render(
    html_path: str,
    out_dir: str,
    *,
    width: int = 750,
    scale: float = 2.0,
    cap: int = 16384,
    full_name: str = "full.png",
    panel_height: int = 1500,
    make_panels: bool = True,
    engine: str = "auto",
) -> dict:
    """Render ``html_path`` to ``out_dir`` as a cropped full image + sliced panels."""
    os.makedirs(out_dir, exist_ok=True)
    raw_png = os.path.join(tempfile.mkdtemp(), "raw.png")

    use_playwright = engine == "playwright" or (engine == "auto" and _has_playwright())
    if use_playwright:
        eff_scale = render_with_playwright(html_path, raw_png, width=width, scale=scale, cap=cap)
    else:
        eff_scale = render_with_chrome_cli(html_path, raw_png, width=width, scale=scale, cap=cap)

    return _slice.finalize(
        raw_png, out_dir, scale=eff_scale, full_name=full_name,
        panel_height=panel_height, make_panels=make_panels,
    )


def _has_playwright() -> bool:
    try:
        import playwright  # noqa: F401

        return True
    except ImportError:
        return False
