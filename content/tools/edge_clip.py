"""Which pieces run out of the SCREENSHOT — redone 25 September.

The first version (PR #31) measured each picture's whole cut-out against the
picture itself. But the picture was already a crop of the screenshot, made by a
content finder that drops thin handles and straps, so it called B090-P010-V4
"clipped at the top" when the screenshot shows the whole bag, handle and
strap, clear of every edge. The crop was cut, not the bag.

Now every picture is measured on its original screenshot (crop_fix.measure_rect:
the piece followed out past the crop, on the screenshot itself), and a piece is
clipped only where it touches the screenshot's own edge — the page scrolled it
away, or the photograph filled the screen. Two other outcomes are kept apart:

  photo_edge  the piece runs to the edge of the shop's own photograph inside
              the page (one of a stack of photos, a grid tile): the screenshot
              holds no more of it, but its edge is not where the piece stops.
              Reported, never called clipped.
  cut         the crop lost what the screenshot has: crop_fix.py measures it
              and recrop.py puts it right. After a re-cut there are none left.

Writes content/catalogue/_edge_clips.json:

  {pid: {pictures: {i: [sides of the screenshot it touches]},
         photo_edge: {i: [sides]}, still_cut: [i], on_model: [i],
         clipped, prefer}}

  clipped   every judged picture runs the piece out of the screenshot
  prefer    a picture where it does not, when the primary one does

A picture on a model is measured but never counts (the head or a foot reaches
the frame, not the piece); ON_MODEL_BY_EYE and NO_PIECE_BY_EYE hold by-eye
exceptions. build_studio.py reads the file.

  python3 content/tools/edge_clip.py [--only PID ...]

Reads studio/data/products.json: run it after build_studio.py, then
build_studio.py again. `rgba` and `locate` (a cut-out found again in the picture
it was cut from, by its own pixels) are used by recrop.py.
"""
import os, sys, json, argparse
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
CAT = ROOT + '/content/catalogue'
STUDIO = ROOT + '/studio'
OUT = CAT + '/_edge_clips.json'
MATCH_MAX = 8.0        # mean abs RGB difference at the best offset; above it, not found

# Read by eye, 25 September. A cut of a person wearing the piece reaches the
# frame with a head or a foot, not with the piece, so a picture on a model is
# measured but never counts as clipped; these are on a model without being
# typed so.
ON_MODEL_BY_EYE = {
    'B046-P010-C3': 'on a model: the head touches the top, the tote is whole',
    'B028-P011-C1': 'on a model: the head touches the top, the bag is whole',
    'B043-P005': 'the model fills the screenshot; the snakeskin bag is inside the frame',
    'B043-P006': 'the model fills the screenshot; the clutch in her hand is inside the frame',
}
# Read by eye, 25 September: the shop's tile runs to the screenshot's edge,
# the bag inside it is clear of every edge.
NOT_CLIPPED_BY_EYE = {
    'B081-P001-C1': 'Marge Sherwood tile runs to the right edge; the bag is clear of it',
    'B081-P002-C1': 'Marge Sherwood tile runs to the right edge; the bag is clear of it',
    'B081-P002-I1-C1': 'Marge Sherwood tile runs to the right edge; the bag is clear of it',
    'B082-P001-C1': 'Marge Sherwood tile runs to the right edge; the bag is clear of it',
    'B005-P001': 'the bra is whole inside its photo; the photo runs to the edge',
    'B010-P003': 'in a lightbox; the shirt is clear of every edge',
    'B011-P008': 'in a lightbox; the shirt is clear of every edge',
    'B017-P001-V3': 'in a lightbox; the polo is clear of every edge',
    'B023-P015-I1-C5': 'a model in a grid tile at the edge; the outfit is whole',
    'B025-P008-V2': 'a listing page; the page, not a piece, reaches the edge',
    'B042-P010': 'a model photograph at the edge; the dress is shown whole below',
    'B044-P006-C1': 'sunglasses on a model; the face photo reaches the edge, the glasses do not',
    'B044-P010-V2': 'the page chrome reaches the edge; the piece is whole',
    'B052-P006-S1': 'a model shown head to foot; her photograph reaches the edge',
    'B062-P003': 'a fan of hoodies clear of every edge',
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


_SHOTS = {}


def shot_type(pid):
    """The viewing pass's shot type for a row (a cell inherits nothing)."""
    if not _SHOTS:
        import csv
        for r in csv.DictReader(open(CAT + '/products.csv')):
            _SHOTS[r['product_id']] = r.get('shot_type', '')
    return _SHOTS.get(pid, '')


def judge(p, measured):
    """measured: {picture index: crop_fix record} -> the product's entry."""
    imgs = p.get('images') or []
    ok = {i: r for i, r in measured.items() if r.get('state') not in ('tiny', 'empty', 'unmeasured')}
    pics = {i: r.get('touches') or [] for i, r in ok.items()}
    photo = {i: r.get('photo_edge') or [] for i, r in ok.items() if r.get('photo_edge')}
    # a person reaching the frame says nothing about where the garment ends:
    # a picture on a model is measured, never counted as clipped
    worn = (shot_type(p['product_id']) == 'on model' or p.get('asset_type') == 'cutout_model'
            or any(w in (p.get('hold') or '') for w in ('model', 'wearing', 'skin')))
    on_model = sorted(i for i in pics if imgs[i].get('type') == 'on-model' or worn
                      or p['product_id'] in ON_MODEL_BY_EYE)
    judged = {i: s for i, s in pics.items() if i not in on_model}
    clipped = bool(judged) and all(judged.values()) and p['product_id'] not in NO_PIECE_BY_EYE \
        and p['product_id'] not in NOT_CLIPPED_BY_EYE
    prim = p.get('primary') or 0
    prefer = None
    if judged.get(prim) and not clipped:
        free = [i for i, s in sorted(judged.items()) if not s]
        prefer = free[0] if free else None
    note = (ON_MODEL_BY_EYE.get(p['product_id']) or NO_PIECE_BY_EYE.get(p['product_id'])
            or NOT_CLIPPED_BY_EYE.get(p['product_id']))
    return dict(pictures={str(i): s for i, s in sorted(pics.items())},
                photo_edge={str(i): s for i, s in sorted(photo.items())},
                still_cut=sorted(i for i, r in ok.items() if r.get('state') == 'cut'),
                on_model=on_model, clipped=clipped, prefer=prefer,
                **({'by_eye': note} if note else {}))


def main():
    import crop_fix as CF
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', nargs='*')
    a = ap.parse_args()
    products = json.load(open(STUDIO + '/data/products.json'))
    if a.only:
        products = [p for p in products if p['product_id'] in a.only]
    review = CF.load('_review_boxes.json', {})
    out = json.load(open(OUT)) if (a.only and os.path.exists(OUT)) else {}
    cache = {}
    for n, p in enumerate(products):
        measured = {}
        for i, e in enumerate(p.get('images') or []):
            if e.get('type') in CF.SKIP_TYPES:
                continue
            rect, src = CF.picture_rect(p, i, review)
            if not rect:
                continue
            key = (src, tuple(round(v) for v in rect[:4]))
            if key not in cache:
                cache[key] = CF.measure_rect(src, rect)
            measured[i] = cache[key]
        if measured:
            out[p['product_id']] = judge(p, measured)
        if n % 200 == 0:
            print(n, '/', len(products), file=sys.stderr)
    json.dump(out, open(OUT, 'w'), indent=1, sort_keys=True)
    clipped = sorted(k for k, v in out.items() if v['clipped'])
    cut = sorted(k for k, v in out.items() if v['still_cut'])
    print(f"measured {len(out)} products; clipped at the screenshot's edge in every picture: "
          f"{len(clipped)}; a picture still cut by its crop: {len(cut)}")
    return out


if __name__ == '__main__':
    main()
