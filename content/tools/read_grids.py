"""Listing-grid cells read by eye, then tidied and cut.

The geometric cell detector kept failing on easy pages — a page of four tiles
on a white ground gave no cells at all — so the cells are now READ: a reader
opens every grid screenshot with a pixel ruler drawn round it and writes down,
per product tile, the rectangle of the photograph and the caption's text
(name, price with currency, colour where the caption states one, what the
garment is). Geometry is used only afterwards, to snap each rectangle to the
garment's own bounds so the box holds the photo and not the caption.

  python3 content/tools/read_grids.py --render OUTDIR   # ruled pages for the readers
  python3 content/tools/read_grids.py --ingest EYEDIR   # merge the readers' JSON, tidy, cut, measure

The readers' files are one JSON per grid screenshot (see PROMPT in the run
notes); --ingest writes them into content/catalogue/_grid_cells.json under the
same keys the geometric pass used (`{pid}#{image index}`), marked
`source: "eye"`, cuts one JPEG and one cut-out per cell into review/, and
measures every cut-out the way flat_lays.py does — one piece, clear of the
frame, no text inside it, nobody wearing it — writing the verdict into
_flat_lays.json under the cell's product ID, which is what the shelf gate
reads. A clean single garment goes to the shelf; anything else waits in
Review under its grid.

A cell the owner has already decided on (a choice for its ID in
asset-choices.json) is never replaced: its geometric record is kept as it is,
and the eye's version of that tile is dropped. The geometric record of every
key that was replaced is kept in _grid_cells_geometry.json for comparison.
"""
from shelf_checks import is_swatch_row   # a swatch row is not a grid
import os, sys, re, json, csv, argparse, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import flat_lays as FL
import grid_cells as G

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CAT = ROOT + '/content/catalogue'
OUT = CAT + '/review'
DEST = CAT + '/_grid_cells.json'
GEOM = CAT + '/_grid_cells_geometry.json'
FLATS = CAT + '/_flat_lays.json'
MARGIN = 40

GARMENT_SLOT = [
    ('shoes', ('loafer', 'boot', 'sneaker', 'pump', 'mule', 'sandal', 'flat', 'slipper', 'clog',
               'moccasin', 'shoe', 'slide', 'heel', 'derby', 'oxford', 'trainer', 'espadrille')),
    ('bag', ('bag', 'tote', 'clutch', 'pouch', 'backpack', 'shopper', 'satchel', 'basket')),
    ('layer', ('coat', 'jacket', 'blazer', 'cardigan', 'parka', 'gilet', 'vest', 'trench',
               'overshirt', 'blouson', 'anorak', 'hoodie')),
    ('bottom', ('trouser', 'jeans', 'skirt', 'short', 'pant', 'chino', 'culotte', 'legging')),
    ('dress', ('dress', 'jumpsuit', 'gown')),
    ('accessory', ('scarf', 'hat', 'beanie', 'belt', 'glove', 'sock', 'bandana', 'cap',
                   'balaclava', 'sunglasses', 'wallet', 'jewel', 'necklace', 'earring')),
    ('top', ('jumper', 'sweater', 'knit', 'shirt', 'blouse', 't-shirt', 'tee', 'top', 'polo',
             'sweatshirt', 'turtleneck', 'pullover', 'tank', 'camisole', 'bodysuit')),
    ('base', ('bra', 'brief', 'slip', 'underwear', 'tights')),
]


def slot_of(cell):
    """The slot the reader's garment word names, else the caption's."""
    g = (cell.get('garment') or '').lower()
    for slot, words in GARMENT_SLOT:
        if any(w in g for w in words):
            return slot
    return G.slot_from(' '.join([cell.get('name') or '', g]))


def none(v):
    v = (v or '').strip()
    return '' if v.upper() == 'NONE' else v


# ---------------------------------------------------------------- render ----

def render(outdir):
    """Every grid screenshot's review copy with a pixel ruler drawn round it."""
    rows = {r['product_id']: r for r in csv.DictReader(open(CAT + '/products.csv'))}
    rv = json.load(open(CAT + '/_review_boxes.json'))
    fp = ROOT + '/content/boards/fonts/Inter-SemiBold.ttf'
    font = ImageFont.truetype(fp, 13) if os.path.exists(fp) else ImageFont.load_default()
    os.makedirs(outdir, exist_ok=True)
    pages = []
    for pid, r in sorted(rows.items()):
        if r['shot_type'] != 'listing grid' or is_swatch_row(r):
            continue
        for i, e in enumerate(rv.get(pid, {}).get('images') or []):
            if not e or 'error' in e or not os.path.exists(f"{CAT}/{e['path']}"):
                continue
            im = Image.open(f"{CAT}/{e['path']}").convert('RGB')
            W, H = im.size
            M = MARGIN
            can = Image.new('RGB', (W + 2 * M, H + 2 * M), (235, 235, 235))
            can.paste(im, (M, M))
            d = ImageDraw.Draw(can)
            for x in range(0, W + 1, 50):
                L = 12 if x % 100 == 0 else 6
                d.line([(M + x, M - L), (M + x, M)], fill=(200, 0, 0))
                d.line([(M + x, M + H), (M + x, M + H + L)], fill=(200, 0, 0))
                if x % 100 == 0:
                    d.text((M + x - 10, 2), str(x), fill=(120, 0, 0), font=font)
                    d.text((M + x - 10, M + H + 14), str(x), fill=(120, 0, 0), font=font)
            for y in range(0, H + 1, 50):
                L = 12 if y % 100 == 0 else 6
                d.line([(M - L, M + y), (M, M + y)], fill=(200, 0, 0))
                d.line([(M + W, M + y), (M + W + L, M + y)], fill=(200, 0, 0))
                if y % 100 == 0:
                    d.text((2, M + y - 7), str(y), fill=(120, 0, 0), font=font)
                    d.text((M + W + 14, M + y - 7), str(y), fill=(120, 0, 0), font=font)
            for x in range(100, W, 100):
                d.line([(M + x, M), (M + x, M + H)], fill=(255, 120, 120))
            for y in range(100, H, 100):
                d.line([(M, M + y), (M + W, M + y)], fill=(255, 120, 120))
            key = f'{pid}#{i}'
            can.save(f'{outdir}/{key.replace("#", "_")}.jpg', quality=88)
            pages.append(dict(key=key, pid=pid, i=i, w=W, h=H, shop=r['shop'], review=e['path']))
    json.dump(pages, open(f'{outdir}/pages.json', 'w'), indent=1)
    print(len(pages), 'grid screenshots rendered ->', outdir)


# ------------------------------------------------------------------ tidy ----

def snap(im, box, pad=0.015, margin=0.07):
    """Snap a read rectangle to the garment's own bounds, plus a margin.

    The reader's box is a ruler estimate and may hold a little caption. Inside
    a barely padded copy of it, the rows that differ from the tile's own
    backdrop are found; runs of such rows thinner than a twelfth of the box are
    text lines, swatch dots and rules and are dropped; what remains is the
    photograph, and the box becomes its bounds with a margin round them, so the
    garment sits clear of its own frame the way a packshot does. The pad is
    small on purpose: a wider one reaches the next tile, whose content then
    joins the mask and the box grows instead of tidying. Falls back to the
    reader's box when nothing separates."""
    W, H = im.size
    x0, y0, x1, y1 = box
    pw, ph = (x1 - x0) * pad, (y1 - y0) * pad
    cx0, cy0 = max(0, int(x0 - pw)), max(0, int(y0 - ph))
    cx1, cy1 = min(W, int(x1 + pw)), min(H, int(y1 + ph))
    if cx1 - cx0 < 20 or cy1 - cy0 < 20:
        return box, 'too small'
    crop = im.crop((cx0, cy0, cx1, cy1))
    a = np.asarray(crop.convert('RGB')).astype(int)
    border = np.concatenate([a[0], a[-1], a[:, 0], a[:, -1]])
    bg = np.median(border, axis=0)
    mask = np.abs(a - bg).max(axis=2) > 18
    # a caption is text: OCR finds its words and they leave the mask, so a
    # small pale shoe above a two-line caption is still the photo, not the text
    try:
        for wx, wy, ww, wh, _t in FL.word_boxes(crop, conf=50):
            mask[max(0, wy - 2):wy + wh + 2, max(0, wx - 2):wx + ww + 2] = False
    except Exception:
        pass
    rows = mask.mean(axis=1) > 0.008
    if not rows.any():
        return box, 'nothing but backdrop'
    runs, start = [], None
    for y, v in enumerate(list(rows) + [False]):
        if v and start is None:
            start = y
        elif not v and start is not None:
            runs.append([start, y]); start = None
    # a sole's shadow or a strap is not a caption: join runs a hair apart
    gap = max(3, int(0.012 * (cy1 - cy0)))
    joined = [runs[0]]
    for s_, e_ in runs[1:]:
        if s_ - joined[-1][1] <= gap:
            joined[-1][1] = e_
        else:
            joined.append([s_, e_])
    thin = max(10, (cy1 - cy0) / 12.0)
    photo = [r for r in joined if r[1] - r[0] >= thin]
    if not photo:
        return box, 'only thin lines'
    # the photograph sits above its caption, so the topmost photo-sized run
    # is the picture — unless it is a sliver next to a far heavier run below
    # (a badge, the tail of the row above), in which case the heavy run wins.
    # A pale shoe over a two-line caption OCR could not read is otherwise lost
    # to its own caption.
    mass = [mask[r[0]:r[1]].sum() for r in photo]
    top = 0
    if mass[top] < 0.15 * max(mass):
        top = max(range(len(photo)), key=lambda k: mass[k])
    ys, ye = photo[top]
    # a photo-sized run directly below it with no text between is the same
    # picture (a shadow, a second shoe): join it
    k = top
    while k + 1 < len(photo) and not any(r[1] - r[0] < thin for r in joined
                                         if photo[k][1] <= r[0] and r[1] <= photo[k + 1][0]) \
            and photo[k + 1][0] - photo[k][1] < 0.08 * (cy1 - cy0):
        ye = photo[k + 1][1]; k += 1
    cols = mask[ys:ye].mean(axis=0) > 0.008
    if not cols.any():
        return box, 'nothing but backdrop'
    xs = int(np.argmax(cols)); xe = len(cols) - int(np.argmax(cols[::-1]))
    # the margin never leaves the reader's box: the box was the photo, and
    # past it lie the caption and the next tile
    mw, mh = int((xe - xs) * margin) + 4, int((ye - ys) * margin) + 4
    nb = [max(cx0, cx0 + xs - mw), max(cy0, cy0 + ys - mh), min(cx1, cx0 + xe + mw), min(cy1, cy0 + ye + mh)]
    if nb[2] - nb[0] < 30 or nb[3] - nb[1] < 30:
        return box, 'snapped to nothing'
    return nb, 'snapped'


def cut_cell(im, b, stem, j):
    """One JPEG and one cut-out for a cell; -> (record fields, cut image)."""
    W, H = im.size
    x0, y0 = int(b[0] * W), int(b[1] * H)
    x1, y1 = int((b[0] + b[2]) * W), int((b[1] + b[3]) * H)
    crop = im.crop((x0, y0, x1, y1))
    name = f'{stem}c{j}.jpg'
    crop.save(f'{OUT}/{name}', 'JPEG', quality=86, optimize=True)
    rec = {'path': f'review/{name}', 'w': crop.width, 'h': crop.height, 'badges_painted': 0}
    cut = None
    try:
        _p, _l, _s, _sp, col = FL.plain_backdrop(crop)
        first = FL.raw_cut(crop)
        keep = first.getchannel('A').resize(crop.size, Image.NEAREST)
        painted_im, painted = FL.paint_out(crop, FL.word_boxes(crop), col, keep=keep)
        cut = FL.raw_cut(painted_im) if painted else first
        rec['badges_painted'] = painted
    except Exception as e:
        rec['cut_error'] = f'{type(e).__name__}: {e}'
    if cut is not None and cut.getbbox():
        m = FL.measure(cut)
        cs = round(FL.cutout_skin(cut), 4)
        bb = cut.getbbox()
        ok = (m['components'] == 1 and m['edge_pixels'] == 0 and m['words_inside'] == 0
              and cs <= FL.SKIN_MAX and min(bb[2] - bb[0], bb[3] - bb[1]) >= 60)
        if max(cut.size) > 1400:
            cut.thumbnail((1400, 1400), Image.LANCZOS); bb = cut.getbbox()
        cut.crop(bb).save(f'{OUT}/{stem}c{j}-cut.webp', 'WEBP', quality=90, method=5)
        rec.update(cut=f'review/{stem}c{j}-cut.webp', cut_skin=cs, **m, clean=bool(ok),
                   why='' if ok else ', '.join(filter(None, [
                       'more than one piece' if m['components'] != 1 else '',
                       'touches the frame' if m['edge_pixels'] else '',
                       'text inside it' if m['words_inside'] else '',
                       'someone is wearing it' if cs > FL.SKIN_MAX else '',
                       'too small' if min(bb[2] - bb[0], bb[3] - bb[1]) < 60 else ''])))
    else:
        rec.update(clean=False, why='nothing cut')
    return rec


def decided_cells():
    """Cell IDs the owner has decided on: never replaced."""
    try:
        ch = json.load(open(CAT + '/asset-choices.json')).get('choices', {})
    except (FileNotFoundError, json.JSONDecodeError):
        return set()
    return {pid for pid, c in ch.items() if re.search(r'-C\d+$', pid) and (c.get('choice') or c.get('hidden'))}


def cell_id(pid, idx, j):
    """The product ID a cell gets in build_products.py: every screenshot of a
    grid row numbers its own cells, so two never share an ID."""
    return f'{pid}-C{j}' if idx == 0 else f'{pid}-I{idx}-C{j}'


def original(e, batch, idx):
    """The screenshot the review copy was cut from, cropped the same way, at
    the original's resolution — or None when it is not on this machine."""
    org = e.get('origin')
    imgs = (batch or {}).get('images') or []
    if not org or idx >= len(imgs) or not os.path.exists(ROOT + '/' + imgs[idx]):
        return None
    with Image.open(ROOT + '/' + imgs[idx]) as f:
        if f.size != (org[4], org[5]):
            return None
        return f.convert('RGB').crop(tuple(org[:4]))


def ingest(eyedir):
    rv = json.load(open(CAT + '/_review_boxes.json'))
    batches = {b['product_id']: b for b in json.load(open(CAT + '/batches.json'))}
    try:
        out = json.load(open(DEST))
    except (FileNotFoundError, json.JSONDecodeError):
        out = {}
    try:
        geom = json.load(open(GEOM))
    except (FileNotFoundError, json.JSONDecodeError):
        geom = {}
    try:
        flats = json.load(open(FLATS))
    except (FileNotFoundError, json.JSONDecodeError):
        flats = {}
    decided = decided_cells()
    files = sorted(f for f in os.listdir(eyedir) if f.endswith('.json') and f != 'pages.json')
    print(len(files), 'pages read by eye')
    stats = collections.Counter()
    compare = []
    for k, f in enumerate(files, 1):
        try:
            eye = json.load(open(os.path.join(eyedir, f)))
        except json.JSONDecodeError as e:
            print('  unreadable:', f, e); stats['unreadable files'] += 1
            continue
        key = eye.get('key') or f[:-5].replace('_', '#')
        pid, idx = key.split('#')[0], int(key.split('#')[1])
        e = ((rv.get(pid) or {}).get('images') or [None] * (idx + 1))[idx]
        if not e or 'error' in e or not os.path.exists(f"{CAT}/{e['path']}"):
            stats['no review copy'] += 1
            continue
        old = out.get(key) or {}
        if old.get('source') != 'eye' and old.get('cells') is not None:
            geom[key] = old                      # the geometric pass, kept for comparison
        kept = [c for c in (old.get('cells') or []) if cell_id(pid, idx, (old.get('cells') or []).index(c)) in decided]
        if not eye.get('is_grid', True):
            out[key] = {'cells': kept, 'source': 'eye', 'is_grid': False, 'note': eye.get('note', ''),
                        'skipped_cut_off': 0}
            stats['pages not a grid by eye'] += 1
            continue
        with Image.open(f"{CAT}/{e['path']}") as im0:
            im = im0.convert('RGB')
        W, H = im.size
        stem = os.path.basename(e['path'])[:-4]
        # the cells are cut from the original screenshot, not the review copy:
        # a review copy is at most 1200 px tall, and a shoe on a four-column
        # grid is 70 px there — too small to stand on the shelf. `origin` is
        # the crop the review copy was made from, in the original's pixels.
        hi = original(e, batches.get(pid), idx)
        stats['cut from the original' if hi is not None else 'cut from the review copy'] += 1
        cells = list(kept)
        j0 = len(kept)
        # a reader who measured on the ruled canvas rather than the page is
        # off by the ruler's margin: boxes run past the page's edge
        boxes = [c.get('box') for c in eye.get('cells') or [] if c.get('box') and len(c['box']) == 4]
        off = MARGIN if boxes and max(max(b[2] - W, b[3] - H) for b in boxes) >= MARGIN * 0.5 else 0
        if off:
            stats['pages read in canvas coordinates'] += 1
        for c in eye.get('cells') or []:
            b = c.get('box') or []
            if len(b) != 4:
                stats['cells without a box'] += 1; continue
            b = [v - off for v in b]
            b = [max(0, min(W, float(b[0]))), max(0, min(H, float(b[1]))),
                 max(0, min(W, float(b[2]))), max(0, min(H, float(b[3])))]
            if b[2] - b[0] < 20 or b[3] - b[1] < 20:
                stats['cells too small'] += 1; continue
            nb, how = snap(im, b)
            stats['snapped' if how == 'snapped' else 'box kept as read'] += 1
            # the crop rule: the snap keeps only the topmost photo-sized run
            # and never leaves the reader's box, so a handle above the bag was
            # cut off; widen to the whole piece, measured on the screenshot
            org = e.get('origin')
            if org and batches.get(pid) and idx < len(batches[pid]['images']):
                import crop_fix
                kx, ky = org[2] / W, org[3] / H
                sb = [org[0] + nb[0] * kx, org[1] + nb[1] * ky, org[0] + nb[2] * kx, org[1] + nb[3] * ky]
                # the other tiles on the page, in the screenshot's pixels
                tiles = [[org[0] + (q[0] - off) * kx, org[1] + (q[1] - off) * ky,
                          org[0] + (q[2] - off) * kx, org[1] + (q[3] - off) * ky]
                         for q in boxes if q is not c.get('box')]
                wb, _m = crop_fix.widen(batches[pid]['images'][idx], sb, others=tiles)
                if wb != [int(round(v)) for v in sb]:
                    nb = [max(0, (wb[0] - org[0]) / kx), max(0, (wb[1] - org[1]) / ky),
                          min(W, (wb[2] - org[0]) / kx), min(H, (wb[3] - org[1]) / ky)]
                    stats['widened to the whole piece'] += 1
            frac = [round(nb[0] / W, 4), round(nb[1] / H, 4), round((nb[2] - nb[0]) / W, 4), round((nb[3] - nb[1]) / H, 4)]
            j = j0 + len(cells) - len(kept)
            rec = {'box': frac, 'read_box': [round(b[0] / W, 4), round(b[1] / H, 4), round((b[2] - b[0]) / W, 4), round((b[3] - b[1]) / H, 4)],
                   'snap': how, 'inferred': False, 'source': 'eye',
                   'name': none(c.get('name')), 'price': none(c.get('price')),
                   'currency': none(c.get('currency')).upper(), 'colour_name': none(c.get('colour')),
                   'garment': none(c.get('garment')), 'category': '', 'label': ''}
            rec['slot'] = slot_of(rec)
            rec.update(cut_cell(hi if hi is not None else im, frac, stem, j))
            cells.append(rec)
            cid = cell_id(pid, idx, j)
            flats[cid] = {'clean': bool(rec.get('clean')), 'why': rec.get('why', ''), 'flat': True,
                          'from_cell': rec.get('cut') or rec['path'], 'measured_by': 'read_grids'}
        # the flat-lay verdicts of cells this key no longer has are dropped
        for j in range(len(cells), 60):
            flats.pop(cell_id(pid, idx, j), None)
        out[key] = {'cells': cells, 'source': 'eye', 'found': len(cells), 'lattice': len(cells),
                    'skipped_cut_off': int(eye.get('skipped_cut_off') or 0),
                    'skipped_why': eye.get('skipped_why') or [], 'note': eye.get('note', ''),
                    'kept_decided': len(kept)}
        g = geom.get(key) or {}
        gc = g.get('cells') or []
        compare.append(dict(key=key, geometry=len(gc), eye=len(cells),
                            geometry_named=sum(1 for c in gc if c.get('name')),
                            eye_named=sum(1 for c in cells if c.get('name')),
                            geometry_priced=sum(1 for c in gc if c.get('price')),
                            eye_priced=sum(1 for c in cells if c.get('price'))))
        if k % 10 == 0 or k == len(files):
            json.dump(out, open(DEST, 'w'), indent=1)
            json.dump(flats, open(FLATS, 'w'), indent=1)
            print(f'  {k}/{len(files)}', flush=True)
    json.dump(out, open(DEST, 'w'), indent=1)
    json.dump(geom, open(GEOM, 'w'), indent=1)
    json.dump(flats, open(FLATS, 'w'), indent=1)
    # the pages this run did not read keep their rows
    try:
        prev = json.load(open(CAT + '/_grid_cells_compare.json'))
    except (FileNotFoundError, json.JSONDecodeError):
        prev = []
    done = {x['key'] for x in compare}
    json.dump([x for x in prev if x['key'] not in done] + compare,
              open(CAT + '/_grid_cells_compare.json', 'w'), indent=1)
    cells = [c for v in out.values() if v.get('source') == 'eye' for c in v.get('cells', [])]
    print('eye cells:', len(cells), '| clean:', sum(1 for c in cells if c.get('clean')),
          '| with a name:', sum(1 for c in cells if c.get('name')),
          '| with a price:', sum(1 for c in cells if c.get('price')),
          '| with a colour name:', sum(1 for c in cells if c.get('colour_name')),
          '| with a slot:', sum(1 for c in cells if c.get('slot')))
    print('skipped as cut off:', sum(v.get('skipped_cut_off', 0) for v in out.values() if v.get('source') == 'eye'))
    print(dict(stats))
    print('why not clean:', collections.Counter(c.get('why', '') for c in cells if not c.get('clean')).most_common(8))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--render', metavar='OUTDIR')
    ap.add_argument('--ingest', metavar='EYEDIR')
    a = ap.parse_args()
    if a.render:
        render(a.render)
    if a.ingest:
        ingest(a.ingest)


if __name__ == '__main__':
    main()
