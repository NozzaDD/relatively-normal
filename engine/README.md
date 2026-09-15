# engine/

The deterministic half of the wardrobe tool, as Python. No language model runs
here: everything is arithmetic on colours, and every verdict can be explained by
pointing at a number. This is the code behind `frameworks/colour-system.md`,
`combinations.md`, `matching.md` and `horizons.md` — the frameworks are the
specification; this folder is the implementation, and when they disagree the
frameworks win and the code is wrong.

## Running it

Python 3.11+. `engine/colour.py` is standard library only. Reading
`seasons.yaml` needs **PyYAML** (`pip install pyyaml`); that is the only
dependency.

From the repository root:

```sh
python -m unittest discover -s engine/tests -t . -v
```

(`pytest engine/tests` also works if pytest is installed — the tests are plain
`unittest` cases.)

Rendering the result screen for one person — items file in, HTML out:

```sh
python -m engine.run --season soft_autumn --direction teal_ochre --items engine/examples/nora-items.yaml --out result.html
```

`engine/examples/nora-items.yaml` holds the five Nora test-case items, so that
command runs with no other setup. Two optional flags carry the intake answers
the screen also shows — `--mood "calm, put together, not trying"` and
`--confidence temperature=medium,value=high,chroma=high` (the runner-up season
needs the confidences) — and `--json path` also writes the raw result. The
committed `engine/examples/nora-result.html` was produced with both optional
flags.

Using it from Python:

```python
from engine import palette, generators, matcher, horizons

season = palette.apply_direction(palette.get_season("soft_autumn"), "teal_ochre")

# the three generators over the season's anchors
out = generators.generate(season.anchors, mood="calm, put together", direction_anchor="deep teal")
out["order"]                      # ['tonal', 'muted', 'opposition'] — calm promoted the quiet lists
out["lists"]["opposition"][0]     # a Pair: dominant, counter, hue_gap, delta_L, delta_rel, bridge

# one item's verdict
matcher.score_item({"id": "t1", "hex": "000000", "slot": "bottom"}, season)
# -> verdict 'in', nearest 'black (below waist)', stage 1

# the whole result screen
items = [{"id": "t1", "hex": "1F5F63", "slot": "top"},
         {"id": "b1", "hex": "000000", "slot": "bottom"},
         {"id": "s1", "hex": "A6502F", "slot": "accessory", "near_face": True}]
horizons.result("soft_autumn", "teal_ochre", items,
                mood="calm", confidence={"temperature": "medium", "value": "high", "chroma": "high"})
```

## Modules

| Module | Implements | What it does |
|---|---|---|
| `colour.py` | `matching.md` §1 (colour space), `combinations.md` §2 | sRGB → CIELAB (D65), Lab ↔ LCh, ΔE2000, and `relative_chroma(L, C, h)` = C\* / C\*max where C\*max is the sRGB gamut boundary at that lightness and hue, found by bisection. Pure functions. |
| `palette.py` | `colour-system.md` §2 (runner-up), §4, §5 | Loads `seasons.yaml`; a `Season` carries its anchors as Lab with tier and relative chroma, its rules (`black`, `white`, `contrast`, `metal`, `avoid`) and its directions. `apply_direction` re-weights toward a direction. `runner_up` derives the second season from per-axis confidence. |
| `generators.py` | `combinations.md` §3, §5 | Opposition, Tonal and Muted exactly as specified, run over chromatic anchors only (neutrals, relative chroma ≤ 0.15, are excluded) — bands, chroma caps, Δ relative chroma limits, ΔL\* minimums, per-generator ranking, the default and calm orderings, direction re-weighting, and the optional bridge. |
| `matcher.py` | `matching.md` §1–§5 | `extract_colours` (k-means in Lab over pixels); `score_item` with the three-stage order — slot rules, avoid list, anchors — and the full black/white tables including `near_face`; `outfit_checks` (coverage, palette share, tier balance, contrast); `pair_valid` and `outfit_valid`, the four outfit pairing rules of `combinations.md` §5 (neutrals are the ground); `rank_gaps`; `fill_gap` with Source 1 (own closet) implemented and Sources 2 and 3 as stubs returning nothing; `score_outfit` producing the §6 JSON. |
| `horizons.py` | `horizons.md` §2–§4 | `result` — the §6 JSON extended with `long_term` (ideal palette, ranked combinations, rules in force, runner-up, direction-of-travel data) and `short_term` (current palette sorted into the ideal's tiers, the distance figure and its reading, over-represented and missing colours, works-now outfits, ranked next moves). |
| `render.py` | `horizons.md` §6 | `render(result)` — the result dict as one self-contained HTML page: colouring and runner-up at the top, ideal palette and current wardrobe as two columns of proportional colour blocks (the current one sorted into the ideal's tiers, out and hard-miss items set apart), the distance figure, the outfit in hand with its checks, works-now and next moves side by side, combinations as swatch pairs, and the long-term data. Inline CSS, no external assets. It computes nothing: every number and verdict is read from the JSON. |
| `run.py` | — | The command line: `python -m engine.run --season … --direction … --items items.yaml --out result.html`. Reads the items file (name, hex, slot, optional near_face and share), calls `horizons.result`, writes the page. |
| `tests/test_nora.py` | `examples/nora-soft-autumn.yaml` | Asserts every expected verdict, the runner-up season, the named pairs' generators, and the exact three ranked lists over Soft Autumn. |

## Item shape

```python
{"id": "…", "hex": "1F5F63", "slot": "top", "near_face": True, "share": 1.0}
```

- `slot`: `top` | `bottom` | `shoes` | `bag` | `accessory`
- `near_face`: read for the accessory slot only. Scarves and hats `True`; belts,
  jewellery and watches `False`. The vision model proposes it, the user
  confirms it. An accessory with no flag is scored as hardware and the result
  carries a flag saying so.
- `share`: weight in share-weighted figures (the palette distance); defaults to 1.

## Where the code had to decide something the frameworks leave open

Each of these is a starting interpretation, marked in the docstrings, and the
owner's to overrule:

- **Direction re-weighting** (`palette.apply_direction`): the direction's anchor
  gets weight 2.0, anchors within 40° of it in hue get 1.5, the rest 1.0; tiers
  are re-ordered by weight. Nothing is added or removed.
- **Bridge** (`generators._bridge`): the §3.6 definition — a neutral, or a
  chromatic anchor that forms a valid Tonal pair with the dominant or the
  counter, any tier, any lightness. "Largest lightness gap to the pair" is read
  as the bridge's distance to the nearer of the two anchors; ties go to the
  lower relative chroma.
- **Band boundaries**: a hue gap of exactly 40.0° is Tonal, exactly 100.0° is
  Muted.
- **Runner-up ties**: when two axes tie on lowest confidence, temperature wins;
  when the least-confident axis is the one the winner holds at centre, both
  poles are one-axis changes, so both are listed and the first in table order
  is returned.
- **Contrast flag thresholds** (`matcher.CONTRAST_MAX_RANGE`): the lightness
  spread each contrast level tolerates. `matching.md` specifies the flag, not
  the numbers; these are starting values to tune against the beta consultations.
- **Tier balance**: only in/near items with a tier are counted; `accent-heavy`
  fires above a 30% accent share, `foundation-light` below a 30% foundation
  share.
- **Palette distance** uses the ΔE each verdict reported, so black trousers
  allowed by a slot rule count at ΔE 0, not at their distance to chocolate.
- **Next moves with the stubs in place**: every fill is from the closet, so
  `price_band` is 1 and `palette_improvement` is measured on the outfit in hand.
- **Gap ranking** without saved outfits: every gap unlocks 1 and ties break by
  severity (empty slot, hard miss, out, near, tier, contrast).

## What is not here

- PNG decoding. `extract_colours` takes pixels; reading the file is the caller's
  job, so the module stays standard-library.
- Sources 2 and 3 (`fill_from_staples`, `fill_from_brands`). Stubs returning
  `None` until `staples/` has sampled hexes and the brand feeds exist.
- The photo analysis in `colour-system.md` §2. The engine takes a season and
  confidences as input; reading them from photographs is the vision model's job.
- Any sentence a person reads. The output is data; the model writes the words.
  The renderer quotes the four distance readings from `horizons.md` §3b and
  leaves the long-term paragraph to the owner.
