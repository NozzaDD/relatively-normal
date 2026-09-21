# content/tools/

Reusable scripts for the swipe library and the boards. Committed so later runs
do not rewrite them. All of them import the engine's colour module read-only;
none writes to `content/swipe/`, and no original image is ever moved, renamed,
deleted or re-encoded.

| Script | What it does |
|---|---|
| `imglib.py` | Shared helpers: iOS/Safari chrome trim, in-page lightbox trim, dHash, white balance against a studio backdrop, skin band, `rembg` cut-out with alpha hard-threshold and connected-component tidy-up. |
| `colour_names.py` | The fixed colour vocabulary — 13 families and a closed list of plain names, assigned from CIELAB LCh plus the engine's relative chroma. `python3 content/tools/colour_names.py` prints a self-test. |
| `cluster_products.py` | Clusters product screenshots into shop **batches** (layout change + legible-brand change) and, inside a batch, into **products** (adjacent shots of one garment). Writes `content/catalogue/batches.json`. Caches per-image signatures in `content/catalogue/_signatures.json`. |
| `render_views.py` | Renders one readable image per product for the viewing pass. |
| `make_assets.py` | One usable image per product: flat cut-out → on-model cut-out → crop tile, as WebP under 1200px. Driven by the `shot_type` recorded in the viewing pass. |

## Dependencies

`pip install Pillow rembg` — the `u2net` model downloads on first use (~176 MB).

## Notes

- `keep_main_blobs` uses a deliberately low relative threshold (0.06). A second
  shoe, a strap or a belt is a small but real component, and an aggressive
  filter deletes exactly those.
- The skin band in `imglib.is_skin` overlaps genuinely warm garment colours
  (rose, salmon, tan). Callers record how much was masked rather than trusting
  it silently — CLAUDE.md hard rule 6.
