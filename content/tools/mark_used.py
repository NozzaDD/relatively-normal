"""Write used_in back into products.csv and inspiration.csv.

This is the column the owner filters on when validating: the pieces that have
actually been published are the ones worth checking first.
"""
import json, csv, os
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CAT = ROOT + '/content/catalogue'

def main():
    B = json.load(open(ROOT + '/content/boards/v2/boards.json'))
    used, used_img = {}, {}
    for k, b in B.items():
        for p in b['pieces']:
            used.setdefault(p['product_id'], []).append(k)
        used_img.setdefault(b['source_image'], []).append(k)

    for path, key, table in ((CAT + '/products.csv', 'product_id', used),
                             (CAT + '/inspiration.csv', 'path', used_img)):
        rows = list(csv.DictReader(open(path)))
        f = list(rows[0].keys())
        for r in rows:
            r['used_in'] = ';'.join(sorted(set(table.get(r[key], []))))
        with open(path, 'w', newline='') as fh:
            w = csv.DictWriter(fh, f); w.writeheader(); w.writerows(rows)
        print(os.path.basename(path), sum(1 for r in rows if r['used_in']), 'rows marked')


if __name__ == '__main__':
    main()
