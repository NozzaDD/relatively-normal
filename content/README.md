# content/

Everything written for an audience, plus the raw material it comes from.

## What belongs here

- `backlog.yaml` — every note, post, series and campaign idea, each with a
  trigger saying when it can run. Nothing is deleted from it; entries are
  marked published or dropped, so the record of what worked stays.
- `ready-now.md` — generated. What can run today and what is waiting on what.
- `ready_now.py` — the generator behind that file.
- `posts/` — the weekly newsletter posts, one markdown file each.
- `swipe/` — saved inspiration: `formats/`, `visuals/`, `products/`,
  `artworks/`, and `notes.md` for the observation that goes with each file.
- `notes/` — working thoughts, half-ideas, research and observations that aren't
  yet a post.
- `note-bank.md` — the running list of ideas, lines and fragments to pull from
  when drafting. Cheap to add to, no structure required.
- `calendar.md` — the publishing schedule: what goes out when, and what state
  each piece is in.

## Regenerating ready-now.md

From the repository root:

```sh
python -m content.ready_now
```

It reads `backlog.yaml`, follows the `metrics_file` entry to `data/metrics.yaml`,
checks every live entry's trigger, and rewrites `ready-now.md`. Don't edit that
file by hand — change the backlog or the metrics and run this again.

The list is date-dependent, so it goes stale on its own: a date window that
opened yesterday won't show until it is regenerated. `--check` says whether the
file on disk is current and exits non-zero when it isn't; `--date YYYY-MM-DD`
answers "what would be ready then" without waiting for the day.

```sh
python -m content.ready_now --check
python -m content.ready_now --date 2026-10-06
```

Needs PyYAML (`pip install pyyaml`).

## What doesn't belong here

Voice rules (`voice/`) and the frameworks the writing draws on (`frameworks/`).
Client-specific work lives in `consultations/`.
