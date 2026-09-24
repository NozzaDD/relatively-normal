# The neutral threshold — report, 24 Sept 2026

A report, not a change. Nothing in `engine/` was altered.

## What the threshold is

A colour is a **neutral** when its **relative chroma ≤ 0.15** (combinations.md
§5; `NEUTRAL_REL` in `engine/generators.py`). Relative chroma is C\* divided by
the largest chroma sRGB can show at that lightness and hue. Neutrals stay out
of the three generators and are the ground a pair sits on, which makes them
the only colours that can be a neutral bridge. The same flag decides the
neutral + neutral rule (ΔL\* ≥ 15) in the matcher, and `colour1_neutral` in the
catalogue.

## Why off-whites fail it

Near white the gamut is tiny, so a very small C\* is a large fraction of it:

| Colour | L\* | C\* | C\*max at that L, h | relative chroma |
|---|---|---|---|---|
| cream `EFE6D3` | 91.5 | 10.3 | 36.8 | **0.281** |
| Cloud Dancer `F0EBE0` | 93.2 | 5.9 | 29.9 | **0.198** |
| warm ivory `F5EBD8` | 93.4 | 10.4 | 24.1 | 0.432 |
| warm white `FBF7EF` | 97.3 | 4.3 | 9.3 | 0.463 |
| stone `D6CEC2` (neutral) | 83.1 | 7.0 | 73.6 | 0.095 |

## What moving it would change

Counted over all twelve seasons in `seasons.yaml`. "Pairs lost" are generated
pairs that disappear because one of their colours becomes a neutral. There are
125 generated pairs today.

| Option | Anchors that become neutral | Pairs lost | Products whose dominant colour becomes neutral (of 2007) | Engine tests that fail (of 98) |
|---|---|---|---|---|
| rel ≤ 0.20 (takes Cloud Dancer, not cream) | 5: sage (Light Summer, Soft Autumn), cocoa rose, mauve (True Summer), soft plum (Soft Summer) | 3 | 187 | 6 |
| rel ≤ 0.30 (takes cream) | 18, including Soft Autumn cream, dusty rose, sage, warm taupe | 24 (Soft Autumn loses 12 of 26) | 445 | 8 — **Olive and Faded Rose** (combinations.md §4) stops being a pair, because dusty rose turns neutral |
| rel ≤ 0.46 (takes every off-white) | 42, including Soft Autumn dark olive, chocolate, camel, soft plum | 47 (Soft Autumn loses 16 of 26; Light Summer 9 of 10) | 735 | not run — plainly breaks the palettes |
| **off-white rule**: rel ≤ 0.15, or L\* ≥ 88 and C\* ≤ 12 | 8: cream in five seasons, warm ivory, and warm white in Bright Spring and Deep Autumn | 19 (Deep Autumn 8 of 16, Soft Autumn 5 of 26) | 51 | 3 (the committed ranked lists and the committed result page, which would have to be regenerated) |

A straight threshold move can't take cream without also taking dusty rose,
sage and warm taupe. Those are real colours in the owner's own palette, and
one of them breaks a worked example. Only a rule that looks at lightness as
well as relative chroma catches the off-whites alone.

The pairs the off-white rule loses are all pairs *with* cream or warm white:
chocolate + cream, cream + soft plum, aubergine + warm white and so on. They
would come back as chocolate *on* cream — a colour on neutral ground, valid
under §5 — rather than as a generated pair. Cream would still bridge Olive and
Faded Rose as a neutral instead of as a Tonal partner. It is the lightest
candidate, so it still wins.

## What deciding it needs

The owner's call, then a session in `engine/` alone (CLAUDE.md: engine and
content don't share a session). That session would:

- change `generators.is_neutral` to take L\* and C\* as well as relative chroma;
- regenerate the committed Nora outputs the three failing tests compare against;
- update combinations.md §5, and §4's note that cream bridges as a Tonal pair.
