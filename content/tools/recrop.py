"""Re-cut every picture whose crop lost part of the piece — 25 September, Part 1.

crop_fix.py measured, against the original screenshot, which pictures cut the
piece off at their own edge while the screenshot still holds all of it
(`state: cut`, with `widened`: the piece's bounds plus a margin). This puts it
right, in the order the pictures were made:

  whole-page pictures   the review copy is made again from the widened crop
                        (`origin` moves, `origin_prev` keeps the old one so a
                        box she drew follows its pixels — migrate_trim.py),
                        with new item/person boxes and a new whole cut-out
  grid cells            the cell is cut again from the widened box, with the
                        same cut and measurement read_grids.py makes
  panels                a panel was split off at a gutter: it IS the
                        photograph, so nothing past it belongs to the piece.
                        Never widened; crop_fix.py reports them as photo_edge.

and then the shelf cut-out of every product whose cut-out came from a widened
picture, cut again from the full-resolution screenshot with soft_cut.py.
Also re-cut: a colourway row split out of another whose cut-out was the
parent's own file (split_mixed.seed fell back to copying it when the row had
no whole cut-out yet), from its own picture; and the three worn bags that
crop_figures.py had cropped to a fixed band, from a box read by eye.

Her decisions:
  a box (item, person, full, her own) is on the photo and follows it — kept
  a cut-out she accepted is kept when the new cut only gained at its edges:
      the old cut is still inside the new one, and what was added lies past
      the old crop's edge. Otherwise it goes back to Review, saying why.
  a removed piece stays removed; the better cut waits under Removed
  undecided: nothing to keep

  python3 content/tools/recrop.py --run         # do it (hours of rembg on a CPU)
  python3 content/tools/recrop.py --sheet       # before/after sheets, bags first

The old files are kept in content/catalogue/before-recrop/. Writes
_recrop.json: what was re-cut, and each decision's fate.
"""
import os, sys, io, json, csv, shutil, argparse, collections
import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
CAT = ROOT + '/content/catalogue'
STUDIO = ROOT + '/studio'
KEEP = CAT + '/before-recrop'
LOG = CAT + '/_recrop.json'
SEND_VERSION = '2026-09-25-recrop'

# Bags on a person that crop_figures.py cut to a fixed band (22-78% of the
# figure's height). A bag hangs where it hangs; these boxes were read by eye
# from the screenshots, in the screenshot's own pixels [x0, y0, x1, y1].
WORN_BAGS_BY_EYE = {
    'B043-P005': [380, 625, 1115, 2525],     # snakeskin shoulder bag: strap and body, worn at the hip
    'B043-P006': [752, 1388, 1145, 1696],    # the clutch in her hand
    'B053-P005': [127, 1081, 933, 1940],     # black hobo on the shoulder
}

# Cut-outs whose fault is the cut, not the crop, read by eye.
RECUT_BY_EYE = {
    'B089-P002-V2': 'the backdrop left inside the handle loop (the old hard cut kept it; soft_cut punches it)',
}


def load(name, default):
    try:
        return json.load(open(CAT + '/' + name))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def keep_old(path):
    """Copy a file into before-recrop/ once, keeping its place under the catalogue."""
    if not os.path.exists(path):
        return
    rel = os.path.relpath(path, CAT)
    dst = os.path.join(KEEP, rel)
    if not os.path.exists(dst):
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(path, dst)


def shot_crop(src, rect):
    """The screenshot at full resolution, cropped to rect [x0, y0, x1, y1]."""
    with Image.open(ROOT + '/' + src) as im:
        return im.convert('RGB').crop(tuple(int(round(v)) for v in rect[:4]))


def entry_of(review, owner, j):
    rv = review.get(owner) or {}
    imgs = rv.get('images') or []
    return imgs[j] if j < len(imgs) else None


# ------------------------------------------------------------ the pictures
def redo_whole_page(review, owner, j, src, widened, slot):
    """The review copy of screenshot j of `owner`, from the widened crop."""
    import build_review_images as BR
    e = entry_of(review, owner, j)
    if not e or 'origin' not in e:
        return False
    OW, OH = e['origin'][4], e['origin'][5]
    x0, y0, x1, y1 = [int(round(v)) for v in widened]
    for p in [CAT + '/' + e['path']] + ([CAT + '/' + e['whole']['path']] if e.get('whole') else []):
        keep_old(p)
    full = BR.fit(shot_crop(src, [x0, y0, x1, y1]), BR.MAXSIDE)
    full.save(CAT + '/' + e['path'], 'JPEG', quality=86, optimize=True)
    person, item, found = BR.boxes_for(full, slot)
    stem = e['path'][len('review/'):-4]
    e.update(w=full.size[0], h=full.size[1], person=person, item=item, mask_found=found,
             bytes=os.path.getsize(CAT + '/' + e['path']),
             # a second widening keeps the crop from before the first, so her
             # boxes move from where she drew them in one step
             origin_prev=list(e['origin_prev'] if e.get('widened_by') and e.get('origin_prev') else e['origin']),
             origin=[x0, y0, x1 - x0, y1 - y0, OW, OH],
             widened_by='crop_fix')
    w = BR.whole_cutout(full)
    if w:
        w.save(f'{CAT}/review/{stem}-whole.webp', 'WEBP', quality=88, method=5)
        e['whole'] = dict(path=f'review/{stem}-whole.webp', w=w.size[0], h=w.size[1],
                          bytes=os.path.getsize(f'{CAT}/review/{stem}-whole.webp'))
    if j == 0:
        review[owner].update({k: e[k] for k in ('w', 'h', 'person', 'item', 'mask_found', 'bytes')})
    return True


def cell_widened(review, grids, owner, j, cell_path, r):
    """The widened box of a cell, kept out of every other cell's tile
    (crop_fix.clear_of), in the screenshot's pixels."""
    import crop_fix
    e = entry_of(review, owner, j)
    g = grids.get(f'{owner}#{j}') or {}
    if not e or 'origin' not in e:
        return r['widened']
    ox, oy, ow, oh = e['origin'][:4]
    at = lambda b: [ox + b[0] * ow, oy + b[1] * oh, ox + (b[0] + b[2]) * ow, oy + (b[1] + b[3]) * oh]  # noqa: E731
    rp = cell_path.replace('full/', 'review/')
    others = [at(c['read_box']) for c in g.get('cells') or [] if c.get('path') != rp and c.get('read_box')]
    return crop_fix.clear_of(r['widened'], r['crop'], others)


def redo_cell(review, grids, flats, owner, j, cell_path, widened, batches):
    """A grid cell cut again from its widened box, as read_grids.py cuts it."""
    import read_grids as RG
    key = f'{owner}#{j}'
    g = grids.get(key) or {}
    e = entry_of(review, owner, j)
    if not e or 'origin' not in e:
        return None
    rp = cell_path.replace('full/', 'review/')
    k = next((n for n, c in enumerate(g.get('cells') or []) if c.get('path') == rp), None)
    if k is None:
        return None
    c = g['cells'][k]
    ox, oy, ow, oh = e['origin'][:4]
    x0, y0, x1, y1 = widened
    frac = [round(max(0, (x0 - ox) / ow), 4), round(max(0, (y0 - oy) / oh), 4),
            round(min(1, (x1 - ox) / ow) - max(0, (x0 - ox) / ow), 4),
            round(min(1, (y1 - oy) / oh) - max(0, (y0 - oy) / oh), 4)]
    stem = os.path.basename(e['path'])[:-4]
    jj = int(rp.rsplit('c', 1)[1].split('.')[0])
    for p in [CAT + '/' + c['path']] + ([CAT + '/' + c['cut']] if c.get('cut') else []):
        keep_old(p)
    hi = RG.original(e, batches.get(owner), j)
    rec = RG.cut_cell(hi if hi is not None else Image.open(CAT + '/' + e['path']).convert('RGB'), frac, stem, jj)
    c.update(rec, box=frac, snap_before=c.get('snap_before') or c.get('box'), snap='widened to the piece (crop_fix)')
    cid = RG.cell_id(owner, j, jj)
    flats[cid] = {**(flats.get(cid) or {}), 'clean': bool(rec.get('clean')), 'why': rec.get('why', ''),
                  'flat': True, 'from_cell': rec.get('cut') or rec['path'], 'measured_by': 'recrop'}
    return cid


# ------------------------------------------------------------ the shelf cut-out
def soft_recut(src_img, slot):
    """soft_cut.cut, keeping where the cut sits in the picture it was cut from:
    -> (RGBA, info, (x0, y0, scale)) with x0, y0 in the picture's pixels."""
    import soft_cut as SC
    where = {}
    orig = SC.finish

    def finish(rgb, alpha, pad=0.02, max_side=SC.MAX_OUT):
        a8 = (np.clip(alpha, 0, 1) * 255 + 0.5).astype(np.uint8)
        ys, xs = np.nonzero(a8 > 3)
        if len(xs):
            H, W = a8.shape
            m = int(pad * max(H, W))
            x0, x1 = max(0, xs.min() - m), min(W, xs.max() + 1 + m)
            y0, y1 = max(0, ys.min() - m), min(H, ys.max() + 1 + m)
            k = min(1.0, max_side / max(x1 - x0, y1 - y0))
            where.update(x0=x0, y0=y0, k=k)
        return orig(rgb, alpha, pad, max_side)
    SC.finish = finish
    try:
        out, info = SC.cut(src_img, slot=slot)
    finally:
        SC.finish = orig
    return out, info, (where.get('x0', 0), where.get('y0', 0), where.get('k', 1.0))


def mask_in_shot(rgba, x0, y0, k, s=0.25):
    """An RGBA cut-out placed at (x0, y0) of the screenshot with scale k (cut px
    per screenshot px) -> (boolean mask at scale s of the screenshot, offset)."""
    a = np.asarray(rgba.getchannel('A')) > 128
    h, w = a.shape
    W, H = max(1, int(w / k * s)), max(1, int(h / k * s))
    m = np.asarray(Image.fromarray(a.astype(np.uint8) * 255).resize((W, H), Image.NEAREST)) > 0
    return m, (int(x0 * s), int(y0 * s))


def compare(old_m, old_at, new_m, new_at, old_crop, s=0.25):
    """How the new cut differs from the old: share of the old kept, share of
    the new, and where what was added lies (past the old crop's edge or not)."""
    X0 = min(old_at[0], new_at[0]); Y0 = min(old_at[1], new_at[1])
    X1 = max(old_at[0] + old_m.shape[1], new_at[0] + new_m.shape[1])
    Y1 = max(old_at[1] + old_m.shape[0], new_at[1] + new_m.shape[0])
    A = np.zeros((Y1 - Y0, X1 - X0), bool); B = np.zeros_like(A)
    A[old_at[1] - Y0:old_at[1] - Y0 + old_m.shape[0], old_at[0] - X0:old_at[0] - X0 + old_m.shape[1]] = old_m
    B[new_at[1] - Y0:new_at[1] - Y0 + new_m.shape[0], new_at[0] - X0:new_at[0] - X0 + new_m.shape[1]] = new_m
    kept = (A & B).sum() / max(1, A.sum())
    added = B & ~A
    inside = np.zeros_like(A)
    cx0, cy0, cx1, cy1 = [int(v * s) for v in old_crop]
    inside[max(0, cy0 - Y0):max(0, cy1 - Y0), max(0, cx0 - X0):max(0, cx1 - X0)] = True
    past = (added & ~inside).sum() / max(1, added.sum())
    return dict(kept=round(float(kept), 3), added=round(float(added.sum() / max(1, B.sum())), 3),
                added_past_old_crop=round(float(past), 3))


def edges_only(c):
    """Only the edges improved: the old cut is still there, and what is new
    is mostly the part the old crop cut off (or very little)."""
    return c['kept'] >= 0.9 and (c['added'] <= 0.03 or c['added_past_old_crop'] >= 0.6)


def locate_old(asset_path, picture_path, origin):
    """Where the old shelf cut-out sat in the screenshot, via the old review
    copy it was cut from (edge_clip.locate) -> (x0, y0, k) or None."""
    import edge_clip as EC
    if not (os.path.exists(asset_path) and os.path.exists(picture_path)):
        return None
    photo, cut = EC.rgba(picture_path), EC.rgba(asset_path)
    m = EC.locate(photo, cut)
    if m is None:
        return None
    s = photo.shape[1] / origin[2]          # review copy px per screenshot px
    return (origin[0] + m[1] / s, origin[1] + m[2] / s, s)


# ------------------------------------------------------------ the run
def run(only=None):
    import send_to_review as ST
    fix = load('_crop_fix.json', [])
    review = load('_review_boxes.json', {})
    grids = load('_grid_cells.json', {})
    flats = load('_flat_lays.json', {})
    # where each shelf cut-out sits in its pictures, as the first edge_clip.py
    # (PR #31) located it by its own pixels — kept for this, since the
    # redone edge_clip.py measures the screenshot instead
    clips = load('_edge_clips_located.json', {})
    batches = {b['product_id']: b for b in load('batches.json', [])}
    rows = {r['product_id']: r for r in csv.DictReader(open(CAT + '/products.csv'))}
    products = {p['product_id']: p for p in json.load(open(STUDIO + '/data/products.json'))}
    choices = load('asset-choices.json', {}).get('choices', {})
    log = load('_recrop.json', {}) if only else {}
    log.setdefault('pictures', {}); log.setdefault('products', {})
    widened = {}                                 # (pid, idx) -> record
    for r in fix:
        if r.get('state') == 'cut':
            for u in r['users']:
                widened[tuple(u)] = r
    # 1. the pictures, each once
    done_pics = set()
    old_origin = {}                             # (owner, j) -> origin before
    for (pid, i), r in sorted(widened.items()):
        if only and pid not in only:
            continue
        p = products.get(pid)
        if not p:
            continue
        e = p['images'][i]
        owner = p.get('parent_id') or pid
        if e.get('type') == 'cell':
            key = ('cell', e['path'])
            if key in done_pics:
                continue
            done_pics.add(key)
            j = e.get('panel_of', 0) or 0
            cid = redo_cell(review, grids, flats, owner, j, e['path'],
                            cell_widened(review, grids, owner, j, e['path'], r), batches)
            log['pictures'][e['path']] = dict(kind='cell', cell=cid, before=r['crop'], after=r['widened'],
                                              source=r['source'])
        elif (e.get('panel_box') or [0, 0, 1, 1]) == [0, 0, 1, 1]:
            j = e.get('panel_of', i) or 0
            key = ('page', owner, j)
            if key in done_pics:
                continue
            done_pics.add(key)
            ee = entry_of(review, owner, j)
            if ee and 'origin' in ee:
                old_origin[(owner, j)] = list(ee['origin'])
            ok = redo_whole_page(review, owner, j, r['source'], r['widened'], rows.get(pid, {}).get('slot', ''))
            log['pictures'][e['path']] = dict(kind='page', done=ok, before=r['crop'], after=r['widened'],
                                              source=r['source'])
        print('picture', len(done_pics), pid, flush=True)
        if len(done_pics) % 25 == 0:
            json.dump(review, open(CAT + '/_review_boxes.json', 'w'), indent=1)
            json.dump(grids, open(CAT + '/_grid_cells.json', 'w'), indent=1)
            json.dump(flats, open(CAT + '/_flat_lays.json', 'w'), indent=1)
    json.dump(review, open(CAT + '/_review_boxes.json', 'w'), indent=1)
    json.dump(grids, open(CAT + '/_grid_cells.json', 'w'), indent=1)
    json.dump(flats, open(CAT + '/_flat_lays.json', 'w'), indent=1)

    # 2. the shelf cut-outs
    same_as_parent = copied_from_parent(rows)
    sends = {}
    for pid, p in sorted(products.items()):
        if only and pid not in only:
            continue
        r0 = rows.get(pid) or {}
        ap = ROOT + '/' + r0.get('asset_path', '')
        if (not r0.get('asset_path') or '/assets/' not in r0['asset_path']
                or p.get('recoloured') or p['asset_type'] == 'crop' or p.get('parent_id')):
            continue                            # a cell's cut-out is its cell's; a recolour is made
        cl = clips.get(pid) or {}
        src_i = (cl.get('asset') or {}).get('picture')
        why = None
        if pid in WORN_BAGS_BY_EYE:
            why = 'worn bag cropped to a fixed band'
        elif pid in RECUT_BY_EYE:
            why = RECUT_BY_EYE[pid]
        elif pid in same_as_parent:
            why = f'the cut-out was {same_as_parent[pid]}\'s, not this row\'s own picture'
            src_i = p.get('primary') or 0
        elif src_i is not None and (pid, src_i) in widened and (cl.get('asset') or {}).get('sides'):
            why = 'the crop cut the piece off at ' + ', '.join(cl['asset']['sides'])
        elif pid in (log.get('products') or {}) and (log['products'][pid].get('picture') is not None) \
                and (pid, log['products'][pid]['picture']) in widened:
            # re-cut in an earlier pass, and its picture widened again
            src_i = log['products'][pid]['picture']
            why = log['products'][pid].get('why') or 'the picture it came from was widened again'
        elif not cl.get('asset') and p['asset_type'] in ('cutout_flat', 'tile'):
            # a cut-out that cannot be found in its own pictures (made from
            # another crop of the page by make_assets) while one of them was
            # widened: cut again from the widened one
            hit = [i for i in range(len(p.get('images') or [])) if (pid, i) in widened]
            if hit:
                src_i = p.get('primary') if p.get('primary') in hit else hit[0]
                why = 'the picture it came from was widened to the whole piece'
        if not why:
            continue
        e = p['images'][src_i] if p.get('images') and src_i is not None and src_i < len(p['images']) else None
        if not e:
            continue
        owner = p.get('parent_id') or pid
        j = e.get('panel_of', src_i) or 0
        ee = entry_of(review, owner, j)
        if not ee or 'origin' not in ee:
            continue
        ox, oy, ow, oh = ee['origin'][:4]
        pb = e.get('panel_box') or [0, 0, 1, 1]
        rect = [ox + pb[0] * ow, oy + pb[1] * oh, ox + (pb[0] + pb[2]) * ow, oy + (pb[1] + pb[3]) * oh]
        if pid in WORN_BAGS_BY_EYE:
            rect = WORN_BAGS_BY_EYE[pid]
        slot = r0.get('slot', '')
        picture = shot_crop(e['source'], rect)
        out, info, (x0, y0, k) = soft_recut(picture, slot)
        if out is None:
            log['products'][pid] = dict(why=why, result='nothing cut; kept the old cut-out')
            continue
        # skin share alone does not say worn for these: tan leather sits in the
        # skin band. The picture's own type or the gate's reading does.
        on_person = e.get('type') == 'on-model' or 'model' in (p.get('hold') or '') \
            or 'wearing' in (p.get('hold') or '')
        if on_person and not info.get('cloth') and slot in ('bag', 'shoes', 'accessory') \
                and pid not in WORN_BAGS_BY_EYE:
            log['products'][pid] = dict(why=why, result='on a person, and the piece cannot be cut '
                                        'off them: kept the old cut-out', info=info)
            continue
        # where the old one sat, from the old review copy it was matched in
        prev = old_origin.get((owner, j)) or ee.get('origin_prev') or ee['origin']
        old_at = locate_old(ap, KEEP + '/' + ee['path'] if os.path.exists(KEEP + '/' + ee['path'])
                            else CAT + '/' + ee['path'], prev)
        keep_old(ap)
        out.save(ap, 'WEBP', quality=90, method=5)
        rec = dict(why=why, picture=src_i, rect=[round(v) for v in rect], info=info)
        if old_at is not None:
            om, oa = mask_in_shot(Image.open(KEEP + '/' + os.path.relpath(ap, CAT)), old_at[0], old_at[1], old_at[2])
            nm, na = mask_in_shot(out, rect[0] + x0, rect[1] + y0, k)
            old_crop = [prev[0], prev[1], prev[0] + prev[2], prev[1] + prev[3]]
            rec['compare'] = compare(om, oa, nm, na, old_crop)
        c = choices.get(pid) or {}
        cat_choice = r0.get('asset_choice')
        choice = c.get('choice') or cat_choice
        hidden = c.get('hidden') or r0.get('shelf') == 'hidden'
        if hidden:
            rec['decision'] = 'removed: stays removed'
        elif choice in ('cutout', 'whole'):
            if 'compare' in rec and edges_only(rec['compare']) and pid not in same_as_parent:
                rec['decision'] = 'kept: only the edges improved'
            else:
                rec['decision'] = 'back to Review'
                sends[pid] = ('re-cut 25 Sept: ' + why + '; the new cut-out takes in what the old crop '
                              'left out, and changed more than its edges. Decide again.')
        elif choice:
            rec['decision'] = f'kept: {choice} is a box on the photo, moved to the same pixels'
        else:
            rec['decision'] = 'undecided'
        log['products'][pid] = rec
        print('cut-out', pid, rec['decision'], rec.get('compare'), flush=True)
        json.dump(log, open(LOG, 'w'), indent=1)
    if sends:
        ST.send(SEND_VERSION, sends)
    log['sent_to_review'] = sorted(set(log.get('sent_to_review') or []) | set(sends))
    json.dump(log, open(LOG, 'w'), indent=1)


def copied_from_parent(rows):
    """Colourway rows whose cut-out file is byte for byte another row's, though
    their screenshots are not: split_mixed.seed copied the parent's."""
    import hashlib
    by = collections.defaultdict(list)
    for pid, r in rows.items():
        p = ROOT + '/' + r['asset_path']
        if r['asset_path'] and '/assets/' in r['asset_path'] and os.path.exists(p):
            by[hashlib.md5(open(p, 'rb').read()).hexdigest()].append(pid)
    out = {}
    for pids in by.values():
        if len(pids) < 2:
            continue
        base = min(pids, key=len)
        for pid in pids:
            if pid != base and pid.startswith(base + '-V') and rows[pid]['image_paths'] != rows[base]['image_paths']:
                out[pid] = base
    return out


# ------------------------------------------------------------ the sheet
def sheet(out_dir):
    """Before and after, bags first: the old picture and cut-out beside the new."""
    log = load('_recrop.json', {})
    rows = {r['product_id']: r for r in csv.DictReader(open(CAT + '/products.csv'))}
    order = {'bag': 0, 'shoes': 1, 'accessory': 2}
    items = []
    for pid, rec in log.get('products', {}).items():
        before = KEEP + '/' + os.path.relpath(ROOT + '/' + rows[pid]['asset_path'], CAT)
        items.append((order.get(rows[pid]['slot'], 3), rows[pid]['slot'], pid, before,
                      ROOT + '/' + rows[pid]['asset_path'], rec.get('decision', rec.get('result', ''))))
    for path, rec in log.get('pictures', {}).items():
        if rec.get('kind') != 'cell':
            continue
        cid = rec.get('cell')
        if not cid or cid not in rows:
            continue
        a = rows[cid]['asset_path']
        items.append((order.get(rows[cid]['slot'], 3), rows[cid]['slot'], cid,
                      KEEP + '/' + os.path.relpath(ROOT + '/' + a, CAT), ROOT + '/' + a, 'cell re-cut'))
    items.sort()
    os.makedirs(out_dir, exist_ok=True)
    T, per = 220, 24
    for n in range(0, len(items), per):
        part = items[n:n + per]
        cols = 4
        rows_n = (len(part) + cols - 1) // cols
        S = Image.new('RGB', (cols * (2 * T + 30), rows_n * (T + 34)), (236, 236, 236))
        d = ImageDraw.Draw(S)
        for k, (_, slot, pid, b, a, note) in enumerate(part):
            x, y = (k % cols) * (2 * T + 30), (k // cols) * (T + 34)
            for m, pth in enumerate((b, a)):
                if not os.path.exists(pth):
                    continue
                im = Image.open(pth).convert('RGBA')
                im.thumbnail((T, T))
                tile = Image.new('RGBA', (T, T), (205, 215, 205, 255) if m else (225, 205, 205, 255))
                tile.alpha_composite(im, ((T - im.width) // 2, (T - im.height) // 2))
                S.paste(tile.convert('RGB'), (x + m * (T + 6), y))
            d.text((x, y + T + 2), f'{pid} · {slot}', fill=(0, 0, 0))
            d.text((x, y + T + 16), note[:60], fill=(90, 90, 90))
        S.save(f'{out_dir}/recrop-{n // per + 1:02d}.jpg', quality=85)
    print(len(items), 'before/after pairs in', out_dir)



def send_browser_only(version, products):
    """A review-sends.json version the desk applies only to pictures she took
    in her own browser (`only_chosen`): nothing is written to asset-choices.json,
    so a clean piece nobody decided stays on the shelf and a removed one stays
    removed."""
    path = CAT + '/review-sends.json'
    sends = load('review-sends.json', {'versions': []})
    sends['versions'] = [v for v in sends['versions'] if v.get('version') != version]
    if products:
        sends['versions'].append(dict(version=version, only_chosen=True, products=products))
    sends['versions'].sort(key=lambda v: v['version'])
    json.dump(sends, open(path, 'w'), indent=1)


def decide_cells():
    """The same rule for the grid cells re-cut: a cell she took keeps its
    choice when its new cut only gained at the edges. Both cuts come from the
    same full-resolution crop of the grid page, so the old one is found in the
    new cell photograph by its own pixels."""
    import send_to_review as ST
    import edge_clip as EC
    log = load('_recrop.json', {})
    choices = load('asset-choices.json', {}).get('choices', {})
    rows = {r['product_id']: r for r in csv.DictReader(open(CAT + '/products.csv'))}
    grids = load('_grid_cells.json', {})
    by_path = {c['path']: c for g in grids.values() for c in g.get('cells') or []}
    sends = {}
    for path, rec in log.get('pictures', {}).items():
        cid = rec.get('cell')
        if rec.get('kind') != 'cell' or not cid:
            continue
        c = choices.get(cid) or {}
        r0 = rows.get(cid) or {}
        choice = c.get('choice') or r0.get('asset_choice')
        hidden = c.get('hidden') or r0.get('shelf') == 'hidden'
        cell = by_path.get(path.replace('full/', 'review/')) or {}
        old_cut = KEEP + '/' + (cell.get('cut') or '')
        new_cut, new_img = CAT + '/' + (cell.get('cut') or ''), CAT + '/' + cell.get('path', '')
        cmp_ = None
        if cell.get('cut') and os.path.exists(old_cut) and os.path.exists(new_cut) and os.path.exists(new_img):
            photo = EC.rgba(new_img)
            mo, mn = EC.locate(photo, EC.rgba(old_cut)), EC.locate(photo, EC.rgba(new_cut))
            if mo and mn:
                om = np.asarray(Image.open(old_cut).getchannel('A')) > 128
                nm = np.asarray(Image.open(new_cut).getchannel('A')) > 128
                # the old crop, in the new cell photograph's pixels
                sx = photo.shape[1] / max(1, rec['after'][2] - rec['after'][0])
                oc = [(rec['before'][0] - rec['after'][0]) * sx, (rec['before'][1] - rec['after'][1]) * sx,
                      (rec['before'][2] - rec['after'][0]) * sx, (rec['before'][3] - rec['after'][1]) * sx]
                cmp_ = compare(om, (mo[1], mo[2]), nm, (mn[1], mn[2]), [v / 1.0 for v in oc], s=1.0)
        rec['compare'] = cmp_
        if hidden:
            rec['decision'] = 'removed: stays removed'
        elif choice:
            if cmp_ and edges_only(cmp_):
                rec['decision'] = 'kept: only the edges improved'
            else:
                rec['decision'] = 'back to Review'
                sends[cid] = ('re-cut 25 Sept: the cell\'s crop cut the piece off; the new cut takes in what it '
                              'left out, and changed more than its edges. Decide again.')
        else:
            rec['decision'] = 'undecided'
    if sends:
        ST.send(SEND_VERSION + '-cells', sends)
    log['cells_sent_to_review'] = sorted(sends)
    # a decision kept only in her browser: the cells whose cut changed more
    # than its edges, and the re-cut rows the catalogue has undecided, go out
    # as a send the desk applies only to a picture she took there
    browser = {}
    reason = ('re-cut 25 Sept: the crop had cut the piece off; the new cut-out takes in what it left out, '
              'and changed more than its edges. Decide again.')
    for rec in log.get('pictures', {}).values():
        if rec.get('kind') == 'cell' and rec.get('cell') and rec.get('decision') == 'undecided' \
                and not (rec.get('compare') and edges_only(rec['compare'])):
            browser[rec['cell']] = reason
    for pid, rec in log.get('products', {}).items():
        if rec.get('decision') == 'undecided' and not (rec.get('compare') and edges_only(rec['compare'])):
            browser[pid] = reason
    send_browser_only(SEND_VERSION + '-browser', browser)
    log['browser_sends'] = sorted(browser)
    json.dump(log, open(LOG, 'w'), indent=1)
    print(collections.Counter(r.get('decision', '').split(':')[0] for r in log['pictures'].values()
                              if r.get('kind') == 'cell'))


def sync_owner_cells():
    """_picture_owners.json keeps each cell's picture entry (box, size, cut) as
    colourway_pictures.py last wrote it; build_studio.py hands that entry to the
    desk. After a re-cut it must say the new box and sizes."""
    own = load('_picture_owners.json', {})
    grids = load('_grid_cells.json', {})
    by = {c['path']: c for g in grids.values() for c in g.get('cells') or []}
    n = 0
    for pid, e in (own.get('cells') or {}).items():
        c = by.get(e['path'].replace('full/', 'review/'))
        if not c or not c.get('box'):
            continue
        if e.get('panel_box') == c['box'] and e.get('w') == c.get('w'):
            continue
        e.update(panel_box=c['box'], w=c.get('w', e.get('w')), h=c.get('h', e.get('h')))
        if c.get('cut') and os.path.exists(CAT + '/' + c['cut']):
            with Image.open(CAT + '/' + c['cut']) as im:
                e['whole'] = dict(path='full/' + os.path.basename(c['cut']), w=im.width, h=im.height)
        n += 1
    json.dump(own, open(CAT + '/_picture_owners.json', 'w'), indent=1)
    print('cell entries brought up to date:', n)

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--run', action='store_true')
    ap.add_argument('--only', nargs='*')
    ap.add_argument('--sheet', default='')
    ap.add_argument('--cells', action='store_true', help='decide the re-cut cells (after --run)')
    a = ap.parse_args()
    if a.run:
        run(set(a.only) if a.only else None)
    if a.cells:
        decide_cells()
        sync_owner_cells()
    if a.sheet:
        sheet(a.sheet)
