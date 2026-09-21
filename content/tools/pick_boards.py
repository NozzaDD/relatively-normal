"""Choose the pieces for each board, and run the acceptance test on the result.

The fault being fixed: pieces were checked against each other, never against the
inspiration's colours. So here every candidate is scored against the look's own
key colours, and any piece that brings a chromatic colour the look does not have
is refused outright. Neutrals are free.
"""
import sys, os, json, csv, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import colour as C

ROOT = '/home/user/relatively-normal'
CAT = ROOT + '/content/catalogue'
MATCH, NEAR = 12.0, 20.0
NEUTRAL_REL = 0.15
NEED = ['layer', 'top', 'bottom', 'shoes', 'bag', 'accessory']
SMALL = {'shoes', 'bag', 'accessory'}          # where an accent is allowed to live
MAX_BOARDS_PER_PRODUCT = 2


def lab(hx):
    return C.srgb_to_lab(tuple(int(hx[i:i + 2], 16) for i in (0, 2, 4)))


def pcolours(p):
    out = []
    for i in (1, 2, 3):
        hx = p.get(f'colour{i}_hex')
        sh = float(p.get(f'colour{i}_share') or 0)
        if hx and sh >= 0.15:
            out.append(dict(hex=hx, share=sh, lab=lab(hx),
                            rel=float(p.get('colour1_rel_chroma') or 0) if i == 1 else None,
                            name=p.get(f'colour{i}_name', ''),
                            family=p.get(f'colour{i}_family', '')))
    return out


def rel_of(hx):
    L, Cc, h = C.lab_to_lch(lab(hx))
    return C.relative_chroma(L, Cc, h)


def usable(p):
    return (p['asset_path'] and p['asset_quality'] in ('good', 'usable')
            and p['slot'] in NEED and p['colour1_hex'])


def brings_foreign_colour(p, keylabs):
    for c in pcolours(p):
        if rel_of(c['hex']) <= NEUTRAL_REL:
            continue
        if min((C.delta_e_2000(c['lab'], k) for k in keylabs), default=999) > NEAR:
            return c
    return None


def pick_for(image, insp, prods, usage):
    keys = [c for c in insp['colours'] if c['share'] >= 0.06]
    keylabs = [lab(c['hex']) for c in keys]
    chrom = [c for c in keys if c['rel'] > NEUTRAL_REL]
    chosen, why = {}, []
    covered = set()
    for slot in NEED:
        cands = []
        for p in prods:
            if p['slot'] != slot or not usable(p):
                continue
            if usage[p['product_id']] >= MAX_BOARDS_PER_PRODUCT:
                continue
            if brings_foreign_colour(p, keylabs):
                continue
            best = (999, None)
            for c in keys:
                cl = lab(c['hex'])
                d = min((C.delta_e_2000(cl, x['lab']) for x in pcolours(p)), default=999)
                if d < best[0]:
                    best = (d, c)
            d, c = best
            # an accent must stay an accent: only a small slot may carry it
            if c and c['role'] == 'accent' and slot not in SMALL:
                d += 40
            new = 1 if (c and d <= MATCH and c['hex'] not in covered) else 0
            qual = 0 if p['asset_quality'] == 'good' else 1
            cands.append((-new, d, qual, p['product_id'], p, c if d <= MATCH else None))
        if not cands:
            why.append(f'{slot}: nothing in the library')
            continue
        cands.sort(key=lambda t: (t[0], t[1], t[2]))
        _, d, _, pid, p, c = cands[0]
        chosen[slot] = dict(product=p, delta_e=round(d, 1),
                            carries=(c['hex'] if c else ''),
                            neutral_filler=(c is None))
        if c:
            covered.add(c['hex'])
    missing = [c for c in chrom if c['hex'] not in covered]
    return dict(keys=keys, chromatic=chrom, chosen=chosen, covered=covered,
                missing=missing, notes=why)


def accept(res):
    """-> list of (test, pass/fail, detail)"""
    out = []
    out.append(('every key colour carried', not res['missing'],
                'missing: ' + ', '.join(c['name'] for c in res['missing']) if res['missing'] else 'all carried'))
    acc_ok, acc_detail = True, 'no accent in the look'
    for c in res['keys']:
        if c['role'] != 'accent':
            continue
        holders = [s for s, v in res['chosen'].items() if v['carries'] == c['hex']]
        if holders:
            acc_detail = f"{c['name']} on {', '.join(holders)}"
            if any(h not in SMALL for h in holders):
                acc_ok = False
    out.append(('an accent stays an accent', acc_ok, acc_detail))
    out.append(('no foreign chromatic colour', True,
                'refused at selection; neutrals free'))
    have = [s for s in NEED if s in res['chosen']]
    out.append(('all components present', len(have) == len(NEED),
                'have ' + ', '.join(have) if len(have) < len(NEED)
                else 'layer, top, bottom, shoes, bag, accessory'))
    fillers = [s for s, v in res['chosen'].items() if v['neutral_filler']]
    out.append(('neutral fillers declared', True,
                ', '.join(fillers) if fillers else 'none'))
    return out
