"""Photo intake — a folder of garment photos to an items CSV, so nobody types
a hex.

For each image: load it with Pillow; if it has an alpha channel, keep only
pixels with alpha > 200; otherwise estimate the background as the median
colour of the four corner regions and drop every pixel within ΔE 10 of it.
Run matching.md §1 (`matcher.extract_colours`) on what remains and take the
dominant colour as the item's hex. Slot and name come from the filename,
`slot_item-name.jpg` — `top_deep-teal-knit.jpg` is slot `top`, name
"deep teal knit". An unknown slot prefix goes to the warnings, never to a
guess.

Pillow is used for loading only (decode, EXIF orientation, a size cap on
decode). Everything else is the standard library and the engine's own colour
maths.
"""
import csv
import html
import random
from pathlib import Path
from statistics import median

from . import colour
from .matcher import SLOTS, extract_colours

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp"}
ALPHA_MIN = 200            # matching.md §1
BACKGROUND_DE = 10.0       # pixels this close to the estimated background are dropped
CORNER_FRACTION = 0.10     # each corner region is this fraction of width and height
DECODE_MAX = 800           # longest side after decode; colour extraction needs no more
SAMPLE_FOR_FILTER = 40000  # pixels sampled before the per-pixel ΔE filter (pure Python)
CSV_HEADER = ["name", "slot", "hex", "dressiness", "weight", "near_face", "notes"]


# ---------------------------------------------------------------- filenames

def parse_filename(path):
    """`slot_item-name.ext` -> (slot or None, name). The slot is None when the
    prefix is not one of the six slots; the name is still derived."""
    stem = Path(path).stem
    if "_" in stem:
        prefix, rest = stem.split("_", 1)
    else:
        prefix, rest = "", stem
    name = rest.replace("-", " ").replace("_", " ").strip()
    slot = prefix.lower() if prefix.lower() in SLOTS else None
    return slot, name


# ---------------------------------------------------------------- pixels

def load_image(path):
    """Decode with Pillow: EXIF orientation applied, longest side capped at
    DECODE_MAX. Returns (RGBA pixel list, (width, height), has_alpha)."""
    from PIL import Image, ImageOps
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im)
        has_alpha = im.mode in ("RGBA", "LA", "PA") or "transparency" in im.info
        im = im.convert("RGBA")
        im.thumbnail((DECODE_MAX, DECODE_MAX))
        data = im.get_flattened_data() if hasattr(im, "get_flattened_data") else im.getdata()
        return list(data), im.size, has_alpha


def _corner_pixels(pixels, size):
    w, h = size
    cw, ch = max(1, int(w * CORNER_FRACTION)), max(1, int(h * CORNER_FRACTION))
    out = []
    for y0, y1 in ((0, ch), (h - ch, h)):
        for x0, x1 in ((0, cw), (w - cw, w)):
            for y in range(y0, y1):
                row = y * w
                out.extend(pixels[row + x0: row + x1])
    return out


def estimate_background(pixels, size):
    """The median colour of the four corner regions, per channel."""
    corners = _corner_pixels(pixels, size)
    return tuple(int(median(p[i] for p in corners)) for i in range(3))


def foreground(pixels, size, has_alpha, seed=0):
    """The pixels that belong to the garment. Alpha channel: alpha > ALPHA_MIN.
    Otherwise: everything further than BACKGROUND_DE from the corner-median
    background. Returns (RGBA pixels, background hex or None)."""
    if has_alpha:
        return [p for p in pixels if p[3] > ALPHA_MIN], None
    bg = estimate_background(pixels, size)
    bg_lab = colour.srgb_to_lab(bg)
    rng = random.Random(seed)
    sample = rng.sample(pixels, SAMPLE_FOR_FILTER) if len(pixels) > SAMPLE_FOR_FILTER else pixels
    kept = [(p[0], p[1], p[2], 255) for p in sample
            if colour.delta_e_2000(colour.srgb_to_lab(p[:3]), bg_lab) > BACKGROUND_DE]
    return kept, colour.rgb_to_hex(bg)


# ---------------------------------------------------------------- one image

def extract_item(path):
    """One photo -> {"file", "slot", "name", "hex", "share", "mode",
    "background", "pixels_used", "colours", "warnings"}."""
    path = Path(path)
    slot, name = parse_filename(path)
    warnings = []
    if slot is None:
        warnings.append(f"{path.name}: slot not recognised from the filename prefix "
                        f"(expected one of {', '.join(SLOTS)}); fill the slot column by hand")
    pixels, size, has_alpha = load_image(path)
    fg, bg_hex = foreground(pixels, size, has_alpha)
    colours = extract_colours(fg) if fg else []
    if not colours:
        warnings.append(f"{path.name}: no garment pixels found after removing the background")
    dominant = colours[0] if colours else None
    return {"file": path.name, "slot": slot, "name": name,
            "hex": dominant["hex"] if dominant else None,
            "share": round(dominant["share"], 3) if dominant else None,
            "mode": "alpha" if has_alpha else "background",
            "background": bg_hex, "pixels_used": len(fg),
            "colours": [{"hex": c["hex"], "share": round(c["share"], 3)} for c in colours],
            "warnings": warnings}


# ---------------------------------------------------------------- the folder

def run_folder(folder, csv_path=None, sheet_path=None):
    """Every image in `folder` -> items.csv and a contact sheet. Rows keep
    name, slot and hex; dressiness, weight, near_face and notes are left for
    the person. A row whose slot could not be read has a blank slot and a
    note, and appears in the warnings. Returns {"items", "warnings", "csv",
    "sheet"}."""
    folder = Path(folder)
    files = sorted(p for p in folder.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES)
    items, warnings = [], []
    for p in files:
        item = extract_item(p)
        items.append(item)
        warnings.extend(item["warnings"])
    csv_path = Path(csv_path) if csv_path else folder / "items.csv"
    sheet_path = Path(sheet_path) if sheet_path else folder / "contact-sheet.html"
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(CSV_HEADER)
        for it in items:
            note = "" if it["slot"] else "slot not recognised from filename — fill in"
            w.writerow([it["name"], it["slot"] or "", it["hex"] or "", "", "", "", note])
    sheet_path.write_text(contact_sheet(items, folder), encoding="utf-8")
    return {"items": items, "warnings": warnings, "csv": str(csv_path), "sheet": str(sheet_path)}


def contact_sheet(items, folder):
    """Each photo beside its extracted swatch and hex, so the extraction can
    be checked by eye. Photos are referenced by relative path; the sheet is
    written into the photo folder."""
    e = lambda v: html.escape("" if v is None else str(v))
    cards = []
    for it in items:
        sw = (f'<div class="sw" style="background:#{e(it["hex"])}"></div>' if it["hex"]
              else '<div class="sw none">no colour</div>')
        others = " ".join(f'<span class="mini" style="background:#{e(c["hex"])}" title="{e(c["hex"])} · {c["share"]}"></span>'
                          for c in it["colours"][1:])
        warn = "".join(f'<div class="warn">{e(w)}</div>' for w in it["warnings"])
        bg = f' · background {e(it["background"])}' if it["background"] else ""
        cards.append(
            f'<div class="card"><img src="{e(it["file"])}" alt="{e(it["file"])}">'
            f'<div class="side">{sw}<div class="hex">{e(it["hex"] or "—")}</div>'
            f'<div class="meta"><b>{e(it["name"])}</b><br>{e(it["slot"] or "slot?")} · {e(it["file"])}<br>'
            f'{e(it["mode"])}{bg} · {it["pixels_used"]} px · share {e(it["share"])}</div>'
            f'<div>{others}</div>{warn}</div></div>')
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Contact sheet · {e(Path(folder).name)}</title>
<style>
body{{margin:0;padding:20px;background:#faf8f4;color:#1f1d1a;font:14px/1.4 -apple-system,Helvetica,Arial,sans-serif}}
h1{{font-size:18px;margin:0 0 14px}} .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px}}
.card{{display:flex;gap:12px;background:#fff;border:1px solid #dcd6cc;border-radius:10px;padding:10px}}
.card img{{width:130px;height:130px;object-fit:contain;background:repeating-conic-gradient(#eee 0 25%,#fff 0 50%) 0 0/16px 16px;border-radius:6px}}
.side{{flex:1;min-width:0}} .sw{{height:56px;border-radius:6px;border:1px solid rgba(0,0,0,.12)}}
.sw.none{{display:flex;align-items:center;justify-content:center;color:#a33a2f;font-size:12px}}
.hex{{font-family:ui-monospace,Menlo,monospace;font-size:15px;margin:4px 0}} .meta{{font-size:12px;color:#6b665e}}
.mini{{display:inline-block;width:16px;height:16px;border-radius:3px;border:1px solid rgba(0,0,0,.12);margin:4px 3px 0 0}}
.warn{{color:#a33a2f;font-size:12px;margin-top:4px}}
</style></head><body><h1>Contact sheet — check each swatch against its photo</h1>
<div class="grid">{"".join(cards)}</div></body></html>
"""


if __name__ == "__main__":  # python -m engine.intake path/to/folder
    import sys
    out = run_folder(sys.argv[1])
    print(out["csv"]); print(out["sheet"])
    for w in out["warnings"]:
        print("warning:", w, file=sys.stderr)
