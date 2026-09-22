"""Cluster product screenshots into shop BATCHES and, inside a batch, into PRODUCTS.

A batch is a run of screenshots taken from one web shop in one sitting. It is
detected from filename sequence plus page layout — the header band, the page
margins and the backdrop are near-identical inside a batch and change at the
boundary.

A product is one garment inside a batch, shown once or several times (packshot,
on model, detail). Grouped on adjacency plus visual similarity of the main
image area plus colour agreement.

Writes content/catalogue/batches.json.
"""
import csv, json, os, re, sys, collections

BRAND = {}
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image
import imglib

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = ROOT + '/content/catalogue'


def seq(path):
    m = re.search(r'IMG_(\d+)', os.path.basename(path))
    return int(m.group(1)) if m else -1


SIGCACHE = OUT + '/_signatures.json'


def signatures(paths):
    if os.path.exists(SIGCACHE):
        c = json.load(open(SIGCACHE))
        if set(c) >= set(paths):
            return {k: v for k, v in c.items()}
    """Per image: header-band hash, page-margin hash, main-area hash+colour."""
    sig = {}
    for p in paths:
        with Image.open(ROOT + '/' + p) as im0:
            im = im0.convert('RGB')
            box = imglib.trim_chrome(im)
            page = im.crop(box)
            w, h = page.size
            header = page.crop((0, 0, w, max(8, int(h * 0.09))))
            margins = page.crop((0, 0, max(8, int(w * 0.06)), h))
            main = page.crop((0, int(h * 0.10), w, int(h * 0.72)))
            small = main.copy(); small.thumbnail((64, 64), Image.LANCZOS)
            px = list(small.getdata())
            n = len(px)
            avg = tuple(sum(c[i] for c in px) // n for i in range(3))
            sig[p] = dict(header=imglib.dhash(header), margin=imglib.dhash(margins),
                          main=imglib.dhash(main), page=imglib.dhash(page),
                          avg=avg, size=list(page.size), box=list(box))
    os.makedirs(OUT, exist_ok=True)
    json.dump(sig, open(SIGCACHE, 'w'))
    return sig


def batch(paths, sig, brand_of=None, peak=17, min_len=3, gap_max=8):
    """Boundaries where the page furniture changes, snapped to legible-brand
    changes. Screenshot filenames here are almost perfectly contiguous, so the
    sequence alone carries no batch signal — layout does."""
    n = len(paths)
    dist = [0.0] * n
    for i in range(1, n):
        a, b = paths[i - 1], paths[i]
        dh = imglib.ham(sig[b]['header'], sig[a]['header'])
        dm = imglib.ham(sig[b]['margin'], sig[a]['margin'])
        dist[i] = 0.55 * dh + 0.45 * dm
        if sig[b]['size'] != sig[a]['size']:
            dist[i] += 12
        if seq(b) - seq(a) > gap_max:
            dist[i] += 40
    cuts = {0}
    for i in range(1, n):
        if dist[i] >= peak:
            cuts.add(i)
    if brand_of:                       # force a cut where a legible brand changes
        for i in range(1, n):
            pa, pb = brand_of(paths[i - 1]), brand_of(paths[i])
            if pa and pb and pa != pb:
                cuts.add(i)
    idx = sorted(cuts) + [n]
    raw = [paths[idx[k]:idx[k + 1]] for k in range(len(idx) - 1)]
    merged = []                        # absorb runts into the previous batch
    for b in raw:
        if merged and len(b) < min_len and len(merged[-1]) >= min_len:
            merged[-1].extend(b)
        else:
            merged.append(b)
    return [b for b in merged if b]


MAX_PER_PRODUCT = 5      # a long run of near-identical listing grids is not one product


def products(bat, sig, main_max=10, colour_max=26):
    """Merge adjacent shots of the same garment."""
    groups = [[bat[0]]]
    for prev, p in zip(bat, bat[1:]):
        dmain = imglib.ham(sig[p]['main'], sig[prev]['main'])
        ca, cb = sig[p]['avg'], sig[prev]['avg']
        dcol = sum(abs(a - b) for a, b in zip(ca, cb))
        if seq(p) - seq(prev) <= 2 and (dmain <= main_max or dcol <= colour_max):
            groups[-1].append(p)
        else:
            groups.append([p])
    out = []
    for g in groups:
        if len(g) <= MAX_PER_PRODUCT:
            out.append(g)
        else:
            out.extend([[x] for x in g])
    return out


def main():
    rows = [r for r in csv.DictReader(open(ROOT + '/content/swipe/index.csv')) if r['type'] == 'product']
    global BRAND
    BRAND = {r['path']: (r['brand_legible'] or '').split(' (')[0].strip().upper() for r in rows}
    paths = sorted({r['path'] for r in rows}, key=lambda p: (os.path.dirname(p), seq(p)))
    print('product images:', len(paths))
    sig = signatures(paths)
    out = []
    bi = 0
    for folder in sorted({os.path.dirname(p) for p in paths}):
        fp = [p for p in paths if os.path.dirname(p) == folder]
        bo = lambda p: BRAND.get(p, '')          # noqa: E731
        for bat in batch(fp, sig, brand_of=bo):
            bi += 1
            bid = f'B{bi:03d}'
            for pi, grp in enumerate(products(bat, sig), 1):
                out.append(dict(batch_id=bid, product_id=f'{bid}-P{pi:03d}', images=grp))
    os.makedirs(OUT, exist_ok=True)
    json.dump(out, open(OUT + '/batches.json', 'w'), indent=1)
    nb = len({o['batch_id'] for o in out})
    print(f'batches: {nb}   products: {len(out)}   images: {sum(len(o["images"]) for o in out)}')
    sizes = collections.Counter(len(o['images']) for o in out)
    print('images per product:', dict(sorted(sizes.items())))
    per = collections.Counter(o['batch_id'] for o in out)
    print('largest batches:', per.most_common(8))


if __name__ == '__main__':
    main()
