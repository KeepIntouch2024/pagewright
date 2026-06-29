"""Background removal for product photos (rembg / U2Net) → transparent PNG.

Mirrors the source project's packshot cut-outs (the `.png` alongside each `.jpg`). Operates on
variant images and any spec.images tagged hero/box/cutout. The original file is kept; a sibling
``*.png`` cut-out is written and the spec is repointed to it.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from ..spec import ProductSpec


def _cutout_file(src_abs: str) -> Optional[str]:
    try:
        from rembg import remove
        from PIL import Image
    except ImportError as e:  # pragma: no cover
        raise ImportError("Cut-out needs rembg: pip install 'pagewright[cutout]'") from e
    out_abs = str(Path(src_abs).with_suffix(".cutout.png"))
    if os.path.exists(out_abs):
        return out_abs
    with Image.open(src_abs) as im:
        res = remove(im.convert("RGBA"))
        res.save(out_abs)
    return out_abs


def cutout(spec: ProductSpec, *, assets_dir: str) -> ProductSpec:
    def process(asset):
        if asset is None or asset.is_empty() or not asset.asset:
            return
        src = asset.asset if os.path.isabs(asset.asset) else os.path.join(assets_dir, asset.asset)
        if not os.path.exists(src):
            return
        out_abs = _cutout_file(src)
        if out_abs:
            asset.asset = os.path.relpath(out_abs, assets_dir) if not os.path.isabs(asset.asset) else out_abs

    for v in spec.variants:
        process(v.image)
    return spec
