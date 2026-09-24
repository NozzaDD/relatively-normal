"""UNIQLO colour variants from the swatch circles.

Every UNIQLO product page carries a row of colour circles under "Colour:" in
the buy panel, one per colour the style comes in, and each circle is a swatch
of the real fabric. uniqlo_pages.py reads them; this script turns them into
variants.

For each style:

  source      the style's clean single flat lay, cut from the one photo panel
              chosen by eye in STYLES and measured: one piece, clear of the
              frame, no text inside
  targets     the centre of every swatch circle, the selected one's ring
              avoided (uniqlo_pages.py)
  real photo  where the style's all-colours photo lays the colours out as
              separate garments, a garment that stands alone — not touching
              the frame, not touching another garment, one colour — is cut out
              and used for its swatch instead of a recolour. A real photo
              always beats a simulated one.
  cross-check every swatch against the colours on the all-colours photo, as a
              dE2000 recorded per swatch
  recolour    otherwise: the source recoloured in CIELAB, the engine's colour
              space with the engine's own constants — the source's lightness
              detail kept, hue, chroma and mean lightness moved to the swatch

A swatch whose colour is the source's own is skipped: the brand's real photo
of that colour is the source itself. The names of the colours that are not
selected are not on the page, so a variant's colour_name_text is empty unless
its swatch is the selected one; the catalogue names every colour from its
pixels. Every recolour row carries recoloured = yes and recolour_source, and
the desk prints "colour simulated" beside it in the info file and piece list.

Writes
  content/catalogue/variants/{source}-sw{nn}.webp
  content/catalogue/_variants.json               rows build_products.py merges in
  content/catalogue/sheets/uniqlo-{style}.jpg    one sheet per style (variant_sheets.py, rows)
"""
import sys, os, json, csv, glob, io
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
from scipy.cluster.vq import kmeans2
import imglib
import flat_lays as FL
from colour_names import classify
from contact_sheet import sheet
from engine import colour as EC

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CAT = ROOT + '/content/catalogue'
OUT = CAT + '/variants'
SCRATCH = __import__('tempfile').mkdtemp(prefix='uq-')   # sheet inputs, never committed
IMG = 'content/swipe/products/IMG_{:0>4}.png'      # '740' -> IMG_0740, '1170' -> IMG_1170

# style -> source (screenshot, photo panel, share of the panel's top to skip,
# because a strip of the photo above sometimes shares the panel) and the
# all-colours photos (screenshot, panel). Chosen by eye from the panel sheets.
# Styles with no clean single flat lay are listed in NO_SOURCE.
STYLES = {
    '100% Cashmere Crew Neck Jumper':        dict(source=('740', 1, 0.45), colours=[('739', 2)]),
    '100% Cashmere Crew Neck Cardigan':      dict(source=('741', 1, 0.0), colours=[]),
    '100% Cashmere V Neck Jumper':           dict(source=('743', 0, 0.0), colours=[]),
    '100% Cashmere Turtleneck Jumper':       dict(source=('745', 0, 0.2), colours=[]),
    '100% Cashmere Crew Neck Short Cardigan': dict(source=('746', 0, 0.08), colours=[]),
    '100% Cashmere High Neck Button Jumper': dict(source=('748', 2, 0.0), colours=[]),
    'Soufflé Yarn Crew Neck Jumper':         dict(source=('750', 1, 0.0), colours=[('749', 1)]),
    '100% Merino Crew Neck Cardigan':        dict(source=('752', 0, 0.0), colours=[]),
    '100% Merino Crew Neck Jumper':          dict(source=('755', 0, 0.1), colours=[('754', 1)]),
    '100% Merino Ribbed Turtleneck Jumper':  dict(source=('758', 0, 0.06), colours=[('757', 0)]),
    '3D Knit Seamless Merino Blend Ribbed Polo Jumper': dict(source=('761', 1, 0.0), colours=[('760', 1)]),
    'Merino Polo Neck Cardigan':             dict(source=('763', 1, 0.0), colours=[]),
    'Utility Cotton Blend Parka':            dict(source=('765', 1, 0.0), colours=[]),
    'Fleece Lined Stand Blouson':            dict(source=('769', 1, 0.0), colours=[]),
    'Seamless Down Parka':                   dict(source=('773', 2, 0.0), colours=[('772', 0)]),
    'Mini T-Shirt (Long Sleeve)':            dict(source=('777', 0, 0.3), colours=[('776', 2)]),
    'Hoodie T-Shirt (Long Sleeve)':          dict(source=('782', 1, 0.0), colours=[('781', 0)]),
    'Soft Ribbed T-Shirt (Long Sleeve)':     dict(source=('785', 0, 0.2), colours=[('784', 1)]),
    'Mini T-Shirt':                          dict(source=('791', 0, 0.0), colours=[('790', 1)]),
    # this screenshot's catalogue row was typed as a t-shirt by the viewing
    # pass; the page and the photo are a coat
    'Hooded Long Coat (Oversized)':          dict(source=('794', 0, 0.12), colours=[],
                                                  slot='layer', garment_type='hooded long coat'),
    'Sweat Half-Zip Pullover':               dict(source=('796', 1, 0.0), colours=[]),
    'Ultra Stretch Active Full-Zip Jacket':  dict(source=('797', 1, 0.0), colours=[]),
    # shares catalogue row B062-P014 with the jacket; the row describes the jacket
    'Ultra Stretch Active Flare Leggings':   dict(source=('798', 2, 0.0), colours=[],
                                                  slot='bottom', garment_type='flare leggings'),
    'Sweatshirt':                            dict(source=('800', 1, 0.1), colours=[('799', 2)]),
    # the 23 September screenshots: three new styles, and a single flat lay for
    # two styles that had none before
    'Soufflé Yarn Polo Jumper':              dict(source=('1164', 1, 0.0), colours=[]),
    'Smooth Cotton Crew Neck Jumper':        dict(source=('1168', 2, 0.0), colours=[('1168', 1)]),
    '100% Supima Cotton T-Shirt':            dict(source=('1172', 2, 0.0), colours=[('1172', 1)]),
    'HEATTECH Extra Warm Cashmere Blend Turtleneck T-Shirt (Long Sleeve)':
                                             dict(source=('1170', 0, 0.3), colours=[]),
    'Crew Neck T-Shirt':                     dict(source=('1171', 2, 0.0), colours=[('1171', 1)]),
}
NO_SOURCE = {
    'Windproof Stand Collar Blouson': 'only a fan of four overlapping colours and a model; no single flat lay',
    'Ribbed Henley Neck Long Sleeve T-Shirt': 'only a model and an overlapping fan; no single flat lay',
    'HEATTECH Ultra Warm Crew Neck T-Shirt (Long Sleeve)': 'only model shots',
}

# Judged by eye on the contact sheets, one per style.
DROPPED = {
    'B062-P011-sw02': 'wine to white: the dark seam inside the back neck prints through as a black line, '
                      'and the right sleeve keeps a dark edge',
    'B062-P011-sw03': 'wine to pale grey: the same black neck-seam line and dark sleeve edge as the white',
    'B062-P011-sw07': 'wine to off-white: the same black neck-seam line and dark sleeve edge as the white',
    'B060-P004-sw03': 'burgundy to off-white: the hood interior stays near black against a pale body and '
                      'the fold shading turns harsh — reads as a filter, not a garment',
    'B061-P003-V2-sw02': 'off-white to dark grey: the beige seam tape and hood lining stand out as '
                         'speckled lines on the dark body',
}

SAME_AS_SOURCE = 16.0      # a swatch this close (dE2000) to the source's garment is its own colour
REAL_MATCH = 12.0          # a lone garment on the all-colours photo is this swatch's colour
DARK_TO_PALE = (30.0, 82.0)  # source L below the first, target L above the second: flagged


# --------------------------------------------------------- Lab, vectorised
# The same constants and piecewise functions as engine/colour.py, applied to
# arrays. The engine stays untouched; this only has to agree with it.
_D65 = np.array(EC._D65)
_M_RGB2XYZ = np.array(EC._RGB_TO_XYZ)
_M_XYZ2RGB = np.array(EC._XYZ_TO_RGB)
_D = 6.0 / 29.0


def srgb_to_lab_np(rgb):                    # rgb float 0-255, shape (..., 3)
    c = rgb / 255.0
    lin = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    xyz = lin @ _M_RGB2XYZ.T / _D65
    f = np.where(xyz > _D ** 3, np.cbrt(np.maximum(xyz, 1e-12)), xyz / (3 * _D * _D) + 4.0 / 29.0)
    L = 116 * f[..., 1] - 16
    a = 500 * (f[..., 0] - f[..., 1])
    b = 200 * (f[..., 1] - f[..., 2])
    return np.stack([L, a, b], axis=-1)


def lab_to_srgb_np(lab):
    fy = (lab[..., 0] + 16) / 116.0
    fx = fy + lab[..., 1] / 500.0
    fz = fy - lab[..., 2] / 200.0
    f = np.stack([fx, fy, fz], axis=-1)
    xyz = np.where(f > _D, f ** 3, 3 * _D * _D * (f - 4.0 / 29.0)) * _D65
    lin = np.clip(xyz @ _M_XYZ2RGB.T, 0, 1)
    c = np.where(lin <= 0.0031308, 12.92 * lin, 1.055 * lin ** (1 / 2.4) - 0.055)
    return np.clip(c * 255, 0, 255)


def de(a, b):
    return EC.delta_e_2000(tuple(float(v) for v in a), tuple(float(v) for v in b))


# ------------------------------------------------------------- the page
def photo_panels(im):
    """The photographs in the left column of a UNIQLO page, top to bottom.
    Each sits on a light grey that the page's white does not share, so a panel
    is a run of rows that are not white down the column's left margin."""
    a = np.asarray(im.convert('L')).astype(int)
    H, W = a.shape
    x0 = int(W * 0.03)
    col = a[:, x0 - 3:x0 + 3].mean(1)
    nonwhite = col < 250
    runs, s = [], None
    for y in range(int(H * 0.08), H):
        if nonwhite[y] and s is None:
            s = y
        if (not nonwhite[y] or y == H - 1) and s is not None:
            if y - s > 120:
                runs.append((s, y))
            s = None
    out = []
    for t, b in runs:
        xs = np.where(a[(t + b) // 2][:int(W * 0.6)] < 250)[0]
        out.append((int(xs.min()), t, int(xs.max()) + 1, b))
    return out


def panel_of(num, idx, skip_top=0.0):
    im = Image.open(ROOT + '/' + IMG.format(num)).convert('RGB')
    l, t, r, b = photo_panels(im)[idx]
    t += int((b - t) * skip_top)
    return im.crop((l, t, r, b))


def rows_by_image():
    rows = list(csv.DictReader(open(CAT + '/products.csv')))
    out = {}
    for r in rows:
        if r.get('recoloured') == 'yes' or r.get('parent_id') or not r['image_paths']:
            continue
        for i, p in enumerate(r['image_paths'].split(';')):
            out.setdefault(p, (r, i))
    return out


# ------------------------------------------------------------- cutting
def source_cut(panel):
    """The panel cut whole, the biggest piece kept, and the three measurements
    the shelf gate uses, taken on the uncropped cut."""
    cut = FL.raw_cut(panel)
    kept, _ = imglib.keep_main_blobs(cut, rel=0.5, max_blobs=1)
    m = FL.measure(kept)
    clean = m['components'] == 1 and m['edge_pixels'] == 0 and m['words_inside'] == 0
    bb = kept.getchannel('A').getbbox()
    return (kept.crop(bb) if bb else kept), m, clean


def garment_lab(rgba, k=3):
    """The garment's own colour: the biggest cluster of its opaque pixels."""
    arr = np.asarray(rgba.convert('RGBA')).astype(np.float64)
    opaque = arr[..., 3] > 200
    lab = srgb_to_lab_np(arr[..., :3])[opaque]
    rng = np.random.default_rng(1)
    s = lab[rng.choice(len(lab), size=min(len(lab), 20000), replace=False)]
    cent, labels = kmeans2(s, k, minit='++', seed=0)
    counts = np.bincount(labels, minlength=k)
    i = int(np.argmax(counts))
    return cent[i], float(counts[i] / counts.sum())


def lone_garments(panel):
    """Every garment on an all-colours photo that stands alone: its own blob,
    clear of the frame, big enough to be a garment, and one colour. A fan's
    garments overlap into one blob and so never qualify, except where the
    whole fan is a single colour, which it never is."""
    cut = FL.raw_cut(panel)
    # rembg reads a grid of garments as one picture and drops half of them;
    # on a plain backdrop, whatever differs from the corners is garment
    arr0 = np.asarray(panel.resize(cut.size)).astype(np.float64)
    k = max(4, min(cut.size) // 30)
    bg = np.median(np.concatenate([arr0[:k, :k].reshape(-1, 3), arr0[:k, -k:].reshape(-1, 3),
                                   arr0[-k:, :k].reshape(-1, 3), arr0[-k:, -k:].reshape(-1, 3)]), axis=0)
    off = ndimage.binary_opening(np.abs(arr0 - bg).max(axis=2) > 14, iterations=2)
    off = ndimage.binary_fill_holes(off)
    a = (np.asarray(cut.getchannel('A')) > 0) | off
    cut = Image.fromarray(np.dstack([arr0, a * 255.0]).astype(np.uint8), 'RGBA')
    # tiles laid close touch through their shadows; wearing the mask down
    # parts them, then each grows back into its own share of the mask
    e = max(2, min(a.shape) // 55)
    seeds, n = ndimage.label(ndimage.binary_erosion(a, iterations=e))
    if not n:
        return [], cut
    _, (iy, ix) = ndimage.distance_transform_edt(seeds == 0, return_indices=True)
    lab_img = np.where(a, seeds[iy, ix], 0)
    sizes = ndimage.sum(a, lab_img, range(1, n + 1))
    big = sizes.max()
    out = []
    arr = np.asarray(cut).astype(np.float64)
    for i, sl in enumerate(ndimage.find_objects(lab_img), 1):
        sz = sizes[i - 1]
        if sz < 0.12 * big:
            continue
        clear = sl[0].start > 1 and sl[1].start > 1 and sl[0].stop < a.shape[0] - 1 and sl[1].stop < a.shape[1] - 1
        m = lab_img[sl] == i
        px = arr[sl][m][:, :3]
        lab = srgb_to_lab_np(px)
        med = np.median(lab, axis=0)
        # one colour: nearly all of it within reach of its own median
        d = np.sqrt((0.5 * (lab[:, 0] - med[0])) ** 2 + (lab[:, 1] - med[1]) ** 2 + (lab[:, 2] - med[2]) ** 2)
        one = float((d < 14).mean())
        out.append(dict(box=(sl[1].start, sl[0].start, sl[1].stop, sl[0].stop), size=int(sz),
                        clear=bool(clear), one_colour=one, lab=med,
                        panel=panel, scale=panel.width / cut.width))
    return out, cut


def real_cut(g):
    """The lone garment cut again on its own, from the photo at full size:
    rembg reads one garment far better than a page of them."""
    l, t, r, b = (int(v * g['scale']) for v in g['box'])
    pad = int(0.06 * max(r - l, b - t))
    P = g['panel']
    crop = P.crop((max(0, l - pad), max(0, t - pad), min(P.width, r + pad), min(P.height, b + pad)))
    cut = FL.raw_cut(crop)
    cut, _ = imglib.keep_main_blobs(cut, rel=0.5, max_blobs=1)
    bb = cut.getchannel('A').getbbox()
    return cut.crop(bb) if bb else cut


def colours_on(cut, k=12):
    """The colours on an all-colours photo, for the cross-check."""
    arr = np.asarray(cut).astype(np.float64)
    keep = arr[..., 3] > 200
    lab = srgb_to_lab_np(arr[..., :3])[keep]
    if len(lab) < 200:
        return []
    rng = np.random.default_rng(0)
    s = lab[rng.choice(len(lab), size=min(len(lab), 40000), replace=False)]
    cent, labels = kmeans2(s, k, minit='++', seed=0)
    counts = np.bincount(labels, minlength=k)
    return [c for c, n in zip(cent, counts) if n / counts.sum() >= 0.01]


def recolour(src_rgba, src_lab, target_lab):
    """Keep the source's lightness detail; take the target's hue, chroma and mean L."""
    arr = np.asarray(src_rgba.convert('RGBA')).astype(np.float64)
    rgb, alpha = arr[..., :3], arr[..., 3]
    lab = srgb_to_lab_np(rgb)
    L, a, b = lab[..., 0], lab[..., 1], lab[..., 2]
    opaque = alpha > 200
    Ls, as_, bs = src_lab
    Cs = float(np.hypot(as_, bs))
    # labels, buttons and tags are the pixels that are not the garment's colour.
    # A fold's shadow keeps the garment's hue and most of its chroma while its
    # lightness drops a long way, so the test is on hue and chroma for a
    # coloured source and on lightness only for a neutral one.
    C = np.hypot(a, b)
    if Cs >= 8:
        dh = np.abs((np.degrees(np.arctan2(b, a) - np.arctan2(bs, as_)) + 180) % 360 - 180)
        garment = opaque & (C >= 0.3 * Cs) & (dh <= 40) & (np.abs(L - Ls) < 55)
    else:
        garment = opaque & (C < max(12.0, 3 * Cs)) & (np.abs(L - Ls) < 45)
    # What that leaves out is of two kinds. A neck label, or a trim in a
    # contrast colour (a rib hem, piping), is the maker's and stays as it is.
    # A seam line, a deep fold or a speck of highlight is the garment's own
    # shading, and left out it prints the source's colour through the new one
    # — dark streaks on a pale variant, pale ones on a dark variant. So only
    # what sits in the neck or is big enough to be a trim keeps its colour.
    out_, n = ndimage.label(opaque & ~garment)
    if n:
        ys, xs = np.where(opaque)
        top, height = ys.min(), max(1, ys.max() - ys.min())
        sizes = ndimage.sum(np.ones_like(L), out_, range(1, n + 1))
        cys = ndimage.center_of_mass(np.ones_like(L), out_, range(1, n + 1))
        keep = np.zeros(n + 1, bool)
        for i in range(n):
            neck = (cys[i][0] - top) / height < 0.16
            trim = sizes[i] > 0.02 * opaque.sum()
            keep[i + 1] = neck or trim
        garment = opaque & ~keep[out_]
    Lt, at, bt = target_lab
    Ct = float(np.hypot(at, bt))
    ht = np.arctan2(bt, at)
    # chroma follows the source's own variation, gently, so folds stay folds
    ratio = np.clip(0.7 + 0.3 * (np.hypot(a, b) / max(Cs, 4.0)), 0.55, 1.35) if Cs >= 6 else np.ones_like(L)
    # a dark target has no room for the source's highlights: compress detail
    scale = 1.0 if Lt >= Ls else float(np.clip(Lt / max(Ls, 1), 0.45, 1.0))
    Ln = np.clip(Lt + (L - Ls) * scale, 1, 99)
    Cn = Ct * ratio
    new = lab.copy()
    new[..., 0] = np.where(garment, Ln, L)
    new[..., 1] = np.where(garment, Cn * np.cos(ht), a)
    new[..., 2] = np.where(garment, Cn * np.sin(ht), b)
    out = np.dstack([lab_to_srgb_np(new), alpha]).astype(np.uint8)
    return Image.fromarray(out, 'RGBA'), float(garment.sum() / max(1, opaque.sum()))


def speckle(rgba):
    """How much the garment's lightness jumps pixel to pixel: the median of the
    absolute difference between neighbours, in L. Recorded, not a gate."""
    arr = np.asarray(rgba.convert('RGBA')).astype(np.float64)
    L = srgb_to_lab_np(arr[..., :3])[..., 0]
    m = arr[..., 3] > 200
    dx = np.abs(np.diff(L, axis=1))[m[:, 1:] & m[:, :-1]]
    return float(np.percentile(dx, 90)) if dx.size else 0.0


def colour_record(lab):
    hx = EC.lab_to_hex(tuple(float(v) for v in lab))
    fam, name, L, C, h, rel, nt = classify(hx)
    return dict(hex=hx, family=fam, name=name, share=1.0, L=round(L, 1), C=round(C, 1),
                h=round(h, 1), rel=round(rel, 3), neutral=nt)


def slug(s):
    import unicodedata
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode()   # soufflé -> souffle
    return ''.join(c if c.isalnum() else '-' for c in s.lower()).strip('-').replace('--', '-')


# ------------------------------------------------------------- main
def main():
    pages = json.load(open(CAT + '/_uniqlo_pages.json'))
    by_img = rows_by_image()
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(SCRATCH, exist_ok=True)
    # only this script's own files: variants/ also holds colourway_variants.py's
    # (-cw) and same_product.py's (-mc)
    for f in glob.glob(OUT + '/*-sw[0-9][0-9].webp') + glob.glob(OUT + '/*-source.png'):
        os.remove(f)
    # style id and every screenshot of the style, from the page readings
    style_imgs, style_id = {}, {}
    for p, rec in pages.items():
        if not rec['name']:
            continue
        style_imgs.setdefault(rec['name'], []).append(p)
        if rec['product_id']:
            style_id[rec['name']] = rec['product_id']

    variants, report, dropped = [], {}, {}
    bases = set()
    for style, st in STYLES.items():
        num, idx, skip = st['source']
        img = IMG.format(num)
        src_row, _ = by_img[img]
        # one catalogue row can hold screenshots of two styles (B062-P014 holds
        # a jacket and a pair of leggings); the screenshot keeps their ids apart
        base_id = src_row['product_id']
        if base_id in bases:
            base_id = f"{base_id}-I{num}"
        bases.add(base_id)
        page = pages[img]
        assert page['name'] == style, (style, page['name'])
        swatches = page['swatches']
        panel = panel_of(num, idx, skip)
        src, meas, clean = source_cut(panel)
        src_lab, src_share = garment_lab(src)
        sid = slug(style)
        spath = f'{OUT}/{base_id}-source.png'
        src.save(spath)
        cells = [dict(path=spath, label=f'SOURCE {src_row["product_id"]} IMG_{num:0>4}\n'
                      f'{"clean" if clean else "NOT clean"}: {meas["components"]} piece(s), '
                      f'{meas["edge_pixels"]} edge px', swatches=[EC.lab_to_hex(tuple(src_lab))])]
        # the swatch circles as read, the selected one marked
        sw_img = Image.new('RGB', (230, 230), (128, 128, 128))
        d = ImageDraw.Draw(sw_img)
        n = len(swatches)
        per = max(1, int(np.ceil(np.sqrt(n))))
        r = 230 // per
        for i, s in enumerate(swatches):
            x, y = (i % per) * r, (i // per) * r
            d.ellipse([x + 4, y + 4, x + r - 4, y + r - 4], fill='#' + s['hex'],
                      outline=(0, 0, 0) if s['selected'] else None, width=3)
            d.text((x + 6, y + 4), str(i + 1), fill=(255, 255, 255))
        swp = f'{SCRATCH}/{sid}-swatches.png'
        sw_img.save(swp)
        sel = [s for s in swatches if s['selected']]
        cells.append(dict(path=swp, label=f'{n} swatches read\nselected: {page["colour_no"]} {page["colour"]}',
                          swatches=[s['hex'] for s in swatches]))
        # all-colours photos: lone garments and the colours for the cross-check
        lone, fan_colours = [], []
        for cn, ci in st['colours']:
            cpanel = panel_of(cn, ci)
            gs, ccut = lone_garments(cpanel)
            cp = f'{SCRATCH}/{sid}-colours-{cn}.png'
            ccut.save(cp)
            cells.append(dict(path=cp, label=f'all colours IMG_{cn:0>4}\n'
                              f'{sum(1 for g in gs if g["clear"] and g["one_colour"] > 0.8)} garments stand alone'))
            fan_colours += colours_on(ccut)
            for g in gs:
                g['from'] = IMG.format(cn)
                lone.append(g)
        # the source's own swatch: the nearest to the measured garment
        d_src = [de(src_lab, s['lab']) for s in swatches]
        own = int(np.argmin(d_src)) if swatches else -1
        # a lone garment goes to the swatch it is nearest, one garment per swatch
        real_for = {}
        cand = sorted(((de(g['lab'], s['lab']), gi, si) for gi, g in enumerate(lone)
                       if g['clear'] and g['one_colour'] > 0.8 for si, s in enumerate(swatches)))
        used_g = set()
        for dd, gi, si in cand:
            if dd > REAL_MATCH or gi in used_g or si in real_for:
                continue
            real_for[si] = (lone[gi], dd)
            used_g.add(gi)
        made = []
        for si, s in enumerate(swatches):
            pid = f"{base_id}-sw{si + 1:02d}"
            xcheck = round(min(de(s['lab'], c) for c in fan_colours), 1) if fan_colours else None
            name_text = f"{page['colour_no']} {page['colour']}" if s['selected'] else ''
            base = dict(product_id=pid, source=src_row['product_id'], style=style,
                        style_id=style_id.get(style, ''), swatch=si + 1, swatch_hex=s['hex'],
                        selected=s['selected'], cross_check_de=xcheck,
                        delta_e_to_source=round(d_src[si], 1), colour_name_text=name_text,
                        garment_type=st.get('garment_type', src_row['garment_type']),
                        slot=st.get('slot', src_row['slot']),
                        slot_confidence='guessed' if 'slot' in st else '',
                        price=page['price'],
                        source_clean=clean)
            if si == own and d_src[si] <= SAME_AS_SOURCE:
                dropped[pid] = (f"swatch {si + 1} is the source's own colour (dE {d_src[si]:.1f}): "
                                f"the real photo is {src_row['product_id']}")
                continue
            path = f'{OUT}/{pid}.webp'
            if si in real_for:
                g, dd = real_for[si]
                im = real_cut(g)
                im.save(path, 'WEBP', quality=88, method=5)
                glab, _ = garment_lab(im)
                rec = dict(base, real=True, real_from=g['from'], real_de=round(dd, 1),
                           colour=colour_record(glab))
                label = f'{pid} REAL photo\nfrom IMG_{g["from"][-8:-4]} dE {dd:.1f} to swatch'
            else:
                im, share = recolour(src, src_lab, s['lab'])
                im.save(path, 'WEBP', quality=88, method=5)
                rec = dict(base, real=False, recoloured_share=round(share, 3),
                           colour=colour_record(s['lab']), speckle=round(speckle(im), 1))
                flag = ''
                if src_lab[0] < DARK_TO_PALE[0] and s['lab'][0] > DARK_TO_PALE[1]:
                    flag = ' DARK->PALE'
                label = f'{pid} recolour{flag}\nswatch {si + 1} {rec["colour"]["name"]} xchk {xcheck}'
            cells.append(dict(path=path, label=label, swatches=[s['hex']]))
            if pid in DROPPED:
                dropped[pid] = DROPPED[pid]
                os.remove(path)
                continue
            rec['asset_path'] = f'content/catalogue/variants/{pid}.webp'
            variants.append(rec)
            made.append(pid)
        report[style] = dict(source=src_row['product_id'], source_image=img, source_clean=clean,
                             source_cut=os.path.relpath(spath, ROOT),
                             source_measure=meas, style_id=style_id.get(style, ''),
                             swatches=len(swatches), own_swatch=own + 1,
                             own_swatch_de=round(d_src[own], 1) if swatches else None,
                             colours_photos=[IMG.format(c) for c, _ in st['colours']],
                             images=sorted(style_imgs.get(style, [])),
                             variants=made, real=[p for p in made if any(v['product_id'] == p and v['real'] for v in variants)])
        print(f'{style}: {len(swatches)} swatches -> {len(made)} variants '
              f'({len(report[style]["real"])} real), source {"clean" if clean else "NOT clean"}', flush=True)
    json.dump(dict(variants=variants, report=report, dropped=dropped, no_source=NO_SOURCE,
                   style_ids=style_id), open(CAT + '/_variants.json', 'w'), indent=1, default=float)
    import variant_sheets             # the per-style sheets, layout A: one row per variant
    variant_sheets.write('rows', only='_variants.json')
    print('styles:', len(report), ' variants kept:', len(variants),
          ' real:', sum(v['real'] for v in variants), ' dropped:', len(dropped))
    for k, why in dropped.items():
        print('  dropped', k, '-', why)


if __name__ == '__main__':
    main()
