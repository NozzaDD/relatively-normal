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

## Added 21 September 2026 — the catalogue run

| Script | What it does |
|---|---|
| `contact_sheet.py` | grids of images on mid-grey, for checking many at once by eye |
| `colour_stability.py` | how far two screenshots of one product disagree about its colour |
| `crop_figures.py` | crops a whole-figure cut-out down to the band where its own slot sits |
| `asset_quality.py` | marks an asset weak when it is mostly skin and hair, or a rectangle |
| `inspiration_colours.py` | clothes-only colours for the inspiration images |
| `build_inspiration.py` | writes `inspiration.csv` |
| `coverage.py` | writes `coverage.csv` — which product can carry which colour in which slot |
| `pick_boards.py` | chooses the pieces for a board and runs the acceptance test |
| `make_boards.py` | renders a board to style-spec part B4 and B5 |
| `build_boards.py` | the six board specs, and the renders |
| `note_visuals.py` | re-renders the four made visuals without engine numbers |
| `boards_readme.py` | the review page for `content/boards/v2` |
| `slot_sheets.py` | one sheet per slot for the catalogue README |
| `brand_questions.py` | one question per batch, not per product |
| `catalogue_readme.py` | the catalogue README, with its counts computed |
| `mark_used.py` | writes `used_in` back into the CSVs |

Order to re-run the whole thing from the index: `cluster_products.py` →
`make_assets.py` → `crop_figures.py` → `extract_colours.py` → `asset_quality.py`
→ `build_products.py` → `inspiration_colours.py` → `build_inspiration.py` →
`coverage.py` → `build_boards.py` → `note_visuals.py` → `slot_sheets.py` →
`brand_questions.py` → `catalogue_readme.py` → `boards_readme.py` →
`mark_used.py`.

Two design notes worth keeping:

- **Background is a topological fact, not a colour one.** The first colour pass
  masked every pixel close to the backdrop and quietly deleted pale garments; the
  mask now flood-fills inward from the border instead.
- **Find the product by content, not by empty space.** The first asset pass looked
  for the largest low-edge block on the page, which on a shop page is just as
  often the margin below the photo. A third of the first tiles came out blank.
