"""Manual path — the user drops a folder of images + a description, and the LLM normalizes it
into the very same ProductSpec the URL path produces. Downstream stages don't know the
difference.

Folder convention (all optional except at least one of images/description):
    mydir/
      description.md          (or description.txt) — free-form copy, specs, bullet points
      *.jpg / *.png / ...     — product photos (read with vision, referenced by local path)
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from ..llm.base import ImageRef
from ..spec import ProductSpec
from .extractor import _run

_IMG_EXT = (".jpg", ".jpeg", ".png", ".webp", ".avif")
_DESC_NAMES = ("description.md", "description.txt", "desc.md", "desc.txt", "README.md")
MAX_IMAGES = 12


def _find_description(folder: Path) -> str:
    for n in _DESC_NAMES:
        p = folder / n
        if p.exists():
            return p.read_text(encoding="utf-8")
    # else concatenate any .md/.txt
    chunks = [p.read_text(encoding="utf-8") for p in folder.glob("*.txt")]
    chunks += [p.read_text(encoding="utf-8") for p in folder.glob("*.md")]
    return "\n\n".join(chunks)


def _find_images(folder: Path) -> list[str]:
    imgs = sorted(
        str(p.resolve()) for p in folder.rglob("*")  # absolute → resolves regardless of cwd
        if p.suffix.lower() in _IMG_EXT and p.is_file()
    )
    return imgs[:MAX_IMAGES]


def extract_manual(
    folder: str,
    *,
    settings,
    primary: str = "en",
    secondary: Optional[str] = None,
) -> ProductSpec:
    fp = Path(folder)
    if not fp.is_dir():
        raise NotADirectoryError(folder)
    desc = _find_description(fp)
    images = _find_images(fp)
    if not desc and not images:
        raise ValueError(f"{folder} has no description.md/.txt and no images.")

    parts: list = []
    if desc:
        parts.append("PRODUCT DESCRIPTION (author-provided):\n" + desc)
    for img in images:
        parts.append(ImageRef(path=img))
    inventory = "\n".join(f"- {p}" for p in images) or "(none)"
    parts.append(
        "Available local images (reference these exact paths only; assign each a role and, "
        "if it is a packshot of a specific variant, attach it to that variant):\n" + inventory
    )

    return _run(parts, images, settings, primary, secondary, source_urls=[])
