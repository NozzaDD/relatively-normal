# content/tools/

Reusable scripts for the swipe library and the boards. Committed so later runs
do not rewrite them. All of them import the engine's colour module read-only;
none writes to `content/swipe/`, and no original image is ever moved, renamed,
deleted or re-encoded.

| Script | What it does |
|---|---|
| `imglib.py` | Shared helpers: iOS/Safari chrome trim, in-page lightbox trim, dHash, white balance against a studio backdrop, skin band, `rembg` cut-out with alpha hard-threshold and connected-component tidy-up. |
| `colour_names.py` | The fixed colour vocabulary — 13 families and a closed list of plain names. Family follows CIELAB hue and chroma, with named exceptions for cream, camel, coral and teal; below C* 12 the original rows decide. `python3 content/tools/colour_names.py` prints a self-test. |
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
| `build_palettes.py` | builds `content/palettes/palettes.json` from the frameworks, the engine's generators and the AW26/27 seed; `build_studio.py` runs it and copies the result |
| `collect_outfits.py` | reads `content/outfits/` (and `content/swipe/outfits/`, where some boards landed) and writes `used_in` back into the catalogue |

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

## Added 22 September 2026 — panels and listing-grid cells

| Script | What it does |
|---|---|
| `panels.py` | splits a product-page screenshot into its separate photographs, classifies each (flat lay, on-model, detail, text, other), cuts each on its own and rates the flat lays. A product whose flat-lay panel measures clean gets that panel as its cut-out and leaves Review. Writes `_panels.json`. |
| `grid_cells.py` | every cell of a listing grid as a product of its own: the cell's photograph, a cut-out, and the name, section, price and fit label read off its caption. Fills the lattice in from the cells the detector found, so a grid of nine no longer yields four. Writes `_grid_cells.json`. |

- A gutter is read from a line's **own evenness**, not from one page-wide
  backdrop colour: two panels often sit on two different whites, and the band
  between them is the line that matters.
- The cut runs through the **middle** of a gutter. A panel that begins where
  the backdrop stops has the garment against its frame from the first row, and
  the "clear of the frame" measurement then rejects every panel there is.
- A panel is classified by what is in it, not by its backdrop: once the page is
  split the panel IS the photograph, so the corner test reads the garment's own
  shoulders and calls a good packshot "other".

## Added 23 September 2026 — one row per garment

| Script | What it does |
|---|---|
| `split_mixed.py` | splits a product row that holds several garments. The clustering groups screenshots by page layout, which cannot tell two of one shop's products apart; colour can, and colour decides on its own — the same style in navy and in cream is two things to put on a shelf. Writes `_product_splits.json`, rewrites `batches.json`, and gives each new row its own pictures, cut-out, colours and viewing row. |

- Listing grids are left alone: a grid screenshot is a page of a dozen
  products, its dominant colour means nothing, and `grid_cells.py` cuts it up.
- The style name is written on every row a split produces, and each row records
  the product it came from, so the pair stay findable together.
- The slot is the parent's and may describe the parent's garment. It is carried
  with a note saying so rather than guessed at again.
- Files are named from the records that own them, never found by matching a
  prefix in the folder: a group that keeps the parent id renames its own later
  pictures, and a prefix scan reads a name another group is about to write.

## Added 23 September 2026 — UNIQLO variants from the swatch circles

| Script | What it does |
|---|---|
| `uniqlo_pages.py` | reads every UNIQLO screenshot's buy panel — product name, selected colour as number and name ("03 GREY"), price with currency — the product ID under Description where the screenshot reaches it, and every colour circle under "Colour:", sampled at its centre inside any selection ring. Writes `_uniqlo_pages.json`. |
| `uniqlo_variants.py` | rewritten. One variant per swatch circle: the style's clean single flat lay (chosen by eye in `STYLES`, measured one piece / clear of the frame / no text) recoloured in CIELAB to the swatch, or — where the all-colours photo has that colour lying alone — the real photo cut out instead. Skips the swatch that is the source's own colour. Writes `_variants.json`, `variants/*.webp` and `sheets/uniqlo-{style}.jpg`. |

- The swatches are pictures of the fabric, and they agree with the flat lays:
  the swatch nearest each source measured a median dE2000 of about 1 from the
  source's garment colour. That is what makes them usable as targets.
- A selected circle is told by the **white gap** inside its ring, not by its
  size — the median size is wrong when the page has only two circles.
- The recolour mask leaves out only what sits in the neck (the label) or is
  big enough to be a trim. Seams and deep folds are recoloured with the rest:
  left out, they print the source's colour through the new one, which is what
  made dark-to-pale variants look fake.
- `build_products.py` applies the page readings to UNIQLO rows (`given`),
  carries the product ID to a row whose screenshots stop above it at
  `guessed`, and hides a style's other rows only when all of a row's
  screenshots belong to that style. A variant takes its shelf verdict from
  its source row, as the desk's rule says. Where a source row's own
  catalogue cut-out failed the flat-lay measurement and the cut its variants
  were made from passes it, the row's picture becomes that cut and its
  colours are read again (`measured_sources`); `build_studio.py` treats a row
  whose picture is a measured cut as clean. A source row keeps the page's
  colour name only when the pictured garment is the selected swatch — the
  gallery photo is often another colour (`source_colour_names`).

Order to re-run: `uniqlo_pages.py` → `uniqlo_variants.py` → `build_products.py`
→ `build_studio.py`. Needs `tesseract`, `pytesseract`, `rembg` (u2net), `scipy`.

## Added 23 September 2026 — one garment per picture, duplicates

| Script | What it does |
|---|---|
| `shelf_checks.py` | two measurements the shelf gate did not make, both on the picture the shelf shows. **Several garments**: a listing-grid page, a style's all-colours photo, a cut-out in 3+ separate pieces (2 where a pair is not the garment), or 3+ separate colour regions with no skin. **Duplicates**: same brand and slot, silhouette IoU ≥ 0.96, lightness structure within 2, median colour within dE2000 3; one keeper per group. Writes `_shelf_checks.json` and, with `--sheets`, `sheets/shelf-check-several.jpg` and `sheets/shelf-check-duplicates.jpg`. `build_studio.py` turns it into `several`, `several_group`, `duplicate_of`, `duplicate_cause`. |

- The colour FIELDS are not used for duplicates. A colourway split that copied
  its parent's picture says "steel blue" beside an oxblood coat; the picture is
  the evidence.
- A recolour shares its source's silhouette exactly, so between recolours the
  colour alone decides. UNIQLO's own swatches are distinct colours: the closest
  two on one style are dE 4.3 apart, above the threshold.
- The old `duplicate_of` boolean — a grid cell whose brand, slot and colour
  name match a filed product — is now `twin`.
- `build_studio.py` reads each picture's size from the file, not from
  `_panels.json` or `_review_boxes.json`: eleven panels had been re-cut since
  their sizes were written, and the desk sized pieces from them.

Order to re-run: `build_products.py` → `shelf_checks.py` → `build_studio.py`.

## Added 23 September 2026 — ingest without renumbering, one product per colour, every shop's colourways

| Script | What it does |
|---|---|
| `cluster_products.py --append [paths]` | new screenshots — the ones in `content/swipe/products/` the swipe index does not type yet, plus any paths given — become new batches after the last one. A full re-run numbers batches by position, so a screenshot inserted mid-sequence renumbers every batch after it and orphans the IDs in `asset-choices.json`, `used_in` and the outfits; it would also undo `split_mixed.py`. |
| `make_assets.py --new`, `extract_colours.py --new` | only products with no asset / no colours yet. A full run overwrites the cut-outs `flat_lays.py` and `panels.py` have since replaced. |
| `same_product.py` | two screenshots of one product in one colour (a flat lay and a model photo, or the same page twice) → one row. Grouped by the page text — same batch, shop, product name and colour name — and confirmed by the pictures: two flat lays by `shelf_checks.py`'s duplicate test, two model photos within dE2000 5. Measures the dE2000 between the flat lay's garment and the model's for every pair; `--merge` folds each group into the flat lay's row in `batches.json`; `--preview DE` shows the flat lays above DE recoloured to their model's colour; `--apply DE` makes them, and `build_products.py` gives those rows `recoloured = yes` and a `recolour_source` naming both screenshots. Only batches from `--from` (default 63) on, so no filed ID is folded away. |
| `colourway_pages.py` | reads the colourway row under "Colour:" on Johnstons of Elgin, Toast and Colorful Standard pages: every swatch's place, size, kind (a fabric patch or a photo of the garment) and colour, and which one is selected (the one with the dark frame). Writes `_colourway_pages.json`. UNIQLO stays with `uniqlo_pages.py`. |
| `colourway_variants.py` | the other shops' variants. A swatch a screenshot already shows is not made again (the page's own selected swatch says which; colour within dE 10 where the page did not reach the swatch row). A photo swatch is cut out of the page — the brand's own picture, not simulated. A fabric swatch recolours the style's clean flat lay with `uniqlo_variants.recolour()` and is marked simulated. No variant is given a colour name: only the selected swatch has one on a page, and that colour is the screenshot's own. Writes `_colourway_variants.json`; `build_products.py` merges it with `_variants.json`, and unlike UNIQLO's leaves the owner's own screenshots on the shelf. |
| `variant_sheets.py` | the per-style variant sheets, each variant beside the swatch it came from, every swatch the same size, the measured dE2000 between swatch and variant under it. `--choose` puts both layouts on one sheet. |

- `url_bar.py` knows `.st` (Toast is `eu.toa.st`).
- `panels.py` types the two photographs of a page the viewing pass read as
  `layout=side-by-side` by position: left the flat lay, right the model.
  rembg often cuts the model away and leaves the jumper, which then measured
  as a clean flat lay, and a rust or coral jumper sits inside the skin band.
- `uniqlo_variants.py` takes four-digit screenshot numbers (`'1170'`).

Order for an ingest: `cluster_products.py --append` → `render_views.py` and
the viewing pass into `_viewing_rows/rows_n*.txt` → `url_bar.py` →
`make_assets.py --new` → `build_products.py` → `crop_figures.py` →
`asset_quality.py` → `flat_lays.py` → `build_review_images.py` → `panels.py`
→ `grid_cells.py` → `same_product.py` (then `--merge`, reset the merged rows
and run the steps above again) → `extract_colours.py --new` →
`uniqlo_pages.py` → `uniqlo_variants.py` → `colourway_pages.py` →
`build_products.py` → `colourway_variants.py` → `build_products.py` →
`shelf_checks.py` → `build_studio.py`.

Two decisions the owner made on 23 September, so the next run does not ask again:

- ~~**Model colour wherever there is one.**~~ Superseded the same evening,
  below: of the fourteen recolours this made, the owner kept two.
- **Variant sheets in layout A** — one row per variant: swatch, variant,
  number, real or simulated, dE. Both variant scripts write their sheets
  through `variant_sheets.write('rows')`.

## Added 23 September 2026 (evening) — incremental by default, the teal recolours

**Reviewed material is never re-run by default.** `panels.py`, `flat_lays.py`,
`asset_quality.py` and `crop_figures.py` only look at products that are new or
whose screenshots have changed since they last processed them; `grid_cells.py`
only gives the relaxed grid detector to new or changed grids, and it already
skipped every grid screenshot it had cut. What each tool has processed is kept in
`content/catalogue/_processed.json` by `incremental.py`: per tool, per product, a
fingerprint of the product's screenshots (paths and byte sizes, from
`batches.json`). A merge that adds a screenshot to a row changes its fingerprint,
so that row is looked at again; nothing else is.

- **Full run:** add `--all` — `python3 content/tools/panels.py --all`, and the
  same for `flat_lays.py`, `asset_quality.py`, `crop_figures.py`,
  `grid_cells.py`. `--redo` still works and means the same. A full run re-cuts,
  re-rates and re-measures reviewed products: that is what it is for, and why
  it is never the default.
- `python3 content/tools/incremental.py` prints, per tool, how many products
  it has processed and how many are new or changed.
- The baseline was stamped on 23 September from the 664 products then filed
  (`incremental.py --stamp-all`). Do not stamp again over an ingest in
  progress: it would mark unprocessed products as done.
- `make_assets.py --new` and `extract_colours.py --new` were already
  incremental; `build_review_images.py` and `url_bar.py` only do screenshots
  they have not done.

Other changes in this run:

| Script | What changed |
|---|---|
| `cluster_products.py --append` | skips a screenshot that is a byte-for-byte copy of an image already filed elsewhere in `content/swipe/` (IMG_1337 is a fashion-show picture). The `IMG_nnnn-2.png` exports are identical copies and were already skipped by name. |
| `same_product.py` | `DROPPED` lists the twelve Colorful Standard rows the owner sent back to their own flat lay; `--apply` never recolours them again. A run with `--from` keeps every group from earlier batches exactly as it was, and `--preview` stores its result as `recolour_preview`, never touching an approved `recolour`. |
| `build_review_images.grid_cells(strict=False)` | for a page the viewing pass typed as a listing grid: two alike blobs side by side are enough. Used by `grid_cells.py` only where the strict detector found nothing. |
| `build_products.py` | a cell of a grid row with several screenshots is `{pid}-I{n}-C{j}` from batch 75 on. Before, every screenshot numbered its cells from C0, so two cells shared an ID; the IDs filed before batch 75 are left as they are. |

The owner's decision, 23 September evening: **only the two teal recolours stay**
— B068-P045 (Oversized Merino Wool Crew) and B068-P077 (Merino Wool Turtleneck),
both OCEAN GREEN. The other twelve show their own flat lay, unrecoloured. For a
new ingest `same_product.py` is run to find pairs, and `--preview` at most; a
recolour is applied only when the owner has looked at the preview and said yes.

## Added 24 September 2026 — grid pages read by eye

| Script | What it does |
|---|---|
| `read_grids.py --render DIR` | every listing-grid screenshot's review copy with a pixel ruler drawn round it (numbers every 100 px, ticks every 50, faint lines every 100), for a reader to open |
| `read_grids.py --ingest DIR` | takes the readers' JSON (one per screenshot: per tile the photograph's rectangle in page pixels, the name, price and currency, the colour name where the caption gives one, what the garment is; tiles cut off at the page edge counted, not listed), snaps each rectangle to the garment's own bounds plus a margin, cuts the cell and its cut-out into `review/`, measures the cut the way `flat_lays.py` does and writes the verdict into `_flat_lays.json` under the cell's ID, which is what the shelf gate reads. Writes the cells into `_grid_cells.json` under the same keys as the geometric pass, marked `source: "eye"`; the geometric records it replaced are kept in `_grid_cells_geometry.json` and the per-page counts in `_grid_cells_compare.json`. A cell the owner has decided on is never replaced. |

- **Geometry is the fallback now, not the way.** The lattice detector in
  `build_review_images.py` / `grid_cells.py` found nothing on plain four-tile
  pages (B079-P004, B080-P008, B080-P009, B080-P012, B081-P001) and half the
  tiles on most others; the readers found 1,005 whole tiles on 254 pages
  where geometry had 756, with a name on 95% and a price on 95% of them
  (geometry: 69% and 19%). `grid_cells.py` still runs for a grid screenshot
  no reader has covered.
- **The snap only tidies.** It works inside the reader's box padded 1.5%, so
  a neighbouring tile cannot join the mask; runs of rows thinner than a
  twelfth of the box are labels and swatch dots and are dropped; the topmost
  photo-sized run is the picture; and a 7% margin round the garment's bounds
  keeps it clear of its own frame, clamped to the reader's box so it never
  takes in the caption.
- **A reader who measured on the ruled canvas** rather than the page is off
  by the 40 px margin; boxes that run past the page's edge give it away and
  the page is shifted back (59 of 263 pages).
- **Cell IDs:** every screenshot of a grid row numbers its own cells,
  `{pid}-C{j}` for the first screenshot and `{pid}-I{n}-C{j}` after it, so no
  two cells share an ID any more (93 did).
- **A cell's brand** is the grid's shop at the grid row's own confidence, not
  a flat `guessed`; its colour name, where the caption printed one, is in
  `colour_name_text`; the reader's garment word is its `garment_type` and
  decides its slot before the caption does.
- **The skin test bites tan leather.** 353 cut-outs measured "someone is
  wearing it" and most are tan and brown loafers, boots and bags: the skin
  band overlaps warm leather (CLAUDE.md hard rule 6, `imglib.is_skin`). They
  wait in Review under their grid rather than going to the shelf unseen.

Order: `read_grids.py --render` → readers → `read_grids.py --ingest` →
`build_products.py` → `shelf_checks.py` → `build_studio.py`.

## Added 24 September 2026 — page text first, colourway pictures, the filter picks the picture

| Script | What it does |
|---|---|
| `page_text.py` | reads what a product page says about itself, per screenshot: the **name** (the line set above the first price in the buy panel, or below it where the price comes first), the **colour or wash** (after "Colour"/"Farbe"/"Wash", or after " \| " in "FRANKIE … Jacket \| Olive"), a **product number** ("Referenz", "Ref.", "Product ID", "Art.-Nr.") and the **shop** (url_bar.py; Safari shows the domain only). OCR lines are cached with their positions in `_page_text.json`, so the fields can be re-read without tesseract. `disagree(a, b)` names the legible fields two pages contradict each other on. |
| `name_split.py` | splits a product-page row whose screenshots disagree on name, colour, number or shop (point 4 of 24 Sept). Where none of name/colour/number is legible on both pages, lightness over 8 L* or a silhouette overlap under 0.9 splits — **only between pictures of one kind**: see its docstring for the measured cases that made that condition necessary, and `literal_would_also_split` in `_name_splits.json` for what the thresholds alone would have split. `KEEP` and `BY_EYE` hold the rows a person decided from a contact sheet. Applies through `split_mixed.apply()`, which it now shares with the colour split; the group holding the first screenshot keeps the row's id. New rows take their name from their own page only when the name was what differed, a price only from a page whose name was read beside it, and never the parent's material or (across shops) brand. |
| `colourway_pictures.py` | every colourway family (a style and its `-V`, `-sw`, `-cw` rows) shares out its pictures by colour: a picture within dE2000 12 of the row it came from stays, else it goes to the nearest row within 12, else it stays and is listed as unassigned. A grid cell's only picture is its own cell. A row whose cut-out is **the same picture as another row's in its family** (split_mixed.py copied the parent's) gets a cut of its own colour when one passes the flat-lay questions, else goes to Review. Writes `_picture_owners.json` (every run kept under `runs`); `build_studio.py` applies it. `_picture_colours.json` caches the readings. |

Changed:

- `cluster_products.py --append` asks the page text first: two pages that contradict each other are two products however alike their layout; two that agree on a field are one; only where neither says anything does layout decide. A batch never spans two shops (the address bar cuts it), a runt never joins a batch across a shop change, and neighbouring batches of one shop are one.
- `build_products.py` keeps a filed row as filed: colours, notes, validated and the brand guess of any row whose screenshots, cut-out path and recolour source are unchanged come from the products.csv it is replacing (`FROZEN`). A change of vocabulary or reader is a decision to re-read, not a side effect of adding a product — to re-read on purpose, delete the rows first. Rebuilding on 24 Sept without this would have renamed 156 colours (the vocabulary change of 9b624c7 was never applied to the catalogue). A brand guessed from a domain is spelt as a page of that shop printed it.
- `build_studio.py` applies `_picture_owners.json`, and writes `studio/data/picture-migration.json`: where each picture the desk last had went, one version per build that moved any. The desk moves a box or whole-picture decision with its picture, once; hiding, the cut-out and a slot stay with their row.
- `read_grids.py --ingest` leaves the rows of pages it did not read in `_grid_cells_compare.json`; it used to write only its own.

Order for an ingest: `cluster_products.py --append` → viewing rows → `build_products.py` → `make_assets.py SHOTMAP --new` (SHOTMAP: `{product_id: shot_type}` from products.csv) → `build_products.py` → `crop_figures.py` → `asset_quality.py` → `flat_lays.py` → `build_review_images.py` → `panels.py` → `name_split.py --only <new multi-screenshot rows>` → `read_grids.py --render` → readers → `--ingest` → `extract_colours.py --new` → `build_products.py` → `colourway_pictures.py` → `shelf_checks.py` → `build_studio.py`. Run `build_products.py` from the products.csv on main (git checkout it first) so rows made earlier in the same run are not frozen half-built.

## Added 24 September 2026 (afternoon) — the eye-read gate, the vocabulary applied

| Script | What it does |
|---|---|
| `eye_gate.py` | the shelf gate for listing-grid cells **read by eye**. Drops two of flat_lays.py's questions that only ever said no for the wrong reason on a shop's category tiles: the skin share (tan, brown, camel and burgundy leather and pink linings sit in the skin band) and "clear of the frame" (shops crop tight). Keeps one piece, no text inside, not a sliver (fills ≥ 0.2 of its box, no longer than 1:8), not too small (≥ 60 px). A person then looks at every cell it would move, 30 a contact sheet (`--sheets DIR`), and lists in `HELD` / `HELD_GRIDS` what is on a model, worn, a prop in the cut or otherwise not a single product. Writes `gate: "eye"` into `_grid_cells.json` and the verdict into `_flat_lays.json`. Geometric cells keep flat_lays.py's gate. |

- **The premise holds for most shops, not all.** Of the 521 cells the gate would have moved, 190 were on a model: CLOSED, Toteme, Lemaire, Studio Nicholson, Arket, A.P.C. and others show their category pages on people. They are in `HELD_GRIDS` and stay in Review. Run the contact-sheet pass on every new grid.
- `build_products.py` names every colour from its hex on every build (`name_from_hex`): the family and the name are a function of the hex and the vocabulary in `colour_names.py`, so they are no longer frozen with the reading. Hexes, shares, lightness and the neutral flag still are.
- `build_studio.py` exports `hold`, the reason the gate kept a row in Review; the desk shows it under the cell.

Order after a grid ingest: `read_grids.py --ingest` → `eye_gate.py --sheets DIR` → the contact-sheet pass into `HELD` → `eye_gate.py` → `build_products.py` → `shelf_checks.py` → `build_studio.py`.

## Added 24 September 2026 (evening) — palette matching, remove and back to Review, page text

| Script | What it does |
|---|---|
| `shelf_text.py` | OCR of every shelf tile as the desk shows it (the cut-out, or the box chosen on the photo), and of every other picture a tile can switch to. Page text is a page word ("colore", "taglia", "size", "add to cart", also cut off at the box's edge: "guid"), a price, or two or more size labels; a lone word is recorded, not acted on. `eng` only and 25 s per picture: the first run with three languages and a second layout pass sat fifteen minutes on one knit texture. Writes `_shelf_text.json`. |
| `send_to_review.py` | `send(version, {pid: reason})`: the products go back to Review — their entry in `asset-choices.json` becomes `review` with the reason (slot, boxes and "not a duplicate" kept), and `review-sends.json` gets a version the desk applies once over a browser's own old decision. |

Changed:

- `build_products.py`: `split_rows` took an undefined `filed` and crashed on the first box drawn since 24 Sept, which is why no *Apply shelf choices (auto)* commit followed the owner's review push. Choices now reach variant, cell and split rows too, and `review` becomes `shelf = review` with `review_reason`. A box drawn on the **cut-out** (`base: asset`) is cut from the parent's cut-out; it used to be cut from the full photo at the same fractions, which is how "Guida alle Taglie" and a size row reached the shelf as Aspesi trousers (B011-P002-S1..S3). The desk's `derivedProducts` had the same mistake.
- `shelf_checks.py`: a product page zoomed onto its colour-swatch row is `swatch row`, never a listing grid (`is_swatch_row`: the viewing pass names one garment "shown in N colourways" or a "colour swatch row", and no tiles). `grid_cells.py` and `read_grids.py` skip it. A piece cut by hand is measured by its own box, not its parent's whole page — measured whole, every box on B022-P002 and B046-P010 was a "duplicate" of its siblings.
- `panels.py`: a panel with eight or more confident words is `text`, whatever area they cover. B018-P001's "Composizione" block covered 3.7% of its panel, cut into one clean piece, and was the product's shelf picture.
- `build_studio.py` exports `review` (why it is back in Review) and `removed` (removed by the owner, as against hidden by the build), and copies `review-sends.json`.

Order after a push of `asset-choices.json`: `build_products.py` → `shelf_checks.py` → `build_studio.py`. After an ingest, `shelf_text.py` → `send_to_review.py` for what it finds.

## Added 24 September 2026 (evening) — better cut-outs, row splits, the hidden products

| Script | What it does |
|---|---|
| `soft_cut.py` | the new cut. Runs on the **screenshot at full resolution** (the review copy's `origin` crop, then the panel's box), keeps the model's **soft alpha**, takes the backdrop's colour back out of the edge pixels, and scales down premultiplied at the end, so the edge is anti-aliased instead of a staircase. `isnet-general-use` rather than u2net (finer structure: straps, handles); where it plainly failed — it kept nearly nothing on a page the garment fills — u2net, then a border flood-fill on a plain backdrop. Everything well inside the outline is made opaque (`solid_core`: on Lilysilk's cream pages isnet gave a dark cardigan 0.3 alpha all over). A piece touching or overlapping the main one is kept whatever its size (`keep_attached`); an enclosed region of the backdrop's colour, flat, big enough to be a gap between legs, is removed (`punch_holes`), but never when the garment is itself within 12 ΔE of the backdrop — colour cannot tell a cream coat from a cream page. A garment on a person is cut off them with `u2net_cloth_seg` by slot (top: upper body; bottom: lower; dress: full; layer: upper + full), whose class map is read straight off the model and scaled NEAREST (rembg's own `predict` scales the class indices with LANCZOS and draws one-pixel outlines round the legs). Shoes, bags and accessories on a person cannot be separated, and are said to be. |
| `recut_hidden.py` | re-cuts the products in `_hidden_reasons.json` from their best picture (a packshot, then a cell, the page, a photo worn; a panel split out with `panels.find_panels(subtle=True)`; the same picture where the fault was only the cut: jagged, holes, handles). `--cut` writes the cut and `_recut.json`, keeps the old cut in `assets-before-recut/`; `--sheets` before/after sheets; `--send` puts the old cut back on everything not in `LOOKS_RIGHT` and sends `LOOKS_RIGHT` back to Review through `send_to_review.py`. |
| `cut_audit.py` | the same faults counted on the shelf, by slot: hard-edged cut-outs, backdrop left inside, bags whose handles a new cut finds. Measures, re-cuts nothing. |

`_hidden_reasons.json` is the owner's 206 hidden products, one reason each, read by eye from contact sheets (point 4). Reading them showed the list of reasons was missing its largest group: **119 were whole people** — the cut was the model and the outfit, not the piece.

Changed:

- `name_split.py`: a name both pages print and agree on no longer settles that two screenshots are one product — a style's name is the same on every colourway's page; only an agreeing colour or product number does, and otherwise the pictures decide. Two untyped cuts that are plainly packshots (skin under 1% once the garment's own colours are left out) are now compared by silhouette too: the burgundy cami read as "worn" because burgundy is in the skin band, and was never compared with the burgundy trousers in its row. Tan leather still reads as skin; B090-P010-V2 and B076-P001 are split by eye (`BY_EYE`), B077-P013 kept whole (`KEEP`, the one row the new test got wrong).
- `panels.py`: `find_panels(subtle=True)` also finds a join between two greys a couple of levels apart when both sides are steady, and a straight line across 85% of the width where one photograph abuts the next. Only the re-cut uses it.
- `shelf_checks.py`: a cut that measures one piece in fewer than three colour regions is not "the style's all-colours photo", whatever screenshot it came from.

Order for a re-cut: `recut_hidden.py --cut` → `--sheets` and a person reading them into `LOOKS_RIGHT` → `--send` → drop the re-cut rows from `products.csv` and their `_colours.json` entries, `extract_colours.py --new` → `build_products.py` → `shelf_checks.py` → `build_studio.py`. Needs `rembg` with `isnet-general-use`, `u2net` and `u2net_cloth_seg` (each ~170 MB, downloaded on first use), `scipy`, `numpy`.
## Added 24 September 2026 (night) — exports tidy themselves

| Script | What it does |
|---|---|
| `tidy_exports.py` | merges every `content/catalogue/asset-choices*.json` (the copies the iPad's Files app makes when the name is taken) into `asset-choices.json`, keyed by product ID, the newest export winning — by the `exported` time inside the file, not the name; deletes the copies and the share sheet's `text.txt`, `text-2.txt` … in `content/catalogue/` and `content/outfits/`. A broken or unreadable export stops it before anything is changed. `build_products.py` runs it first; so does the *Apply shelf choices* workflow, whose path filter now watches `asset-choices*.json`. `test_tidy_exports.py` tests it. |

The desk now writes the full export time (`2026-09-24T18:30:00.000Z`), not the day: two exports of one day could not be told apart. Older date-only exports of the same day count the copy as newer than `asset-choices.json`, since a copy only exists because a new export was saved beside it.
