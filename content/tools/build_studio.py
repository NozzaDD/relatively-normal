"""Build studio/data/ — everything the styling desk needs, and nothing else.

The desk is a static page. It never reads the catalogue CSVs or the original
screenshots: this script turns them into two JSON files and a set of web-sized
images inside studio/, which is the only folder that gets deployed. Re-run it
after the catalogue changes and the desk refreshes with it.

  python3 content/tools/build_studio.py [--no-images] [--skip-inspiration]
"""
import sys, os, csv, json, shutil, collections, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CAT = ROOT + '/content/catalogue'
STUDIO = ROOT + '/studio'
DATA = STUDIO + '/data'

THUMB = 320          # shelf thumbnail, long side
INSP_MAX = 1600      # web copy of an inspiration image, long side
INSP_THUMB = 360


def n(v):
    return (v or '').strip()


def num(v):
    try:
        return round(float(v), 4)
    except (TypeError, ValueError):
        return None


def colours_of(r):
    out = []
    for i in (1, 2, 3):
        hx = n(r.get(f'colour{i}_hex'))
        if not hx:
            continue
        c = dict(hex='#' + hx.lstrip('#'), name=n(r.get(f'colour{i}_name')),
                 family=n(r.get(f'colour{i}_family')), share=num(r.get(f'colour{i}_share')))
        if i == 1:
            c['neutral'] = n(r.get('colour1_neutral')).lower() in ('true', '1', 'yes')
        out.append(c)
    return out


def image_source(r):
    """Where the picture came from. The desk prints this into the info file, so
    it has to say what is true and nothing more."""
    if n(r.get('recoloured')) == 'yes':
        return "colour simulated: recoloured from the brand's photo of another colour"
    if n(r['asset_type']).startswith('cutout') or n(r['asset_type']) == 'tile':
        return 'brand product shot, screenshotted from the shop page'
    return 'unknown'


def parse_box(v):
    try:
        b = [float(x) for x in n(v).split(',')]
        return b if len(b) == 4 else None
    except ValueError:
        return None


def image_list(rv, sources):
    """Every screenshot of a product as the desk sees it: path, size, boxes, cells."""
    out = []
    for i, e in enumerate(rv.get('images') or []):
        if not e or 'error' in e:
            continue
        d = dict(path='full/' + os.path.basename(e['path']), w=e['w'], h=e['h'],
                 item=e.get('item'), person=e.get('person'),
                 suggested=e.get('suggested') or [],
                 source=sources[i] if i < len(sources) else '')
        if e.get('whole'):
            d['whole'] = dict(path='full/' + os.path.basename(e['whole']['path']),
                              w=e['whole']['w'], h=e['whole']['h'])
        out.append(d)
    return out


def build_products(rows, review):
    out = []
    by_id = {r['product_id']: r for r in rows}
    for r in rows:
        if not n(r['asset_path']):
            continue
        parent = by_id.get(n(r.get('parent_id'))) if n(r.get('parent_id')) else None
        rv = review.get(parent['product_id'] if parent else r['product_id']) or {}
        clean = (n(r['asset_type']) == 'cutout_flat' and n(r['asset_quality']) == 'good')
        has_full = bool(rv.get('w')) and 'error' not in rv
        images = image_list(rv, (parent or r)['image_paths'].split(';'))
        idx = int(n(r.get('asset_image')) or 0)
        entry = images[idx] if idx < len(images) else (images[0] if images else None)
        out.append(dict(
            product_id=r['product_id'],
            slot=n(r['slot']),
            garment_type=n(r['garment_type']),
            pattern=n(r['pattern']),
            weight=num(r['weight']),
            formality=num(r['formality']),
            colours=colours_of(r),
            colour_confidence=n(r['colour_confidence']),
            colour_stability=n(r['colour_stability']),
            asset=(entry['path'] if n(r['asset_type']) == 'crop' and entry else f"assets/{r['product_id']}.webp"),
            thumb=f"thumbs/{r['product_id']}.webp",
            asset_type=n(r['asset_type']),
            asset_quality=n(r['asset_quality']),
            brand=n(r['brand']), brand_confidence=n(r['brand_confidence']),
            brand_role=n(r['brand_role']),
            product_name=n(r['product_name']),
            product_name_confidence=n(r['product_name_confidence']),
            material=n(r['material']), material_confidence=n(r['material_confidence']),
            price=n(r['price']), price_confidence=n(r['price_confidence']),
            product_url=n(r['product_url']),
            product_url_confidence=n(r['product_url_confidence']),
            image_source=image_source(r),
            shop=n(r['shop']),
            used_in=[x for x in n(r['used_in']).split(';') if x],
            # review: a clean flat cut-out needs no decision; everything else
            # gets a full photo and two boxes to choose from
            clean=clean,
            full=dict(path=entry['path'], w=entry['w'], h=entry['h']) if (has_full and entry) else None,
            boxes=dict(item=rv['item'], person=rv['person']) if has_full else None,
            images=images or None,
            image=idx,
            parent_id=n(r.get('parent_id')),
            choice=n(r.get('asset_choice')) or None,
            custom_box=parse_box(r.get('asset_box')),
            base=n(r.get('asset_base')) or 'photo',
            hidden=n(r.get('shelf')) == 'hidden',
            recoloured=n(r.get('recoloured')) == 'yes',
            recolour_source=n(r.get('recolour_source')),
        ))
    return out


def crop_box(im, box):
    W, H = im.size
    x, y, w, h = box
    return im.crop((int(x * W), int(y * H), int((x + w) * W), int((y + h) * H)))


def insp_colours(r):
    out = []
    for i in (1, 2, 3, 4):
        hx = n(r.get(f'colour{i}_hex'))
        if not hx:
            continue
        out.append(dict(hex='#' + hx.lstrip('#'), name=n(r.get(f'colour{i}_name')),
                        family=n(r.get(f'colour{i}_family')),
                        share=num(r.get(f'colour{i}_share')),
                        role=n(r.get(f'colour{i}_role')), sits=n(r.get(f'colour{i}_sits'))))
    return out


def build_inspiration(rows):
    out = []
    for r in rows:
        stem = os.path.splitext(os.path.basename(r['path']))[0]
        folder = os.path.basename(r['folder'])
        iid = f"{folder.replace(' ', '-')}--{stem}"
        out.append(dict(
            inspiration_id=iid,
            source_path=r['path'],
            folder=r['folder'],
            house=n(r['house']), house_confidence=n(r['house_confidence']),
            colours=insp_colours(r),
            accent_sits=n(r['accent_sits']),
            pattern=n(r['pattern']), pattern_confidence=n(r['pattern_confidence']),
            colour_story=n(r['colour_story']),
            colour_story_confidence=n(r['colour_story_confidence']),
            non_clothing_dominant=dict(hex='#' + n(r['non_clothing_dominant_hex']).lstrip('#'),
                                       name=n(r['non_clothing_dominant_name'])),
            clothes_share=num(r['clothes_share']),
            colour_confidence=n(r['colour_confidence']),
            image=f'inspiration/{iid}.jpg',
            thumb=f'inspiration/thumbs/{iid}.jpg',
            image_source=("someone else's photo, screenshotted from a fashion-week gallery"
                          if 'fashion shows' in r['folder'] else
                          "someone else's photo or screenshot"),
        ))
    return out


def copy_assets(products, rows_by_id):
    a_dir, t_dir, f_dir = STUDIO + '/assets', STUDIO + '/thumbs', STUDIO + '/full'
    for d in (a_dir, t_dir, f_dir):
        os.makedirs(d, exist_ok=True)
    keep, keep_full = set(), set()
    for p in products:
        pid = p['product_id']
        src = ROOT + '/' + rows_by_id[pid]['asset_path']
        if p['asset_type'] != 'crop':                      # a crop has no asset of its own
            keep.add(pid + '.webp')
            shutil.copyfile(src, f'{a_dir}/{pid}.webp')
        for e in p['images'] or []:
            for src_name in [os.path.basename(e['path'])] + \
                    ([os.path.basename(e['whole']['path'])] if e.get('whole') else []):
                keep_full.add(src_name)
                dst = f'{f_dir}/{src_name}'
                src_f = f'{CAT}/review/{src_name}'
                # incremental: only copy what is new or has changed
                if not os.path.exists(dst) or os.path.getsize(dst) != os.path.getsize(src_f):
                    shutil.copyfile(src_f, dst)
        # the thumb shows what the shelf will place: the chosen crop, or the cut-out
        box, base_path = None, None
        entry = (p['images'][p['image']] if p['images'] and p['image'] < len(p['images']) else None)
        if p['full'] and p['choice'] in ('item', 'person', 'full', 'custom', 'whole'):
            if p['choice'] == 'whole':
                box = [0, 0, 1, 1]
            elif p['choice'] == 'custom':
                box = p['custom_box']
            elif p['choice'] == 'full':
                box = [0, 0, 1, 1]
            else:
                box = (entry or p['boxes'] or {}).get(p['choice'])
            if p.get('base') == 'whole' and entry and entry.get('whole'):
                base_path = f"{ROOT}/studio/{entry['whole']['path']}"
            else:
                base_path = f"{ROOT}/studio/{p['full']['path']}"
        keep.add(pid + '.webp')
        with Image.open(base_path if box else src) as im:
            mode = 'RGBA' if (p.get('base') in ('whole', 'asset') or not box) else 'RGB'
            t = crop_box(im.convert(mode), box) if box else im.convert('RGBA')
            t.thumbnail((THUMB, THUMB), Image.LANCZOS)
            t.save(f'{t_dir}/{pid}.webp', 'WEBP', quality=80, method=5)
    for d, k in ((a_dir, keep), (t_dir, keep), (f_dir, keep_full)):   # drop what the catalogue lost
        for f in os.listdir(d):
            if f not in k:
                os.remove(os.path.join(d, f))


def copy_inspiration(items):
    import inspiration_colours as I
    d, td = STUDIO + '/inspiration', STUDIO + '/inspiration/thumbs'
    os.makedirs(td, exist_ok=True)
    keep = set()
    for it in items:
        keep.add(it['inspiration_id'] + '.jpg')
        with Image.open(ROOT + '/' + it['source_path']) as im0:
            im = I.photo_only(im0.convert('RGB'))   # drop browser chrome + letterbox
            im.thumbnail((INSP_MAX, INSP_MAX), Image.LANCZOS)
            im.save(f"{d}/{it['inspiration_id']}.jpg", 'JPEG', quality=80,
                    optimize=True, progressive=True)
            im.thumbnail((INSP_THUMB, INSP_THUMB), Image.LANCZOS)
            im.save(f"{td}/{it['inspiration_id']}.jpg", 'JPEG', quality=78, optimize=True)
    for folder in (d, td):
        for f in os.listdir(folder):
            if f.endswith('.jpg') and f not in keep:
                os.remove(os.path.join(folder, f))


def copy_fonts():
    dst = STUDIO + '/fonts'
    os.makedirs(dst, exist_ok=True)
    for f in os.listdir(ROOT + '/content/boards/fonts'):
        if f.endswith('.ttf'):
            shutil.copyfile(f'{ROOT}/content/boards/fonts/{f}', f'{dst}/{f}')


def folder_size(p):
    return sum(os.path.getsize(os.path.join(dp, f))
               for dp, _, fs in os.walk(p) for f in fs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--no-images', action='store_true',
                    help='rebuild the JSON only, leave the copied images alone')
    ap.add_argument('--skip-inspiration', action='store_true',
                    help='rebuild assets, thumbs and full photos but not the inspiration '
                         'images, which need the original screenshots in content/swipe/')
    a = ap.parse_args()

    prod_rows = list(csv.DictReader(open(CAT + '/products.csv')))
    insp_rows = list(csv.DictReader(open(CAT + '/inspiration.csv')))
    try:
        review = json.load(open(CAT + '/_review_boxes.json'))
    except (FileNotFoundError, json.JSONDecodeError):
        review = {}
    products = build_products(prod_rows, review)
    inspiration = build_inspiration(insp_rows)

    os.makedirs(DATA, exist_ok=True)
    meta = dict(built_from='content/catalogue', products=len(products),
                inspiration=len(inspiration),
                slots=sorted({p['slot'] for p in products if p['slot']}),
                families=sorted({c['family'] for p in products for c in p['colours'] if c['family']}),
                brands=sorted({p['brand'] for p in products if p['brand']}),
                asset_types=sorted({p['asset_type'] for p in products}),
                clean=sum(1 for p in products if p['clean']),
                with_full=sum(1 for p in products if p['full']),
                hidden=sum(1 for p in products if p['hidden']),
                recoloured=sum(1 for p in products if p['recoloured']),
                derived=sum(1 for p in products if p['parent_id']),
                images=sum(len(p['images'] or []) for p in products if not p['parent_id']),
                whole_cutouts=sum(1 for p in products for e in (p['images'] or []) if e.get('whole')))
    json.dump(products, open(DATA + '/products.json', 'w'), separators=(',', ':'))
    json.dump(inspiration, open(DATA + '/inspiration.json', 'w'), separators=(',', ':'))
    json.dump(meta, open(DATA + '/meta.json', 'w'), indent=1)

    if not a.no_images:
        copy_assets(products, {r['product_id']: r for r in prod_rows})
        if not a.skip_inspiration:
            copy_inspiration(inspiration)
        copy_fonts()

    print('products %d  inspiration %d' % (len(products), len(inspiration)))
    total = 0
    for sub in ('data', 'assets', 'thumbs', 'full', 'inspiration', 'fonts', 'js'):
        p = f'{STUDIO}/{sub}'
        if os.path.isdir(p):
            s = folder_size(p)
            total += s
            print('  %-12s %6.1f MB' % (sub + '/', s / 1e6))
    total += sum(os.path.getsize(f'{STUDIO}/{f}') for f in os.listdir(STUDIO)
                 if os.path.isfile(f'{STUDIO}/{f}'))
    print('  %-12s %6.1f MB' % ('deployed', total / 1e6))
    print('  counts:', collections.Counter(p['asset_quality'] for p in products))


if __name__ == '__main__':
    main()
