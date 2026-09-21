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
                                 # long press, sideways drag, pinch, categories, review, frame
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
