# Intake — what the app asks before it analyses

Two parts: the photo requirements the app must enforce before analysis runs
(`colour-system.md` §2), and the three questions that pick a direction within the
season (`colour-system.md` §5).

Both are user-facing. The wording below is a specification of what must be asked
and checked, not final interface copy.

---

## Part 1 — Photo checklist

Analysis does not run until all of these are satisfied. The first three are a
count; the rest are conditions the user confirms and, where possible, the app
checks.

### The three photos

- [ ] **Face, straight on**
- [ ] **Face, in profile**
- [ ] **One photo including hair and shoulders**

Three is the minimum. The analysis is a judgement across all three photos, never
one — so a missing angle is a blocker, not a warning.

### Lighting

- [ ] **Natural daylight, indirect**
- [ ] No overhead artificial light
- [ ] Not golden hour
- [ ] No filter
- [ ] No beauty mode

Lighting alone can move the temperature reading a full step. This is the section
worth being strict about.

### Face

- [ ] No foundation or coloured makeup (ideal)
- [ ] Lipstick removed

Stated as ideal rather than required — but the confidence score should fall when
the user says makeup is present.

### Background

- [ ] Neutral background where possible
- [ ] A white wall is best — it reveals white balance

Where the photos disagree with each other, the one with the most neutral
background is weighted highest. The app should record which photo that is.

### What the user should be told

- Three photos, all three angles, or the analysis does not run.
- The result is only as good as the light. A confident wrong answer is worse than
  a hedged right one, so the app returns the **top two seasons** and a confidence
  per axis rather than one certain answer.

---

## Part 2 — The three questions

A season is a region, not a point. Two people in the same season can look
completely different. These three questions pick the direction within it.

### Question 1 — What do you wear most?

**Format:** single choice, four options.

- denim
- tailoring
- knitwear
- dresses

**What it sets:** the foundation texture, and it shifts the foundations tier
toward the neutrals that suit that garment type.

- denim → the blue-adjacent neutrals in the season
- tailoring → the greys and browns

### Question 2 — What do you want to feel like in your clothes?

**Format:** free text.

**What it sets:** mapped to a direction keyword, which becomes a ranking input for
combinations — never a filter. Nothing outside the season enters because of a mood
word.

| Words in the answer | Direction |
|---|---|
| calm, grounded, quiet | the muted end of the season |
| sharp, awake, noticed | the clearer end of the season |
| warm, soft, easy | the warm-neutral end of the season |

### Question 3 — What do you reach for to look like yourself?

**Format:** free text.

**What it sets:** the strongest signal of the three. If the answer names a colour,
that colour's family becomes the anchor of the supporting tier — **provided it is
inside the season.**

If the named colour is outside the season, say so honestly and show the nearest
in-season alternative. Never silently swap it.

---

## Output of intake

- Three photos, meeting the checklist, with a record of which has the most neutral
  background
- One answer per question, in the formats above
- The selected **direction** — each season in `seasons.yaml` carries two or three
  named directions, and the questions select one

The palette is then the season's base tiers re-weighted toward the chosen
direction.

---

## Open questions for the owner

- Question 1 specifies a foundation shift for **denim** and **tailoring** only.
  **knitwear** and **dresses** are offered as answers but no shift is defined for
  them — and `examples/nora-soft-autumn.yaml` answers `knitwear`. Left as-is,
  since the fix is a decision about the method, not a gap in this file.
- The photo checklist has no defined behaviour for a user who confirms makeup is
  present: whether that blocks analysis or only lowers confidence is unspecified
  in `colour-system.md` §2.
