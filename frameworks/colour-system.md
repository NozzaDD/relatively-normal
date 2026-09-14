# Colour System — the method

This file encodes how a personal palette is derived from photographs and preferences. It is written to run on any face, not one. `examples/nora-soft-autumn.yaml` is the first test case: when this method is applied to those photos, it must reproduce that result.

## 1. Three axes, not twelve boxes

Every person sits somewhere on three independent axes. The twelve "seasons" are just named regions of that space. Work in the axes; report the season.

| Axis | Range | What it's read from |
|---|---|---|
| **Temperature** | warm ↔ neutral ↔ cool | Skin undertone. Does the skin read golden/peachy or rosy/blue-pink? Which metal flatters, gold or silver? |
| **Value** | light ↔ medium ↔ deep | Overall darkness of hair, eyes and skin together. Not skin alone. |
| **Chroma** | soft/muted ↔ clear/bright | How much contrast and saturation the natural colouring carries. Soft = features blend; bright = features pop against each other. |

Each season has a **primary** characteristic (the axis that matters most) and a **secondary** one. The primary is what a wrong colour violates first.

## 2. Reading the axes from photographs

Requirements the app must enforce before analysis:

- Three photos minimum: face straight on, face in profile, and one including hair and shoulders
- **Natural daylight, indirect.** No overhead artificial light, no golden hour, no filter, no beauty mode
- Ideally no foundation or coloured makeup; lipstick removed
- Neutral background if possible; a white wall is best because it reveals white balance

The analysis is a judgement across all three photos, never one. Where photos disagree, weight the one with the most neutral background.

### Temperature
- Compare skin against a pure white reference in the same frame (the wall, a white top). Skin that looks golden or peach next to white → warm. Skin that looks pink, rose or slightly blue → cool. Skin that looks neither, or shifts with the reference → neutral.
- Veins on the inner wrist, if visible: greenish → warm; blue-purple → cool; mixed → neutral. Supporting evidence only.
- Hair: golden, copper, warm brown, warm black → warm. Ash, cool brown, blue-black, silver → cool.
- Eyes: amber, hazel with gold, warm green → warm. Grey, cool blue, cool green, black-brown → cool.

### Value
- Estimate hair, eye and skin on a 1–10 darkness scale, then combine. Light: average ≤ 4. Medium: 4–7. Deep: ≥ 7.
- Hair carries the most weight; it's the largest area near the face.

### Chroma
- Contrast **between** features: light skin with dark hair and clear eyes → high contrast → clear/bright. Features within a narrow value range → low contrast → soft.
- Saturation of eyes and hair: a vivid iris or vivid hair → bright. Greyed, dusty, muted tones → soft.

### Confidence
Output a confidence for each axis (high / medium / low) and **always return the top two seasons**, not one. Photo-based analysis is unreliable at the margins — lighting alone can move temperature a full step. A confident wrong answer is worse than a hedged right one.

**The runner-up season** is the season that differs from the winner on exactly one axis, choosing the axis with the lowest confidence. Flip that axis one step toward the centre-or-opposite reading that changes the season, hold the other two, and read the result from the table in §3. When two axes tie for lowest confidence, temperature is the one to flip — it is the axis photo analysis gets wrong most often. Example: a Soft Autumn read with chroma high, value high and temperature medium has Soft Summer as runner-up, because temperature is the least certain axis and it is the only one that separates the two.

## 3. Mapping axes to a season

| Primary | Secondary | Season |
|---|---|---|
| Light | Warm | Light Spring |
| Warm | Bright | True Spring |
| Bright | Warm | Bright Spring |
| Light | Cool | Light Summer |
| Cool | Soft | True Summer |
| Soft | Cool | Soft Summer |
| Soft | Warm | Soft Autumn |
| Warm | Deep | True Autumn |
| Deep | Warm | Deep Autumn |
| Deep | Cool | Deep Winter |
| Cool | Bright | True Winter |
| Bright | Cool | Bright Winter |

Decision order: identify the **dominant** axis first (the one furthest from centre), then the temperature lean, then read the season from the table. When two axes are equally dominant, temperature breaks the tie.

## 4. From season to palette

`seasons.yaml` holds the base palette for each season in three tiers:

- **Foundations, 55%** — the colours most of the wardrobe should be. Low-risk, combine with everything in the palette.
- **Supporting, 30%** — the colours that give the wardrobe its character.
- **Accents, 15%** — small pieces, scarves, a single statement item.

Plus, per season: metals, where black is allowed, where white is allowed, the natural contrast level to dress to, and an `avoid` list used by the matcher to flag the clearest misses.

## 5. Direction within a season — the three questions

A season is a region, not a point. Two Soft Autumns can look completely different: one leans **teal and ochre**, another **rust and olive**. The three intake questions pick the direction:

1. **What do you wear most?** (denim / tailoring / knitwear / dresses) — sets the *foundation texture* and shifts foundations toward the neutrals that suit that garment type:
   - denim → the blue-adjacent neutrals in the season
   - tailoring → the greys and browns
   - knitwear → the season's warm mid-tones; texture carries the depth, so the colour does not have to
   - dresses → the supporting tier; one garment covers the body, so it needs colour
2. **What do you want to feel like in your clothes?** (free text) — mapped to a direction keyword: *calm, grounded, quiet* → the muted end of the season; *sharp, awake, noticed* → the clearer end; *warm, soft, easy* → the warm-neutral end
3. **What do you reach for to look like yourself?** (free text) — the strongest signal. If they name a colour, that colour's family becomes the anchor of the supporting tier, provided it's inside the season.

Each season in `seasons.yaml` carries two or three named **directions**. The questions select one. The output palette is the season's base tiers, re-weighted toward the chosen direction.

## 6. Outfit rules that generalise

These are the rules from the original analysis, restated so they apply to every season rather than one person:

| Rule | Generalisation |
|---|---|
| "Black below the waist, or in leather and hardware" | For **soft** and **light** seasons, black stays away from the face: bottoms, shoes, bags, hardware. For **deep** and **bright** seasons black is a foundation and can sit anywhere. |
| "Rust in small pieces only" | Any accent-tier colour: small pieces, never a full garment near the face. |
| "Light and soft colours near the face" | Whatever tier holds the colours closest to the person's own skin and hair value goes nearest the face. |
| "Near-complementary pairs, contrast in the foundation tier" | The Wada mechanism, fully specified in `combinations.md`: opposed hue, matched chroma, wide value gap. Generated from the palette, not hand-picked. |
| "Match your contrast" | Dress to the natural contrast between features. Low-contrast people are overwhelmed by high-contrast outfits; high-contrast people look washed out in tonal ones. |

## 7. Combinations are a separate step

A palette answers "which colours". `combinations.md` answers "which colours together" — the Wada mechanism run over the season's anchors, ranked by the chosen direction and the mood answer. Both files are needed to produce what the original analysis produced by hand.

## 8. What this method does not do

- It does not assess body shape, fit or proportion. That's a separate system.
- It does not rank the twelve seasons by desirability. None is better.
- It does not override what someone loves. If question 3 names a colour outside the season, say so honestly and show the nearest in-season alternative — never silently swap it.
