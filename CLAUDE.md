# CLAUDE.md — Relatively Normal

Read this before doing anything in this repository.

## What this is

A styling newsletter on Substack and, from 2027, a wardrobe tool. Positioning: online
styling inspired by fashion weeks, colour palettes and reader questions about specific
occasions. Sustainable and well-made brands preferred but not exclusively — quality and
wear count decide, so H&M can appear when it earns it. Personal angle: Italian materials
and craftsmanship, and the perspective of a German living in Switzerland, permanently
on the hunt for things worth buying.

## Hard rules

1. You NEVER write final published text. Not a note, not a post, not a caption.
   You produce angles, structures, research, variants and edits. The owner writes
   the words. If asked to "write the note", produce three angles and a rough shape.
2. Never invent a brand, product, price, material composition or affiliate link.
   If it isn't in brands/ or you can't verify it, say so.
3. The material rubric in frameworks/ is the source of truth for whether a brand
   or garment passes. Do not reason about quality from general knowledge when the
   rubric exists.
4. Sustainability is a rule, not a posture. Never describe a brand as sustainable
   unless a rubric field supports it.
5. A rule may only name a colour that exists as an anchor in seasons.yaml.
6. Identify a fabric by its declared fibre, never by its colour. Denim, suede and
   silk share their colours with real palette anchors; a colour test cannot
   separate them.
7. When a frequency assumption doubles, a per-unit engagement assumption should
   usually fall. This applies to the model and to any rule where more of
   something is assumed to produce proportionally more.
8. Report and stop rather than build something you can demonstrate is wrong.
   Three framework errors were caught this way; none would have been caught by
   building the instruction as written.

## Structure

- voice/ samples + do/don't sheet. Read before any writing task.
- frameworks/ colour.yaml, coverage-matrix, material-rubric.md, scope.md
- brands/ one YAML per brand; schema in brands/README.md
- content/ calendar.md, note-bank.md, posts/
- content/swipe/ inspiration — formats, visuals, products, artworks, and notes.md
- content/palettes/ the desk's palettes — palettes.json is built by content/tools/build_palettes.py; README says what it found
- consultations/ one folder per beta participant, never published without consent noted
- staples/ the staples catalogue — one YAML per slot; schema in staples/README.md
- engine/ the deterministic colour engine in Python; the frameworks are its specification, tests in engine/tests/
- templates/trial/ the narrow first-trial scope — one occasion, one month
- data/ utm-scheme.md, metrics
- app/ empty until 2027

Before building anything that sounds missing, read frameworks/scope.md. It is the
answer to "should we build X": usually X already exists in engine/ and needs
turning on, not writing. Narrowing happens in what we ask a person for, never by
removing capability.

## Conventions

- Files are markdown or YAML. English for structure and metadata; the owner writes
  in English.
- Front matter on every post: title, date, format, campaign, brands, affiliate (yes/no).
- Brand slugs are lowercase-hyphenated: max-mara-weekend, merz-b-schwanen.
- Commit messages say what changed and why, one line.

## How sessions work here

The repository is the memory. Sessions are disposable: one task, one report, then
let it go. Nothing you learned in a session survives it — if it matters, it goes
into a file, and usually into frameworks/ or this document.

Work must be merged to main before the next session starts, or the next session
will not see it. A branch that has not landed does not exist as far as the next
session is concerned.

Separate areas of work belong in separate sessions. Engine and content do not
share a session: they touch different files, fail in different ways, and mixing
them makes both reports worse.

## When unsure

Ask. A wrong claim about a brand's materials reaches readers who trust the rubric.
