"""Two screenshots of one product in one colour: find them, measure them, keep one row.

Shops show a product in two ways: a flat lay and the same garment on a model
side by side (Toast, Care of Carl), or one centred picture per screenshot,
either the flat lay or the model (Colorful Standard, a Johnstons lightbox).
The owner often screenshots both, so the catalogue got two rows for one
garment in one colour.

SAME PRODUCT is decided by what the pages say plus what the pictures show,
never by colour alone:

  names     same batch, same shop, the same product name and the same colour
            name as the viewing pass read them off the pages. A screenshot
            with no name on the page (a lightbox) joins its neighbour only
            when its browser tab reads as the start of that neighbour's name.
  pictures  two flat lays: the duplicate test shelf_checks.py uses —
            silhouette IoU, lightness structure, median colour. Two model
            photos: the garment's colour within MODEL_DE. A flat lay and a
            model photo cannot be compared by silhouette, so the page names
            decide and the colour gap is what is measured and reported.

For every pair the dE2000 between the garment on the flat lay and the garment
on the model is measured: the flat lay's biggest colour cluster against the
model's, the model's skin removed and, on a whole figure, only the band where
the slot sits (crop_figures.BAND). Nothing is recoloured here.

  python3 content/tools/same_product.py [--from 63]  # measure, write _same_product.json + a sheet
  python3 content/tools/same_product.py --merge    # also fold each group into one row in batches.json

Merging only regroups screenshots in batches.json — the flat lay's
product ID is kept, and its screenshot is put first so it is the row's
primary picture — and the pipeline is then re-run for those rows.
"""
import os, sys, json, csv, re, glob, argparse, collections, itertools
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import numpy as np
from PIL import Image, ImageDraw
from scipy.cluster.vq import kmeans2
import uniqlo_variants as UV
import shelf_checks as SC
from crop_figures import BAND, FIGURE
from contact_sheet import _font, GREY
from engine import colour as EC

ROOT, CAT = UV.ROOT, UV.CAT
MODEL_DE = 5.0           # two model photos of one colour agree this closely: B065-P007
                         # (olive) and -P008 (brown), both labelled "hemlock", measure 7.0
FLAT_TYPES = ('flat packshot', 'ghost mannequin')


def norm(s):
    s = (s or '').strip()
    return '' if s.upper() in ('NONE', '-', '') else re.sub(r'\W+', ' ', s.lower()).strip()


def viewing():
    rows = {}
    for f in sorted(glob.glob(CAT + '/_viewing_rows/rows_*.txt')):
        for ln in open(f):
            p = [x.strip() for x in ln.rstrip('\n').split('|')]
            if len(p) >= 16:
                rows[p[0]] = p
    return rows


def pictures(pid, shot, panels, assets):
    """(flat, model) picture paths for one single-screenshot product."""
    flat = model = None
    pan = panels.get(f'{pid}#0') or {}
    if pan.get('split'):
        # the biggest of each kind: a strip of the page header can be typed
        # on-model because a head shows in it
        big = sorted(pan['panels'], key=lambda p: -p['box'][2] * p['box'][3])
        for p in big:
            if p['type'] == 'flat lay' and flat is None and p.get('cut'):
                flat = CAT + '/' + p['cut']
            if p['type'] == 'on-model' and model is None:
                model = CAT + '/' + (p.get('cut') or p['path'])
    a = (assets.get(pid) or {}).get('asset_path')
    if a:
        if shot in FLAT_TYPES and flat is None:
            flat = ROOT + '/' + a
        elif shot == 'on model' and model is None:
            model = ROOT + '/' + a
    return flat, model


def lab_pixels(rgba):
    arr = np.asarray(rgba.convert('RGBA')).astype(np.float64)
    m = arr[..., 3] > 200
    return UV.srgb_to_lab_np(arr[..., :3]), m


def biggest_cluster(lab, k=3):
    rng = np.random.default_rng(1)
    s = lab[rng.choice(len(lab), size=min(len(lab), 20000), replace=False)]
    cent, labels = kmeans2(s, k, minit='++', seed=0)
    counts = np.bincount(labels, minlength=k)
    return cent[int(np.argmax(counts))]


def flat_colour(path):
    lab, m = lab_pixels(Image.open(path))
    if m.sum() < 200:              # an opaque panel: the garment is what is not the corners
        return None, {}
    return biggest_cluster(lab[m]), {}


def model_colour(path, slot):
    """The garment on a person: the slot's band of a whole figure, skin out."""
    im = Image.open(path).convert('RGBA')
    a = np.asarray(im)[..., 3]
    if (a > 200).mean() > 0.97:
        # an uncut photo panel: cut it the way the catalogue does
        import flat_lays as FL
        im = FL.raw_cut(im.convert('RGB'))
    bb = im.getchannel('A').point(lambda v: 255 if v > 200 else 0).getbbox()
    if not bb:
        return None, {}
    w, h = bb[2] - bb[0], bb[3] - bb[1]
    band = BAND.get(slot, (0, 1)) if h >= FIGURE * w else (0, 1)
    crop = im.crop((bb[0], bb[1] + int(h * band[0]), bb[2], bb[1] + int(h * band[1])))
    lab, m = lab_pixels(crop)
    L, A, B = lab[..., 0], lab[..., 1], lab[..., 2]
    C = np.hypot(A, B)
    hh = (np.degrees(np.arctan2(B, A)) + 360) % 360
    skin = (hh >= 18) & (hh <= 62) & (C >= 8) & (C <= 40) & (L >= 25) & (L <= 92)
    keep = m & ~skin
    if keep.sum() < 200:
        return None, dict(skin_share=1.0)
    return biggest_cluster(lab[keep]), dict(skin_share=round(float((m & skin).sum() / max(1, m.sum())), 3),
                                            band=list(band))


def flat_match(pa, pb):
    fa, fb = SC.features(pa), SC.features(pb)
    if not fa or not fb:
        return None
    iou = float((fa['m'] & fb['m']).sum() / (fa['m'] | fb['m']).sum())
    both = fa['m'] & fb['m']
    sd = float(np.abs(fa['L'][both] - fb['L'][both]).mean())
    de = float(EC.delta_e_2000(tuple(fa['med']), tuple(fb['med'])))
    return dict(iou=round(iou, 3), structure=round(sd, 2), de=round(de, 2),
                same=iou >= SC.IOU and sd <= SC.STRUCT and de <= SC.DE)


def groups(batches, view, first_batch):
    """Candidate groups by the page text: [[pid, ...], ...] in screenshot order.
    Only batches from first_batch on: an ingested row's ID may already be in
    asset-choices.json, used_in or an outfit, and folding it away would
    orphan them."""
    by = collections.defaultdict(list)
    single = [b for b in batches if len(b['images']) == 1 and int(b['batch_id'][1:]) >= first_batch]
    for b in single:
        v = view.get(b['product_id'])
        if not v or v[7] == 'listing grid':
            continue
        name, col = norm(v[11]), norm(v[12])
        if name and col:
            by[(b['batch_id'], norm(v[9]) or '', name, col)].append(b['product_id'])
    out = [g for g in by.values() if len(g) > 1]
    # a nameless screenshot whose tab title starts its neighbour's name
    named = {b['product_id']: b for b in single}
    order = [b['product_id'] for b in single]
    for i, pid in enumerate(order):
        v = view.get(pid)
        if not v or norm(v[11]) or v[7] == 'listing grid':
            continue
        m = re.search(r'tab (?:reads|title|shows)?\s*"([^"]+?)(?:\.\.\.|…)?"', v[15])
        if not m:
            continue
        tab = norm(m.group(1))
        for j in (i + 1, i - 1):
            if 0 <= j < len(order) and named[order[j]]['batch_id'] == named[pid]['batch_id']:
                w = view.get(order[j])
                if w and norm(w[11]).startswith(tab) and len(tab) >= 8:
                    g = next((g for g in out if order[j] in g), None)
                    if g:
                        g.append(pid)
                    else:
                        out.append([order[j], pid])
                    break
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--merge', action='store_true')
    ap.add_argument('--preview', type=float, metavar='DE',
                    help='sheet of the flat lays above this dE recoloured to the model, nothing applied')
    ap.add_argument('--apply', type=float, metavar='DE',
                    help='recolour the flat lays above this dE; build_products.py applies them. '
                         'The owner chose 0 on 23 September: wherever a model photo of the same '
                         'product and colour exists, its colour replaces the flat lay\'s')
    ap.add_argument('--from', dest='first', type=int, default=63,
                    help='first batch number to look in (63: the 23 September ingest)')
    a = ap.parse_args()
    batches = json.load(open(CAT + '/batches.json'))
    if (a.preview is not None or a.apply is not None) and os.path.exists(CAT + '/_same_product.json'):
        # the groups are merged already: measure again on the merged rows' own
        # pictures, which is what the shelf will show
        res = remeasure(json.load(open(CAT + '/_same_product.json')), batches)
        recolour(res, a.apply if a.apply is not None else a.preview, write=a.apply is not None)
        json.dump(res, open(CAT + '/_same_product.json', 'w'), indent=1, default=float)
        sheet(res)
        return
    view = viewing()
    panels = json.load(open(CAT + '/_panels.json'))
    assets = json.load(open(CAT + '/_assets.json'))
    img = {b['product_id']: b['images'][0] for b in batches}
    res = []
    for g in groups(batches, view, a.first):
        members = []
        for pid in g:
            v = view[pid]
            flat, model = pictures(pid, v[7], panels, assets)
            layout = re.match(r'layout=([\w-]+)', v[15])
            members.append(dict(pid=pid, image=img[pid], shot=v[7], slot=v[1],
                                layout=layout.group(1) if layout else '', flat=flat, model=model))
        for m in members:
            lab, info = model_colour(m['model'], m['slot']) if m['model'] else (None, {})
            m['model_lab'] = None if lab is None else [round(float(x), 2) for x in lab]
            m.update(info)
        # every pair compared, then joined: picture checks decide which of the
        # screenshots the page text grouped are really one garment in one colour
        checks, par = [], {m['pid']: m['pid'] for m in members}

        def root(x):
            while par[x] != x:
                x = par[x]
            return x
        for x, y in itertools.combinations(members, 2):
            if x['flat'] and y['flat']:
                c = flat_match(x['flat'], y['flat']) or dict(same=False)
                checks.append(dict(a=x['pid'], b=y['pid'], kind='flat/flat', **c))
                if c['same']:
                    par[root(y['pid'])] = root(x['pid'])
            elif x['model_lab'] and y['model_lab'] and not (x['flat'] or y['flat']):
                d = UV.de(x['model_lab'], y['model_lab'])
                checks.append(dict(a=x['pid'], b=y['pid'], kind='model/model', de=round(d, 1),
                                   same=d <= MODEL_DE))
                if d <= MODEL_DE:
                    par[root(y['pid'])] = root(x['pid'])
        comps = collections.defaultdict(list)
        for m in members:
            comps[root(m['pid'])].append(m)
        with_flat = [c for c in comps.values() if any(m['flat'] for m in c)]
        only_model = [c for c in comps.values() if not any(m['flat'] for m in c)]
        # a model photo cannot be compared with a flat lay by silhouette: the
        # page text joins it, and only when there is one flat lay to join
        if len(with_flat) == 1:
            for c in only_model:
                with_flat[0].extend(c)
            parts = with_flat
        else:
            parts = with_flat + only_model
        for part in parts:
            flats = [m for m in part if m['flat']]
            models = [m for m in part if m['model_lab']]
            fl = flat_colour(flats[0]['flat'])[0] if flats else None
            pair_de = round(UV.de(fl, models[0]['model_lab']), 1) if fl is not None and models else None
            kinds = sorted({m['layout'] for m in part})
            same = len(part) > 1
            why = [] if same else [f"{c['a']} / {c['b']} differ ({c['kind']}" +
                                   (f", IoU {c['iou']}, structure {c['structure']}, dE {c['de']})"
                                    if 'iou' in c else f", dE {c.get('de')})")
                                   for c in checks if not c['same']]
            res.append(dict(members=part, same=same, why=why,
                            checks=[c for c in checks if {c['a'], c['b']} <= {m['pid'] for m in part}]
                            if same else checks,
                            flat=flats[0]['pid'] if flats else None,
                            model=models[0]['pid'] if models else None,
                            flat_lab=None if fl is None else [round(float(x), 2) for x in fl],
                            flat_model_de=pair_de, layouts=kinds,
                            literal=('side-by-side' in kinds and 'centred' in kinds)))
            print(' + '.join(f"{m['pid']}({m['layout']},{m['shot']})" for m in part),
                  'SAME' if same else 'NOT SAME', f'dE flat/model {pair_de}', '; '.join(why), flush=True)
    if a.preview is not None or a.apply is not None:
        recolour(res, a.apply if a.apply is not None else a.preview, write=a.apply is not None)
    json.dump(res, open(CAT + '/_same_product.json', 'w'), indent=1, default=float)
    sheet(res)
    if a.merge:
        merge(batches, res)


def model_cut(image, pid, i):
    import imglib, flat_lays as FL
    d = os.path.join(__import__('tempfile').gettempdir(), 'rn-model-cuts')    # working files, never committed
    os.makedirs(d, exist_ok=True)
    path = f'{d}/{pid}-{i}-model.png'
    if not os.path.exists(path):
        im = Image.open(ROOT + '/' + image).convert('RGB')
        im = im.crop(imglib.trim_chrome(im))
        cut, _ = imglib.keep_main_blobs(FL.raw_cut(im), rel=0.5, max_blobs=1)
        cut.crop(cut.getbbox()).save(path)
    return path


def remeasure(res, batches):
    """Flat and model pictures of each merged row, from the pipeline's own
    output: the row's cut-out when it is a flat cut, else its flat-lay panel;
    the model screenshot's whole cut-out in Review, else its on-model panel."""
    by = {b['product_id']: b for b in batches}
    panels = json.load(open(CAT + '/_panels.json'))
    assets = json.load(open(CAT + '/_assets.json'))
    review = json.load(open(CAT + '/_review_boxes.json'))
    for r in res:
        if not r['same']:
            continue
        keep = next(m['pid'] for m in r['members'] if m['pid'] in by)
        imgs = by[keep]['images']
        a = assets.get(keep, {})
        for m in r['members']:
            i = imgs.index(m['image'])
            pan = panels.get(f'{keep}#{i}') or {}
            big = sorted(pan.get('panels', []), key=lambda p: -p['box'][2] * p['box'][3])
            flat = next((CAT + '/' + p['cut'] for p in big if p['type'] == 'flat lay' and p.get('cut')), None)
            model = next((CAT + '/' + (p.get('cut') or p['path']) for p in big if p['type'] == 'on-model'), None)
            if m['shot'] in FLAT_TYPES and flat is None and i == 0 and a.get('asset_type') == 'cutout_flat':
                flat = ROOT + '/' + a['asset_path']
            if m['shot'] == 'on model' and model is None:
                e = (review.get(keep, {}).get('images') or [])
                if i < len(e) and e[i] and e[i].get('whole'):
                    model = CAT + '/' + e[i]['whole']['path']
                else:
                    # a clean flat row has no Review copies: cut the model
                    # screenshot here, page furniture trimmed as everywhere
                    model = model_cut(m['image'], keep, i)
            m['flat'], m['model'] = flat, model
            lab, info = model_colour(model, m['slot']) if model else (None, {})
            m['model_lab'] = None if lab is None else [round(float(x), 2) for x in lab]
            m.update(info)
        flats = [m for m in r['members'] if m['flat']]
        models = [m for m in r['members'] if m['model_lab']]
        fl = flat_colour(flats[0]['flat'])[0] if flats else None
        r['flat'] = flats[0]['pid'] if flats else None
        r['model'] = models[0]['pid'] if models else None
        r['flat_lab'] = None if fl is None else [round(float(x), 2) for x in fl]
        r['flat_model_de'] = round(UV.de(fl, models[0]['model_lab']), 1) if fl is not None and models else None
        r['row'] = keep
        print(keep, ' + '.join(f"IMG_{m['image'][-8:-4]}" for m in r['members']), 'dE', r['flat_model_de'])
    return res


def recolour(res, threshold, write):
    """The flat lay recoloured to the colour on the model, for every pair whose
    measured gap is above the threshold. The model photo carries the true
    colour; the flat lay carries the shape. Marked simulated: it is our
    picture, not the brand's."""
    cells = []
    for r in res:
        r.pop('recolour', None)          # a run replaces the last one's choice
    for r in res:
        if not r['same'] or r['flat_model_de'] is None or r['flat_model_de'] <= threshold:
            continue
        # a product shown only side by side keeps its flat lay's own colour:
        # the owner's rule, and the two photos there come from one shoot
        if all(m['layout'] == 'side-by-side' for m in r['members']):
            continue
        by = {m['pid']: m for m in r['members']}
        f, m = by[r['flat']], by[r['model']]
        src = Image.open(f['flat']).convert('RGBA')
        src_lab, _ = UV.garment_lab(src)
        out, share = UV.recolour(src, src_lab, np.array(m['model_lab']))
        path = f"{UV.OUT}/{r.get('row', r['flat'])}-mc.webp"
        out.save(path, 'WEBP', quality=88, method=5)
        glab, _ = UV.garment_lab(out)
        r['recolour'] = dict(asset_path=os.path.relpath(path, ROOT), source=r.get('row', r['flat']),
                             recolour_source=';'.join([f['image'], m['image']]),
                             target_lab=m['model_lab'], recoloured_share=round(share, 3),
                             result_to_model_de=round(UV.de(glab, m['model_lab']), 1),
                             applied=bool(write))
        cells += [dict(path=f['flat'], label=f"{r['flat']} flat lay\nIMG_{f['image'][-8:-4]}"),
                  dict(path=m['model'], label=f"{r['model']} model\nIMG_{m['image'][-8:-4]}"),
                  dict(path=path, label=f"recoloured to the model\ndE {r['flat_model_de']} -> "
                                        f"{r['recolour']['result_to_model_de']}")]
    from contact_sheet import sheet as grid
    out = CAT + '/sheets/same-product-recolour-preview.jpg'
    grid(cells, out, cols=6, cell=220, label_h=40,
         title=f'Flat lay recoloured to the model photo, pairs above dE {threshold}'
               + ('' if write else ' — preview, not applied'))
    print(len(cells) // 3, 'pairs above', threshold, '->', out)


def sheet(res):
    """One row per group: flat | model | the two measured colours | dE."""
    rows = [r for r in res if r['flat'] or r['model']]
    cell, pad = 220, 10
    W = 4 * (cell + pad) + 420
    H = 60 + len(rows) * (cell + 34 + pad)
    im = Image.new('RGB', (W, H), GREY)
    d = ImageDraw.Draw(im)
    d.text((pad, 14), 'Same product, same colour: flat lay, model, measured colours, dE2000',
           font=_font(22, True), fill=(20, 20, 20))
    f = _font(15)
    y = 60
    for r in rows:
        by = {m['pid']: m for m in r['members']}
        x = pad
        for pic in ((by[r['flat']]['flat'] if r['flat'] else None),
                    (by[r['model']]['model'] if r['model'] else None)):
            if pic and os.path.exists(pic):
                t = Image.open(pic).convert('RGBA')
                t.thumbnail((cell, cell))
                bg = Image.new('RGBA', (cell, cell), GREY + (255,))
                bg.alpha_composite(t, ((cell - t.width) // 2, (cell - t.height) // 2))
                im.paste(bg.convert('RGB'), (x, y))
            x += cell + pad
        for lab in (r['flat_lab'], (by[r['model']].get('model_lab') if r['model'] else None)):
            if lab:
                d.rectangle([x, y, x + cell - 1, y + cell - 1], fill='#' + EC.lab_to_hex(tuple(lab)).lstrip('#'))
            x += cell + pad
        lines = [' + '.join(m['pid'] for m in r['members']),
                 ' / '.join(f"IMG_{m['image'][-8:-4]} {m['layout']}" for m in r['members']),
                 f"dE flat/model: {r['flat_model_de']}" if r['flat_model_de'] is not None else 'dE: no flat+model',
                 'same product' if r['same'] else 'NOT the same: ' + r['why'][0][:48]]
        for i, t in enumerate(lines):
            d.text((x, y + 8 + i * 22), t[:52], font=f, fill=(20, 20, 20))
        y += cell + 34 + pad
    out = CAT + '/sheets/same-product-pairs.jpg'
    im.save(out, 'JPEG', quality=84)
    print(out)


def merge(batches, res):
    """Fold each confirmed group into one row: the flat lay's, flat lay first."""
    by = {b['product_id']: b for b in batches}
    drop = set()
    n = 0
    for r in res:
        if not r['same']:
            continue
        order = sorted(r['members'], key=lambda m: (m['flat'] is None, m['image']))
        keep = order[0]['pid']          # the flat lay's row, so its shot type is the flat one
        by[keep]['images'] = [m['image'] for m in order]
        drop.update(m['pid'] for m in order[1:])
        n += 1
    out = [b for b in batches if b['product_id'] not in drop]
    json.dump(out, open(CAT + '/batches.json', 'w'), indent=1)
    print(f'merged {n} groups; {len(drop)} rows folded into the row of their first screenshot')


if __name__ == '__main__':
    main()
