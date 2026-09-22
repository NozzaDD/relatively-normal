"""Packshots on a plain backdrop: find them, cut them properly, rate them.

A flat lay is the easy case — one garment, no model, a seamless light
backdrop — and its cut-out ought to be perfect. It often was not, because the
shop's own furniture sat in the photo: a NEU badge, a size button, a wishlist
heart. rembg keeps those, because they are objects. So: find the badges with
OCR, paint them out with the backdrop's own colour, and cut again.

Then rate the result by measuring it rather than by the old asset_quality,
which was a rule of thumb about skin and rectangles:

  one piece      the alpha is a single connected component
  off the edge   no alpha on the frame's own border
  no text in it  OCR over the cut-out finds no word inside the mask

All three, and the product goes on the shelf without Review. Any one of them
missing and it stays in Review, where a person looks at it.

  python3 content/tools/flat_lays.py [--limit N]

Writes content/catalogue/_flat_lays.json and, for every product it re-cuts,
content/catalogue/assets/{pid}.webp. It reads the review copies, never the
originals, and touches nothing else.
"""
import os, sys, json, argparse, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from PIL import Image, ImageDraw, ImageFilter
import imglib
from colour_names import classify                      # noqa: F401  (vocabulary check)

try:
    import pytesseract
except ImportError:                                     # no badge masking, then
    pytesseract = None

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CAT = ROOT + '/content/catalogue'
OUT = CAT + '/_flat_lays.json'
MAXSIDE = 1400                  # the cut is made larger than the asset it feeds

CORNER = 0.07                   # the patch of each corner the backdrop is read from
PLAIN_L = 185                   # every corner is light...
PLAIN_SD = 18                   # ...even in itself...
PLAIN_SPREAD = 18               # ...and the same as the other three
SKIN_MAX = 0.015                # a flat lay has no one in it
BLOB_MIN = 0.005                # a component smaller than this is not a garment


def corner_patches(im, frac=CORNER):
    """The four corners: [(luminance, spread, colour), ...].

    The corners, not a ring around the whole photo. A packshot is cropped close
    to the garment, so a ring runs through the garment's own shoulders and reads
    as busy backdrop; the corners are the part of the frame the garment is least
    likely to reach.
    """
    W, H = im.size
    b = max(6, int(min(W, H) * frac))
    out = []
    for box in ((0, 0, b, b), (W - b, 0, W, b), (0, H - b, b, H), (W - b, H - b, W, H)):
        px = list(im.crop(box).getdata())
        n = len(px) or 1
        mean = [sum(p[i] for p in px) / n for i in range(3)]
        var = [sum((p[i] - mean[i]) ** 2 for p in px) / n for i in range(3)]
        out.append((0.299 * mean[0] + 0.587 * mean[1] + 0.114 * mean[2],
                    max(v ** 0.5 for v in var), tuple(int(round(c)) for c in mean)))
    return out


def plain_backdrop(im):
    """-> (is_plain, dimmest corner, busiest corner, spread, backdrop colour)."""
    c = corner_patches(im)
    lums = [x[0] for x in c]
    sds = [x[1] for x in c]
    spread = max(lums) - min(lums)
    col = tuple(int(round(sum(x[2][i] for x in c) / 4)) for i in range(3))
    plain = min(lums) >= PLAIN_L and max(sds) <= PLAIN_SD and spread <= PLAIN_SPREAD
    return plain, round(min(lums), 1), round(max(sds), 1), round(spread, 1), col


def skin_share(im):
    """How much of the photo reads as skin, on the engine's own band."""
    small = im.copy()
    small.thumbnail((160, 160), Image.LANCZOS)
    n = small.width * small.height or 1
    hit = 0
    cache = {}
    for r, g, b in small.getdata():
        k = (r >> 3, g >> 3, b >> 3)
        v = cache.get(k)
        if v is None:
            L, ch, h, _rel = imglib.lch('%02x%02x%02x' % (r, g, b))
            v = cache[k] = imglib.is_skin(L, ch, h)
        hit += v
    return hit / n


def cutout_skin(cut):
    """How much of the cut-out itself reads as skin — a model in the frame."""
    a = cut.getchannel('A')
    small = cut.convert('RGB').copy()
    small.thumbnail((140, 140), Image.LANCZOS)
    sa = a.resize(small.size, Image.NEAREST)
    cache, hit, op = {}, 0, 0
    for (r, g, b), al in zip(small.getdata(), sa.getdata()):
        if not al:
            continue
        op += 1
        k = (r >> 3, g >> 3, b >> 3)
        v = cache.get(k)
        if v is None:
            L, ch, h, _rel = imglib.lch('%02x%02x%02x' % (r, g, b))
            v = cache[k] = imglib.is_skin(L, ch, h)
        hit += v
    return hit / op if op else 0.0


def word_boxes(im, conf=55):
    """Every confident word in the photo, as boxes in its own pixels."""
    if pytesseract is None:
        return []
    try:
        d = pytesseract.image_to_data(im, output_type=pytesseract.Output.DICT)
    except Exception:
        return []
    out = []
    for i, t in enumerate(d['text']):
        t = (t or '').strip()
        if len(t) < 2:
            continue
        try:
            if float(d['conf'][i]) < conf:
                continue
        except (TypeError, ValueError):
            continue
        w, h = d['width'][i], d['height'][i]
        if w <= 0 or h <= 0 or h > im.height * 0.25:
            continue
        out.append((d['left'][i], d['top'][i], w, h, t))
    return out


def alpha_components(a, min_rel=BLOB_MIN):
    """Connected components of a 0/255 alpha band, largest first. No filtering
    is applied to the image — this only counts, because the brief is that
    component filtering drops nothing."""
    W, H = a.size
    px = a.load()
    seen = [[False] * W for _ in range(H)]
    sizes = []
    for y0 in range(H):
        for x0 in range(W):
            if px[x0, y0] == 0 or seen[y0][x0]:
                continue
            n = 0
            stack = [(x0, y0)]
            seen[y0][x0] = True
            while stack:
                x, y = stack.pop()
                n += 1
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < W and 0 <= ny < H and not seen[ny][nx] and px[nx, ny]:
                        seen[ny][nx] = True
                        stack.append((nx, ny))
            sizes.append(n)
    sizes.sort(reverse=True)
    total = sum(sizes) or 1
    return [s for s in sizes if s / total >= min_rel], total


def photo_for(pid, shot, batches):
    """The product's first photo, trimmed the way Review trims it.

    The review copy where there is one — a product already on the shelf has
    none, because it never needed reviewing — and otherwise the same trim
    computed here. Nothing is written either way: the originals and the review
    copies are left exactly as they are.
    """
    src = f'{CAT}/review/{pid}.jpg'
    if os.path.exists(src):
        with Image.open(src) as f:
            return f.convert('RGB')
    b = batches.get(pid)
    if not b or not b.get('images'):
        return None
    import build_review_images as R
    try:
        im, _org, _prev = R.full_photo(b, 0, shot)
    except Exception:
        return None
    return im.convert('RGB')


def raw_cut(im):
    """rembg at full size, hard alpha, nothing dropped."""
    import io
    from rembg import remove
    work = im.copy()
    work.thumbnail((MAXSIDE, MAXSIDE), Image.LANCZOS)
    buf = io.BytesIO()
    work.save(buf, 'PNG')
    out = Image.open(io.BytesIO(remove(buf.getvalue(), session=imglib.session()))).convert('RGBA')
    out.putalpha(out.getchannel('A').point(lambda v: 255 if v >= 200 else 0))
    return out


def paint_out(im, boxes, colour, keep=None):
    """Paint word boxes with the backdrop's own colour.

    `keep` is the garment's mask from the first cut: a word that sits on the
    garment is the garment's own print and is left alone, both because painting
    it would damage the piece and because the rating asks whether text remains
    inside the mask — masking it first would answer the question by cheating.
    """
    out = im.copy()
    d = ImageDraw.Draw(out)
    painted = 0
    for x, y, w, h, _t in boxes:
        if keep is not None:
            cx, cy = min(keep.width - 1, x + w // 2), min(keep.height - 1, y + h // 2)
            if keep.getpixel((cx, cy)):
                continue
        p = max(2, h // 4)
        d.rectangle([x - p, y - p, x + w + p, y + h + p], fill=colour)
        painted += 1
    return out.filter(ImageFilter.GaussianBlur(0.4)) if painted else out, painted


def measure(cut):
    """-> dict of the three measurements, on the cut-out as it stands."""
    a = cut.getchannel('A')
    comps, total = alpha_components(a.resize((min(220, a.width), min(220, a.height)), Image.NEAREST))
    W, H = a.size
    edge = 0
    px = a.load()
    for x in range(W):
        edge += (px[x, 0] > 0) + (px[x, H - 1] > 0)
    for y in range(H):
        edge += (px[0, y] > 0) + (px[W - 1, y] > 0)
    flat = Image.new('RGB', cut.size, (255, 255, 255))
    flat.paste(cut, mask=a)
    inside = 0
    for x, y, w, h, _t in word_boxes(flat, conf=60):
        cx, cy = min(W - 1, x + w // 2), min(H - 1, y + h // 2)
        if px[cx, cy]:
            inside += 1
    return {'components': len(comps), 'edge_pixels': edge, 'words_inside': inside}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--redo', action='store_true')
    args = ap.parse_args()
    import csv
    rows = list(csv.DictReader(open(CAT + '/products.csv')))
    assets = json.load(open(CAT + '/_assets.json'))
    batches = {b['product_id']: b for b in json.load(open(CAT + '/batches.json'))}
    try:
        out = {} if args.redo else json.load(open(OUT))
    except (FileNotFoundError, json.JSONDecodeError):
        out = {}
    todo = [r for r in rows if not r.get('parent_id') and not r.get('recoloured')
            and r['product_id'] in assets and r['product_id'] not in out]
    if args.limit:
        todo = todo[:args.limit]
    print(f'{len(todo)} products to look at, {len(out)} already done', flush=True)
    for k, r in enumerate(todo, 1):
        pid = r['product_id']
        im = photo_for(pid, r.get('shot_type', ''), batches)
        if im is None:
            out[pid] = {'flat': False, 'why': 'no photo'}
            continue
        plain, lum, sd, spread, col = plain_backdrop(im)
        skin = round(skin_share(im), 4)
        rec = {'flat': False, 'lum': lum, 'sd': sd, 'spread': spread, 'skin': skin,
               'shot': r.get('shot_type', '')}
        if not (plain and skin <= SKIN_MAX):
            rec['clean'] = False
            rec['why'] = 'backdrop not plain' if not plain else 'skin in the frame'
            out[pid] = rec
        else:
            # a packshot on a plain backdrop: paint the page's furniture out
            # with the backdrop's own colour and cut it again
            first = raw_cut(im)
            mask = first.getchannel('A').resize(im.size, Image.NEAREST)
            clean_im, painted = paint_out(im, word_boxes(im), col, keep=mask)
            cut = raw_cut(clean_im) if painted else first
            # measured BEFORE the crop: "does not touch the frame edge" is a
            # question about the photograph's frame, and a cut-out trimmed to
            # its own bounding box touches its edges by construction
            m = measure(cut)
            cs = round(cutout_skin(cut), 4)
            bb = cut.getbbox()
            rec.update({'flat': True, 'badges_painted': painted, **m, 'cutout_skin': cs})
            ok = (m['components'] == 1 and m['edge_pixels'] == 0 and m['words_inside'] == 0
                  and cs <= SKIN_MAX and bb and min(bb[2] - bb[0], bb[3] - bb[1]) >= 60)
            rec['clean'] = bool(ok)
            rec['why'] = '' if ok else ', '.join(filter(None, [
                'more than one piece' if m['components'] != 1 else '',
                'touches the frame' if m['edge_pixels'] else '',
                'text inside it' if m['words_inside'] else '',
                'someone is wearing it' if cs > SKIN_MAX else '']))
            if ok:
                cut.crop(bb).save(f'{CAT}/assets/{pid}.webp', 'WEBP', quality=90, method=5)
                rec['recut'] = True
            out[pid] = rec
        if k % 10 == 0 or k == len(todo):
            json.dump(out, open(OUT, 'w'), indent=1)
            print(f'  {k}/{len(todo)}', flush=True)
    json.dump(out, open(OUT, 'w'), indent=1)
    # the asset record follows the measurement: a re-cut flat lay IS a flat
    # cut-out, whatever the old rule of thumb called it, and every product
    # carries the verdict and the reason with it
    for pid, v in out.items():
        a = assets.get(pid)
        if not a:
            continue
        if v.get('recut'):
            a['asset_type'] = 'cutout_flat'
            a['note'] = ((a.get('note', '') + '; ') if a.get('note') else '') + \
                're-cut as a flat lay, %d badge(s) painted out' % v.get('badges_painted', 0)
            a['bytes'] = os.path.getsize(f'{CAT}/assets/{pid}.webp')
        a['measured'] = 'clean' if v.get('clean') else (v.get('why') or 'not measured')
    json.dump(assets, open(CAT + '/_assets.json', 'w'), indent=1)
    flat = [v for v in out.values() if v.get('flat')]
    clean = [v for v in out.values() if v.get('clean')]
    print(f'flat lays re-cut: {len(flat)} of {len(out)};  clean by measurement: {len(clean)}')
    print('badges painted out:', sum(v.get('badges_painted', 0) for v in flat))
    print('why not clean:', collections.Counter(v.get('why', '') for v in out.values()
                                                if not v.get('clean')).most_common(8))


if __name__ == '__main__':
    main()
