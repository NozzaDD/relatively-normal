"""Cluster product screenshots into shop BATCHES and, inside a batch, into PRODUCTS.

A batch is a run of screenshots taken from one web shop in one sitting. It is
detected from filename sequence plus page layout — the header band, the page
margins and the backdrop are near-identical inside a batch and change at the
boundary.

A product is one garment inside a batch, shown once or several times (packshot,
on model, detail). Grouped on adjacency plus visual similarity of the main
image area plus colour agreement.

Writes content/catalogue/batches.json. `--append [extra paths]` adds new
screenshots as new batches without renumbering the existing ones.
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
    def other_shop(a, b):
        pa = brand_of(a[-1]) if brand_of else ''
        pb = brand_of(b[0]) if brand_of else ''
        return bool(pa and pb and pa != pb)
    for b in raw:
        # a runt joins the batch before it, never across a change of shop
        if merged and len(b) < min_len and len(merged[-1]) >= min_len and not other_shop(merged[-1], b):
            merged[-1].extend(b)
        else:
            merged.append(b)
    if brand_of:
        # one shop, one sitting: neighbouring batches the address bar puts in
        # the same shop are one batch, however much its page layout varies
        out = []
        for b in merged:
            da = {brand_of(x) for x in out[-1]} - {''} if out else set()
            db = {brand_of(x) for x in b} - {''}
            if out and da and da == db:
                out[-1].extend(b)
            else:
                out.append(b)
        merged = out
    return [b for b in merged if b]


MAX_PER_PRODUCT = 5      # a long run of near-identical listing grids is not one product


def products(bat, sig, main_max=10, colour_max=26, text=None):
    """Merge adjacent shots of the same garment.

    The page's own text decides first (`text`, from page_text.py): two pages
    that name different products, colours or product numbers are two products
    however alike their layout, and two that agree on one of those and
    contradict none are one. Only where neither page says anything legible
    about itself does the layout and colour of the page decide, as before —
    consecutive pages from one shop share every pixel of their furniture, which
    is how three Levi's jeans became one product."""
    import page_text as T
    groups = [[bat[0]]]
    for prev, p in zip(bat, bat[1:]):
        dmain = imglib.ham(sig[p]['main'], sig[prev]['main'])
        ca, cb = sig[p]['avg'], sig[prev]['avg']
        dcol = sum(abs(a - b) for a, b in zip(ca, cb))
        near = seq(p) - seq(prev) <= 2
        fa, fb = (text or {}).get(prev), (text or {}).get(p)
        if fa and fb and T.disagree(fa, fb):
            same = False
        elif fa and fb and T.legible_in_both(fa, fb):
            same = near
        else:
            same = near and (dmain <= main_max or dcol <= colour_max)
        if same:
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


def copies(paths):
    """path -> the image elsewhere in content/swipe that it is a byte-for-byte
    copy of. Only files of the same size are read."""
    import hashlib
    swipe = ROOT + '/content/swipe'
    by_size = collections.defaultdict(list)
    for root, _, fs in os.walk(swipe):
        for f in fs:
            q = os.path.join(root, f)
            by_size[os.path.getsize(q)].append(os.path.relpath(q, ROOT))
    h = lambda rel: hashlib.sha1(open(ROOT + '/' + rel, 'rb').read()).hexdigest()  # noqa: E731
    out = {}
    for p in paths:
        others = [q for q in by_size[os.path.getsize(ROOT + '/' + p)]
                  if q != p and q not in paths and not re.search(r'-\d+\.\w+$', q)]
        hp = h(p) if others else None
        for q in others:
            if h(q) == hp:
                out[p] = q
                break
    return out


def append(extra=()):
    """Cluster screenshots that no batch holds yet into NEW batches after the
    last one, leaving every existing batch and product ID as it is.

    A full re-run numbers batches by position, so a screenshot inserted in the
    middle of the sequence renumbers every batch after it — and the IDs in
    asset-choices.json, used_in and the outfits would then point at other
    garments. It would also undo split_mixed.py's rewrite of batches.json.
    New screenshots are the ones in content/swipe/products/ that the swipe
    index does not type yet; `extra` adds paths the index typed as something
    else but that are product pages after all."""
    out = json.load(open(OUT + '/batches.json'))
    have = {i for o in out for i in o['images']}
    idx = {r['path'] for r in csv.DictReader(open(ROOT + '/content/swipe/index.csv'))}
    folder = 'content/swipe/products'
    new = [folder + '/' + f for f in os.listdir(ROOT + '/' + folder)
           if re.match(r'IMG_\d+(-\d+)?\.(png|jpe?g)$', f, re.I)]
    new = [p for p in new if p not in idx and p not in have] + [p for p in extra if p not in have]
    new = sorted(set(new), key=seq)
    # a byte-identical copy of an image already filed — IMG_1337.png is the
    # same file as fashion shows ss27/IMG_1337.png — is not a new product.
    # identical files are one, by content and never by name (25 Sept): iOS
    # exports IMG_1357-2.png beside IMG_1357.png; two identical new files are
    # one as well, the first in sequence kept
    same = copies(new)
    import hashlib
    seen = {}
    for p in [q for q in new if q not in same]:
        h = hashlib.sha1(open(ROOT + '/' + p, 'rb').read()).hexdigest()
        if h in seen:
            same[p] = seen[h]
        else:
            seen[h] = p
    if same:
        print('skipped as copies of a filed image:', ', '.join(f'{os.path.basename(a)} = {b}' for a, b in same.items()))
        new = [p for p in new if p not in same]
    print('new product images:', len(new))
    if not new:
        return
    old = json.load(open(SIGCACHE)) if os.path.exists(SIGCACHE) else {}
    missing = [p for p in new if p not in old]
    if missing:
        if os.path.exists(SIGCACHE):
            os.rename(SIGCACHE, SIGCACHE + '.bak')
        try:
            sig_new = signatures(missing)
        finally:
            if os.path.exists(SIGCACHE + '.bak'):
                os.replace(SIGCACHE + '.bak', SIGCACHE)
        old.update(sig_new)
        json.dump(old, open(SIGCACHE, 'w'))
    sig = old
    bi = max(int(o['batch_id'][1:]) for o in out)
    added = []
    import page_text as T
    import url_bar as U
    # the address bar names the shop: a batch never spans two domains
    bars = json.load(open(OUT + '/_url_bars.json')) if os.path.exists(OUT + '/_url_bars.json') else {'images': {}}
    vocab, eye = U.vocabulary(), U.eye_read()
    for p in new:
        if p not in bars['images']:
            d, raw = U.read_bar(ROOT + '/' + p)
            bars['images'][p] = {'domain': U.snap(d, vocab, eye), 'raw': raw}
    json.dump(bars, open(OUT + '/_url_bars.json', 'w'), indent=1)
    dom = {p: bars['images'][p]['domain'] for p in new}
    text = T.ensure(new)
    for bat in batch(new, sig, brand_of=lambda p: dom.get(p, '')):
        bi += 1
        bid = f'B{bi:03d}'
        for pi, grp in enumerate(products(bat, sig, text=text), 1):
            added.append(dict(batch_id=bid, product_id=f'{bid}-P{pi:03d}', images=grp))
    out.extend(added)
    json.dump(out, open(OUT + '/batches.json', 'w'), indent=1)
    print(f'added batches: {len({a["batch_id"] for a in added})}   products: {len(added)}')
    for a in added:
        print(a['product_id'], ' '.join(os.path.basename(i) for i in a['images']))


def main():
    if '--append' in sys.argv:
        return append([a for a in sys.argv[1:] if a != '--append'])
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
