# staples/

The staples catalogue — **source 2** in `matching.md` §5.

Not things found while browsing. A researched catalogue of reliable basics that
come in many colourways, so that any colour gap in a slot has a known, vetted
answer. The catalogue is small — twenty to forty items, researched once and
reviewed seasonally — so every entry is genuinely vetted.

Staples are the bridge, not the destination. They move someone from the wardrobe
they have toward the palette they should have, at low cost. The investment pieces
that define the destination wardrobe come from source 3 and the partnerships.

---

## Status of this folder

**Everything in here is an unconfirmed candidate.** These files were assembled as
a starting list of items that plausibly pass the rubric on fibre and expected wear
count, from brands widely available in Switzerland and Germany. They are the list
to research, not the result of research.

Specifically, in every file:

- `price` and `currency` are `unknown` — no price has been checked
- `hex` is `unknown` on every colourway — hexes must be **sampled from product
  photographs**, not guessed, or the ΔE matching in `matching.md` §2 is
  meaningless
- `url` and `affiliate` are blank
- `rubric_score` is blank — nothing has been scored
- `seasons_served` is `unknown` — it follows from the colourway hexes, so it
  cannot be filled before they are sampled
- `reviewed` is blank — nothing has been reviewed

Colourways are listed only where the colour is a reliable part of the range.
Retailers rotate colours every season, so even these need confirming.

---

## Schema

Copied from `matching.md` §5, source 2. Each staple is one item with a list of
colourways:

```yaml
- item: merino crew neck
  brand: uniqlo
  slot: top
  price: 40
  currency: EUR
  fibre: 100% extra-fine merino
  rubric_score: 9        # out of 15 (five fields, 0–3 each, frameworks/material-rubric.md): strong on fibre, wear count and price band; weak on origin
  seasons_served: [soft_autumn, true_autumn, soft_summer, true_summer, deep_winter]
  colourways:
    - {name: olive, hex: "5B6236", url: "…", affiliate: "…"}
    - {name: dark teal, hex: "1F5F63", url: "…", affiliate: "…"}
    - {name: camel, hex: "B89A6B", url: "…", affiliate: "…"}
    # …
  reviewed: 2026-10
```

### Field notes

- **`slot`** — singular, and one of the five slots in `matching.md`: `top`,
  `bottom`, `shoes`, `bag`, `accessory`. The filenames are plural; the field is
  not.
- **`item`** — the item's name. Its **slug** for `utm_content` (see
  `data/utm-scheme.md`) is this name hyphenated: `merino crew neck` →
  `merino-crew-neck`, and a specific colourway appends the colour.
- **`rubric_score`** — from `frameworks/material-rubric.md`, on its 0–15 scale
  (five fields, 0–3 each). The passing threshold lives in that file.
- **`reviewed`** — year and month of the last check. Any colourway older than six
  months is shown with a "check availability" flag rather than a confident link.
  Better a caveat than a dead link.

---

## Files

One file per slot:

| File | Slot |
|---|---|
| `tops.yaml` | `top` |
| `bottoms.yaml` | `bottom` |
| `shoes.yaml` | `shoes` |
| `bags.yaml` | `bag` |
| `accessories.yaml` | `accessory` |

---

## How a staple earns its place

A staple earns its place on fibre and wear count, not on being from a manifesto
brand. That is the "H&M if the quality justifies it" principle made concrete — and
it is why the brands in this folder mostly are not the brands in `brands/`. The
two folders answer different questions: `brands/` is where the destination
wardrobe comes from, `staples/` is what closes a gap this month.

One item covers many gaps, because the colourway list is what gets matched, not
the item. That is the whole reason to prefer items with deep colour ranges.

## Rules

- Never invent a price, a composition, a colourway or a URL. `unknown` and blank
  are correct answers.
- Sample hexes from photographs of the actual garment, and record which photo.
  A colour name is not a colour.
- Re-check colourways seasonally and update `reviewed`.
