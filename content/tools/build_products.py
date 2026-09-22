"""Fold the viewing rows + batch clustering + colour extraction into products.csv."""
import csv, json, glob, os, re, sys, collections
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
          'parent_id', 'asset_image']


def read_rows():
    rows = {}
    for f in sorted(glob.glob(CAT + '/_viewing_rows/rows_*.txt')):
        for ln in open(f):
            p = [x.strip() for x in ln.rstrip('\n').split('|')]
            if len(p) < 16 or not re.match(r'^B\d+-P\d+$', p[0]):
                continue
            rows[p[0]] = dict(zip(
                ['product_id', 'slot', 'garment_type', 'material_visible', 'pattern',
                 'weight', 'formality', 'shot_type', 'complete_in_frame', 'shop_text',
                 'brand_text', 'product_name_text', 'colour_name_text',
                 'composition_text', 'price_text', 'notes'], p[:16]))
    return rows


def none(v):
    return '' if (v or '').strip().upper() in ('NONE', '', '-') else v.strip()


def shop_of(batch_rows):
    """One shop per batch: the most common legible shop string."""
    c = collections.Counter(none(r['shop_text']).lower() for r in batch_rows if none(r['shop_text']))
    return c.most_common(1)[0][0] if c else ''


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
    return re.sub(r'[^a-z0-9]', '', (s or '').lower())


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


def variant_rows(base_by_id):
    """Recoloured UNIQLO variants from uniqlo_variants.py, as full product rows."""
    v = load_json(CAT + '/_variants.json', {})
    out, hide = [], {}
    for x in v.get('variants', []):
        src = base_by_id.get(x['source'])
        if not src:
            continue
        d = dict(src)
        c = x['colour']
        d.update(product_id=x['product_id'], n_images=0, image_paths='',
                 colour1_hex=c['hex'], colour1_share=c['share'], colour1_L=c['L'],
                 colour1_C=c['C'], colour1_h=c['h'], colour1_rel_chroma=c['rel'],
                 colour1_neutral=c['neutral'], colour1_family=c['family'], colour1_name=c['name'],
                 colour2_hex='', colour2_share='', colour2_family='', colour2_name='',
                 colour3_hex='', colour3_share='', colour3_family='', colour3_name='',
                 colour_confidence='medium', colour_stability='stable',
                 asset_type='cutout_flat', asset_path=x['asset_path'], asset_quality='good',
                 colour_name_text=x.get('colour_name_text', ''),
                 notes=f"recoloured from {x['source']} in CIELAB; colour simulated, not the brand's photo",
                 validated='', used_in='', shelf='', asset_choice='', asset_box='',
                 recoloured='yes', recolour_source=x['source'], parent_id='', asset_image='')
        out.append(d)
    # the other UNIQLO images of a recoloured style leave the shelf, replaced by the variants
    for style, rep in v.get('report', {}).items():
        src = base_by_id.get(rep['source'])
        if not src:
            continue
        for pid, r in base_by_id.items():
            if (pid != rep['source'] and r['brand'] == src['brand']
                    and r['garment_type'] == src['garment_type']):
                hide[pid] = f"replaced by variants of {rep['source']}"
    return out, hide


def split_rows(choices, by_id, review):
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
                     asset_path='content/catalogue/' + entry['path'], asset_image=idx,
                     asset_choice='custom', asset_box=','.join(f'{v:.4f}' for v in box),
                     shelf='', recoloured='', recolour_source='',
                     notes=f'cut by hand from {pid} image {idx}', validated='', used_in='')
            for i in (1, 2, 3):
                for k in ('hex', 'share', 'family', 'name'):
                    d[f'colour{i}_{k}'] = ''
            for k in ('colour1_L', 'colour1_C', 'colour1_h', 'colour1_rel_chroma', 'colour1_neutral'):
                d[k] = ''
            try:
                with Image.open(CAT + '/' + entry['path']) as im:
                    W, H = im.size
                    crop = im.convert('RGB').crop((int(box[0] * W), int(box[1] * H),
                                                   int((box[0] + box[2]) * W), int((box[1] + box[3]) * H)))
                cols, skin, kept = X.colours_for_image(crop, is_cutout=False)
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
    shops = {bid: shop_of(rs) for bid, rs in by_batch.items()}
    kinds = {bid: shop_kind(rs, shops[bid]) for bid, rs in by_batch.items()}

    out = []
    for b in bat:
        pid = b['product_id']
        r = rows.get(pid, {})
        a = assets.get(pid, {})
        c = cols.get(pid, {})
        cl = c.get('colours', [])
        shop = shops.get(b['batch_id'], '')
        kind = kinds.get(b['batch_id'], 'unknown')

        brand = none(r.get('brand_text', ''))
        bconf = 'given' if brand else ''
        if not brand and kind == 'mono-brand':
            # the only guess allowed: another image in this batch named the shop
            # and every legible brand in it was that shop's own
            cands = {none(x['brand_text']) for x in by_batch[b['batch_id']] if none(x['brand_text'])}
            if len(cands) == 1:
                brand, bconf = cands.pop(), 'guessed'
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
            brand=brand, brand_confidence=bconf,
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
            parent_id='', asset_image='')
        ch = choices.get(pid)
        if ch:
            d['asset_choice'] = ch.get('choice', '')
            d['asset_box'] = ','.join(str(v) for v in ch['box']) if ch.get('box') else ''
            d['asset_image'] = ch.get('image', 0) if ch.get('choice') in ('custom', 'item', 'person', 'full') else ''
            if ch.get('hidden'):
                d['shelf'] = 'hidden'
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
    variants, hide = variant_rows(by_id)
    for pid, why in hide.items():
        by_id[pid]['shelf'] = 'hidden'
        by_id[pid]['notes'] = (by_id[pid]['notes'] + '; ' + why).strip('; ')
    for v in variants:
        v['used_in'] = keep.get(v['product_id'], {}).get('used_in', '')
        v['validated'] = keep.get(v['product_id'], {}).get('validated', '')
    out.extend(variants)
    splits = split_rows(choices, by_id, review)
    for d in splits:
        d['used_in'] = keep.get(d['product_id'], {}).get('used_in', '')
        d['validated'] = keep.get(d['product_id'], {}).get('validated', '')
    out.extend(splits)

    os.makedirs(CAT, exist_ok=True)
    with open(CAT + '/products.csv', 'w', newline='') as f:
        w = csv.DictWriter(f, FIELDS)
        w.writeheader()
        w.writerows(out)
    print(len(out), 'products ->', CAT + '/products.csv')
    print('variants merged:', len(variants), ' splits:', len(splits),
          ' hidden:', sum(1 for d in out if d['shelf'] == 'hidden'),
          ' choices applied:', sum(1 for d in out if d['asset_choice']))
    for k in ('brand_confidence', 'colour_confidence', 'asset_type', 'shop_type', 'slot'):
        print(k, collections.Counter(d[k] for d in out).most_common())


if __name__ == '__main__':
    main()
