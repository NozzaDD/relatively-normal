"""Build the six boards: specs from the picker, images from the catalogue."""
import sys, os, json, csv, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from PIL import Image
from engine import colour as C
import inspiration_colours as I
import make_boards

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = ROOT + '/content/boards/v2'

# the owner writes the words; these are drafts, labelled "not my voice yet"
WORDS = {
 'IMG_0843.png': ("Rust twice, and nothing else bright", "One colour at two weights, with brown underneath it."),
 'IMG_0861.png': ("Pale on pale, one warm thing", "Everything quiet except the boots."),
 'IMG_0814.png': ("Ochre over black", "The jacket does the talking and everything under it stays quiet."),
 'IMG_0802.png': ("Brick, and nothing else loud", "One strong colour and three quiet ones underneath."),
 'IMG_0805.png': ("Black, and one thing that isn't", "Black head to toe is easy. The green wrap is the reason to look."),
 'IMG_0093.png': ("Cream, with brown underneath", "Cream on top, brown below, nothing else."),
}


def swatches(pieces, prods, keys, near=20.0):
    """Only colours the pieces actually carry — and only the ones the look has.

    A cut-out that kept a model's jeans would otherwise put a denim chip in the
    strip of a board with no denim on it, which is the fault this whole run is
    about, just at the other end."""
    klabs = [C.hex_to_lab(k['hex']) for k in keys]
    agg = []
    for p in pieces:
        pr = prods[p['product_id']]
        for i in (1, 2):
            hx, sh = pr.get(f'colour{i}_hex'), pr.get(f'colour{i}_share')
            if not hx or not sh or float(sh) < 0.25:
                continue
            if min((C.delta_e_2000(C.hex_to_lab(hx), k) for k in klabs), default=999) > near:
                continue
            l = C.hex_to_lab(hx)
            for a in agg:
                if C.delta_e_2000(l, C.hex_to_lab(a['hex'])) <= 10:
                    a['share'] += float(sh); break
            else:
                agg.append(dict(hex=hx, share=float(sh),
                                name=prods[p['product_id']].get(f'colour{i}_name', '')))
    agg.sort(key=lambda a: -a['share'])
    return agg[:5]


def main():
    prods = {p['product_id']: p for p in csv.DictReader(open(ROOT + '/content/catalogue/products.csv'))}
    spec = json.load(open('/tmp/claude-0/boardspec.json'))
    os.makedirs(OUT + '/inspiration', exist_ok=True)
    out = {}
    for n, (key, s) in enumerate(spec.items(), 1):
        with Image.open(ROOT + '/' + s['image']) as im0:
            crop = I.photo_only(im0.convert('RGB'))
            if max(crop.size) > 1400:
                crop.thumbnail((1400, 1400), Image.LANCZOS)
            ip = f'content/boards/v2/inspiration/board-{n}.jpg'
            crop.save(ROOT + '/' + ip, 'JPEG', quality=88, optimize=True)
        title, line = WORDS[key]
        b = dict(n=n, source_image=s['image'], inspiration=ip, title=title, line=line,
                 keys=s['keys'],
                 pieces=[dict(slot=p['slot'], product_id=p['product_id'],
                              delta_e=p['delta_e'], carries=p['carries'], filler=p['filler'],
                              asset_path=prods[p['product_id']]['asset_path'],
                              asset_type=prods[p['product_id']]['asset_type'])
                         for p in s['pieces']],
                 swatches=swatches(s['pieces'], prods, s['keys']))
        out[f'board-{n}'] = b
    json.dump(out, open(OUT + '/boards.json', 'w'), indent=1)
    WIDE = ('board-3', 'board-6')          # the two strongest, for the post
    for k, b in out.items():
        for v in ('a', 'b'):
            make_boards.render(b, version=v, size=(1080, 1350), labels=False,
                               out=f'{OUT}/{k}-{v}.jpg')
            if k in WIDE:
                _, marks = make_boards.render(b, version=v, size=(1456, 1092), labels=True,
                                              out=f'{OUT}/{k}-{v}-wide.jpg')
                b['numbered'] = [m['product_id'] for m in marks]
        print(k, b['title'], '->', len(b['pieces']), 'pieces,', len(b['swatches']), 'swatches')
    json.dump(out, open(OUT + '/boards.json', 'w'), indent=1)


if __name__ == '__main__':
    main()
