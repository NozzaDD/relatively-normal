"""Which pictures cut the piece off at the picture's edge — 25 September.

A bag whose handle runs out of the top of the photograph has no handle in any
cut-out of that photograph: the cut can only keep what is in the frame. So the
question is asked of every picture, not of the cut-out alone:

  for each picture of a product (fabric close-ups and page panels aside), and
  for the product's own shelf cut-out, does the piece touch the picture's edge?

It is measured, not judged. A picture's whole cut-out (review/{pid}-whole.webp)
is that photograph at the same scale, background removed and trimmed to the
piece; the trim lost its position, so the cut is found again in the photo by
matching its opaque pixels, and a side counts as touched when a run of opaque
pixels lies on the photo's own border there. The shelf cut-out is found the
same way in each picture: the best match names the picture it was cut from.

Writes content/catalogue/_edge_clips.json:

  {pid: {pictures: {i: [sides]}, asset: {picture, sides}, clipped, prefer}}

  pictures  the sides each measured picture touches (top, bottom, left, right)
  asset     the picture the shelf cut-out came from, and the sides it touches
  clipped   every measured picture touches an edge: no photo shows it whole
  prefer    a picture that does not touch the edge, where the one the shelf
            cut-out came from does — offered first on the desk

build_studio.py reads it: a clipped product says "clipped at the edge" in
Review, and the pictures are offered unclipped first. `--apply` also makes the
preferred picture's whole cut-out the shelf cut-out, keeping the old one in
content/catalogue/assets-before-edge/.

  python3 content/tools/edge_clip.py [--apply] [--only PID ...]

Reads studio/data/products.json and studio/full, studio/assets: run it after
build_studio.py, then build_studio.py again.
"""
import os, sys, json, shutil, argparse
import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CAT = ROOT + '/content/catalogue'
STUDIO = ROOT + '/studio'
OUT = CAT + '/_edge_clips.json'
SKIP_TYPES = ('detail', 'text', 'other', 'listing grid')
MATCH_MAX = 8.0        # mean abs RGB difference at the best offset; above it, not found
SIDES = ('top', 'bottom', 'left', 'right')

# Read by eye, 25 September, from the bags measured clipped. A cut of a person
# wearing the piece reaches the frame with a head or a foot, not with the
# piece, so a picture on a model is measured but never counts as clipped; these
# two are on a model without being typed so.
ON_MODEL_BY_EYE = {
    'B046-P010-C3': 'on a model: the head touches the top, the tote is whole',
    'B028-P011-C1': 'on a model: the head touches the top, the bag is whole',
}
# Not a picture of the piece at all: nothing to be clipped.
NO_PIECE_BY_EYE = {
    'B027-P010-C0': 'a sliver of the grid page (955 x 153) with no bag in it',
}


def rgba(path):
    with Image.open(path) as im:
        return np.asarray(im.convert('RGBA'), dtype=np.float32)


def _search(P, ref, ys, xs, dys, dxs):
    best = (1e9, 0, 0)
    for dy in dys:
        d = np.abs(P[ys[:, None] + dy, xs[:, None] + dxs[None, :]] - ref[:, None, :]).mean(axis=(0, 2))
        i = int(d.argmin())
        if d[i] < best[0]:
            best = (float(d[i]), int(dxs[i]), int(dy))
    return best


def locate(photo, cut, npts=400, step=4):
    """(diff, dx, dy) of the cut's opaque pixels in the photo, or None.

    Every offset on a coarse lattice first, then every offset around the best
    one: the cut is the photo's own pixels, so the true offset stands out."""
    H, W = photo.shape[:2]
    h, w = cut.shape[:2]
    if h > H or w > W:
        return None
    ys, xs = np.nonzero(cut[:, :, 3] >= 200)
    if len(ys) < 50:
        return None
    k = np.random.default_rng(0).choice(len(ys), min(npts, len(ys)), replace=False)
    ys, xs = ys[k], xs[k]
    ref = cut[ys, xs, :3]
    P = photo[:, :, :3]
    _, cx, cy = _search(P, ref, ys, xs, range(0, H - h + 1, step), np.arange(0, W - w + 1, step))
    best = _search(P, ref, ys, xs, range(max(0, cy - step), min(H - h, cy + step) + 1),
                   np.arange(max(0, cx - step), min(W - w, cx + step) + 1))
    return best if best[0] <= MATCH_MAX else None


def touched(cut, dx, dy, W, H):
    """The sides of the photo the cut's opaque pixels reach, with a real run."""
    h, w = cut.shape[:2]
    a = cut[:, :, 3] >= 200
    out = []
    for side, on_edge, line, length in (
            ('top', dy == 0, a[0, :], w), ('bottom', dy + h == H, a[-1, :], w),
            ('left', dx == 0, a[:, 0], h), ('right', dx + w == W, a[:, -1], h)):
        if not on_edge:
            continue
        # the longest run of opaque pixels on that border line: a stray pixel
        # of anti-aliasing is not the piece running out of the frame
        run = best = 0
        for v in line:
            run = run + 1 if v else 0
            best = max(best, run)
        if best >= max(4, 0.01 * length):
            out.append(side)
    return out


def dropped(whole, asset):
    """How much of the piece in the picture the shelf cut-out left out, and how
    much of that is in the top quarter — where a bag's handles are."""
    (wa, wx, wy), (aa, ax, ay) = whole, asset
    H = max(wy + wa.shape[0], ay + aa.shape[0])
    W = max(wx + wa.shape[1], ax + aa.shape[1])
    w_ = np.zeros((H, W), bool); a_ = np.zeros((H, W), bool)
    w_[wy:wy + wa.shape[0], wx:wx + wa.shape[1]] = wa
    a_[ay:ay + aa.shape[0], ax:ax + aa.shape[1]] = aa
    lost = w_ & ~a_
    n = int(w_.sum()) or 1
    top = lost[wy:wy + max(1, wa.shape[0] // 4)]
    return dict(dropped=round(lost.sum() / n, 4), dropped_top=round(top.sum() / n, 4))


def measure(p):
    imgs = p.get('images') or []
    pics, photos, wholes = {}, {}, {}
    for i, e in enumerate(imgs):
        if e.get('type') in SKIP_TYPES or not e.get('whole'):
            continue
        fp, wp = STUDIO + '/' + e['path'], STUDIO + '/' + e['whole']['path']
        if not (os.path.exists(fp) and os.path.exists(wp)):
            continue
        photo, cut = rgba(fp), rgba(wp)
        photos[i] = photo
        m = locate(photo, cut)
        if m is None:
            continue
        pics[i] = touched(cut, m[1], m[2], photo.shape[1], photo.shape[0])
        wholes[i] = (cut[:, :, 3] >= 200, m[1], m[2])
    asset = None
    ap = STUDIO + '/' + (p.get('asset') or '')
    if p.get('asset_type') != 'crop' and os.path.exists(ap) and ap.startswith(STUDIO + '/assets/'):
        cut = rgba(ap)
        found = []
        for i, e in enumerate(imgs):
            if e.get('type') in SKIP_TYPES:
                continue
            photo = photos.get(i)
            if photo is None and os.path.exists(STUDIO + '/' + e['path']):
                photo = photos[i] = rgba(STUDIO + '/' + e['path'])
            if photo is None:
                continue
            m = locate(photo, cut)
            if m:
                found.append((m[0], i, m[1], m[2], touched(cut, m[1], m[2], photo.shape[1], photo.shape[0])))
        if found:
            _, i, x, y, sides = min(found)
            asset = dict(picture=i, sides=sides)
            if i in wholes:
                asset.update(dropped(wholes[i], (cut[:, :, 3] >= 200, x, y)))
    measured = dict(pics)
    if asset is not None and asset['picture'] not in measured:
        measured[asset['picture']] = asset['sides']
    on_model = {i for i in measured if (imgs[i].get('type') == 'on-model'
                                         or 'on a model' in (p.get('hold') or '')
                                         or p['product_id'] in ON_MODEL_BY_EYE)}
    judged = {i: s for i, s in measured.items() if i not in on_model}
    clipped = (bool(judged) and all(judged.values())
               and p['product_id'] not in NO_PIECE_BY_EYE)
    prefer = None
    if asset and asset['sides'] and not clipped:
        # another picture: the shelf cut-out's own one may be clear where the
        # cut-out was cropped closer (a figure cropped to its slot's band)
        free = [i for i, s in sorted(pics.items()) if not s and i != asset['picture']
                and i not in on_model]
        prefer = free[0] if free else None
    note = ON_MODEL_BY_EYE.get(p['product_id']) or NO_PIECE_BY_EYE.get(p['product_id'])
    return dict(pictures={str(i): s for i, s in sorted(pics.items())}, asset=asset,
                clipped=clipped, prefer=prefer, on_model=sorted(on_model),
                **({'by_eye': note} if note else {}))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true',
                    help="make the preferred picture's whole cut-out the shelf cut-out")
    ap.add_argument('--only', nargs='*')
    a = ap.parse_args()
    products = json.load(open(STUDIO + '/data/products.json'))
    out = {} if not a.only else (json.load(open(OUT)) if os.path.exists(OUT) else {})
    for n, p in enumerate(products):
        if a.only and p['product_id'] not in a.only:
            continue
        r = measure(p)
        if r['pictures'] or r['asset']:
            out[p['product_id']] = r
        if n % 200 == 0:
            print(n, '/', len(products), file=sys.stderr)
    json.dump(out, open(OUT, 'w'), indent=1, sort_keys=True)
    clipped = sorted(k for k, v in out.items() if v['clipped'])
    prefer = sorted(k for k, v in out.items() if v['prefer'] is not None)
    print(f'measured {len(out)} products; clipped in every picture: {len(clipped)}; '
          f'a better picture than the shelf cut-out\'s: {len(prefer)}')
    if a.apply:
        by = {p['product_id']: p for p in products}
        os.makedirs(CAT + '/assets-before-edge', exist_ok=True)
        import csv
        rows = {r['product_id']: r for r in csv.DictReader(open(CAT + '/products.csv'))}
        for pid in prefer:
            # only a flat cut-out is swapped: a picture's whole cut-out of a
            # person is the whole figure, where the shelf holds the garment's band
            if by[pid]['asset_type'] != 'cutout_flat' or pid not in rows:
                continue
            e = by[pid]['images'][out[pid]['prefer']]
            dst = ROOT + '/' + rows[pid]['asset_path']
            keep = f'{CAT}/assets-before-edge/{os.path.basename(dst)}'
            if os.path.exists(dst) and not os.path.exists(keep):
                shutil.copyfile(dst, keep)
            with Image.open(STUDIO + '/' + e['whole']['path']) as im:
                im.convert('RGBA').save(dst, 'WEBP', quality=88, method=5)
            out[pid]['applied'] = out[pid]['prefer']
            print('shelf cut-out now from picture', out[pid]['prefer'] + 1, 'of', pid)
        json.dump(out, open(OUT, 'w'), indent=1, sort_keys=True)


if __name__ == '__main__':
    main()
