"""One "full" image and two boxes for every product that is not a clean flat cut-out.

The desk's Review tab shows a product four ways — cut-out, item box, person
box, full photo — and the stylist picks. The boxes are rectangles, not files:
the desk crops the full image at runtime. This script writes

  content/catalogue/review/{pid}.jpg     the product photo without page UI, ≤ 1200 px
  content/catalogue/_review_boxes.json   {pid: {w, h, item: [x,y,w,h], person: [x,y,w,h]}}

with boxes as fractions of the full image. Nothing here touches the originals
or the existing assets.
"""
import sys, os, json, csv, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, '/home/user/relatively-normal')
from PIL import Image
import imglib
from make_assets import photo_region, fit
from crop_figures import BAND, FIGURE

ROOT = '/home/user/relatively-normal'
CAT = ROOT + '/content/catalogue'
OUT = CAT + '/review'
MAXSIDE = 1200


def needs_review(a):
    return not (a.get('asset_type') == 'cutout_flat' and a.get('asset_quality') == 'good')


def full_photo(product):
    src = ROOT + '/' + product['images'][0]
    with Image.open(src) as im0:
        page = im0.convert('RGB')
        page = page.crop(imglib.trim_chrome(page))
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


def main():
    A = json.load(open(CAT + '/_assets.json'))
    B = {b['product_id']: b for b in json.load(open(CAT + '/batches.json'))}
    slots = {r['product_id']: r['slot'] for r in csv.DictReader(open(CAT + '/products.csv'))}
    os.makedirs(OUT, exist_ok=True)
    try:
        out = json.load(open(CAT + '/_review_boxes.json'))
    except (FileNotFoundError, json.JSONDecodeError):
        out = {}
    todo = [pid for pid, a in sorted(A.items()) if needs_review(a) and pid not in out]
    print(f'{len(todo)} products to do ({len(out)} already done)', flush=True)
    for i, pid in enumerate(todo, 1):
        try:
            full = full_photo(B[pid])
            full.save(f'{OUT}/{pid}.jpg', 'JPEG', quality=86, optimize=True)
            person, item, found = boxes_for(full, slots.get(pid, ''))
            out[pid] = dict(w=full.size[0], h=full.size[1], person=person, item=item,
                            mask_found=found, bytes=os.path.getsize(f'{OUT}/{pid}.jpg'))
        except Exception as e:
            out[pid] = dict(error=f'{type(e).__name__}: {e}')
        if i % 20 == 0 or i == len(todo):
            json.dump(out, open(CAT + '/_review_boxes.json', 'w'), indent=1)
            print(f'  {i}/{len(todo)}', flush=True)
    json.dump(out, open(CAT + '/_review_boxes.json', 'w'), indent=1)
    c = collections.Counter('error' if 'error' in v else ('mask' if v['mask_found'] else 'no mask')
                            for v in out.values())
    print('done:', dict(c), 'total %.1f MB' % (sum(v.get('bytes', 0) for v in out.values()) / 1e6))


if __name__ == '__main__':
    main()
