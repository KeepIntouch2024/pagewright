"""LLM extraction → ProductSpec.

The model reads the captured page text + screenshots and returns a schema-valid ProductSpec.
No per-site selectors — structure comes from the model reading the page.

Two invariants are enforced *in code*, not left to the prompt:
  - Provenance/language/timestamp are stamped by us afterward (never invented by the model).
  - Every asset path the model emits must be one of the real downloaded files; anything else
    is nulled out. The model can reference images but cannot fabricate them.
"""

from __future__ import annotations

import os
from typing import Optional

from ..llm.base import ImageRef, get_backend
from ..spec import ProductSpec

MAX_TEXT_CHARS = 24000
MAX_SHOTS = 3

SYSTEM = (
    "You are a meticulous e-commerce data extractor. From the supplied product page material, "
    "produce a ProductSpec. Rules: (1) Use ONLY facts present in the material — never invent "
    "prices, specs, features, or marketing claims. (2) If a field is unknown, omit it. "
    "(3) For any image/icon, reference ONLY a path from the provided 'Available local images' "
    "list; if none fits, omit the asset (do NOT make up a filename or URL). (4) Put the source "
    "language text in the base fields; leave *_secondary empty unless the page itself is "
    "bilingual. (5) Group related capabilities into 'features' and taxonomy tags into "
    "'attributes'. Use a 'variant' per purchasable model when the page covers several."
)


def extract_from_capture(
    work_dir: str,
    *,
    settings,
    primary: str = "en",
    secondary: Optional[str] = None,
) -> ProductSpec:
    from ..acquire.fetcher import RawCapture

    cap = RawCapture.load(work_dir)
    parts: list = []
    text = (cap.text or "")[:MAX_TEXT_CHARS]
    parts.append(
        f"SOURCE URL: {cap.url}\nPAGE TITLE: {cap.title}\n\nPAGE TEXT:\n{text}"
    )
    for shot in cap.screenshots[:MAX_SHOTS]:
        if os.path.exists(shot):
            parts.append(ImageRef(path=shot))

    allowed = [p for p in cap.downloaded_images if os.path.exists(p)]
    inventory = "\n".join(f"- {p}" for p in allowed) or "(none downloaded)"
    parts.append("Available local images (reference these exact paths only):\n" + inventory)

    return _run(parts, allowed, settings, primary, secondary, source_urls=[cap.url])


def _run(parts, allowed_images, settings, primary, secondary, source_urls) -> ProductSpec:
    backend = get_backend(settings)
    schema = ProductSpec.model_json_schema()
    data = backend.structured(parts, schema=schema, schema_name="ProductSpec", system=SYSTEM)

    spec = ProductSpec.model_validate(data)
    _sanitize_assets(spec, set(allowed_images))
    # stamp provenance / language ourselves (not the model's job)
    spec.meta.source_urls = list(dict.fromkeys(source_urls + spec.meta.source_urls))
    spec.meta.language.primary = primary
    if secondary:
        spec.meta.language.secondary = secondary
    return spec


def _sanitize_assets(spec: ProductSpec, allowed: set[str]) -> None:
    """Null any asset path the model emitted that isn't a real downloaded file. Remote URLs are
    left intact (they get downloaded later); only invented *local* paths are scrubbed."""

    def fix(asset):
        if asset is None:
            return
        if asset.asset and asset.asset not in allowed and not os.path.exists(asset.asset):
            asset.asset = None

    if spec.meta.brand:
        fix(spec.meta.brand.logo)
    for f in spec.features:
        fix(f.icon)
    for g in spec.attributes:
        for v in g.values:
            fix(v.icon)
    for v in spec.variants:
        fix(v.image)
