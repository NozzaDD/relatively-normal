"""Read the colourway row off any shop's product page, not only UNIQLO's.

Shops show the colours a style comes in under a line that says "Colour:" or
"Color:", followed by the selected colour's name:

  UNIQLO               circles of the fabric                (uniqlo_pages.py)
  Johnstons of Elgin   rounded squares of the fabric, 5 to 14
  Toast                small photographs of the garment in each colour
  Colorful Standard    small photographs of the garment in each colour

This finds that line by OCR, takes the band beneath it down to the next line
of text, and reads every swatch in the band: where it is, how big, whether it
is the selected one, and what it shows.

  kind = fabric    a flat patch of colour (circle or square): the swatch's
                   centre is sampled, as uniqlo_pages.py does
  kind = photo     a small picture of the garment on a pale ground: the
                   garment is found against the thumbnail's own corners and
                   its median colour is recorded; the thumbnail itself is kept
                   so the variant can be cut from the brand's own photograph

Names: only the selected swatch has one, and only because the page prints it
after "Colour:". The others get none. Nothing here guesses a name.

The selected swatch is told by its frame: every shop here draws a dark border
or ring around the selected one and nothing around the rest, so it is the one
whose outer band is much darker than its neighbours'.

  python3 content/tools/colourway_pages.py            # every row of the shops in SHOPS
  python3 content/tools/colourway_pages.py IMG_1137 eu.toa.st   # one screenshot, printed

Writes content/catalogue/_colourway_pages.json keyed by image path. UNIQLO is
left to uniqlo_pages.py, whose reading is already checked against the pages.
"""
import sys, os, re, json, csv
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import numpy as np
from PIL import Image
from scipy import ndimage
import pytesseract
from engine import colour as EC
from colour_names import classify
from uniqlo_pages import lines_of

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CAT = ROOT + '/content/catalogue'
OUT = CAT + '/_colourway_pages.json'

# shop (as build_products.py files it) -> where the buy panel starts, as a share
# of the width. Portrait pages put the buy panel under the photo on some shops;
# 0 means read the whole width.
# kind is the shop's, not guessed per swatch: a Johnstons fabric square has a
# pale rim that reads as a thumbnail's ground to any per-blob test.
SHOPS = {
    'johnstonsofelgin.com': dict(panel_x=0.52, kind='fabric'),
    'eu.toa.st': dict(panel_x=0.55, kind='photo'),
    'colorfulstandard.com': dict(panel_x=0.0, kind='photo'),
}
END_LINE = re.compile(r'^(Size|SIZE|Add|ADD|Größe)')
COLOUR_LINE = re.compile(r'\bColou?r\s*[:;]\s*(.+)$', re.I)


def colour_line(lines):
    for i, l in enumerate(lines):
        m = COLOUR_RE_MATCH(l['text'])
        if m:
            return i, l, m
    return None, None, None


def COLOUR_RE_MATCH(t):
    m = COLOUR_LINE.search(t.strip())
    if not m:
        return None
    name = re.sub(r'[^A-Za-z \-\'&]', '', m.group(1)).strip()
    return name or None


def rgb_to_lab(rgb):
    return list(EC.srgb_to_lab(tuple(int(round(v)) for v in rgb)))


def frame_darkness(arr, x0, y0, x1, y1):
    """How dark the swatch's frame is: the darker of its own outermost band
    (a frame that fills was merged into the blob) and a low percentile of the
    thin ring just outside it (a hairline frame a few pixels off the photo)."""
    H, W = arr.shape[:2]
    t = max(2, int(0.035 * min(x1 - x0, y1 - y0)))
    inner = _edge_band(arr, x0, y0, x1, y1)
    xa, ya, xb, yb = max(0, x0 - 2 * t), max(0, y0 - 2 * t), min(W, x1 + 2 * t), min(H, y1 + 2 * t)
    box = arr[ya:yb, xa:xb].mean(axis=2)
    ring = np.ones(box.shape, bool)
    ring[y0 - ya:y1 - ya, x0 - xa:x1 - xa] = False
    outer = float(np.percentile(box[ring], 8)) if ring.any() else 255.0
    return min(inner, outer)


def _edge_band(arr, x0, y0, x1, y1):
    """Median lightness of the blob's own outermost band. The selected
    swatch's frame or ring is part of the blob (holes are filled), so on the
    selected one this band is the dark frame; on the rest it is the swatch's
    pale rim or the thumbnail's ground."""
    t = max(2, int(0.035 * min(x1 - x0, y1 - y0)))
    box = arr[y0:y1, x0:x1].mean(axis=2)
    m = np.zeros(box.shape, bool)
    m[:t, :] = m[-t:, :] = True
    m[:, :t] = m[:, -t:] = True
    return float(np.median(box[m]))


def photo_garment(tile):
    """The garment in a thumbnail: whatever differs from its corners."""
    a = np.asarray(tile).astype(np.float64)
    k = max(2, min(a.shape[:2]) // 10)
    bg = np.median(np.concatenate([a[:k, :k].reshape(-1, 3), a[:k, -k:].reshape(-1, 3),
                                   a[-k:, :k].reshape(-1, 3), a[-k:, -k:].reshape(-1, 3)]), axis=0)
    m = np.abs(a - bg).max(axis=2) > 18
    m = ndimage.binary_opening(m, iterations=1)
    m = ndimage.binary_fill_holes(m)
    lab, n = ndimage.label(m)
    if not n:
        return None, 0.0
    sizes = ndimage.sum(m, lab, range(1, n + 1))
    keep = lab == (1 + int(np.argmax(sizes)))
    return keep, float(keep.mean())


def fill_lattice(blobs, diff, mw, mh):
    """Swatches sit on a lattice. Where the selected one's frame touches its
    neighbours the three read as one wide blob and all three are dropped, so
    the lattice is rebuilt from the pitch of the ones found and every empty
    lattice cell that holds something is added back."""
    if len(blobs) < 3:
        return blobs
    xs = sorted(b['x'] for b in blobs)
    steps = [b - a for a, b in zip(xs, xs[1:]) if b - a > 0.5 * mw]
    if not steps:
        return blobs
    pitch = float(np.median(steps))
    rows = sorted({b['y'] for b in blobs})
    ys = []
    for y in rows:
        if not ys or y - ys[-1] > 0.5 * mh:
            ys.append(y)
    x_first = min(xs)
    n = int(round((max(xs) - x_first) / pitch)) + 1
    have = [(b['x'], b['y']) for b in blobs]
    out = list(blobs)
    for y in ys:
        for k in range(n):
            x = int(round(x_first + k * pitch))
            if any(abs(hx - x) < 0.4 * mw and abs(hy - y) < 0.4 * mh for hx, hy in have):
                continue
            cell = diff[y:y + mh, x:x + mw]
            if cell.size and (cell > 6).mean() > 0.5:
                # snap to the thumbnail's own left edge: the pitch is a
                # median, and a cell a few pixels off puts the garment's
                # edge in the frame ring
                win = diff[y + mh // 4:y + 3 * mh // 4, max(0, x - mw // 6):x + mw // 3]
                cols = np.where((win > 6).mean(axis=0) > 0.9)[0]
                if cols.size:
                    x = max(0, x - mw // 6) + int(cols[0])
                out.append(dict(x=x, y=y, w=mw, h=mh, fill=1.0, filled=True))
    return out


def find_swatches(im, y0, y1, x0=0, kind=None):
    """Every swatch in the band [y0, y1) of im, left of nothing, right of x0."""
    band = im.crop((x0, y0, im.width, y1))
    arr = np.asarray(band.convert('RGB')).astype(np.float64)
    if arr.shape[0] < 20:
        return []
    bg = np.median(np.concatenate([arr[:3].reshape(-1, 3), arr[-3:].reshape(-1, 3)]), axis=0)
    diff = np.abs(arr - bg).max(axis=2)
    mask = ndimage.binary_fill_holes(ndimage.binary_closing(diff > 6, iterations=2))
    lab, n = ndimage.label(mask)
    blobs = []
    for i, sl in enumerate(ndimage.find_objects(lab), 1):
        h, w = sl[0].stop - sl[0].start, sl[1].stop - sl[1].start
        if h < 28 or w < 28 or not 0.5 < w / h < 1.6:
            continue
        fill = (lab[sl] == i).sum() / (w * h)
        if fill < 0.6:
            continue
        blobs.append(dict(x=sl[1].start, y=sl[0].start, w=w, h=h, fill=fill))
    if len(blobs) < 2:
        return []
    mw, mh = np.median([b['w'] for b in blobs]), np.median([b['h'] for b in blobs])
    blobs = [b for b in blobs if 0.75 * mw <= b['w'] <= 1.4 * mw and 0.75 * mh <= b['h'] <= 1.4 * mh]
    # the swatch rows run on from the first without a gap; the size buttons
    # below are the same size and must not join them
    ys = sorted({b['y'] for b in blobs})
    if not ys:
        return []
    rows_y = [ys[0]]
    for y in ys[1:]:
        if y - rows_y[-1] > 0.5 * mh:
            if y - rows_y[-1] > 1.6 * mh:
                break
            rows_y.append(y)
    blobs = [b for b in blobs if b['y'] <= rows_y[-1] + 0.5 * mh]
    blobs = fill_lattice(blobs, diff, int(mw), int(mh))
    out = []
    for b in blobs:
        xa, ya, xb, yb = b['x'], b['y'], b['x'] + b['w'], b['y'] + b['h']
        inner = arr[ya + b['h'] // 5: yb - b['h'] // 5, xa + b['w'] // 5: xb - b['w'] // 5]
        spread = float(np.std(inner.reshape(-1, 3), axis=0).mean())
        # a thumbnail of a garment on a pale ground has its ground in the corners
        pad = max(3, int(0.12 * min(b['w'], b['h'])))
        tile = arr[ya + pad // 3: yb - pad // 3, xa + pad // 3: xb - pad // 3]
        corners = np.concatenate([tile[:pad, :pad].reshape(-1, 3), tile[-pad:, -pad:].reshape(-1, 3)])
        centre = np.median(inner.reshape(-1, 3), axis=0)
        photo = (kind == 'photo') if kind else (
            np.abs(np.median(corners, axis=0) - centre).max() > 25 and corners.mean() > 170 and spread > 6)
        rec = dict(x=int(xa + x0), y=int(ya + y0), w=int(b['w']), h=int(b['h']),
                   frame=frame_darkness(arr, xa, ya, xb, yb), spread=round(spread, 1))
        if photo:
            t = Image.fromarray(tile.astype(np.uint8))
            m, share = photo_garment(t)
            px = np.asarray(t).astype(np.float64)[m] if m is not None and share > 0.08 else inner.reshape(-1, 3)
            med = np.median(px, axis=0)
            rec.update(kind='photo', garment_share=round(share, 3),
                       tile=[int(xa + pad // 3 + x0), int(ya + pad // 3 + y0),
                             int(xb - pad // 3 + x0), int(yb - pad // 3 + y0)])
        else:
            med = centre
            rec.update(kind='fabric')
        hx = '%02X%02X%02X' % tuple(int(round(v)) for v in med)
        fam, name, L, C, h, rel, nt = classify(hx)
        rec.update(hex=hx, lab=[round(v, 2) for v in rgb_to_lab(med)], family=fam, name=name)
        out.append(rec)
    if not out:
        return []
    # the selected one: the frame much darker than the rest's
    fr = np.array([s['frame'] for s in out])
    med = np.median(fr)
    i = int(np.argmin(fr))
    for j, s in enumerate(out):
        s['selected'] = bool(j == i and med - fr[i] > 25)
    rows = max(1.0, float(np.median([s['h'] for s in out])))
    out.sort(key=lambda s: (round(s['y'] / rows), s['x']))
    return out


def read_page(path, shop):
    im = Image.open(ROOT + '/' + path).convert('RGB')
    W, H = im.size
    cfg = SHOPS.get(shop, dict(panel_x=0.0))
    x0 = int(W * cfg['panel_x'])
    lines = lines_of(im.crop((x0, 0, W, H)))
    rec = dict(image=path, shop=shop, colour='', swatches=[], why='')
    i, l, name = colour_line(lines)
    if l is None:
        rec['why'] = 'no "Colour:" line on the page'
        return rec
    rec['colour'] = name
    y0 = l['bottom'] + 4
    # the band ends at the size row or the buy button; OCR reads fragments
    # inside the thumbnails as lines, so any other line is no boundary
    nxt = [m for m in lines[i + 1:] if m['top'] > y0 + 20 and END_LINE.match(m['text'].strip())]
    y1 = min(H, (nxt[0]['top'] - 4) if nxt else y0 + 700)
    rec['band'] = [x0, y0, W, y1]
    rec['swatches'] = find_swatches(im, y0, y1, x0, cfg.get('kind'))
    if not rec['swatches']:
        rec['why'] = 'no swatches found in the band under "Colour:"'
    return rec


def shop_rows():
    rows = list(csv.DictReader(open(CAT + '/products.csv')))
    return [r for r in rows if r['shop'] in SHOPS and r['recoloured'] != 'yes'
            and not r.get('parent_id') and r['image_paths'] and r['shot_type'] != 'listing grid']


def main():
    if len(sys.argv) > 1:
        p, shop = f'content/swipe/products/{sys.argv[1]}.png', sys.argv[2]
        r = read_page(p, shop)
        print(r['colour'], r.get('band'), r['why'])
        for s in r['swatches']:
            print(' ', s['kind'], s['x'], s['y'], s['w'], s['h'], s['hex'], s['name'],
                  'SELECTED' if s['selected'] else '', 'frame', round(s['frame']))
        return
    out = {}
    for r in shop_rows():
        for p in r['image_paths'].split(';'):
            if p in out:
                continue
            rec = read_page(p, r['shop'])
            out[p] = rec
            sel = [s for s in rec['swatches'] if s['selected']]
            print(os.path.basename(p), r['shop'], '|', rec['colour'], '|', len(rec['swatches']),
                  'swatches', ','.join(sorted({s['kind'] for s in rec['swatches']})),
                  len(sel), 'selected', rec['why'], flush=True)
    json.dump(out, open(OUT, 'w'), indent=1)


if __name__ == '__main__':
    main()
