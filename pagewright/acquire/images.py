"""Download candidate product images, filter out junk (sprites, tracking pixels, tiny icons),
and de-duplicate by content hash.

For Cloudflare/login-walled sites (tier 3), a plain httpx GET of an image may itself be blocked.
In that case we fall back to fetching the bytes *inside* the authenticated browser via CDP —
the same trick the source project used to pull binary assets through a cleared session.
"""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Optional

_MIN_BYTES = 4096        # smaller than this is almost certainly an icon/sprite/pixel
_MIN_DIM = 200           # px; below this on both axes → skip


def _safe_name(url: str, idx: int) -> str:
    base = re.sub(r"[?#].*$", "", url).rstrip("/").split("/")[-1] or f"img{idx}"
    base = re.sub(r"[^A-Za-z0-9._-]", "_", base)[-60:]
    if not re.search(r"\.(jpe?g|png|webp|avif)$", base, re.I):
        base += ".jpg"
    return f"{idx:02d}_{base}"


def _ok_image(path: str) -> bool:
    try:
        if os.path.getsize(path) < _MIN_BYTES:
            return False
        from PIL import Image

        with Image.open(path) as im:
            w, h = im.size
        return w >= _MIN_DIM or h >= _MIN_DIM
    except Exception:
        return False


def download_images(
    urls: list[str],
    dest: str,
    *,
    settings,
    page_url: str,
    capture=None,
) -> list[str]:
    os.makedirs(dest, exist_ok=True)
    import httpx

    headers = {"User-Agent": settings.user_agent, "Referer": page_url}
    saved: list[str] = []
    seen_hashes: set[str] = set()
    need_browser: list[str] = []

    with httpx.Client(follow_redirects=True, timeout=settings.request_timeout, headers=headers) as c:
        for i, u in enumerate(urls):
            try:
                r = c.get(u)
                if r.status_code in (403, 429, 503) or not r.content:
                    need_browser.append(u)
                    continue
                p = _commit(dest, _safe_name(u, i), r.content, seen_hashes)
                if p:
                    saved.append(p)
            except Exception:
                need_browser.append(u)

    # tier 2/3 fallback: fetch bytes through the (possibly authenticated) browser
    if need_browser and capture is not None and getattr(capture, "tier", 1) >= 2:
        for i, u in enumerate(need_browser, start=len(urls)):
            data = _browser_fetch_bytes(u, page_url, settings)
            if data:
                p = _commit(dest, _safe_name(u, i), data, seen_hashes)
                if p:
                    saved.append(p)
    return saved


def _commit(dest: str, name: str, data: bytes, seen: set) -> Optional[str]:
    h = hashlib.sha1(data).hexdigest()
    if h in seen:
        return None
    path = os.path.join(dest, name)
    Path(path).write_bytes(data)
    if not _ok_image(path):
        os.remove(path)
        return None
    seen.add(h)
    return os.path.abspath(path)  # absolute → resolves at compose/verify regardless of cwd


def _browser_fetch_bytes(url: str, page_url: str, settings) -> Optional[bytes]:
    """Pull asset bytes from inside the CDP-attached browser (bypasses bot walls)."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None
    import base64

    try:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(settings.cdp_url)
            ctx = browser.contexts[0] if browser.contexts else browser.new_context()
            page = ctx.new_page()
            page.goto(page_url, wait_until="domcontentloaded",
                      timeout=int(settings.request_timeout * 1000))
            b64 = page.evaluate(
                """async (u) => {
                    const r = await fetch(u);
                    const buf = await r.arrayBuffer();
                    let s = ''; const bytes = new Uint8Array(buf);
                    for (let i = 0; i < bytes.length; i++) s += String.fromCharCode(bytes[i]);
                    return btoa(s);
                }""",
                url,
            )
            page.close()
            return base64.b64decode(b64) if b64 else None
    except Exception:
        return None
