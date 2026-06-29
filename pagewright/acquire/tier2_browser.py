"""Tier 2 — Playwright headless Chromium. Renders JS/SPA pages and passes light bot checks.

Stealth-ish defaults: a real UA, a normal viewport, and AutomationControlled disabled. We wait
for network idle, capture a full-page screenshot (the LLM reads it), and pull rendered DOM text
+ image URLs (resolved against the final URL).
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
            "Tier 2 needs Playwright: pip install 'pagewright[browser]' && playwright install chromium"
        ) from e

    shot = os.path.join(tempfile.mkdtemp(), "tier2.png")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
        )
        ctx = browser.new_context(
            user_agent=settings.user_agent,
            viewport={"width": 1280, "height": 1600},
            locale="en-US",
        )
        page = ctx.new_page()
        try:
            page.goto(url, wait_until="networkidle", timeout=int(settings.request_timeout * 1000))
        except Exception:
            page.goto(url, timeout=int(settings.request_timeout * 1000))
        page.wait_for_timeout(800)
        html = page.content()
        title = page.title()
        text = page.evaluate("() => document.body ? document.body.innerText : ''")
        imgs = page.evaluate(
            """() => Array.from(document.images).flatMap(im => {
                   const out = [im.currentSrc || im.src];
                   const og = document.querySelector('meta[property="og:image"]');
                   if (og) out.push(og.content);
                   return out;
               }).filter(Boolean)"""
        )
        final_url = page.url
        try:
            page.screenshot(path=shot, full_page=True)
        except Exception:
            page.screenshot(path=shot)
        browser.close()

    cap = RawCapture(url=url, tier=2, html=html, text=text or "", title=title or "")
    cap.screenshots = [shot] if os.path.exists(shot) else []
    cap.image_urls = absolutize(final_url, imgs)
    cap.challenged = looks_challenged(html)
    cap.meta = {"final_url": final_url}
    return cap
