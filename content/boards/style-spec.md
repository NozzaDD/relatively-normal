# style-spec.md — what the formats in `swipe/formats/` actually do

Derived on 21 September 2026 from **120 screenshots** of other writers' Substack
posts, Notes, feeds and a few brand pages — every row in `content/swipe/index.csv`
with `type = format`, opened at ~1000px wide so the body text was readable, plus
the four format-shaped rows that live in `swipe/products/`.

**This file records structure only.** No sentence, headline, title or image from
any of those screenshots is reproduced here or anywhere else in this repository.
Where a pattern is named, the screenshot that shows it is cited so the claim can
be checked.

---

## Part A — anatomy

### A1. The Note

This is the overwhelming majority of the evidence: roughly **75 of the 120**
screenshots are single Notes, and they converge hard.

**The dominant shape — one line, then a three-up image row, then nothing.**

```
[one line of text]
[image] [image] [image]
(reaction bar)
```

Seen in `IMG_0021`, `IMG_0022`, `IMG_0023`, `IMG_0026`, `IMG_0030`, `IMG_0065`,
`IMG_0068`, `IMG_0070`, `IMG_0072`, `IMG_0073`, `IMG_0074`, `IMG_0082`,
`IMG_0087`, `IMG_0089`, `IMG_0094`, `IMG_0095`, `IMG_0102`, `IMG_0106`,
`IMG_0107`, `IMG_0108`, `IMG_0119`, `IMG_0144`, `IMG_0158`, `IMG_0232`,
`IMG_0233`, `IMG_0491`, `IMG_0493`, `IMG_0494`. A two-image variant runs in
`IMG_0017`, `IMG_0024`, `IMG_0029`, `IMG_0104`; a single large image in
`IMG_0078`, `IMG_0105`, `IMG_0120`, `IMG_0159`, `IMG_0495`.

**First line.** One line. Not a headline — a caption. Four recurring registers:

| Register | Shape | Seen in |
|---|---|---|
| **Label** | A bare noun phrase, often lowercase, sometimes just two words and a colon | `IMG_0074`, `IMG_0078`, `IMG_0088`, `IMG_0107`, `IMG_0108` |
| **Verdict** | A flat first-person judgement, no hedging | `IMG_0070`, `IMG_0072`, `IMG_0073`, `IMG_0087`, `IMG_0492` |
| **Confession** | A small admission, often self-deprecating | `IMG_0064`, `IMG_0084`, `IMG_0233`, `IMG_0497` |
| **Question** | Direct address, answered in the replies | `IMG_0085`, `IMG_0094`, `IMG_0095` |

**Length.** 1–2 lines is the norm. Anything past ~6 lines gets truncated by a
see-more link (`IMG_0170`), which the writers seem to treat as a cost.

**Number of images.** Three is the default, and it is a horizontal scroller, so
three is what shows. Two and one both occur. Four appears occasionally
(`IMG_0099`, `IMG_0108`).

**Closing.** *Notes almost never close.* No sign-off, no call to comment, no
question at the end — the reaction bar is the ending. Counted across the set,
the exceptions are a short half-line aside (`IMG_0492`, `IMG_0497`) and the
question-notes, where the question *is* the first line rather than the last.
This is the single most consistent finding in Part A and the easiest thing to
get wrong.

**Products are not labelled.** In note after note the garment is shown and never
named, priced or linked — the image carries the recommendation and the text
supplies only the occasion or the mood (`IMG_0119`, `IMG_0144`, `IMG_0158`,
`IMG_0160`, `IMG_0163`, `IMG_0164`). Where shopping intent exists it arrives as
a bare link or a link-preview card, not a list (`IMG_0170`, `IMG_0232`,
`IMG_0233`).

**Register signal.** Lowercase and unpunctuated reads casual (`IMG_0119`,
`IMG_0158`, `IMG_0159`, `IMG_0162`); sentence case with a full stop reads as a
recommendation or a review (`IMG_0120`, `IMG_0121`, `IMG_0160`).

### A2. The post

Two distinct bodies of evidence, and they behave differently.

**A2a. The styling post** — `IMG_0025`, `IMG_0032`, `IMG_0038`, `IMG_0039`,
`IMG_0040`, `IMG_0044`, `IMG_0092`, `IMG_0100`.

- **Title**: a recurring series name plus a colon plus the edition, or a
  sentence-shaped claim. `IMG_0025` is series + colon + month; `IMG_0038` is a
  numbered letter plus a count-led promise; `IMG_0039` is a colour-as-story plus
  a day-to-night span.
- **Subtitle**: always one line, and it states what the reader gets, not what
  the piece is about. Present on every titled post in the set.
- **Byline block**: author, date, sometimes a Listen button.
- **The opening**: `IMG_0025` puts the premise in a **quote block with a
  coloured left rule**, then an italic bridge line explaining the reuse. Others
  cold-open on a claim (`IMG_0032`, `IMG_0100`) or lead with the image before any
  words (`IMG_0038`, `IMG_0039`, `IMG_0063`).
- **Body rhythm**: a **bold, sentence-shaped section heading**, two to four short
  paragraphs, then one image or one collage. Repeat. `IMG_0028`, `IMG_0031`,
  `IMG_0032`, `IMG_0040`, `IMG_0100`.
- **Images sit between paragraphs**, never gathered into a gallery at the end.
- **Products**: two schools. Inline linked product names inside running prose
  (`IMG_0025`, `IMG_0039`, `IMG_0040`, `IMG_0044`), or a **small credit line
  directly under the collage naming the pieces** (`IMG_0032`). Nobody in this set
  uses a numbered list keyed to a numbered board.
- **Close**: a salutation and a first name (`IMG_0038`), or it simply runs on.

**A2b. The instructional post** — `IMG_0110`–`IMG_0118`, `IMG_0122`–`IMG_0129`.
Numbered sections with decimal sub-headings, an assertive sub-head, two to four
paragraphs, a screenshot as evidence, repeat, with a boxed call-to-action
between sections and a real ending: takeaway paragraph, subscribe line, thanks
(`IMG_0118`). Included for completeness; it is a different genre from the
styling posts and its apparatus does not transfer.

**A2c. The show review** — `IMG_0810`, `IMG_0816`, `IMG_0834`, `IMG_0867`.
Date or byline, a **drop cap**, a few lines truncated by a more-link, a
horizontal rule, then a numbered three-across grid of looks. Worth knowing
because it is the format readers arrive from.

### A3. What recurs across writers, and what doesn't

**Recurs (safe to build on):**
1. One-line caption over a three-up image row, no close — the Note.
2. Bold sentence-shaped section headings with one visual each — the post body.
3. A subtitle that promises, in one line.
4. Collage or board as the recurring visual unit rather than single photographs
   (`IMG_0025`, `IMG_0031`, `IMG_0032`, `IMG_0037`, `IMG_0038`, `IMG_0068`,
   `IMG_0079`, `IMG_0170`).
5. Colour-led notes that name a colour or a pairing as the whole caption and
   prove it across unrelated objects — not garments (`IMG_0102`, `IMG_0108`).

**Does not recur (a choice, not a convention):**
- Numbered labels on a board keyed to a numbered list below it. **Nobody does
  this.** The only numbered apparatus in 120 screenshots is the show-review grid
  (`IMG_0810` etc.) and a lookbook grid (`IMG_0533`).
- A swatch strip with hex values. The only named-colour card in the set is in a
  colour-analysis **video** (`IMG_0141`), not in anyone's post or note.

Both of those are in the brief's default board spec, so both are used below —
but they are our move, not a borrowed one, and that is worth knowing.

---

## Part B — board look

Eleven screenshots contain a collage, flat-lay or outfit board. Each was cropped
to its board region into a temp folder (not committed) and studied. There are
enough examples to derive a look; three distinct schools emerged.

### B1. The card board — the school worth copying

`IMG_0037`, `IMG_0068`, `IMG_0170`.

- **Ground**: warm off-white / cream, flat, occupying the whole card. In
  `IMG_0170` the ground has a faint paper texture.
- **Card**: rounded corners, sitting on a much darker page ground so the card
  reads as an object. `IMG_0037` and `IMG_0068` show three such cards side by
  side in one Note.
- **Inspiration image inside the board**: yes — `IMG_0037` and `IMG_0068` both
  place a rectangular photograph or artwork inside the card, usually upper-left
  or as a backdrop panel, with the cut-out garments overlapping its edge. This
  is exactly the inspiration-plus-outfit arrangement the brief describes.
- **Scale**: deliberately uneven. A coat at full height next to earrings at 5%
  of it. Small accessories are scattered at the edges rather than lined up.
- **Overlap**: slight and frequent. Pieces touch and overlap by maybe 5–15% of
  their width; nothing is neatly gridded.
- **Body order**: loose rather than strict. Tops upper, bottoms lower, shoes at
  the foot — but accessories float wherever there is a hole.
- **Labels**: none. No numbers, no captions, no prices.
- **Swatches**: none.
- **Signature**: a small, wide-letter-spaced serif wordmark, bottom centre
  (`IMG_0037`, `IMG_0068`) or on a small card inside the board (`IMG_0170`).
- **Shadow**: barely any. Pieces sit flat.

### B2. The mosaic — dense, edge to edge

`IMG_0025`, `IMG_0031`, `IMG_0032`, `IMG_0079`.

No ground visible at all: rectangular photo crops and cut-outs tiled to fill the
frame, touching, on white (`IMG_0025`, `IMG_0031`) or with staggered rectangles
and slight overlaps (`IMG_0032`). No labels, though `IMG_0032` carries a small
credit line *underneath* the collage. High information density, low legibility
per piece. Good for a mood, bad for "here are the six pieces".

### B3. The colour board — swatch beside the thing

`IMG_0141`, `IMG_0142`.

Warm greige ground. A product cut-out on the left, a **named colour card** in the
middle — a large flat colour block with a thin white inset border, the code and
the colour name in small sans-serif underneath — and a worn example on the right.
Varied sizes, slight overlaps, thin borders on the photographs. This is the only
place in 120 screenshots where a colour is *named and shown* rather than just
shown, and it is the direct ancestor of the swatch strip used below.

### B4. The spec we build to

Taking B1 as the base, B3 for the swatch idea, and the brief's default where the
evidence is silent:

| Element | Decision | From |
|---|---|---|
| Canvas | 1080 × 1350 portrait; landscape variant 1456 px wide | brief |
| Ground | warm off-white `#F3EFE7` | B1 |
| Card | full-bleed ground, thin warm border, no rounded corner (a rounded corner reads as a screenshot of a card rather than a board) | B1, adapted |
| Inspiration image | left, ~40% of width, thin white border, slight inset shadow | B1 + brief |
| Pieces | right, loose body order — layer / top / bottom / shoes / bag / accessory — with 5–12% overlaps and uneven scale | B1 |
| Shadow | very soft, 6–10px, low opacity | B1 |
| Labels | small numbered discs beside each piece | **brief — not observed in any screenshot** |
| Swatches | strip along the bottom, hex under each chip | **B3 for the idea, brief for the strip** |
| Title | short serif, upper left | B1 signature adapted |
| Typeface | EB Garamond (serif) + Inter (sans), both SIL OFL, fetched to `content/boards/fonts/` | — |
| Version B | palette card replaces the inspiration photograph, same geometry | brief |

**Honest divergence:** numbered labels and the swatch strip make these boards
more explanatory and less atmospheric than anything in the swipe file. That is a
deliberate difference — the whole proposition is saying *why*, and none of these
writers do. It also means the boards will not look like theirs, which is the
point.
