# content/palettes/

The palettes the styling desk offers as a working reference beside the canvas.
You choose one as the inspiration for a board. It sits beside the canvas while
you work and is saved with the outfit. It appears on the picture only when
**On board** is ticked.

| File | What |
|---|---|
| `trends-aw26-27.yaml` | the seed for this season's palettes, transcribed from the owner's brief of 24 Sept 2026 — external sources |
| `palettes.json` | **generated** by `content/tools/build_palettes.py`; do not edit by hand |

`build_studio.py` rebuilds `palettes.json` and copies it to `studio/data/`.

## What each palette carries

`id`, `name`, `category` (`season` / `family` / `trend`), `group`, `when` (one
plain sentence, a working note and not published text), 3 to 6 `colours`, and
`source`. Each colour has `hex`, `name`, `role` (dominant / secondary / accent)
and `share`; the shares add to 100. `placement` is `upper` / `mid` / `lower` /
`accessory` where the frameworks give one, and `null` where they don't.

- **Shares** follow the frameworks' own splits: 50 / 30 / 20 for three colours
  (combinations.md §3.6), 55 / 30 / 15 for four or more (colour-system.md §4).
  No source gives trend shares, so for trends the split is assigned by these
  rules and `share_basis` says so.
- **Placement** comes from only two framework rules. An accent-tier colour
  goes in small pieces (colour-system.md §6 → `accessory`). The season's
  `black` rule keeps black to bottoms, shoes, bags and hardware. The one other
  placement is Olive and Faded Rose's "rose near the face, olive as the body"
  (combinations.md §4). Everything else in the frameworks that places a colour
  needs the person's own colouring, so it cannot be written into a palette.
- **An accent-tier colour always takes the smallest share.** The 50/30/20
  split would otherwise put a Soft Autumn rust at 50% of an outfit. A pair of
  two accent-tier colours has no valid split and is listed under `gaps`.

## The three categories

**season (a)** — for each of the twelve seasons in `seasons.yaml`, built from:
each direction's colour on two of the season's neutrals (combinations.md §5),
each direction's best generated pair, and the top pair of each generator list.
Pairs come from `engine/generators.py` and bridges from its §3.6 rule. Soft
Autumn also carries the four worked examples of combinations.md §4. The repo
has no notion of "modern", so nothing here claims it.

**family (b)** — for each colour family, the version each season holds, with
every generated pair it takes part in (`combinations`). The family is the one
`content/tools/colour_names.py` measures from hue and chroma. Since 24 Sept
2026 that vocabulary files saturated colours correctly: true red is red,
cobalt blue, teal blue, camel brown, coral orange. 144 of the 153 chromatic
anchors now file; the rest are off-whites and rose beige, which take neutral
names. Where an anchor's own name points to another family, `gaps` says so as
`name differs`.

**trend (c)** — AW26/27, from the seed. Every palette is `confidence:
external` and names its sources as `web, Sept 2026, <url>`. Hexes are
re-expressed in the engine's space: each colour carries `engine` (Lab, LCh,
relative chroma, neutral). Each palette also carries `in_season` and
`near_season`, the combinations.md §6 filter (every colour within ΔE 15 of an
anchor, or all but one). Where the source gives alternatives with "or", each
pair is its own palette. Its third colour is a bridge from the set's own
neutrals (cream, anthracite) by §3.6.

**Soft Summer versions** move each colour to its nearest Soft Summer anchor.
A version is kept only if the result passes the rules any Soft Summer palette
would:

- nothing more than ΔE 16 from its anchor;
- at least three distinct colours;
- every chromatic pair valid under §5;
- every pair of neutrals at least 15 L* apart.

It is marked `derived` and keeps the trend's source. The reasons for every
trend that could not be translated are in `soft_summer_not_translated`.

## What the build found (24 Sept 2026)

- **Soft Summer produces no generated pair at all.** Every chromatic anchor
  sits between L\* 45 and 68, so no two are ever 15 (Opposition) or 25
  (Tonal, Muted) apart in value. The season has no muted depths — no dark
  teal, no soft burgundy, no cocoa — and so 19 of the 20 AW26/27 palettes have
  no Soft Summer version. The one that translates is T10a (soft white, graphite,
  dusty teal as the accent).
- **Gaps are listed, not filled**: generator lists that come out empty, pairs
  whose accent-tier colours conflict with colour-system §6, directions whose
  anchor is in no usable pair, families a season does not hold, and anchors
  left unfiled.
- Stand-in hexes in the seed (`hex_given: false`): pale pink, bordeaux, warm
  brown, white and black had no hex in the brief. Each is taken from another
  palette in the same brief and marked; confirm or replace them.
