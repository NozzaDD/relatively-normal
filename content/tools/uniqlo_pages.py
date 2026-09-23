"""Read every UNIQLO product screenshot: the buy panel, the product ID, the swatches.

UNIQLO lays a product page out as photographs on the left and a buy panel on
the right. The panel carries the product name, the selected colour as number
and name ("03 GREY"), the price with its currency, and a row of colour circles
under "Colour:". Each circle is a swatch of the real fabric, one per colour
the style comes in. The product ID sits under "Description" in the left
column, when the screenshot reaches that far down.

Everything read here is legible on the page, so it is `given`. The names of the
colours that are not selected are not on the page and are not guessed: a
swatch carries its sampled colour and nothing else.

The product ID identifies the style, so screenshots sharing one are the same
style in whatever colour each shows.

Writes content/catalogue/_uniqlo_pages.json, keyed by image path.
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

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CAT = ROOT + '/content/catalogue'
PANEL_X = 0.58                      # the buy panel starts here, as a share of the width

COLOUR_RE = re.compile(r'Colo(?:u?r)?\s*[:;]\s*(\d{2})\s+([A-Z][A-Z \-]*[A-Z])')
PRICE_RE = re.compile(r'(\d{1,4}(?:[.,]\d{2})?)\s*(€|EUR|CHF|£|\$)')
ID_RE = re.compile(r'Product\s*ID\s*[:;]?\s*([0-9]{6})')


def lines_of(im):
    d = pytesseract.image_to_data(im, output_type=pytesseract.Output.DICT)
    lines = {}
    for i, t in enumerate(d['text']):
        if t.strip():
            k = (d['block_num'][i], d['par_num'][i], d['line_num'][i])
            lines.setdefault(k, []).append((d['left'][i], d['top'][i], d['width'][i],
                                            d['height'][i], t))
    out = []
    for v in lines.values():
        out.append(dict(text=' '.join(x[4] for x in v), top=min(x[1] for x in v),
                        bottom=max(x[1] + x[3] for x in v), left=min(x[0] for x in v),
                        height=max(x[3] for x in v)))
    out.sort(key=lambda l: (l['top'], l['left']))
    # one printed line that tesseract cut in two ("Colo" + ": 32 BEIGE")
    merged = []
    for l in out:
        m = merged[-1] if merged else None
        if m and abs(m['top'] - l['top']) <= 4 and abs(m['height'] - l['height']) <= 4:
            m['text'] = (m['text'] + l['text']) if l['text'][:1] in ':;' else (m['text'] + ' ' + l['text'])
            m['bottom'] = max(m['bottom'], l['bottom'])
            m['left'] = min(m['left'], l['left'])
        else:
            merged.append(dict(l))
    return merged


def read_panel(lines):
    """Name, colour, price off the buy panel's lines. The name is the line
    straight above "Colour:"; UNIQLO sets nothing between them."""
    got = dict(name='', colour_no='', colour='', price='', colour_line=None, size_line=None,
               price_line=None)
    for i, l in enumerate(lines):
        m = COLOUR_RE.search(l['text'])
        if m and got['colour_line'] is None:
            got['colour_no'], got['colour'] = m.group(1), m.group(2).strip()
            got['colour_line'] = l
            # a long name wraps: take every line stacked tight above and set
            # flush with "Colour:" — the header's icons sit further right
            name, j, below = [], i - 1, l
            while (j >= 0 and below['top'] - lines[j]['bottom'] < 2.6 * lines[j]['height']
                   and abs(lines[j]['left'] - l['left']) < 20 and len(name) < 3):
                name.insert(0, lines[j]['text'].strip())
                below, j = lines[j], j - 1
            got['name'] = ' '.join(name)
        if got['colour_line'] is not None and got['size_line'] is None and l['text'].startswith('Size'):
            got['size_line'] = l
        m = PRICE_RE.search(l['text'])
        if m and got['price_line'] is None and got['colour_line'] is not None:
            got['price_line'] = l
    return got


def find_swatches(panel, y0, y1):
    """Colour circles between the "Colour:" line and the "Size:" line.

    A circle is a round blob that differs from the panel's white. The selected
    one wears a dark ring with a white gap inside it, so its fill and its ring
    are separate blobs: the fill is what is sampled, the ring is dropped as a
    thin annulus. A pale swatch barely differs from white, so the threshold is
    low and holes are filled."""
    arr = np.asarray(panel.crop((0, y0, panel.width, y1)).convert('RGB')).astype(np.float64)
    bg = np.median(arr[:4].reshape(-1, 3), axis=0)
    diff = np.abs(arr - bg).max(axis=2)
    mask = ndimage.binary_fill_holes(diff > 5)
    lab, n = ndimage.label(mask)
    objs = ndimage.find_objects(lab)
    blobs = []
    for i, sl in enumerate(objs, 1):
        h = sl[0].stop - sl[0].start
        w = sl[1].stop - sl[1].start
        if h < 30 or w < 30 or not 0.8 < w / h < 1.25:
            continue
        fill = (lab[sl] == i).sum() / (w * h)
        if fill < 0.6:                              # round fills pi/4 of its box
            continue
        blobs.append(dict(x=sl[1].start, y=sl[0].start, w=w, h=h))
    if not blobs:
        return []
    d = np.median([b['w'] for b in blobs])
    blobs = [b for b in blobs if 0.8 * d <= b['w'] <= 1.35 * d]
    out = []
    for b in blobs:
        cx, cy = b['x'] + b['w'] / 2, b['y'] + b['h'] / 2
        yy, xx = np.mgrid[0:arr.shape[0], 0:arr.shape[1]]
        rr = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) / (b['w'] / 2)
        # the selected one wears a dark ring with a white gap inside it: the
        # gap is the tell, since a ring's size alone depends on the rest
        gap = diff[(rr > 0.80) & (rr < 0.86)]
        selected = b['w'] > 1.06 * min(x['w'] for x in blobs) and np.median(gap) < 12
        disc = rr <= 0.45 * d / b['w']              # the centre, well inside any ring
        px = arr[disc]
        med = np.median(px, axis=0)
        hx = '%02X%02X%02X' % tuple(int(round(v)) for v in med)
        fam, name, L, C, h, rel, nt = classify(hx)
        out.append(dict(cx=round(cx), cy=round(cy + y0), d=int(b['w']), selected=bool(selected),
                        hex=hx, lab=[round(v, 2) for v in EC.srgb_to_lab(tuple(int(round(v)) for v in med))],
                        family=fam, name=name, spread=round(float(np.std(px, axis=0).mean()), 1)))
    out.sort(key=lambda s: (round(s['cy'] / d), s['cx']))
    return out


def read_price(panel, line):
    """The price line again, alone and at twice the size: a leading 1 and the
    decimal comma are what the whole-panel pass drops."""
    pad = line['height']
    box = (max(0, line['left'] - pad), max(0, line['top'] - pad // 2),
           min(panel.width // 2, line['left'] + 9 * line['height']), line['bottom'] + pad // 2)
    crop = panel.crop(box)
    crop = crop.resize((crop.width * 2, crop.height * 2), Image.LANCZOS)
    # the size tooltip can sit on the same line; the price is the left half
    for psm in (7, 8, 6):
        t = pytesseract.image_to_string(crop, config=f'--psm {psm}')
        m = PRICE_RE.search(t.replace(' ', ''))
        if m:
            # UNIQLO's euro pages write a decimal comma; a dot is OCR's reading of it
            return f"{m.group(1).replace('.', ',')} {m.group(2)}"
    return ''


def read_page(path):
    im = Image.open(ROOT + '/' + path).convert('RGB')
    W, H = im.size
    x0 = int(W * PANEL_X)
    panel = im.crop((x0, 0, W, H))
    got = read_panel(lines_of(panel))
    if got['price_line'] is not None:
        got['price'] = read_price(panel, got['price_line'])
    rec = dict(image=path, name=got['name'], colour_no=got['colour_no'], colour=got['colour'],
               price=got['price'], product_id='', swatches=[])
    whole = pytesseract.image_to_string(im.crop((0, 0, x0, H)))
    m = ID_RE.search(whole)
    if m:
        rec['product_id'] = m.group(1)
    if got['colour_line'] is not None:
        y0 = got['colour_line']['bottom'] + 4
        y1 = got['size_line']['top'] - 4 if got['size_line'] else min(H, y0 + 500)
        sw = find_swatches(panel, y0, y1)
        for s in sw:
            s['cx'] += x0
        rec['swatches'] = sw
    return rec


def uniqlo_rows():
    rows = list(csv.DictReader(open(CAT + '/products.csv')))
    return [r for r in rows if (r['shop'] == 'uniqlo.com' or r['brand'] == 'UNIQLO')
            and r['recoloured'] != 'yes' and r['image_paths']]


def main():
    out = {}
    paths = sorted({p for r in uniqlo_rows() for p in r['image_paths'].split(';') if p})
    for p in paths:
        rec = read_page(p)
        out[p] = rec
        print(os.path.basename(p), rec['product_id'] or '------', rec['colour_no'], rec['colour'],
              '|', rec['price'], '|', rec['name'], '|', len(rec['swatches']), 'swatches',
              sum(s['selected'] for s in rec['swatches']), 'selected', flush=True)
    json.dump(out, open(CAT + '/_uniqlo_pages.json', 'w'), indent=1)


if __name__ == '__main__':
    main()
