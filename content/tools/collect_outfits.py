"""Read content/outfits/ and write used_in back into the catalogue.

The desk saves a board as three files with one name: the image, a .json and a
.md. Drop them in content/outfits/ and run this. It fills `used_in` in
products.csv and inspiration.csv with the slugs of the boards each piece
appears on, so a week's content can be filtered, validated, and later refreshed
from the catalogue.

It only ever writes `used_in`. Nothing else in the catalogue is touched, and
nothing in content/outfits/ is modified.

  python3 content/tools/collect_outfits.py [--check]
"""
import os, sys, csv, json, glob, argparse, collections

ROOT = '/home/user/relatively-normal'
CAT = ROOT + '/content/catalogue'
OUT = ROOT + '/content/outfits'


def read_outfits():
    """-> (list of info dicts, list of problems)"""
    infos, problems = [], []
    for path in sorted(glob.glob(OUT + '/*.json')):
        try:
            info = json.load(open(path))
        except json.JSONDecodeError as e:
            problems.append(f'{os.path.basename(path)}: not valid JSON ({e.msg})')
            continue
        if info.get('kind') != 'relatively-normal.outfit':
            problems.append(f'{os.path.basename(path)}: not an outfit file, skipped')
            continue
        info['_file'] = os.path.basename(path)
        info['_slug'] = info.get('slug') or os.path.splitext(os.path.basename(path))[0]
        infos.append(info)
    return infos, problems


def used_maps(infos):
    prod, insp = collections.defaultdict(set), collections.defaultdict(set)
    for info in infos:
        slug = info['_slug']
        for p in info.get('pieces', []):
            if p.get('product_id'):
                prod[p['product_id']].add(slug)
        i = info.get('inspiration') or {}
        if i.get('inspiration_id'):
            insp[i['inspiration_id']].add(slug)
    return prod, insp


def inspiration_key(row):
    """inspiration.csv is keyed by path; the desk stores an inspiration_id."""
    folder = os.path.basename(row['folder']).replace(' ', '-')
    stem = os.path.splitext(os.path.basename(row['path']))[0]
    return f'{folder}--{stem}'


import re
OUTFIT_SLUG = re.compile(r'^\d{4}-\d{2}-\d{2}-')


def write_used(path, key_fn, table, check):
    """Rewrites only the slugs this script manages.

    `used_in` also carries entries from before the desk existed — the six
    rebuilt boards are filed as `board-1`…`board-6`. Those are left alone; only
    date-prefixed outfit slugs are removed and re-added, so re-running never
    quietly drops something it did not put there."""
    rows = list(csv.DictReader(open(path)))
    if not rows:
        return 0, 0
    fields = list(rows[0].keys())
    if 'used_in' not in fields:
        fields.append('used_in')
    changed = 0
    for r in rows:
        keep = [x for x in (r.get('used_in') or '').split(';') if x and not OUTFIT_SLUG.match(x)]
        want = ';'.join(sorted(set(keep) | table.get(key_fn(r), set())))
        if (r.get('used_in') or '') != want:
            changed += 1
            r['used_in'] = want
    if not check and changed:
        with open(path, 'w', newline='') as fh:
            w = csv.DictWriter(fh, fields)
            w.writeheader()
            w.writerows(rows)
    return changed, sum(1 for r in rows if r.get('used_in'))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true', help='report, change nothing')
    a = ap.parse_args()

    os.makedirs(OUT, exist_ok=True)
    infos, problems = read_outfits()
    prod, insp = used_maps(infos)

    pc, pn = write_used(CAT + '/products.csv', lambda r: r['product_id'], prod, a.check)
    ic, inn = write_used(CAT + '/inspiration.csv', inspiration_key, insp, a.check)

    print(f'{len(infos)} outfit file(s) in content/outfits/')
    for info in infos:
        missing = [p['product_id'] for p in info.get('pieces', [])
                   if p.get('product_id') not in known_products()]
        note = f"  ({len(missing)} piece(s) not in the catalogue: {', '.join(missing)})" if missing else ''
        print(f"  {info['_slug']}: {len(info.get('pieces', []))} pieces{note}")
    verb = 'would change' if a.check else 'changed'
    print(f'products.csv: {verb} {pc} row(s); {pn} now carry a used_in')
    print(f'inspiration.csv: {verb} {ic} row(s); {inn} now carry a used_in')
    for p in problems:
        print('  !', p)
    missing_files = [i['_slug'] for i in infos
                     if not any(os.path.exists(f"{OUT}/{i['_slug']}{ext}")
                                for ext in ('.png', '.jpg', '.jpeg'))]
    if missing_files:
        print('  ! no image beside the info file for:', ', '.join(missing_files))


_known = None


def known_products():
    global _known
    if _known is None:
        _known = {r['product_id'] for r in csv.DictReader(open(CAT + '/products.csv'))}
    return _known


if __name__ == '__main__':
    main()
