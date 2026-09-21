"""Clothes-only colours for the inspiration images.

Whole-frame colours are what produced the mismatched boards: a teal wall behind
a model reads as a key colour and then nothing in the wardrobe can carry it.
Here the backdrop is flood-filled away from the border, skin is masked, and only
what is left counts. Roles: dominant, secondary, accent.
"""
import sys, os, json, csv, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image
import imglib
from colour_names import classify
from engine.matcher import extract_colours
from engine import colour as C

ROOT = '/home/user/relatively-normal'
TOL = 13.0


def bg_mask(im, tol=TOL):
    from collections import deque
    w, h = im.size
    px = im.load()
    bd = imglib.backdrop_rgb(im)
    blab = C.srgb_to_lab(bd)
    cache = {}

    def near(x, y):
        r, g, b = px[x, y][:3]
        k = (r >> 3, g >> 3, b >> 3)
        v = cache.get(k)
        if v is None:
            v = cache[k] = C.delta_e_2000(C.srgb_to_lab((r, g, b)), blab) <= tol
        return v

    bg = bytearray(w * h)
    q = deque()
    for x in range(w):
        for y in (0, h - 1):
            if not bg[y * w + x] and near(x, y):
                bg[y * w + x] = 1; q.append((x, y))
    for y in range(h):
        for x in (0, w - 1):
            if not bg[y * w + x] and near(x, y):
                bg[y * w + x] = 1; q.append((x, y))
    while q:
        x, y = q.popleft()
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= nx < w and 0 <= ny < h and not bg[ny * w + nx] and near(nx, ny):
                bg[ny * w + nx] = 1; q.append((nx, ny))
    return bg, bd


def role(i, col, rel):
    if i == 0:
        return 'dominant'
    if col['share'] < 0.18 and rel > 0.30:
        return 'accent'
    return 'secondary' if i == 1 else ('accent' if rel > 0.30 else 'secondary')


def clothes_colours(path):
    with Image.open(path) as im0:
        im = im0.convert('RGB')
        im.thumbnail((300, 300), Image.LANCZOS)
        bg, bd = bg_mask(im)
        px = list(im.getdata())
    keep, skin, bgn = [], 0, 0
    for i, (r, g, b) in enumerate(px):
        if bg[i]:
            bgn += 1; keep.append((r, g, b, 0)); continue
        L, ch, h = C.lab_to_lch(C.srgb_to_lab((r, g, b)))
        if imglib.is_skin(L, ch, h):
            skin += 1; keep.append((r, g, b, 0))
        else:
            keep.append((r, g, b, 255))
    kept = sum(1 for p in keep if p[3])
    if kept < 500:
        keep = [(r, g, b, 0 if bg[i] else 255) for i, (r, g, b) in enumerate(px)]
        skin = 0
        kept = sum(1 for p in keep if p[3])
    cols = extract_colours(keep, k=5, floor=0.04, sample=20000, seed=0)
    merged = []
    for c in cols:
        for m in merged:
            if C.delta_e_2000(tuple(c['lab']), tuple(m['lab'])) <= 7:
                m['share'] += c['share']; break
        else:
            merged.append(dict(c))
    merged.sort(key=lambda c: -c['share'])
    out = []
    for i, c in enumerate(merged[:4]):
        fam, nm, L, Cc, h, rel, nt = classify(c['hex'])
        out.append(dict(hex=c['hex'], share=round(c['share'], 3), family=fam, name=nm,
                        L=round(L, 1), C=round(Cc, 1), h=round(h, 1), rel=round(rel, 3),
                        neutral=nt, role=role(i, c, rel)))
    return out, dict(skin_share=round(skin / max(1, len(px)), 3),
                     background_share=round(bgn / max(1, len(px)), 3),
                     clothes_share=round(kept / max(1, len(px)), 3),
                     background_hex='%02X%02X%02X' % bd,
                     background_name=classify('%02X%02X%02X' % bd)[1])


def main():
    idx = list(csv.DictReader(open(ROOT + '/content/swipe/index.csv')))
    imgs = [r for r in idx if r['type'] in ('visual', 'artwork')]
    out = {}
    for i, r in enumerate(imgs, 1):
        try:
            cols, meta = clothes_colours(ROOT + '/' + r['path'])
        except Exception as e:
            out[r['path']] = dict(error=f'{type(e).__name__}: {e}'); continue
        out[r['path']] = dict(colours=cols, **meta, folder=r['folder'],
                              brand_legible=r.get('brand_legible', ''),
                              what_it_shows=r.get('what_it_shows', ''),
                              colour_words=r.get('colour_words', ''),
                              styled_how=r.get('styled_how', ''))
        if i % 25 == 0:
            print(f'  {i}/{len(imgs)}', flush=True)
    json.dump(out, open(ROOT + '/content/catalogue/_inspiration.json', 'w'), indent=1)
    print('inspiration images:', len(out))
    print(collections.Counter(c['family'] for v in out.values() for c in v.get('colours', [])).most_common())


if __name__ == '__main__':
    main()
