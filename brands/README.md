# brands/

One YAML file per brand, named with a lowercase-hyphenated slug:
`max-mara.yaml`, `merz-b-schwanen.yaml`, `barena-venezia.yaml`.

Structured, factual notes on each brand so they can be compared, filtered and
later loaded by the wardrobe tool (`matching.md` §5, source 3). Prose reviews and
opinion belong in `content/notes/`, not here.

## Hard rules for this folder

- **Nothing goes in a field unless it is verified.** No invented prices, material
  compositions, ownership or affiliate links.
- `unknown` is a valid and expected value. It means nobody has checked yet, and it
  is always better than a plausible guess.
- **Never record a brand as sustainable unless a `frameworks/material-rubric.md`
  field supports it.** There is no `sustainable` key for this reason.
- `rubric_score` stays blank until the brand is scored against the rubric.

## Schema

```yaml
name:                 # Brand name as it writes itself
slug:                 # lowercase-hyphenated; matches the filename
country:              # Country of the brand's base, or unknown
ownership:            # family | private | listed | group | unknown
price_band:           # accessible | mid | upper | luxury | unknown
core_materials: []    # Fibres and cloths the brand actually builds on; [] if unchecked
construction_notes:   # Construction markers relevant to rubric field 2, or unknown
rubric_score:         # BLANK until scored. Fields in frameworks/material-rubric.md
affiliate_available:  # yes | no | unknown
partnership_tier:     # first | mid | later | mill
notes:                # Free text: what it's for, what to check, what is unverified
```

### Field values

**`ownership`**

| Value | Meaning |
|---|---|
| `family` | Owned and run by the founding family |
| `private` | Privately held, not by the founding family (investor, fund, individual) |
| `listed` | Publicly traded, including where a family retains control |
| `group` | A line inside a larger fashion group |
| `unknown` | Not verified |

**`price_band`** — positioning, not a price list. Rough guide for a core garment:

| Value | Guide |
|---|---|
| `accessible` | under ~150 |
| `mid` | ~150–450 |
| `upper` | ~450–1200 |
| `luxury` | above ~1200 |

Currency deliberately unstated — these are bands for sorting, not quotes. Adjust
the boundaries once real figures are in.

**`partnership_tier`** — the order to approach them in, not a quality ranking:

| Value | Meaning |
|---|---|
| `first` | Approach early: reachable, plausible fit for a small newsletter |
| `mid` | Approach once there is an audience and a track record |
| `later` | Long-term; large or tightly controlled brands |
| `mill` | Not a clothing brand — a cloth or yarn maker. A different kind of partnership: material stories, not product placement |

### Multi-line brands

Where one house runs several lines at different price points, keep them in one
file under a `lines:` key, each with its own `price_band` and `notes`:

```yaml
lines:
  - name:
    price_band:
    notes:
```

The top-level fields describe the house; `lines` carries what differs.

## Maintenance

- Date anything that goes stale — prices, ownership, production location.
- Re-score against the rubric when a brand changes ownership or moves production.
- A brand file is a prior for a typical garment, not a verdict on a specific piece.
