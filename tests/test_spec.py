"""ProductSpec contract: schema generation, round-trip, and the SA example validates."""

import json
from pathlib import Path

from pagewright.spec import ProductSpec, dump_spec, load_spec

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "sa_infinity" / "product_spec.json"


def test_json_schema_has_top_level_fields():
    schema = json.loads(ProductSpec.json_schema_str())
    for key in ("product", "features", "variants", "attributes", "comparison"):
        assert key in schema["properties"]


def test_sa_example_loads_and_is_complete():
    spec = load_spec(str(EXAMPLE))
    assert len(spec.variants) == 7
    assert len(spec.features) == 12
    assert len(spec.attributes) == 4
    assert spec.comparison and len(spec.comparison.rows) == 8
    assert len(spec.guidance) == 8
    # the flagship is marked
    assert any(v.flagship for v in spec.variants)
    # every variant feature_id resolves
    feat_ids = {f.id for f in spec.features}
    for v in spec.variants:
        for fid in v.feature_ids:
            assert fid in feat_ids


def test_round_trip(tmp_path):
    spec = load_spec(str(EXAMPLE))
    out = tmp_path / "spec.json"
    dump_spec(spec, str(out))
    again = load_spec(str(out))
    assert again.product.name == spec.product.name
    assert len(again.features) == len(spec.features)


def test_all_assets_collects_icons_and_images():
    spec = load_spec(str(EXAMPLE))
    assets = spec.all_assets()
    # 12 feature icons + 18 attribute icons (1+3+5+9) + 7 variant images = 37
    assert len(assets) == 12 + 18 + 7
