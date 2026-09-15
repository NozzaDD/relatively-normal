"""Command-line entry point.

    python -m engine.run --season soft_autumn --direction teal_ochre \\
        --items engine/examples/nora-items.yaml --out result.html

The items file is a YAML list; each entry has `name`, `hex`, `slot` and an
optional `near_face` (accessories) and `share`. Optional flags carry the two
intake inputs the result screen also uses: `--mood` (the answer to question 2)
and `--confidence temperature=medium,value=high,chroma=high` (needed for the
runner-up season). `--json` also writes the raw result.
"""
import argparse
import json
import sys

import yaml

from . import horizons, render


def load_items(path):
    with open(path) as fh:
        raw = yaml.safe_load(fh)
    if not isinstance(raw, list):
        raise SystemExit(f"{path}: expected a YAML list of items")
    items = []
    for i, row in enumerate(raw):
        for key in ("name", "hex", "slot"):
            if key not in row:
                raise SystemExit(f"{path}: item {i} is missing {key!r}")
        item = {"id": row["name"], "hex": str(row["hex"]), "slot": row["slot"]}
        if "near_face" in row:
            item["near_face"] = bool(row["near_face"])
        if "share" in row:
            item["share"] = float(row["share"])
        items.append(item)
    return items


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
    ap.add_argument("--items", required=True, help="YAML list of items: name, hex, slot, optional near_face")
    ap.add_argument("--out", required=True, help="path of the HTML file to write")
    ap.add_argument("--mood", default=None, help="answer to intake question 2 (free text)")
    ap.add_argument("--confidence", default=None,
                    help="per-axis confidence, e.g. temperature=medium,value=high,chroma=high")
    ap.add_argument("--json", default=None, help="also write the raw result JSON here")
    args = ap.parse_args(argv)

    items = load_items(args.items)
    result = horizons.result(args.season, args.direction, items,
                             mood=args.mood, confidence=parse_confidence(args.confidence))
    render.render_file(result, args.out)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=1)
    print(args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
