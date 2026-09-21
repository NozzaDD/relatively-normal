"""Build studio/data/ — everything the styling desk needs, and nothing else.

The desk is a static page. It never reads the catalogue CSVs or the original
screenshots: this script turns them into two JSON files and a set of web-sized
images inside studio/, which is the only folder that gets deployed. Re-run it
after the catalogue changes and the desk refreshes with it.

  python3 content/tools/build_studio.py [--no-images]
"""
import sys, os, csv, json, shutil, collections, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, '/home/user/relatively-normal')
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) \
    if False else '/home/user/relatively-normal'
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
    if n(r['asset_type']).startswith('cutout') or n(r['asset_type']) == 'tile':
        return 'brand product shot, screenshotted from the shop page'
    return 'unknown'


def build_products(rows):
    out = []
    for r in rows:
        if not n(r['asset_path']):
            continue
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
            asset=f"assets/{r['product_id']}.webp",
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
        ))
    return out


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


def copy_assets(products):
    src_dir = CAT + '/assets'
    a_dir, t_dir = STUDIO + '/assets', STUDIO + '/thumbs'
    os.makedirs(a_dir, exist_ok=True)
    os.makedirs(t_dir, exist_ok=True)
    keep = set()
    for p in products:
        pid = p['product_id']
        keep.add(pid + '.webp')
        src = f'{src_dir}/{pid}.webp'
        shutil.copyfile(src, f'{a_dir}/{pid}.webp')
        with Image.open(src) as im:
            t = im.convert('RGBA')
            t.thumbnail((THUMB, THUMB), Image.LANCZOS)
            t.save(f'{t_dir}/{pid}.webp', 'WEBP', quality=80, method=5)
    for d in (a_dir, t_dir):                    # drop anything the catalogue lost
        for f in os.listdir(d):
            if f not in keep:
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
    a = ap.parse_args()

    prod_rows = list(csv.DictReader(open(CAT + '/products.csv')))
    insp_rows = list(csv.DictReader(open(CAT + '/inspiration.csv')))
    products = build_products(prod_rows)
    inspiration = build_inspiration(insp_rows)

    os.makedirs(DATA, exist_ok=True)
    meta = dict(built_from='content/catalogue', products=len(products),
                inspiration=len(inspiration),
                slots=sorted({p['slot'] for p in products if p['slot']}),
                families=sorted({c['family'] for p in products for c in p['colours'] if c['family']}),
                brands=sorted({p['brand'] for p in products if p['brand']}),
                asset_types=sorted({p['asset_type'] for p in products}))
    json.dump(products, open(DATA + '/products.json', 'w'), separators=(',', ':'))
    json.dump(inspiration, open(DATA + '/inspiration.json', 'w'), separators=(',', ':'))
    json.dump(meta, open(DATA + '/meta.json', 'w'), indent=1)

    if not a.no_images:
        copy_assets(products)
        copy_inspiration(inspiration)
        copy_fonts()

    print('products %d  inspiration %d' % (len(products), len(inspiration)))
    total = 0
    for sub in ('data', 'assets', 'thumbs', 'inspiration', 'fonts', 'js'):
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
