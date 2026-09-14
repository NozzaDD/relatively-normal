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
status: draft | scheduled | published
tags: []
utm_campaign:
---
```

Then the post body in markdown. Keep drafts here too — `status` tracks where a
piece is, so nothing needs to move between folders.
