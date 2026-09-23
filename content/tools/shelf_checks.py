"""Two questions the shelf gate did not ask: is the picture ONE garment, and is
the product already on the shelf under another row.

  python3 content/tools/shelf_checks.py [--sheets]

Writes content/catalogue/_shelf_checks.json; build_studio.py reads it. With
--sheets, one contact sheet per check in content/catalogue/sheets/. Nothing is
deleted or merged: a product with several garments in its picture goes back to
Review, and a duplicate is marked with its keeper and hidden from the shelf.
Both are measured on the picture the shelf shows (the row's asset), never
judged from a colour field or by eye.

SEVERAL GARMENTS. The gate measured one connected piece, clear of the frame,
no text — and a fan of five colourways laid over each other passes all three.
A picture holds several garments when any of these is true:

  grid page      the row's picture is a listing-grid page (the viewing pass)
  all-colours    the picture is a style's all-colours photo (uniqlo_variants)
  pieces         the cut-out falls into 3+ separate pieces of real size, or 2
                 where a pair is not the garment (not shoes, gloves, trousers)
  colour regions 3+ separate, coherent colour regions (dE76 >= 12 apart, each
                 >= 8% of the garment and one connected block >= 6%) and no
                 skin in the picture. Shading on one garment stays within 12;
                 a person brings skin, so an outfit on a model is not a fan.

DUPLICATES. Same brand and slot, then the picture itself: the silhouettes
overlap (IoU >= 0.96 on a 40 px square), the lightness structure inside them
agrees (mean |dL| <= 2 after removing each one's mean), and the garment's
median colour is within dE2000 3. A recolour of the same source shares the
silhouette exactly, so the colour decides; a colourway split that copied its
parent's picture matches on all three while its colour FIELDS disagree, which
is why the fields are not used. Clusters are joined; one keeper per cluster:
a real photo over a recolour, then the cleaner cut, then the row with a name
and price, then the original row over a derived one.
"""
import os, sys, csv, json, re, math, itertools, collections, argparse
import numpy as np
from PIL import Image
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
CAT = ROOT + '/content/catalogue'
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)
from engine import colour as C          # noqa: E402

PAIR_SLOTS = ('shoes', 'accessory', 'bottom')   # a pair or two legs is one product
IOU, STRUCT, DE = 0.96, 2.0, 3.0


def lab_arr(rgb):
    a = rgb / 255.0
    a = np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)
    M = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    xyz = a @ M.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[:, 1] - 16, 500 * (f[:, 0] - f[:, 1]), 200 * (f[:, 1] - f[:, 2])], 1)


def load(path, side):
    im = Image.open(path).convert('RGBA')
    im.thumbnail((side, side))
    return np.asarray(im)


def pieces(a):
    """Separate pieces of real size in a cut-out; None for an opaque picture."""
    m = a[..., 3] > 128
    if m.mean() > 0.97:
        return None
    lab, n = ndimage.label(m)
    if not n:
        return 0
    sizes = np.bincount(lab.ravel())[1:]
    return int(((sizes >= 0.12 * sizes.max()) & (sizes >= 0.015 * m.size)).sum())


def skin_share(L):
    Cc = np.hypot(L[:, 1], L[:, 2])
    h = np.degrees(np.arctan2(L[:, 2], L[:, 1])) % 360
    return float(((L[:, 0] >= 40) & (L[:, 0] <= 82) & (Cc >= 12) & (Cc <= 38)
                  & (h >= 25) & (h <= 75)).mean())


def colour_regions(a, k=10, merge=12.0):
    """(regions, skin share) of a cut-out, or None for an opaque picture."""
    m = a[..., 3] > 128
    if m.mean() > 0.97 or m.sum() < 400:
        return None
    L = lab_arr(a[..., :3][m].astype(float))
    rng = np.random.default_rng(0)
    c = L[rng.choice(len(L), k, replace=False)]
    for _ in range(20):
        lab = np.argmin(((L[:, None] - c[None]) ** 2).sum(2), 1)
        c = np.array([L[lab == j].mean(0) if (lab == j).any() else c[j] for j in range(k)])
    par = list(range(k))

    def root(x):
        while par[x] != x:
            x = par[x]
        return x
    for i in range(k):
        for j in range(i + 1, k):
            if np.linalg.norm(c[i] - c[j]) < merge:
                par[root(i)] = root(j)
    g = np.array([root(x) for x in lab])
    full = np.full(m.shape, -1)
    full[m] = g
    n = 0
    for r in set(g.tolist()):
        reg, nn = ndimage.label(full == r)
        big = np.bincount(reg.ravel())[1:].max() / m.sum() if nn else 0
        if (g == r).mean() >= 0.08 and big >= 0.06:
            n += 1
    return n, skin_share(L)


def colours_photos():
    v = json.load(open(CAT + '/_variants.json')) if os.path.exists(CAT + '/_variants.json') else {}
    return {x for r in v.get('report', {}).values() for x in r.get('colours_photos', [])}


def root_of(r):
    """The row whose picture a derived row shares: a grid, a split's parent, a
    recolour's source. Review groups several-garment rows under it."""
    if r.get('parent_id'):
        return r['parent_id']
    if r.get('recolour_source'):
        return r['recolour_source']
    return re.sub(r'-V\d+$', '', r['product_id'])


def several(rows):
    cp = colours_photos()
    out = {}
    for r in rows:
        if r.get('shelf') == 'hidden' or not r.get('asset_path'):
            continue
        why = []
        if r.get('shot_type') == 'listing grid':
            why.append('grid page: the picture is a listing-grid page of several products')
        imgs = [x for x in (r.get('image_paths') or '').split(';') if x]
        # a variant cut from that photo is one garment lying alone on it
        if imgs and set(imgs) <= cp and not r.get('recolour_source'):
            why.append('all-colours: the picture is the style\'s all-colours photo')
        try:
            a = load(ROOT + '/' + r['asset_path'], 200)
        except (FileNotFoundError, OSError):
            continue
        pc = pieces(a)
        if pc is not None and (pc >= 3 or (pc == 2 and r.get('slot') not in PAIR_SLOTS)):
            why.append(f'pieces: the cut-out is {pc} separate pieces')
        cr = colour_regions(a)
        if cr and cr[0] >= 3 and cr[1] < 0.03:
            why.append(f'colour regions: {cr[0]} separate colour regions and no skin — a fan of colourways')
        if why:
            out[r['product_id']] = dict(why=why, group=root_of(r))
    return out


def norm(s):
    return re.sub(r'[^a-z0-9]', '', (s or '').lower())


def features(path, N=40):
    im = Image.open(path).convert('RGBA')
    w, h = im.size
    s = max(w, h)
    sq = Image.new('RGBA', (s, s), (0, 0, 0, 0))
    sq.paste(im, ((s - w) // 2, (s - h) // 2))
    a = np.asarray(sq.resize((N, N), Image.BILINEAR)).astype(float)
    m = a[..., 3] > 128
    if m.sum() < 30:
        return None
    lab = lab_arr(a[..., :3].reshape(-1, 3)).reshape(N, N, 3)
    return dict(m=m, L=np.where(m, lab[..., 0] - lab[..., 0][m].mean(), 0),
                med=np.median(lab[m], 0), asp=w / h)


def family(pid):
    return re.sub(r'-(V\d+|sw\d+|C\d+|S\d+)$', '', re.sub(r'-sw\d+$', '', pid))


def cause(a, b):
    """Which run made the second row of a pair."""
    if (a['recolour_source'] or '-sw' in a['product_id']
            or b['recolour_source'] or '-sw' in b['product_id']) \
            and family(a['product_id']) == family(b['product_id']):
        return 'UNIQLO variant'
    if re.sub(r'-V\d+$', '', a['product_id']) == re.sub(r'-V\d+$', '', b['product_id']):
        return 'colourway split'
    return 'already in the catalogue'


def keeper_rank(r, clean):
    derived = bool(r['parent_id'] or r['recolour_source'] or re.search(r'-(V|sw|C|S)\d+$', r['product_id']))
    kind = {'cutout_flat': 0, 'cutout_model': 1, 'tile': 2}.get(r['asset_type'], 3)
    return (r['recoloured'] == 'yes',                      # a real photo over a recolour
            not clean.get(r['product_id'], False), kind,   # then the cleaner cut
            not (r['product_name'] and r['price']),        # then a name and a price
            derived, r['product_id'])


def duplicates(rows, clean):
    live = [r for r in rows if r.get('shelf') != 'hidden' and r.get('asset_path')]
    feat = {}
    for r in live:
        try:
            f = features(ROOT + '/' + r['asset_path'])
        except (FileNotFoundError, OSError):
            f = None
        if f:
            feat[r['product_id']] = f
    by = collections.defaultdict(list)
    for r in live:
        if r['product_id'] in feat and norm(r['brand']) and r['slot']:
            by[(norm(r['brand']), r['slot'])].append(r)
    pairs = []
    for ps in by.values():
        for a, b in itertools.combinations(ps, 2):
            fa, fb = feat[a['product_id']], feat[b['product_id']]
            if abs(math.log(fa['asp'] / fb['asp'])) > 0.25:
                continue
            iou = (fa['m'] & fb['m']).sum() / (fa['m'] | fb['m']).sum()
            if iou < IOU:
                continue
            both = fa['m'] & fb['m']
            sd = float(np.abs(fa['L'][both] - fb['L'][both]).mean())
            de = C.delta_e_2000(tuple(fa['med']), tuple(fb['med']))
            if sd <= STRUCT and de <= DE:
                pairs.append((a['product_id'], b['product_id'], round(float(iou), 3), round(sd, 2), round(de, 2)))
    par = {}

    def root(x):
        par.setdefault(x, x)
        while par[x] != x:
            x = par[x]
        return x
    for a, b, *_ in pairs:
        par[root(a)] = root(b)
    clusters = collections.defaultdict(list)
    for x in list(par):
        clusters[root(x)].append(x)
    by_id = {r['product_id']: r for r in rows}
    measured = {frozenset((a, b)): dict(iou=i, struct=s, de=e) for a, b, i, s, e in pairs}
    out = {}
    for members in clusters.values():
        keep = min(members, key=lambda p: keeper_rank(by_id[p], clean))
        for m in members:
            if m == keep:
                continue
            out[m] = dict(keeper=keep, cause=cause(by_id[m], by_id[keep]),
                          measured=measured.get(frozenset((m, keep))),
                          cluster=sorted(members))
    return out, pairs


def clean_verdicts():
    """The shelf gate's own verdict, as build_studio.py computes it."""
    sys.argv = sys.argv[:1]
    import build_studio as B
    rows = list(csv.DictReader(open(CAT + '/products.csv')))
    review = json.load(open(CAT + '/_review_boxes.json'))
    return {p['product_id']: p['clean'] for p in B.build_products(rows, review)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sheets', action='store_true')
    a = ap.parse_args()
    rows = list(csv.DictReader(open(CAT + '/products.csv')))
    clean = clean_verdicts()
    sev = several(rows)
    dup, pairs = duplicates(rows, clean)
    json.dump(dict(several=sev, duplicates=dup,
                   thresholds=dict(iou=IOU, structure=STRUCT, de2000=DE)),
              open(CAT + '/_shelf_checks.json', 'w'), indent=1, sort_keys=True)
    print('several garments:', len(sev), ' of them on the shelf before:',
          sum(1 for p in sev if clean.get(p)))
    print('  by reason:', collections.Counter(w.split(':')[0] for v in sev.values() for w in v['why']))
    print('duplicates:', len(dup), ' pairs measured:', len(pairs))
    print('  by cause:', collections.Counter(v['cause'] for v in dup.values()))
    if a.sheets:
        from contact_sheet import sheet
        by_id = {r['product_id']: r for r in rows}
        os.makedirs(CAT + '/sheets', exist_ok=True)
        sheet([dict(path=ROOT + '/' + by_id[p]['asset_path'],
                    label=f"{p} {by_id[p]['slot']}\n" + '; '.join(w.split(':')[0] for w in v['why']))
               for p, v in sorted(sev.items())], CAT + '/sheets/shelf-check-several.jpg',
              cols=10, cell=150, label_h=40, title='Several garments in one picture — back to Review')
        cells = []
        for p, v in sorted(dup.items(), key=lambda x: (x[1]['cause'], x[0])):
            cells += [dict(path=ROOT + '/' + by_id[p]['asset_path'], label=f"{p}\n{v['cause']}"),
                      dict(path=ROOT + '/' + by_id[v['keeper']]['asset_path'], label=f"keeper {v['keeper']}")]
        sheet(cells, CAT + '/sheets/shelf-check-duplicates.jpg', cols=10, cell=130, label_h=40,
              title='Duplicates (left) and their keepers (right)')


if __name__ == '__main__':
    main()
