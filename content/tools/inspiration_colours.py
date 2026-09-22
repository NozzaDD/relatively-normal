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

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
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


def ring_colours(im, frac=0.08, n=3):
    """The modal colours of the outer frame — the runway floor and the wall.

    Border-connected flood fill alone is not enough here: most of these images
    are screenshots with a black letterbox, so the fill eats the letterbox and
    stops, and the floor stays in as `tan`. Whatever fills the frame ring is not
    the outfit, wherever it sits in the picture.
    """
    w, h = im.size
    m = max(2, int(min(w, h) * frac))
    px = im.load()
    c = collections.Counter()
    for y in range(h):
        inside = m <= y < h - m
        for x in range(w):
            if inside and m <= x < w - m:
                continue
            r, g, b = px[x, y][:3]
            c[(r >> 4, g >> 4, b >> 4)] += 1
    return [C.srgb_to_lab(tuple(v * 16 + 8 for v in q)) for q, _ in c.most_common(n)]


def photo_only(im):
    """Strip browser chrome and the letterbox so the picture is all that is left."""
    im = im.crop(imglib.trim_chrome(im))
    box = imglib.photo_box(im)
    if box and (box[2] - box[0]) > im.size[0] * 0.3 and (box[3] - box[1]) > im.size[1] * 0.3:
        im = im.crop(box)
    return im


def subject_crop(im, band=(0.34, 0.66), top=0.10, bottom=0.94):
    """The centre band of the frame.

    A runway photograph puts the model in the middle and everything that is not
    the outfit — floor, wall, front row, the photographers — around the edges.
    Blob-finding could not separate them (the model merges with the floor she is
    standing on), but geometry can: sample the middle third and nothing else.
    Fashion-week captures are the overwhelming majority of this folder, so this
    is the right default; images where it fails are marked by a low clothes
    share rather than quietly trusted."""
    w, h = im.size
    return im.crop((int(w * band[0]), int(h * top), int(w * band[1]), int(h * bottom))), True


def clothes_colours(path, band=(0.38, 0.62), top=0.16, bottom=0.88):
    """Clothes-only colours: the middle of the frame, minus what the edges are made of."""
    with Image.open(path) as im0:
        full = photo_only(im0.convert('RGB'))
        full.thumbnail((420, 420), Image.LANCZOS)
        ring = ring_colours(full)                       # floor, wall, front row
        im, _ = subject_crop(full, band, top, bottom)
        px = list(im.getdata())
    keep, skin, bgn, cache = [], 0, 0, {}
    for r, g, b in px:
        k = (r >> 3, g >> 3, b >> 3)
        v = cache.get(k)
        if v is None:
            L, ch, h = C.lab_to_lch(C.srgb_to_lab((r, g, b)))
            l = C.srgb_to_lab((r, g, b))
            v = cache[k] = (2 if any(C.delta_e_2000(l, q) <= 11 for q in ring)
                            else (1 if imglib.is_skin(L, ch, h) else 0))
        if v == 2:
            bgn += 1; keep.append((r, g, b, 0))
        elif v == 1:
            skin += 1; keep.append((r, g, b, 0))
        else:
            keep.append((r, g, b, 255))
    kept = sum(1 for p in keep if p[3])
    if kept < 500:                                      # the mask ate the outfit
        keep = [(r, g, b, 255) for r, g, b in px]
        skin = bgn = 0
        kept = len(keep)
    cols = extract_colours(keep, k=5, floor=0.04, sample=20000, seed=0)
    merged = []
    for c in cols:
        for m in merged:
            if C.delta_e_2000(tuple(c['lab']), tuple(m['lab'])) <= 7:
                m['share'] += c['share']; break
        else:
            merged.append(dict(c))
    merged.sort(key=lambda c: -c['share'])
    # where each colour sits in the frame: an accent at the hem is a shoe, the
    # same colour at the neck is a scarf, and the board has to put it in the
    # right place
    w = im.size[0]
    sy = [0.0] * len(merged[:4]); sn = [0] * len(merged[:4])
    labs = [tuple(c['lab']) for c in merged[:4]]
    for i, (r, g, b, a) in enumerate(keep):
        if not a:
            continue
        l = C.srgb_to_lab((r, g, b))
        j = min(range(len(labs)), key=lambda k: C.delta_e_2000(l, labs[k]))
        sy[j] += (i // w); sn[j] += 1
    H = max(1, im.size[1])
    out = []
    for i, c in enumerate(merged[:4]):
        fam, nm, L, Cc, h, rel, nt = classify(c['hex'])
        y = (sy[i] / sn[i] / H) if sn[i] else 0.5
        out.append(dict(sits=('upper' if y < 0.34 else 'middle' if y < 0.67 else 'lower'),
                        sits_y=round(y, 2),
                        hex=c['hex'], share=round(c['share'], 3), family=fam, name=nm,
                        L=round(L, 1), C=round(Cc, 1), h=round(h, 1), rel=round(rel, 3),
                        neutral=nt, role=role(i, c, rel)))
    bd = imglib.backdrop_rgb(full)
    return out, dict(skin_share=round(skin / max(1, len(px)), 3),
                     background_share=round(bgn / max(1, len(px)), 3),
                     clothes_share=round(kept / max(1, len(px)), 3),
                     background_hex='%02X%02X%02X' % bd,
                     background_name=classify('%02X%02X%02X' % bd)[1],
                     ring_hexes=[C.lab_to_hex(q) for q in ring])


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
