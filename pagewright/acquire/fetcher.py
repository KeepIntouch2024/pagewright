"""Layered fallback fetcher — the answer to "how do I scrape arbitrary product sites?".

Three tiers, auto-escalating; whatever wins, the *captured text + screenshots* are what the
LLM extractor consumes — so there are no per-site parsers:

  Tier 1  httpx + readable-text extraction          static / server-rendered pages
  Tier 2  Playwright headless (stealthy)            JS/SPA sites, light bot checks
  Tier 3  attach to YOUR real Chrome over CDP        Cloudflare, login walls, paywalls

Escalation triggers: HTTP 403/429/503, a Cloudflare/"Just a moment" interstitial, an empty
SPA shell (almost no text), or too few images found. You can also force a tier.

Be a good citizen: robots.txt is honored by default and requests are rate-limited.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse


@dataclass
class RawCapture:
    url: str
    tier: int = 0
    html: str = ""
    text: str = ""
    title: str = ""
    screenshots: list[str] = field(default_factory=list)  # local PNG paths
    image_urls: list[str] = field(default_factory=list)
    downloaded_images: list[str] = field(default_factory=list)
    challenged: bool = False
    meta: dict = field(default_factory=dict)

    def save(self, out_dir: str) -> None:
        os.makedirs(out_dir, exist_ok=True)
        Path(out_dir, "page.html").write_text(self.html or "", encoding="utf-8")
        Path(out_dir, "page.txt").write_text(self.text or "", encoding="utf-8")
        manifest = {
            "url": self.url, "tier": self.tier, "title": self.title,
            "challenged": self.challenged, "screenshots": self.screenshots,
            "image_urls": self.image_urls, "downloaded_images": self.downloaded_images,
            "meta": self.meta,
        }
        Path(out_dir, "capture.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    @classmethod
    def load(cls, work_dir: str) -> "RawCapture":
        m = json.loads(Path(work_dir, "capture.json").read_text(encoding="utf-8"))
        cap = cls(url=m["url"], tier=m.get("tier", 0), title=m.get("title", ""),
                  challenged=m.get("challenged", False), screenshots=m.get("screenshots", []),
                  image_urls=m.get("image_urls", []),
                  downloaded_images=m.get("downloaded_images", []), meta=m.get("meta", {}))
        p = Path(work_dir, "page.html")
        cap.html = p.read_text(encoding="utf-8") if p.exists() else ""
        t = Path(work_dir, "page.txt")
        cap.text = t.read_text(encoding="utf-8") if t.exists() else ""
        return cap


# -- escalation heuristics -------------------------------------------------------------------
_CF_MARKERS = ("just a moment", "cf-chl", "challenge-platform", "cf_chl_opt",
               "checking your browser", "enable javascript and cookies")


def looks_challenged(html: str, status: Optional[int] = None) -> bool:
    if status in (403, 429, 503):
        return True
    low = (html or "").lower()
    return any(m in low for m in _CF_MARKERS)


def looks_empty(text: str, min_chars: int = 350) -> bool:
    return len((text or "").strip()) < min_chars


def _allowed_by_robots(url: str, ua: str) -> bool:
    import urllib.robotparser as rp

    parts = urlparse(url)
    robots = f"{parts.scheme}://{parts.netloc}/robots.txt"
    p = rp.RobotFileParser()
    try:
        p.set_url(robots)
        p.read()
    except Exception:
        return True  # no robots / unreachable → don't block
    return p.can_fetch(ua, url)


# -- orchestration ---------------------------------------------------------------------------
def acquire(
    url: str,
    out_dir: str,
    *,
    settings,
    force_tier: Optional[int] = None,
    download_images: bool = True,
    max_images: int = 24,
) -> RawCapture:
    if settings.respect_robots and not _allowed_by_robots(url, settings.user_agent):
        raise PermissionError(
            f"robots.txt disallows fetching {url}. Override with PAGEWRIGHT_RESPECT_ROBOTS=0 "
            "only for pages you are authorized to access."
        )

    cap: Optional[RawCapture] = None
    tiers = [force_tier] if force_tier else [1, 2, 3]
    for tier in tiers:
        cap = _run_tier(tier, url, settings)
        if force_tier:
            break
        # decide whether to escalate
        if not cap.challenged and not looks_empty(cap.text) and len(cap.image_urls) >= 1:
            break
        if tier < 3:
            continue  # escalate
    assert cap is not None

    if download_images and cap.image_urls:
        from .images import download_images as _dl

        cap.downloaded_images = _dl(
            cap.image_urls[:max_images], os.path.join(out_dir, "images"),
            settings=settings, page_url=url, capture=cap,
        )
    cap.save(out_dir)
    return cap


def _run_tier(tier: int, url: str, settings) -> RawCapture:
    if tier == 1:
        from .tier1_http import fetch as t1

        return t1(url, settings)
    if tier == 2:
        from .tier2_browser import fetch as t2

        return t2(url, settings)
    if tier == 3:
        from .tier3_attach import fetch as t3

        return t3(url, settings)
    raise ValueError(f"bad tier {tier}")


def absolutize(base_url: str, links: list[str]) -> list[str]:
    out, seen = [], set()
    for h in links:
        if not h or h.startswith("data:"):
            continue
        u = urljoin(base_url, h)
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out
