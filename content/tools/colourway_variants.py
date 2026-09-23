"""Colour variants for any shop that shows its colourways, not only UNIQLO.

uniqlo_variants.py makes UNIQLO's; this makes everyone else's from what
colourway_pages.py read off the pages, by the same three rules:

  1. A colour the owner already has a screenshot of is not made again. The
     page says which swatch is selected; that swatch is found in the style's
     reference row by its colour — it is the same picture, so they agree to
     within a dE or two — because Johnstons moves the selected colour to the
     front and the order is not the same from page to page. So "swatch 4 is
     covered by IMG_1133" is read, not guessed. A screenshot whose page did not reach the swatch row
     is matched to the nearest swatch by colour, one screenshot per swatch,
     only within COVER_DE.
  2. Where the shop shows a photograph of each colour (Toast's and Colorful
     Standard's thumbnails), the variant is that photograph, cut out: the
     brand's own picture, not simulated.
  3. Where it shows only a patch of fabric (Johnstons of Elgin), the style's
     clean flat lay is recoloured to the patch in CIELAB with the same
     recolour() as UNIQLO's, and the row is marked simulated.

A variant's colour_name_text is empty. Only the selected swatch's name is
printed on a page, and the selected swatch is always a colour that
screenshot already covers.

Writes content/catalogue/_colourway_variants.json (same shape as
_variants.json), variants/*.webp and sheets/{shop}-{style}.jpg.
"""
import os, sys, json, csv, re, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import numpy as np
from PIL import Image
import imglib
import flat_lays as FL
import uniqlo_variants as UV
from colourway_pages import SHOPS
from engine import colour as EC

ROOT = UV.ROOT
CAT = UV.CAT
OUT = UV.OUT
COVER_DE = 10.0      # a screenshot's garment this close to a swatch is that colour
SAME_SWATCH = 4.0    # one swatch picture read on two pages agrees this closely
LABEL = {'johnstonsofelgin.com': 'Johnstons of Elgin', 'eu.toa.st': 'Toast',
         'colorfulstandard.com': 'Colorful Standard'}
THUMB_SCALE = 3      # a thumbnail is cut at this many times its size
# Judged by eye on the per-style sheets.
DROPPED = {
    'B068-P003-cw01': "the pale thumbnail ground joins the pale grey jumper; the cut keeps a white block "
                      "under the hem",
}


def flat_panel(pid):
    """A side-by-side row's flat-lay panel: its cut where it measured clean,
    else the panel photo. The row's own asset may be the whole page cut."""
    try:
        pan = json.load(open(CAT + '/_panels.json')).get(f'{pid}#0') or {}
    except FileNotFoundError:
        return None
    for p in pan.get('panels', []):
        if p['type'] == 'flat lay' and p.get('typed_by') == 'position':
            return 'content/catalogue/' + (p.get('cut') or p['path'])
    return None


def hex_lab(h):
    return np.array(EC.hex_to_lab(h))


def norm(s):
    return re.sub(r'\W+', ' ', (s or '').lower()).strip()


def style_name(r):
    """The style's name without the colour in it. Johnstons prints the colour
    inside the name ("Iris Classic Blue Cashmere Cardigan", Colour: BLUE), so
    four colours of one cardigan read as four styles. The page's own colour
    name is taken out of its own product name; nothing else is changed.
    Returns (name, whether anything was taken out)."""
    name, col = r['product_name'], (r.get('colour_name_text') or '').strip()
    if col and re.search(r'\b' + re.escape(col) + r'\b', name, re.I):
        return re.sub(r'\s+', ' ', re.sub(r'\b' + re.escape(col) + r'\b', '', name, flags=re.I)).strip(), True
    return name, False


def row_lab(r):
    return hex_lab(r['colour1_hex']) if r.get('colour1_hex') else None


def thumb_cut(page_path, tile):
    """The garment in a colour thumbnail, cut from the screenshot itself."""
    im = Image.open(ROOT + '/' + page_path).convert('RGB').crop(tuple(tile))
    im = im.resize((im.width * THUMB_SCALE, im.height * THUMB_SCALE), Image.LANCZOS)
    cut = FL.raw_cut(im)
    cut, _ = imglib.keep_main_blobs(cut, rel=0.5, max_blobs=1)
    m = FL.measure(cut)
    bb = cut.getchannel('A').getbbox()
    return (cut.crop(bb) if bb else cut), m


def main():
    import shelf_checks
    rows = [r for r in csv.DictReader(open(CAT + '/products.csv'))
            # the owner's own screenshots only: a variant from an earlier run,
            # real or recoloured, carries a recolour_source
            if r['shop'] in SHOPS and not r.get('recolour_source') and not r.get('parent_id')
            and r['image_paths'] and r['shot_type'] != 'listing grid']
    pages = json.load(open(CAT + '/_colourway_pages.json'))
    clean = shelf_checks.clean_verdicts()
    for f in os.listdir(OUT):
        if f.endswith('.webp') and '-cw' in f:
            os.remove(os.path.join(OUT, f))
    styles = collections.defaultdict(list)
    for r in rows:
        if r['product_name']:
            styles[(r['shop'], norm(style_name(r)[0]))].append(r)
    variants, report, dropped = [], {}, {}
    for (shop, _), rs in sorted(styles.items()):
        style, stripped = style_name(rs[0])
        # the reference swatch row: the fullest reading among the style's pages
        readings = [(r, p, pages[p]) for r in rs for p in r['image_paths'].split(';')
                    if p in pages and pages[p]['swatches']]
        if not readings:
            continue
        ref_row, ref_path, ref = max(readings, key=lambda x: len(x[2]['swatches']))
        sw = ref['swatches']
        n = len(sw)
        # 1. which swatches a screenshot already covers
        covered, how = {}, {}
        for r, p, rec in readings:
            sel = [s for s in rec['swatches'] if s['selected']]
            if len(sel) != 1:
                continue
            d, i = min((UV.de(sel[0]['lab'], s['lab']), i) for i, s in enumerate(sw))
            if d <= SAME_SWATCH and i not in covered:
                covered[i] = r['product_id']
                how[i] = f'selected on {os.path.basename(p)} (dE {d:.1f} to the reference swatch)'
        done = set(covered.values())
        cand = []
        for r in rs:
            lab = row_lab(r)
            if r['product_id'] in done or lab is None:
                continue
            for i, s in enumerate(sw):
                if i not in covered:
                    cand.append((UV.de(lab, s['lab']), i, r['product_id']))
        for d, i, pid in sorted(cand):
            if d > COVER_DE or i in covered or pid in done:
                continue
            covered[i], how[i] = pid, f'colour match dE {d:.1f}'
            done.add(pid)
        todo = [i for i in range(n) if i not in covered]
        kinds = {s['kind'] for s in sw}
        # 3. a source for recolouring, only where a recolour is needed
        src = src_cut = src_lab = None
        if todo and 'fabric' in kinds:
            ok = [r for r in rs if clean.get(r['product_id']) and r['asset_path']]
            if ok:
                med_L = float(np.median([sw[i]['lab'][0] for i in todo]))
                src = min(ok, key=lambda r: abs(float(r['colour1_L'] or 50) - med_L))
                src_cut = Image.open(ROOT + '/' + src['asset_path']).convert('RGBA')
                src_lab, _ = UV.garment_lab(src_cut)
        base_id = (src or ref_row)['product_id']
        slug = f"{LABEL.get(shop, shop).lower().replace(' ', '-')}-{UV.slug(style)}"
        made = []
        for i in todo:
            s = sw[i]
            pid = f'{base_id}-cw{i + 1:02d}'
            base = dict(product_id=pid, source=base_id, style=style, shop=shop, swatch=i + 1,
                        swatch_hex=s['hex'], selected=False, colour_name_text='',
                        garment_type=(src or ref_row)['garment_type'], slot=(src or ref_row)['slot'],
                        slot_confidence='', price=ref_row['price'], source_clean=bool(src),
                        # the colour-free name is ours, taken from the printed one
                        product_name_confidence='guessed' if stripped else 'given')
            path = f'{OUT}/{pid}.webp'
            if s['kind'] == 'photo':
                im, m = thumb_cut(ref_path, s['tile'])
                if m['components'] != 1:
                    dropped[pid] = f"thumbnail {i + 1} on {os.path.basename(ref_path)} cut into {m['components']} pieces"
                    continue
                im.save(path, 'WEBP', quality=88, method=5)
                glab, _ = UV.garment_lab(im)
                # measured the way colourway_pages.py measured the thumbnail
                # (the median of the garment), so the two numbers compare
                arr = np.asarray(im).astype(np.float64)
                med = np.median(UV.srgb_to_lab_np(arr[..., :3])[arr[..., 3] > 200], axis=0)
                rec = dict(base, real=True, real_from=ref_path, tile=s['tile'], colour=UV.colour_record(glab),
                           swatch_to_variant_de=round(UV.de(med, s['lab']), 1))
            elif src is not None:
                im, share = UV.recolour(src_cut, src_lab, s['lab'])
                im.save(path, 'WEBP', quality=88, method=5)
                glab, _ = UV.garment_lab(im)
                rec = dict(base, real=False, recoloured_share=round(share, 3),
                           colour=UV.colour_record(s['lab']), speckle=round(UV.speckle(im), 1),
                           swatch_to_variant_de=round(UV.de(glab, s['lab']), 1),
                           delta_e_to_source=round(UV.de(src_lab, s['lab']), 1))
            else:
                dropped[pid] = 'fabric swatch and no clean flat lay of the style to recolour'
                continue
            if pid in DROPPED:
                dropped[pid] = DROPPED[pid]
                os.remove(path)
                continue
            rec['asset_path'] = f'content/catalogue/variants/{pid}.webp'
            variants.append(rec)
            made.append(pid)
        # the sheet's source picture: the recolour source, else the reference row's own
        sheet_src = src or ref_row
        report[style] = dict(shop=shop, shop_label=LABEL.get(shop, shop), source=base_id,
                             source_image=ref_path, source_clean=bool(src) or bool(clean.get(ref_row['product_id'])),
                             source_cut=flat_panel(sheet_src['product_id']) or sheet_src['asset_path'],
                             swatches=n, kinds=sorted(kinds),
                             covered={str(i + 1): [covered[i], how[i]] for i in sorted(covered)},
                             own_swatch=next((i + 1 for i, p in covered.items() if p == sheet_src['product_id']), None),
                             own_hex=next((sw[i]['hex'] for i, p in covered.items()
                                           if p == sheet_src['product_id']), ''),
                             images=sorted({p for r in rs for p in r['image_paths'].split(';')}),
                             variants=made, real=[p for p in made if p.endswith(tuple(
                                 f'cw{i + 1:02d}' for i in todo if sw[i]['kind'] == 'photo'))],
                             sheet=slug)
        print(f"{LABEL.get(shop, shop)} {style}: {n} swatches, {len(covered)} covered by screenshots, "
              f"{len(made)} variants ({sum(1 for v in variants if v['product_id'] in made and v['real'])} real)",
              flush=True)
    json.dump(dict(variants=variants, report=report, dropped=dropped), open(CAT + '/_colourway_variants.json', 'w'),
              indent=1, default=float)
    import variant_sheets
    variant_sheets.write('rows', only='_colourway_variants.json')
    print('variants:', len(variants), ' real:', sum(v['real'] for v in variants),
          ' simulated:', sum(not v['real'] for v in variants), ' dropped:', len(dropped))
    for k, why in dropped.items():
        print('  dropped', k, '-', why)


if __name__ == '__main__':
    main()
