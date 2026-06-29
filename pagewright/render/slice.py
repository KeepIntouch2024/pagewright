"""Auto-crop + panel slicing for long e-commerce images.

Ported from the original 详情页_v2/render.sh PIL block. Two jobs:
  1. crop_bottom_whitespace: trim trailing near-white rows (the screenshot is taller than
     the content).
  2. slice_panels: cut the tall image into upload-friendly panels, *snapping every cut to a
     low-detail ("quiet") row* so we never slice through text or an icon.

Pure Pillow/NumPy — no browser — so it is unit-testable on a fixture image.
"""

from __future__ import annotations

import os
from typing import Optional

import numpy as np
from PIL import Image

WHITE_THRESHOLD = 248  # a pixel channel >= this counts as "blank"


def crop_bottom_whitespace(im: Image.Image, threshold: int = WHITE_THRESHOLD) -> Image.Image:
    """Drop trailing rows that are entirely near-white (or near-blank)."""
    a = np.asarray(im.convert("RGB"))
    nonblank_rows = np.where((a < threshold).any(axis=2).any(axis=1))[0]
    if nonblank_rows.size == 0:
        return im
    bottom = int(nonblank_rows.max()) + 1
    return im.crop((0, 0, im.width, bottom))


def _row_detail(im: Image.Image) -> np.ndarray:
    """Horizontal detail per row: sum of |Δ| along x in grayscale. Low == quiet band."""
    g = np.asarray(im.convert("L")).astype("int16")
    return np.abs(np.diff(g, axis=1)).sum(axis=1)


def slice_panels(
    im: Image.Image,
    out_dir: str,
    *,
    scale: float = 1.0,
    panel_height: int = 1500,
    search: int = 260,
    prefix: str = "panel",
) -> list[str]:
    """Slice ``im`` into panels ~``panel_height``*``scale`` px tall, snapping each cut to the
    quietest row within ±``search``*``scale`` px. Returns the written panel paths.

    The last piece absorbs the remainder when it would otherwise be a sliver.
    """
    os.makedirs(out_dir, exist_ok=True)
    rowvar = _row_detail(im)
    target = int(panel_height * scale)
    reach = int(search * scale)
    h = im.height

    def quiet_cut(center: int) -> int:
        lo = max(0, center - reach)
        hi = min(h, center + reach)
        band = rowvar[lo:hi]
        if band.size == 0:
            return min(center, h)
        return lo + int(band.argmin())

    paths: list[str] = []
    y = 0
    n = 1
    while y < h:
        nxt = y + target
        if h - nxt < target * 0.5:  # last piece: take the rest
            cut = h
        else:
            cut = quiet_cut(nxt)
        cut = max(cut, y + 1)  # never produce an empty / negative crop
        p = os.path.join(out_dir, f"{prefix}_{n:02d}.png")
        im.crop((0, y, im.width, cut)).save(p)
        paths.append(p)
        y = cut
        n += 1
    return paths


def finalize(
    raw_png_path: str,
    out_dir: str,
    *,
    scale: float = 1.0,
    full_name: str = "full.png",
    panel_height: int = 1500,
    make_panels: bool = True,
) -> dict:
    """Crop a raw screenshot and (optionally) slice it. Returns paths + sizes."""
    im = crop_bottom_whitespace(Image.open(raw_png_path).convert("RGB"))
    os.makedirs(out_dir, exist_ok=True)
    full_path = os.path.join(out_dir, full_name)
    im.save(full_path)
    result = {"full": full_path, "size": list(im.size), "panels": []}
    if make_panels:
        result["panels"] = slice_panels(im, out_dir, scale=scale, panel_height=panel_height)
    return result
