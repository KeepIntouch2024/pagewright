"""Pagewright — LLM-orchestrated e-commerce poster / 详情页 generator.

Pipeline:  acquire → extract → enrich → compose → render → verify
Contract:  pagewright.spec.ProductSpec couples them and nothing else.

Core invariant: the LLM understands, writes, translates and lays out — it never
generates factual pixels. Icons, photos and spec numbers are real assets rendered
deterministically via HTML→PNG. (This is why the project exists: AI-painted icons
hallucinate; real-asset HTML is pixel-accurate and verifiable.)
"""

from .spec import ProductSpec, load_spec, dump_spec  # noqa: F401

__version__ = "0.1.0"
__all__ = ["ProductSpec", "load_spec", "dump_spec", "__version__"]
