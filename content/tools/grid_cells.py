"""Every cell of a shop's listing grid, as a product of its own.

A listing grid is one screenshot holding a dozen products. The cutter took one
garment and the rest were lost. This reads each cell: the photograph, the
caption under it, and a cut-out of the garment.

The detector in build_review_images.py finds the cells whose blob separates
cleanly from the page — usually four of nine. Those four are enough to say
where the lattice is: the column centres, the row centres and the cell pitch
all follow, and the missing cells are the lattice positions that hold content.

Since 24 September this is the FALLBACK. Grid pages are read by eye
(read_grids.py), and a screenshot whose cells were read is left alone here:
its entry in _grid_cells.json carries `source: "eye"` and is never rewritten.

  python3 content/tools/grid_cells.py [--limit N] [--all]

Writes content/catalogue/_grid_cells.json and one JPEG and cut-out per cell into
content/catalogue/review/. Originals are never touched, and the grid's own
review copy is left exactly as it is.
"""
import os, sys, json, re, argparse, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from PIL import Image
import imglib
import flat_lays as FL
from colour_names import classify as colour_classify

try:
    import pytesseract
except ImportError:
    pytesseract = None

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CAT = ROOT + '/content/catalogue'
OUT = CAT + '/review'
DEST = CAT + '/_grid_cells.json'

CAPTION = 0.42           # the caption band under a cell, as a share of its height
INK = 0.05               # a lattice position holds content when this much differs

PRICE = re.compile(r'(?:(CHF|EUR|USD|GBP|€|£|\$)\s*([\d][\d.,\s]{0,10}\d|\d)'
                   r'|([\d][\d.,\s]{0,10}\d|\d)\s*(CHF|EUR|USD|GBP|€|£|\$))', re.I)
LABELS = ('regular fit', 'relaxed fit', 'oversized fit', 'slim fit', 'bestseller',
          'neuheit', 'neu', 'new', 'sale', 'nachhaltiger', 'conscious', 'limited')
SECTIONS = ('jacket', 'coat', 'parka', 'blazer', 'cardigan', 'knitwear', 'jumper',
            'shirt', 'blouse', 't-shirt', 'tops', 'top', 'tee', 'sweater', 'sweatshirt',
            'trouser', 'jeans', 'skirt', 'short', 'dress', 'bag', 'handbag', 'shoe',
            'boot', 'loafer', 'sandal', 'scarf', 'belt', 'accessor', 'hose', 'rock',
            'kleid', 'jacke', 'mantel', 'tasche', 'schuhe')
SLOT_WORDS = [
    ('layer', ('jacket', 'coat', 'parka', 'blazer', 'cardigan', 'gilet', 'vest',
               'jacke', 'mantel', 'blouson', 'anorak', 'overshirt')),
    ('top', ('shirt', 'blouse', 't-shirt', 'tee', 'top', 'sweater', 'jumper', 'knit',
             'sweatshirt', 'polo', 'hemd', 'pullover', 'strick')),
    ('bottom', ('trouser', 'jeans', 'skirt', 'short', 'pant', 'hose', 'rock', 'chino')),
    ('dress', ('dress', 'kleid', 'jumpsuit')),
    ('bag', ('bag', 'tote', 'clutch', 'handbag', 'tasche', 'shopper')),
    ('shoes', ('shoe', 'boot', 'loafer', 'sandal', 'mule', 'sneaker', 'schuh', 'pump')),
    ('accessory', ('scarf', 'belt', 'hat', 'glove', 'sock', 'schal', 'gürtel', 'cap')),
    ('base', ('bra', 'brief', 'slip', 'camisole', 'vest top')),
]


def lattice(cells, W, H):
    """Fill the grid in from the cells that were found.

    Column and row centres come from the cells themselves; a position joins the
    grid when a cell-sized crop there is not simply backdrop. Only ever adds to
    what the detector found, and only inside the page.
    """
    if len(cells) < 3:
        return list(cells)
    mw = sorted(c[2] for c in cells)[len(cells) // 2]
    mh = sorted(c[3] for c in cells)[len(cells) // 2]

    def centres(vals, tol):
        out = []
        for v in sorted(vals):
            if out and abs(v - out[-1][-1]) <= tol:
                out[-1].append(v)
            else:
                out.append([v])
        return [sum(g) / len(g) for g in out]
    cx = centres([c[0] + c[2] / 2 for c in cells], mw * 0.45)
    cy = centres([c[1] + c[3] / 2 for c in cells], mh * 0.45)
    if len(cx) < 2 or len(cy) < 2:
        return list(cells)
    # extend each axis by its own pitch, so a missing outer column comes back
    def extend(cs, pitch, hi):
        if len(cs) < 2:
            return cs
        gaps = sorted(cs[i + 1] - cs[i] for i in range(len(cs) - 1))
        step = gaps[len(gaps) // 2]
        if step <= pitch * 0.5:
            return cs
        out = list(cs)
        while out[0] - step > pitch * 0.45:
            out.insert(0, out[0] - step)
        while out[-1] + step < hi - pitch * 0.45:
            out.append(out[-1] + step)
        return out
    cx = extend(cx, mw, 1.0)
    cy = extend(cy, mh, 1.0)
    have = {(round((c[0] + c[2] / 2) / (mw * 0.5)), round((c[1] + c[3] / 2) / (mh * 0.5)))
            for c in cells}
    out = list(cells)
    for y in cy:
        for x in cx:
            key = (round(x / (mw * 0.5)), round(y / (mh * 0.5)))
            if key in have:
                continue
            bx, by = x - mw / 2, y - mh / 2
            if bx < -0.01 or by < -0.01 or bx + mw > 1.01 or by + mh > 1.01:
                continue
            out.append([round(max(0.0, bx), 4), round(max(0.0, by), 4),
                        round(min(mw, 1 - bx), 4), round(min(mh, 1 - by), 4)])
            have.add(key)
    return sorted(out, key=lambda c: (round(c[1] / (mh * 0.5)), c[0]))


def has_content(im, box):
    """Is there anything but backdrop in this lattice position?"""
    W, H = im.size
    x, y, w, h = box
    crop = im.crop((int(x * W), int(y * H), int((x + w) * W), int((y + h) * H)))
    if min(crop.size) < 30:
        return False
    s = crop.convert('L').resize((48, 48), Image.BILINEAR)
    px = sorted(s.getdata())
    return (px[-3] - px[2]) > 28


def caption_text(im, box, W, H):
    """OCR of the band under a cell, where the shop writes what it is."""
    if pytesseract is None:
        return []
    x, y, w, h = box
    y0 = int((y + h) * H)
    y1 = min(H, int((y + h + h * CAPTION) * H))
    if y1 - y0 < 12:
        return []
    # some shops print the caption under the photograph, some inside the card
    # the detector drew round it: read both and keep whatever comes back
    lines = []
    for box in ((max(0, int(x * W) - 4), y0, min(W, int((x + w) * W) + 4), y1),
                (int(x * W), int((y + h * 0.72) * H), int((x + w) * W), int((y + h) * H))):
        if box[3] - box[1] < 12 or box[2] - box[0] < 20:
            continue
        band = im.crop(box)
        band = band.resize((band.width * 2, band.height * 2), Image.LANCZOS)
        try:
            raw = pytesseract.image_to_string(band)
        except Exception:
            continue
        lines += [ln.strip() for ln in raw.splitlines() if len(ln.strip()) >= 2]
    seen, out = set(), []
    for ln in lines:
        if ln.lower() not in seen:
            seen.add(ln.lower())
            out.append(ln)
    return out


def read_caption(lines):
    """-> {name, category, price, currency, label} from a cell's caption."""
    out = {'name': '', 'category': '', 'price': '', 'currency': '', 'label': ''}
    rest = []
    for ln in lines:
        low = ln.lower()
        m = PRICE.search(ln)
        if m and not out['price']:
            cur = (m.group(1) or m.group(4) or '').upper()
            num = (m.group(2) or m.group(3) or '').strip()
            num = re.sub(r'\s+', '', num)
            if re.search(r'\d', num):
                out['currency'] = {'€': 'EUR', '£': 'GBP', '$': 'USD'}.get(cur, cur)
                out['price'] = num
                if len(ln) < len(num) + 8:
                    continue
        hit = [l for l in LABELS if l in low]
        if hit and len(ln) <= 26:
            out['label'] = ln.strip()
            continue
        rest.append(ln)
    # the name is the longest line left; the category is a SHORTER line that
    # names a section. One line that does both is a name, not a category —
    # "SHIRT CRISTAL TENDON NERO" is what the thing is called.
    rest = [ln for ln in rest if len(ln) >= 3]
    if rest:
        out['name'] = max(rest, key=len).strip()
        for ln in rest:
            low = ln.lower()
            if ln != out['name'] and any(s in low for s in SECTIONS) and len(ln) <= 34:
                out['category'] = ln.strip()
                break
    return out


def slot_from(text):
    """The slot a caption names, or '' when it does not name one."""
    low = (text or '').lower()
    for slot, words in SLOT_WORDS:
        if any(w in low for w in words):
            return slot
    return ''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--redo', action='store_true',
                    help='cut every grid again, including reviewed ones')
    ap.add_argument('--all', dest='redo', action='store_true', help='same as --redo')
    args = ap.parse_args()
    import csv
    review = json.load(open(CAT + '/_review_boxes.json'))
    rows = {r['product_id']: r for r in csv.DictReader(open(CAT + '/products.csv'))}
    try:
        out = json.load(open(DEST))
    except (FileNotFoundError, json.JSONDecodeError):
        out = {}
    # a full run redoes the geometric cells only: a page read by eye
    # (read_grids.py) keeps what the reader saw
    if args.redo:
        out = {k: v for k, v in out.items() if v.get('source') == 'eye'}
    # a page the viewing pass typed as a listing grid but where the strict
    # detector found no cells gets the relaxed one — for new or changed
    # products only (incremental.py), so no reviewed grid grows new cells
    import incremental as INC
    import build_review_images as BR
    grids = [pid for pid in sorted(review) if rows.get(pid, {}).get('shot_type') == 'listing grid']
    fresh, fp = INC.select('grid_cells', grids, args.redo)
    relaxed = 0
    for pid in fresh:
        for e in review[pid].get('images') or []:
            if e and 'error' not in e and not e.get('suggested') and os.path.exists(f"{CAT}/{e['path']}"):
                with Image.open(f"{CAT}/{e['path']}") as f:
                    e['suggested'] = BR.grid_cells(f, min_cells=2, strict=False)
                if e['suggested']:
                    e['suggested_by'] = 'relaxed: typed a listing grid by the viewing pass'
                    relaxed += 1
    if relaxed:
        json.dump(review, open(CAT + '/_review_boxes.json', 'w'), indent=1)
    print('grid screenshots given cells by the relaxed detector:', relaxed)
    jobs = []
    for pid, rec in sorted(review.items()):
        if rows.get(pid, {}).get('shot_type') != 'listing grid':
            continue
        for i, e in enumerate(rec.get('images') or []):
            if e and e.get('suggested') and f'{pid}#{i}' not in out:
                jobs.append((pid, i, e))     # keys read by eye are in `out` already
    if args.limit:
        jobs = jobs[:args.limit]
    print(f'{len(jobs)} grids to cut, {len(out)} already done', flush=True)
    for k, (pid, i, e) in enumerate(jobs, 1):
        key = f'{pid}#{i}'
        src = f"{CAT}/{e['path']}"
        if not os.path.exists(src):
            out[key] = {'cells': [], 'why': 'no review copy'}
            continue
        with Image.open(src) as f:
            im = f.convert('RGB')
        W, H = im.size
        found = [list(c) for c in e['suggested']]
        boxes = [b for b in lattice(found, W, H) if has_content(im, b)]
        stem = os.path.basename(e['path'])[:-4]
        cells = []
        for j, b in enumerate(boxes):
            x0, y0 = int(b[0] * W), int(b[1] * H)
            x1, y1 = int((b[0] + b[2]) * W), int((b[1] + b[3]) * H)
            crop = im.crop((x0, y0, x1, y1))
            if min(crop.size) < 60:
                continue
            cap = read_caption(caption_text(im, b, W, H))
            cut, painted = None, 0
            try:
                _p, _l, _s, _sp, col = FL.plain_backdrop(crop)
                first = FL.raw_cut(crop)
                mask = first.getchannel('A').resize(crop.size, Image.NEAREST)
                painted_im, painted = FL.paint_out(crop, FL.word_boxes(crop), col, keep=mask)
                cut = FL.raw_cut(painted_im) if painted else first
            except Exception:
                cut = None
            name = f'{stem}c{j}.jpg'
            crop.save(f'{OUT}/{name}', 'JPEG', quality=86, optimize=True)
            rec = {'box': [round(v, 4) for v in b], 'path': f'review/{name}',
                   'w': crop.width, 'h': crop.height, 'inferred': list(b) not in
                   [list(c) for c in found], 'badges_painted': painted, **cap}
            if cut is not None and cut.getbbox():
                bb = cut.getbbox()
                cut.crop(bb).save(f'{OUT}/{stem}c{j}-cut.webp', 'WEBP', quality=90, method=5)
                rec['cut'] = f'review/{stem}c{j}-cut.webp'
                rec['cut_skin'] = round(FL.cutout_skin(cut), 4)
            rec['slot'] = slot_from(' '.join([cap.get('category', ''), cap.get('name', '')]))
            cells.append(rec)
        out[key] = {'cells': cells, 'found': len(found), 'lattice': len(boxes)}
        if k % 5 == 0 or k == len(jobs):
            json.dump(out, open(DEST, 'w'), indent=1)
            print(f'  {k}/{len(jobs)}', flush=True)
    json.dump(out, open(DEST, 'w'), indent=1)
    if not args.limit:
        INC.mark('grid_cells', fresh, fp)
    cells = [c for v in out.values() for c in v.get('cells', [])]
    print(f'grids: {len(out)}; cells: {len(cells)} '
          f'({sum(1 for c in cells if c.get("inferred"))} filled in from the lattice)')
    print('with a name:', sum(1 for c in cells if c.get('name')),
          '| with a price:', sum(1 for c in cells if c.get('price')),
          '| with a category:', sum(1 for c in cells if c.get('category')),
          '| with a slot:', sum(1 for c in cells if c.get('slot')),
          '| with a cut-out:', sum(1 for c in cells if c.get('cut')))


if __name__ == '__main__':
    main()
