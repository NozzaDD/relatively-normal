"""The shelf gate for listing-grid cells read by eye.

flat_lays.py's four questions were written for rembg cut-outs of arbitrary
screenshots, where a person or the page's edge in the picture means the piece
is not a packshot. A cell a reader took off a shop's category page is a
packshot by construction, and the reader already left out every tile the page
cut off. Two of the questions then only ever say no for the wrong reason:

  - "someone is wearing it", the skin share: tan, brown, camel and burgundy
    leather and a ballet flat's pink lining sit inside the skin band
    (imglib.is_skin, CLAUDE.md hard rule 6). 30 of the 66 cells of 24 Sept.
  - "clear of the frame": a shop crops its tiles tight, so a boot's heel
    touches the tile's edge.

For eye-read cells only, the gate keeps the questions that still mean
something about the cut-out itself:

  - one piece                  (components == 1)
  - no text inside it          (words_inside == 0)
  - not a sliver               (the piece fills at least FILL of its own box,
                                and its box is no longer than ASPECT to 1)
  - not too small              (the shorter side of the piece at least MIN_SIDE px)

A person then looks: every cell this gate would move to the shelf goes on a
contact sheet (`--sheets DIR`, 30 a sheet), and any that is on a model, a
lifestyle photo, a logo tile or otherwise not a single product is listed in
HELD with the reason. Those stay in Review.

Writes the verdict into _grid_cells.json (`gate: "eye"`, `clean`, `why`) and
_flat_lays.json under the cell's ID (`measured_by: "eye_gate"`), which is what
the shelf gate reads. Cells from the geometric pass keep flat_lays.py's gate.

  python3 content/tools/eye_gate.py --check          # counts only
  python3 content/tools/eye_gate.py --sheets DIR     # the safety pass's sheets
  python3 content/tools/eye_gate.py                  # apply
"""
import os, sys, json, argparse, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image
import read_grids as RG

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CAT = ROOT + '/content/catalogue'
FILL = 0.2          # a piece that fills less of its own box is a strap, a lace, a sliver
ASPECT = 8.0        # a belt laid flat is about 1:8; longer is a line, not a garment
MIN_SIDE = 60       # the same floor read_grids.py always used

# The safety pass of 24 Sept, 18 contact sheets of the 521 cells the gate
# would move: the premise that a category page is a packshot holds for most
# shops and not for all. CLOSED, Toteme, Lemaire, Studio Nicholson and others
# show their grids on models. Only cells the gate would MOVE are held; a cell
# already on the shelf passed the old, stricter gate.
# Whole grid pages where every moving tile was on a model: {grid row: reason}
HELD_GRIDS = {
    'B018-P003': 'on a model',
    'B019-P006': 'on a model',
    'B019-P007': 'on a model',
    'B020-P002': 'on a model',
    'B020-P005': 'on a model',
    'B021-P007': 'on a model',
    'B021-P008': 'on a model',
    'B023-P009': 'on a model',
    'B023-P011': 'on a model',
    'B023-P015': 'on a model',
    'B023-P016': 'on a model',
    'B023-P017': 'on a model',
    'B024-P001': 'on a model',
    'B024-P002': 'on a model',
    'B024-P003': 'on a model',
    'B024-P004': 'on a model',
    'B024-P005': 'on a model',
    'B024-P006': 'on a model',
    'B026-P001': 'on a model',
    'B026-P002': 'on a model',
    'B026-P003': 'on a model',
    'B026-P004': 'on a model',
    'B026-P005': 'on a model',
    'B026-P006': 'on a model',
    'B026-P007': 'on a model',
    'B026-P008': 'on a model',
    'B026-P011': 'on a model',
    'B027-P009': 'on a model',
    'B027-P011': 'on a model',
    'B030-P007': 'on a model',
    'B032-P003': 'on a model',
    'B033-P003': 'on a model',
    'B034-P001': 'on a model',
    'B034-P003': 'on a model',
    'B036-P008': 'on a model',
    'B039-P004': 'on a model',
    'B044-P020': 'on a model',
    'B045-P001': 'on a model',
    'B052-P007': 'on a model',
    'B053-P002': 'on a model',
    'B057-P004': 'on a model',
    'B065-P001': 'on a model',
    'B065-P004': 'on a model',
}
# Single cells: {cell id: reason}
HELD = {
    'B023-P004-C4': 'on a model',
    'B023-P007-C0': 'on a model',
    'B023-P008-C0': 'on a model',
    'B023-P010-C1': 'on a model',
    'B023-P010-C2': 'on a model',
    'B023-P010-C5': 'on a model',
    'B023-P014-C1': 'on a model',
    'B023-P014-C2': 'on a model',
    'B023-P014-C4': 'on a model',
    'B023-P014-C5': 'on a model',
    'B028-P010-I3-C0': 'on a model',
    'B028-P011-C1': 'on a model',
    'B030-P006-C0': 'on a model',
    'B033-P002-I1-C0': 'on a model',
    'B034-P004-C1': 'on a model',
    'B036-P001-C1': 'on a model',
    'B036-P005-C0': 'on a model',
    'B036-P007-C1': 'on a model',
    'B042-P006-C0': 'a hanger and a wooden prop are part of the cut-out',
    'B042-P006-C1': 'a hanger and a wooden prop are part of the cut-out',
    'B042-P007-C1': 'a hanger and a wooden prop are part of the cut-out',
    'B044-P015-C1': 'on a model',
    'B046-P008-C0': 'on a model',
    'B062-P018-C0': 'worn: a foot in the shoe, legs in frame',
    'B062-P019-C1': 'a close-up of leather, not the boot the caption names',
    'B062-P020-C0': 'worn: a foot in the sandal, jeans in frame',
    'B062-P020-C1': 'worn: a foot in the sandal',
    'B069-P002-C2': 'on a model',
    'B071-P002-C3': 'on a model',
    'B071-P003-C5': 'on a model',
    'B071-P004-C2': 'on a model',
    'B071-P005-C5': 'a shop badge is left in the cut-out',
    'B076-P003-C0': 'on a model',
    'B078-P007-C0': 'worn: legs and feet in the shoes',
    'B078-P007-C5': 'worn: trousers and a foot in the shoe',
    'B078-P008-C3': 'worn: trousers and a foot in the shoe',
}


def held(cid):
    """Why the safety pass kept a cell back, or None."""
    if cid in HELD:
        return HELD[cid]
    grid = cid.split('-I')[0].rsplit('-C', 1)[0]
    return HELD_GRIDS.get(grid)


def measure(path):
    with Image.open(path) as im:
        a = np.asarray(im.convert('RGBA'))[..., 3] > 128
    if not a.any():
        return dict(fill=0.0, aspect=0.0, side=0)
    ys, xs = np.nonzero(a)
    h, w = ys.max() - ys.min() + 1, xs.max() - xs.min() + 1
    return dict(fill=round(float(a[ys.min():ys.max() + 1, xs.min():xs.max() + 1].mean()), 3),
                aspect=round(float(max(w, h) / max(1, min(w, h))), 2), side=int(min(w, h)))


def verdict(c):
    """(clean, why) for one eye-read cell, from its stored measurements."""
    if not c.get('cut') or not os.path.exists(CAT + '/' + c['cut']):
        return False, 'nothing cut', {}
    m = measure(CAT + '/' + c['cut'])
    why = []
    if c.get('components', 0) != 1:
        why.append('more than one piece')
    if c.get('words_inside', 0):
        why.append('text inside it')
    if m['fill'] < FILL or m['aspect'] > ASPECT:
        why.append('a sliver')
    if m['side'] < MIN_SIDE:
        why.append('too small')
    return not why, ', '.join(why), m


def cells():
    g = json.load(open(CAT + '/_grid_cells.json'))
    for key, rec in sorted(g.items()):
        if rec.get('source') != 'eye':
            continue
        pid, idx = key.split('#')[0], int(key.split('#')[1])
        for j, c in enumerate(rec.get('cells') or []):
            yield g, key, j, RG.cell_id(pid, idx, j), c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--sheets', metavar='DIR')
    a = ap.parse_args()
    flats = json.load(open(CAT + '/_flat_lays.json'))
    g = None
    stats, moving, why_not = collections.Counter(), [], collections.Counter()
    for g, key, j, cid, c in cells():
        before = bool((flats.get(cid) or {}).get('clean'))
        ok, why, m = verdict(c)
        if ok and not before and held(cid):
            ok, why = False, 'held by eye: ' + held(cid)
        stats[(before, ok)] += 1
        if ok and not before:
            moving.append((cid, c))
        if not ok:
            why_not[why] += 1
        if not a.check and not a.sheets:
            c.update(gate='eye', clean=ok, why=why, fill=m.get('fill'), aspect=m.get('aspect'))
            flats[cid] = dict(flats.get(cid) or {}, clean=ok, why=why, flat=True,
                              from_cell=c.get('cut') or c['path'], measured_by='eye_gate')
    print('eye-read cells: clean before -> after:', dict(stats))
    print('moving to the shelf:', len(moving), ' held back:', dict(why_not))
    if a.sheets:
        from contact_sheet import sheet
        os.makedirs(a.sheets, exist_ok=True)
        for k in range(0, len(moving), 30):
            sheet([{'path': CAT + '/' + c['cut'], 'label': f"{cid}\n{c.get('garment', '')[:30]}"}
                   for cid, c in moving[k:k + 30]], f'{a.sheets}/eye-gate-{k // 30:02d}.jpg', cols=6, cell=240)
        print('sheets:', (len(moving) + 29) // 30, '->', a.sheets)
    if not a.check and not a.sheets:
        json.dump(g, open(CAT + '/_grid_cells.json', 'w'), indent=1)
        json.dump(flats, open(CAT + '/_flat_lays.json', 'w'), indent=1)


if __name__ == '__main__':
    main()
