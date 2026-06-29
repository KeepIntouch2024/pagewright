"""Generation library — a persistent, local archive of every poster you make.

Each generation is saved under ``~/.pagewright/library/<entry-id>/`` with its full image, panels,
the ProductSpec that produced it, a thumbnail, and a ``meta.json``. Generations of the same
product are grouped by a ``project`` key and numbered as versions (v1, v2, …) so you can browse
history, re-download, delete, compare, or re-render an old spec into a new version.

Everything is local files — no database, no cloud. The desktop app's History panel and the
``pagewright library`` CLI both read this.
"""

from __future__ import annotations

import datetime
import json
import re
import shutil
import uuid
from pathlib import Path
from typing import Optional

LIB_DIR = Path.home() / ".pagewright" / "library"
THUMB_W = 380
THUMB_MAX_H = 460  # long images are cropped to a representative top slice for the grid


def _now_iso() -> str:
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def _stamp() -> str:
    return datetime.datetime.now().strftime("%Y%m%d-%H%M%S")


def slug(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"[^\w一-鿿]+", "-", s).strip("-")
    return s or "untitled"


def _all_meta() -> list[dict]:
    if not LIB_DIR.exists():
        return []
    out = []
    for d in LIB_DIR.iterdir():
        m = d / "meta.json"
        if m.is_file():
            try:
                out.append(json.loads(m.read_text(encoding="utf-8")))
            except Exception:
                continue
    return out


def _next_version(project: str) -> int:
    return sum(1 for m in _all_meta() if m.get("project") == project) + 1


def _make_thumb(full_png: Path, dest: Path) -> Optional[str]:
    try:
        from PIL import Image

        with Image.open(full_png) as im:
            im = im.convert("RGB")
            w, h = im.size
            tw = THUMB_W
            th = int(h * tw / w)
            im = im.resize((tw, th))
            if th > THUMB_MAX_H:  # crop to a representative top slice for tall detail pages
                im = im.crop((0, 0, tw, THUMB_MAX_H))
            im.save(dest, "PNG")
        return dest.name
    except Exception:
        return None


def archive(
    output_dir: str,
    spec,
    *,
    title: Optional[str] = None,
    mode: Optional[str] = None,
    source_url: Optional[str] = None,
    target_lang: Optional[str] = None,
    theme: Optional[str] = None,
    model: Optional[str] = None,
) -> dict:
    """Copy a rendered output dir + its spec into the library as a new versioned entry."""
    from .spec import dump_spec

    LIB_DIR.mkdir(parents=True, exist_ok=True)
    eid = f"{_stamp()}-{uuid.uuid4().hex[:4]}"
    dest = LIB_DIR / eid
    dest.mkdir(parents=True, exist_ok=True)

    out = Path(output_dir)
    files: dict = {"panels": []}
    full = out / "full.png"
    full_size = None
    if full.exists():
        shutil.copy2(full, dest / "full.png")
        files["full"] = "full.png"
        thumb = _make_thumb(dest / "full.png", dest / "thumb.png")
        if thumb:
            files["thumb"] = thumb
        try:
            from PIL import Image

            with Image.open(full) as im:
                full_size = list(im.size)
        except Exception:
            pass
    for p in sorted(out.glob("panel_*.png")):
        shutil.copy2(p, dest / p.name)
        files["panels"].append(p.name)

    # Make the entry self-contained: copy every local asset the spec references into
    # <entry>/assets/ and rewrite the spec's paths to be relative — so an old version still
    # renders after the original temp files (or downloads) are gone. Remote-only assets are left.
    _embed_assets(spec, dest)
    dump_spec(spec, str(dest / "spec.json"))
    files["spec"] = "spec.json"

    name = title or spec.product.name or "untitled"
    project = slug(spec.product.name or title or "untitled")
    meta = {
        "id": eid,
        "created_at": _now_iso(),
        "title": name,
        "title_secondary": getattr(spec.product, "name_secondary", None),
        "project": project,
        "version": _next_version(project),
        "mode": mode,
        "source_url": source_url,
        "target_lang": target_lang,
        "theme": theme,
        "model": model,
        "full_size": full_size,
        "n_panels": len(files["panels"]),
        "files": files,
    }
    (dest / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta


def _embed_assets(spec, dest: Path) -> None:
    import os

    adir = dest / "assets"
    mapping: dict[str, str] = {}  # source path -> relative dest path
    n = 0
    for a in spec.all_assets():
        if not a.asset:
            continue
        src = a.asset if os.path.isabs(a.asset) else a.asset
        sp = Path(src)
        if not sp.is_file():
            continue
        key = str(sp.resolve())
        if key in mapping:
            a.asset = mapping[key]
            continue
        adir.mkdir(parents=True, exist_ok=True)
        name = f"{n:03d}_{re.sub(r'[^A-Za-z0-9._-]', '_', sp.name)[-50:]}"
        shutil.copy2(sp, adir / name)
        rel = f"assets/{name}"
        mapping[key] = rel
        a.asset = rel
        n += 1


def list_entries() -> list[dict]:
    """Newest first."""
    return sorted(_all_meta(), key=lambda m: m.get("created_at", ""), reverse=True)


def get(entry_id: str) -> Optional[dict]:
    m = LIB_DIR / entry_id / "meta.json"
    if m.is_file():
        return json.loads(m.read_text(encoding="utf-8"))
    return None


def entry_dir(entry_id: str) -> Path:
    return LIB_DIR / entry_id


def file_path(entry_id: str, name: str) -> Optional[Path]:
    """Resolve a file inside an entry, basename-guarded (no traversal)."""
    d = (LIB_DIR / entry_id).resolve()
    p = (d / Path(name).name).resolve()
    if p.is_file() and str(p).startswith(str(d)):
        return p
    return None


def delete(entry_id: str) -> bool:
    d = LIB_DIR / entry_id
    if d.is_dir() and (d / "meta.json").exists():
        shutil.rmtree(d, ignore_errors=True)
        return True
    return False


def grouped() -> list[dict]:
    """Entries grouped by project, each project's versions newest-first."""
    groups: dict[str, dict] = {}
    for m in list_entries():
        g = groups.setdefault(m["project"], {"project": m["project"], "title": m["title"], "entries": []})
        g["entries"].append(m)
    return list(groups.values())
