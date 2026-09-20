---
title: I found the combination this whole system is named after, in a corduroy jacket
date: 2026-10-04
format: weekly
campaign: 2026-10-04-petrol-and-ochre
brands: [massimo-alba, aspesi, lardini, closed]
affiliate: no
---

status: outline

> **Post B — the strongest post this material makes possible, and it isn't in the plan.**
>
> **Slot: Sunday 4 October.** That is the last weekly slot before
> `campaign-beta-round-1` opens on **6 October**, so the post lands two days
> before the consultations ask and funnels straight into it.
>
> **What it displaces:** formally, nothing — there is no `content/calendar.md`,
> so no slot is assigned to anything. Practically it displaces the first outing
> of `series-polly-pocket`, the other obvious candidate for a pre-campaign
> Sunday. It also competes with Post A for the 4 October date if Post A slips;
> see Post A's open questions.
>
> **Why it beats what is in the plan:** of nine outfits built from the library
> and run through the engine, this is the **only one that comes back valid** —
> and it happens to be the reference pair the entire colour direction is named
> after, buildable from two garments on one brand's website. The backlog's
> nearest equivalent, `post-reverse-engineered-outfits`, is gated on
> `building_in_public_3_published`, which has not happened.

---

## Three title options

1. **I found the combination this whole system is named after, in a corduroy jacket**
   — leads with the object. Longest, and the most likely to be read.
2. **Teal and ochre: the only outfit that passed**
   — leads with the verdict. Stronger for people who already know the series.
3. **Every piece was right. The outfit was wrong. Except once.**
   — leads with the failure and lands on the exception. The most argumentative
   and the best fit for `angle-attention`.

**Thesis (one sentence).** "Is this colour right for me" is the question
everyone sells the answer to, and it is the wrong question — the useful one is
whether two right colours are right *together*, which is a different test with a
different answer, and I can show you eight outfits where the first test passes
and the second one doesn't.

---

## Paragraph-level outline

**¶1 — The setup, in objects not theory.**
Image: `products/IMG_0263.png`. Two garments on one page — a petrol corduroy
jacket and a petrol corduroy trouser — and, three pages away, an ochre bandana.
Start there. Do not mention the framework yet.

**¶2 — What I did.**
Short and plain: I saved 878 product screenshots over some months, pulled the
colours out of them, and ran every combination I liked through the same test.
This is the `series-building-in-public` beat and it earns the rest.

**¶3 — The nine outfits, and the eight that failed.**
Image: `products/IMG_0198.png` (the oxblood trench). Uses **worked example B1**
in full. The point: four garments, every one *in palette*, verdict **not valid**.
This is the paragraph that reframes the whole category. In-palette and
goes-together are two different questions and colour analysis only ever answers
the first.

**¶4 — The one that passed.**
Images: `products/IMG_0263.png` then `products/IMG_0250.png`. Uses **worked
example B2** in full, with the engine's own output quoted. The point: petrol
against ochre, hue gap 172.7°, Δ relative chroma 0.03, ΔL\* 21.5 — opposition,
`Petrol and Ochre`. Named pair, valid outfit, real garments.

**¶5 — And even it has a flag.**
Same images. The engine marks the bandana **not corporate** — ochre is
accent-only in a formal workplace under Soft Autumn's own list — and marks the
outfit **foundation-light**. Publish the flags. A system that only ever agrees
with you isn't measuring anything.

**¶6 — A room, and the same test, and a different answer.**
Images: `visuals/IMG_0147.jpeg` then `products/IMG_0271.png`. Uses **worked
example C1** in full. The point: an interior that obviously works and fails
every generator (ΔL\* 2.8 where 15 is required), rebuilt in clothes where it
passes as `Dark Olive and Dusty Rose`. The rule is a tool, not a judge.

**¶7 — The thing I couldn't build.**
Images: `visuals/IMG_0066.png` then `products/IMG_0246.png`. Uses **worked
example C3** in full. The point: a picture that passes the Tonal test cleanly
(ΔL\* 42.3) collapses when rebuilt from real garments (ΔL\* 0.6), because every
warm neutral I own or have saved sits in the same narrow band of lightness. Name
the missing piece precisely: a camel or straw bottom around L\* 70.

**¶8 — Why this is a relief.**
No new image, or reuse `fashion shows ss27/IMG_0860.png` small. The
`angle-attention` close: a filter that says no is a filter that gives you back
attention. "I love it, but it's not for me" is a sentence that costs nothing and
returns something. The point is not fewer beautiful things — it's being able to
enjoy one without having to decide about it.

**¶9 — The ask.**
Four consultations, October work wardrobes, comment to enter. Two days before
`campaign-beta-round-1` opens on 6 October. This is the paragraph the whole post
is a ramp for, and it works precisely because ¶3 admitted failure first.

---

## The worked examples, in full

Every verdict below is the engine's, produced by importing `engine.palette`,
`engine.generators` and `engine.matcher`, loading `soft_autumn` with the
`teal_ochre` direction applied (26 generated pairs), and scoring these inputs.
Nothing in `engine/` or `frameworks/` was changed.

### B1 · Four right pieces, one wrong outfit

`products/IMG_0198.png` (Aspesi oxblood trench) + `products/IMG_0212.png`
(stone knit) + `products/IMG_0252.png` (Massimo Alba taupe corduroy) +
`products/IMG_0283.png` (brown shoe).
Occasion: office, corporate, 9 °C, rain. Casual→dressy: **dressy**.
Light→heavy: **heavy**.

| Slot | Hex | Verdict | Nearest anchor | ΔE |
|---|---|---|---|---|
| layer | `4A2730` | in | soft plum | 7.9 |
| top | `C6BBA9` | in (neutral) | stone | 5.4 |
| bottom | `8C7351` | in | warm mid grey | 11.0 |
| shoes | `3A2A20` | in | chocolate | 4.9 |

**OUTFIT VALID: False** — flags `['no generated pair' ×3, 'too many colours']`.
Weather check passes (layer present, heaviest weight 3). Context check passes
(corporate, office, no flags).

Every item is in palette. The outfit still fails, because three warm chromatics
that each sit near a *neutral* anchor form no generated pair with one another.
This is the cleanest demonstration in the library that the two questions are
different.

### B2 · The one that passed

`products/IMG_0263.png` (AGRA cotton corduroy jacket, LAMNA cotton corduroy
trousers) + `products/IMG_0250.png` (BANDANA, cashmere and silk, colour "Nugget
Gold") + `products/IMG_0212.png` (stone knit).
Occasion: office, corporate, 12 °C, clear. Casual→dressy: **mid-dressy**.
Light→heavy: **mid-heavy**.

| Slot | Hex | Verdict | Nearest anchor | ΔE |
|---|---|---|---|---|
| layer | `3F6166` | in | **petrol** | 4.3 |
| bottom | `2F5459` | in | **petrol** | 3.7 |
| accessory (`near_face: true`) | `C08A2E` | in | **ochre** | 2.6 |
| top | `C6BBA9` | in (neutral) | stone | 5.4 |

**OUTFIT VALID: True** — flags `[]`.

Pairs: jacket + trouser **monochrome**; jacket + bandana **opposition,
`Petrol and Ochre`**; trouser + bandana **opposition, `Petrol and Ochre`**;
everything else chromatic + neutral on the ground.

Two non-fatal flags: tier mix **foundation-light** (0.29 foundation / 0.71
supporting), and the context check marks the bandana **not corporate** — ochre
is accent-only in a formal workplace per Soft Autumn's `corporate` list in
`seasons.yaml`.

The accessory is not decoration here. Under `matching.md` §2 a scarf carries
`near_face: true`, which makes it the face colour and re-scores the layer
underneath it as away-from-the-face. One small piece changes which rule the
biggest piece is judged by.

### C1 · A room that fails the rule and works anyway

`visuals/IMG_0147.jpeg`, right-hand panel: mint-sage painted shelves, a
dusty-rose window seat, terracotta blinds.

Sage `8FA58C` against dusty rose `C99BA0`: hue gap **127.7°** (opposition band),
Δ relative chroma **0.16** (inside the 0.20 limit), **ΔL\* 2.8** against a
required **15**. Engine: `NO GENERATOR`.

It works anyway, for the same reason `combinations.md` §4 keeps *Plum and Old
Gold* in the worked examples while admitting it passes nothing: a pair can hold
for a reason the mechanism doesn't encode. Here the reason is that the two
colours are separated in **space** — a wall of shelving and a seat — not in
value.

Rebuilt from `products/`: raspberry knit `C397A0` (`IMG_0271.png`, VIRGINIA,
virgin wool and alpaca) + dark olive skirt `3F4430` (`IMG_0223.png`) + camel
corduroy jacket `A87C4A` (`IMG_0223.png`). Engine: **OUTFIT VALID: False** —
but knit + skirt passes as **Muted, `Dark Olive and Dusty Rose`**, the named
pair from `combinations.md` §4, and skirt + jacket passes as **Muted,
`Dark Olive and Camel`**. Only knit + jacket fails.

So the wearable version of that room needs the olive and does **not** need the
camel. **Missing piece: a cream or stone mid-weight layer.** Nothing in 878
images is one.

### C3 · The picture that passed and the wardrobe that didn't

`visuals/IMG_0066.png` — a tan dress in tall ornamental grasses. Palette
`80703F` (33%) `4B441D` (28%) `DDA264` (20%) `141509` (13%) `A8A599` (5%).
*The dress reads as suede; no fibre is stated anywhere in the image, so under
CLAUDE.md hard rule 6 it stays unknown.*

Dress `DDA264` against grass `4B441D`: hue gap **27.1°** (Tonal band), Δ
relative chroma **0.12**, **ΔL\* 42.3**. Engine: **tonal** — passes. One hue
family, matched saturation, a wide value step. That is why a tan dress in green
grass doesn't read as camouflage.

Rebuilt: camel corduroy skirt `7E5C44` (`IMG_0246.png`, RENE) + olive merino
`62652D` (`IMG_0204.png`, VERDE) + brown Mary-Jane `2B221E` (`IMG_0246.png`).
Engine: **OUTFIT VALID: False**, all three pairs `no generated pair`, plus
`too many colours`.

The reason is exact: skirt L\* **42.0**, merino L\* **41.4** — a value gap of
**0.6** where the image had **42.3**. The garments reproduce the hues and lose
the thing that made the picture work. **Missing piece: a camel or straw bottom
around L\* 70.** The library's warm neutrals are all bunched between L\* 40 and
L\* 60.

---

## Product slots, with brand status

| ¶ | Piece | File | Brand | Status in `brands/` |
|---|---|---|---|---|
| 1, 4 | AGRA cotton corduroy jacket | `products/IMG_0263.png` | Massimo Alba | **in `brands/massimo-alba.yaml`** · `rubric_score` **blank** · `ownership: unknown` (file says founder-led in practice, legal form unconfirmed) · `affiliate_available: unknown` · `partnership_tier: first` |
| 1, 4 | LAMNA cotton corduroy trousers | `products/IMG_0263.png` | Massimo Alba | as above |
| 2, 4 | BANDANA, cashmere and silk, colour "Nugget Gold" | `products/IMG_0250.png` | Massimo Alba | as above |
| 6 | VIRGINIA virgin wool and alpaca sweater, colour "Raspberry" | `products/IMG_0271.png` | Massimo Alba | as above |
| 3 | TRENCH DOPPIO PETTO IN GABARDINE DI LANA VERGINE, colour "BARBERA" | `products/IMG_0198.png` | Aspesi | **in `brands/aspesi.yaml`** · `rubric_score` **blank** · `ownership: unknown` — file warns "the founder-era independence may no longer hold; check before describing it as independent or family-run" |
| 3, 4 | stone knit (styled, no product page) | `products/IMG_0212.png` | Aspesi | as above. **No product name legible for the knit** — "unknown, Nora to confirm" |
| 6, 7 | camel corduroy jacket, dark olive skirt | `products/IMG_0223.png` | Aspesi | as above |
| 7 | VERDE merino boat-neck | `products/IMG_0204.png` | Aspesi | as above |
| 7 | RENE cotton corduroy skirt | `products/IMG_0246.png` | Massimo Alba | as above |
| 3 | brown shoe (styled, no product page) | `products/IMG_0283.png` | Lardini | **in `brands/lardini.yaml`** · `rubric_score` **blank**. The shoe itself has **no product page in the library** — it appears only as styling |
| 8 (optional) | runway look | `fashion shows ss27/IMG_0860.png` | truncated tab `Tory Bur…` | **NOT IN `brands/`, not identifiable.** Inspiration only — do not name, link or recommend |

**Flags.**
- **Every brand named here is in `brands/`** — `massimo-alba`, `aspesi`,
  `lardini`, `closed` — and **not one of them can be said to pass**, because
  all fifteen `rubric_score` fields are blank and `material-rubric.md` has no
  passing threshold. Under CLAUDE.md hard rule 3 that means no quality claim in
  this post is currently supportable. **This is the blocking issue for the post.**
- `brands/closed.yaml` is in the front matter only if ¶2 or ¶8 mentions the
  AI-imagery finding. If it doesn't, drop `closed` from the list. The file
  already says "NOT SCORED for environmental claims. The brand makes them; none
  is recorded here until a rubric field supports it" — worth reading before
  writing anything about it.
- **No composition percentages exist.** Fibres are named in product *titles*
  ("cotton corduroy", "cashmere and silk", "virgin wool and alpaca") and in
  Aspesi's Italian details text ("pura lana vergine", "velluto di cotone tinto
  in capo"). Every Composition panel in every screenshot is collapsed. Do not
  write a percentage.
- `affiliate: no`. Every `affiliate_available` field in `brands/` is `unknown`.
- **Price is legible on most of these pages and is deliberately absent above**,
  per the editorial rule you gave me. Note that this rule is **not written down
  in the repository**, and `horizons.md` §3d actively divides by `price_band` —
  see §7.4 of `content/review-2026-09-20.md`.

---

## Which of the 25 notes lead into this post, and which follow

**Lead in (run before 4 Oct):**
- **N01** — the pair the system is named after, found in a corduroy jacket (Mon 21, #1). ¶1 in miniature; the earliest and most important trailer.
- **N02** — one ochre square is the whole outfit (Mon 21, #2). Sets up the `near_face` idea ¶4 depends on.
- **N03** — every piece was right, the outfit was wrong (Tue 22, #1). ¶3 in miniature. If only one note runs, this one.
- **N06** — this room is an outfit (Wed 23, #2). ¶6 in miniature.
- **N08** — the same outfit, 42 points of lightness apart (Thu 24, #2). ¶7 in miniature.
- **N12** — three colours I love, together nothing (Sun 27, #1). Reinforces ¶3 from the reader's side.
- **N15** — the composition panel is always closed (Mon 28, #2). Prepares the reader for why no percentages appear.

**Follow (run after 4 Oct, into the campaign):**
- **N22** — what have you had five years? (Fri 2 Oct, #2). Comment warm-up two days out.
- **N25** — beautiful, and not for me (Sun 4 Oct, #2). Runs the same evening; ¶8 as a standalone.
- **N14** — this product photo is not a photograph (Mon 28, #1). The building-in-public thread that makes ¶2 credible.
- **N05** — a palette is a filter, and the relief is the point (Wed 23, #1). The `angle-attention` case ¶8 closes on.

---

## What I need from you

1. **The rubric threshold — this is blocking.** `material-rubric.md` has four
   blanks: pass mark out of 15, per-field minimums, automatic failures, and
   separate thresholds for staples and investment pieces. Until they are filled,
   nothing in this post can say a brand is well made, and the post is partly
   about material. Fill those four lines and I can score Massimo Alba, Aspesi
   and Lardini against actual evidence.
2. **Have you worn teal and ochre together, or is this the first time?** ¶1 and
   ¶9 read completely differently depending on the answer, and I cannot invent
   it.
3. **Do you own the missing camel?** ¶7 names a gap at roughly L\* 70. Whether
   that gap is real in *your* wardrobe or only in the library changes ¶7 from
   an observation into a confession, which is stronger.
4. **The consultations ask in ¶9 — four people or five?** `campaign-beta-round-1`
   says five, capped publicly, seventeen items, intake via a form off the
   comments. `post-reverse-engineered-outfits` says four, October work
   wardrobes. Those are two different asks and the post can only make one.
5. **Your voice.** `voice/` has a README and nothing else. Nothing here has been
   checked against how you write, because there is nothing to check it against.
6. **One thing that actually happened.** ¶2 says "I saved 878 screenshots over
   some months". I know the number; I don't know why you started, and that
   sentence is the post's only claim on the reader's attention in the first
   thirty seconds.

---

## Open questions

- **Does ¶3 have to come before ¶4?** I think yes — admitting eight failures
  before the one success is what makes ¶9's ask land as a next step rather than
  a pitch, which is the exact structure `post-reverse-engineered-outfits`
  describes ("the outfits come first and the method second; that order is the
  whole persuasion"). But it means the post opens on failure.
- **Is this actually `post-reverse-engineered-outfits`, early?** The backlog
  entry is gated on `building_in_public_3_published`, which has not fired. This
  post does the same job with real evidence and no gate. If you agree, the
  backlog entry should be marked superseded rather than left waiting — but that
  is an edit to `backlog.yaml` and I have not made it.
- **Does it collide with Post A?** Both want a Sunday, and the fashion-week
  window closes 6 Oct. If Post A moves to 4 Oct, this moves to 11 Oct and loses
  its two-day run-up to the campaign.
- **§7.1 of the review.** The stone knit used in B1 and B2 is a *neutral* at
  relative chroma 0.13 and a *chromatic* at 0.19, depending on which screenshot
  it was sampled from — and that flips B5 from valid to failed. If you agree
  that is a framework problem, ¶5 could say so out loud and the post becomes a
  much better `series-building-in-public` piece. If you don't, leave it in the
  review and out of the post.
- **`format: weekly`** — same question as Post A. `content/posts/README.md`
  requires the field and never lists permitted values.
