# studio/ — the styling desk

A single static page. No framework, no build step: open `index.html` and it
runs. Everything under `data/`, `assets/`, `thumbs/`, `inspiration/` and
`fonts/` is generated — do not edit by hand.

```
python3 content/tools/build_studio.py            # rebuild data + images
python3 content/tools/build_studio.py --no-images # JSON only, much faster
```

## What is where

| Path | What |
|---|---|
| `index.html` | the page |
| `style.css` | all of the styling |
| `js/data.js` | **the only file that knows where items come from.** Swap the source and the desk reads a user's own wardrobe instead of the catalogue. |
| `js/model.js` | the board — pure data and pure functions |
| `js/colour.js` | OKLab distance, used to *rank* suggestions and nothing else |
| `js/palette.js` | the chosen palette: its snapshot, and the outfit's colour share against it |
| `js/render.js` | draws a board onto a canvas; the export path |
| `js/export.js` | PNG, JPEG, the info JSON, the markdown list, the share sheet |
| `js/app.js` | the UI, and the only file that touches the DOM |

`data.js` is the seam the brief asked for. `createStaticSource()` reads the
built JSON; `createMemorySource()` takes a catalogue object directly. The UI
only ever calls `load()`, `assetUrl()`, `thumbUrl()`, `inspirationUrl()` and
`inspirationThumbUrl()`.

## The shelf, the gate and Review

A product is on the shelf by default when its cut-out has been **measured
clean**, or when you have **reviewed** it. Measured clean means all of this, on
a packshot with a plain backdrop and nobody in it: the cut-out is one connected
piece, it does not touch the photograph's edge, and OCR finds no page text left
inside it. Nothing is judged by eye or by the old good/usable/weak rating.
Everything else waits in the Review tab until you decide; **Show unreviewed**
brings it all in for a look. A recoloured variant is on the shelf exactly when
its source is. New products from a later ingest follow the same rule.

A screenshot that held two photographs stacked on the page — the flat packshot
above, the same garment on a model below — is now **two pictures of one
product**, each labelled by what it is. The shelf shows the primary picture,
which is the flat lay wherever there is one, and the colours are read from it.
**Other picture** on a selected piece, or the badge on a shelf cell, switches to
another picture and keeps where the piece sits and how big it is; the info file
records which was used.

Where you screenshotted a product twice in one colour — the flat lay and the
same garment on a model — it is **one row with both pictures**, and the flat
lay is recoloured to the colour measured on the model photo, because the model
photo is where the shop's colour is true. That row says *simulated*, and its
`recolour_source` names both screenshots.

**One picture, one garment.** Clean is not the same as single: a fan of five
colourways laid over each other is one connected piece, clear of the frame, with
no text in it. `content/tools/shelf_checks.py` measures the shelf picture of every
row and marks it `several` when it is a listing-grid page, a style's all-colours
photo, a cut-out in three or more separate pieces (two, where a pair is not the
garment), or three or more separate colour regions with no skin in the picture.
Those rows are off the shelf and back in Review — taking one whole no longer
counts as a decision; a box you draw does — and **Several garments** in Review
groups them under the row that owns the picture, whose card has Add box.

**Duplicates** are marked, never deleted. The same script compares rows of the
same brand and slot by the picture itself — silhouette, lightness structure and
the garment's median colour (dE2000 ≤ 3) — because a colourway split that copied
its parent's picture carries colour fields that disagree with it. One row in each
group is the keeper (a real photo over a recolour, then the cleaner cut, then the
one with a name and a price); the others carry `duplicate_of` and
`duplicate_cause` and are hidden from the shelf. **Duplicates** in Review shows
each beside its keeper; **Not a duplicate** puts one back and travels in
`asset-choices.json` as `not_duplicate`.

**The tile is what a tap places.** Both read `shelfView()` in `data.js`: the
picture picked with the badge, else your choice (this browser's, then the
catalogue's), else the cut-out. The built thumbnail is shown only while it is a
picture of that same view; a choice made since the last rebuild is cut live from
the picture itself.

**Proportions come from pixels.** A piece's aspect is measured on the decoded
image it shows (`pixelAspect()` in `model.js`) when it is placed, when Other
picture switches it, when a saved board or an opened file loads, and again at
export, where the drawing takes the size from the pixels it draws. Stored picture
sizes and thumbnails are never trusted for it. A framed picture keeps its own
proportions inside the mat. Resizing changes the width and the height together;
there is no one-sided stretch.

A **listing grid** is a page of a dozen products, so each of its cells is now a
product of its own, derived from the grid, with the cell's own photograph,
cut-out and colours, and whatever its caption gave: name, price, colour name,
what the garment is. The cells are read off the page by eye
(`content/tools/read_grids.py`), not found by geometry; the brand is the
grid's shop at the grid's own confidence. A cell whose cut-out measures clean
— one piece, clear of the frame, no text, nobody wearing it — is on the shelf
like any clean flat lay; the rest wait in Review grouped under the grid they
came from, with **Accept all cells** to take a whole grid in one tap. A cell that matches a product already
filed by brand, slot and colour is flagged *twin?* — flagged, never merged. The
grid itself is hidden once its cells exist.

A **fabric close-up** is kept but is not a version of the garment: it stays out
of the filmstrip and off the shelf, and **Show details** in Adjust box brings it
in when you want it.

Where one row held several garments — the clustering reads page layout, which
cannot tell two of a shop's products apart — the row is **split by colour**, one
row per garment, each with its own pictures, cut-out and colour fields. The same
style in two colourways is two rows; the style name is written on both so they
stay findable together, and the note says which row each was split from. The
slot is the parent's and may describe the parent's garment, so it is worth a
look.

**The slot is yours to set.** A row of eight buttons — layer, top, bottom,
dress, shoes, bag, accessory, base — sits on every Review card, on each listing
cell (tap its label), and under a selected piece on the canvas. What you pick
goes into `asset-choices.json` and the build writes it to the catalogue as
`given`, above anything read off a caption or inherited from the row a product
was split out of. Setting a slot is not a decision about the picture, so it
never marks a product reviewed. Two filters find the ones that need it: **No
slot**, and **Slot worth a look** — the rows whose slot came from a listing-grid
caption or from the product they were split out of.

Review shows each waiting product four ways — the cut-out, a box around the
item, a box around the whole person, the full photo — and you tap the one you
want. **Adjust box** lets you draw your own rectangle on the full photo.
**Hide** takes the product off the shelf; **Later** skips it. The boxes are
rectangles, not files: the desk crops the full photo at runtime, on the canvas
and in the export. Choices apply at once in the browser; **Export choices**
hands over `asset-choices.json`, which goes in `content/catalogue/` for the
build script to read.

**Adjust box** opens every *version* of the product, not just every screenshot:
its cut-out, and for each screenshot the whole cut-out, the item box, the
person box and the whole photo. Arrows or the filmstrip move between them and
the counter counts them all. Whichever you pick, the whole uncropped image is
shown with that version's box on it, so a crop that cut too much can be
widened as well as tightened; a cut-out is shown on the board's own off-white,
and a box drawn on one keeps its transparency. A selected box has eight
handles — four corners, four edges — and each grabs from 44 px away, so a
handle sitting on the picture's own edge is still catchable. Pinch to zoom and
move two fingers to pan; the boxes scale with the picture, and **fit** in the
bar puts it back. While a handle is moving, a loupe follows the finger with the
box's size in the picture's own pixels. **Use this one** takes the
version whole. Nothing is drawn over the picture except boxes and their
handles — the labels sit in the header. **Add box** draws further boxes on the
same image; each gets a slot from the buttons and an optional colour name, and each becomes its own
product — the parent's id plus a suffix (`B062-P018-S1`), the parent's batch,
shop and brand with confidence inherited and never upgraded, your slot and
colour name, and a runtime crop of that box as its image. The new piece is on
the shelf at once; its colours are read from the box region by the build
script at the next rebuild. The parent stays in the catalogue and you decide
whether it is hidden or also on the shelf. Where a page is plainly a listing
grid, **Suggested boxes** offers the detected cells to accept, adjust or delete
one by one. Each Review card says how many photos the product has, and
**More than one photo** narrows the list to those.

**If the trim changes**, boxes already drawn are moved onto the new crop rather
than thrown away — in `content/catalogue/asset-choices.json` by
`migrate_trim.py`, and in this browser's own storage when the desk next loads.

**Pull in Working Copy before saving an export.** A push of
`asset-choices.json` to `main` makes GitHub rebuild the shelf and commit the
result back as *Apply shelf choices (auto)*; pulling first keeps your next
commit on top of it. A failed rebuild commits nothing — see it under the
repository's **Actions** tab, workflow *Apply shelf choices*.

**Frame…** on the canvas bar is one setting for every framed image on the
board — the inspiration image, page tiles and every box: thin border, white
mat, corner radius. It is saved with the board and remembered for the next.

## Palettes

Above the canvas, the first dropdown picks a category and group: a colour
season, a colour family, or this season's AW26/27 palettes and their Soft
Summer versions. The button beside it opens that group's palettes as swatch
rows; tap one. It appears **beside** the canvas as a working reference, with
names, shares, roles and placement. **On board** puts it on the board as a
strip, above the pieces' own strip, and is off by default.

While a palette is chosen, **Matches this palette** on the shelf ranks pieces
by distance to its colours, using the same OKLab comparison as *Matches this
look*. Only one of the two is on at a time. Under the canvas, two bars compare
what the palette suggests with how the pieces divide by colour share. Each
piece is weighted by slot as matching.md §3 weights tier balance: top and
bottom double, a dress four. A colour further than 0.12 (OKLab) from every
palette colour counts as *outside*. The bars are a reading aid, not a verdict.

Choosing, changing or clearing a palette never moves anything on the canvas.
The info file records it (`palette`: id, name, category, colours, source) and
whether the strip was shown. The `.md` piece list names it in one line.
Reopening a saved outfit brings the selection back. The palettes come from
`content/palettes/palettes.json`, which `build_studio.py` rebuilds and copies to
`data/palettes.json`. Without that file the desk still works, with no palettes.

## Where saved outfits go

**Save** hands over four files with one name (`.png`, `.jpg`, `.json`, `.md`).
Put all four in **`content/outfits/`**, not `content/swipe/outfits/`.
`content/swipe/` holds inspiration, not boards. `collect_outfits.py` reads both
folders, so nothing already saved there is lost, and it names each board it
finds in the wrong one so you can move it. `content/outfits/README.md` has the
rest.

## Touch

- A vertical swipe on the shelf scrolls it.
- A tap adds the piece to the middle of the canvas, each new one a little
  further along. One gesture adds one piece: only the first finger counts,
  the gesture's id is spent the moment it places, and the placement happens
  in the same turn as the finger lifting, never after an image has loaded.
  The picture badge on a tile only switches pictures.
- A long press (about 300 ms) or a mostly sideways drag picks the piece up;
  it lands where you let go.
- On the canvas, two fingers on the selected piece resize and rotate it. The
  round handles still work.

## Running it locally

```
npx serve studio        # or: python3 -m http.server -d studio 8000
```

It must be served over HTTP, not opened as a `file://` URL — ES modules and
`fetch` both need an origin.

## Deployment

`vercel.json` at the repository root sets `outputDirectory: "studio"`, so the
desk is served at the root of the deployment. `.vercelignore` excludes
everything else, so `content/` — including the original screenshots — is never
uploaded. The page carries a `noindex` meta tag, an `X-Robots-Tag` header and a
`robots.txt`, and nothing links to it.

## Tests

```
node studio/test/unit.mjs        # pure functions — no browser needed
node studio/test/e2e.mjs         # headless Chromium, mouse: load, filter, drag, save, reopen
node studio/test/e2e-touch.mjs   # headless Chromium, iPad touch profile via CDP: swipe, tap,
                                 # long press, sideways drag, pinch, categories, review, frame,
                                 # adjust on any image, multi-box split
node studio/test/e2e-fixes.mjs   # iPad touch profile: proportions of a tall narrow and a
                                 # wide piece in the model, on the canvas and in the PNG;
                                 # one gesture = one piece; tile = placement; several
                                 # garments and duplicates in Review
```

Playwright's WebKit is not installable in this environment (the browser
download is blocked at the proxy), so Safari and iOS Safari are untested here.

`e2e.mjs` needs Playwright resolvable from the repository root. On this machine:

```
mkdir -p node_modules && ln -s /opt/node22/lib/node_modules/playwright node_modules/playwright
```

Neither test folder is deployed.

## Ten things to check on the iPad

1. Open the page. The shelf shows only clean cut-outs, and **Review** in the
   tabs carries a number. Swipe the shelf up and down with one finger: it
   scrolls and nothing is added.
2. Tap **top** in the category row. The shelf narrows and the button shows
   the same count as the shelf. Tap it again to clear.
3. Tap a thumbnail. It lands in the middle of the canvas. Tap two more: each
   sits a little further along, not on top of the last.
4. Press and hold a thumbnail for half a second, then drag it onto the canvas
   and let go. It should land where your finger was.
5. Put two fingers on a selected piece and spread and turn them. It should
   grow and rotate; the round handles still work on their own.
6. Tap **shoes** in the checklist under the canvas. The shelf filters to shoes.
7. Open **Review**. Pick a slot, tap a card's *item box* — the card marks
   itself, the piece appears on the shelf, and the progress count moves.
   Try **Adjust box**: drag a rectangle, **Use this box**.
8. Tap **Hide** on another card. It leaves the shelf. **Export choices** should
   offer `asset-choices.json` in the share sheet.
9. Tap **Frame…**, turn the mat off and corners to *round*. The inspiration
   image and every box on the canvas change together. Save: the PNG shows
   the same frame.
10. Put a UNIQLO piece labelled *simulated* on the board and Save. The `.md`
    piece list should say *colour simulated* beside it.

If anything on that list does not happen, the thing to write down is what you
tapped and what appeared instead.
