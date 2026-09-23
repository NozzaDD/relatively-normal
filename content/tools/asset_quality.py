"""Downgrade assets that show a person rather than a piece.

Background removal on a detail shot happily returns a model's head, and a head
is not a bag. Any cut-out that is mostly skin and hair is marked weak so the
board picker will not use it; the row stays in the catalogue with the reason.

Only new or changed products are rated (see incremental.py); `--all` re-rates
every one.
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from PIL import Image
import imglib
from engine import colour as C

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SKIN_MAX = 0.65        # legs and arms in a cropped figure are fine; a head is not


def alpha_fill(path):
    """How much of its own bounding box a cut-out fills.

    A cut-out that fills its box is a rectangle, and a rectangle is a page panel
    — a size guide, a promo card, a grey placeholder — not a garment."""
    with Image.open(path) as im0:
        a = im0.convert('RGBA').getchannel('A').point(lambda v: 255 if v > 200 else 0)
        bb = a.getbbox()
        if not bb:
            return 0.0
        n = sum(a.crop(bb).histogram()[255:])
        return n / max(1, (bb[2] - bb[0]) * (bb[3] - bb[1]))


def skin_share(path):
    with Image.open(path) as im0:
        im = im0.convert('RGBA')
        im.thumbnail((160, 160), Image.LANCZOS)
        px = list(im.getdata())
    op = skin = 0
    cache = {}
    for r, g, b, a in px:
        if a < 200:
            continue
        op += 1
        k = (r >> 3, g >> 3, b >> 3)
        v = cache.get(k)
        if v is None:
            L, ch, h = C.lab_to_lch(C.srgb_to_lab((r, g, b)))
            v = cache[k] = imglib.is_skin(L, ch, h) or (18 <= h <= 70 and ch <= 12 and L <= 40)
        skin += v
    return skin / max(1, op)


import re


def base_quality(a):
    """The quality make_assets gave it, rebuilt from its note so this tool can be
    re-run with a different threshold without regenerating every asset."""
    note = a.get('note', '')
    found = 'box found' in note
    if a['asset_type'] == 'tile':
        m = re.search(r'([\d.]+)% of page', note)
        area = float(m.group(1)) / 100 if m else 0
        return 'good' if (found and 0.05 <= area <= 0.85) else ('usable' if found else 'weak')
    m = re.search(r'(\d+) components', note)
    nb = int(m.group(1)) if m else 9
    return 'good' if (found and nb <= 4) else 'usable'


def main():
    import incremental as INC
    A = json.load(open(ROOT + '/content/catalogue/_assets.json'))
    # new or changed products only, unless --all: a product the owner has
    # reviewed keeps the rating it was reviewed with
    cands = [pid for pid, a in sorted(A.items())
             if a.get('asset_path') and a['asset_type'].startswith('cutout')]
    todo, fp = INC.select('asset_quality', cands)
    INC.report('asset_quality', todo, cands)
    n = 0
    for pid in todo:
        a = A[pid]
        s = skin_share(ROOT + '/' + a['asset_path'])
        fill = alpha_fill(ROOT + '/' + a['asset_path'])
        a['alpha_fill'] = round(fill, 3)
        a['skin_share'] = round(s, 3)
        a['note'] = re.sub(r'; \d+% skin and hair[^;]*', '', a.get('note', ''))
        a['asset_quality'] = base_quality(a)
        a['note'] = re.sub(r'; rectangular[^;]*', '', a['note'])
        if s > SKIN_MAX:
            a['asset_quality'] = 'weak'
            a['note'] += '; %d%% skin and hair — the cut-out found the model, not the piece' % round(s * 100)
            n += 1
        elif fill > 0.90:
            a['asset_quality'] = 'weak'
            a['note'] += '; rectangular (%d%% of its own box) — a page panel, not a piece' % round(fill * 100)
            n += 1
    json.dump(A, open(ROOT + '/content/catalogue/_assets.json', 'w'), indent=1)
    INC.mark('asset_quality', todo, fp)
    print('marked weak:', n)


if __name__ == '__main__':
    main()
