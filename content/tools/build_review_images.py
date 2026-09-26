"""Web-sized copies of every screenshot of every product that is not a clean flat
cut-out: the photo area alone, a whole cut-out of it, two boxes, and on listing
grids the cells.

The desk's Review tab shows a product four ways — cut-out, item box, person
box, full photo — and the stylist picks; Adjust box lets her draw on any of the
product's screenshots and cut one image into several products. Boxes are
rectangles, not files: the desk crops at runtime. This script writes

  content/catalogue/review/{pid}.jpg        the best screenshot, shop page trimmed away, ≤ 1200 px
  content/catalogue/review/{pid}-{i}.jpg    every further screenshot of the product, i ≥ 1
  content/catalogue/review/{pid}[-i]-whole.webp  the whole figure or item cut out of it
  content/catalogue/_review_boxes.json      {pid: {w, h, item, person, images: [
                                               {path, w, h, item, person, mask_found,
                                                suggested, whole, origin}]}}

with boxes as fractions of their image. `suggested` is the cells of a listing
grid where the page is uniform cells on a plain backdrop; it is empty where
detection is unsure. `origin` and `origin_prev` are this build's crop and the
one before it, both in the ORIGINAL screenshot's own pixels, [x, y, w, h, W, H];
they are what let a box the stylist drew under an older trim be moved to the
same pixels under a new one — see migrate_trim.py.

Nothing here touches the originals or the existing assets.
"""
import sys, os, json, csv, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from PIL import Image
import imglib
from make_assets import photo_region, fit
from crop_figures import BAND, FIGURE

try:
    import pytesseract
    OCR = True
except ImportError:                                   # the trim falls back to edges
    OCR = False

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CAT = ROOT + '/content/catalogue'
OUT = CAT + '/review'
MAXSIDE = 1200


def flat_verdicts():
    """flat_lays.py's measured verdicts, where it has run."""
    try:
        return json.load(open(CAT + '/_flat_lays.json'))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def needs_review(a, pid=None, flats=None):
    """Everything but a measured-clean flat lay.

    The gate used to be the old asset_quality rule of thumb. It is now the
    measurement flat_lays.py makes, so that a product the desk will show in
    Review always has the review copy Review needs to draw on.
    """
    if flats is not None and pid is not None and pid in flats:
        return not flats[pid].get('clean')
    return not (a.get('asset_type') == 'cutout_flat' and a.get('asset_quality') == 'good')


# ------------------------------------------------------------------ the trim
# A shop page is a photograph with type around it: a search bar across the top,
# the name, price and size buttons below, and on a tablet a details column
# beside it. The content finder (product_box, else photo_region) already picks
# the photograph out of the page and does it well. The OCR pass only tidies its
# edges: it eats bands that are mostly type off the outside of that crop, and
# never anything else.
#
# It is deliberately one-directional and bounded. Five attempts at picking the
# photograph out of the page by text geometry each traded one failure for
# another; one of them — eroding from the whole page rather than from the
# content box — stopped at the first quiet band and handed back the entire
# page, which is worse than no trim at all. Starting inside the content box and
# eating only inward cannot do that: the result is always a subset of the crop
# the build made before, never a superset.
CELLS = 40               # grid the crop is tested on
CELL_FILL = 0.22         # a word must cover this much of a cell to mark it
EAT_MAX = 0.32           # never eat more than this off any one side
DENSE = 0.22             # a band goes when this many of its cells carry type
GRID_EAT = 0.16          # a listing grid only loses bars off the top and bottom


def text_grid(im):
    """A CELLS × CELLS mask of `im`: True where type sits. None without tesseract."""
    if not OCR:
        return None
    small = im.copy()
    small.thumbnail((1000, 1000), Image.LANCZOS)
    W, H = small.size
    if W < CELLS or H < CELLS:
        return None
    try:
        d = pytesseract.image_to_data(small, output_type=pytesseract.Output.DICT)
    except Exception:
        return None
    cw, chh = W / CELLS, H / CELLS
    cover = [[0.0] * CELLS for _ in range(CELLS)]
    for i, conf in enumerate(d['conf']):
        try:
            if float(conf) < 45 or not d['text'][i].strip():
                continue
        except (TypeError, ValueError):
            continue
        x, y, w, h = d['left'][i], d['top'][i], d['width'][i], d['height'][i]
        if w <= 0 or h <= 0 or w > W * 0.95 or h > H * 0.5:
            continue
        for gy in range(int(y / chh), min(CELLS, int((y + h) / chh) + 1)):
            for gx in range(int(x / cw), min(CELLS, int((x + w) / cw) + 1)):
                ox = max(0, min((gx + 1) * cw, x + w) - max(gx * cw, x))
                oy = max(0, min((gy + 1) * chh, y + h) - max(gy * chh, y))
                cover[gy][gx] += (ox * oy) / (cw * chh)
    return [[c >= CELL_FILL for c in row] for row in cover]


def erode_text_edges(noisy):
    """(l, t, r, b) in CELLS units: the crop with its type-heavy edges eaten."""
    C = len(noisy)
    lim = int(C * EAT_MAX)
    left, top, right, bot = 0, 0, C, C
    changed = True
    while changed:
        changed = False
        if top < lim and sum(noisy[top][left:right]) >= DENSE * (right - left):
            top += 1; changed = True
        if bot > C - lim and sum(noisy[bot - 1][left:right]) >= DENSE * (right - left):
            bot -= 1; changed = True
        if left < lim and sum(noisy[y][left] for y in range(top, bot)) >= DENSE * (bot - top):
            left += 1; changed = True
        if right > C - lim and sum(noisy[y][right - 1] for y in range(top, bot)) >= DENSE * (bot - top):
            right -= 1; changed = True
    return left, top, right, bot


def photo_area(page, shot_type=''):
    """The photograph alone, as a box in the page's coordinates.

    Always the content finder's box, or a tidier box inside it — never wider.
    """
    W, H = page.size
    if shot_type == 'listing grid':
        # the whole grid: the stylist cuts it up herself, and the cell detector
        # needs every cell, not the largest one. Only the page's own bars go —
        # narrowing a grid would cut its outer cells in half.
        noisy = text_grid(page)
        if noisy is None:
            return (0, 0, W, H)
        C = len(noisy)
        lim = int(C * GRID_EAT)
        top, bot = 0, C
        changed = True
        while changed:
            changed = False
            if top < lim and sum(noisy[top]) >= DENSE * C:
                top += 1; changed = True
            if bot > C - lim and sum(noisy[bot - 1]) >= DENSE * C:
                bot -= 1; changed = True
        return (0, int(top / C * H), W, int(bot / C * H))
    base = imglib.product_box(page) or photo_region(page)
    bw, bh = base[2] - base[0], base[3] - base[1]
    if bw < 80 or bh < 80:
        return base
    noisy = text_grid(page.crop(base))
    if noisy is None:                       # no tesseract: the content box as it is
        return base
    l, t, r, b = erode_text_edges(noisy)
    C = len(noisy)
    box = (base[0] + int(l / C * bw), base[1] + int(t / C * bh),
           base[0] + int(r / C * bw), base[1] + int(b / C * bh))
    if box[2] - box[0] < bw * 0.5 or box[3] - box[1] < bh * 0.5:
        return base
    return box


def full_photo(product, idx=0, shot_type=''):
    """-> (image, origin, origin_prev)

    Both crops are measured in the ORIGINAL file's pixels: the one this build
    makes, and the one the build before it made. Recording both is what lets a
    box the stylist already drew be moved to the same pixels under the new trim
    instead of being thrown away — see migrate_trim.py.
    """
    src = ROOT + '/' + product['images'][idx]
    with Image.open(src) as im0:
        orig = im0.convert('RGB')
        OW, OH = orig.size
        ch = imglib.trim_chrome(orig)
        page = orig.crop(ch)
        box = photo_area(page, shot_type)
        prev = ((0, 0) + page.size) if shot_type == 'listing grid' else \
            (imglib.product_box(page) or photo_region(page))
        crop = page.crop(box)
    org = [ch[0] + box[0], ch[1] + box[1], box[2] - box[0], box[3] - box[1], OW, OH]
    prv = [ch[0] + prev[0], ch[1] + prev[1], prev[2] - prev[0], prev[3] - prev[1], OW, OH]
    if shot_type != 'listing grid':
        # the crop rule (crop_fix.widen): the whole piece plus a margin. The
        # content finder works at 200 px wide, where a handle or a strap is a
        # pixel or two and is dropped as type; the screenshot still has it.
        import crop_fix
        w, _ = crop_fix.widen(product['images'][idx], [org[0], org[1], org[0] + org[2], org[1] + org[3]])
        if w != [org[0], org[1], org[0] + org[2], org[1] + org[3]]:
            org = [w[0], w[1], w[2] - w[0], w[3] - w[1], OW, OH]
            crop = orig.crop(tuple(w))
    return fit(crop, MAXSIDE), org, prv


def whole_cutout(full):
    """The whole figure or item, background removed and nothing else dropped.

    imglib.cutout() filters small components, which is right for a board asset
    and wrong here: the second shoe, a strap, a belt are exactly what the
    stylist is looking for when she opens this. So no component filtering at
    all — only the alpha threshold and a trim to what is left.
    """
    import io
    from rembg import remove
    work = full.copy()
    work.thumbnail((MAXSIDE, MAXSIDE), Image.LANCZOS)
    buf = io.BytesIO()
    work.save(buf, 'PNG')
    out = Image.open(io.BytesIO(remove(buf.getvalue(), session=imglib.session()))).convert('RGBA')
    out.putalpha(out.getchannel('A').point(lambda v: 255 if v >= 200 else 0))
    bb = out.getbbox()
    if not bb:
        return None
    out = out.crop(bb)
    if min(out.size) < 40:
        return None
    # A cut-out that is still a filled rectangle the size of the frame means
    # rembg found nothing to separate — a flat swatch, a page panel. That is
    # not the piece, so hand back nothing rather than the whole screenshot.
    a = out.getchannel('A')
    w, h = out.size
    if (w * h) / (full.width * full.height) > 0.9:
        rows = sum(1 for y in range(h) if a.crop((0, y, w, y + 1)).getbbox() == (0, 0, w, 1))
        cols = sum(1 for x in range(w) if a.crop((x, 0, x + 1, h)).getbbox() == (0, 0, 1, h))
        if rows / h > 0.95 and cols / w > 0.95:
            return None
    return out


def boxes_for(full, slot):
    """(person, item) as fractions of the full image, from the alpha mask."""
    W, H = full.size
    try:
        cut, _ = imglib.cutout(full.copy(), max_side=MAXSIDE, blob_rel=0.04)
        a = cut.getchannel('A').point(lambda v: 255 if v > 200 else 0)
        bb = a.getbbox()
    except Exception:
        bb = None
    if not bb or (bb[2] - bb[0]) < W * 0.05 or (bb[3] - bb[1]) < H * 0.05:
        whole = [0.0, 0.0, 1.0, 1.0]
        return whole, whole, False
    # the cut-out is at the full image's own scale (fit is a no-op at ≤ MAXSIDE)
    sx, sy = W / cut.size[0], H / cut.size[1]
    x0, y0, x1, y1 = bb[0] * sx, bb[1] * sy, bb[2] * sx, bb[3] * sy
    pad = 0.015
    person = [max(0, x0 / W - pad), max(0, y0 / H - pad),
              min(1, (x1 - x0) / W + 2 * pad), min(1, (y1 - y0) / H + 2 * pad)]
    h, w = y1 - y0, x1 - x0
    band = BAND.get(slot, (0.0, 1.0))
    if h >= FIGURE * w and band != (0.0, 1.0):
        iy0 = y0 + h * band[0]
        iy1 = y0 + h * band[1]
        item = [person[0], max(0, iy0 / H - pad), person[2], min(1, (iy1 - iy0) / H + 2 * pad)]
    else:
        item = list(person)
    return [round(v, 4) for v in person], [round(v, 4) for v in item], True


# ------------------------------------------------------------- listing grids
def grid_cells(im, min_cells=4, strict=True):
    """The cells of a listing grid, or [] when the page is not plainly one.

    Uniform cells on a plain backdrop: the content that differs from the page's
    modal colour breaks into blobs of about one size, laid out in at least two
    rows and two columns. Anything less regular is not offered — a wrong
    suggestion costs more taps than none.

    `strict=False` is for a page the viewing pass already typed as a listing
    grid, so the page need not prove it: two alike blobs side by side are
    enough, and header text or a half-scrolled row no longer vetoes the rest.
    """
    import numpy as np
    from scipy import ndimage
    from collections import Counter
    w0, h0 = im.size
    small = im.convert('RGB').copy()
    small.thumbnail((320, 320), Image.BILINEAR)
    a = np.asarray(small).astype(int)
    q = (a // 16)
    bg = Counter(map(tuple, q.reshape(-1, 3))).most_common(1)[0][0]
    bgr = np.array(bg) * 16 + 8
    mask = np.abs(a - bgr).sum(axis=2) > 45
    mask = ndimage.binary_opening(mask, iterations=1)
    lab, n = ndimage.label(mask)
    if n < min_cells:
        return []
    H, W = mask.shape
    cells = []
    for i, sl in enumerate(ndimage.find_objects(lab), 1):
        if sl is None:
            continue
        y0, y1, x0, x1 = sl[0].start, sl[0].stop, sl[1].start, sl[1].stop
        area = (y1 - y0) * (x1 - x0)
        if area < 0.012 * W * H or area > 0.6 * W * H:
            continue
        cells.append((x0, y0, x1 - x0, y1 - y0))
    if len(cells) < min_cells:
        return []
    mw = float(np.median([c[2] for c in cells]))
    mh = float(np.median([c[3] for c in cells]))
    alike = [c for c in cells if 0.55 * mw <= c[2] <= 1.6 * mw and 0.55 * mh <= c[3] <= 1.6 * mh]
    if len(alike) < min_cells or (strict and len(alike) < 0.7 * len(cells)):
        return []

    def bands(vals, tol):
        out = []
        for v in sorted(vals):
            if out and abs(v - out[-1][-1]) <= tol:
                out[-1].append(v)
            else:
                out.append([v])
        return out
    rows = bands([c[1] + c[3] / 2 for c in alike], mh * 0.5)
    cols = bands([c[0] + c[2] / 2 for c in alike], mw * 0.5)
    if (len(rows) < 2 and strict) or len(cols) < 2:
        return []
    pad = 0.015
    out = []
    for x, y, w, h in sorted(alike, key=lambda c: (round((c[1] + c[3] / 2) / (mh * 0.5)), c[0])):
        out.append([round(max(0, x / W - pad), 4), round(max(0, y / H - pad), 4),
                    round(min(1, w / W + 2 * pad), 4), round(min(1, h / H + 2 * pad), 4)])
    return out


def main():
    A = json.load(open(CAT + '/_assets.json'))
    B = {b['product_id']: b for b in json.load(open(CAT + '/batches.json'))}
    prows = list(csv.DictReader(open(CAT + '/products.csv')))
    slots = {r['product_id']: r['slot'] for r in prows}
    shots = {r['product_id']: r['shot_type'] for r in prows}
    os.makedirs(OUT, exist_ok=True)
    try:
        out = json.load(open(CAT + '/_review_boxes.json'))
    except (FileNotFoundError, json.JSONDecodeError):
        out = {}
    flats = flat_verdicts()
    pids = [pid for pid, a in sorted(A.items()) if needs_review(a, pid, flats)]
    # one entry per screenshot; the first may already exist from an earlier run
    def done(pid, i):
        rec = out.get(pid, {})
        imgs = rec.get('images') or []
        if i < len(imgs) and imgs[i] and 'error' not in imgs[i]:
            return True
        return i == 0 and 'w' in rec
    todo = [(pid, i) for pid in pids for i in range(len(B[pid]['images'])) if not done(pid, i)]
    print(f'{len(todo)} images to do over {len(pids)} products', flush=True)
    grids = 0
    for k, (pid, i) in enumerate(todo, 1):
        name = f'{pid}.jpg' if i == 0 else f'{pid}-{i}.jpg'
        stem = name[:-4]
        shot = shots.get(pid, '')
        try:
            full, origin, origin_prev = full_photo(B[pid], i, shot)
            full.save(f'{OUT}/{name}', 'JPEG', quality=86, optimize=True)
            person, item, found = boxes_for(full, slots.get(pid, ''))
            entry = dict(path=f'review/{name}', w=full.size[0], h=full.size[1], person=person,
                         item=item, mask_found=found, bytes=os.path.getsize(f'{OUT}/{name}'),
                         suggested=grid_cells(full) if shot == 'listing grid' else [],
                         origin=origin, origin_prev=origin_prev)
            # a listing grid is cut with boxes, so it gets no whole cut-out
            if shot != 'listing grid':
                w = whole_cutout(full)
                if w:
                    w.save(f'{OUT}/{stem}-whole.webp', 'WEBP', quality=88, method=5)
                    entry['whole'] = dict(path=f'review/{stem}-whole.webp', w=w.size[0], h=w.size[1],
                                          bytes=os.path.getsize(f'{OUT}/{stem}-whole.webp'))
        except Exception as e:
            entry = dict(path=f'review/{name}', error=f'{type(e).__name__}: {e}', suggested=[])
        rec = out.setdefault(pid, {})
        imgs = rec.setdefault('images', [])
        while len(imgs) <= i:
            imgs.append(None)
        imgs[i] = entry
        if i == 0 and 'error' not in entry:
            rec.update({k2: entry[k2] for k2 in ('w', 'h', 'person', 'item', 'mask_found', 'bytes')})
        if k % 20 == 0 or k == len(todo):
            json.dump(out, open(CAT + '/_review_boxes.json', 'w'), indent=1)
            print(f'  {k}/{len(todo)}', flush=True)
    # the first image was built by an earlier run: give it its images[0] entry and a grid pass
    for pid in pids:
        rec = out[pid]
        imgs = rec.setdefault('images', [])
        if not imgs or imgs[0] is None:
            entry = {k2: rec[k2] for k2 in ('w', 'h', 'person', 'item', 'mask_found', 'bytes') if k2 in rec}
            entry['path'] = f'review/{pid}.jpg'
            imgs[:1] = [entry]
        for e in imgs:
            if e and 'suggested' not in e and 'error' not in e:
                with Image.open(f"{CAT}/{e['path']}") as im:
                    e['suggested'] = grid_cells(im) if shots.get(pid) == 'listing grid' else []
    json.dump(out, open(CAT + '/_review_boxes.json', 'w'), indent=1)
    imgs_all = [e for v in out.values() for e in v.get('images', []) if e]
    c = collections.Counter('error' if 'error' in e else ('mask' if e.get('mask_found') else 'no mask') for e in imgs_all)
    print('done:', dict(c), '%d images, %.1f MB' % (len(imgs_all), sum(e.get('bytes', 0) for e in imgs_all) / 1e6))
    print('grids detected on', sum(1 for e in imgs_all if e.get('suggested')), 'images;',
          'products with more than one image:', sum(1 for v in out.values() if len(v.get('images', [])) > 1))
    whole = [e for e in imgs_all if e.get('whole')]
    print('whole cut-outs:', len(whole), '%.1f MB' % (sum(e['whole']['bytes'] for e in whole) / 1e6),
          '| images without one:', len(imgs_all) - len(whole))


if __name__ == '__main__':
    main()
