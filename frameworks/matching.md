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

Each extracted colour is evaluated in a fixed order. The first stage that returns a verdict wins; later stages do not run.

1. **Slot-conditional rules** — the season's `black` and `white` fields in `seasons.yaml`, which depend on which of the five slots the item sits in.
2. **Avoid list** — the season's clearest misses.
3. **Palette anchors** — ΔE2000 against every anchor in the three tiers.

The order matters. Black is in Soft Autumn's `avoid` list *and* allowed below the waist; if the avoid list ran first, correctly-worn black trousers would fail. Rules first, then misses, then matches.

### Stage 1 — slot-conditional rules

A rule fires when the item's dominant colour is within **ΔE2000 ≤ 8** of the rule colour: `000000` for the black rule, `FFFFFF` for the white rule. Cream, soft white and warm white are ordinary anchors and are scored in stage 3 like any other colour; the white rule exists to catch *optic* white specifically.

Every rule names a colour that exists as an anchor for that season (CLAUDE.md, hard rule 5), so `nearest` is always a real anchor name.

**Black** — by `black` field value and slot:

| `black` | top | accessory, `near_face: true` | bottom | shoes | bag | accessory, `near_face: false` | `nearest` |
|---|---|---|---|---|---|---|---|
| `anywhere` | in | in | in | in | in | in | black |
| `anywhere_with_warm_partner` | in | in | in | in | in | in | black — plus an outfit flag in §3 if no warm-tier item is present |
| `below_waist_or_hardware` | **out** — *black works on you, just not next to your face* | **out** — same reason | in | in | in | in | black (below waist) for bottom and shoes; black (hardware) for bag and hardware accessories; black for top and near-face accessories |
| `away_from_face` | **out** — *black works on you, just not next to your face* | **out** — same reason | in | in | in | in | black (away from face) for the allowed slots; black for top and near-face accessories |
| `avoid` | hard miss | hard miss | hard miss | hard miss | hard miss | hard miss | black |

**White** (item within ΔE 8 of `FFFFFF`) — by `white` field value and slot:

| `white` | top | accessory, `near_face: true` | bottom | shoes | bag | accessory, `near_face: false` | `nearest` |
|---|---|---|---|---|---|---|---|
| `pure_white` | in | in | in | in | in | in | pure white |
| `anywhere` | in | in | in | in | in | in | the season's white anchor (warm white or pure white) |
| `soft_white` | **near** — *a softer white next to your face* | **near** — same reason | in | in | in | in | soft white |
| `cream_or_warm_white` | **near** — *cream or a warm white next to your face* | **near** — same reason | in | in | in | in | warm white |
| `cream_only` | **hard miss** — *cream, not white, next to your face* | **hard miss** — same reason | in | in | in | in | cream |

**Accessories carry a `near_face` flag, set at tagging.** Scarves and hats are `true`; belts, jewellery and watches are `false`. The vision model proposes the flag and the user confirms it. When `near_face` is true the accessory is evaluated under the top slot's rules for black and white; when false, under the hardware rules. The flag is stored on the item and is what stage 1 reads.

**The layer slot** (coat, jacket, cardigan) is a face position for the black and white rules — the top column above — only when the outfit has no in-palette accessory with `near_face: true`. When such an accessory is present, the accessory is the face colour and the layer is evaluated as away from the face, under the bottom / shoes / bag column, with `nearest` reported as *black (away from face)*. A scarf sits between the collar and the face. Scored on its own, outside an outfit, a layer is at the face.

Only the `below_waist_or_hardware` row of the black table was specified by the owner; the remaining rows follow the same pattern (the top slot and near-face accessories are the face positions, the rest are not) and are to be confirmed.

### Stage 2 — avoid list

Compute ΔE2000 from the colour to every entry in the season's `avoid` list.

| Nearest avoid colour's ΔE | Verdict |
|---|---|
| ≤ 8 | **Hard miss** — flag explicitly; report the avoid colour hit |

Stage 2 runs only if no stage-1 rule fired, so black on the bottom of a `below_waist_or_hardware` season never reaches it.

### Stage 3 — palette anchors

Compute ΔE2000 against every anchor in the three tiers.

| Nearest anchor's ΔE | Verdict |
|---|---|
| ≤ 12 | **In palette** — matches that anchor |
| 12 – 16 | **Near** — report the nearest anchor and what would need to shift (lighter, warmer, softer) |
| > 16 | **Out** — report the nearest anchor anyway, so the user sees what the item *would* need to be |

Thresholds are starting points. They should be tuned against the beta consultations: every judgement the owner makes by hand in November is a labelled example of where the line actually sits.

An item's verdict is its dominant colour's verdict, with secondary colours reported but not scored — a navy coat with brass buttons is navy.

## 3. Score the outfit

Items sit in six slots: **top, bottom, layer, shoes, bag, accessory**. The layer (coat, jacket, cardigan — anything worn over the top) is optional and is never a coverage gap. Every item also carries two attributes set at tagging: **dressiness** (1–4, casual to dressy) and **weight** (1–4, light to heavy — thermal warmth, not colour temperature). Outfits carry an **occasion**, a **dress code** (1–5) and **weather** (clear or rain).

These checks run on the set:

**Coverage.** Which slots are empty. Reported as plain text: *Missing: bottom, shoes.* This is the gap detector and it's a lookup, not an algorithm.

**Palette share.** Count items by verdict. Report *4 of 5 in palette; the bag is out (nearest: chocolate).* The bag is now a candidate gap.

**Tier balance.** Compare the outfit's tier mix to the 55/30/15 target by item count, weighted by how much of the body each slot covers (top and bottom count double). An outfit that's three accents and no foundation gets flagged: *Accent-heavy — a foundation-tier top would settle this.*

**Contrast.** Compute the Lab lightness range across the outfit's dominant colours. Compare to the season's `contrast` level. A low-contrast season wearing a 70-point lightness spread gets: *Higher contrast than your natural colouring; consider closing the gap between top and bottom.*

**Zone fit.** Every filled item's dressiness must be within 1 of the occasion's dress code. Otherwise flag the item: *too casual* when it sits below, *too dressy* when it sits above. Not checked when the outfit has no occasion.

**Weather fit.** If the weather is rain, the layer slot is required and the outfit's heaviest item must have weight ≥ 3; otherwise flag *not enough for rain*. In clear weather the layer is optional.

**Context fit.** Outfits carry a **formality** (corporate or casual; casual when blank) and a **setting** (office or home; office when blank). When formality is corporate, every item in a *face-visible* slot must be in the season's `corporate` list in `seasons.yaml` — in palette, and admitted against an anchor on that list — else flag *not corporate*, naming the item. Face-visible slots are top, layer and accessory when the setting is home (what the camera sees); every slot when the setting is office.

An outfit *works now* (`horizons.md` §3c) when it passes the pairing rules in `combinations.md` §5 and the zone, weather and context checks.

## 4. Rank the gaps

A gap is any of: an empty slot; an out-of-palette item in a filled slot; an item flagged too casual or too dressy; an outfit not enough for rain; a tier imbalance; a contrast mismatch; a **zone gap** — for each occasion, a slot where the closet holds no item within 1 of the dress code, phrased *no [slot] dressy enough for [occasion]*; and a **context gap** — for each corporate occasion, a face-visible slot where the closet holds no item from the corporate list, phrased *no corporate [slot] for [occasion]*. Rank them by **how many outfits the fix would unlock** — the count of outfits the fix would complete or repair — so an empty bottom slot that appears in four of five saved outfits outranks a slightly-off scarf in one.

The top three ranked gaps are what the monthly recommendation run works from. Nothing else is sent.

## 5. Fill the gaps — three sources, in strict order

For each ranked gap, the system looks for a fill. **It checks the sources in this order and stops at the first that produces a good match.** Buying is the last resort, not the first suggestion — that ordering is the product's whole argument, and it's what makes the affiliate link trustworthy when it does appear.

### Source 1 — the user's own closet

Everything they uploaded, not just what's on the canvas. Filter to the missing slot, score each candidate's dominant colour against the palette *and* against the other items already in the outfit (the outfit pairing rules in `combinations.md` §5). If an in-palette item exists that pairs with what's there:

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
  rubric_score: 9        # out of 15 (five fields, 0–3 each, frameworks/material-rubric.md): strong on fibre, wear count and price band; weak on origin
  seasons_served: [soft_autumn, true_autumn, soft_summer, true_summer, deep_winter]
  colourways:
    - {name: olive, hex: "5B6236", url: "…", affiliate: "…"}
    - {name: dark teal, hex: "1F5F63", url: "…", affiliate: "…"}
    - {name: camel, hex: "B89A6B", url: "…", affiliate: "…"}
    # …
  reviewed: 2026-10
```

**Matching a gap to a staple:** filter to the gap's slot, then for each staple find its colourway nearest the gap's target anchor. If the nearest colourway is within ΔE 12 and the staple's rubric score clears the passing threshold (set in `frameworks/material-rubric.md`, on the 0–15 scale), it's a match. Output the *specific colourway*:

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
    "layer":     null,
    "accessory": null
  },
  "occasion": "work", "dress_code": 3, "weather": "clear", "formality": "corporate", "setting": "office",
  "checks": {
    "coverage":   {"missing": ["bottom", "accessory"]},
    "palette":    {"in": 2, "near": 1, "out": 0, "hard_miss": 0},
    "tier_mix":   {"foundation": 0.67, "supporting": 0.33, "accent": 0.0, "flag": null},
    "contrast":   {"lightness_range": 36, "season_target": "low", "flag": null},
    "zone":       {"dress_code": 3, "flags": [{"item_id": "…", "slot": "accessory", "dressiness": 1, "flag": "too casual"}]},
    "weather":    {"weather": "clear", "layer_present": false, "heaviest": 3, "flag": null},
    "context":    {"formality": "corporate", "setting": "office", "face_visible": ["top", "bottom", "layer", "shoes", "bag", "accessory"], "flags": [{"item_id": "…", "slot": "accessory", "flag": "not corporate"}]}
  },
  "gaps_ranked": [
    {"type": "empty_slot", "slot": "bottom", "unlocks": 4,
     "fill": {"source": "closet", "item_id": "…", "reason": "in palette, pairs with top"}},
    {"type": "near_miss", "slot": "bag", "nearest": "chocolate", "unlocks": 1,
     "fill": {"source": "staple", "item": "merino crew neck", "brand": "uniqlo", "colourway": "dark teal", "hex": "1F5F63", "delta_e": 3.2, "price": 40, "affiliate": true, "rubric": 9, "pairs_with": 5}}
  ]
}
```

Every item carries `dressiness` (1–4) and `weight` (1–4) from tagging; accessory items additionally carry `near_face` (true / false) — see §2, stage 1. Each slot entry in the JSON reports them alongside the verdict. With saved outfits the matcher returns one such block per outfit and a single `gaps_ranked` across all of them.

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
