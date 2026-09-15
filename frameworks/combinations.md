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
6. Optionally add a **bridge**: a third anchor that adds no third voice — either a neutral (relative chroma ≤ 0.15, §5), or a chromatic anchor that forms a valid Tonal pair with the dominant or the counter. Its lightness need not sit between the two; a bridge may be the lightest or the darkest of the three. Where several qualify, take the one with the largest lightness gap to the pair (its distance to the nearer of the two). Three-colour combinations use dominant / counter / bridge at roughly 50 / 30 / 20.
7. Rank within each generator: opposition by hue separation (closer to 180° ranks higher) then value contrast; tonal by hue separation (closer to 0° ranks higher) then value contrast; muted by value contrast then hue separation, since in that band the value gap is what carries the pair.

**Ranking the three lists.** Default order is Opposition, then Tonal, then Muted. A mood answer of *calm, quiet* or *grounded* (intake question 2) promotes Tonal and Muted above Opposition, keeping Tonal ahead of Muted. Mood is a ranking input, never a filter — all three lists are always produced.

Soft seasons will produce muted pairs; bright seasons will produce clear ones. The rule is the same; the palette does the work.

**Direction re-weighting.** When the intake questions have chosen a direction (see `colour-system.md` §5), rank combinations containing that direction's anchor first within each of the three lists. The owner's `teal_ochre` direction puts every teal-containing pair at the top.

## 4. Worked example — Soft Autumn

These four are the combinations that came out of the original analysis. Every number below is computed from the hex values in `seasons.yaml` (sRGB → CIELAB, D65); nothing is estimated.

| Name | Dominant | Counter | Bridge | Hue gap | Δ rel. chroma | ΔL* | Generator |
|---|---|---|---|---|---|---|---|
| **Teal and Ochre** | deep teal `1F5F63` | ochre `C7912B` | stone `D6CEC2` | 125.0° | 0.00 (0.85 / 0.85) | 27.1 | **Opposition** — passes all three |
| **Petrol and Cinnamon** | petrol `2C5A66` | cinnamon `B5693C` | stone `D6CEC2` | 169.3° | 0.10 (0.72 / 0.62) | 16.5 | **Opposition** — passes all three |
| **Olive and Faded Rose** | dark olive `4E5A3A` | dusty rose `C09A93` | cream `EFE6D3` | 88.2° | 0.13 (0.40 / 0.27) | 30.4 | **Muted** — passes all four |
| **Plum and Old Gold** | soft plum `5C3A4E` | old gold `B8963E` | stone `D6CEC2` | 104.5° | 0.40 (0.33 / 0.73) | 34.6 | **None** — a deliberate chroma step |

Bridges were re-checked against §3.6 on 2026-09-15, and again the same day after warm charcoal `3A3632` (L\* 22.9, relative chroma 0.098) and stone `D6CEC2` (L\* 83.1, 0.095) joined warm mid grey (L\* 55.2, 0.115) as Soft Autumn's neutrals. Where several anchors qualify, the one with the largest lightness gap to the pair wins, which is why stone — the lightest of the three — now bridges three of the four. The three chromatic bridges from the original analysis all fail the Tonal test with both of their pair's anchors and were replaced: camel against cinnamon is hue 25.8°, Δrel 0.20, but ΔL\* only 13.1 (needs 25); warm taupe is 43.8° from dark olive and 44.4° from dusty rose (needs ≤ 40°); chocolate against old gold is 22.4° but Δrel 0.37 (needs ≤ 0.20). Replacements are the qualifying anchor with the largest lightness gap to the pair.

**Teal and Ochre** is the reference pair. Keep the teal deep and green-leaning, never cool-bright. Bridge: stone, a neutral, L\* 83.1 — gap 19.3 to the pair (above ochre); warm charcoal (13.8) and warm mid grey (8.7) also qualify.

**Petrol and Cinnamon** — warmer counter than ochre; reads richer, good for outerwear. The narrowest value gap of the four, and the reason the opposition minimum is 15 rather than 25. Bridge: stone, L\* 83.1 — gap 31.0 to the pair, the widest of the four; warm charcoal (12.7) and warm mid grey (3.0) also qualify. Camel, the original bridge, fails on lightness (ΔL\* 13.1 to cinnamon).

**Olive and Faded Rose** — the quietest pair. Rose near the face, olive as the body. Bridge: cream, which forms a Tonal pair with dark olive (32.3°, Δrel 0.12, ΔL\* 55.1) and sits lightest of the three at L\* 91.5, gap 24.7 to the pair; stone, warm charcoal, warm mid grey, chocolate and sage also qualify with smaller gaps (16.2, 13.5, 11.7, 11.7, 0.2). A Muted pair: at 88.2° the hues are neither opposed nor analogous, so in this middle band neither opposition nor analogy is doing the work — the pair only holds because both colours are quiet (0.40 and 0.27, under the 0.45 cap) and the value gap of 30.4 carries it.

**Plum and Old Gold** — the most evening of the four; gold in small pieces only. This one is not a matched-chroma pair and was never meant to be: a low-saturation plum (0.33) against a near-saturated gold (0.73) is a **deliberate chroma step**, the gold doing the work an accent does. Its hue gap puts it in the opposition band, but a Δ relative chroma of 0.40 fails every generator's chroma test. It sits outside all three, and it is kept here as the example of what the generators do not produce — a pair that works for a reason the mechanism does not encode. Bridge: stone, L\* 83.1 — gap 19.5 to the pair (above old gold); warm mid grey (8.5) and warm charcoal (6.1) also qualify. Chocolate, the original bridge, fails on chroma against old gold and on lightness against soft plum (ΔL\* 4.3).

## 5. Neutrals are the ground

A **neutral** is any anchor or item with **relative chroma ≤ 0.15**. Neutrals do not enter the three generators; the generators run over chromatic anchors only. A generated pair is two colours; the neutrals are what the pair sits on.

These are the pairing rules for an outfit. They run after the slot rules for black and white in `matching.md` §2 have already been applied, so every item arrives with its verdict.

| Pair | Valid when |
|---|---|
| **Chromatic + chromatic, monochrome** | The two are within ΔE 12 of *each other* and both are in palette — valid regardless of the generators. One colour in two garments is a tonal outfit, not a failed pair |
| **Chromatic + chromatic** | The pair matches a generated pair: each item is within ΔE 12 of one of that pair's two anchors |
| **Chromatic + neutral** | Both are in palette |
| **Neutral + neutral** | ΔL* ≥ 15; otherwise flag as **flat** |
| **Three or more chromatic items** | Every chromatic pair must be valid; otherwise flag as **too many colours** |

The monochrome test runs first, so a pair that passes it is reported with kind **monochrome** and never reaches the generator test. An outfit is valid when every pair in it is valid. This is what "works now" (`horizons.md` §3c) and the closet search (`matching.md` §5, source 1) are built from.

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
