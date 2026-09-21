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
node studio/test/unit.mjs   # pure functions — no browser needed
node studio/test/e2e.mjs    # headless Chromium: load, filter, drag, save, reopen
```

`e2e.mjs` needs Playwright resolvable from the repository root. On this machine:

```
mkdir -p node_modules && ln -s /opt/node22/lib/node_modules/playwright node_modules/playwright
```

Neither test folder is deployed.

## Ten things to check on the iPad

1. Open the page in Safari. The shelf fills with pieces and the count top right
   reads `406 of 463`.
2. Type `aspesi` in the search box. The shelf narrows; clear it again.
3. Set **Any slot** to `shoes`, then tap **Clear**.
4. Tap **Matrix**, then tap a cell with a number in it — the shelf should jump
   back to a filtered list.
5. Tap **Inspiration…**, pick a look. It appears on the canvas, and
   **Matches this look** stops being greyed out — turn it on and watch the
   shelf reorder.
6. Press and drag a piece from the shelf onto the canvas. Drag it around, then
   use the round handles at its corner to resize and rotate it.
7. Fill all six slots — the chips at the bottom fill in as you go — and check
   the weight and formality reading beside them.
8. Turn **Numbers** on and off, type a title, and watch the swatch strip change
   as you add pieces.
9. Tap **Save**. The share sheet should offer four files; send them to Files or
   Working Copy. Check the PNG is 2160 × 2700 in Photos.
10. Close the tab, reopen the page — the board should still be there. Then tap
    **Open**, choose the `.json` you just saved, and confirm it comes back.

If anything on that list does not happen, the thing to write down is what you
tapped and what appeared instead.
