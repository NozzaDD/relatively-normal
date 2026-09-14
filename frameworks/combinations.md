# Combinations — the Wada mechanism

Sanzo Wada was a kimono and costume designer whose *A Dictionary of Color Combinations* (1933–34, 348 combinations, browsable at sanzo-wada.dmbk.io) was built by someone dressing bodies, not decorating rooms. His combinations are the reference this system generates from. This file turns his mechanism into a rule that runs on any season's palette.

## 1. Why this exists

A palette tells you which colours suit someone. It doesn't tell you which ones to put *together*. Two in-palette colours can still make a dull outfit, and the difference between dull and considered is combination logic — which is exactly what the first version of this system was missing.

The owner's own case: teal and ochre felt "simple but still out there, with colour vibration." That isn't taste; it's a mechanism, and it's Wada's.

## 2. The mechanism

A Wada combination has three properties at once:

| Property | Rule | Why it works |
|---|---|---|
| **Hue opposition** | Two hues 100–180° apart on the wheel (Lab hue, h°) — near-complementary or split-complementary | This is where the vibration comes from |
| **Chroma matched** | Both at the same *relative* saturation: Δ relative chroma ≤ 0.20 | Matched chroma is what stops opposition from shouting |
| **Value contrast** | ΔL* ≥ 15 | Separation in value keeps the pair legible instead of muddy |

Saturated teal against saturated orange is a costume. The same hues pulled down to matched low chroma and set far apart in value read as considered. **The energy comes from the hue; the calm comes from the chroma; the clarity comes from the value.**

### Relative chroma

```
relative_chroma = C* / C*max(L*, h)
```

where **C\*max(L\*, h)** is the sRGB gamut boundary — the largest chroma that can be displayed at that lightness and hue. Relative chroma is the fraction of the available saturation a colour actually uses.

**Why the rule changed.** Absolute chroma (C\*) cannot be compared across hues, because the gamut is far wider at some hues and lightnesses than at others. A deep teal has almost no room to be saturated; a mid-lightness ochre has a great deal. Measured absolutely, deep teal `1F5F63` is C\* 20.2 and ochre `C7912B` is C\* 59.4 — a gap of 39, which reads as "one muted, one vivid" and fails a matched-chroma test. Measured relatively, deep teal sits at **0.846** of its gamut boundary and ochre at **0.850** — a difference of **0.004**. Both are as saturated as their corner of the gamut allows, which is exactly why they read as a matched pair. The absolute rule killed the reference pair; the relative rule keeps it.

## 3. The generators

Given a season's palette from `seasons.yaml`, two generators run over every pair of anchors across all three tiers. They share the chroma test and differ on hue and value.

| | Hue gap | Δ relative chroma | ΔL* |
|---|---|---|---|
| **Opposition** | 100–180° | ≤ 0.20 | ≥ 15 |
| **Tonal** | ≤ 40° | ≤ 0.20 | ≥ 25 |

Opposition is the Wada mechanism above. Tonal is the same discipline applied to one hue family: matched chroma and a wide value step, without the hue vibration.

For each generator:

1. Take every pair of anchors across all three tiers.
2. Keep pairs whose Lab hue gap is inside the generator's band.
3. Keep pairs where |relative_chroma₁ − relative_chroma₂| ≤ 0.20.
4. Keep pairs where |L*₁ − L*₂| meets the generator's minimum.
5. For each surviving pair, name the **dominant** (deeper) and the **counter** (lighter). Dominant takes 60–70% of the outfit; counter takes 30–40%.
6. Optionally add a **bridge**: a foundation-tier neutral whose L* sits between the two. Three-colour combinations use dominant / counter / bridge at roughly 50 / 30 / 20.
7. Rank within each generator by hue separation (opposition: closer to 180° ranks higher; tonal: closer to 0° ranks higher) then by value contrast.

**Ranking the two lists.** Opposition pairs rank first by default; tonal pairs follow. A mood answer of *calm, quiet* or *grounded* (intake question 2) promotes the tonal list above the opposition list. Mood is a ranking input, never a filter — both lists are always produced.

Soft seasons will produce muted pairs; bright seasons will produce clear ones. The rule is the same; the palette does the work.

**Direction re-weighting.** When the intake questions have chosen a direction (see `colour-system.md` §5), rank combinations containing that direction's anchor first within each list. The owner's `teal_ochre` direction puts every teal-containing pair at the top.

## 4. Worked example — Soft Autumn

These four are the combinations that came out of the original analysis. Every number below is computed from the hex values in `seasons.yaml` (sRGB → CIELAB, D65); nothing is estimated.

| Name | Dominant | Counter | Bridge | Hue gap | Δ rel. chroma | ΔL* | Generator |
|---|---|---|---|---|---|---|---|
| **Teal and Ochre** | deep teal `1F5F63` | ochre `C7912B` | warm mid grey `8B8378` | 125.0° | 0.00 (0.85 / 0.85) | 27.1 | **Opposition** — passes all three |
| **Petrol and Cinnamon** | petrol `2C5A66` | cinnamon `B5693C` | camel `B89A6B` | 169.3° | 0.10 (0.72 / 0.62) | 16.5 | **Opposition** — passes all three |
| **Olive and Faded Rose** | dark olive `4E5A3A` | dusty rose `C09A93` | warm taupe `A8957C` | 88.2° | 0.13 (0.40 / 0.27) | 30.4 | **Unresolved — see note** |
| **Plum and Old Gold** | soft plum `5C3A4E` | old gold `B8963E` | chocolate `4A3728` | 104.5° | 0.40 (0.33 / 0.73) | 34.6 | **Neither** — a deliberate chroma step |

**Teal and Ochre** is the reference pair. Keep the teal deep and green-leaning, never cool-bright.

**Petrol and Cinnamon** — warmer counter than ochre; reads richer, good for outerwear. The narrowest value gap of the four, and the reason the opposition minimum is 15 rather than 25. Note the camel bridge sits *above* both in lightness (L\* 65.3), not between them; a bridge that meets §3.6 would be warm mid grey.

**Olive and Faded Rose** — the quietest pair. Rose near the face, olive as the body. *Owner decision needed:* this pair was designated tonal, but its computed hue gap is 88.2°, outside the tonal band (≤ 40°) and outside the opposition band (≥ 100°). It passes both generators' chroma and value tests. As the thresholds stand it is produced by neither generator; the row is left unclassified rather than mislabelled.

**Plum and Old Gold** — the most evening of the four; gold in small pieces only. This one is not a matched-chroma pair and was never meant to be: a low-saturation plum (0.33) against a near-saturated gold (0.73) is a **deliberate chroma step**, the gold doing the work an accent does. It sits outside both generators, and it is kept here as the example of what the generators do not produce — a pair that works for a reason the mechanism does not encode. The chocolate bridge is deeper than both (L\* 24.8), not between them.

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
| calm, quiet, grounded, easy | soft | Promote the tonal list above the opposition list (§3); within each, prefer lower chroma and a narrower value gap |
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
