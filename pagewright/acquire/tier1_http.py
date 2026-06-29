"""Tier 1 — static HTTP fetch + readable-text extraction. Fast, zero browser.

Good for server-rendered product pages. Uses trafilatura for main text when available
(falls back to a crude tag strip), and collects candidate product image URLs from <img>
src/srcset and OpenGraph tags.
"""

from __future__ import annotations

import re

from .fetcher import RawCapture, absolutize, looks_challenged

_IMG_EXT = re.compile(r"\.(jpe?g|png|webp|avif)(\?|$)", re.I)


def fetch(url: str, settings) -> RawCapture:
    import httpx

    headers = {"User-Agent": settings.user_agent, "Accept-Language": "en,zh;q=0.8"}
    with httpx.Client(follow_redirects=True, timeout=settings.request_timeout, headers=headers) as c:
        r = c.get(url)
        html = r.text
        status = r.status_code

    cap = RawCapture(url=url, tier=1, html=html, meta={"status": status})
    cap.challenged = looks_challenged(html, status)
    cap.title = _title(html)
    cap.text = _readable_text(html, url)
    cap.image_urls = _images(html, url)
    return cap


def _title(html: str) -> str:
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""


def _readable_text(html: str, url: str) -> str:
    try:
        import trafilatura

        txt = trafilatura.extract(html, url=url, include_tables=True, favor_recall=True)
        if txt and len(txt.strip()) > 200:
            return txt
    except Exception:
        pass
    # crude fallback: strip scripts/styles/tags
    cleaned = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.I | re.S)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def _images(html: str, url: str) -> list[str]:
    cands: list[str] = []
    # OpenGraph hero
    for m in re.finditer(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)', html, re.I):
        cands.append(m.group(1))
    # <img src> and the largest candidate in srcset
    for m in re.finditer(r"<img\b[^>]*>", html, re.I):
        tag = m.group(0)
        src = re.search(r'\bsrc=["\']([^"\']+)', tag)
        if src:
            cands.append(src.group(1))
        ss = re.search(r'\bsrcset=["\']([^"\']+)', tag)
        if ss:
            best = ss.group(1).split(",")[-1].strip().split(" ")[0]
            if best:
                cands.append(best)
    abs_imgs = absolutize(url, cands)
    return [u for u in abs_imgs if _IMG_EXT.search(u)]
