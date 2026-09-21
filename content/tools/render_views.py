"""Render one readable image per product for the viewing pass.

Picks the representative image (the first in sequence — usually the packshot),
trims iOS/Safari chrome and writes a JPEG at a width where product titles,
colour names and composition lines are readable.
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image
import imglib

ROOT = '/home/user/relatively-normal'


def main(outdir, width=980):
    os.makedirs(outdir, exist_ok=True)
    B = json.load(open(ROOT + '/content/catalogue/batches.json'))
    for o in B:
        src = ROOT + '/' + o['images'][0]
        with Image.open(src) as im0:
            im = im0.convert('RGB')
            im = im.crop(imglib.trim_chrome(im))
            im.thumbnail((width, int(width * 2.2)), Image.LANCZOS)
            im.save(os.path.join(outdir, o['product_id'] + '.jpg'), quality=88)
    print('rendered', len(B))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else '/tmp/views')
