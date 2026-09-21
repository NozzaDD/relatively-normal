"""Which inspiration images this library can actually dress.

For every inspiration image and every key colour in it, the catalogue products
per slot that match or come near. Thresholds start at dE2000 < 12 match,
12-20 near, and are calibrated by eye (see content/catalogue/README.md).
"""
import sys, os, json, csv, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import colour as C

ROOT = '/home/user/relatively-normal'
CAT = ROOT + '/content/catalogue'
MATCH, NEAR = 12.0, 20.0
SLOTS = ['layer', 'top', 'bottom', 'dress', 'shoes', 'bag', 'accessory', 'base', 'multiple']
NEUTRAL_REL = 0.15


def lab(hx):
    return C.srgb_to_lab(tuple(int(hx[i:i + 2], 16) for i in (0, 2, 4)))


def product_colours(p):
    """(lab, share) for every recorded colour with a share worth carrying."""
    out = []
    for i in (1, 2, 3):
        hx = p.get(f'colour{i}_hex')
        if hx and float(p.get(f'colour{i}_share') or 0) >= 0.15:
            out.append((lab(hx), float(p[f'colour{i}_share']), hx,
                        p.get(f'colour{i}_name', ''), p.get(f'colour{i}_family', '')))
    return out


def main():
    prods = list(csv.DictReader(open(CAT + '/products.csv')))
    insp = json.load(open(CAT + '/_inspiration.json'))
    pl = [(p, product_colours(p)) for p in prods]

    rows, per_image = [], {}
    for path, v in sorted(insp.items()):
        if 'colours' not in v:
            continue
        keys = [c for c in v['colours'] if c['share'] >= 0.06]
        got = {}
        for c in keys:
            cl = lab(c['hex'])
            for slot in SLOTS:
                m, n = [], []
                for p, pcs in pl:
                    if p['slot'] != slot:
                        continue
                    d = min((C.delta_e_2000(cl, x[0]) for x in pcs), default=999)
                    if d <= MATCH:
                        m.append((round(d, 1), p['product_id']))
                    elif d <= NEAR:
                        n.append((round(d, 1), p['product_id']))
                m.sort(); n.sort()
                if m or n:
                    rows.append(dict(image=path, colour_hex=c['hex'], colour_name=c['name'],
                                     colour_family=c['family'], colour_role=c['role'],
                                     colour_share=c['share'], chromatic=c['rel'] > NEUTRAL_REL,
                                     slot=slot, n_match=len(m), n_near=len(n),
                                     best_delta_e=(m or n)[0][0],
                                     match_ids=';'.join(i for _, i in m[:8]),
                                     near_ids=';'.join(i for _, i in n[:8])))
                got.setdefault(c['hex'], {})[slot] = (len(m), len(n))
        chrom = [c for c in keys if c['rel'] > NEUTRAL_REL]
        covered = sum(1 for c in chrom
                      if any(got.get(c['hex'], {}).get(s, (0, 0))[0] for s in SLOTS))
        per_image[path] = dict(n_key=len(keys), n_chromatic=len(chrom),
                               chromatic_covered=covered,
                               score=covered * 10 + sum(v2[0] for d in got.values() for v2 in d.values()) / 100.0,
                               clothes_share=v['clothes_share'],
                               background_name=v['background_name'])
    with open(CAT + '/coverage.csv', 'w', newline='') as f:
        w = csv.DictWriter(f, list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    json.dump(per_image, open(CAT + '/_coverage_by_image.json', 'w'), indent=1)
    print(len(rows), 'coverage rows;', len(per_image), 'images')
    best = sorted(per_image.items(), key=lambda kv: -kv[1]['score'])[:15]
    for p, s in best:
        print('  %-58s chrom %d/%d' % (p.split('/')[-1], s['chromatic_covered'], s['n_chromatic']))


if __name__ == '__main__':
    main()
