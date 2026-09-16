"""Regenerate content/ready-now.md — every backlog trigger checked against the
metrics.

    python -m content.ready_now

Reads `content/backlog.yaml`, finds the entry carrying a `metrics_file` key,
reads that file (`data/metrics.yaml`), evaluates every live entry's trigger,
and writes `content/ready-now.md`: what can run today, what is waiting and on
what.

Trigger kinds, as the backlog header defines them:

    none       evergreen — always ready
    date       ready from `from`, until `to` if given
    milestone  ready when the named metric reaches `value`
    event      ready once `events[name]` carries a date

Entries whose status is `published` or `dropped` are left out: the backlog
keeps them as a record, but they are not work that can run.

The list is date-dependent, so it goes stale on its own. `--check` re-derives
it and exits 1 if the file on disk is out of date, without writing.

Needs PyYAML. Nothing here is published text — it is an index of the backlog.
"""
import argparse
import sys
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
BACKLOG = ROOT / "content" / "backlog.yaml"
OUT = ROOT / "content" / "ready-now.md"

LIVE_STATUSES = ("idea", "drafted", "scheduled")
TYPE_ORDER = ("campaign", "series", "post", "note")

# The standing rules the backlog keeps at its foot, repeated here so the list a
# person actually works from carries them.
RULES = [
    "Two notes a day. Never link the newsletter in the first note of the day.",
    "Ten minutes replying on other people's notes — that is where profile clicks come from.",
    "Sustainability is an ethic shown in what you do and don't buy, never a topic led with.",
    'A short "what I actually bought" list is the trusted form of affiliate links.',
    "Milestone posts publish at the moment, not months later.",
]


def load(backlog_path=BACKLOG):
    """(entries, metrics, metrics_file) from the backlog and the metrics file
    it names."""
    backlog = yaml.safe_load(backlog_path.read_text())
    if not isinstance(backlog, list):
        raise SystemExit(f"{backlog_path}: expected a YAML list of entries, got {type(backlog).__name__}")
    try:
        metrics_file = next(x["metrics_file"] for x in backlog if isinstance(x, dict) and "metrics_file" in x)
    except StopIteration:
        raise SystemExit(f"{backlog_path}: no entry carries a metrics_file key")
    metrics = yaml.safe_load((ROOT / metrics_file).read_text())
    entries = [x for x in backlog if isinstance(x, dict) and "id" in x]
    return entries, metrics, metrics_file


def check_trigger(trigger, metrics, today):
    """(ready, one line saying why) for one trigger."""
    kind = trigger.get("kind")
    if kind == "none":
        return True, "evergreen"
    if kind == "date":
        start, end = trigger.get("from"), trigger.get("to")
        if end and today > end:
            return False, f"window closed {end}"
        if start and today < start:
            return False, f"opens {start} ({(start - today).days} days)"
        return True, f"window {start} to {end}" if end else f"from {start}"
    if kind == "milestone":
        metric = trigger["metric"]
        have, want = metrics.get(metric, 0), trigger["value"]
        label = metric.replace("_", " ")
        return (have >= want,
                f"{label} {have} ≥ {want}" if have >= want else f"{label} {have} of {want}")
    if kind == "event":
        name = trigger["name"]
        when = (metrics.get("events") or {}).get(name)
        label = name.replace("_", " ")
        return (when is not None, f"{label} on {when}" if when else f"{label} has not happened")
    return False, f"unknown trigger kind {kind!r}"


def render(entries, metrics, metrics_file, today):
    """The markdown for ready-now.md."""
    live = [e for e in entries if e.get("status") in LIVE_STATUSES]
    rows = [(e, *check_trigger(e.get("trigger", {}), metrics, today)) for e in live]
    order = {t: i for i, t in enumerate(TYPE_ORDER)}
    key = lambda r: (order.get(r[0].get("type"), len(TYPE_ORDER)), r[0]["id"])
    ready = sorted((r for r in rows if r[1]), key=key)
    waiting = sorted((r for r in rows if not r[1]), key=key)

    events = metrics.get("events") or {}
    happened = [k.replace("_", " ") for k, v in events.items() if v]
    out = [
        "# Ready now",
        "",
        f"Generated from `content/backlog.yaml` against `{metrics_file}` on {today}. ",
        "Do not edit by hand — change the backlog or the metrics and run `python -m content.ready_now`.",
        "",
        f"**{len(ready)} of {len(live)}** live entries can run today. "
        f"Metrics as of {metrics.get('last_updated')}: {metrics.get('free_subscribers')} free subscribers, "
        f"{metrics.get('paid_subscribers')} paid, {metrics.get('affiliate_orders')} affiliate orders, "
        f"{metrics.get('consultations_completed')} consultations. "
        + ("Events so far: " + ", ".join(happened) + "." if happened else "No milestone events have happened yet."),
        "",
        "## Ready",
        "",
    ]
    for t in TYPE_ORDER:
        group = [r for r in ready if r[0].get("type") == t]
        if not group:
            continue
        out += [f"### {t.title()} ({len(group)})", ""]
        out += [f"- **{e['title']}** — `{e['id']}` · {e['status']} · {why}" for e, _, why in group]
        out.append("")
    if not ready:
        out += ["Nothing can run today. That is a finding, not a failure.", ""]

    out += ["## Waiting", ""]
    if waiting:
        out += ["| Entry | Type | Waiting on |", "|---|---|---|"]
        out += [f"| {e['title']} | {e.get('type')} | {why} |" for e, _, why in waiting]
    else:
        out.append("Nothing is waiting.")
    out += ["", "## The rules that travel with this list", ""]
    out += [f"- {r}" for r in RULES]
    out.append("")
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m content.ready_now",
                                 description="Regenerate content/ready-now.md from the backlog and the metrics.")
    ap.add_argument("--date", default=None, metavar="YYYY-MM-DD",
                    help="evaluate date triggers as at this day (default: today)")
    ap.add_argument("--out", default=None, help=f"write somewhere other than {OUT.relative_to(ROOT)}")
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if the file on disk is out of date; write nothing")
    args = ap.parse_args(argv)

    today = date.fromisoformat(args.date) if args.date else date.today()
    entries, metrics, metrics_file = load()
    text = render(entries, metrics, metrics_file, today)
    out = Path(args.out) if args.out else OUT

    if args.check:
        current = out.read_text() if out.exists() else None
        if current == text:
            print(f"{out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}: up to date ({today})")
            return 0
        print(f"{out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}: OUT OF DATE as at {today} — "
              f"run python -m content.ready_now", file=sys.stderr)
        return 1

    out.write_text(text)
    ready = text.count("\n- **")
    print(f"{out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}: {ready} ready as at {today}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
