# Scope — what the trial is, and what it is not

Written for whoever picks this repository up next, including a future session.
**The trial is the first slice of the full product, not a smaller product.** The
whole path already exists in `engine/` and is tested. Nothing has been removed
to make the trial; parts of it are simply unused at first. Do not rebuild them.

## What the trial asks

One occasion — work. One month — October. Sixteen items plus two coats, and
four outfits. That is the whole ask. `templates/trial/` holds the two
spreadsheets and the instructions; `engine/examples/trial-nora/` is a worked
example.

```sh
python -m engine.run --season … --direction … --items items.csv --outfits outfits.csv \
    --trial --occasion work --month October --out result.html
```

`--trial` changes exactly three things:

1. **The missing-from-the-closet list is suppressed.** Sixteen items chosen for
   one occasion cannot say what a whole wardrobe lacks, and a list that implied
   otherwise would be the most misleading thing on the page.
2. **The page is titled for the occasion and the month**, not for the wardrobe.
3. **The long-term horizon is replaced** by what this slice actually showed —
   and, as plainly, what it could not.

Everything else is identical: the three-stage verdicts, the slot rules, the four
pairing rules, the three generators, the gap ranking, the colour-share bars, the
next moves. A trial result and a full result are the same computation.

## What it deliberately leaves out

| Left out | Why | Where it already lives |
|---|---|---|
| **Other occasions** — weekends, travel, events, holiday | One occasion is enough to test whether the colour work is right. Four outfits from one occasion give cleaner evidence than twenty from six. | Nothing to build: `occasion`, `dress_code`, `formality` and `setting` are per-outfit already |
| **The twelve-season intake at scale** | The season is given, not derived: reading axes from photographs is the least reliable step and would confound the trial. A wrong season makes every downstream verdict wrong for a reason that has nothing to do with the engine. | `frameworks/colour-system.md` §2 specifies it; `frameworks/intake.md` is the questionnaire; `engine/palette.py` derives the runner-up from confidences |
| **Staples matching** (source 2) | `staples/` has no sampled hex values yet, so a colourway match would be invented rather than measured. | `matcher.fill_from_staples` is a stub with the matching rule written in `matching.md` §5; `staples/` holds the candidates |
| **The brand database, live** (source 3) | Needs affiliate feeds. Phase B. | `matcher.fill_from_brands` is a stub; `brands/` holds fifteen scored-ready files |
| **Body shape** | The colour system does not assess fit or proportion, and says so. Colour first, shape second. | `colour-system.md` §8; the product commitment is in `content/backlog.yaml` under `angle-stylist-in-your-pocket` |

## What is in the engine and unused in a trial

These are built, tested and correct. A trial just doesn't exercise them:

- The **long-term horizon** (`horizons.md` §2) and the **three directions side
  by side** (§2b) — a trial replaces the first and does not show the second.
- The **missing-from-the-closet** list (§3b) and its ten-item floor.
- **Seasons other than the one given** — all twelve palettes, their corporate
  lists and their neutrals are in `seasons.yaml`.
- **The dress and base slots**, **denim by fibre**, **texture**, **material
  preferences** — all live, all tested; a work trial may simply not contain a
  dress or a base.

## The rule this file exists to enforce

If a future session is asked for something on that list, the answer is almost
always **it is already here** — wire it up or turn it on. Removing capability to
narrow the trial would be the wrong move: the narrowing is in what we ask for,
not in what the engine can do.
