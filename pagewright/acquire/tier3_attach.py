"""Tier 3 — attach to YOUR already-running Chrome over CDP.

This is the general, scriptable version of how the source project beat Cloudflare: it drove a
real browser that had *already* passed the challenge / logged in. You launch Chrome once with a
debugging port, clear the wall by hand, then Pagewright reuses that authenticated session — no
solver, no fragile evasion.

    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \\
        --remote-debugging-port=9222 --user-data-dir="$HOME/pf-chrome"
    # log in / pass Cloudflare in that window, then:  pagewright acquire <url> --tier 3

Because the page is fetched inside that trusted context, same-origin asset bytes can be pulled
with page.evaluate(fetch) too (see images.py). An alternative for browser-extension users is the
localhost POST sink in localserver.py.
"""

from __future__ import annotations

import os
import tempfile

from .fetcher import RawCapture, absolutize, looks_challenged


def fetch(url: str, settings) -> RawCapture:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:  # pragma: no cover
        raise ImportError(
            "Tier 3 needs Playwright: pip install 'pagewright[browser]' && playwright install chromium"
        ) from e

    shot = os.path.join(tempfile.mkdtemp(), "tier3.png")
    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp(settings.cdp_url)
        except Exception as e:
            raise RuntimeError(
                f"Could not attach to Chrome at {settings.cdp_url}. Launch Chrome with "
                f"--remote-debugging-port=9222 (see tier3_attach.py docstring). Original: {e}"
            ) from e
        ctx = browser.contexts[0] if browser.contexts else browser.new_context()
        page = ctx.new_page()
        try:
            page.goto(url, wait_until="networkidle", timeout=int(settings.request_timeout * 1000))
        except Exception:
            page.goto(url, timeout=int(settings.request_timeout * 1000))
        page.wait_for_timeout(1200)  # give a human a beat if a challenge is mid-flight
        html = page.content()
        title = page.title()
        text = page.evaluate("() => document.body ? document.body.innerText : ''")
        imgs = page.evaluate(
            "() => Array.from(document.images).map(im => im.currentSrc || im.src).filter(Boolean)"
        )
        final_url = page.url
        try:
            page.screenshot(path=shot, full_page=True)
        except Exception:
            page.screenshot(path=shot)
        page.close()

    cap = RawCapture(url=url, tier=3, html=html, text=text or "", title=title or "")
    cap.screenshots = [shot] if os.path.exists(shot) else []
    cap.image_urls = absolutize(final_url, imgs)
    cap.challenged = looks_challenged(html)
    cap.meta = {"final_url": final_url, "via": "cdp"}
    return cap
