"""One usable image per product.

Order of preference, per the brief:
  a) flat cut-out from a packshot
  b) on-model cut-out (head and face are fine)
  c) crop tile — a clean 4:5 tile with no page UI and no text

Never touches the originals. Writes WebP (with alpha for cut-outs) at most
1200px on the long side into content/catalogue/assets/.
"""
import json, os, sys, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image, ImageFilter, ImageChops
import imglib

ROOT = '/home/user/relatively-normal'
ASSETS = ROOT + '/content/catalogue/assets'
MAXSIDE = 1200


# ------------------------------------------------------------- find the photo
def edge_density(im, cells=(48, 64)):
    """Per-cell edge energy on a downscaled grey copy. Text columns are dense;
    a studio photograph is not."""
    g = im.convert('L').resize((cells[0] * 4, cells[1] * 4), Image.LANCZOS)
    e = g.filter(ImageFilter.FIND_EDGES)
    w, h = e.size
    px = e.load()
    cw, chh = w // cells[0], h // cells[1]
    grid = [[0.0] * cells[0] for _ in range(cells[1])]
    for cy in range(cells[1]):
        for cx in range(cells[0]):
            s = 0
            for y in range(cy * chh, (cy + 1) * chh):
                for x in range(cx * cw, (cx + 1) * cw):
                    s += px[x, y]
            grid[cy][cx] = s / max(1, cw * chh)
    return grid


def photo_region(im):
    """Largest low-edge-density block — the product photograph, not the copy."""
    grid = edge_density(im)
    H, W = len(grid), len(grid[0])
    flat = sorted(v for row in grid for v in row)
    thresh = flat[int(len(flat) * 0.62)]
    colq = [sum(1 for y in range(H) if grid[y][x] <= thresh) / H for x in range(W)]
    best, cur = (0, 0, 0), None
    for x in range(W):
        if colq[x] >= 0.45:
            cur = x if cur is None else cur
            if x - cur + 1 > best[0]:
                best = (x - cur + 1, cur, x)
        else:
            cur = None
    _, x0, x1 = best
    if best[0] < W * 0.25:
        x0, x1 = 0, W - 1
    rowq = [sum(1 for x in range(x0, x1 + 1) if grid[y][x] <= thresh) / max(1, x1 - x0 + 1) for y in range(H)]
    best, cur = (0, 0, 0), None
    for y in range(H):
        if rowq[y] >= 0.6:
            cur = y if cur is None else cur
            if y - cur + 1 > best[0]:
                best = (y - cur + 1, cur, y)
        else:
            cur = None
    _, y0, y1 = best
    if best[0] < H * 0.18:
        y0, y1 = 0, H - 1
    w, h = im.size
    return (int(x0 / W * w), int(y0 / H * h), int((x1 + 1) / W * w), int((y1 + 1) / H * h))


# ------------------------------------------------------------- quality checks
def cutout_ok(cut, crop_size):
    if cut.size[0] < 120 or cut.size[1] < 120:
        return False, 'too small'
    a = cut.getchannel('A')
    n = sum(a.histogram()[200:])
    fill = n / (cut.size[0] * cut.size[1])
    if fill < 0.10:
        return False, 'almost empty'
    if fill > 0.95:
        return False, 'whole frame kept — background not removed'
    cw, ch = crop_size
    if cut.size[0] > cw * 0.97 and cut.size[1] > ch * 0.97:
        return False, 'cut-out spans the whole crop'
    return True, ''


def save(im, path, quality=86):
    if im.mode == 'RGBA':
        im.save(path, 'WEBP', quality=quality, method=5, lossless=False)
    else:
        im.convert('RGB').save(path, 'WEBP', quality=quality, method=5)
    return os.path.getsize(path)


def fit(im, maxside=MAXSIDE):
    if max(im.size) > maxside:
        im = im.copy()
        im.thumbnail((maxside, maxside), Image.LANCZOS)
    return im


def tile(page, box, ratio=4 / 5):
    """Clean 4:5 tile centred on the photo region, inset to drop any UI edge."""
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    ins = 0.035
    x0, y0 = x0 + int(w * ins), y0 + int(h * ins)
    x1, y1 = x1 - int(w * ins), y1 - int(h * ins)
    w, h = x1 - x0, y1 - y0
    if w <= 0 or h <= 0:
        return None
    if w / h > ratio:
        nw = int(h * ratio)
        cx = (x0 + x1) // 2
        x0, x1 = cx - nw // 2, cx + nw // 2
    else:
        nh = int(w / ratio)
        cy = y0 + int(h * 0.42)                    # bias up: garments sit high
        y0, y1 = max(0, cy - nh // 2), max(0, cy - nh // 2) + nh
        if y1 > page.size[1]:
            y1 = page.size[1]; y0 = max(0, y1 - nh)
    return page.crop((max(0, x0), max(0, y0), min(page.size[0], x1), min(page.size[1], y1)))


def build(product, shot_type):
    """-> dict(asset_type, asset_quality, file, note)"""
    src = ROOT + '/' + product['images'][0]
    with Image.open(src) as im0:
        page = im0.convert('RGB').crop(imglib.trim_chrome(im0.convert('RGB')))
    box = photo_region(page)
    crop = page.crop(box)
    want_cut = shot_type in ('flat packshot', 'ghost mannequin', 'on model', 'detail')
    if want_cut and min(crop.size) >= 100:
        try:
            cut, nb = imglib.cutout(fit(crop, 1400))
            ok, why = cutout_ok(cut, fit(crop, 1400).size)
            if ok:
                kind = 'cutout_flat' if shot_type in ('flat packshot', 'ghost mannequin') else 'cutout_model'
                q = 'good' if (nb <= 4 and min(cut.size) >= 220) else 'usable'
                return dict(asset_type=kind, asset_quality=q, image=fit(cut), note=f'{nb} components')
        except Exception as e:
            why = f'{type(e).__name__}'
    t = tile(page, box)
    if t is None or min(t.size) < 80:
        t = page
    return dict(asset_type='tile', asset_quality='usable' if min(t.size) >= 300 else 'weak',
                image=fit(t), note='crop tile: cut-out not clean or not applicable')


def main(shotmap_path):
    shot = json.load(open(shotmap_path))
    B = json.load(open(ROOT + '/content/catalogue/batches.json'))
    os.makedirs(ASSETS, exist_ok=True)
    out = {}
    for i, p in enumerate(B, 1):
        pid = p['product_id']
        st = shot.get(pid, 'flat packshot')
        try:
            r = build(p, st)
        except Exception as e:
            r = dict(asset_type='tile', asset_quality='weak', image=None, note=f'ERROR {type(e).__name__}: {e}')
        if r['image'] is None:
            out[pid] = dict(asset_type='none', asset_quality='weak', asset_path='', note=r['note'], bytes=0)
            continue
        ext = 'webp'
        fn = f'{pid}.{ext}'
        n = save(r.pop('image'), os.path.join(ASSETS, fn))
        out[pid] = dict(asset_type=r['asset_type'], asset_quality=r['asset_quality'],
                        asset_path=f'content/catalogue/assets/{fn}', note=r['note'], bytes=n)
        if i % 50 == 0:
            print(f'  {i}/{len(B)}', flush=True)
    json.dump(out, open(ROOT + '/content/catalogue/_assets.json', 'w'), indent=1)
    tot = sum(v['bytes'] for v in out.values())
    print('assets:', len(out), 'total %.1f MB' % (tot / 1e6))
    import collections
    print(collections.Counter(v['asset_type'] for v in out.values()))
    print(collections.Counter(v['asset_quality'] for v in out.values()))


if __name__ == '__main__':
    main(sys.argv[1])
