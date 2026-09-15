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

Given a season's palette from `seasons.yaml`, three generators run over every pair of **chromatic** anchors across all three tiers. A **neutral** is any anchor or item with relative chroma ≤ 0.15; neutrals do not enter the generators (see §5). The generators partition the hue circle — Tonal ≤ 40°, Muted 40–100°, Opposition 100–180° — so every pair falls into exactly one band and is tested by that band's generator.

| | Hue gap | Relative chroma of each | Δ relative chroma | ΔL* |
|---|---|---|---|---|
| **Opposition** | 100–180° | — | ≤ 0.20 | ≥ 15 |
| **Tonal** | ≤ 40° | — | ≤ 0.20 | ≥ 25 |
| **Muted** | 40–100° | both ≤ 0.45 | ≤ 0.15 | ≥ 25 |

Opposition is the Wada mechanism above. Tonal is the same discipline applied to one hue family: matched chroma and a wide value step, without the hue vibration. Muted fills the band between them: in the middle band neither opposition nor analogy is doing the work, so the pair only holds when both colours are quiet and the value gap carries it — hence the cap on each colour's relative chroma, the tighter chroma match, and the wider value minimum.

For each generator:

1. Take every pair of chromatic anchors (relative chroma > 0.15) across all three tiers.
2. Keep pairs whose Lab hue gap is inside the generator's band.
3. Keep pairs where |relative_chroma₁ − relative_chroma₂| is within the generator's limit. Muted additionally requires each colour's relative chroma ≤ 0.45.
4. Keep pairs where |L*₁ − L*₂| meets the generator's minimum.
5. For each surviving pair, name the **dominant** (deeper) and the **counter** (lighter). Dominant takes 60–70% of the outfit; counter takes 30–40%.
6. Optionally add a **bridge**: a foundation-tier neutral — relative chroma ≤ 0.15, by the definition in §5 — whose L* sits between the two. Three-colour combinations use dominant / counter / bridge at roughly 50 / 30 / 20.
7. Rank within each generator: opposition by hue separation (closer to 180° ranks higher) then value contrast; tonal by hue separation (closer to 0° ranks higher) then value contrast; muted by value contrast then hue separation, since in that band the value gap is what carries the pair.

**Ranking the three lists.** Default order is Opposition, then Tonal, then Muted. A mood answer of *calm, quiet* or *grounded* (intake question 2) promotes Tonal and Muted above Opposition, keeping Tonal ahead of Muted. Mood is a ranking input, never a filter — all three lists are always produced.

Soft seasons will produce muted pairs; bright seasons will produce clear ones. The rule is the same; the palette does the work.

**Direction re-weighting.** When the intake questions have chosen a direction (see `colour-system.md` §5), rank combinations containing that direction's anchor first within each of the three lists. The owner's `teal_ochre` direction puts every teal-containing pair at the top.

## 4. Worked example — Soft Autumn

These four are the combinations that came out of the original analysis. Every number below is computed from the hex values in `seasons.yaml` (sRGB → CIELAB, D65); nothing is estimated.

| Name | Dominant | Counter | Bridge | Hue gap | Δ rel. chroma | ΔL* | Generator |
|---|---|---|---|---|---|---|---|
| **Teal and Ochre** | deep teal `1F5F63` | ochre `C7912B` | warm mid grey `8B8378` | 125.0° | 0.00 (0.85 / 0.85) | 27.1 | **Opposition** — passes all three |
| **Petrol and Cinnamon** | petrol `2C5A66` | cinnamon `B5693C` | camel `B89A6B` | 169.3° | 0.10 (0.72 / 0.62) | 16.5 | **Opposition** — passes all three |
| **Olive and Faded Rose** | dark olive `4E5A3A` | dusty rose `C09A93` | warm taupe `A8957C` | 88.2° | 0.13 (0.40 / 0.27) | 30.4 | **Muted** — passes all four |
| **Plum and Old Gold** | soft plum `5C3A4E` | old gold `B8963E` | chocolate `4A3728` | 104.5° | 0.40 (0.33 / 0.73) | 34.6 | **None** — a deliberate chroma step |

**Teal and Ochre** is the reference pair. Keep the teal deep and green-leaning, never cool-bright.

**Petrol and Cinnamon** — warmer counter than ochre; reads richer, good for outerwear. The narrowest value gap of the four, and the reason the opposition minimum is 15 rather than 25. Note the camel bridge sits *above* both in lightness (L\* 65.3), not between them; a bridge that meets §3.6 would be warm mid grey.

**Olive and Faded Rose** — the quietest pair. Rose near the face, olive as the body. A Muted pair: at 88.2° the hues are neither opposed nor analogous, so in this middle band neither opposition nor analogy is doing the work — the pair only holds because both colours are quiet (0.40 and 0.27, under the 0.45 cap) and the value gap of 30.4 carries it.

**Plum and Old Gold** — the most evening of the four; gold in small pieces only. This one is not a matched-chroma pair and was never meant to be: a low-saturation plum (0.33) against a near-saturated gold (0.73) is a **deliberate chroma step**, the gold doing the work an accent does. Its hue gap puts it in the opposition band, but a Δ relative chroma of 0.40 fails every generator's chroma test. It sits outside all three, and it is kept here as the example of what the generators do not produce — a pair that works for a reason the mechanism does not encode. The chocolate bridge is deeper than both (L\* 24.8), not between them.

## 5. Neutrals are the ground

A **neutral** is any anchor or item with **relative chroma ≤ 0.15**. Neutrals do not enter the three generators; the generators run over chromatic anchors only. A generated pair is two colours; the neutrals are what the pair sits on.

These are the pairing rules for an outfit. They run after the slot rules for black and white in `matching.md` §2 have already been applied, so every item arrives with its verdict.

| Pair | Valid when |
|---|---|
| **Chromatic + chromatic** | The pair matches a generated pair: each item is within ΔE 12 of one of that pair's two anchors |
| **Chromatic + neutral** | Both are in palette |
| **Neutral + neutral** | ΔL* ≥ 15; otherwise flag as **flat** |
| **Three or more chromatic items** | Every chromatic pair must be valid; otherwise flag as **too many colours** |

An outfit is valid when every pair in it is valid. This is what "works now" (`horizons.md` §3c) and the closet search (`matching.md` §5, source 1) are built from.

## 6. Wada's dictionary as a personal subset

Wada's 348 combinations are public with hex values. Filter them against the user's palette:

- For each Wada combination, compute ΔE2000 from each of its colours to the nearest palette anchor.
- If **every** colour is within ΔE 15 → the combination is *in season*. Show it.
- If all but one are within 15 → *near*. Show it with the odd colour marked and its nearest in-season substitute.
- Otherwise hide it.

The result is a browsable booklet of Wada combinations that are actually wearable *by this person* — which is the thing the owner originally wanted, before the analysis existed to filter it. Different seasons get different subsets of the same 348; a Soft Autumn and a Bright Winter would share almost none.

## 7. Mood — the other Japanese reference

Shigenobu Kobayashi's *Color Image Scale* places combinations on two axes — **warm ↔ cool** and **soft ↔ hard** — and maps mood words onto the resulting quadrants: *natural, elegant, chic, casual, dynamic, gorgeous.*

That's the machinery behind intake question 2, "what do you want to feel like in your clothes":

| Answer keywords | Kobayashi region | Effect on ranking |
|---|---|---|
| calm, quiet, grounded, easy | soft | Promote the tonal and muted lists above the opposition list (§3); within each, prefer lower chroma and a narrower value gap |
| sharp, awake, noticed, precise | hard | Prefer wider value gaps (ΔL* ≥ 40) and the clearer end of the season |
| warm, cosy, soft | warm-soft | Weight toward the warm-leaning anchors |
| cool, clean, modern | cool-soft or cool-hard | Weight toward the cool-leaning anchors within the season |

Mood is a *ranking* input, never a filter. Nothing outside the season enters because of a mood word.

## 8. What the model does with this

- Names the combinations in the owner's register — "Petrol and Cinnamon", not "combination 7"
- Writes the one-line placement note ("rose near the face, olive as the body")
- Explains *why* a pair works, using the three properties, in a sentence a reader can repeat

## 9. What it never does

- Propose a pair the generator didn't produce
- Move a colour outside its palette to make a pair work
- Present a Wada combination as in-season when the filter said near
