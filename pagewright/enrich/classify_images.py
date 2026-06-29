"""Tag each product image with a role (hero / box / lifestyle / diagram / cutout) and a short
alt caption, using vision. Roles let the composer place the right image in the right slot
(hero shot vs. a taper diagram vs. a lifestyle photo)."""

from __future__ import annotations

import os

from ..llm.base import ImageRef, get_backend
from ..spec import ProductSpec

_ROLE_SCHEMA = {
    "type": "object",
    "properties": {
        "role": {"type": "string", "enum": ["hero", "box", "lifestyle", "diagram", "cutout", "other"]},
        "alt": {"type": "string"},
    },
    "required": ["role"],
}

SYSTEM = (
    "Classify one product image. role=hero (main packshot/beauty), box (boxed/packaged product), "
    "lifestyle (in-use/context), diagram (spec chart/taper/exploded), cutout (background-removed "
    "product), other. Give a short factual alt caption. Describe only what you see."
)


def classify_images(spec: ProductSpec, *, settings, assets_dir: str) -> ProductSpec:
    backend = get_backend(settings)
    for img in spec.images:
        if img.role and img.role != "other" and img.alt:
            continue
        path = img.path if os.path.isabs(img.path) else os.path.join(assets_dir, img.path)
        if not os.path.exists(path):
            continue
        try:
            out = backend.structured(
                [ImageRef(path=path), "Classify this product image."],
                schema=_ROLE_SCHEMA, schema_name="image_role", system=SYSTEM,
            )
            img.role = out.get("role", img.role)
            if out.get("alt") and not img.alt:
                img.alt = out["alt"]
        except Exception:
            continue
    return spec
