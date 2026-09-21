---
title: What of SS27 actually survives a European autumn
date: 2026-09-27
format: weekly
campaign: 2026-09-27-european-autumn-ss27
brands: []
affiliate: no
---

status: outline

> **Post A — what the plan says is due next.**
> There is no `content/calendar.md`, so "due next" was derived from
> `content/backlog.yaml` and `content/ready-now.md`. The only dated trigger open
> in the next fortnight is `series-fashion-week-european-lens`, window
> **2026-09-17 → 2026-10-06**. It closes in 16 days and then lapses until
> February. The library's second-largest folder — 79 SS27 runway screenshots —
> exists to serve it. This is that post.
>
> `brands: []` is deliberate and **must stay empty unless step 5 below resolves
> the tab titles**. The runway galleries carry truncated browser tabs
> (`Kallmeye…`, `Tory Bur…`, `Proenza`) and CLAUDE.md hard rule 2 forbids
> naming a house that isn't legible. See *What I need from you*.

---

## Three title options

1. **What of SS27 actually survives a European autumn**
   — plainest, matches the backlog entry's own framing.
2. **Nine degrees and raining: the SS27 edit**
   — leads with the constraint rather than the season. Sharper, less searchable.
3. **I watched the shows with a weather app open**
   — the personal register. Best if the piece leans on your own scepticism
   rather than on the analysis.

**Thesis (one sentence).** A runway look is a proposal made under studio
lighting on a warm set, and the only useful question for a reader in Zürich in
October is which of its *relationships* — not its garments — survive a real
temperature and a real wardrobe.

---

## Paragraph-level outline

**¶1 — The frame.** Establish the single criterion before showing anything:
not "is this nice", not "will this be everywhere", but "does this relationship
work at nine degrees with the clothes you own". One paragraph, no images.

**¶2 — The neutral suit, and why it is the easy one.**
Image: `fashion shows ss27/IMG_0836.png`. Uses **worked example O-new (see
below)**. The point: a stone-greige suit with one rust accessory is the
corporate version of the entire system — one neutral ground, one accent. It
survives autumn unchanged. Say why that's boring and correct.

**¶3 — Two reds, and the rule they break.**
Images: `fashion shows ss27/IMG_0843.png`, then `IMG_0838.png`. Uses
**worked example O3** in full. The point: head-to-toe rust with an oxblood bag
fails the value test by a wide margin (ΔL\* 14.0 against a required 25) and
works anyway, because three different surfaces are doing the job three
different colours would normally do. This is the paragraph that earns the
reader's trust, because it admits the method's limit in the method's own terms.

**¶4 — The one where the room is half the outfit.**
Image: `fashion shows ss27/IMG_0860.png`. Uses **worked example O4**. The point:
this look is the reference pair — ochre against teal, 172.7°, Δ relative chroma
0.03 — and the teal is a *wall*. Deflate it honestly. A runway has a set
designer; your hallway does not. This is also where the attention-economy angle
enters: it is beautiful, it is not transferable, and both facts can sit
together.

**¶5 — What is actually transferable: placement.**
Image: `fashion shows ss27/IMG_0863.png`. Uses **worked example O6**. The point:
the only light thing in the look is a pale sash at the waist. You cannot buy
the dress; you can move a belt. Placement travels where garments don't.

**¶6 — The European test, applied.**
No new image; a short list built from ¶2–¶5. Four relationships, each rated on
whether it holds at nine degrees: neutral-plus-one-accent (holds), tonal-plus-
texture (holds, and is warmer than it looks), garment-plus-set (doesn't travel),
one-pale-band-placed (holds, costs nothing).

**¶7 — What I'd wear instead, from things that exist.**
Images: `products/IMG_0223.png` and `products/IMG_0283.png`. Uses **worked
examples O1 and O2**. The point: the wearable version of ¶2 already exists as
two real garments, and one of them — the Aspesi camel corduroy jacket over a
dark olive skirt — is a pair the engine names (`Dark Olive and Camel`, Muted).
Bring it back to earth.

**¶8 — The honest close.** The window on this post closes on 6 October and then
there is nothing seasonal until February. Say what you'll do with the other
75 screenshots. Lead into the consultations ask without making it yet — Post B
carries that.

---

## The worked examples, in full

### O3 · `fashion shows ss27/IMG_0843.png` — rust knit and rust wrap skirt

Head-to-toe one rust, cardigan and skirt, with an oxblood tote and a taupe pump.
Knit-on-knit; the cardigan hem cuts the skirt at the high hip; a front slit gives
the column a moving edge. The unexpected move is the taupe shoe — a lighter
neutral under a saturated column, which stops the look ending in a dark full
stop.

**It fails the rule and works anyway.** Knit `943D2A` against tote `5A2A22`:
hue gap **4.0°** — the Tonal band — Δ relative chroma **0.11** (inside the 0.20
limit), and **ΔL\* 14.0** against a required **25**. Engine verdict:
`NO GENERATOR`.

What carries it is surface: rib knit, wrap crepe, polished leather.
`matching.md` has a texture check, but it only fires to flag an outfit as
*flat* — it cannot credit texture for rescuing a failed value gap. That is a
real limit of the system and this paragraph is where to say so.

### O4 · `fashion shows ss27/IMG_0860.png` — ochre pile knit, plum skirt, teal set

Ochre beaded-fringe sweater over a deep plum crackled midi skirt, plum beanie,
chartreuse-gold sandals, against a strong teal wall on a terracotta floor.

Knit `9C6A22` against backdrop `1D4559`: hue gap **172.7°**, Δ relative chroma
**0.03**, ΔL\* **21.5**. Engine verdict: **opposition** — this is Teal and Ochre,
the reference pair the whole direction is named after, and **the garment supplies
only one half of it**.

Re-scored as an office outfit (ochre knit, plum skirt, chartreuse sandal) the
engine returns **not valid**: plum + chartreuse passes as Muted
(`Soft Plum and Camel`), the ochre knit pairs with neither, tier mix is
**foundation-light** at 1.00 supporting / 0.00 foundation, and the context check
flags **two** items *not corporate*. Beautiful, and not for the office, with
reasons.

### O6 · `fashion shows ss27/IMG_0863.png` — black dress, butter-yellow sash

A black draped V-neck dress with a pale butter-yellow sash at the waist, a deep
burgundy draped panel, oxblood shoes. Dress `262427`, oxblood notes `60342E`.

The only light thing in the outfit sits exactly at the waist, which is where a
value break moves the eye. One accent, placed, not scattered.

Frameworks reading: black at the face is *out* for Soft Autumn
(`black: below_waist_or_hardware` in `seasons.yaml`). So this is a look to learn
the **placement** from, not the colours — and saying that explicitly is the
difference between this newsletter and a runway roundup.

### O-new · `fashion shows ss27/IMG_0836.png` — stone-greige suit, rust raffia bag

Oversized shoulder, long lapel, wide trouser breaking over a flat brown shoe;
one rust raffia bucket bag. Palette `C0B8AF` (41%) `2F2A2D` (24%) `E7EAEC` (16%)
`736F71` (12%) `864B31` (8%).

One neutral ground plus one accent, which is what the tier split
(55 / 30 / 15) describes when you build it rather than read it. It is the least
exciting look in the folder and the only one that transfers whole.

### O1 · `products/IMG_0223.png` — Aspesi camel corduroy jacket *(for ¶7)*

*GIACCA IN VELLUTO A COSTE, colour BEIGE. The Italian details text names
garment-dyed 500-line cotton corduroy with a cotton twill sleeve lining; the
Composition panel is collapsed, so no percentages are available.*

Short straight jacket over a full mid-calf skirt — the break at the high hip,
the skirt carrying all the volume. Jacket open over a fine stone knit, nothing
tucked. Four surfaces, no two alike: corduroy pile, flat knit, matte skirt cloth,
smooth black boot. Camel `A87C4A` over dark olive, stone between them.

Engine, on the outfit as the brand styled it: **not valid**, but three of four
pairs pass and two of them on the named Muted pair **`Dark Olive and Camel`**.
The one that fails is camel jacket against stone knit — two warm neutrals a
value step apart with no band for them. (See §7.1 of
`content/review-2026-09-20.md`; I think that failure is the system's, not the
outfit's.)

The unexpected move is the **black boot on a soft season**, and it is legal:
`seasons.yaml` gives Soft Autumn `black: below_waist_or_hardware`, and the slot
rule runs before the avoid list.

### O2 · `products/IMG_0283.png` — Lardini SHORT BEIGE PEACOAT *(for ¶7)*

A cropped camel peacoat over very wide, very long chocolate trousers that break
over the shoe. Two garments, two colours, nothing else. Melton against flat
suiting — the weakest texture mix in the set, and it survives because the value
gap is enormous (camel around L\* 59, chocolate around L\* 19).
`combinations.md`'s "the clarity comes from the value", in one picture.

---

## Product slots, with brand status

| ¶ | Piece | File | Brand | Status in `brands/` |
|---|---|---|---|---|
| 7 | camel corduroy jacket (GIACCA IN VELLUTO A COSTE, colour BEIGE) | `products/IMG_0223.png` | Aspesi | **in `brands/aspesi.yaml`** — `rubric_score` **blank**, `ownership: unknown`, `affiliate_available: unknown`. Cannot be said to pass. |
| 7 | dark olive midi skirt (styled with the above; not a separate product page) | `products/IMG_0223.png` | Aspesi | as above. **No product name or composition legible** — "unknown, Nora to confirm". |
| 7 | SHORT BEIGE PEACOAT | `products/IMG_0283.png` | Lardini | **in `brands/lardini.yaml`** — `rubric_score` **blank**. File warns canvas construction "varies by line — do not assume canvas across the range". |
| 2–6 | every runway look | `fashion shows ss27/IMG_0836, 0838, 0843, 0860, 0863` | **truncated tab only** | **NOT IN `brands/`, and not identifiable.** Inspiration only. Do not name, do not link, do not recommend. |

**Flags.**
- Both named brands are in `brands/` and **neither can be scored**, because every
  `rubric_score` in the folder is blank and `material-rubric.md` has no passing
  threshold set. Any sentence implying either brand "passes" is unsupported
  until that is filled in.
- The runway houses are **inspiration-only by necessity** — they are not in
  `brands/` and their names are not legible. This happens to match the editorial
  rule you gave me ("runway and luxury houses are colour and trend inspiration
  only"), which, as noted in the review, **is not written down anywhere in this
  repository**.
- `affiliate: no` in the front matter. Nothing here is linkable: no
  `affiliate_available` field in `brands/` is anything but `unknown`.

---

## Which of the 25 notes lead into this post, and which follow

**Lead in (run before 27 Sep):**
- **N04** — three SS27 looks judged on weather alone (Tue 22, #2). The direct trailer.
- **N07** — tan on green, why it isn't camouflage (Thu 24, #1). Teaches the Tonal test the post leans on in ¶3.
- **N11** — two patterns, and why it isn't loud (Sat 26, #1). Sets up "relationships, not garments".
- **N13** — the shoe the palette says you can't wear (Sun 27, #2). Runs the same day; the O1 black-boot beat in miniature.

**Follow (run after 27 Sep):**
- **N17** — two reds, one value step (Tue 29, #2). Expands ¶3 into its own note.
- **N18** — one pale band, at the waist (Wed 30, #1). Expands ¶5.
- **N24** — short over long, dark over pale (Sun 4 Oct, #1). Carries ¶7 into Post B's week.
- **N10** — the rebuy question (Fri 25, #2). Comment generator, deliberately unrelated, to keep the week from being all analysis.

---

## What I need from you

1. **The house names, or a decision not to use them.** Three galleries have
   truncated tabs. Either confirm the collections from your own browser history,
   or the post runs describing looks without attributing them — which is
   defensible but unusual, and readers will ask.
2. **The weather.** ¶1 and ¶6 turn on a real temperature. What is a Zürich
   October morning actually like, and what do you actually put on?
3. **Whether ¶3's admission is too much.** The post says the method fails on a
   look that obviously works. I think that is the strongest paragraph. You may
   think it undercuts the product before it launches.
4. **Your voice.** `voice/` contains a README and nothing else — no samples, no
   do/don't sheet. None of the above has been checked against how you write.
5. **Anything that actually happened to you** at the shows, in a shop, on a
   train. There is none in here and the register the backlog calls "the Italian
   boyfriend" cannot be supplied by me.

---

## Open questions

- **Does the window matter more than the post?** The trigger closes 6 Oct. If
  27 Sep is too soon, the last usable date is Sun 4 Oct — but that is the slot
  Post B wants. One of the two moves, or one waits until February.
- **Seventy-nine screenshots, five used.** Is the rest a second post, a notes
  archive, or deletion? See Approvals item 1 in the review.
- **Is `format: weekly` right?** `data/utm-scheme.md` defines `weekly` as a
  `utm_medium` value; `content/posts/README.md` requires a `format` field but
  never says what the permitted values are. I used `weekly`. There is no other
  post in the repository to match against.
- **`series-fashion-week-european-lens` recurs every Feb/Mar and Sep/Oct.** Should
  this post be built as a template so the February one is a fill-in rather than
  a rewrite?

---
---

# DRAFT

**Written 21 September 2026. Publish-ready prose — and not in your voice yet:
`voice/` still contains only a README, so none of this has been checked against
how you actually write.** The no-published-text rule was suspended for this
session at your instruction; it resumes afterwards.

**Scope note.** This draft is written for a general reader. It names no personal
palette, no colouring, no wardrobe, and it reports no palette-membership or
contrast verdict — those are tied to a profile the reader doesn't share. It uses
only the general pairing relationships.

---

## Title options

1. **What of these actually survives a European autumn**
2. **Nine degrees, and a show notebook**
3. **I went through the September shows looking for arithmetic**

**Subtitle:** Four colour relationships from the autumn shows, and what each one
costs to reproduce from clothes that already exist.

---

## The draft

A runway look is a proposal made under lights, on a set that was built for it,
worn by someone standing still for four seconds. Almost nothing about that
survives contact with a Tuesday. But the *relationships* do — the reason two
colours sat well together in a photograph is the same reason they will sit well
together on a pavement, and that reason can be written down as a number.

So this is not a trend report. It is four relationships, pulled out of four
photographs, with the garments removed and only the colours left. Then the same
relationship rebuilt out of things you can actually buy.

One piece of housekeeping first. When I pull colours out of a runway photograph
I take them from the clothes only — not the wall, not the floor, not the model.
This matters more than it sounds. One of the looks below is famous for a
particular colour pairing that, once you mask out the set, turns out not to be
in the clothes at all.

### The easy one: a cool colour against a warm one

<img src="../boards/2026-09-21/board-1-a-wide.jpg" width="720">

1. Double-breasted trench in virgin wool gabardine, colour *Barbera* — Aspesi
2. Boat-neck merino knit, colour *Avio* — Aspesi
3. Cotton gabardine skirt, colour *Beige* — Aspesi
4. Tall riding boots — brand unknown
5. Crinkled leather shoulder bag — COS
6. Ribbed wool scarf — Margaret Howell

The look that started this is a pale blue coat with a warm brown shoe. Opposite
sides of the wheel — a hundred and sixty-seven degrees apart, which is as close
to true opposition as clothes usually get.

But hue opposition on its own is a costume. Saturated orange against saturated
teal is a traffic cone. What makes this particular version calm is that both
colours are using about the same *fraction* of the saturation available to them
— the difference is two hundredths. Matched intensity is what stops opposition
shouting.

Rebuilt above: a blue knit at 2, a tan skirt at 3. Hue gap a hundred and
sixty-four degrees, saturations within thirteen hundredths, and a lightness gap
of twenty-three points to keep them legible against each other rather than
muddy. The trench and the boot are the same colour as each other — near enough
that the system calls them one colour — so they read as a frame rather than a
third voice.

The thing to take from this one is the second condition. Everybody knows about
opposite colours. Far fewer people know that they have to be equally loud.

### The one everybody can wear: one hue, three depths

<img src="../boards/2026-09-21/board-2-a.jpg" width="480">

1. *Carlotta2* cotton corduroy double-breasted jacket, colour *Taupe* — Massimo Alba
2. V-neck wool-cashmere knit — Aspesi
3. Cotton gabardine skirt, colour *Beige* — Aspesi
4. Soft flat loafers with pull tab — soeur
5. Cashmere-and-silk bandana, deep brown — Massimo Alba

If opposition is the party trick, this is the thing you would actually wear on a
Wednesday, and it is the hardest to get subtly wrong.

One hue. Several depths of it. The condition is that the hues stay within about
forty degrees of each other — which is roughly "the same colour name" — and that
the *lightness* steps stay wide. Twenty-five points minimum. That number is the
whole discipline. Two browns eight points apart do not read as a decision; they
read as an accident with the laundry.

On this board the knit and the jacket are three and a half degrees apart in hue
and twenty-eight and a half points apart in lightness. The knit and the skirt are
so close in colour — six points of difference — that they count as one colour
worn twice, which is allowed outright and is a great deal more elegant than it
sounds.

What this one costs to reproduce: almost nothing. Every wardrobe already contains
three browns or three greys or three blues. The work is not acquisition, it is
arranging them so the steps are wide enough.

### The quiet one nobody talks about

<img src="../boards/2026-09-21/board-4-a.jpg" width="480">

1. Short blouson jacket, olive — Aspesi
2. *Virginia* virgin wool and alpaca sweater, colour *Raspberry* — Massimo Alba
3. Wide-leg velvet trousers, cream — Aspesi
4. Soft flat loafers with pull tab — soeur
5. Ribbed wool scarf — Margaret Howell

There is a third case, between opposition and same-family, that gets almost no
attention: hues roughly forty to a hundred degrees apart. Faded pink against a
dark olive. Neither opposite nor neighbourly — the awkward middle.

It works under stricter conditions than either of the others. Both colours have
to be genuinely low in saturation, and the lightness step has to be wide. On this
board the gap is fifty-one points, which is what is holding it up.

And here is the honest part. I could not find this relationship in any of the
runway photographs I looked at. Not one. The reason is structural rather than
mysterious: shows are lit and styled for saturation, and this particular
relationship only exists below a certain saturation ceiling. It is a shop-floor
relationship and a real-life relationship, and it is almost absent from the
runway — which may be exactly why nobody writes about it.

### The one where the room was doing half the work

<img src="../boards/2026-09-21/board-4-b.jpg" width="480">

The look that produced the board above is, at first glance, a textbook example of
opposite colours: a gold knit against a strong teal. It is the pairing I most
wanted to write about.

Then I masked out everything that was not a garment, and the teal went with it.
It is the set wall. The clothes are ochre, plum and a deep brick — a perfectly
nice arrangement, and a completely different one. Half of what made that
photograph was a colour nobody in it was wearing.

This is not a complaint about the show. It is a note about what a photograph of
clothes is. Backgrounds are chosen by someone whose job is to make the clothes
look inevitable, and they are extremely good at it. If you have ever bought
something that looked wrong at home, this is one of the reasons, and it is not
your lighting.

### What it costs

Four relationships, and what each one actually asks of you:

- **Opposite hues** — needs two colours at matched saturation. Cheap to arrange
  if you already own both, impossible to fake if you do not.
- **One hue, several depths** — needs nothing you do not have. Just wider steps.
- **The quiet middle** — needs both colours to be genuinely muted, which is a
  buying constraint rather than a styling one.
- **One colour on a neutral ground** — needs exactly one loud thing. The most
  forgiving of the four and the one most wardrobes are already halfway to.

The gap I kept running into, building all six of these, was not a colour. It was
a **mid-tone**. A shoe at the middle of the lightness range, a bag at the middle
of the lightness range. Almost everything sold is very dark or very pale, and
two very dark things next to each other go flat. If you are buying one thing this
autumn on the strength of a relationship rather than a look, buy the middle.

---

## Notes that lead into this post, and follow it

**Before:** board 1 and board 2 as Notes (`content/boards/2026-09-21/README.md`),
then Note B, *tan on green should be camouflage*, which teaches the tonal rule
the post leans on twice.

**After:** board 4 and board 6 as Notes; then Note D, *two reds, one step apart*,
which is the honest limit of the whole method and works better after the post
than before it.

---

## Still open

- **Title.** Option 1 is searchable and dull; option 3 is the one I would click.
- **The house names.** Still not legible on any of the four galleries used, so no
  house is named anywhere in the draft. If you can confirm them from your own
  history, the piece gets stronger; if not, it stands as written.
- **Length.** This is around 900 words. Every styling post in the swipe file is
  longer, and most carry one image per section — this carries four images across
  six sections, which is sparser than the convention.
- **The product list format.** I used a numbered list keyed to numbers on the
  board. **Nobody in 120 screenshots does this** — they use inline links in
  running text, or a small unnumbered credit line under the collage. Our version
  is clearer and less native. Your call, and it is the same question as the
  swatch strip.
- **`brands: []` in the front matter is still correct** — no house is named, and
  the brands that appear on the boards appear in the boards, not in the post's
  own metadata. If you want the post to carry them, the list is: `aspesi`,
  `massimo-alba`, `lardini`.
