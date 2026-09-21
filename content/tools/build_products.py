"""Fold the viewing rows + batch clustering + colour extraction into products.csv."""
import csv, json, glob, os, re, sys, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ROOT = '/home/user/relatively-normal'
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
          'colour_name_text', 'notes', 'validated', 'used_in']


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


def main():
    rows = read_rows()
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
            notes=r.get('notes', ''), validated='', used_in='')
        for i, col in enumerate(cl[:3], 1):
            d[f'colour{i}_hex'] = col['hex']
            d[f'colour{i}_share'] = col['share']
            d[f'colour{i}_family'] = col['family']
            d[f'colour{i}_name'] = col['name']
            if i == 1:
                d.update(colour1_L=col['L'], colour1_C=col['C'], colour1_h=col['h'],
                         colour1_rel_chroma=col['rel'], colour1_neutral=col['neutral'])
        out.append(d)

    os.makedirs(CAT, exist_ok=True)
    with open(CAT + '/products.csv', 'w', newline='') as f:
        w = csv.DictWriter(f, FIELDS)
        w.writeheader()
        w.writerows(out)
    print(len(out), 'products ->', CAT + '/products.csv')
    for k in ('brand_confidence', 'colour_confidence', 'asset_type', 'shop_type', 'slot'):
        print(k, collections.Counter(d[k] for d in out).most_common())


if __name__ == '__main__':
    main()
