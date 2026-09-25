"""How many products ON THE SHELF show the faults the owner hid products for —
point 7 of 24 September. Measures, re-cuts nothing.

  jagged   the tile is a cut-out whose alpha has only two levels (0 and 255):
           the hard threshold every cut-out made before soft_cut.py has. At
           shelf size a staircase on a curved edge shows; on a straight one less.
  holes    opaque pixels inside the cut that are the backdrop's colour (the
           screenshot's corners), flat, in a piece big enough to be a gap
           between legs or between arm and body — soft_cut.punch_holes' test,
           run on the existing cut.
  handles  bags only: isnet-general-use, run on the same picture, finds opaque
           structure above the old cut's top edge covering ≥ 1.5% of the
           height — a handle or strap the old cut dropped. Slow, so bags only.

    python3 content/tools/cut_audit.py            # writes _cut_audit.json, prints by slot
"""
import os, sys, json, collections, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image
import soft_cut as S
from shelf_text import shelf_rows

OUT = S.CAT + '/_cut_audit.json'


def backdrop_of(p):
    e = (p.get('images') or [{}])[p.get('image') or 0] or {}
    path = S.STUDIO + '/' + e['path'] if e.get('path') else None
    if not path or not os.path.exists(path):
        return None, 0
    return S.backdrop(Image.open(path).convert('RGB'))


def holes(p, a4, bg, noise):
    rgb, alpha = a4[..., :3], a4[..., 3].astype(np.float32) / 255
    _, share = S.punch_holes(rgb, alpha, bg, noise)
    return share


def lost_handles(p, a4):
    src, e = S.source_picture(p)
    if src is None:
        return None
    new = S.model_alpha(src) > 0.5
    ys = np.nonzero(new.any(1))[0]
    if not len(ys):
        return None
    # the old cut, placed where it came from: compare heights of the two cuts
    # relative to their widths (the cut is cropped to its own box)
    old = a4[..., 3] > 128
    oh, ow = old.shape
    xs = np.nonzero(new.any(0))[0]
    nh, nw = ys[-1] - ys[0] + 1, xs[-1] - xs[0] + 1
    return round(float((nh / nw) / (oh / ow) - 1), 3)


def main():
    products = json.load(open(S.STUDIO + '/data/products.json'))
    rows = shelf_rows(products)
    out, t0 = {}, time.time()
    for n, p in enumerate(rows, 1):
        rec = {'slot': p.get('slot') or ''}
        if p.get('choice') in ('item', 'person', 'full', 'custom') and (p.get('base') or 'photo') == 'photo':
            rec['kind'] = 'box on the photo'          # no cut edge to judge
            out[p['product_id']] = rec
            continue
        try:
            a4 = np.asarray(Image.open(S.STUDIO + '/' + p['asset']).convert('RGBA'))
        except Exception:
            continue
        a = a4[..., 3]
        rec['kind'] = 'tile' if p.get('asset_type') == 'tile' else 'cut-out'
        if rec['kind'] == 'cut-out':
            opaque = a > 0
            rec['jagged'] = bool(((a > 0) & (a < 255)).sum() < 0.002 * max(1, opaque.sum()))
            bg, noise = backdrop_of(p)
            if bg is not None:
                rec['holes'] = round(holes(p, a4, bg, noise), 4)
            if p.get('slot') == 'bag':
                rec['handle_gain'] = lost_handles(p, a4)
        out[p['product_id']] = rec
        if n % 100 == 0:
            print(f'{n}/{len(rows)}', round(time.time() - t0), 's', flush=True)
    json.dump(dict(products=out), open(OUT, 'w'), indent=0)
    by = collections.defaultdict(collections.Counter)
    for rec in out.values():
        s = rec['slot'] or '—'
        by[s]['shelf'] += 1
        by[s]['cut-outs'] += rec.get('kind') == 'cut-out'
        by[s]['jagged'] += bool(rec.get('jagged'))
        by[s]['holes'] += (rec.get('holes') or 0) >= 0.005
        by[s]['handles'] += (rec.get('handle_gain') or 0) >= 0.08
    print('slot        shelf  cut-outs  jagged  holes  handles')
    for s, c in sorted(by.items(), key=lambda kv: -kv[1]['shelf']):
        print(f"{s:10s} {c['shelf']:6d} {c['cut-outs']:9d} {c['jagged']:7d} {c['holes']:6d} {c['handles']:8d}")
    tot = sum(by.values(), collections.Counter())
    print('total     ', tot['shelf'], tot['cut-outs'], tot['jagged'], tot['holes'], tot['handles'])


if __name__ == '__main__':
    main()
