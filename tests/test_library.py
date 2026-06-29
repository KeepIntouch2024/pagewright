"""Generation library: archiving, versioning, self-contained assets, traversal guard."""

from pathlib import Path

import numpy as np
from PIL import Image

from pagewright import library
from pagewright.spec import Asset, Product, ProductSpec, Variant


def _fake_output(tmp: Path, color=(20, 40, 80)) -> str:
    out = tmp / "output"
    out.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.full((3000, 1350, 3), color, dtype=np.uint8)).save(out / "full.png")
    for i in range(1, 3):
        Image.fromarray(np.full((1200, 1350, 3), color, dtype=np.uint8)).save(out / f"panel_{i:02d}.png")
    return str(out)


def _spec(tmp: Path) -> ProductSpec:
    asset = tmp / "photo.png"
    Image.fromarray(np.zeros((600, 600, 3), dtype=np.uint8)).save(asset)
    return ProductSpec(product=Product(name="Demo Bottle"),
                       variants=[Variant(id="v1", name="500ml", image=Asset(asset=str(asset)))])


def test_archive_versions_and_self_contained(tmp_path, monkeypatch):
    monkeypatch.setattr(library, "LIB_DIR", tmp_path / "library")

    m1 = library.archive(_fake_output(tmp_path / "a"), _spec(tmp_path), mode="manual", theme="editorial")
    m2 = library.archive(_fake_output(tmp_path / "b"), _spec(tmp_path), mode="manual", theme="cool")
    assert m1["version"] == 1 and m2["version"] == 2
    assert m1["project"] == m2["project"] == "demo-bottle"

    # entry is self-contained: the variant image was copied in and the spec path rewritten
    from pagewright.spec import load_spec

    spec = load_spec(str(library.entry_dir(m1["id"]) / "spec.json"))
    rel = spec.variants[0].image.asset
    assert rel.startswith("assets/")
    assert (library.entry_dir(m1["id"]) / rel).exists()
    assert (library.entry_dir(m1["id"]) / "thumb.png").exists()


def test_list_group_and_delete(tmp_path, monkeypatch):
    monkeypatch.setattr(library, "LIB_DIR", tmp_path / "library")
    library.archive(_fake_output(tmp_path / "a"), _spec(tmp_path))
    library.archive(_fake_output(tmp_path / "b"), _spec(tmp_path))
    assert len(library.list_entries()) == 2
    groups = library.grouped()
    assert len(groups) == 1 and len(groups[0]["entries"]) == 2

    eid = library.list_entries()[0]["id"]
    assert library.delete(eid) is True
    assert len(library.list_entries()) == 1


def test_file_path_traversal_guard(tmp_path, monkeypatch):
    monkeypatch.setattr(library, "LIB_DIR", tmp_path / "library")
    m = library.archive(_fake_output(tmp_path / "a"), _spec(tmp_path))
    assert library.file_path(m["id"], "full.png") is not None
    assert library.file_path(m["id"], "../../etc/passwd") is None
