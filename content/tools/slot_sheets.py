"""One sheet per slot, for looking at the whole catalogue on an iPad."""
import sys, os, csv, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from contact_sheet import sheet

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = ROOT + '/content/catalogue/sheets'
FAM_ORDER = ['black', 'grey', 'cool neutral', 'white', 'warm neutral', 'brown',
             'red', 'orange', 'yellow', 'green', 'blue', 'purple', 'pink']
MARK = {'given': '✓', 'looked up': '✓', 'guessed': '?', 'input needed': '—'}


def main():
    rows = list(csv.DictReader(open(ROOT + '/content/catalogue/products.csv')))
    os.makedirs(OUT, exist_ok=True)
    by = collections.defaultdict(list)
    for r in rows:
        by[r['slot'] or 'unfiled'].append(r)
    out = []
    for slot, rs in sorted(by.items(), key=lambda kv: -len(kv[1])):
        rs.sort(key=lambda r: (FAM_ORDER.index(r['colour1_family'])
                               if r['colour1_family'] in FAM_ORDER else 99,
                               float(r['colour1_L'] or 0)))
        cells = []
        for r in rs:
            cells.append(dict(
                path=ROOT + '/' + r['asset_path'] if r['asset_path'] else '',
                label='%s %s\n%s %s' % (r['product_id'], MARK.get(r['brand_confidence'], ''),
                                        (r['brand'] or 'brand?')[:18], r['colour1_name']),
                swatches=[r[f'colour{i}_hex'] for i in (1, 2, 3) if r[f'colour{i}_hex']]))
        p = f'{OUT}/{slot}.jpg'
        sheet(cells, p, cols=8, cell=180, label_h=40, swatch_h=12,
              title='%s — %d products, sorted by colour family then lightness' % (slot, len(rs)))
        kb = os.path.getsize(p) / 1000
        if kb > 1000:                      # keep every sheet under 1 MB
            from PIL import Image
            im = Image.open(p)
            im.save(p, 'JPEG', quality=68, optimize=True)
            kb = os.path.getsize(p) / 1000
        out.append((slot, len(rs), round(kb)))
        print('%-10s %3d products  %4d kB' % (slot, len(rs), kb))
    return out


if __name__ == '__main__':
    main()
