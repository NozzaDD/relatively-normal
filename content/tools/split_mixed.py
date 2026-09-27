"""One row per garment, where the clustering left several garments in one row.

cluster_products.py groups screenshots by page layout, which is right for
finding where one shop's run of pages begins and ends and wrong for telling
two of its products apart: consecutive pages from the same shop look identical,
so a navy jacket, a pair of cream trousers and a brown checked coat end up in
one product with one filmstrip.

Colour is what separates them, and colour is decisive on its own: the same
style in navy and in cream is two things to put on a shelf, not one thing twice.
Where the page gave a style or product name it is written on every row the split
produces, and each row records the product it was split from, so the pair stay
findable together the way the recoloured variants do.

  python3 content/tools/split_mixed.py [--check] [--threshold 18]

Listing grids are left alone: a grid screenshot is a page of a dozen products,
its dominant colour means nothing, and grid_cells.py already cuts it up.

Writes content/catalogue/_product_splits.json, rewrites batches.json, copies
each group's pictures under its own name, and extends _review_boxes.json,
_panels.json, _flat_lays.json, _assets.json, _colours.json and the viewing rows
so the new rows are ordinary products from here on. Originals are never touched.
"""
import os, sys, json, shutil, argparse, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from PIL import Image
import extract_colours as X
from colour_names import classify
from engine import colour as C                          # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CAT = ROOT + '/content/catalogue'
REV = CAT + '/review'
OUT = CAT + '/_product_splits.json'
STAGE = CAT + '/review/_stage'

THRESHOLD = 18           # CIELAB distance at which two garments are two garments
DETAIL = ('text', 'other')


def load(name, default):
    try:
        return json.load(open(CAT + '/' + name))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def picture_for(pid, i, review, panels):
    """The picture that says what colour screenshot i is: a panel cut first."""
    sp = panels.get(f'{pid}#{i}') or {}
    if sp.get('split'):
        for want in ('flat lay', 'on-model'):
            for p in sp['panels']:
                if p['type'] == want and p.get('cut'):
                    return CAT + '/' + p['cut'], True
            for p in sp['panels']:
                if p['type'] == want:
                    return CAT + '/' + p['path'], False
    imgs = review.get(pid, {}).get('images') or []
    if i >= len(imgs) or not imgs[i] or 'error' in imgs[i]:
        return None, False
    e = imgs[i]
    if e.get('whole'):
        return CAT + '/' + e['whole']['path'], True
    return CAT + '/' + e['path'], False


def is_junk(pid, i, panels):
    """A screenshot that is all page furniture founds no product of its own."""
    sp = panels.get(f'{pid}#{i}') or {}
    return bool(sp.get('split')) and all(p['type'] in DETAIL for p in sp['panels'])


def read_colours(path, cut):
    with Image.open(path) as im:
        crop = im.convert('RGBA' if cut else 'RGB')
    cols, skin, kept = X.colours_for_image(crop, is_cutout=cut)
    return cols, skin, kept


def de(a, b):
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


def groups_for(pid, n, review, panels, cache, threshold):
    """Screenshot indices grouped by the colour of the garment in them."""
    labs = []
    for i in range(n):
        if is_junk(pid, i, panels):
            labs.append(None)
            continue
        path, cut = picture_for(pid, i, review, panels)
        if not path or not os.path.exists(path):
            labs.append(None)
            continue
        try:
            cols, skin, kept = read_colours(path, cut)
        except Exception:
            labs.append(None)
            continue
        if not cols:
            labs.append(None)
            continue
        cache[(pid, i)] = (cols, skin, kept)
        labs.append(C.hex_to_lab(cols[0]['hex']))
    gs = []
    for i, l in enumerate(labs):
        if l is None:                         # no colour of its own: it stays put
            (gs[-1] if gs else gs.append([]) or gs[-1]).append(i)
            continue
        placed = False
        for g in gs:
            ref = next((labs[j] for j in g if labs[j] is not None), None)
            if ref is not None and de(l, ref) <= threshold:
                g.append(i)
                placed = True
                break
        if not placed:
            gs.append([i])
    return [g for g in gs if g], labs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true', help='say what would change, change nothing')
    ap.add_argument('--threshold', type=float, default=THRESHOLD)
    args = ap.parse_args()
    import csv
    batches = json.load(open(CAT + '/batches.json'))
    review = load('_review_boxes.json', {})
    panels = load('_panels.json', {})
    flats = load('_flat_lays.json', {})
    assets = load('_assets.json', {})
    colours = load('_colours.json', {})
    rows = {r['product_id']: r for r in csv.DictReader(open(CAT + '/products.csv'))}

    cache, plan = {}, {}
    for b in batches:
        pid = b['product_id']
        if len(b['images']) < 2 or rows.get(pid, {}).get('shot_type') == 'listing grid':
            continue
        gs, _labs = groups_for(pid, len(b['images']), review, panels, cache, args.threshold)
        if len(gs) > 1:
            plan[pid] = gs
    extra = sum(len(g) - 1 for g in plan.values())
    print(f'{len(plan)} products hold more than one garment; '
          f'they become {sum(len(g) for g in plan.values())} rows (+{extra})')
    json.dump({k: v for k, v in plan.items()}, open(OUT, 'w'), indent=1)
    if args.check:
        for pid, gs in list(plan.items())[:8]:
            print('  ', pid, gs)
        return

    apply(plan, batches, review, panels, flats, assets, colours, rows, cache)


def apply(plan, batches, review, panels, flats, assets, colours, rows, cache,
          new_id=None, viewing_name='rows_split.txt', why='by colour'):
    """Give every group in `plan` ({pid: [[screenshot indices], ...]}) a row.

    The group holding screenshot 0 keeps the id, so the decisions and outfits
    that name it still point at the garment they were made on. `new_id(pid, k)`
    names the k-th other group (default `{pid}-V{k+1}`). Shared by
    split_mixed.py (split by colour) and name_split.py (split by what the page
    says)."""
    new_id = new_id or (lambda pid, k: f'{pid}-V{k + 1}')
    # ---- apply. Every file is copied under its new name through a staging
    # folder, so a name that is both a source and a destination cannot clobber.
    os.makedirs(STAGE, exist_ok=True)
    viewing = []
    migration = {}
    new_batches, made = [], 0
    for b in batches:
        pid = b['product_id']
        gs = plan.get(pid)
        if not gs:
            new_batches.append(b)
            continue
        # the original list is read for every group: rewriting review[pid] as
        # the groups are walked would hand the later ones the first group's
        # pictures, which is how V2 ended up holding V1's photograph
        orig = list(review.get(pid, {}).get('images') or [])
        for k, g in enumerate(gs):
            npid = pid if k == 0 else new_id(pid, k)
            new_batches.append(dict(batch_id=b['batch_id'], product_id=npid,
                                    images=[b['images'][i] for i in g]))
            imgs = []
            for j, i in enumerate(g):
                migration[f'{pid}#{i}'] = {'product_id': npid, 'image': j}
                e = dict(orig[i]) if i < len(orig) and orig[i] else None
                if e is None:
                    imgs.append(None)
                    continue
                old_stem = os.path.basename(e['path'])[:-4]
                new_stem = npid if j == 0 else f'{npid}-{j}'
                sp = panels.get(f'{pid}#{i}')
                # The files are named by the records that own them, not found by
                # matching a prefix in the folder: a group that keeps the parent
                # id renames its own later pictures, so a prefix scan can read a
                # name that another group is still about to write.
                wanted = [e['path']] + ([e['whole']['path']] if e.get('whole') else [])
                for pn in (sp or {}).get('panels', []):
                    wanted.append(pn['path'])
                    if pn.get('cut'):
                        wanted.append(pn['cut'])
                if old_stem != new_stem:
                    for rel in wanted:
                        src = f'{CAT}/{rel}'
                        dst = f"{STAGE}/{os.path.basename(rel).replace(old_stem, new_stem, 1)}"
                        if os.path.exists(src):
                            shutil.copyfile(src, dst)
                        else:
                            print('  missing source, skipped:', rel)
                e['path'] = f'review/{new_stem}.jpg'
                if e.get('whole'):
                    e['whole'] = dict(e['whole'], path=f'review/{new_stem}-whole.webp')
                imgs.append(e)
                if sp:
                    sp2 = json.loads(json.dumps(sp))
                    for pn in sp2.get('panels', []):
                        pn['path'] = pn['path'].replace(old_stem, new_stem, 1)
                        if pn.get('cut'):
                            pn['cut'] = pn['cut'].replace(old_stem, new_stem, 1)
                    panels[f'{npid}#{j}'] = sp2
            if npid != pid:
                made += 1
                review[npid] = dict(review.get(pid, {}), images=imgs)
                seed(npid, pid, g, imgs, panels, flats, assets, colours, cache, rows, viewing, why)
            else:
                review[pid] = dict(review.get(pid, {}), images=imgs)
                reseat(pid, g, imgs, panels, flats, assets, colours, cache)
    # staged copies land in review/ only once every read is done
    for f in sorted(os.listdir(STAGE)):
        shutil.move(f'{STAGE}/{f}', f'{REV}/{f}')
    os.rmdir(STAGE)
    json.dump(new_batches, open(CAT + '/batches.json', 'w'), indent=1)
    json.dump(review, open(CAT + '/_review_boxes.json', 'w'), indent=1)
    json.dump(panels, open(CAT + '/_panels.json', 'w'), indent=1)
    json.dump(flats, open(CAT + '/_flat_lays.json', 'w'), indent=1)
    json.dump(assets, open(CAT + '/_assets.json', 'w'), indent=1)
    json.dump(colours, open(CAT + '/_colours.json', 'w'), indent=1)
    if viewing:
        vf = CAT + '/_viewing_rows/' + viewing_name
        old = [ln.rstrip('\n') for ln in open(vf)] if os.path.exists(vf) else []
        mine = {v.split(' | ')[0] for v in viewing}
        with open(vf, 'w') as f:
            f.write('\n'.join([ln for ln in old if ln and ln.split(' | ')[0] not in mine] + viewing) + '\n')
    os.makedirs(ROOT + '/studio/data', exist_ok=True)
    mf = ROOT + '/studio/data/split-migration.json'
    try:
        prev = json.load(open(mf)).get('moved', {})
    except (FileNotFoundError, json.JSONDecodeError):
        prev = {}
    prev.update(migration)
    json.dump({'version': 1, 'moved': prev}, open(mf, 'w'), indent=1)
    print(f'{made} new product rows; {len(migration)} screenshots re-seated')




def colour_record(cols, skin, kept, shot):
    d = {'colours': [], 'skin_share': round(skin, 3), 'kept_share': round(kept, 3)}
    for c in cols[:3]:
        fam, nm, L, Cc, h, rel, nt = classify(c['hex'])
        d['colours'].append({'hex': c['hex'], 'share': round(c['share'], 3), 'L': round(L, 1),
                             'C': round(Cc, 1), 'h': round(h, 1), 'rel': round(rel, 3),
                             'neutral': nt, 'family': fam, 'name': nm})
    d['colour_confidence'] = X.confidence(shot, cols, skin, kept)
    d['colour_stability'] = 'stable'
    return d


def best_of(pid, g, cache):
    for i in g:
        if (pid, i) in cache:
            return cache[(pid, i)]
    return None


def seed(npid, pid, g, imgs, panels, flats, assets, colours, cache, rows, viewing, why='by colour'):
    """Give a new row everything an ordinary product has."""
    got = best_of(pid, g, cache)
    parent = rows.get(pid, {})
    shot = parent.get('shot_type', 'on model')
    if got:
        colours[npid] = colour_record(*got, shot=shot)
    src_asset, fallback = None, None
    for j, e in enumerate(imgs):
        for pn in (panels.get(f'{npid}#{j}') or {}).get('panels', []):
            if pn.get('clean') and pn.get('cut'):
                src_asset = CAT + '/' + pn['cut']
                flats[npid] = {'clean': True, 'why': '', 'flat': True, 'from_panel': pn['path']}
                break
        if src_asset:
            break
        if e and e.get('whole') and not fallback:
            fallback = CAT + '/' + e['whole']['path']
    src_asset = src_asset or fallback
    if src_asset and os.path.exists(src_asset):
        with Image.open(src_asset) as im:
            im.convert('RGBA').save(f'{CAT}/assets/{npid}.webp', 'WEBP', quality=90, method=5)
        assets[npid] = dict(assets.get(pid, {}),
                            asset_path=f'content/catalogue/assets/{npid}.webp',
                            bytes=os.path.getsize(f'{CAT}/assets/{npid}.webp'),
                            note='split out of %s: its own garment, its own colours' % pid)
        assets[npid].setdefault('asset_type', 'cutout_model')
        assets[npid].setdefault('asset_quality', 'good')
    elif imgs and imgs[0] and imgs[0].get('path') and os.path.exists(CAT + '/' + imgs[0]['path']):
        # no clean panel and no whole cut-out yet: cut the row's OWN picture.
        # Copying the parent's cut-out (as this did until 25 Sept) gave 37
        # colourway rows the parent's colour — B090-P009-V2 burgundy on a tan page.
        import soft_cut
        with Image.open(CAT + '/' + imgs[0]['path']) as im:
            out, _info = soft_cut.cut(im.convert('RGB'), slot=parent.get('slot', ''))
        if out is not None:
            out.save(f'{CAT}/assets/{npid}.webp', 'WEBP', quality=90, method=5)
            assets[npid] = dict(assets.get(pid, {}), asset_path=f'content/catalogue/assets/{npid}.webp',
                                bytes=os.path.getsize(f'{CAT}/assets/{npid}.webp'),
                                note='split out of %s: cut from its own picture' % pid)
    # the viewing pass described the page, which is still true of every group;
    # the style name is kept on all of them so the rows stay findable together
    v = parent
    viewing.append(' | '.join([npid, v.get('slot', ''), v.get('garment_type', ''),
                               v.get('material_visible', ''), v.get('pattern', ''),
                               str(v.get('weight', '')), str(v.get('formality', '')),
                               shot, v.get('complete_in_frame', ''), v.get('shop', ''),
                               v.get('brand', ''), v.get('product_name', ''), 'NONE',
                               v.get('material', ''), v.get('price', ''),
                               'split out of %s %s; slot and garment type are '
                               'the parent\'s and may describe the parent\'s garment '
                               '— worth a look' % (pid, why)]))


def reseat(pid, g, imgs, panels, flats, assets, colours, cache):
    """The group that keeps the original id still needs its own colours."""
    got = best_of(pid, g, cache)
    if got and pid in colours:
        colours[pid] = colour_record(*got, shot='on model')


if __name__ == '__main__':
    main()
