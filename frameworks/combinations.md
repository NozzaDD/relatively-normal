# Combinations — the Wada mechanism

Sanzo Wada was a kimono and costume designer whose *A Dictionary of Color Combinations* (1933–34, 348 combinations, browsable at sanzo-wada.dmbk.io) was built by someone dressing bodies, not decorating rooms. His combinations are the reference this system generates from. This file turns his mechanism into a rule that runs on any season's palette.

## 1. Why this exists

A palette tells you which colours suit someone. It doesn't tell you which ones to put *together*. Two in-palette colours can still make a dull outfit, and the difference between dull and considered is combination logic — which is exactly what the first version of this system was missing.

The owner's own case: teal and ochre felt "simple but still out there, with colour vibration." That isn't taste; it's a mechanism, and it's Wada's.

## 2. The mechanism

A Wada combination has three properties at once:

| Property | Rule | Why it works |
|---|---|---|
| **Hue opposition** | Two hues 120–180° apart on the wheel — near-complementary or split-complementary | This is where the vibration comes from |
| **Chroma matched** | Both at the same saturation level: both muted, or both clear. Chroma C* within 10 of each other | Matched chroma is what stops opposition from shouting |
| **Value contrast** | One deep, one light. ΔL* ≥ 25 | Separation in value keeps the pair legible instead of muddy |

Saturated teal against saturated orange is a costume. The same hues pulled down to matched low chroma and set far apart in value read as considered. **The energy comes from the hue; the calm comes from the chroma; the clarity comes from the value.**

## 3. The generator

Given a season's palette from `seasons.yaml`, produce its combinations:

1. Take every pair of anchors across all three tiers.
2. Keep pairs where the hue angle difference (in Lab hue, h°) is between 120° and 180°.
3. Keep pairs where the chroma difference |C*₁ − C*₂| ≤ 10.
4. Keep pairs where the lightness difference |L*₁ − L*₂| ≥ 25.
5. For each surviving pair, name the **dominant** (deeper) and the **counter** (lighter). Dominant takes 60–70% of the outfit; counter takes 30–40%.
6. Optionally add a **bridge**: a foundation-tier neutral whose L* sits between the two. Three-colour combinations use dominant / counter / bridge at roughly 50 / 30 / 20.
7. Rank by hue separation (closer to 180° ranks higher) then by value contrast.

Soft seasons will produce muted pairs; bright seasons will produce clear ones. The rule is the same; the palette does the work.

**Direction re-weighting.** When the intake questions have chosen a direction (see `colour-system.md` §5), rank combinations containing that direction's anchor first. The owner's `teal_ochre` direction puts every teal-containing pair at the top.

## 4. Worked example — Soft Autumn

These four are the combinations that came out of the original analysis, restated with the generator's fields:

| Name | Dominant | Counter | Bridge | Hue gap | Notes |
|---|---|---|---|---|---|
| **Teal and Ochre** | deep teal `1F5F63` | ochre `C7912B` | warm mid grey `8B8378` | ~145° | The reference pair. Keep the teal deep and green-leaning, never cool-bright |
| **Petrol and Cinnamon** | petrol `2C5A66` | cinnamon `B5693C` | camel `B89A6B` | ~150° | Warmer counter than ochre; reads richer, good for outerwear |
| **Olive and Faded Rose** | dark olive `4E5A3A` | dusty rose `C09A93` | warm taupe `A8957C` | ~160° | The quietest pair. Rose near the face, olive as the body |
| **Plum and Old Gold** | soft plum `5C3A4E` | old gold `B8963E` | chocolate `4A3728` | ~130° | The most evening of the four; gold in small pieces only |

Every one of these passes the three tests: opposed hue, matched low chroma, wide value gap. That's the proof the generator reproduces the hand-made result.

## 5. Wada's dictionary as a personal subset

Wada's 348 combinations are public with hex values. Filter them against the user's palette:

- For each Wada combination, compute ΔE2000 from each of its colours to the nearest palette anchor.
- If **every** colour is within ΔE 15 → the combination is *in season*. Show it.
- If all but one are within 15 → *near*. Show it with the odd colour marked and its nearest in-season substitute.
- Otherwise hide it.

The result is a browsable booklet of Wada combinations that are actually wearable *by this person* — which is the thing the owner originally wanted, before the analysis existed to filter it. Different seasons get different subsets of the same 348; a Soft Autumn and a Bright Winter would share almost none.

## 6. Mood — the other Japanese reference

Shigenobu Kobayashi's *Color Image Scale* places combinations on two axes — **warm ↔ cool** and **soft ↔ hard** — and maps mood words onto the resulting quadrants: *natural, elegant, chic, casual, dynamic, gorgeous.*

That's the machinery behind intake question 2, "what do you want to feel like in your clothes":

| Answer keywords | Kobayashi region | Effect on ranking |
|---|---|---|
| calm, quiet, grounded, easy | soft | Prefer combinations with lower chroma and narrower value gap (ΔL* 25–35) |
| sharp, awake, noticed, precise | hard | Prefer wider value gaps (ΔL* ≥ 40) and the clearer end of the season |
| warm, cosy, soft | warm-soft | Weight toward the warm-leaning anchors |
| cool, clean, modern | cool-soft or cool-hard | Weight toward the cool-leaning anchors within the season |

Mood is a *ranking* input, never a filter. Nothing outside the season enters because of a mood word.

## 7. What the model does with this

- Names the combinations in the owner's register — "Petrol and Cinnamon", not "combination 7"
- Writes the one-line placement note ("rose near the face, olive as the body")
- Explains *why* a pair works, using the three properties, in a sentence a reader can repeat

## 8. What it never does

- Propose a pair the generator didn't produce
- Move a colour outside its palette to make a pair work
- Present a Wada combination as in-season when the filter said near
