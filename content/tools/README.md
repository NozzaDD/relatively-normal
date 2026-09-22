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
| `coverage_map.py` | writes `coverage.csv` — which product can carry which colour in which slot |
| `pick_boards.py` | chooses the pieces for a board and runs the acceptance test |

## Added 22 September 2026 — the URL bar and the flat lays

| Script | What it does |
|---|---|
| `url_bar.py` | reads Safari's address bar off each screenshot and writes `_url_bars.json`. The bar's text is set larger than a tab title, which is how the page you are looking at is told from the tabs behind it. |
| `flat_lays.py` | finds packshots on a plain backdrop, paints the shop's badges out with the backdrop's own colour, cuts them again, and rates the result by measurement: one connected piece, clear of the frame, no text inside. Writes `_flat_lays.json`; the shelf gate reads it. |

- The backdrop is read from the four **corners**, not a ring around the photo:
  a packshot is cropped close, so a ring runs through the garment's shoulders.
- The frame test is made on the uncropped cut. A cut-out trimmed to its own
  bounding box touches its own edges by construction, so measuring after the
  crop says "touches the frame" about everything.
- A word sitting **on** the garment is left alone. Painting it out first would
  answer the "no text inside it" question by cheating, and would damage a print.
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
`coverage_map.py` → `build_boards.py` → `note_visuals.py` → `slot_sheets.py` →
`brand_questions.py` → `catalogue_readme.py` → `boards_readme.py` →
`mark_used.py`.

Two design notes worth keeping:

- **Background is a topological fact, not a colour one.** The first colour pass
  masked every pixel close to the backdrop and quietly deleted pale garments; the
  mask now flood-fills inward from the border instead.
- **Find the product by content, not by empty space.** The first asset pass looked
  for the largest low-edge block on the page, which on a shop page is just as
  often the margin below the photo. A third of the first tiles came out blank.

## Added 21 September 2026 — the styling desk

| Script | What it does |
|---|---|
| `build_studio.py` | builds `studio/data/` and the web-sized images the desk serves |
| `collect_outfits.py` | reads `content/outfits/` and writes `used_in` back into the catalogue |

`build_studio.py` is the only thing that writes into `studio/data/`,
`studio/assets/`, `studio/thumbs/`, `studio/inspiration/` and `studio/fonts/`.
Re-run it whenever the catalogue changes; `--no-images` rebuilds the JSON alone
in a second or two.

`collect_outfits.py` only ever writes the `used_in` column, and only the
date-prefixed outfit slugs inside it — entries like `board-3` from the rebuilt
boards are left alone, so re-running it never drops something it did not put
there. `--check` reports without writing.

## Added 22 September 2026 — review, variants, the shelf gate

| Script | What it does |
|---|---|
| `build_review_images.py` | one full photo (no page UI, ≤ 1200 px) and two boxes — item, person — for every product that is not a clean flat cut-out |
| `uniqlo_variants.py` | recolours a UNIQLO flat lay once per colour read off the all-colours picture; writes `_variants.json` and one contact sheet per style |

`build_products.py` now merges the variants as rows (`recoloured = yes`,
`recolour_source`), hides the other UNIQLO images of a recoloured style
(`shelf = hidden`), applies `content/catalogue/asset-choices.json` from the
desk (`asset_choice`, `asset_box`, `shelf`), and keeps `validated` and
`used_in` across rebuilds. `build_studio.py` copies the full photos to
`studio/full/` and makes each thumbnail from the chosen crop.

`coverage.py` was renamed `coverage_map.py`: it shadowed the `coverage`
package that numba, and so rembg, imports.

Order to re-run: `cluster_products.py` → `make_assets.py` → `crop_figures.py`
→ `extract_colours.py` → `asset_quality.py` → `build_review_images.py` →
`uniqlo_variants.py` → `build_products.py` → `inspiration_colours.py` →
`build_inspiration.py` → `coverage_map.py` → `build_studio.py`.

## Added 23 September 2026 — any-image adjust, multi-box split

`build_review_images.py` now writes every screenshot of every product in
Review (`review/{pid}-{i}.jpg`, i ≥ 1), boxes for each, and `suggested` cells
where a page is plainly a listing grid. Listing-grid products keep the whole
trimmed page as their full image, so the grid can be cut up. Clustering already
caps a product at five images.

`build_products.py` reads `splits` from `asset-choices.json` and creates one
row per box: `{parent}-S{n}`, with `parent_id`, `asset_type = crop`,
`asset_image` and `asset_box`, the slot and `colour_name_text` the stylist
gave, batch, shop and brand from the parent (confidence inherited, never
upgraded), and colours read from the box region by `extract_colours`. The
`used_in` collector marks both the cut piece and its parent.
