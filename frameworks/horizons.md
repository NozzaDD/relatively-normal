# Horizons — what the person actually sees

The pipeline in `colour-system.md`, `combinations.md` and `matching.md` produces data. This file specifies the *result screen*: the thing a user reads after uploading three photos of their face and their items. It runs on any face and any wardrobe.

**The result has two horizons, always shown together.** Long-term says where the wardrobe should go. Short-term says what to do about it now, given what's actually in the five slots. They are different answers to different questions, and showing only one is the mistake every colour-analysis service makes.

---

## 1. Inputs

| From | What |
|---|---|
| Photos (3) | → axes → season → **ideal palette** with direction (`colour-system.md`) |
| Questions (3) | → direction and mood ranking |
| Items (up to 17, by slot) | → each item's dominant colour in Lab (`matching.md` §1) → the **current palette** |

The ideal palette is derived from the person. The current palette is derived from the clothes. The product lives in the gap between them.

---

## 2. Long-term horizon — the ideal

**"This is where your wardrobe is going."**

- Season and direction, in plain language, with the top-two seasons and confidence per axis. Never one certain answer.
- The **ideal palette**, shown as proportional blocks: foundations 55%, supporting 30%, accents 15%, using the colour names not just swatches.
- The person's **combinations** (`combinations.md` §3), ranked by direction and mood: three to five named pairs with the placement note.
- The rules in force for this season: where black goes, where white goes, the contrast level to dress to.
- **Direction of travel, one paragraph.** Which tier should grow over the next year, which colours currently over-represented should be allowed to fade out, and the one investment piece that would anchor the destination wardrobe.

This is steering. It doesn't tell anyone to buy anything this month.

---

## 3. Short-term horizon — the realistic

**"This is what to do with what you have."**

### 3a. The current palette

Every uploaded item's dominant colour, laid out as proportional blocks in the same three-tier format as the ideal, **sorted into the ideal's tiers by nearest anchor.** A Bright Winter whose closet is all soft autumn tones will see immediately that their "foundations" block is full of colours that aren't foundations for them.

Per item: in / near / out / hard miss, with the nearest anchor named.

### 3b. The delta

One number and one sentence. The **palette distance**: the share-weighted mean ΔE from each item's colour to its nearest ideal anchor. An item's contribution is its ΔE to the nearest anchor that would be *in* for that item's slot after the slot rules — never to the colour that triggered a hard miss — so black trousers admitted below the waist contribute 0, a white shirt at the face contributes its ΔE to cream, and out items contribute their ΔE to the nearest palette anchor.

| Distance | Reading |
|---|---|
| ≤ 10 | *Your wardrobe already matches your colouring. The work is combinations, not colours.* |
| 10 – 18 | *Mostly there. One or two colours are pulling against you.* |
| 18 – 28 | *A real gap. Worth steering deliberately over the next year.* |
| > 28 | *Your wardrobe and your colouring disagree. Start with the pieces nearest your face.* |

Then: which items are **pulling against you** — the items whose verdict is not *in*, largest contribution to the distance first, each with its verdict and its nearest admitted anchor as the fix — and which colours are **missing**: foundation-tier anchors no item lands on. The missing list is judged only when the closet holds ten or more items; below that it reads *not enough items to judge — add more before reading this*.

### 3c. What works now

Before any suggestion to buy: the outfits that can be built *today* from the uploaded items using in-palette pieces and the outfit pairing rules in `combinations.md` §5. Ranked by how many items they use and how close the pair is to a named combination.

*"From what you own, these three work: …"*

If none work, say so. That is a finding, not a failure.

### 3d. The realistic next move

The one to three purchases that would do the most, ranked by a single score:

```
value = outfits_unlocked × palette_improvement ÷ price_band
```

- `outfits_unlocked` — how many of the person's existing items the new piece pairs with (the outfit pairing rules in `combinations.md` §5, against every item in the closet, not just the canvas)
- `palette_improvement` — how much the delta in 3b falls if this piece is added
- `price_band` — from the staples catalogue or brand database

A next move that fills a context gap ranks above one that fills a zone gap of the same unlock count: a corporate gap blocks a whole recurring week, a zone gap one event.

**Constraint: a realistic next move must pair with at least two items the person already owns.** A perfect-palette piece that goes with nothing in the closet is a long-term purchase, and it belongs in section 2, not here.

Each suggestion names its source (`matching.md` §5): *already own* → *staple* → *brand*. Staples fill most short-term gaps because they're cheap, reliable and available in the colourway the gap needs; investment pieces are the long-term horizon.

---

## 4. How the two horizons relate

| | Long-term | Short-term |
|---|---|---|
| Answers | Where should this go? | What do I do now? |
| Derived from | The person | The person *and* the clothes |
| Suggests | An investment piece, a direction | One to three pieces that pair with what's owned |
| Source | Manifesto brands, partnerships | Own closet first, then staples |
| Timeframe | 12–24 months | This month |
| Changes when | Rarely — the person doesn't change | Every upload, every outfit built |

**The two can disagree, and that's the point.** Someone whose ideal is deep teal and ochre but whose closet is navy and camel gets told both things: the destination, and the fact that a rust scarf and an olive knit would make eight of their existing pieces work together this month. Nobody is told to throw out a wardrobe.

---

## 5. The monthly re-run

Long-term horizon: unchanged unless the person re-runs their photos.

Short-term horizon: recomputed from the outfits actually built that month. The delta moves as items are added; the "what works now" list grows; the realistic next move updates. This is the content of the personalised recommendation email, and it only fires when outfits were built (`matching.md` §4).

---

## 6. Layout, in one screen

```
┌─────────────────────────────────────────────────────────────┐
│  YOUR COLOURING                                              │
│  Soft Autumn · teal & ochre     (runner-up: Soft Summer)     │
│                                                              │
│  IDEAL PALETTE            YOUR WARDROBE TODAY                │
│  ████████████ 55%         ████████ 40%   ← foundations       │
│  ██████ 30%               ██████████ 45% ← supporting        │
│  ███ 15%                  ███ 15%        ← accents           │
│                                                              │
│  Distance: 14 — mostly there. Navy is pulling against you.   │
│                                                              │
│  WORKS NOW                    NEXT MOVE                      │
│  · teal knit + black trouser  1. Olive crew (staple, €40)    │
│  · camel coat + cream shirt      pairs with 6 of your items  │
│  · olive trouser + rust scarf 2. Ochre scarf (staple, €25)   │
│                                  pairs with 4                │
│  YOUR COMBINATIONS            LONG-TERM                      │
│  Teal & Ochre · Petrol &      Let the teal tier grow; let    │
│  Cinnamon · Olive & Faded     navy fade. One piece: a deep   │
│  Rose                         teal coat (Herno, Aspesi).     │
└─────────────────────────────────────────────────────────────┘
```

The model writes the sentences. Every number, every verdict, every ranking on that screen came from the matcher.
