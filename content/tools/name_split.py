"""One row per product, told apart by what each page says about itself.

split_mixed.py separates the garments in a row by colour, and cannot separate
the ones that are close in colour: three Levi's jeans in three washes stayed in
one row as three "pictures". A product page names its product, and that is the
first thing to ask. Two screenshots stay in one row only when they agree on
every one of these that both of them show:

  - the product name read off the page      (page_text.py)
  - the page's colour or wash name
  - a visible product number
  - the shop, from Safari's address bar

Where none of the first three is legible on both, the pictures decide: the
garments' lightness differing by more than 8 L*, or their silhouettes
overlapping less than 0.9 (IoU, on the largest piece of each cut-out, each
scaled to its own box). Neither test is made across kinds: a Margaret Howell
jumper flat and worn measured 8.0 and 8.9 L* apart, a Lemaire blouson 8.3, and
a flat lay never overlaps its own garment worn by 0.9. The kind is panels.py's
typing where the page was split into photographs, else whether the cut shows
skin. The silhouette test needs panels.py's typing on both: on an untyped page
the skin share cannot tell trousers on legs or loafers on feet from a
packshot, and it split three such products from themselves (B021-P015,
B037-P004, B078-P001). What the thresholds alone would have split is in the
report (`literal` in the JSON).

Grouping is complete-link: a screenshot joins a group only if it is compatible
with every screenshot already in it. The group holding the first screenshot
keeps the row's id, and with it every decision and outfit that names the row;
the others become `{root}-V{n}` with the next free n. Decisions made on a
screenshot follow the screenshot (asset-choices.json here, the browser's own
through studio/data/picture-migration.json, written by build_studio.py).

  python3 content/tools/name_split.py --check     # report, change nothing
  python3 content/tools/name_split.py             # split
  python3 content/tools/name_split.py --only B090-P013 ...

Listing grids are left alone (grid_cells.py and read_grids.py cut those).
Writes content/catalogue/_name_splits.json with every pair's reason.
"""
import os, sys, re, json, csv, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import numpy as np
import page_text as T
import split_mixed as SM
from engine import colour as C

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CAT = ROOT + '/content/catalogue'
OUT = CAT + '/_name_splits.json'

L_MAX = 8.0          # L* between two garments before they are two
IOU_MIN = 0.9        # silhouette overlap below which they are two
SKIN_MODEL = 0.03
# Rows the thresholds split and the contact sheet says are one product; kept
# whole, as same_product.py keeps its DROPPED list.
KEEP = {
    'B104-P001': 'the same ME+EM Leg Elongator Jean, Authentic Dark Wash, same REF: two views '
                 'of one page, 8.0 L* apart only by light (screenshots read, 25 Sept)',
    'B051-P002': 'the same lace skirt worn and flat: 8.4 L* apart only because '
                 'the model photo is lit warmer (contact sheet, 24 Sept)',
    'B077-P013': 'the same brown sleeveless knit twice; IMG_1219 is scrolled so the '
                 'top is cut off, and the outline overlaps 0.56 for that reason only '
                 '(contact sheet, 24 Sept evening — the first rule change that compares '
                 'untyped bare cuts would have split it)',
}    # skin share of a cut above which it is a picture of someone wearing it


# Rows whose pages say nothing and whose pictures the two tests cannot tell
# apart, split by the viewing pass (a person reading the contact sheet).
BY_EYE = {
    'B090-P010-V2': ([[0], [1, 2]], 'IMG_1364 is the Town and Country bag in dark brown; IMG_1365-1366 '
                                    'the same bag in tan. The pages agree on the name only; the tan '
                                    'leather reads as skin, so the cut is typed as worn and not compared '
                                    '(contact sheet, 24 Sept evening; the owner hid the row for it)'),
    'B076-P001': ([[0], [1, 2]], 'IMG_1190 is the belted cream jacket; IMG_1193-1194 a cream tank top, '
                                 'the second scrolled to its buy panel. 1194 has no cut to compare, so '
                                 'complete-link put it with the jacket (contact sheet, 24 Sept evening)'),
    'B092-P002': ([[0], [1]], 'IMG_1393 is the FRANKIE jacket in Olive laid flat; IMG_1394 is a model '
                              'in a black faux fur jacket. Flat against worn is not compared, and the '
                              'model photo has no text (contact sheet, 24 Sept)'),
    'B092-P008': ([[0], [1, 2], [3]], 'IMG_1401 is the BEAU hat; IMG_1402-1403 a belted long faux fur coat '
                                      'front and back; IMG_1404 an open long coat with a pale facing. '
                                      'No text on 1402-1404 and all within 5.4 L* (contact sheet, 24 Sept)'),
}


def silhouette(path, N=64):
    """The garment's outline: the largest opaque piece of the cut, cropped to
    its own box and scaled to N x N, so that two photographs of one garment at
    different sizes and positions, or with a shop's badge left beside it,
    compare as the same shape."""
    from PIL import Image
    from scipy import ndimage
    try:
        a = np.asarray(Image.open(path).convert('RGBA'))[..., 3] > 128
    except Exception:
        return None
    lab, n = ndimage.label(a)
    if not n:
        return None
    big = 1 + int(np.argmax(ndimage.sum(a, lab, range(1, n + 1))))
    m = lab == big
    ys, xs = np.nonzero(m)
    m = m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    if m.sum() < 400:
        return None
    im = Image.fromarray((m * 255).astype(np.uint8)).resize((N, N), Image.BILINEAR)
    return np.asarray(im) > 127


def picture(pid, i, review, panels, cache):
    """What screenshot i shows: its garment colour (Lab), kind, silhouette."""
    if SM.is_junk(pid, i, panels):
        return None
    path, cut = SM.picture_for(pid, i, review, panels)
    if not path or not os.path.exists(path):
        return None
    try:
        cols, skin, kept = SM.read_colours(path, cut)
    except Exception:
        return None
    if not cols:
        return None
    cache[(pid, i)] = (cols, skin, kept)
    # the kind is panels.py's reading of the photograph, the one the desk
    # labels its pictures with; a whole page nobody has typed has no kind
    typed = None
    sp = panels.get(f'{pid}#{i}') or {}
    for pn in sp.get('panels') or []:
        if CAT + '/' + (pn.get('cut') or '') == path or CAT + '/' + pn['path'] == path:
            typed = {'flat lay': 'flat', 'on-model': 'model'}.get(pn['type'])
    # an untyped page: someone is in it when the cut shows skin that is not
    # the garment's own colour (soft_cut.skin_share); the old share counted a
    # burgundy, rust or tan garment as skin
    own = own_skin(path, [c['lab'] for c in cols if c.get('share', 0) >= 0.1]) if cut else None
    s = skin if own is None else own
    kind = typed or ('model' if s > SKIN_MODEL else 'flat')
    return dict(lab=C.hex_to_lab(cols[0]['hex']), kind=kind, typed=typed, skin=round(s, 3),
                bare=(not typed and own is not None and own <= BARE),
                mask=silhouette(path) if cut else None, path=os.path.relpath(path, ROOT))


BARE = 0.01          # an untyped cut with less skin than this is plainly a packshot


def own_skin(path, colours=None):
    """Skin share of a cut-out, the garment's own colours left out."""
    from PIL import Image
    import soft_cut
    try:
        im = np.asarray(Image.open(path).convert('RGBA'))
    except Exception:
        return None
    return soft_cut.skin_share(im[..., :3], im[..., 3].astype(np.float32) / 255.0, colours)


def compatible(fa, fb, pa, pb, literal=False):
    """(same product?, why). Page text first; the pictures only where no text
    field is legible on both pages, and only between two pictures of one kind.
    `literal` drops that last condition, for the report."""
    d = T.disagree(fa, fb)
    if d:
        return False, 'page ' + '/'.join(d)
    both = T.legible_in_both(fa, fb)
    # A colour or a product number both pages print and agree on settles it.
    # The NAME alone does not (24 Sept): a style's name is the same on every
    # colourway's page, so "TOWN AND COUNTRY COLLECTION" kept a dark brown and
    # a tan Fairfax & Favor bag in one row. Where only the name agrees, the
    # pictures still decide the colour.
    if set(both) & {'colour', 'pid'}:
        return True, 'page agrees on ' + '/'.join(both)
    agreed = ('page agrees on name only; ' if both else '')
    if not pa or not pb:
        return True, agreed + 'no picture to compare'
    dl = abs(pa['lab'][0] - pb['lab'][0])
    if not literal and pa['kind'] != pb['kind']:
        # a flat lay against the same garment worn: the light on a person
        # moves L* by more than 8 and the outline never matches, so neither
        # test says anything about whether it is the same product
        return True, agreed + 'pictures not of one known kind (%s, %s), not compared' % (pa['kind'], pb['kind'])
    if dl > L_MAX:
        return False, agreed + 'lightness %.1f' % dl
    # the silhouette needs panels.py's typing on both, or — since 24 Sept — two
    # untyped cuts that are plainly flat: no skin once the garment's own colour
    # is left out (a burgundy cami read as "worn" because burgundy sits in the
    # skin band, and so was never compared with the burgundy trousers beside it)
    sure = (pa['typed'] and pb['typed']) or (pa.get('bare') and pb.get('bare'))
    if pa['mask'] is not None and pb['mask'] is not None and (literal or sure):
        iou = float((pa['mask'] & pb['mask']).sum() / max(1, (pa['mask'] | pb['mask']).sum()))
        if iou < IOU_MIN:
            return False, agreed + 'silhouette %.2f' % iou
        return True, agreed + 'pictures agree (dL %.1f, IoU %.2f)' % (dl, iou)
    return True, agreed + 'pictures agree (dL %.1f)' % dl


# the slot a product's own name gives it, in the languages the shops write in;
# first match wins, so "trench" is a layer before "cotton" is anything
SLOT_WORDS = [
    ('shoes', r'boot|stivale|loafer|mocassin|sneaker|shoe|scarpa|sandal|mule|pump|ballerina|slipper'),
    ('bag', r'bag|tasche|borsa|\bsac\b|tote|clutch|pouch|handle'),
    ('accessory', r'bandana|foulard|scarf|schal|sciarpa|echarpe|hat\b|cap\b|beanie|balaclava|belt|gloves?'),
    ('layer', r'coat|cappotto|giacca|giaccone|jacket|blazer|trench|caban|parka|soprabito|bomber|blouson|gilet|vest\b|mantel|manteau|veste'),
    ('bottom', r'pantalon|trouser|jeans|skirt|gonna|short|chino|culotte|hose|jupe'),
    ('dress', r'dress|abito|kleid|robe'),
    ('top', r'chemise|maglia|jumper|sweater|pullover|cardigan|polo|camicia|shirt|blouse|top\b|tee\b|t-shirt|turtleneck|crew|knit|longsleeve'),
]


def slot_from_name(name):
    n = (name or '').lower()
    for slot, rx in SLOT_WORDS:
        if re.search(rx, n):
            return slot
    return ''


def retype(p, name, own_name=True):
    """A split row's viewing fields from its own page. The parent's material
    and garment description are the parent's garment, so they go; the slot
    comes from the page's name where a word in it names one. `own_name` is
    False where the pages agree on the name (or only one shows it) and the
    row was split for its colour or number: it is the same style."""
    slot = slot_from_name(name)
    p[13] = 'NONE'                                   # composition: the parent's
    if name and own_name:
        p[2] = name.lower()
    if slot:
        p[1] = slot
        p[15] = p[15].split(';')[0] + '; slot guessed from the page\'s name "%s"' % name
    return p


def groups_for(n, ok):
    gs = []
    for i in range(n):
        for g in gs:
            if all(ok(i, j) for j in g):
                g.append(i)
                break
        else:
            gs.append([i])
    return gs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--only', nargs='*')
    a = ap.parse_args()
    batches = json.load(open(CAT + '/batches.json'))
    review = SM.load('_review_boxes.json', {})
    panels = SM.load('_panels.json', {})
    flats = SM.load('_flat_lays.json', {})
    assets = SM.load('_assets.json', {})
    colours = SM.load('_colours.json', {})
    rows = {r['product_id']: r for r in csv.DictReader(open(CAT + '/products.csv'))}
    # a row is a product page row: two or more screenshots, not a listing grid
    todo = [b for b in batches if len(b['images']) >= 2
            and rows.get(b['product_id'], {}).get('shot_type') != 'listing grid'
            and (not a.only or b['product_id'] in a.only)]
    text = T.ensure(sorted({p for b in todo for p in b['images']}))
    cache, plan, report = {}, {}, {}
    for b in todo:
        pid, ims = b['product_id'], b['images']
        pics = [picture(pid, i, review, panels, cache) for i in range(len(ims))]
        why = {}

        def ok(i, j):
            r, w = compatible(text[ims[i]], text[ims[j]], pics[i], pics[j])
            why[f'{i}-{j}'] = w
            return r
        gs = groups_for(len(ims), ok)
        lit = groups_for(len(ims), lambda i, j: compatible(text[ims[i]], text[ims[j]], pics[i], pics[j], True)[0])
        report[pid] = dict(groups=gs, pairs=why, literal=lit,
                           pages=[{k: text[p][k] for k in ('name', 'colour', 'pid', 'domain')} for p in ims])
        if pid in KEEP:
            report[pid]['kept'] = KEEP[pid]
            gs = [list(range(len(ims)))]
        if pid in BY_EYE and len(ims) == sum(len(g) for g in BY_EYE[pid][0]):
            gs = BY_EYE[pid][0]
            report[pid]['by_eye'] = BY_EYE[pid][1]
            report[pid]['groups'] = gs
        if len(gs) > 1:
            plan[pid] = gs
    n_new = sum(len(g) - 1 for g in plan.values())
    lit = {k: v['literal'] for k, v in report.items() if len(v['literal']) > len(v['groups'])}
    print(f'the thresholds applied across kinds too would split {len(lit)} more rows: '
          + ', '.join(f'{k} {v}' for k, v in lit.items()))
    print(f'{len(todo)} product-page rows with two or more screenshots; '
          f'{len(plan)} split, into {sum(len(g) for g in plan.values())} rows (+{n_new})')
    def save(run):
        """Every run is kept: a check never overwrites what a split did."""
        try:
            prev = json.load(open(OUT))
        except (FileNotFoundError, json.JSONDecodeError):
            prev = {}
        runs = prev.get('runs', [])
        if a.check:
            prev['last_check'] = run
        else:
            runs.append(run)
        prev.update(rule=dict(L_MAX=L_MAX, IOU_MIN=IOU_MIN, text=T.SIM), runs=runs)
        json.dump(prev, open(OUT, 'w'), indent=1)
    save(dict(rows=report, plan=plan))
    for pid, gs in plan.items():
        print(' ', pid, gs, '|', '; '.join(sorted({w for k, w in report[pid]['pairs'].items()
                                                   if not w.startswith(('page agrees', 'pictures agree', 'no picture', 'pictures not of'))})))
    if a.check or not plan:
        return

    taken = {b['product_id'] for b in batches} | set(rows)

    def new_id(pid, k):
        root = re.sub(r'-V\d+$', '', pid)
        n = 2
        while f'{root}-V{n}' in taken:
            n += 1
        taken.add(f'{root}-V{n}')
        return f'{root}-V{n}'
    before = {b['product_id']: list(b['images']) for b in batches}
    SM.apply(plan, batches, review, panels, flats, assets, colours, rows, cache,
             new_id=new_id, viewing_name='rows_namesplit.txt', why='by the name on its page')
    # the new rows carry what their own pages say, not the parent's name
    after = json.load(open(CAT + '/batches.json'))
    vf = CAT + '/_viewing_rows/rows_namesplit.txt'
    lines = [ln.rstrip('\n').split(' | ') for ln in open(vf) if ln.strip()]
    made = {b['product_id']: b['images'] for b in after if b['product_id'] not in before}
    src = {}                     # new row -> (parent row, its group, the kept group)
    for pid, gs in plan.items():
        for k, g in enumerate(gs[1:], 1):
            nid = next(n for n, v in made.items() if v == [before[pid][i] for i in g])
            src[nid] = (pid, g, gs[0])
    for p in lines:
        ims = made.get(p[0])
        if not ims:
            continue
        pid, g, g0 = src[p[0]]
        why = {w for i in g for j in g0
               for w in (report[pid]['pairs'].get(f'{max(i, j)}-{min(i, j)}') or '').replace('page ', '').split('/')}
        name = next((text[x]['name'] for x in ims if text.get(x, {}).get('name')), '')
        col = next((text[x]['colour'] for x in ims if text.get(x, {}).get('colour')), '')
        # a price is only taken off a page whose name was read beside it: a
        # banner's "CHF 10 sparen" or a stray "€7" is not this product's price
        price = next((text[x]['price'] for x in ims if text.get(x, {}).get('price')
                      and text[x].get('name')), '')
        own = 'name' in why
        if own or not p[11] or p[11] == 'NONE':
            p[11] = name or 'NONE'
        p[12] = col or 'NONE'
        p[14] = price or 'NONE'
        # another shop's page in the row: the parent's brand is not this one's
        dom = {text[x]['domain'] for x in ims if text[x].get('domain')}
        pdom = {text[x]['domain'] for x in (before[pid][i] for i in g0) if text[x].get('domain')}
        if dom and pdom and not dom & pdom:
            # another shop's page: nothing the parent's viewing row says is
            # about this garment, so the row starts from what its page says
            p[9], p[10] = dom.pop(), 'NONE'
            p[11] = name or 'NONE'
            p[1], p[2] = (slot_from_name(name), name.lower()) if name else ('', '')
            own = True
        retype(p, name if own else p[11], own)
    with open(vf, 'w') as f:
        f.write('\n'.join(' | '.join(p) for p in lines) + '\n')
    # decisions filed against a screenshot follow it
    moved = json.load(open(ROOT + '/studio/data/split-migration.json')).get('moved', {})
    prev = json.load(open(OUT))
    prev['runs'][-1].update(made=made, moved={k: v for k, v in moved.items() if k.split('#')[0] in plan})
    json.dump(prev, open(OUT, 'w'), indent=1)
    print(f'{len(made)} new rows')


if __name__ == '__main__':
    main()
