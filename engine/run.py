"""Command-line entry point.

    python -m engine.run --season soft_autumn --direction teal_ochre \\
        --items engine/examples/nora-items.csv --outfits engine/examples/nora-outfits.csv \\
        --out result.html

`--items` reads either the CSV in templates/items.csv (name, slot, hex,
dressiness, weight, near_face, notes) or a YAML list (name, hex, slot,
optional near_face, dressiness, weight, share). `--outfits` reads the CSV in
templates/outfits.csv (outfit, occasion, dress_code, weather, then one column
per slot holding an item name or blank). Optional flags carry the two intake
inputs the result screen also uses: `--mood` (the answer to question 2) and
`--confidence temperature=medium,value=high,chroma=high` (needed for the
runner-up season). `--json` also writes the raw result.
"""
import argparse
import csv
import json
import sys

import yaml

from . import horizons, render
from .matcher import SLOTS


def _int_or_none(v, what, where):
    if v is None or str(v).strip() == "":
        return None
    try:
        return int(str(v).strip())
    except ValueError:
        raise SystemExit(f"{where}: {what} must be a whole number, got {v!r}")


def _item_from_row(row, where):
    name = (row.get("name") or "").strip()
    item = {"id": name, "hex": str(row["hex"]).strip().lstrip("#"), "slot": str(row["slot"]).strip()}
    if item["slot"] not in SLOTS:
        raise SystemExit(f"{where}: item {name!r} has unknown slot {item['slot']!r}; expected one of {', '.join(SLOTS)}")
    if len(item["hex"]) != 6:
        raise SystemExit(f"{where}: item {name!r} needs a six-character hex, got {row['hex']!r}")
    nf = row.get("near_face")
    if nf is not None and str(nf).strip() != "":
        item["near_face"] = str(nf).strip().lower() in ("true", "1", "yes")
    for key in ("dressiness", "weight"):
        v = _int_or_none(row.get(key), key, f"{where}, item {name!r}")
        if v is not None:
            if not 1 <= v <= 4:
                raise SystemExit(f"{where}: item {name!r} {key} must be 1-4, got {v}")
            item[key] = v
    if row.get("share") not in (None, ""):
        item["share"] = float(row["share"])
    return item


def load_items(path):
    """The closet, from templates/items.csv format or a YAML list. Rows with a
    blank name (the template's hint rows) are skipped."""
    if str(path).lower().endswith(".csv"):
        with open(path, newline="", encoding="utf-8-sig") as fh:
            rows = list(csv.DictReader(fh))
    else:
        with open(path) as fh:
            rows = yaml.safe_load(fh)
        if not isinstance(rows, list):
            raise SystemExit(f"{path}: expected a YAML list of items")
    items = []
    for i, row in enumerate(rows):
        if not (row.get("name") or "").strip():
            continue
        for key in ("hex", "slot"):
            if row.get(key) in (None, ""):
                raise SystemExit(f"{path}: item {i} ({row.get('name')!r}) is missing {key!r}")
        items.append(_item_from_row(row, path))
    return items


def load_outfits(path, items):
    """Saved outfits from templates/outfits.csv format. Every named item must
    exist in the items file."""
    known = {i["id"] for i in items}
    with open(path, newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    outfits = []
    for i, row in enumerate(rows):
        name = (row.get("outfit") or "").strip()
        if not name:
            continue
        where = f"{path}, outfit {name!r}"
        dc = _int_or_none(row.get("dress_code"), "dress_code", where)
        if dc is not None and not 1 <= dc <= 5:
            raise SystemExit(f"{where}: dress_code must be 1-5, got {dc}")
        weather = (row.get("weather") or "").strip().lower() or None
        if weather not in (None, "clear", "rain"):
            raise SystemExit(f"{where}: weather must be clear or rain, got {weather!r}")
        slots = {}
        for s in SLOTS:
            v = (row.get(s) or "").strip()
            if v and v not in known:
                raise SystemExit(f"{where}: {s} names {v!r}, which is not in the items file")
            slots[s] = v or None
        outfits.append({"name": name, "occasion": (row.get("occasion") or "").strip() or None,
                        "dress_code": dc, "weather": weather, "slots": slots})
    return outfits


def parse_confidence(text):
    if not text:
        return None
    out = {}
    for part in text.split(","):
        axis, _, level = part.partition("=")
        out[axis.strip()] = level.strip()
    missing = {"temperature", "value", "chroma"} - set(out)
    if missing:
        raise SystemExit(f"--confidence needs all three axes; missing {sorted(missing)}")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m engine.run", description="Render the result screen for one person.")
    ap.add_argument("--season", required=True, help="season key from seasons.yaml, e.g. soft_autumn")
    ap.add_argument("--direction", required=True, help="direction key within the season, e.g. teal_ochre")
    ap.add_argument("--items", required=True, help="items file: templates/items.csv format, or a YAML list")
    ap.add_argument("--outfits", default=None, help="saved outfits: templates/outfits.csv format")
    ap.add_argument("--out", required=True, help="path of the HTML file to write")
    ap.add_argument("--mood", default=None, help="answer to intake question 2 (free text)")
    ap.add_argument("--confidence", default=None,
                    help="per-axis confidence, e.g. temperature=medium,value=high,chroma=high")
    ap.add_argument("--json", default=None, help="also write the raw result JSON here")
    args = ap.parse_args(argv)

    items = load_items(args.items)
    outfits = load_outfits(args.outfits, items) if args.outfits else None
    result = horizons.result(args.season, args.direction, items, outfits=outfits,
                             mood=args.mood, confidence=parse_confidence(args.confidence))
    render.render_file(result, args.out)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=1)
    print(args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
