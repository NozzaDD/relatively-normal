"""Each colourway row carries only the pictures of its own colour.

A style split into colourways — by colour (split_mixed.py, `-V2`), by the name
on its page (name_split.py, `-V3`), by UNIQLO's swatches (`-sw02`), by the other
shops' swatches (`-cw03`) — is a family of rows. The pictures of the family are
every photograph any of its rows was screenshotted with. A picture belongs to
the row whose colour it shows: its garment colour (the cut-out where there is
one, else the page photo with the backdrop flooded out, as extract_colours.py
reads every product) is compared with each row's own first colour by the
engine's dE2000. A picture within 12 of the row it came from stays there; one
that is not goes to the nearest row within 12. 12 is the catalogue's
match threshold: on the sheets it is about where two garments stop reading as
one colour. A picture within 12 of no row stays with the row it came from and
goes to no colourway: that row is its parent.

A listing-grid cell is a family of one: its only picture is its own cell,
photograph and cut-out. The grid page it was cut from stays with the grid.

The row's primary picture is a flat lay of its own colour where it has one,
else the one of its own pictures nearest its colour.
Its shelf picture, the cut-out, has to be of its own colour too: where the
cut-out measures further than 12 from the row's colour and one of its own
pictures has a cut-out within it, that cut becomes the row's picture
(`assets/{pid}.webp`). Its colour fields stay: they were read off that
colour's picture already, which is how the two came to disagree.

Writes content/catalogue/_picture_owners.json, which build_studio.py applies:
{"rows": {pid: {"pictures": [path, ...], "primary": path}}, "cells": {pid: picture},
 "unassigned": [...], "report": {...}}. Paths are the desk's (`full/...`).

  python3 content/tools/colourway_pictures.py [--check]
"""
import os, sys, re, csv, json, argparse, collections, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from engine import colour as C
import build_studio as BS
import split_mixed as SM

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CAT = ROOT + '/content/catalogue'
OUT = CAT + '/_picture_owners.json'
MATCH = 12.0
CACHE = CAT + '/_picture_colours.json'


def root_of(pid, rows):
    src = (rows.get(pid) or {}).get('recolour_source', '')
    if src in rows and src != pid:
        return root_of(src, rows)
    return re.sub(r'-V\d+$', '', pid)


def src_path(p):
    """A desk path (full/x.jpg) -> the catalogue file it is copied from."""
    return CAT + '/review/' + os.path.basename(p)


SHARE = 0.25        # a colour that covers a quarter of the garment is its colour


def read_file(f, cut, cache):
    """[(hex, share)] of a picture file's garment, cached by name and size."""
    if not os.path.exists(f):
        return []
    k = 'v2:%s:%d' % (os.path.relpath(f, ROOT), os.path.getsize(f))
    if k not in cache:
        try:
            cols, _skin, _kept = SM.read_colours(f, cut)
            cache[k] = [(c['hex'], round(c['share'], 3)) for c in cols]
        except Exception:
            cache[k] = []
    return cache[k]


def measure(e, cache):
    """The garment colours of one picture, its cut-out first."""
    w = (e.get('whole') or {}).get('path')
    return read_file(src_path(w or e['path']), bool(w), cache)


def dist(cols, hx):
    """How far a picture is from a row's colour: its nearest colour that
    covers a quarter of the garment. The largest cluster alone flips between
    a boot's leather and its shadow from one read to the next."""
    ds = [C.delta_e_2000(C.hex_to_lab(c), C.hex_to_lab(hx)) for c, sh in cols if sh >= SHARE]
    if not ds and cols:
        ds = [C.delta_e_2000(C.hex_to_lab(cols[0][0]), C.hex_to_lab(hx))]
    return min(ds) if ds else None


def cell_pictures(rows):
    """Every listing-grid cell's own picture, keyed by the cell's row id."""
    cells = BS.load_json_safe(CAT + '/_grid_cells.json')
    out = {}
    from PIL import Image
    for key, rec in cells.items():
        pid, idx = key.split('#')[0], int(key.split('#')[1])
        for j, c in enumerate(rec.get('cells') or []):
            rid = f'{pid}-C{j}' if idx == 0 else f'{pid}-I{idx}-C{j}'
            if rid not in rows or not c.get('path') or not os.path.exists(CAT + '/' + c['path']):
                continue
            with Image.open(CAT + '/' + c['path']) as im:
                w, h = im.size
            d = dict(path='full/' + os.path.basename(c['path']), w=w, h=h, item=None, person=None,
                     suggested=[], source=(rows[rid]['image_paths'] or ''), type='cell',
                     panel_of=idx, panel_box=c.get('box') or [0, 0, 1, 1])
            if c.get('cut') and os.path.exists(CAT + '/' + c['cut']):
                with Image.open(CAT + '/' + c['cut']) as im:
                    d['whole'] = dict(path='full/' + os.path.basename(c['cut']), w=im.width, h=im.height)
            out[rid] = d
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    a = ap.parse_args()
    rows = {r['product_id']: r for r in csv.DictReader(open(CAT + '/products.csv'))}
    review = BS.load_json_safe(CAT + '/_review_boxes.json')
    panels = BS.load_panels()
    try:
        cache = json.load(open(CACHE))
    except (FileNotFoundError, json.JSONDecodeError):
        cache = {}

    fam = collections.defaultdict(list)
    for pid, r in rows.items():
        if not r.get('parent_id'):
            fam[root_of(pid, rows)].append(pid)
    owners, unassigned, report = {}, [], collections.Counter()
    asset_fix = []
    for rt, members in sorted(fam.items()):
        if len(members) < 2:
            continue
        colour = {m: rows[m]['colour1_hex'] for m in members if rows[m]['colour1_hex']}
        pool = []                                      # (picture, the row it came from)
        for m in members:
            r = rows[m]
            imgs = BS.image_list(review.get(m) or {}, r['image_paths'].split(';'), m, panels,
                                 r.get('shot_type', ''))
            pool += [(e, m) for e in imgs]
        mine = {m: [] for m in members}
        for e, frm in pool:
            if BS.is_detail_type(e.get('type')):
                mine[frm].append(e['path'])            # a close-up stays where it was
                continue
            cols = measure(e, cache)
            ds = sorted((dist(cols, c), m) for m, c in colour.items()) if cols else []
            own = next((d for d, m in ds if m == frm), None)
            if own is not None and own <= MATCH:
                to = frm                               # it is its own row's colour: it stays
            elif ds and ds[0][0] <= MATCH:
                to = ds[0][1]
                if to != frm:
                    report['pictures moved to the row of their colour'] += 1
            else:
                to = frm
                unassigned.append(dict(family=rt, picture=e['path'], stays_with=frm,
                                       nearest=ds[0][1] if ds else None,
                                       de=round(ds[0][0], 1) if ds else None))
            mine[to].append(e['path'])
        for m in members:
            pics = mine[m]
            best = None
            if pics and m in colour:
                ranked = []
                for e, _f in pool:
                    if e['path'] in pics and not BS.is_detail_type(e.get('type')):
                        cols = measure(e, cache)
                        if cols:
                            ranked.append((dist(cols, colour[m]), e['path'], e))
                ranked.sort(key=lambda x: x[0])
                # the primary: a flat lay of the row's own colour first, as
                # the shelf has always preferred, else its nearest picture
                mine_ok = [x for x in ranked if x[0] <= MATCH]
                flat = [x for x in mine_ok if x[2].get('type') == 'flat lay']
                if flat or mine_ok:
                    best = (flat or mine_ok)[0][1]
                # the shelf picture: the row's own cut-out, unless it is another colour
                asset = ROOT + '/' + rows[m]['asset_path'] if rows[m]['asset_path'] else ''
                if asset and os.path.exists(asset) and not rows[m].get('recoloured'):
                    cols = read_file(asset, True, cache)
                    d0 = dist(cols, colour[m]) if cols else 0
                    if d0 > MATCH:
                        cut = next((x for x in ranked if x[2].get('whole') and x[0] <= MATCH), None)
                        asset_fix.append(dict(pid=m, de=round(d0, 1),
                                              to=cut[2]['whole']['path'] if cut else None,
                                              to_type=cut[2].get('type') if cut else None))
            owners[m] = dict(pictures=pics, primary=best)
            before = [e['path'] for e, f in pool if f == m]
            if before != pics:
                report['rows whose pictures changed'] += 1
    cells = cell_pictures(rows)
    for rid in cells:
        report['cells given their own picture'] += 1
    json.dump(cache, open(CACHE, 'w'))
    res = dict(match=MATCH, rows=owners, cells=cells, unassigned=unassigned,
               asset_fix=asset_fix, report=dict(report))
    print(json.dumps(dict(report), indent=1))
    print('families:', sum(1 for v in fam.values() if len(v) > 1),
          ' unassigned pictures:', len(unassigned), ' shelf pictures of another colour:', len(asset_fix))
    for x in asset_fix:
        print('  ', x)
    # Only a cut-out the row INHERITED is replaced: one that is the same
    # picture as another row's of the family (split_mixed.py copied the
    # parent's when a group had no cut of its own). A row whose own cut-out
    # disagrees with its colour fields may have wrong fields instead, and
    # which is wrong is a question for a person; those are listed, not changed.
    sig = {}
    for rt, members in fam.items():
        if len(members) < 2:
            continue
        for m in members:
            ap_ = rows[m]['asset_path']
            if ap_ and os.path.exists(ROOT + '/' + ap_) and not rows[m].get('recoloured'):
                sig.setdefault(rt, {})[m] = pic_hash(ROOT + '/' + ap_)
    flats = BS.load_json_safe(CAT + '/_flat_lays.json')
    done = []
    for x in asset_fix:
        rt = root_of(x['pid'], rows)
        h = sig.get(rt, {}).get(x['pid'])
        twin = [m for m, g in sig.get(rt, {}).items() if m != x['pid'] and g == h]
        # the picture is the parent's own: the row it was first made for keeps it
        owner = rt if rt in twin + [x['pid']] else sorted(twin + [x['pid']])[0]
        x['inherited_from'] = owner if twin and owner != x['pid'] else None
        if not x['inherited_from']:
            x['action'] = 'listed: its own cut-out, colour fields disagree'
            continue
        ok = x['to'] and os.path.exists(src_path(x['to'])) and sound(src_path(x['to']))
        if ok:
            x['action'] = 'cut-out replaced with its own picture\'s'
        else:
            x['action'] = 'to Review: no sound cut of its own colour'
        done.append(x)
    res['asset_fix'] = asset_fix
    print('inherited cut-outs:', len(done), ' replaced:',
          sum(1 for x in done if x['action'].startswith('cut-out')),
          ' sent to Review:', sum(1 for x in done if x['action'].startswith('to Review')))
    if a.check:
        json.dump(res, open(os.environ.get('CHECK_OUT', '/dev/null'), 'w'), indent=1)
        return
    from PIL import Image
    assets = BS.load_json_safe(CAT + '/_assets.json')
    for x in done:
        if x['action'].startswith('cut-out'):
            with Image.open(src_path(x['to'])) as im:
                im.convert('RGBA').save(CAT + f"/assets/{x['pid']}.webp", 'WEBP', quality=90, method=5)
            # an inherited crop tile is a cut-out now; a cut-out keeps its kind
            a0 = assets.get(x['pid'])
            if a0 and a0.get('asset_type') == 'tile':
                a0['asset_type'] = 'cutout_model' if x.get('to_type') == 'on-model' else 'cutout_flat'
            flats[x['pid']] = dict(clean=True, why='', own_cut=x['to'],
                                   note='cut-out was %s\'s; replaced with its own colour\'s, measured '
                                        'one piece, no text' % x['inherited_from'])
        else:
            flats[x['pid']] = dict(clean=False, why='its cut-out was %s\'s garment and it has no sound '
                                   'cut of its own colour' % x['inherited_from'])
    json.dump(assets, open(CAT + '/_assets.json', 'w'), indent=1)
    json.dump(flats, open(CAT + '/_flat_lays.json', 'w'), indent=1)
    # each run's counts are kept: a second run finds nothing left to replace
    # and would otherwise read as if nothing had been
    prev = BS.load_json_safe(OUT)
    res['runs'] = prev.get('runs', []) + [dict(report=res['report'], unassigned=len(unassigned),
                                               inherited=len(done),
                                               replaced=[x['pid'] for x in done if x['action'].startswith('cut-out')],
                                               to_review=[x['pid'] for x in done if x['action'].startswith('to Review')])]
    json.dump(res, open(OUT, 'w'), indent=1)


def pic_hash(path):
    from PIL import Image
    import imglib
    with Image.open(path) as im:
        return imglib.dhash(im.convert('RGB'), 16)


def sound(path):
    """The flat-lay gate's own questions on a cut: one piece, no words in it,
    and big enough to be a garment rather than a sliver of page."""
    from PIL import Image
    import flat_lays as FL
    import numpy as np
    with Image.open(path) as im:
        cut = im.convert('RGBA')
    a = np.asarray(cut)[..., 3] > 128
    if a.mean() < 0.2 or not 0.2 < cut.width / cut.height < 5 or min(cut.size) < 120:
        return False
    m = FL.measure(cut)
    return m['components'] == 1 and m['words_inside'] == 0


if __name__ == '__main__':
    main()
