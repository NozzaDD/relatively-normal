# content/posts/

One markdown file per weekly post.

## Naming

`YYYY-MM-DD-slug.md`, dated by intended publication date.

## Structure

Start each file with front matter so posts stay sortable and can later be read
by the site in `app/`:

```yaml
---
title:
date:
format:
campaign:
brands: []
affiliate: no
---
```

All six fields are required on every post. `brands` lists brand slugs as they are
named in `brands/`; `affiliate` is yes/no; `campaign` matches the UTM scheme in
`data/utm-scheme.md`.

Then the post body in markdown. Drafts live here too — the calendar in
`content/calendar.md` tracks what state each piece is in, so nothing needs to move
between folders.
