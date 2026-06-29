# North Face Nuptse example — product photos NOT included

This example ships only `product_spec.json` and `theme.toml`. The product photos it references
are **The North Face's copyrighted images**, so they are intentionally **not committed** to this
repository (`.gitignore` → `examples/*/assets/`).

`product_spec.json` references:

```
assets/products/hero.png   # front (Lava Red / TNF Black)
assets/products/alt.png    # detail
assets/products/back.png   # back
```

This spec was produced by reading the live product page (Akamai-protected, so via a real browser
— Pagewright's tier-3 acquisition) and downloading the photos from the open image CDN
(`assets.thenorthface.com`) at run time. To reproduce locally, place the three images at the
paths above (use them only for your own authorized purposes), then:

```bash
bash run.sh          # → output/full.png  (cool theme, bilingual)
```

If the images are missing, Pagewright renders the layout with text/monogram fallbacks — the page
still builds. **Pagewright never fabricates a product photo.**

> Real product data shown (price, 700-fill down, colorways, sizes, official benefit ratings,
> description) belongs to The North Face and is used here only to demonstrate the tool.
