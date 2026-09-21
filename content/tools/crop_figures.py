"""Crop whole-figure cut-outs down to the piece they are filed under.

rembg returns the person, not the garment. A cut-out of a model in an orange
bomber filed as `bottom` puts the bomber on the board as well as the trousers —
which is how a board ends up carrying colours the look never had. So any cut-out
tall enough to be a whole figure is cropped to the band where its own slot sits.
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, '/home/user/relatively-normal')
import csv
from PIL import Image

ROOT = '/home/user/relatively-normal'
FIGURE = 1.55                    # alpha bbox h/w above this is a person, not a packshot
BAND = {'layer': (0.00, 0.80), 'dress': (0.00, 1.00), 'top': (0.04, 0.56),
        'base': (0.04, 0.56), 'bottom': (0.42, 1.00), 'shoes': (0.74, 1.00),
        'bag': (0.22, 0.78), 'accessory': (0.00, 0.42), 'multiple': (0.00, 1.00)}


def main():
    A = json.load(open(ROOT + '/content/catalogue/_assets.json'))
    slots = {r['product_id']: r['slot'] for r in
             csv.DictReader(open(ROOT + '/content/catalogue/products.csv'))}
    n = 0
    for pid, a in A.items():
        if not a.get('asset_path') or not a['asset_type'].startswith('cutout'):
            continue
        if 'cropped to' in a.get('note', ''):          # idempotent: never twice
            continue
        band = BAND.get(slots.get(pid, ''), (0.0, 1.0))
        if band == (0.0, 1.0):
            continue
        p = ROOT + '/' + a['asset_path']
        with Image.open(p) as im0:
            im = im0.convert('RGBA')
            bb = im.getchannel('A').point(lambda v: 255 if v > 200 else 0).getbbox()
            if not bb:
                continue
            w, h = bb[2] - bb[0], bb[3] - bb[1]
            if h < FIGURE * w:
                continue
            y0 = bb[1] + int(h * band[0])
            y1 = bb[1] + int(h * band[1])
            cut = im.crop((bb[0], y0, bb[2], y1))
            bb2 = cut.getchannel('A').point(lambda v: 255 if v > 200 else 0).getbbox()
            if bb2:
                cut = cut.crop(bb2)
            if min(cut.size) < 60:
                continue
            cut.save(p, 'WEBP', quality=86, method=5)
        a['asset_type'] = 'cutout_model'
        a['note'] = (a.get('note', '') + '; cropped to the %s band of a whole figure' % slots[pid])
        a['bytes'] = os.path.getsize(p)
        n += 1
    json.dump(A, open(ROOT + '/content/catalogue/_assets.json', 'w'), indent=1)
    print('cropped', n, 'whole-figure cut-outs to their slot band')


if __name__ == '__main__':
    main()
