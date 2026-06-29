"""ProductSpec — the single data contract of Pagewright.

This is the *only* thing that couples acquisition to generation. Every input path
(a scraped URL, the user's own uploads) is normalized into a ProductSpec; every
output template consumes one. Add a new source or a new template without either
side knowing about the other.

Design notes / invariants encoded here:
- Bilingual by construction: every human-facing string has an optional ``*_secondary``
  twin so a page can show 中英对照 (English verbatim + a translation). The primary
  language is whatever you author/extract in; secondary is the translation.
- Facts are real, never generated. ``icon``/``image`` point at *files on disk* (or a
  URL to download). The LLM matches features to real icons; it must not invent pixels.
- Traceable: ``citations`` and per-field ``source_url`` let a verifier check that every
  claim on the page came from somewhere.

The shape generalizes the original SA flydock data (参数信息.txt / all_products_raw.json /
the hand-built index.html): a product can be a single SKU or a *family* with several
``variants`` (the "7 builds"), a grid of ``features`` (the tech-icon cards), grouped
``attributes`` (water/temp/fishing/species chips), a ``comparison`` table, and ``guidance``
("how to choose").
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

ImageRole = Literal["hero", "box", "lifestyle", "diagram", "cutout", "other"]


class Asset(BaseModel):
    """A real visual asset. Exactly one of ``asset`` (local path, preferred) or ``url``
    (remote, to be downloaded) should be set. ``None`` means "no real asset" — render a
    text-only fallback rather than fabricating an image."""

    asset: Optional[str] = Field(None, description="Local path relative to the spec file / assets dir.")
    url: Optional[str] = Field(None, description="Remote URL to download into the assets dir.")
    alt: Optional[str] = None
    alt_secondary: Optional[str] = None

    def is_empty(self) -> bool:
        return not (self.asset or self.url)


class Brand(BaseModel):
    name: str
    name_secondary: Optional[str] = None
    abbr: Optional[str] = None  # logo monogram when there's no logo image (e.g. "SA")
    logo: Optional[Asset] = None
    tagline: Optional[str] = None
    tagline_secondary: Optional[str] = None
    origin: Optional[str] = None  # e.g. "Midland, Michigan · U.S.A."
    since: Optional[str] = None  # e.g. "1945"


class Language(BaseModel):
    primary: str = "en"
    secondary: Optional[str] = None  # e.g. "zh-CN" for 中英对照


class Meta(BaseModel):
    source_urls: list[str] = Field(default_factory=list)
    captured_at: Optional[str] = None  # ISO date; stamped by the pipeline, not the LLM
    language: Language = Field(default_factory=Language)
    brand: Optional[Brand] = None


class Option(BaseModel):
    key: str  # "weight", "color", "line-type"
    key_secondary: Optional[str] = None
    values: list[str] = Field(default_factory=list)


class Description(BaseModel):
    text: str
    text_secondary: Optional[str] = None
    source_url: Optional[str] = None


class Product(BaseModel):
    name: str
    name_secondary: Optional[str] = None
    family: Optional[str] = None  # set when this spec describes a multi-variant family
    family_secondary: Optional[str] = None
    category: Optional[str] = None
    price: Optional[str] = None
    currency: Optional[str] = None
    tagline: Optional[str] = None  # short hero punch line ("SEVEN BUILDS. ONE TAPER.")
    tagline_secondary: Optional[str] = None
    summary: Optional[str] = None
    summary_secondary: Optional[str] = None
    cta: Optional[str] = None  # closer call-to-action
    cta_secondary: Optional[str] = None
    options: list[Option] = Field(default_factory=list)
    descriptions: list[Description] = Field(default_factory=list)


class KeyStat(BaseModel):
    """A hero/closer stat chip, e.g. {k: '90FT', v: '27.5M 总长'}."""

    k: str
    v: Optional[str] = None


class Highlight(BaseModel):
    """A 'design DNA' pillar — a highlighted aspect of the product."""

    key: Optional[str] = None  # eyebrow label, e.g. "Core 线芯"
    key_secondary: Optional[str] = None
    name: str
    name_secondary: Optional[str] = None
    desc: Optional[str] = None
    desc_secondary: Optional[str] = None


class Feature(BaseModel):
    """A capability/technology shown as an icon card (e.g. AST, Welded Loops)."""

    id: str
    name: str
    name_secondary: Optional[str] = None
    desc: Optional[str] = None
    desc_secondary: Optional[str] = None
    icon: Optional[Asset] = None  # real icon only; None -> text-only card
    group: Optional[str] = None  # e.g. "Coatings & Slickness"
    group_secondary: Optional[str] = None
    used_by: list[str] = Field(default_factory=list)  # variant ids


class AttributeValue(BaseModel):
    name: str
    name_secondary: Optional[str] = None
    icon: Optional[Asset] = None


class AttributeGroup(BaseModel):
    """A taxonomy axis rendered as a chip row (e.g. Water Type / Species)."""

    group: str
    group_secondary: Optional[str] = None
    note: Optional[str] = None
    values: list[AttributeValue] = Field(default_factory=list)


class Variant(BaseModel):
    """One member of a product family — a product card in the lineup."""

    id: str
    name: str
    name_secondary: Optional[str] = None
    short: Optional[str] = None  # compact label for "used by" references, e.g. "Amp Smooth"
    category: Optional[str] = None  # series label, e.g. "Mastery Series"
    positioning: Optional[str] = None  # short tagline chip, e.g. "入门全能 · 高性价比"
    desc: Optional[str] = None
    desc_secondary: Optional[str] = None
    badges: list[str] = Field(default_factory=list)  # the small "tagm" meta chips
    feature_ids: list[str] = Field(default_factory=list)  # which Feature.id this carries
    image: Optional[Asset] = None
    price: Optional[str] = None
    rank: Optional[str] = None  # "01 ENTRY", "07 FLAGSHIP"
    flagship: bool = False


class ComparisonRow(BaseModel):
    label: str
    label_secondary: Optional[str] = None
    cells: list[str] = Field(default_factory=list)  # one per variant, in variant order
    kind: Literal["text", "bool", "rating"] = "text"  # render hint


class RefTable(BaseModel):
    """A numeric reference table (e.g. grain/head-weight by line size)."""

    title: str
    title_secondary: Optional[str] = None
    note: Optional[str] = None
    header: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)


class Comparison(BaseModel):
    columns: list[str] = Field(default_factory=list)  # variant short names, in order
    columns_secondary: list[str] = Field(default_factory=list)
    rows: list[ComparisonRow] = Field(default_factory=list)
    ref_tables: list[RefTable] = Field(default_factory=list)


class Guidance(BaseModel):
    """A "how to choose" Q→A row."""

    q: str
    q_secondary: Optional[str] = None
    a: str
    a_secondary: Optional[str] = None
    highlight: bool = False


class Image(BaseModel):
    path: str  # local path relative to assets dir
    role: ImageRole = "other"
    alt: Optional[str] = None
    alt_secondary: Optional[str] = None
    variant_id: Optional[str] = None


class Citation(BaseModel):
    claim: str
    source_url: Optional[str] = None


class Lead(BaseModel):
    """Per-section heading + intro. Keyed in ProductSpec.leads by section name
    ('highlights' | 'features' | 'attributes' | 'variants' | 'comparison' | 'guidance').
    All fields optional — anything omitted falls back to a sensible generic default."""

    eyebrow: Optional[str] = None  # small-caps line above the title
    title: Optional[str] = None  # primary big title
    title_secondary: Optional[str] = None  # shown as the main title when bilingual
    subtitle: Optional[str] = None  # small latin line under the title
    text: Optional[str] = None  # intro paragraph
    text_secondary: Optional[str] = None


class ProductSpec(BaseModel):
    """The full normalized description of a product (or product family)."""

    model_config = {"extra": "forbid"}

    meta: Meta = Field(default_factory=Meta)
    product: Product
    hero_stats: list[KeyStat] = Field(default_factory=list)
    highlights: list[Highlight] = Field(default_factory=list)  # "design DNA" pillars
    features: list[Feature] = Field(default_factory=list)
    attributes: list[AttributeGroup] = Field(default_factory=list)
    variants: list[Variant] = Field(default_factory=list)
    comparison: Optional[Comparison] = None
    guidance: list[Guidance] = Field(default_factory=list)
    images: list[Image] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    leads: dict[str, Lead] = Field(default_factory=dict)  # per-section intro paragraphs

    # ---- convenience helpers used by composer/verify --------------------------------
    def feature_by_id(self, fid: str) -> Optional[Feature]:
        return next((f for f in self.features if f.id == fid), None)

    def all_assets(self) -> list[Asset]:
        """Every Asset referenced anywhere — used by acquire/images to download, and by
        verify to confirm each one resolves to a real file."""
        out: list[Asset] = []
        if self.meta.brand and self.meta.brand.logo:
            out.append(self.meta.brand.logo)
        for f in self.features:
            if f.icon:
                out.append(f.icon)
        for g in self.attributes:
            for v in g.values:
                if v.icon:
                    out.append(v.icon)
        for v in self.variants:
            if v.image:
                out.append(v.image)
        return out

    @classmethod
    def json_schema_str(cls) -> str:
        """JSON Schema for the LLM's structured-output tool (see llm/base.py)."""
        import json

        return json.dumps(cls.model_json_schema(), ensure_ascii=False, indent=2)


def load_spec(path: str) -> ProductSpec:
    import json
    from pathlib import Path

    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return ProductSpec.model_validate(data)


def dump_spec(spec: ProductSpec, path: str) -> None:
    from pathlib import Path

    Path(path).write_text(
        spec.model_dump_json(indent=2, exclude_none=True), encoding="utf-8"
    )
