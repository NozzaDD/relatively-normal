"""Command-line entry point.

    python -m engine.run --season soft_autumn --direction teal_ochre \\
        --items engine/examples/nora-items.csv --outfits engine/examples/nora-outfits.csv \\
        --out result.html

`--photos folder` runs the photo intake first (engine/intake.py) and uses the
items.csv it writes into that folder; `--items` takes a CSV that already
exists. One of the two is required.

`--items` reads either the CSV in templates/items.csv (name, slot, hex,
dressiness, weight, near_face, notes) or a YAML list (name, hex, slot,
optional near_face, dressiness, weight, share). `--outfits` reads the CSV in
templates/outfits.csv (outfit, occasion, dress_code, weather, formality,
setting, then one column per slot holding an item name or blank; formality
defaults to casual and setting to office when blank). Optional flags carry the two intake
inputs the result screen also uses: `--mood` (the answer to question 2) and
`--confidence temperature=medium,value=high,chroma=high` (needed for the
runner-up season). `--json` also writes the raw result.
"""
import argparse
import csv
import json
import sys
from pathlib import Path

import yaml

from . import horizons, render
from .matcher import FIBRES, SLOTS, SURFACES


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
    for key in ("fibre", "surface"):
        v = (row.get(key) or "").strip().lower()
        if v:
            allowed = FIBRES if key == "fibre" else SURFACES
            if v not in allowed:
                raise SystemExit(f"{where}: item {name!r} {key} must be one of {', '.join(allowed)}, got {v!r}")
            item[key] = v
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
        lw = _int_or_none(row.get("life_weight"), "life_weight", where)
        if lw is not None and not 1 <= lw <= 10:
            raise SystemExit(f"{where}: life_weight must be 1-10, got {lw}")
        weather = (row.get("weather") or "").strip().lower() or None
        if weather not in (None, "clear", "rain"):
            raise SystemExit(f"{where}: weather must be clear or rain, got {weather!r}")
        formality = (row.get("formality") or "").strip().lower() or "casual"
        if formality not in ("corporate", "casual"):
            raise SystemExit(f"{where}: formality must be corporate or casual, got {formality!r}")
        setting = (row.get("setting") or "").strip().lower() or "office"
        if setting not in ("office", "home"):
            raise SystemExit(f"{where}: setting must be office or home, got {setting!r}")
        slots = {}
        for s in SLOTS:
            v = (row.get(s) or "").strip()
            if v and v not in known:
                raise SystemExit(f"{where}: {s} names {v!r}, which is not in the items file")
            slots[s] = v or None
        outfits.append({"name": name, "occasion": (row.get("occasion") or "").strip() or None,
                        "dress_code": dc, "weather": weather, "formality": formality, "setting": setting,
                        "life_weight": lw, "slots": slots})
    return outfits


def load_intake(path):
    """The intake file (templates/intake.yaml): the three colour questions, the
    axis confidences and the material preferences. Every part is optional."""
    raw = yaml.safe_load(Path(path).read_text()) or {}
    if not isinstance(raw, dict):
        raise SystemExit(f"{path}: expected a YAML mapping")
    conf = raw.get("confidence") or None
    if conf:
        missing = {"temperature", "value", "chroma"} - set(conf)
        if missing:
            raise SystemExit(f"{path}: confidence needs all three axes; missing {sorted(missing)}")
    materials = raw.get("materials") or {}
    for key in ("loves", "avoids"):
        for f in materials.get(key) or []:
            if f not in FIBRES:
                raise SystemExit(f"{path}: materials {key} has {f!r}, not one of {', '.join(FIBRES)}")
    return {"questions": raw.get("questions") or {}, "confidence": conf, "materials": materials}


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
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--items", help="items file: templates/items.csv format, or a YAML list")
    src.add_argument("--photos", help="folder of garment photos; intake writes items.csv there first")
    ap.add_argument("--outfits", default=None, help="saved outfits: templates/outfits.csv format")
    ap.add_argument("--intake", default=None,
                    help="intake file: templates/intake.yaml format (questions, confidence, materials)")
    ap.add_argument("--out", required=True, help="path of the HTML file to write")
    ap.add_argument("--mood", default=None, help="answer to intake question 2 (free text)")
    ap.add_argument("--confidence", default=None,
                    help="per-axis confidence, e.g. temperature=medium,value=high,chroma=high")
    ap.add_argument("--json", default=None, help="also write the raw result JSON here")
    args = ap.parse_args(argv)

    items_path = args.items
    if args.photos:
        from . import intake
        out = intake.run_folder(args.photos)
        for w in out["warnings"]:
            print("warning:", w, file=sys.stderr)
        print(f"intake: {out['csv']} and {out['sheet']}", file=sys.stderr)
        items_path = out["csv"]
    items = load_items(items_path)
    outfits = load_outfits(args.outfits, items) if args.outfits else None
    intake_data = load_intake(args.intake) if args.intake else None
    mood, confidence = args.mood, parse_confidence(args.confidence)
    if intake_data:
        # a flag wins over the file, so one run can override a stored answer
        mood = mood or (intake_data["questions"] or {}).get("wants_to_feel")
        confidence = confidence or intake_data["confidence"]
    result = horizons.result(args.season, args.direction, items, outfits=outfits,
                             mood=mood, confidence=confidence,
                             materials=(intake_data or {}).get("materials"))
    render.render_file(result, args.out)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=1)
    print(args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
