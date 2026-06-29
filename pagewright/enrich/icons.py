"""Match features/attributes to REAL icon assets — never generate an icon.

You supply an icon library (a directory of image files, optionally with a ``catalog.json`` of
``{filename: {label, group}}`` like the source project's ``downloads/_icons``). For each feature
or attribute value lacking an icon, we pick the best-matching real file by label similarity. If
nothing clears the threshold, the icon stays ``None`` and the card renders text-only. This is the
anti-hallucination rule from the source project, enforced in code.
"""

from __future__ import annotations

import json
import os
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional

from ..spec import Asset, ProductSpec

_IMG_EXT = (".png", ".jpg", ".jpeg", ".webp", ".svg")
_THRESHOLD = 0.62


def _norm(s: str) -> str:
    return "".join(ch for ch in s.lower() if ch.isalnum() or ch.isspace()).strip()


def _load_library(icon_dir: str) -> list[tuple[str, str]]:
    """Return [(label, path)] from catalog.json if present, else from filenames."""
    d = Path(icon_dir)
    cat = d / "catalog.json"
    out: list[tuple[str, str]] = []
    if cat.exists():
        data = json.loads(cat.read_text(encoding="utf-8"))
        for fn, info in data.items():
            label = info.get("label", fn) if isinstance(info, dict) else str(info)
            out.append((label, str(d / fn)))
    else:
        for p in d.rglob("*"):
            if p.suffix.lower() in _IMG_EXT and p.is_file():
                out.append((p.stem.replace("-", " ").replace("_", " "), str(p)))
    return out


def _best(label: str, library: list[tuple[str, str]]) -> Optional[str]:
    target = _norm(label)
    best_score, best_path = 0.0, None
    for lib_label, path in library:
        score = SequenceMatcher(None, target, _norm(lib_label)).ratio()
        # boost on token containment (e.g. "AST Plus" vs "ast-plus")
        if target and (_norm(lib_label) in target or target in _norm(lib_label)):
            score = max(score, 0.9)
        if score > best_score:
            best_score, best_path = score, path
    return best_path if best_score >= _THRESHOLD else None


def match_icons(spec: ProductSpec, *, icon_dir: str, assets_dir: Optional[str] = None) -> ProductSpec:
    if not os.path.isdir(icon_dir):
        raise NotADirectoryError(f"icon library not found: {icon_dir}")
    library = _load_library(icon_dir)
    base = Path(assets_dir) if assets_dir else None

    def rel(path: str) -> str:
        if base:
            try:
                return os.path.relpath(path, base)
            except ValueError:
                return path
        return path

    def ensure(obj_has_icon, name: str):
        if obj_has_icon.icon and not obj_has_icon.icon.is_empty():
            return
        hit = _best(name, library)
        if hit:
            obj_has_icon.icon = Asset(asset=rel(hit), alt=name)

    for f in spec.features:
        ensure(f, f.name)
    for g in spec.attributes:
        for v in g.values:
            ensure(v, v.name)
    return spec
