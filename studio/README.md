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
| `js/render.js` | draws a board onto a canvas; the export path |
| `js/export.js` | PNG, JPEG, the info JSON, the markdown list, the share sheet |
| `js/app.js` | the UI, and the only file that touches the DOM |

`data.js` is the seam the brief asked for. `createStaticSource()` reads the
built JSON; `createMemorySource()` takes a catalogue object directly. The UI
only ever calls `load()`, `assetUrl()`, `thumbUrl()`, `inspirationUrl()` and
`inspirationThumbUrl()`.

## The shelf, the gate and Review

A product is on the shelf by default when it is a **clean flat cut-out** of
good quality, or when you have **reviewed** it. Everything else waits in the
Review tab until you decide; **Show unreviewed** brings it all in for a look.
New products from a later ingest follow the same rule.

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

## Touch

- A vertical swipe on the shelf scrolls it.
- A tap adds the piece to the middle of the canvas, each new one a little
  further along.
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
