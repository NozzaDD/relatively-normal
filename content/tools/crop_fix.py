"""Crops that lose what is in the screenshot — 25 September, Part 1.

Every picture the desk shows is a rectangle of an original screenshot, made in
up to three steps:

  1. build_review_images.full_photo: Safari's chrome trimmed off, then the
     photograph picked out of the page by imglib.product_box (the largest blob
     that is not the page colour and not type, at 200 px wide, padded 4%) and
     its type-heavy edges eaten by OCR. This is `origin` in _review_boxes.json,
     the "full photo" of the desk.
  2. panels.py: a page of stacked photographs split into panels — `panel_box`,
     as fractions of the review copy.
  3. read_grids.py / grid_cells.py: a listing grid's cells — the cell's box,
     again as fractions of the grid's review copy.

The shelf cut-out and every whole cut-out are cut from one of those
rectangles, so they can only keep what it holds. Step 1 is where handles and
straps were lost: at 200 px wide a handle is one or two pixels, its cells are
edge-dense enough to be taken for type, and the blob it belonged to became the
bag's body alone.

This module asks, of every picture, what the screenshot says: where is the
piece, all of it? It reads the screenshot itself (chrome trimmed), marks what
is neither the photograph's backdrop nor the page's own colour, and follows
the pieces the crop holds out past its edges. Then:

  ok       nothing the crop holds runs past its edge
  cut      the piece runs past the crop's edge but stops inside the screenshot:
           the crop lost it. `widened` is the piece's own bounds plus a margin.
  clipped  the piece reaches the screenshot's own edge (the page scrolled it
           away, or the shop's photo panel is the screen): no crop can help.

  python3 content/tools/crop_fix.py --measure [--only PID ...]   -> _crop_fix.json
"""
import os, sys, json, argparse
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
CAT = ROOT + '/content/catalogue'
STUDIO = ROOT + '/studio'
OUT = CAT + '/_crop_fix.json'

WORK = 760            # the screenshot is read at this width
DIFF = 40             # sum of |RGB| difference that is "not this colour" (product_box's)
MARGIN = 0.05         # of the piece's own size, each side
MARGIN_MIN = 12       # screenshot pixels, at least
FILL_MAX = 0.9        # a "piece" filling this much of its own bounds is the whole photo
SKIP_TYPES = ('detail', 'text', 'other', 'listing grid')


def load(name, default):
    try:
        return json.load(open(CAT + '/' + name))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def picture_rect(p, idx, review):
    """The picture's rectangle in its screenshot's pixels [x0, y0, x1, y1],
    with the screenshot's path — the review crop, then the panel or cell box."""
    imgs = p.get('images') or []
    if idx >= len(imgs):
        return None, None
    e = imgs[idx]
    src = e.get('source')
    if not src or not os.path.exists(ROOT + '/' + src):
        return None, None
    rv = review.get(p['product_id']) or review.get(p.get('parent_id') or '') or {}
    rimgs = rv.get('images') or []
    j = e.get('panel_of', idx) or 0
    origin = (rimgs[j].get('origin') if j < len(rimgs) and rimgs[j] else None) or rv.get('origin')
    if not origin:
        return None, src
    x, y, w, h = origin[:4]
    pb = e.get('panel_box') or [0, 0, 1, 1]
    at = lambda b: [x + b[0] * w, y + b[1] * h, x + (b[0] + b[2]) * w, y + (b[1] + b[3]) * h]  # noqa: E731
    size = [origin[4] if len(origin) > 4 else None, origin[5] if len(origin) > 5 else None]
    # the photograph's own bounds, where the page says them: a panel was split
    # off at a gutter, so the panel IS the photograph
    # (a reader's tile box is not used: some cut the handle off themselves;
    # the tile's own backdrop, stopped at its gutter, bounds a cell instead)
    frame = None
    if e.get('type') != 'cell' and pb != [0, 0, 1, 1]:
        frame = at(pb)
    return at(pb) + size + [frame], src


_TILES = {}


def cell_tiles():
    """{review path of a cell: the reader's tile box, as fractions of the grid's review copy}."""
    if not _TILES:
        for v in load('_grid_cells.json', {}).values():
            for c in v.get('cells', []):
                if c.get('path') and c.get('read_box'):
                    _TILES[c['path']] = c['read_box']
    return _TILES


def modal(px):
    """The most common colour of an (n, 3) array, quantised to 4 levels: 16
    put a page's 248 white and a photograph's 240 grey in one bin (the
    Longchamp pages), and the photograph's edge was lost."""
    q = (np.asarray(px) // 4).astype(np.int64)
    k = q[:, 0] * 4096 + q[:, 1] * 64 + q[:, 2]
    v = np.bincount(k).argmax()
    return np.array([(v // 4096) * 4 + 2, (v // 64 % 64) * 4 + 2, (v % 64) * 4 + 2], np.float32)


_SHOT = {}


def screenshot(src):
    """(work RGB array, scale work/original, page box in work pixels)."""
    if src not in _SHOT:
        import imglib
        with Image.open(ROOT + '/' + src) as im0:
            im = im0.convert('RGB')
            l, t, r, b = imglib.trim_chrome(im)
            k = WORK / im.width
            small = im.resize((WORK, max(1, round(im.height * k))), Image.BILINEAR)
        a = np.asarray(small, np.float32)
        page = (int(l * k), int(t * k), min(a.shape[1], int(np.ceil(r * k))), min(a.shape[0], int(np.ceil(b * k))))
        if len(_SHOT) > 8:
            _SHOT.clear()
        _SHOT[src] = (a, k, page, im.size)
    return _SHOT[src]


def measure_rect(src, rect):
    """-> dict(state, rect, piece, widened, touches) in screenshot pixels."""
    from scipy import ndimage
    a, k, (pl, pt, pr, pb), (OW, OH) = screenshot(src)
    x0, y0, x1, y1 = rect[:4]
    if rect[4] and rect[4] != OW:                 # re-exported at another size
        s = OW / rect[4]
        x0, y0, x1, y1 = x0 * s, y0 * s, x1 * s, y1 * s
    X0, Y0 = max(pl, int(x0 * k)), max(pt, int(y0 * k))
    X1, Y1 = min(pr, int(np.ceil(x1 * k))), min(pb, int(np.ceil(y1 * k)))
    if X1 - X0 < 12 or Y1 - Y0 < 12:
        return dict(state='tiny')
    page = a[pt:pb, pl:pr]
    crop = a[Y0:Y1, X0:X1]
    # the photograph's backdrop: the commonest colour of the crop's outer ring;
    # the page's own colour: the commonest colour of the whole page
    ring = np.concatenate([crop[:2].reshape(-1, 3), crop[-2:].reshape(-1, 3),
                           crop[:, :2].reshape(-1, 3), crop[:, -2:].reshape(-1, 3)])
    bg, pg = modal(ring), modal(page.reshape(-1, 3))
    cy0, cy1, cx0, cx1 = Y0 - pt, Y1 - pt, X0 - pl, X1 - pl
    H, W = page.shape[:2]
    # a crop that overhangs its photograph has the page's own colour on its
    # ring; the photograph's backdrop is then the commonest colour inside the
    # crop that is not the page's, where that is a studio backdrop (light,
    # neutral) and not the garment (the Longchamp pages: page 248, photo 240)
    if np.abs(bg - pg).sum() <= DIFF // 2:
        inner = crop.reshape(-1, 3)
        inner = inner[(np.abs(inner - pg).sum(1) > DIFF // 2) & (inner.min(1) >= 190)
                      & (inner.max(1) - inner.min(1) <= 24)]
        if len(inner) > 0.1 * crop.shape[0] * crop.shape[1]:
            bg = modal(inner)
    # the photograph the crop sits in: the backdrop's own colour, connected,
    # from the crop's ring outwards. A grid tile ends at its gutter, a panel
    # at the next photograph; nothing is taken from beyond it.
    near_bg = np.abs(page - bg).sum(2) <= DIFF // 2
    blab, _ = ndimage.label(near_bg)
    # the ring, and the backdrop just inside it: an overhanging crop's ring is
    # all page, and the photograph starts a little way in
    inset = max(2, int(0.03 * min(cx1 - cx0, cy1 - cy0)))
    ringlab = np.concatenate([blab[cy0, cx0:cx1], blab[cy1 - 1, cx0:cx1], blab[cy0:cy1, cx0], blab[cy0:cy1, cx1 - 1],
                              blab[cy0 + inset, cx0:cx1], blab[cy1 - 1 - inset, cx0:cx1],
                              blab[cy0:cy1, cx0 + inset], blab[cy0:cy1, cx1 - 1 - inset]])
    ringlab = ringlab[ringlab > 0]
    if len(ringlab):
        # every backdrop region the ring runs through for a real share of it,
        # not only the largest: a crop whose edge crosses a bag's handle loop
        # has the loop's inside on its ring, and that alone would end the
        # photograph below the handle (the Longchamp hobos, 25 Sept)
        cnt = np.bincount(ringlab)
        labs = [l for l in np.nonzero(cnt)[0] if l and cnt[l] >= 0.05 * len(ringlab)]
        sl = ndimage.find_objects(np.isin(blab, labs).astype(np.int32))[0]
        fx0, fx1 = min(cx0, sl[1].start), max(cx1, sl[1].stop)
        fy0, fy1 = min(cy0, sl[0].start), max(cy1, sl[0].stop)
    else:
        fx0, fy0, fx1, fy1 = cx0, cy0, cx1, cy1
    frame = rect[6] if len(rect) > 6 else None
    if frame:
        s_ = (OW / rect[4]) if rect[4] and rect[4] != OW else 1.0
        gx0, gy0 = int(frame[0] * s_ * k) - pl, int(frame[1] * s_ * k) - pt
        gx1, gy1 = int(np.ceil(frame[2] * s_ * k)) - pl, int(np.ceil(frame[3] * s_ * k)) - pt
        fx0, fy0 = max(fx0, min(gx0, cx0)), max(fy0, min(gy0, cy0))
        fx1, fy1 = min(fx1, max(gx1, cx1)), min(fy1, max(gy1, cy1))
    mask = (np.abs(page - bg).sum(2) > DIFF) & (np.abs(page - pg).sum(2) > DIFF)
    # any light, neutral expanse that reaches the crop's ring is a backdrop —
    # a grid tile's grey, a page's white — whichever side of a threshold its
    # exact shade falls: without this a tile 42 levels off the page read as
    # "the piece" and ran to the screenshot's edge (nine bags called clipped)
    light = (page.min(2) >= 200) & ((page.max(2) - page.min(2)) <= 22)
    llab, _ = ndimage.label(light)
    ring_l = np.unique(np.concatenate([llab[cy0, cx0:cx1], llab[cy1 - 1, cx0:cx1],
                                       llab[cy0:cy1, cx0], llab[cy0:cy1, cx1 - 1]]))
    ring_l = ring_l[ring_l > 0]
    if len(ring_l):
        mask &= ~np.isin(llab, ring_l)
    # outside the photograph nothing belongs to the piece
    frame = np.zeros_like(mask)
    frame[fy0:fy1, fx0:fx1] = True
    mask &= frame
    lab, n = ndimage.label(mask, structure=np.ones((3, 3)))
    if not n:
        return dict(state='empty')
    # a gutter or a rule between photographs is a line, not a piece
    thin = max(3, int(0.006 * WORK))
    for c, sl in enumerate(ndimage.find_objects(lab), 1):
        if sl is None:
            continue
        hh, ww = sl[0].stop - sl[0].start, sl[1].stop - sl[1].start
        if min(hh, ww) <= thin and max(hh, ww) >= 8 * min(hh, ww):
            lab[sl][lab[sl] == c] = 0
    inside = lab[cy0:cy1, cx0:cx1]
    cnt = np.bincount(inside.ravel(), minlength=n + 1)
    cnt[0] = 0
    if cnt.max() < 0.003 * inside.size:
        return dict(state='empty')
    # the piece: what the crop holds that is big enough to be it — letters of
    # the page's type and specks are left out
    keep = [c for c in np.nonzero(cnt)[0] if cnt[c] >= max(0.05 * cnt.max(), 0.003 * inside.size)]
    objs = ndimage.find_objects(lab)
    bx0 = min(objs[c - 1][1].start for c in keep); bx1 = max(objs[c - 1][1].stop for c in keep)
    by0 = min(objs[c - 1][0].start for c in keep); by1 = max(objs[c - 1][0].stop for c in keep)
    # clipped is asked of the main piece alone — the largest thing the crop
    # holds — not of a toolbar, a buy button or a swatch row the crop also
    # holds, which reach the screen's edge by design
    main = int(np.argmax(cnt))
    ms = objs[main - 1]
    mx0, mx1, my0, my1 = ms[1].start, ms[1].stop, ms[0].start, ms[0].stop
    touches = [s for s, v in (('top', my0 <= 0), ('bottom', my1 >= H), ('left', mx0 <= 0), ('right', mx1 >= W)) if v]
    # the shop's photograph ends inside the page and the piece runs to it:
    # cut off by the shop's photo, which no crop of the screenshot can undo
    photo_edge = [s for s, v in (('top', by0 <= fy0 and fy0 > 0), ('bottom', by1 >= fy1 and fy1 < H),
                                 ('left', bx0 <= fx0 and fx0 > 0), ('right', bx1 >= fx1 and fx1 < W))
                  if v and s not in touches]
    out_of_crop = bx0 < cx0 or by0 < cy0 or bx1 > cx1 or by1 > cy1
    # tight against the crop's own edge counts too: no margin, a crop edge
    near = max(1, int(0.004 * WORK))
    tight = [s for s, v in (('top', by0 <= cy0 + near - 1 and cy0 > 0), ('bottom', by1 >= cy1 - near + 1 and cy1 < H),
                            ('left', bx0 <= cx0 + near - 1 and cx0 > 0), ('right', bx1 >= cx1 - near + 1 and cx1 < W))
             if v and s not in touches]
    # a piece on a backdrop leaves backdrop inside its own bounds; a whole
    # photograph taken for the piece (a model shot filling the width, a
    # coloured studio wall) fills them. Then nothing here can say where the
    # piece ends, and the picture is `unmeasured`, never clipped or widened.
    inbox = lab[my0:my1, mx0:mx1] == main
    fill = float(inbox.mean()) if inbox.size else 0.0
    to_orig = lambda v, o: (v + o) / k                      # noqa: E731
    piece = [to_orig(bx0, pl), to_orig(by0, pt), to_orig(bx1, pl), to_orig(by1, pt)]
    photo = [to_orig(fx0, pl), to_orig(fy0, pt), to_orig(fx1, pl), to_orig(fy1, pt)]
    res = dict(piece=[round(v) for v in piece], touches=touches, photo_edge=photo_edge,
               photo=[round(v) for v in photo], crop=[round(v) for v in (x0, y0, x1, y1)], fill=round(fill, 3))
    if fill >= FILL_MAX:
        res['state'] = 'unmeasured'
        return res
    tight = [t for t in tight if t not in photo_edge]
    if not out_of_crop and not tight:
        res['state'] = 'clipped' if touches else 'photo_edge' if photo_edge else 'ok'
        return res
    pw, ph = piece[2] - piece[0], piece[3] - piece[1]
    mx, my = max(MARGIN_MIN, MARGIN * pw), max(MARGIN_MIN, MARGIN * ph)
    # the margin stays inside the photograph (and the screenshot)
    L, T, R, B = max(pl / k, photo[0]), max(pt / k, photo[1]), min(pr / k, photo[2]), min(pb / k, photo[3])
    wid = [max(L, min(x0, piece[0] - mx)), max(T, min(y0, piece[1] - my)),
           min(R, max(x1, piece[2] + mx)), min(B, max(y1, piece[3] + my))]
    res.update(state='cut', widened=[round(v) for v in wid], clipped=bool(touches),
               grew=round((wid[2] - wid[0]) * (wid[3] - wid[1]) / max(1, (x1 - x0) * (y1 - y0)), 3))
    return res


def clear_of(box, crop, others):
    """A widened grid cell may not reach into another cell's tile: on a grid
    with one seamless backdrop nothing else stops it (25 Sept: 42 cells took
    in the next tile's garment). Each side that overlaps a neighbour's tile is
    pulled back to that tile's edge, never inside the cell's own crop.
    All boxes [x0, y0, x1, y1] in one frame."""
    x0, y0, x1, y1 = box
    for o in others:
        if o[2] <= x0 or o[0] >= x1 or o[3] <= y0 or o[1] >= y1:
            continue                                  # no overlap
        cx, cy = (crop[0] + crop[2]) / 2, (crop[1] + crop[3]) / 2
        ox, oy = (o[0] + o[2]) / 2, (o[1] + o[3]) / 2
        if abs(ox - cx) / max(1, o[2] - o[0]) >= abs(oy - cy) / max(1, o[3] - o[1]):
            if ox > cx:
                x1 = max(crop[2], min(x1, o[0]))
            else:
                x0 = min(crop[0], max(x0, o[2]))
        else:
            if oy > cy:
                y1 = max(crop[3], min(y1, o[1]))
            else:
                y0 = min(crop[1], max(y0, o[3]))
    return [x0, y0, x1, y1]


def widen(src, rect, frame=None, others=()):
    """THE CROP RULE: a crop holds the whole piece plus a margin. `rect` is
    [x0, y0, x1, y1] in the screenshot's pixels; returns it widened until the
    piece clears every edge that is not the screenshot's own (or its
    photograph's, where `frame` names it), with the measurement.
    Used by build_review_images.full_photo and read_grids when they crop."""
    with Image.open(ROOT + '/' + src) as im:
        W, H = im.size
    r = measure_rect(src, list(rect[:4]) + [W, H, frame])
    if r.get('state') == 'cut':
        w = clear_of(r['widened'], rect[:4], others) if others else r['widened']
        return [int(round(v)) for v in w], r
    return [int(round(v)) for v in rect[:4]], r


def pictures(products):
    """Every picture once: {(source, rounded rect): [(pid, idx), ...]}."""
    review = load('_review_boxes.json', {})
    seen = {}
    for p in products:
        for i, e in enumerate(p.get('images') or []):
            if e.get('type') in SKIP_TYPES:
                continue
            rect, src = picture_rect(p, i, review)
            if not rect:
                continue
            key = (src, tuple(round(v) for v in rect[:4]))
            rect = rect[:6] + [rect[6]]
            seen.setdefault(key, dict(rect=rect, users=[]))['users'].append([p['product_id'], i])
    return seen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--measure', action='store_true')
    ap.add_argument('--only', nargs='*')
    a = ap.parse_args()
    products = json.load(open(STUDIO + '/data/products.json'))
    if a.only:
        products = [p for p in products if p['product_id'] in a.only]
    pics = pictures(products)
    out = []
    for n, ((src, _), v) in enumerate(sorted(pics.items())):
        r = measure_rect(src, v['rect'])
        out.append(dict(source=src, rect=[round(x, 1) if x else x for x in v['rect'][:6]],
                        frame=[round(x, 1) for x in v['rect'][6]] if v['rect'][6] else None,
                        users=v['users'], **r))
        if n % 200 == 0:
            print(n, '/', len(pics), file=sys.stderr)
    if not a.only:
        json.dump(out, open(OUT, 'w'), indent=0)
    from collections import Counter
    print(Counter(x['state'] for x in out))
    return out


if __name__ == '__main__':
    r = main()
    if len(r) < 20:
        for x in r:
            print(json.dumps(x))
