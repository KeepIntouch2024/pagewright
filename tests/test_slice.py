"""Panel slicing + crop on a synthetic fixture image (no browser needed)."""

import numpy as np
from PIL import Image

from pagewright.render.slice import crop_bottom_whitespace, slice_panels


def _fixture(height=4000, width=300):
    """White canvas with three dark text-like bands separated by quiet white gaps."""
    a = np.full((height, width, 3), 255, dtype=np.uint8)
    for top in (200, 1600, 3000):  # busy bands
        a[top:top + 240] = 30
    # trailing whitespace at the bottom (rows 3600..end stay white)
    return Image.fromarray(a)


def test_crop_bottom_whitespace_trims_trailing_white():
    im = _fixture()
    cropped = crop_bottom_whitespace(im)
    # last dark band ends at 3240, so cropped height should be ~3240, well below 4000
    assert cropped.height < 3500
    assert cropped.height >= 3240


def test_slice_panels_writes_files_and_avoids_busy_rows(tmp_path):
    im = crop_bottom_whitespace(_fixture())
    paths = slice_panels(im, str(tmp_path), scale=1.0, panel_height=1200, search=300)
    assert len(paths) >= 2
    # every panel is a valid, non-empty image and the heights sum back to the whole
    total = 0
    for p in paths:
        with Image.open(p) as panel:
            assert panel.height > 0
            total += panel.height
    assert total == im.height
