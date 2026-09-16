# The trial — one occasion, one month

The first slice of the wardrobe tool, narrow on purpose. Not a smaller product:
the same engine, asked a smaller question. The full path is still there and
still works — see `frameworks/scope.md` for what is deliberately unused.

**The ask: your work outfits for October.**

## What to send

**Sixteen items, plus two coats.** Enough to build a working week from, few
enough to photograph in one sitting.

The sixteen are the ones an outfit needs: tops, bottoms, shoes, bags and
accessories. The two layers are the seventeenth and eighteenth — the engine
treats `layer` as optional and never counts an empty one as a gap — but send
them, because the rain outfit requires one.

| How many | Slot | What counts |
|---|---|---|
| 4 | `top` | shirts, knits, blouses — whatever goes on top at work |
| 4 | `bottom` | trousers, skirts, jeans |
| 2 | `shoes` | the two pairs you actually wear to work |
| 2 | `bag` | what you carry |
| 2 | `accessory` (jewellery) | `near_face` **false** |
| 2 | `accessory` (scarves) | `near_face` **true** |
| 2 | `layer` | coat, jacket, cardigan — anything worn over the top |

**Four outfits** you would actually wear this month:

| # | Weather | What it is |
|---|---|---|
| 1 | clear | a normal work day |
| 2 | clear | a different normal work day |
| 3 | rain | the same week, wet |
| 4 | clear | outfit 1 or 2 taken from daytime into the evening |

Every outfit carries a **formality** (`corporate` or `casual`) and a **setting**
(`office` or `home`), so all four combinations can be expressed: corporate in
the office, corporate at home on camera, casual in the office, casual at home.
Fill them honestly — they change which slots are judged at the face.

## The two files

`items.csv` and `outfits.csv` here are stubbed with the right number of rows and
all the columns. Fill them in, keep the row counts, and run:

```sh
python -m engine.run --season soft_autumn --direction teal_ochre \
    --items items.csv --outfits outfits.csv --trial --occasion work --month October \
    --out result.html
```

Column meanings are in `templates/README.md` — the trial uses the same two
formats, nothing special. `life_weight` matters more here than anywhere: with
four outfits it is what decides which gap gets fixed first.

## What you get back

Everything the full run gives except two things: no "missing from the closet"
list (sixteen items cannot say what a whole wardrobe lacks), and the long-term
horizon is replaced by **what this slice actually showed** — plus, as plainly,
what it could not.

## Photographs

`engine/examples/photos/README.md` has the naming convention and the
photographing rules. `jewellery_`, `scarf_`, `bag_`, `shoes_` and the rest map
straight onto the slots above, so intake fills most of `items.csv` for you.
