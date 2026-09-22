"""Web-sized copies of every screenshot of every product that is not a clean flat
cut-out, with two boxes per image and, on listing grids, the cells.

The desk's Review tab shows a product four ways — cut-out, item box, person
box, full photo — and the stylist picks; Adjust box lets her draw on any of the
product's screenshots and cut one image into several products. Boxes are
rectangles, not files: the desk crops at runtime. This script writes

  content/catalogue/review/{pid}.jpg       the best screenshot, page UI trimmed, ≤ 1200 px
  content/catalogue/review/{pid}-{i}.jpg   every further screenshot of the product, i ≥ 1
  content/catalogue/_review_boxes.json     {pid: {w, h, item, person, images: [
                                              {path, w, h, item, person, mask_found, suggested}]}}

with boxes as fractions of their image. `suggested` is the cells of a listing
grid where the page is uniform cells on a plain backdrop; it is empty where
detection is unsure. Nothing here touches the originals or the existing assets.
"""
import sys, os, json, csv, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from PIL import Image
import imglib
from make_assets import photo_region, fit
from crop_figures import BAND, FIGURE

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CAT = ROOT + '/content/catalogue'
OUT = CAT + '/review'
MAXSIDE = 1200


def needs_review(a):
    return not (a.get('asset_type') == 'cutout_flat' and a.get('asset_quality') == 'good')


def full_photo(product, idx=0, shot_type=''):
    src = ROOT + '/' + product['images'][idx]
    with Image.open(src) as im0:
        page = im0.convert('RGB')
        page = page.crop(imglib.trim_chrome(page))
    if shot_type == 'listing grid':
        # the whole grid: the stylist cuts it up herself, and the cell detector
        # needs every cell, not the largest one
        return fit(page, MAXSIDE)
    box = imglib.product_box(page) or photo_region(page)
    return fit(page.crop(box), MAXSIDE)


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
def grid_cells(im, min_cells=4):
    """The cells of a listing grid, or [] when the page is not plainly one.

    Uniform cells on a plain backdrop: the content that differs from the page's
    modal colour breaks into blobs of about one size, laid out in at least two
    rows and two columns. Anything less regular is not offered — a wrong
    suggestion costs more taps than none.
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
    if len(alike) < min_cells or len(alike) < 0.7 * len(cells):
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
    if len(rows) < 2 or len(cols) < 2:
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
    pids = [pid for pid, a in sorted(A.items()) if needs_review(a)]
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
        try:
            full = full_photo(B[pid], i, shots.get(pid, ''))
            full.save(f'{OUT}/{name}', 'JPEG', quality=86, optimize=True)
            person, item, found = boxes_for(full, slots.get(pid, ''))
            entry = dict(path=f'review/{name}', w=full.size[0], h=full.size[1], person=person,
                         item=item, mask_found=found, bytes=os.path.getsize(f'{OUT}/{name}'),
                         suggested=grid_cells(full))
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
                    e['suggested'] = grid_cells(im)
    json.dump(out, open(CAT + '/_review_boxes.json', 'w'), indent=1)
    imgs_all = [e for v in out.values() for e in v.get('images', []) if e]
    c = collections.Counter('error' if 'error' in e else ('mask' if e.get('mask_found') else 'no mask') for e in imgs_all)
    print('done:', dict(c), '%d images, %.1f MB' % (len(imgs_all), sum(e.get('bytes', 0) for e in imgs_all) / 1e6))
    print('grids detected on', sum(1 for e in imgs_all if e.get('suggested')), 'images;',
          'products with more than one image:', sum(1 for v in out.values() if len(v.get('images', [])) > 1))


if __name__ == '__main__':
    main()
