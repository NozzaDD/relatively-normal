# brands/

One YAML file per brand, named with a lowercase-hyphenated slug:
`max-mara-weekend.yaml`, `merz-b-schwanen.yaml`, `cos.yaml`.

## What belongs here

Structured, factual notes on each brand so they can be compared, filtered and
later loaded by the wardrobe tool: price bands, sizing and fit notes, materials
and quality, what they're actually good for, what to avoid, where they sit in
the frameworks, and sourcing links.

## What doesn't belong here

Prose reviews and opinion pieces — those are content. Keep these files
structured and scannable; if a thought needs a paragraph, it probably belongs in
`content/notes/`.

## Conventions

- One brand per file, YAML only. The schema lives in this README.
- Keep the same keys across files so they stay machine-readable.
- Nothing goes in a field unless it is verified. No invented prices, material
  compositions or affiliate links — leave the key empty and say it is unknown.
- Never record a brand as sustainable unless a material-rubric field supports it.
- Note the date on anything that goes stale (prices, sizing changes, ownership).
