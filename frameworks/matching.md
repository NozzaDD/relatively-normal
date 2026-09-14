# Matching — from cutouts to verdicts

This is the deterministic half of the product. No language model runs here. Everything is arithmetic on colours, and every verdict can be explained by pointing at a number.

## 1. Extract the item's colours

Input: a transparent PNG cutout.

1. Take only pixels with alpha > 200. Ignore the fringe — anti-aliased edges are contaminated by whatever was behind the item.
2. Downsample to roughly 20,000 pixels. Colour extraction doesn't need more, and it keeps the app fast on a tablet.
3. Convert every pixel from sRGB to **CIELAB** (D65 illuminant). Never cluster in RGB — distances in RGB don't match how eyes see difference.
4. Run k-means with k = 3 in Lab space. Keep clusters holding more than 8% of pixels.
5. Output up to three colours as `{lab, hex, share}` ordered by share. The first is the item's **dominant colour**.

Patterned items produce two or three meaningful clusters; plain items produce one dominant and two noise clusters that the 8% floor removes.

## 2. Score against the palette

For each extracted colour, compute **ΔE2000** against every anchor in the user's palette — all three tiers plus the `avoid` list from `seasons.yaml`.

| Nearest anchor's ΔE | Verdict |
|---|---|
| ≤ 12 | **In palette** — matches that anchor |
| 12 – 20 | **Near** — report the nearest anchor and what would need to shift (lighter, warmer, softer) |
| > 20 | **Out** — report the nearest anchor anyway, so the user sees what the item *would* need to be |
| ≤ 12 to an `avoid` colour | **Hard miss** — flag explicitly; this overrides a "near" against a real anchor |

Thresholds are starting points. They should be tuned against the beta consultations: every judgement the owner makes by hand in November is a labelled example of where the line actually sits.

An item's verdict is its dominant colour's verdict, with secondary colours reported but not scored — a navy coat with brass buttons is navy.

## 3. Score the outfit

Once items sit in the five slots, three checks run on the set:

**Coverage.** Which slots are empty. Reported as plain text: *Missing: bottom, shoes.* This is the gap detector and it's a lookup, not an algorithm.

**Palette share.** Count items by verdict. Report *4 of 5 in palette; the bag is out (nearest: chocolate).* The bag is now a candidate gap.

**Tier balance.** Compare the outfit's tier mix to the 55/30/15 target by item count, weighted by how much of the body each slot covers (top and bottom count double). An outfit that's three accents and no foundation gets flagged: *Accent-heavy — a foundation-tier top would settle this.*

**Contrast.** Compute the Lab lightness range across the outfit's dominant colours. Compare to the season's `contrast` level. A low-contrast season wearing a 70-point lightness spread gets: *Higher contrast than your natural colouring; consider closing the gap between top and bottom.*

## 4. Rank the gaps

A gap is any of: an empty slot; an out-of-palette item in a filled slot; a tier imbalance; a contrast mismatch. Rank them by **how many outfits the fix would unlock** — an empty bottom slot that appears in four of five saved outfits outranks a slightly-off scarf in one.

The top three ranked gaps are what the monthly recommendation run works from. Nothing else is sent.

## 5. Fill the gaps — three sources, in strict order

For each ranked gap, the system looks for a fill. **It checks the sources in this order and stops at the first that produces a good match.** Buying is the last resort, not the first suggestion — that ordering is the product's whole argument, and it's what makes the affiliate link trustworthy when it does appear.

### Source 1 — the user's own closet

Everything they uploaded, not just what's on the canvas. Filter to the missing slot, score each candidate's dominant colour against the palette *and* against the other items already in the outfit (a Wada pair check from `combinations.md`). If an in-palette item exists that pairs with what's there:

> *You already own this: the olive trousers. They sit in your foundation tier and pair with the teal knit.*

No link, no purchase. This is the answer most of the time for people who've uploaded seventeen items, and delivering it builds the trust that makes source 3 convert.

### Source 2 — the staples catalogue

**Not things found while browsing. A researched catalogue of reliable basics that come in many colourways**, so that any colour gap in a slot has a known, vetted answer. The Uniqlo merino crew in ten colours. The Sunspel tee in twelve. The pair of trousers that exists in every foundation neutral.

Each staple is one item with a list of colourways:

```yaml
- item: merino crew neck
  brand: uniqlo
  slot: top
  price: 40
  currency: EUR
  fibre: 100% extra-fine merino
  rubric_score: 9        # passes on fibre, wear count and price-per-wear; not on origin
  seasons_served: [soft_autumn, true_autumn, soft_summer, true_summer, deep_winter]
  colourways:
    - {name: olive, hex: "5B6236", url: "…", affiliate: "…"}
    - {name: dark teal, hex: "1F5F63", url: "…", affiliate: "…"}
    - {name: camel, hex: "B89A6B", url: "…", affiliate: "…"}
    # …
  reviewed: 2026-10
```

**Matching a gap to a staple:** filter to the gap's slot, then for each staple find its colourway nearest the gap's target anchor. If the nearest colourway is within ΔE 12 and the staple's rubric score clears the threshold, it's a match. Output the *specific colourway*:

> *Nothing in your closet fills this. The merino crew in dark teal does: €40, pure merino, sits in your foundation tier and pairs with five of your items.*

**Why staples are the right source 2:**

- The catalogue is small — twenty to forty items, researched once by the owner and reviewed seasonally — so every entry is genuinely vetted
- One item covers many gaps, because the colourway list is what's matched, not the item
- It's the "H&M if the quality justifies it" principle made concrete: a staple earns its place on fibre and wear count, not on being from a manifesto brand
- It's cheap, which is what the short-term horizon needs (`horizons.md` §3d)

**Staples are the bridge, not the destination.** They move someone from the wardrobe they have toward the palette they should have, at low cost. The investment pieces that define the destination wardrobe come from source 3 and the partnerships. Both appear on the result screen; they serve different horizons.

**Colourways go stale.** Retailers drop and add colours every season. Each staple carries a `reviewed` date, and any colourway older than six months is shown with a "check availability" flag rather than a confident link. Better a caveat than a dead link.

### Source 3 — the brand database, live

Only when sources 1 and 2 return nothing. Search the catalogues of brands in `brands/` that pass the rubric, via their affiliate feeds, for the slot and target colour. Return the best three by colour distance, rubric score and price band. The model writes the rationale; the matcher chose the items.

If source 3 also returns nothing, say so:

> *No good match this month. The gap is real; the right piece hasn't appeared yet. I'll check again next run.*

That sentence is worth more than a bad recommendation.

### Why the order is fixed

| Source | Trust it builds | Revenue |
|---|---|---|
| Own closet | Highest — the tool found something they forgot | None |
| Staples catalogue | High — vetted basics in the exact colourway needed | Affiliate |
| Live brand search | Medium — algorithmic, but rubric-filtered | Affiliate |

A product that led with source 3 would be a shopping newsletter with extra steps. Leading with source 1 is what makes people believe source 3 when it finally shows up.

### For the MVP

Source 1 is a lookup and ships first. Source 2 is the right MVP for recommendations: the owner researches twenty staples, the system matches colourways — that is the concierge model from the beta, automated one step. Source 3 needs affiliate feed integration and comes with Phase B.

## 6. Output schema

What the matcher returns for an outfit, and what the recommendation step consumes:

```json
{
  "outfit_id": "…",
  "slots": {
    "top":       {"item_id": "…", "dominant": {"hex": "1F5F63", "lab": [36, -14, -8]}, "verdict": "in", "nearest": "deep teal", "delta_e": 4.1},
    "bottom":    null,
    "shoes":     {"item_id": "…", "dominant": {"hex": "000000", "lab": [0, 0, 0]}, "verdict": "in", "nearest": "black (below waist)", "delta_e": 0},
    "bag":       {"item_id": "…", "dominant": {"hex": "7B4F2E", "lab": [38, 15, 24]}, "verdict": "near", "nearest": "chocolate", "delta_e": 15.2},
    "accessory": null
  },
  "checks": {
    "coverage":   {"missing": ["bottom", "accessory"]},
    "palette":    {"in": 2, "near": 1, "out": 0, "hard_miss": 0},
    "tier_mix":   {"foundation": 0.67, "supporting": 0.33, "accent": 0.0, "flag": null},
    "contrast":   {"lightness_range": 36, "season_target": "low", "flag": null}
  },
  "gaps_ranked": [
    {"type": "empty_slot", "slot": "bottom", "unlocks": 4,
     "fill": {"source": "closet", "item_id": "…", "reason": "in palette, pairs with top"}},
    {"type": "near_miss", "slot": "bag", "nearest": "chocolate", "unlocks": 1,
     "fill": {"source": "staple", "item": "merino crew neck", "brand": "uniqlo", "colourway": "dark teal", "hex": "1F5F63", "delta_e": 3.2, "price": 40, "affiliate": true, "rubric": 9, "pairs_with": 5}}
  ]
}
```

The language model receives this JSON and writes the sentence a person reads. It never computes anything in it.

## 7. What the model is allowed to do with it

- Turn `gaps_ranked` into a short, human paragraph in the owner's voice
- Turn "nearest: chocolate, ΔE 15" into "this is close — a slightly deeper brown would land it"
- Explain *why* a tier flag matters in one sentence

## 8. What it is never allowed to do

- Change a verdict
- Suggest a colour that isn't in the palette
- Suggest an item that isn't in the brand database with a real link
- Score anything. If a number is needed, it comes from section 2, 3, 4 or 5.
- Skip a source. If the closet had an answer, the closet's answer is the answer.
