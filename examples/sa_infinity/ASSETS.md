# Assets for the SA Infinity example are NOT included

This example ships only `product_spec.json`, `theme.toml`, and `run.sh`. The icons and product
photos it references are **Scientific Anglers' copyrighted material**, so they are intentionally
**not committed** to this repository (see `.gitignore` → `examples/*/assets/`).

`product_spec.json` references files under `assets/`:

```
assets/icons/*.png        # 17 official technology icons (200×200)
assets/icons/attr/*.jpg   # attribute icons (water / temp / fishing / species)
assets/products/*.png     # 7 product packshots (transparent cut-outs)
```

To run this example locally, place the corresponding image files at those paths (you can pull
them from the official product/technology pages with `pagewright acquire`, for your own
authorized use), then:

```bash
bash run.sh          # → output/full.png
```

If an asset is missing, Pagewright simply renders a text-only fallback for that card — the page
still builds, just without those images. This is by design: **Pagewright never fabricates a
missing icon or photo.**

> Want a runnable example with no copyright caveats? Use `examples/manual_demo/` and drop your
> own product images into `examples/manual_demo/images/`.
