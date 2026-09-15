# UTM Scheme

The naming convention for every tagged link. Consistency here is what makes the
metrics readable later — a link tagged off-scheme is a row that never joins up
with anything else, and there is no fixing it after the click.

All values **lowercase, hyphenated, no spaces, no underscores.**

---

## The five parameters

| Parameter | Values |
|---|---|
| `utm_source` | `substack` \| `tiktok` \| `instagram` \| `tool` |
| `utm_medium` | `note` \| `weekly` \| `monthly-personal` |
| `utm_campaign` | `YYYY-MM-DD-slug` |
| `utm_content` | `item-slug` or `brand-slug` |
| `utm_term` | occasion or gap-type |

### `utm_source` — where the click came from

| Value | Meaning |
|---|---|
| `substack` | The newsletter itself, on the web or in the inbox |
| `tiktok` | TikTok, in any placement |
| `instagram` | Instagram, in any placement |
| `tool` | The wardrobe tool — a link inside a recommendation the app produced |

### `utm_medium` — what kind of piece it was

| Value | Meaning |
|---|---|
| `note` | A short note |
| `weekly` | The weekly post |
| `monthly-personal` | The personalised monthly recommendation run |

Source and medium are independent. A weekly post shared to Instagram is
`source=instagram`, `medium=weekly`.

### `utm_campaign` — which piece

Always `YYYY-MM-DD-slug`, dated by publication date, matching the post filename in
`content/posts/` minus the `.md`.

```
2026-10-05-teal-and-ochre
```

This is the key that joins a link back to the post that carried it. The post's
`campaign` front-matter field (see `content/posts/README.md`) must carry the same
string.

### `utm_content` — which thing was clicked

The item or brand, so that two links in the same piece can be told apart.

- A brand: use the brand slug exactly as it appears in `brands/` —
  `max-mara`, `merz-b-schwanen`, `barena-venezia`
- A staple: use the item slug from `staples/` — `merino-crew`, `wool-trouser`
- A specific colourway: append it — `merino-crew-olive`

### `utm_term` — why it was suggested

The occasion or the gap type the link was answering. This is the field that turns
click data into something the frameworks can use: it says what job the reader was
trying to do.

- Occasion: `wedding-guest`, `office`, `weekend`, `travel`, `winter-coat`
- Gap type, from `matching.md` §4: `empty-slot`, `near-miss`, `tier-imbalance`,
  `contrast-mismatch`

---

## Worked examples

A brand link in the weekly post, answering a coat gap:

```
?utm_source=substack&utm_medium=weekly&utm_campaign=2026-10-05-teal-and-ochre
&utm_content=herno&utm_term=winter-coat
```

A staple colourway in a monthly personalised run, filling an empty slot:

```
?utm_source=tool&utm_medium=monthly-personal&utm_campaign=2026-11-01-monthly
&utm_content=merino-crew-dark-teal&utm_term=empty-slot
```

A note on Instagram pointing at a brand:

```
?utm_source=instagram&utm_medium=note&utm_campaign=2026-10-12-what-camel-is-for
&utm_content=max-mara&utm_term=office
```

---

## Rules

- **Never reuse a campaign string.** One post, one campaign. A re-share of the
  same post keeps the original campaign and changes only the source.
- **Never invent a slug.** `utm_content` must match a real file in `brands/` or
  `staples/`. If it does not exist there, it does not go in a link.
- Tag every outbound link, affiliate or not. Untagged links are invisible in the
  metrics and make affiliate performance look better or worse than it is.
- Affiliate links carry the affiliate network's own parameters as well. Keep the
  UTM parameters — they answer a different question.
- `utm_term` is optional only when nothing sensible fits. Prefer leaving it out to
  inventing a category.

## Open question for the owner

`utm_medium` has no value for a link in the beta consultation deliverables
(`consultations/`). Either those links go untagged, or the scheme needs a fourth
medium. Not decided here.
