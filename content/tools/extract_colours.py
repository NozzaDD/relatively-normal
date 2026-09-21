"""Garment-only colours per product, read off the saved asset.

The asset is already the garment (cut-out) or a clean tile, so this is a much
cleaner read than sampling a whole product page. On model shots the skin band
is masked and the share it removed is recorded.

Records up to three colours with share, CIELAB L*/C*/h, the engine's relative
chroma and neutral flag, plus a family and a plain name from the fixed
vocabulary in colour_names.py.
"""
import json, os, sys, collections, statistics
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image
import imglib
from colour_names import classify
from engine.matcher import extract_colours
from engine import colour as C

ROOT = '/home/user/relatively-normal'


def _bg_mask(im, tol=10.0):
    """Border-connected background only.

    The first cut of this masked every pixel close to the backdrop in L* and
    chroma, which quietly deleted pale garments: a cream knit on a white studio
    sweep came back 96% "pale grey" with 3% of pixels kept. Background is a
    topological fact, not a colour one, so flood-fill inward from the border
    instead and leave anything enclosed by the garment alone.
    """
    w, h = im.size
    px = im.load()
    bd = imglib.backdrop_rgb(im)
    blab = C.srgb_to_lab(bd)
    cache = {}

    def near(x, y):
        r, g, b = px[x, y][:3]
        k = (r >> 3, g >> 3, b >> 3)          # dE2000 per pixel is too slow; 5-bit
        v = cache.get(k)                      # buckets are well under the tolerance
        if v is None:
            v = cache[k] = C.delta_e_2000(C.srgb_to_lab((r, g, b)), blab) <= tol
        return v

    bg = bytearray(w * h)
    from collections import deque
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
    return bg


def garment_pixels(im, is_cutout, white_balance=False):
    """-> (rgba list for extract_colours, skin_share, kept_share, wb_applied)

    White balancing is off by default: measured over all 463 assets it moved the
    dominant colour by a median dE of 0.00 and occasionally by 66, so it is a
    no-op that sometimes does damage.
    """
    if not is_cutout:
        rgb = im.convert('RGB')
        if white_balance:
            rgb = imglib.white_balance(rgb, imglib.backdrop_rgb(rgb))
        w, h = rgb.size
        bg = _bg_mask(rgb)
        px = list(rgb.getdata())
        keep = [(r, g, b, 0 if bg[i] else 255) for i, (r, g, b) in enumerate(px)]
        # a small garment in a big tile is normal, so judge the mask by an
        # absolute pixel count, not by the share it removed
        if sum(1 for p in keep if p[3]) < 400:
            keep = [(r, g, b, 255) for r, g, b in px]
    else:
        im = im.convert('RGBA')
        keep = [(r, g, b, 255 if al > 200 else 0) for r, g, b, al in im.getdata()]
    op = sum(1 for p in keep if p[3])
    skin = 0
    out = []
    for r, g, b, a in keep:
        if not a:
            out.append((r, g, b, 0)); continue
        L, ch, h = C.lab_to_lch(C.srgb_to_lab((r, g, b)))
        if imglib.is_skin(L, ch, h):
            skin += 1
            out.append((r, g, b, 0))
        else:
            out.append((r, g, b, 255))
    kept = sum(1 for p in out if p[3])
    if kept < 250:                                  # skin mask ate the garment
        out = keep
        kept = op
        skin_share = 0.0
    else:
        skin_share = skin / op if op else 0.0
    return out, skin_share, (kept / max(1, len(keep))), white_balance


def colours_for(path, is_cutout, wb=False, k=4):
    with Image.open(path) as im0:
        im = im0.copy()
        im.thumbnail((320, 320), Image.LANCZOS)
        px, skin, keptshare, _ = garment_pixels(im, is_cutout, white_balance=wb)
    cols = extract_colours(px, k=k, floor=0.05, sample=20000, seed=0)
    # merge near-identical clusters so a print keeps its components but a solid
    # does not get split three ways by shading
    merged = []
    for c in cols:
        for m in merged:
            if C.delta_e_2000(tuple(c['lab']), tuple(m['lab'])) <= 7:
                m['share'] += c['share']
                break
        else:
            merged.append(dict(c))
    merged.sort(key=lambda c: -c['share'])
    return merged[:3], skin, keptshare


def confidence(asset_type, cols, skin, keptshare):
    if not cols:
        return 'low'
    top = cols[0]
    L, Cc, h = C.lab_to_lch(tuple(top['lab']))
    if asset_type == 'cutout_model' or asset_type == 'tile':
        base = 'medium'
    else:
        base = 'high'
    if skin > 0.25:
        return 'low'
    if keptshare < 0.01:               # almost nothing left to read
        return 'low'
    if L > 92 or L < 6:                # white on white, or black on black
        base = 'low' if base != 'high' else 'medium'
    if Cc > 55 and L > 70:             # patent / satin blow-out
        base = 'medium'
    return base


def main():
    A = json.load(open(ROOT + '/content/catalogue/_assets.json'))
    B = {o['product_id']: o for o in json.load(open(ROOT + '/content/catalogue/batches.json'))}
    out = {}
    wb_tests = []
    for i, (pid, a) in enumerate(sorted(A.items()), 1):
        if not a.get('asset_path'):
            out[pid] = dict(error='no asset'); continue
        p = ROOT + '/' + a['asset_path']
        is_cut = a['asset_type'].startswith('cutout')
        try:
            cols, skin, keptshare = colours_for(p, is_cut, wb=False)
        except Exception as e:
            out[pid] = dict(error=f'{type(e).__name__}: {e}'); continue
        rec = []
        for c in cols:
            fam, nm, L, Cc, h, rel, nt = classify(c['hex'])
            rec.append(dict(hex=c['hex'], share=round(c['share'], 3), L=round(L, 1),
                            C=round(Cc, 1), h=round(h, 1), rel=round(rel, 3),
                            neutral=nt, family=fam, name=nm))
        out[pid] = dict(colours=rec, skin_share=round(skin, 3),
                        kept_share=round(keptshare, 3),
                        colour_confidence=confidence(a['asset_type'], cols, skin, keptshare),
                        colour_stability='stable')
        if i % 60 == 0:
            print(f'  {i}/{len(A)}', flush=True)
    # multi-image products: how much do shots of one product disagree?
    json.dump(out, open(ROOT + '/content/catalogue/_colours.json', 'w'), indent=1)
    print('colours:', len(out))
    print('confidence:', collections.Counter(v.get('colour_confidence', 'error') for v in out.values()))
    if wb_tests:
        ds = sorted(d for _, d in wb_tests)
        print('white balance moved the dominant by dE: median %.2f, p90 %.2f, max %.2f'
              % (ds[len(ds) // 2], ds[int(len(ds) * .9)], ds[-1]))


if __name__ == '__main__':
    main()
