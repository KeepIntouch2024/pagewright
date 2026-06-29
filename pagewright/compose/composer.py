"""ProductSpec + theme → a single self-contained HTML page (data inlined).

The page is assembled from a block library (blocks/*.html) over a base shell (base.html)
whose CSS is driven by theme tokens (CSS custom properties). Sections appear only when the
spec has the data for them, and the numbered content sections (Design DNA / Technologies /
Attributes / Builds / Comparison / How-to-choose) are auto-renumbered 01..0N accordingly.

Assets are referenced by absolute file path so the rendered screenshot resolves icons and
photos no matter where the .html is written. The LLM never authors this HTML — it only
produces the ProductSpec; composition is deterministic and reviewable.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Union

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..spec import Asset, ProductSpec

_HERE = Path(__file__).parent

try:  # py311+
    import tomllib as _toml
except ModuleNotFoundError:  # pragma: no cover
    import tomli as _toml  # type: ignore

# Mirrors the original 详情页_v2 palette so the SA example reproduces 1:1.
DEFAULT_THEME: dict = {
    "colors": {
        "red": "#D81E05", "red2": "#B5160A",
        "ink": "#1b1b1b", "ink2": "#2a2a2a",
        "paper": "#FBF8F2", "cream": "#F3ECDF", "cream2": "#EDE4D3",
        "teal": "#0B4F48", "gold": "#A9823C",
        "muted": "#7a7468", "line": "#e4ddcd", "line2": "#d8cfbb",
        "dark": "#161616",
    },
    "fonts": {
        "cjk": '"PingFang SC","Noto Sans SC","Hiragino Sans GB","Microsoft YaHei",sans-serif',
        "latin": '"Helvetica Neue",Helvetica,Arial,sans-serif',
    },
    "layout": {"width": 750},
}


def load_theme(path: Optional[str]) -> dict:
    theme = {k: dict(v) if isinstance(v, dict) else v for k, v in DEFAULT_THEME.items()}
    if path:
        data = _toml.loads(Path(path).read_text(encoding="utf-8"))
        for k, v in data.items():
            if isinstance(v, dict) and isinstance(theme.get(k), dict):
                theme[k].update(v)
            else:
                theme[k] = v
    return theme


def _make_env(assets_dir: Path) -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(_HERE)),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )

    def asset_url(a: Union[Asset, str, None]) -> str:
        """Resolve an Asset (or raw path) to an absolute file path for <img src>."""
        if a is None:
            return ""
        path = a if isinstance(a, str) else (a.asset or a.url or "")
        if not path:
            return ""
        if path.startswith(("http://", "https://", "file://", "data:")):
            return path
        p = Path(path)
        if not p.is_absolute():
            p = (assets_dir / path).resolve()
        return p.as_uri()

    def has_asset(a: Union[Asset, None]) -> bool:
        return a is not None and not a.is_empty()

    env.globals["asset_url"] = asset_url
    env.globals["has_asset"] = has_asset
    env.filters["safe_inline"] = safe_inline
    return env


# Spec text may carry intentional light formatting (<b>, <i>, <br>, <sub>, <span class="…">).
# But spec text can also come from an LLM reading an untrusted web page, so a raw |safe would
# let a malicious page inject <script>/<img onerror> into the rendered HTML (which is then
# screenshotted by a headless browser). safe_inline HTML-escapes everything, then re-permits
# ONLY that small whitelist of inline tags. No <script>, no event handlers, no <img>, no href.
import re as _re
from markupsafe import Markup, escape as _escape

# Allowed inline tags, each with an OPTIONAL safe class attr (single/double quoted, after
# escaping the quotes become &#34;/&#39;). The class value is restricted to word/space/hyphen,
# so no quotes/brackets can break out — no <script>, no event handlers, no href/style.
_ALLOWED_TAGS = _re.compile(
    r"&lt;/?(?:b|i|em|strong|sub|sup|span)"
    r"(?:\s+class=(?:&#34;|&#39;)[\w \-]{0,40}(?:&#34;|&#39;))?\s*&gt;"
    r"|&lt;br\s*/?&gt;"
)


def _restore(m):
    return (m.group(0).replace("&lt;", "<").replace("&gt;", ">")
            .replace("&#34;", '"').replace("&#39;", "'"))


def safe_inline(value) -> Markup:
    if value is None:
        return Markup("")
    return Markup(_ALLOWED_TAGS.sub(_restore, str(_escape(value))))


def _make_name_lookup(spec: ProductSpec):
    vmap = {v.id: (v.short or v.name) for v in spec.variants}
    all_ids = {v.id for v in spec.variants}
    zh = bool(spec.meta.language.secondary)

    def names_for(ids: list[str]) -> str:
        if len(ids) > 1 and set(ids) == all_ids:
            return f"全部 {len(all_ids)} 款" if zh else f"all {len(all_ids)}"
        return " / ".join(vmap.get(i, i) for i in ids)

    return names_for


def _section_numbers(spec: ProductSpec) -> dict[str, str]:
    order = []
    if spec.highlights:
        order.append("highlights")
    if spec.features:
        order.append("features")
    if spec.attributes:
        order.append("attributes")
    if spec.variants:
        order.append("variants")
    if spec.comparison:
        order.append("comparison")
    if spec.guidance:
        order.append("guidance")
    return {name: f"{i + 1:02d}" for i, name in enumerate(order)}


def _source_hosts(spec: ProductSpec) -> list[str]:
    from urllib.parse import urlsplit

    hosts: list[str] = []
    for u in spec.meta.source_urls:
        h = urlsplit(u).netloc
        if h and h not in hosts:
            hosts.append(h)
    return hosts


def _grouped_features(spec: ProductSpec) -> list[dict]:
    """Features grouped by .group, preserving first-seen order (for the icon grid)."""
    groups: list[dict] = []
    index: dict[str, dict] = {}
    for f in spec.features:
        key = f.group or ""
        if key not in index:
            g = {"group": f.group, "group_secondary": f.group_secondary, "feats": []}
            index[key] = g
            groups.append(g)
        index[key]["feats"].append(f)
    return groups


def compose(
    spec: ProductSpec,
    *,
    assets_dir: Optional[str] = None,
    theme_path: Optional[str] = None,
) -> str:
    """Render the full page HTML string."""
    base = Path(assets_dir).resolve() if assets_dir else Path.cwd()
    env = _make_env(base)
    env.globals["names_for"] = _make_name_lookup(spec)
    theme = load_theme(theme_path)
    if "layout" in theme and "width" in theme["layout"]:
        width = int(theme["layout"]["width"])
    else:
        width = 750

    ctx = {
        "s": spec,
        "p": spec.product,
        "brand": spec.meta.brand,
        "lang": spec.meta.language,
        "bilingual": bool(spec.meta.language.secondary),
        "theme": theme,
        "colors": theme["colors"],
        "fonts": theme["fonts"],
        "width": width,
        "no": _section_numbers(spec),
        "feature_groups": _grouped_features(spec),
        "vname": {v.id: v.name for v in spec.variants},
        "flag_col": next((i for i, v in enumerate(spec.variants) if v.flagship), None),
        "source_hosts": _source_hosts(spec),
    }
    return env.get_template("base.html").render(**ctx)


def compose_to_file(
    spec: ProductSpec,
    out_html: str,
    *,
    assets_dir: Optional[str] = None,
    theme_path: Optional[str] = None,
) -> str:
    html = compose(spec, assets_dir=assets_dir, theme_path=theme_path)
    os.makedirs(os.path.dirname(os.path.abspath(out_html)), exist_ok=True)
    Path(out_html).write_text(html, encoding="utf-8")
    return out_html
