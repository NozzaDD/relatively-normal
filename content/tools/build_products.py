"""Fold the viewing rows + batch clustering + colour extraction into products.csv."""
import csv, json, glob, os, re, sys, collections, unicodedata
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CAT = ROOT + '/content/catalogue'
FIELDS = ['product_id', 'batch_id', 'shop', 'shop_type', 'slot', 'garment_type',
          'material_visible', 'pattern', 'weight', 'formality', 'shot_type',
          'complete_in_frame', 'n_images', 'image_paths',
          'brand', 'brand_confidence', 'brand_role',
          'product_name', 'product_name_confidence',
          'material', 'material_confidence',
          'price', 'price_confidence',
          'product_url', 'product_url_confidence',
          'colour1_hex', 'colour1_share', 'colour1_L', 'colour1_C', 'colour1_h',
          'colour1_rel_chroma', 'colour1_neutral', 'colour1_family', 'colour1_name',
          'colour2_hex', 'colour2_share', 'colour2_family', 'colour2_name',
          'colour3_hex', 'colour3_share', 'colour3_family', 'colour3_name',
          'colour_confidence', 'colour_stability',
          'asset_type', 'asset_path', 'asset_quality',
          'colour_name_text', 'notes', 'validated', 'used_in',
          # the desk's review decisions and the recoloured variants
          'shelf', 'asset_choice', 'asset_box', 'recoloured', 'recolour_source',
          # a piece the stylist cut out of another product's screenshot
          'parent_id', 'asset_image', 'asset_base',
          # where a brand that was not printed on the page came from
          'brand_evidence',
          # given = the stylist set it on the desk; inherited = from the product
          # this row was split out of; guessed = from a listing-grid caption
          'slot_confidence',
          # the shop's own product number, which names the style: UNIQLO prints
          # it under Description ("Product ID: 485303")
          'shop_product_id', 'shop_product_id_confidence',
          # why a row is back in Review (shelf = review): her "Back to Review",
          # or a build that found something wrong with its picture
          'review_reason']


def read_rows():
    rows = {}
    for f in sorted(glob.glob(CAT + '/_viewing_rows/rows_*.txt')):
        for ln in open(f):
            p = [x.strip() for x in ln.rstrip('\n').split('|')]
            # ...-V2 is a product split out of another by colour, and is a
            # product in its own right from here on
            if len(p) < 16 or not re.match(r'^B\d+-P\d+(-V\d+)?$', p[0]):
                continue
            rows[p[0]] = dict(zip(
                ['product_id', 'slot', 'garment_type', 'material_visible', 'pattern',
                 'weight', 'formality', 'shot_type', 'complete_in_frame', 'shop_text',
                 'brand_text', 'product_name_text', 'colour_name_text',
                 'composition_text', 'price_text', 'notes'], p[:16]))
    return rows


def none(v):
    return '' if (v or '').strip().upper() in ('NONE', '', '-') else v.strip()


def url_bars():
    """Safari's address bar, read per screenshot by url_bar.py."""
    try:
        return json.load(open(CAT + '/_url_bars.json'))
    except (FileNotFoundError, json.JSONDecodeError):
        return {'images': {}, 'batches': {}}


def shop_of(batch_rows):
    """One shop per batch: the most common legible shop string."""
    c = collections.Counter(none(r['shop_text']).lower() for r in batch_rows if none(r['shop_text']))
    return c.most_common(1)[0][0] if c else ''


def shop_for_product(images, bid, bars):
    """The shop, from this product's own address bars first.

    Per product, not per batch, because batches do span shops: the clustering
    reads layout, and two shops with the same layout run together. Sixteen
    batches disagree with themselves about the domain, so a batch majority
    would file the minority under the wrong shop. The batch is the fallback,
    the viewing pass the fallback after that.
    """
    c = collections.Counter(bars['images'].get(i, {}).get('domain', '') for i in images)
    c.pop('', None)
    if c:
        return c.most_common(1)[0][0], 'own'
    b = bars['batches'].get(bid, {}).get('domain', '')
    return (b, 'batch') if b else ('', '')


def shop_kind(batch_rows, shop):
    """mono-brand when every legible brand in the batch matches the shop."""
    brands = {none(r['brand_text']).lower() for r in batch_rows if none(r['brand_text'])}
    if not brands:
        return 'unknown'
    key = re.sub(r'[^a-z]', '', shop.split('.')[0])
    if len(brands) == 1 and key and key in re.sub(r'[^a-z]', '', list(brands)[0]):
        return 'mono-brand'
    if len(brands) == 1:
        return 'mono-brand'
    return 'multi-brand'


def brand_roles():
    """Role comes from brands/, never from my own judgement: a filed brand is a
    recommend unless its partnership_tier is `mill`, which is a cloth supplier
    and so inspiration only. Anything not filed is `not filed`."""
    out = {}
    for f in sorted(glob.glob(ROOT + '/brands/*.yaml')):
        txt = open(f).read()
        name = re.search(r'^name:\s*(.+)$', txt, re.M)
        tier = re.search(r'^partnership_tier:\s*(\S+)', txt, re.M)
        if not name:
            continue
        out[re.sub(r'[^a-z0-9]', '', name.group(1).lower())] = (
            'inspiration-only' if tier and tier.group(1) == 'mill' else 'recommend')
    return out


def norm(s):
    """A name squashed for comparison, accents folded: sezane.com is sézane."""
    t = unicodedata.normalize('NFKD', (s or '').lower())
    return re.sub(r'[^a-z0-9]', '', ''.join(c for c in t if not unicodedata.combining(c)))


REGION = re.compile(r'^(de|ch|uk|fr|it|us|eu|at|nl|be|es|se|dk|jp)\.')


def domain_label(domain):
    """The shop's own name inside a domain: de.maxmara.com -> maxmara."""
    return norm(REGION.sub('', (domain or '').lower()).split('.')[0])


def canonical_brands():
    """{squashed name: the name as the catalogue writes it}.

    Only names the repository already holds: the brands/ files, and every
    brand the viewing pass actually read off a page. A domain whose label is
    not one of them yields no brand at all — inventing a label out of a domain
    is exactly the invention CLAUDE.md forbids.
    """
    out = {}
    for f in sorted(glob.glob(ROOT + '/brands/*.yaml')):
        m = re.search(r'^name:\s*(.+)$', open(f).read(), re.M)
        if m:
            out[norm(m.group(1))] = m.group(1).strip().lower()
    for r in read_rows().values():
        b = none(r.get('brand_text', ''))
        if b:
            out.setdefault(norm(b), b.lower())
    return out


def load_json(path, default):
    try:
        return json.load(open(path))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def kept_columns():
    """Columns the owner or another script fills in. They survive a rebuild."""
    keep = {}
    try:
        for r in csv.DictReader(open(CAT + '/products.csv')):
            keep[r['product_id']] = {k: r.get(k, '') for k in ('validated', 'used_in')}
    except FileNotFoundError:
        pass
    return keep


def apply_pages(by_id):
    """What uniqlo_pages.py read off each UNIQLO screenshot's buy panel.

    The name, the selected colour ("03 GREY") and the price are legible on the
    page, so they are `given` and replace what the viewing pass typed. The row
    is read from its first screenshot; where its screenshots show different
    products — the clustering put two pages in one row — the note says so.

    The product ID sits under Description, so only some screenshots reach it.
    On a row's own screenshot it is `given`. A row whose screenshots stop above
    it takes the ID from another screenshot of the same name at `guessed`,
    with the screenshot that shows it as evidence: the ID is what identifies
    the style, and a matching name is the inference.
    """
    pages = load_json(CAT + '/_uniqlo_pages.json', {})
    if not pages:
        return 0
    ids, id_from = {}, {}
    for p, rec in pages.items():
        if rec.get('product_id') and rec.get('name'):
            ids[rec['name']] = rec['product_id']
            id_from[rec['name']] = os.path.basename(p)
    n = 0
    for d in by_id.values():
        imgs = [x for x in (d.get('image_paths') or '').split(';') if x in pages]
        if not imgs:
            continue
        recs = [pages[x] for x in imgs]
        rec = recs[0]
        if not rec.get('name'):
            continue
        n += 1
        d['product_name'], d['product_name_confidence'] = rec['name'], 'given'
        if rec.get('price'):
            d['price'], d['price_confidence'] = rec['price'], 'given'
        if rec.get('colour_no'):
            d['colour_name_text'] = f"{rec['colour_no']} {rec['colour']}"
        own = next((r['product_id'] for r in recs if r.get('product_id')), '')
        if own:
            d['shop_product_id'], d['shop_product_id_confidence'] = own, 'given'
        elif rec['name'] in ids:
            d['shop_product_id'], d['shop_product_id_confidence'] = ids[rec['name']], 'guessed'
            d['notes'] = (d['notes'] + f"; product ID read on {id_from[rec['name']]}, "
                          "a screenshot of the same name").strip('; ')
        else:
            d['shop_product_id_confidence'] = 'input needed'
        names = sorted({r['name'] for r in recs if r.get('name')})
        if len(names) > 1:
            d['notes'] = (d['notes'] + '; its screenshots show different products: '
                          + ' / '.join(names) + ' — name and price are from the first').strip('; ')
    return n


def measured_sources(by_id):
    """A UNIQLO style's source row takes the cut its variants were made from.

    uniqlo_variants.py cuts each style's flat lay again from the one photo
    panel it sits in and measures it the way flat_lays.py does: one piece,
    clear of the frame, no text inside. Where the row's own catalogue cut-out
    did not pass — the page read as "skin in the frame" because the jumper is
    brown, or the backdrop was not plain because the panel above rode along —
    and the new cut does, the row's picture becomes the new cut and its
    colours are read again from it. build_studio.py then gives the row the
    measured verdict, and its variants inherit it as they always have.
    A row that already passed keeps the cut-out it has."""
    from PIL import Image
    import extract_colours as X
    from colour_names import classify
    flats = load_json(CAT + '/_flat_lays.json', {})
    v = load_json(CAT + '/_variants.json', {})
    n = 0
    for style, rep in v.get('report', {}).items():
        d = by_id.get(rep['source'])
        if not d or not rep.get('source_clean') or not rep.get('source_cut'):
            continue
        if (flats.get(rep['source']) or {}).get('clean'):
            continue
        # a row that holds two styles' screenshots (B062-P014: a jacket and
        # leggings) takes the cut of the style whose screenshot comes first
        imgs = (d.get('image_paths') or '').split(';')
        mine = [r['source_image'] for r in v['report'].values() if r['source'] == rep['source']]
        if rep['source_image'] not in imgs or \
                min(mine, key=lambda p: imgs.index(p) if p in imgs else 99) != rep['source_image']:
            continue
        d.update(asset_path=rep['source_cut'], asset_type='cutout_flat', asset_quality='good')
        with Image.open(ROOT + '/' + rep['source_cut']) as im:
            cols, skin, kept = X.colours_for_image(im.convert('RGBA'), is_cutout=True)
        for i in (1, 2, 3):
            for k in ('hex', 'share', 'family', 'name'):
                d[f'colour{i}_{k}'] = ''
        for i, c in enumerate(cols[:3], 1):
            fam, nm, L, Cc, h, rel, nt = classify(c['hex'])
            d[f'colour{i}_hex'] = c['hex']; d[f'colour{i}_share'] = round(c['share'], 3)
            d[f'colour{i}_family'] = fam; d[f'colour{i}_name'] = nm
            if i == 1:
                d.update(colour1_L=round(L, 1), colour1_C=round(Cc, 1), colour1_h=round(h, 1),
                         colour1_rel_chroma=round(rel, 3), colour1_neutral=nt)
        d['colour_confidence'] = X.confidence('cutout_flat', cols, skin, kept)
        d['notes'] = (d['notes'] + f"; picture re-cut from the flat-lay panel of "
                      f"{os.path.basename(rep['source_image'])} and measured clean "
                      "(one piece, clear of the frame, no text)").strip('; ')
        n += 1
    return n


def source_colour_names(by_id):
    """UNIQLO's page names the selected colour, and the gallery photo is often
    another one: IMG_0755 says 55 GREEN above a brown jumper. On a style's
    source row the name is kept only when the swatch nearest the pictured
    garment is the selected one; otherwise it is cleared, and the variant made
    for the selected swatch is the row that carries it."""
    pages = load_json(CAT + '/_uniqlo_pages.json', {})
    v = load_json(CAT + '/_variants.json', {})
    n = 0
    for rep in v.get('report', {}).values():
        d = by_id.get(rep['source'])
        page = pages.get(rep['source_image'])
        if not d or not page or not rep.get('own_swatch'):
            continue
        if d.get('image_paths', '').split(';')[0] != rep['source_image'] and \
                rep['source_image'] not in d.get('image_paths', ''):
            continue
        own = page['swatches'][rep['own_swatch'] - 1]
        if not own['selected'] and d.get('colour_name_text'):
            d['notes'] = (d['notes'] + f"; the page names {d['colour_name_text']}, the selected colour, "
                          "but the photo shows another — the name is on that colour's variant").strip('; ')
            d['colour_name_text'] = ''
            n += 1
    return n


def model_colour_rows(by_id):
    """A row made of a flat lay and a model photo of the same product in the
    same colour (same_product.py) shows the flat lay recoloured to the colour
    measured on the model, where the owner approved that for the pair's dE.
    The model photo carries the true colour; the picture is ours, so the row
    is marked simulated with both screenshots as its recolour source."""
    from PIL import Image
    import extract_colours as X
    from colour_names import classify
    n = 0
    for r in load_json(CAT + '/_same_product.json', []):
        rc = r.get('recolour') or {}
        d = by_id.get(rc.get('source'))
        if not d or not rc.get('applied') or not os.path.exists(ROOT + '/' + rc['asset_path']):
            continue
        d.update(asset_path=rc['asset_path'], asset_type='cutout_flat', recoloured='yes',
                 recolour_source=rc['recolour_source'])
        with Image.open(ROOT + '/' + rc['asset_path']) as im:
            cols, skin, kept = X.colours_for_image(im.convert('RGBA'), is_cutout=True)
        for i in (1, 2, 3):
            for k in ('hex', 'share', 'family', 'name'):
                d[f'colour{i}_{k}'] = ''
        for i, c in enumerate(cols[:3], 1):
            fam, nm, L, Cc, h, rel, nt = classify(c['hex'])
            d[f'colour{i}_hex'] = c['hex']; d[f'colour{i}_share'] = round(c['share'], 3)
            d[f'colour{i}_family'] = fam; d[f'colour{i}_name'] = nm
            if i == 1:
                d.update(colour1_L=round(L, 1), colour1_C=round(Cc, 1), colour1_h=round(h, 1),
                         colour1_rel_chroma=round(rel, 3), colour1_neutral=nt)
        d['notes'] = (d['notes'] + f"; flat lay recoloured to the colour on the model photo "
                      f"(dE {r['flat_model_de']} between them); colour simulated").strip('; ')
        n += 1
    return n


def variant_rows(base_by_id):
    """UNIQLO colour variants from uniqlo_variants.py, as full product rows.

    One row per swatch circle on the style's page. Most are the style's flat
    lay recoloured to the swatch — recoloured = yes, colour simulated. A few
    are a real photograph of that colour, cut from the all-colours picture
    where the garment lay alone; those are the brand's own photo and are not
    marked simulated."""
    v = load_json(CAT + '/_variants.json', {})
    # every other shop's, from colourway_variants.py: the same row shape, but
    # a real photo there is the colour's own thumbnail on the page, and the
    # owner's screenshots of the style stay on the shelf — a swatch they cover
    # was never made again
    cw = load_json(CAT + '/_colourway_variants.json', {})
    out, hide = [], {}
    for x in v.get('variants', []) + cw.get('variants', []):
        src = base_by_id.get(x['source'])
        if not src:
            continue
        d = dict(src)
        c = x['colour']
        real = x.get('real')
        thumb = x['product_id'].rsplit('-', 1)[-1].startswith('cw')
        note = (f"cut from the colour thumbnail {x['swatch']} on {os.path.basename(x['real_from'])}, "
                f"the brand's own photo of this colour; style {x['style']}"
                if real and thumb else
                f"cut from the all-colours photo {os.path.basename(x['real_from'])}, the brand's own "
                f"photo of this colour; swatch {x['swatch']} of the style {x['style']}"
                if real else
                f"recoloured from {x['source']} to swatch {x['swatch']} of the style {x['style']} in CIELAB; "
                "colour simulated, not the brand's photo")
        d.update(product_id=x['product_id'], n_images=0,
                 product_name=x['style'], product_name_confidence=x.get('product_name_confidence', 'given'),
                 price=x.get('price') or src['price'],
                 price_confidence='given' if x.get('price') else src['price_confidence'],
                 slot=x['slot'], garment_type=x['garment_type'],
                 slot_confidence=x.get('slot_confidence') or src.get('slot_confidence', ''),
                 image_paths=x['real_from'] if real else '',
                 colour1_hex=c['hex'], colour1_share=c['share'], colour1_L=c['L'],
                 colour1_C=c['C'], colour1_h=c['h'], colour1_rel_chroma=c['rel'],
                 colour1_neutral=c['neutral'], colour1_family=c['family'], colour1_name=c['name'],
                 colour2_hex='', colour2_share='', colour2_family='', colour2_name='',
                 colour3_hex='', colour3_share='', colour3_family='', colour3_name='',
                 colour_confidence='high' if not real else 'medium', colour_stability='stable',
                 asset_type='cutout_flat', asset_path=x['asset_path'], asset_quality='good',
                 # only the selected colour's name is printed on the page
                 colour_name_text=x.get('colour_name_text', ''),
                 notes=note, validated='', used_in='', shelf='', asset_choice='', asset_box='',
                 recoloured='' if real else 'yes', recolour_source=x['source'],
                 parent_id='', asset_image='', asset_base='')
        out.append(d)
    # the other screenshots of a style that has variants leave the shelf: every
    # colour now has a row of its own. A row is hidden only when all of its
    # screenshots belong to that one style, so a row the clustering filled from
    # two pages stays where it is.
    sources = {x['source'] for x in v.get('variants', [])}
    for style, rep in v.get('report', {}).items():
        imgs = set(rep.get('images', []))
        for pid, r in base_by_id.items():
            mine = [x for x in (r.get('image_paths') or '').split(';') if x]
            if pid not in sources and mine and set(mine) <= imgs:
                hide[pid] = f"replaced by the colour variants of {rep['source']}"
    return out, hide


SHOP_SCOPED_GUESS_FROM = 75


# What a filed row keeps across a rebuild: its colours were read once, off a
# picture that has not changed, and a later change to the vocabulary or the
# reader is a decision to re-read, not a side effect of adding a product.
# To re-read on purpose, delete the rows (or products.csv) first.
# The READING is frozen (hexes, shares, lightness); the names are not: a
# family and a name are a function of the hex and the vocabulary, and are
# given again from the hex on every build (name_from_hex), as the owner asked
# on 24 Sept when the vocabulary of that morning was applied.
FROZEN = ['colour1_hex', 'colour1_share', 'colour1_L', 'colour1_C', 'colour1_h',
          'colour1_rel_chroma', 'colour1_neutral',
          'colour2_hex', 'colour2_share',
          'colour3_hex', 'colour3_share',
          'colour_confidence', 'colour_stability', 'notes', 'validated',
          # a brand guess leans on the other rows of the batch, so a row added
          # to the batch (a split, a new screenshot) must not re-guess it
          'brand', 'brand_confidence', 'brand_evidence']


def filed_rows():
    try:
        return {r['product_id']: r for r in csv.DictReader(open(CAT + '/products.csv'))}
    except FileNotFoundError:
        return {}


def unchanged(old, d):
    """The same row on the same pictures: same screenshots, same cut-out."""
    return bool(old) and all((old.get(k) or '') == (d.get(k) or '')
                             for k in ('image_paths', 'asset_path', 'recolour_source'))


def keep_filed(out, filed):
    n = 0
    for d in out:
        o = filed.get(d['product_id'])
        if unchanged(o, d):
            for k in FROZEN:
                d[k] = o.get(k, '')
            n += 1
    return n


def name_from_hex(out):
    """Every colour's family and plain name from its hex, in the vocabulary
    colour_names.py holds now. Nothing else about a colour changes."""
    from colour_names import classify
    n = 0
    for d in out:
        for i in (1, 2, 3):
            hx = (d.get(f'colour{i}_hex') or '').strip().lstrip('#')
            if not hx:
                continue
            fam, nm = classify(hx)[:2]
            if (d.get(f'colour{i}_family'), d.get(f'colour{i}_name')) != (fam, nm):
                d[f'colour{i}_family'], d[f'colour{i}_name'] = fam, nm
                n += 1
    return n


def grid_rows(by_id, review, filed=None):
    """One row per cell of a listing grid.

    A listing grid is a screenshot of a dozen products; each cell is one of
    them. The cell's own photograph, its own cut-out and its own colours make
    the row; the caption gives the name, the section and the price, each with
    its own confidence. The brand is the grid's shop and is only ever
    `guessed` — the caption names the product, not the label.

    These go to Review, never straight to the shelf: a cell read off a page is
    a suggestion, and the person decides.
    """
    from PIL import Image
    import extract_colours as X
    from colour_names import classify as colour_classify
    cells = load_json(CAT + '/_grid_cells.json', {})
    out = []
    for key, rec in sorted(cells.items()):
        pid, idx = key.split('#')[0], int(key.split('#')[1])
        parent = by_id.get(pid)
        if not parent:
            continue
        for j, c in enumerate(rec.get('cells') or []):
            d = dict(parent)
            # every screenshot of a grid row numbers its own cells, so two
            # cells never share an ID (the first screenshot keeps the plain
            # -C{j} form the desk's cell test knows)
            rid = f'{pid}-C{j}' if idx == 0 else f'{pid}-I{idx}-C{j}'
            asset = c.get('cut') or c.get('path')
            cap_slot = c.get('slot') or ''
            brand = parent.get('brand', '')
            eye = c.get('source') == 'eye'
            # a multi-brand retailer's grid names several brands across its
            # tiles; the page's list says nothing about which tile is whose
            multi = parent.get('shop_type') == 'multi-brand' or ';' in brand
            if multi:
                brand = ''
            d.update(product_id=rid, parent_id=pid, n_images=1,
                     image_paths=(parent['image_paths'].split(';') + [''] * 9)[idx],
                     slot=cap_slot, slot_confidence='guessed' if cap_slot else '',
                     garment_type=c.get('garment') or c.get('name', '') or parent.get('garment_type', ''),
                     shot_type='cell of a listing grid', complete_in_frame='yes' if eye else '',
                     asset_type='cutout_flat' if c.get('cut') else 'tile',
                     asset_quality='good', asset_path='content/catalogue/' + asset,
                     asset_image=idx, asset_base='photo', asset_choice='', asset_box='',
                     shelf='', recoloured='', recolour_source='',
                     # the brand is the grid's shop, at the confidence the grid
                     # row itself has: a mono-brand shop's own domain is the
                     # same evidence for every tile on the page
                     brand=brand,
                     brand_confidence=(parent.get('brand_confidence') or 'guessed') if brand else 'input needed',
                     brand_evidence=(parent.get('brand_evidence') or 'listing grid page') if brand else '',
                     product_name=c.get('name', ''),
                     product_name_confidence='given' if c.get('name') else 'input needed',
                     price=(c.get('currency', '') + ' ' + c.get('price', '')).strip(),
                     price_confidence='given' if c.get('price') else 'input needed',
                     material='', material_confidence='input needed',
                     product_url='', product_url_confidence='input needed',
                     colour_name_text=c.get('colour_name', ''),
                     notes='cell %d of the listing grid %s%s%s%s%s' % (
                         j + 1, pid,
                         '; read by eye' if eye else '',
                         '; multi-brand page, the brand is not read per tile' if multi else '',
                         '; section "%s"' % c['category'] if c.get('category') else '',
                         '; label "%s"' % c['label'] if c.get('label') else ''),
                     validated='', used_in='')
            if unchanged((filed or {}).get(rid), d):
                out.append(d)              # keep_filed puts its colours back
                continue
            for i in (1, 2, 3):
                for k in ('hex', 'share', 'family', 'name'):
                    d[f'colour{i}_{k}'] = ''
            for k in ('colour1_L', 'colour1_C', 'colour1_h', 'colour1_rel_chroma', 'colour1_neutral'):
                d[k] = ''
            try:
                with Image.open(CAT + '/' + asset) as im:
                    crop = im.convert('RGBA' if c.get('cut') else 'RGB')
                cols, skin, kept = X.colours_for_image(crop, is_cutout=bool(c.get('cut')))
                for i, col in enumerate(cols[:3], 1):
                    fam, nm, L, Cc, h, rel, nt = colour_classify(col['hex'])
                    d[f'colour{i}_hex'] = col['hex']; d[f'colour{i}_share'] = round(col['share'], 3)
                    d[f'colour{i}_family'] = fam; d[f'colour{i}_name'] = nm
                    if i == 1:
                        d.update(colour1_L=round(L, 1), colour1_C=round(Cc, 1), colour1_h=round(h, 1),
                                 colour1_rel_chroma=round(rel, 3), colour1_neutral=nt)
                d['colour_confidence'] = X.confidence('tile', cols, skin, kept)
                d['colour_stability'] = 'stable'
            except Exception as e:
                d['colour_confidence'] = 'low'
                d['notes'] += '; colour read failed: %s' % type(e).__name__
            out.append(d)
    return out


def flag_twins(cells, existing):
    """Mark a cell that looks like a product already in the catalogue.

    Brand, slot and first colour name the same. Nothing is merged and nothing
    is dropped: the row says which product it resembles and the person decides.
    """
    seen = collections.defaultdict(list)
    for r in existing:
        if r.get('parent_id'):
            continue
        seen[(norm(r.get('brand')), r.get('slot'), r.get('colour1_name'))].append(r['product_id'])
    n = 0
    for c in cells:
        k = (norm(c.get('brand')), c.get('slot'), c.get('colour1_name'))
        if not k[0] or not k[1] or not k[2]:
            continue
        twins = seen.get(k)
        if twins:
            c['notes'] += '; looks like ' + ', '.join(twins[:3])
            c['validated'] = 'possible duplicate'
            n += 1
    return n


def apply_choice(d, ch):
    """One asset-choices.json entry onto a products.csv row: the picture she
    chose, removed (shelf = hidden), or back in Review (shelf = review, with
    the reason). A row sent back to Review keeps no picture choice."""
    if not ch:
        return
    if ch.get('review'):
        d['shelf'] = 'review'
        d['review_reason'] = ch['review'] if isinstance(ch['review'], str) else 'sent back to Review'
        d['asset_choice'] = ''
        d['asset_box'] = ''
        return
    d['asset_choice'] = ch.get('choice', '')
    d['asset_box'] = ','.join(str(v) for v in ch['box']) if ch.get('box') else ''
    if ch.get('choice') in ('custom', 'item', 'person', 'full', 'whole'):
        d['asset_image'] = ch.get('image', 0)
        d['asset_base'] = ch.get('base', 'photo')
    if ch.get('hidden'):
        d['shelf'] = 'hidden'


def split_rows(choices, by_id, review, filed=None):
    """Rows for the boxes the stylist drew on other products' screenshots.

    Batch, shop and brand come from the parent, confidence inherited and never
    upgraded. Slot and colour name are hers. The colours are read from the box
    region by the same pipeline that reads every other product."""
    from PIL import Image
    import extract_colours as X
    from colour_names import classify
    out = []
    for pid, ch in choices.items():
        parent = by_id.get(pid)
        if not parent:
            continue
        for sp in ch.get('splits', []):
            if not sp.get('box') or 'n' not in sp:
                continue
            imgs = review.get(pid, {}).get('images') or []
            idx = int(sp.get('image', 0) or 0)
            entry = imgs[idx] if idx < len(imgs) and imgs[idx] else None
            if not entry or 'error' in entry:
                continue
            base = sp.get('base', 'photo')
            src_entry = entry.get('whole') if base == 'whole' and entry.get('whole') else entry
            # a box drawn on the CUT-OUT is a box on the parent's asset, not on
            # the photo: cropping the photo with it took the page's size row and
            # "Guida alle Taglie" instead of the swatch she boxed (B011-P002-S1..S3)
            src_file = (ROOT + '/' + parent['asset_path'] if base == 'asset' and parent.get('asset_path')
                        else CAT + '/' + src_entry['path'])
            box = [float(v) for v in sp['box']]
            d = dict(parent)
            rid = f"{pid}-S{sp['n']}"
            d.update(product_id=rid, parent_id=pid, n_images=1,
                     image_paths=(parent['image_paths'].split(';') + [''] * 9)[idx],
                     slot=sp.get('slot') or parent['slot'],
                     colour_name_text=sp.get('colour_name', ''),
                     product_name='', product_name_confidence='input needed',
                     material='', material_confidence='input needed',
                     price='', price_confidence='input needed',
                     product_url='', product_url_confidence='input needed',
                     shot_type='crop of ' + parent['shot_type'], complete_in_frame='',
                     asset_type='crop', asset_quality='good',
                     asset_path=os.path.relpath(src_file, ROOT), asset_image=idx,
                     asset_base=base,
                     asset_choice='custom', asset_box=','.join(f'{v:.4f}' for v in box),
                     shelf='', recoloured='', recolour_source='',
                     notes=f'cut by hand from {pid} image {idx}', validated='', used_in='')
            if unchanged((filed or {}).get(rid), d):
                out.append(d)              # keep_filed puts its colours back
                continue
            for i in (1, 2, 3):
                for k in ('hex', 'share', 'family', 'name'):
                    d[f'colour{i}_{k}'] = ''
            for k in ('colour1_L', 'colour1_C', 'colour1_h', 'colour1_rel_chroma', 'colour1_neutral'):
                d[k] = ''
            try:
                with Image.open(src_file) as im:
                    W, H = im.size
                    mode = 'RGBA' if base in ('whole', 'asset') else 'RGB'
                    crop = im.convert(mode).crop((int(box[0] * W), int(box[1] * H),
                                                  int((box[0] + box[2]) * W), int((box[1] + box[3]) * H)))
                cols, skin, kept = X.colours_for_image(crop, is_cutout=(base in ('whole', 'asset')))
                for i, c in enumerate(cols[:3], 1):
                    fam, nm, L, Cc, h, rel, nt = classify(c['hex'])
                    d[f'colour{i}_hex'] = c['hex']; d[f'colour{i}_share'] = round(c['share'], 3)
                    d[f'colour{i}_family'] = fam; d[f'colour{i}_name'] = nm
                    if i == 1:
                        d.update(colour1_L=round(L, 1), colour1_C=round(Cc, 1), colour1_h=round(h, 1),
                                 colour1_rel_chroma=round(rel, 3), colour1_neutral=nt)
                d['colour_confidence'] = X.confidence('tile', cols, skin, kept)
                d['colour_stability'] = 'stable'
            except Exception as e:
                d['colour_confidence'] = 'low'
                d['notes'] += f'; colour read failed: {type(e).__name__}'
            out.append(d)
    return out


def main():
    # the share sheet's copies (asset-choices-2.json …) and stubs (text.txt)
    # first: merged and deleted, or — if one is broken — nothing built at all
    import tidy_exports
    try:
        tidy_exports.tidy()
    except tidy_exports.BrokenExport as e:
        print(f'::error::Export not applied, nothing changed — {e}')
        sys.exit(1)
    filed = filed_rows()
    rows = read_rows()
    keep = kept_columns()
    review = load_json(CAT + '/_review_boxes.json', {})
    choices = load_json(CAT + '/asset-choices.json', {}).get('choices', {})
    bat = json.load(open(CAT + '/batches.json'))
    assets = json.load(open(CAT + '/_assets.json'))
    cols = json.load(open(CAT + '/_colours.json'))
    roles = brand_roles()
    by_batch = collections.defaultdict(list)
    for b in bat:
        if b['product_id'] in rows:
            by_batch[b['batch_id']].append(rows[b['product_id']])
    bars = url_bars()
    brand_names = canonical_brands()
    shops = {bid: shop_of(rs) for bid, rs in by_batch.items()}
    kinds = {bid: shop_kind(rs, shops[bid]) for bid, rs in by_batch.items()}

    # each product's own shop, so a brand guess never crosses from one shop's
    # pages to another's inside one batch: B080 holds Jamie Haller, ATP Atelier
    # and Marge Sherwood screenshots, and ATP's grids were guessed Jamie Haller
    own_domain = {b['product_id']: shop_for_product(b['images'], b['batch_id'], bars)[0] for b in bat}
    out = []
    for b in bat:
        pid = b['product_id']
        r = rows.get(pid, {})
        a = assets.get(pid, {})
        c = cols.get(pid, {})
        cl = c.get('colours', [])
        domain, where = shop_for_product(b['images'], b['batch_id'], bars)
        shop = domain or shops.get(b['batch_id'], '')
        kind = kinds.get(b['batch_id'], 'unknown')
        label = brand_names.get(domain_label(domain)) if domain else None
        if label:
            # the domain is a brand the repository already holds, so the shop
            # is that brand's own: this is what tells a label's site apart from
            # a retailer's, and it works where no brand is printed on the page
            kind = 'mono-brand'
        elif domain:
            kind = shop_kind(by_batch[b['batch_id']], domain)

        brand = none(r.get('brand_text', ''))
        bconf = 'given' if brand else ''
        eviden = ''
        if not brand and kind == 'mono-brand':
            # the only guess allowed: another image in this batch named the shop
            # and every legible brand in it was that shop's own
            # (from batch 75 on: applied earlier it would re-guess filed rows,
            # B050's Ulla Johnson pages among them — the owner decides those)
            scoped = int(b['batch_id'][1:]) >= SHOP_SCOPED_GUESS_FROM
            cands = {none(x['brand_text']) for x in by_batch[b['batch_id']] if none(x['brand_text'])
                     and (not scoped or not domain or own_domain.get(x['product_id']) in (domain, ''))}
            if len(cands) == 1:
                brand, bconf = cands.pop(), 'guessed'
        if not brand and label:
            # a mono-brand shop's own domain names its own label. A domain is
            # strong evidence but it is still not the page saying the brand, so
            # it is never `given` — CLAUDE.md hard rule 2. A retailer's domain
            # matches no filed brand and so sets the shop and nothing else.
            brand, bconf = label, 'guessed'
            eviden = 'URL bar, %s' % domain
        if not brand:
            bconf = 'input needed'
        name = none(r.get('product_name_text', ''))
        comp = none(r.get('composition_text', ''))
        price = none(r.get('price_text', ''))

        d = dict.fromkeys(FIELDS, '')
        d.update(
            product_id=pid, batch_id=b['batch_id'], shop=shop, shop_type=kind,
            slot=r.get('slot', ''), garment_type=r.get('garment_type', ''),
            material_visible=r.get('material_visible', ''), pattern=r.get('pattern', ''),
            weight=r.get('weight', ''), formality=r.get('formality', ''),
            shot_type=r.get('shot_type', ''), complete_in_frame=r.get('complete_in_frame', ''),
            n_images=len(b['images']), image_paths=';'.join(b['images']),
            brand=brand, brand_confidence=bconf, brand_evidence=eviden,
            brand_role=roles.get(norm(brand), 'not filed') if brand else 'not filed',
            product_name=name, product_name_confidence='given' if name else 'input needed',
            material=comp, material_confidence='given' if comp else 'input needed',
            price=price, price_confidence='given' if price else 'input needed',
            product_url='', product_url_confidence='input needed',
            colour_confidence=c.get('colour_confidence', ''),
            colour_stability=c.get('colour_stability', ''),
            asset_type=a.get('asset_type', ''), asset_path=a.get('asset_path', ''),
            asset_quality=a.get('asset_quality', ''),
            colour_name_text=none(r.get('colour_name_text', '')),
            notes=r.get('notes', ''),
            validated=keep.get(pid, {}).get('validated', ''),
            used_in=keep.get(pid, {}).get('used_in', ''),
            shelf='', asset_choice='', asset_box='', recoloured='', recolour_source='',
            parent_id='', asset_image='', asset_base='')
        ch = choices.get(pid)
        if ch and ch.get('slot'):
            # the stylist looked at the garment; nothing inferred beats that
            d['slot'] = ch['slot']
            d['slot_confidence'] = 'given'
        elif 'slot guessed from the page' in (d.get('notes') or ''):
            d['slot_confidence'] = 'guessed'
        elif 'slot and garment type are the parent' in (d.get('notes') or ''):
            d['slot_confidence'] = 'inherited'
        apply_choice(d, ch)
        for i, col in enumerate(cl[:3], 1):
            d[f'colour{i}_hex'] = col['hex']
            d[f'colour{i}_share'] = col['share']
            d[f'colour{i}_family'] = col['family']
            d[f'colour{i}_name'] = col['name']
            if i == 1:
                d.update(colour1_L=col['L'], colour1_C=col['C'], colour1_h=col['h'],
                         colour1_rel_chroma=col['rel'], colour1_neutral=col['neutral'])
        out.append(d)

    by_id = {d['product_id']: d for d in out}
    applied = set(by_id)                 # the screenshot rows had their choices above
    read = apply_pages(by_id)
    print('UNIQLO rows read off the page:', read)
    print('UNIQLO source rows switched to their measured cut:', measured_sources(by_id))
    print('UNIQLO source rows whose photo is not the selected colour:', source_colour_names(by_id))
    print('flat lays recoloured to their model photo:', model_colour_rows(by_id))
    variants, hide = variant_rows(by_id)
    for pid, why in hide.items():
        by_id[pid]['shelf'] = 'hidden'
        by_id[pid]['notes'] = (by_id[pid]['notes'] + '; ' + why).strip('; ')
    for v in variants:
        v['used_in'] = keep.get(v['product_id'], {}).get('used_in', '')
        v['validated'] = keep.get(v['product_id'], {}).get('validated', '')
    out.extend(variants)
    splits = split_rows(choices, by_id, review, filed)
    for d in splits:
        d['used_in'] = keep.get(d['product_id'], {}).get('used_in', '')
        d['validated'] = keep.get(d['product_id'], {}).get('validated', '')
    out.extend(splits)
    cells = grid_rows(by_id, review, filed)
    twins = flag_twins(cells, out)
    for d in cells:
        d['used_in'] = keep.get(d['product_id'], {}).get('used_in', '')
        if keep.get(d['product_id'], {}).get('validated'):
            d['validated'] = keep[d['product_id']]['validated']
    # the grid itself leaves the shelf once its cells exist: it is a page, not
    # a product, and every garment on it now has a row of its own
    parents = {d['parent_id'] for d in cells}
    for pid in parents:
        if pid in by_id:
            by_id[pid]['shelf'] = 'hidden'
            by_id[pid]['notes'] = (by_id[pid]['notes'] + '; cut into %d cells'
                                   % sum(1 for d in cells if d['parent_id'] == pid)).strip('; ')
    out.extend(cells)
    # the desk's decisions reach every row, not only the screenshot rows: a
    # colourway variant, a grid cell or a cut piece is removed, sent back to
    # Review or given a picture the same way (47 variant decisions of 24 Sept
    # were being dropped here)
    late = 0
    for d in out:
        ch = choices.get(d['product_id'])
        if ch and d['product_id'] not in applied:
            if ch.get('slot'):
                d['slot'] = ch['slot']
                d['slot_confidence'] = 'given'
            apply_choice(d, ch)
            late += 1
    print('choices applied to variant, cell and split rows:', late)

    # a brand guessed from a domain ("flattered") is spelt the way a page of
    # the same shop printed it ("Flattered"), so the desk lists it once
    spelt = {}
    for d in out:
        if d.get('brand_confidence') == 'given' and d.get('brand'):
            spelt.setdefault(norm(d['brand']), d['brand'])
    for d in out:
        if d.get('brand_confidence') == 'guessed' and norm(d.get('brand')) in spelt:
            d['brand'] = spelt[norm(d['brand'])]
    print('filed rows kept as filed:', keep_filed(out, filed))
    print('colours renamed from their hex:', name_from_hex(out))
    os.makedirs(CAT, exist_ok=True)
    with open(CAT + '/products.csv', 'w', newline='') as f:
        w = csv.DictWriter(f, FIELDS)
        w.writeheader()
        w.writerows(out)
    print(len(out), 'products ->', CAT + '/products.csv')
    print('grid cells:', len(cells), 'from', len(parents), 'grids;',
          twins, 'flagged as possible duplicates')
    print('variants merged:', len(variants), ' splits:', len(splits),
          ' hidden:', sum(1 for d in out if d['shelf'] == 'hidden'),
          ' choices applied:', sum(1 for d in out if d['asset_choice']))
    for k in ('brand_confidence', 'colour_confidence', 'asset_type', 'shop_type', 'slot'):
        print(k, collections.Counter(d[k] for d in out).most_common())


if __name__ == '__main__':
    main()
