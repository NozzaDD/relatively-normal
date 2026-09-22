"""How far do two screenshots of the same product disagree about its colour?

Only products with more than one image can answer this. The dominant colour is
read off each original screenshot's photo region and the widest pairwise dE2000
is the spread. Writes _stability.json; anything above 5 is marked unstable so
the board work knows not to lean on that hex.
"""
import sys, os, json, statistics
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image
import imglib
from engine.matcher import extract_colours
from engine import colour as C

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CAT = ROOT + '/content/catalogue'
UNSTABLE = 5.0


def dominant(path):
    with Image.open(path) as im0:
        im = im0.convert('RGB')
        im = im.crop(imglib.trim_chrome(im))
        box = imglib.photo_box(im)
        if box:
            im = im.crop(box)
        im.thumbnail((200, 200), Image.LANCZOS)
        px = [(r, g, b, 255) for r, g, b in im.getdata()]
    cols = extract_colours(px, k=3, floor=0.05, sample=8000, seed=0)
    return cols[0]['lab'] if cols else None


def main():
    bat = json.load(open(CAT + '/batches.json'))
    out, spreads = {}, []
    for b in bat:
        if len(b['images']) < 2:
            continue
        labs = []
        for p in b['images']:
            try:
                l = dominant(ROOT + '/' + p)
            except Exception:
                l = None
            if l:
                labs.append(l)
        if len(labs) < 2:
            continue
        s = max(C.delta_e_2000(tuple(a), tuple(c))
                for i, a in enumerate(labs) for c in labs[i + 1:])
        spreads.append(s)
        out[b['product_id']] = dict(n=len(labs), spread=round(s, 2),
                                    stability='unstable' if s > UNSTABLE else 'stable')
    json.dump(out, open(CAT + '/_stability.json', 'w'), indent=1)
    print('multi-image products:', len(out))
    if spreads:
        spreads.sort()
        print('spread dE2000: median %.1f  p90 %.1f  max %.1f'
              % (statistics.median(spreads), spreads[int(len(spreads) * .9)], spreads[-1]))
    print('unstable:', sum(1 for v in out.values() if v['stability'] == 'unstable'))


if __name__ == '__main__':
    main()
