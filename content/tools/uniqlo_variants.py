"""UNIQLO colour variants: one clean flat-lay, recoloured once per available colour.

UNIQLO pages give one good single flat lay per style plus a picture with every
colour stacked or fanned out. The single flat lay is the source. The colours
are read off the all-colours picture (garments masked, skin dropped, shading
merged). Each recolour keeps the source's lightness detail and moves hue,
chroma and mean lightness to the target — in CIELAB, the engine's colour
space, with the engine's own constants.

A recoloured piece is not the brand's photo of that colour. Every variant row
carries recoloured = yes and recolour_source, and the desk prints
"colour simulated" beside it in the info file and the piece list.

Writes
  content/catalogue/variants/{source}-{colour}.webp
  content/catalogue/_variants.json          rows build_products.py merges in
  content/catalogue/sheets/uniqlo-{style}.jpg  one contact sheet per style
"""
import sys, os, json, csv, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import numpy as np
from PIL import Image
from scipy.cluster.vq import kmeans2
import imglib
from colour_names import classify
from make_assets import photo_region, fit
from contact_sheet import sheet
from engine import colour as EC

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CAT = ROOT + '/content/catalogue'
OUT = CAT + '/variants'

# style -> the single flat lay (source) and the picture with every colour on it.
# Chosen from the UNIQLO contact sheets: only styles that have both qualify.
STYLES = {
    'merino-crew-neck-jumper':   dict(source='B059-P005', colours='B059-P004'),
    'hooded-henley-tee':         dict(source='B062-P004', colours='B062-P003'),
    'cropped-fitted-tee':        dict(source='B062-P011', colours='B062-P010'),
    'crew-neck-sweatshirt':      dict(source='B062-P016', colours='B062-P015'),
}

# Judged by eye on the contact sheets in content/catalogue/sheets/uniqlo-*.jpg.
# A style is dropped when it has no clean source; a variant when it looks fake.
DROPPED = {
    'hooded-henley-tee': "the catalogue's cut-out of B062-P004 is a sliver of the hood, not the "
                         "garment, so the style has no clean source",
    'B059-P005-off-white': 'dark brown to off-white: the lightness jump leaves speckle and looks fake',
}
# A variant within this dE of the source is the source's own colour, and the
# brand's real photo already exists as a row. No simulated copy of a real photo.
SAME_AS_SOURCE = 12.0

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


# ------------------------------------------------------------- images
def page_photo(pid, B):
    with Image.open(ROOT + '/' + B[pid]['images'][0]) as im0:
        page = im0.convert('RGB')
        page = page.crop(imglib.trim_chrome(page))
    return page


def source_cutout(pid, B, assets):
    """The catalogue's own cut-out when it is a good flat one; otherwise re-cut
    from the page keeping the one biggest blob, so a knit detail crop or a hand
    does not ride along."""
    a = assets.get(pid, {})
    if a.get('asset_type') == 'cutout_flat' and a.get('asset_quality') == 'good':
        return Image.open(ROOT + '/' + a['asset_path']).convert('RGBA')
    page = page_photo(pid, B)
    box = imglib.product_box(page) or photo_region(page)
    cut, _ = imglib.cutout(fit(page.crop(box), 1400), blob_rel=0.45, max_side=1200)
    bb = cut.getchannel('A').point(lambda v: 255 if v > 200 else 0).getbbox()
    return cut.crop(bb) if bb else cut


def garment_pixels_of_colour_picture(pid, B):
    """Every garment pixel on the all-colours picture, background and skin gone."""
    page = page_photo(pid, B)
    # UNIQLO lays the page out as photos left, buy panel right. The panel's
    # black button and colour chips would cluster as colours, so only the photo
    # column is read — the whole column, since the colours picture can sit
    # under a model shot.
    W, H = page.size
    photo = page.crop((0, 0, int(W * 0.62), H))
    photo.thumbnail((1100, 1100), Image.LANCZOS)
    # every garment is its own blob here, so keep many more than a cut-out would
    import io
    from rembg import remove
    buf = io.BytesIO(); photo.save(buf, 'PNG')
    cut = Image.open(io.BytesIO(remove(buf.getvalue(), session=imglib.session()))).convert('RGBA')
    cut.putalpha(cut.getchannel('A').point(lambda v: 255 if v >= 200 else 0))
    cut, _ = imglib.keep_main_blobs(cut, rel=0.02, max_blobs=40)
    arr = np.asarray(cut.convert('RGBA')).astype(np.float64)
    keep = arr[..., 3] > 200
    lab = srgb_to_lab_np(arr[..., :3])
    L = lab[..., 0]; a = lab[..., 1]; b = lab[..., 2]
    C = np.hypot(a, b); h = np.degrees(np.arctan2(b, a)) % 360
    skin = (h >= 18) & (h <= 62) & (C >= 8) & (C <= 40) & (L >= 25) & (L <= 92)
    keep &= ~skin
    return lab[keep], cut


def cluster_colours(lab, k=14, merge=9.0, min_share=0.03):
    if len(lab) < 200:
        return []
    rng = np.random.default_rng(0)
    sample = lab[rng.choice(len(lab), size=min(len(lab), 40000), replace=False)]
    cent, labels = kmeans2(sample, k, minit='++', seed=0)
    counts = np.bincount(labels, minlength=k).astype(float)
    order = np.argsort(-counts)
    merged = []                                    # [lab, count]
    for i in order:
        if counts[i] == 0:
            continue
        c = cent[i]
        for m in merged:
            if EC.delta_e_2000(tuple(c), tuple(m[0])) <= merge:
                w = m[1] + counts[i]
                m[0] = (m[0] * m[1] + c * counts[i]) / w
                m[1] = w
                break
        else:
            merged.append([c.copy(), counts[i]])
    total = sum(m[1] for m in merged)
    out = []
    for lab_c, n in merged:
        share = n / total
        if share < min_share:
            continue
        hx = EC.lab_to_hex(tuple(lab_c))
        fam, name, L, Cc, hh, rel, nt = classify(hx)
        out.append(dict(hex=hx, lab=[round(float(v), 2) for v in lab_c], share=round(float(share), 3),
                        family=fam, name=name, L=round(L, 1), C=round(Cc, 1), h=round(hh, 1),
                        rel=round(rel, 3), neutral=nt))
    out.sort(key=lambda c: -c['share'])
    return out


def recolour(src_rgba, target_lab):
    """Keep the source's lightness detail; take the target's hue, chroma and mean L."""
    arr = np.asarray(src_rgba.convert('RGBA')).astype(np.float64)
    rgb, alpha = arr[..., :3], arr[..., 3]
    lab = srgb_to_lab_np(rgb)
    L, a, b = lab[..., 0], lab[..., 1], lab[..., 2]
    opaque = alpha > 200
    # the garment colour: the biggest cluster of opaque pixels
    sample = lab[opaque]
    rng = np.random.default_rng(1)
    sample = sample[rng.choice(len(sample), size=min(len(sample), 20000), replace=False)]
    cent, labels = kmeans2(sample, 3, minit='++', seed=0)
    src = cent[np.argmax(np.bincount(labels, minlength=3))]
    Ls, as_, bs = src
    Cs = float(np.hypot(as_, bs))
    # labels, buttons and tags are the pixels that are not the garment's colour
    dab = np.hypot(a - as_, b - bs)
    garment = opaque & (dab <= max(10.0, 0.55 * Cs)) & (L > 4) & (L < 97)
    Lt, at, bt = target_lab
    Ct = float(np.hypot(at, bt))
    ht = np.arctan2(bt, at)
    # chroma follows the source's own variation, gently, so folds stay folds
    ratio = np.clip(0.7 + 0.3 * (np.hypot(a, b) / max(Cs, 4.0)), 0.55, 1.35) if Cs >= 6 else np.ones_like(L)
    # a dark target has no room for the source's highlights: compress detail
    scale = 1.0 if Lt >= Ls else float(np.clip(Lt / max(Ls, 1), 0.45, 1.0))
    Ln = np.clip(Lt + (L - Ls) * scale, 1, 99)
    Cn = Ct * ratio
    an = Cn * np.cos(ht)
    bn = Cn * np.sin(ht)
    new = lab.copy()
    new[..., 0] = np.where(garment, Ln, L)
    new[..., 1] = np.where(garment, an, a)
    new[..., 2] = np.where(garment, bn, b)
    out = np.dstack([lab_to_srgb_np(new), alpha]).astype(np.uint8)
    return Image.fromarray(out, 'RGBA'), src, float(garment.sum() / max(1, opaque.sum()))


def slug(name):
    return name.lower().replace(' ', '-')


def main():
    B = {b['product_id']: b for b in json.load(open(CAT + '/batches.json'))}
    assets = json.load(open(CAT + '/_assets.json'))
    rows = {r['product_id']: r for r in csv.DictReader(open(CAT + '/products.csv'))}
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(CAT + '/sheets', exist_ok=True)
    variants, report, dropped = [], {}, {}
    for style, st in STYLES.items():
        if style in DROPPED:
            dropped[style] = DROPPED[style]
            print(f'{style}: dropped — {DROPPED[style]}', flush=True)
            continue
        src_row = rows[st['source']]
        src = source_cutout(st['source'], B, assets)
        lab_px, colour_cut = garment_pixels_of_colour_picture(st['colours'], B)
        colours = cluster_colours(lab_px)
        src_lab_guess = None
        made, cells = [], []
        cpath = f'/tmp/claude-0/uq/{style}-colours.png'
        colour_cut.save(cpath)
        cells.append(dict(path=cpath, label=f"{st['colours']} all colours\n" + ', '.join(c['name'] for c in colours)))
        spath = f'{OUT}/{st["source"]}-source.png'
        src.save(spath)
        cells.append(dict(path=spath, label=f"{st['source']} source (clean flat lay)"))
        seen = set()
        for c in colours:
            name = c['name']
            if name in seen:                       # two clusters with one name: keep the bigger
                continue
            seen.add(name)
            img, src_lab, share = recolour(src, c['lab'])
            src_lab_guess = src_lab
            pid = f"{st['source']}-{slug(name)}"
            path = f'{OUT}/{pid}.webp'
            img.save(path, 'WEBP', quality=88, method=5)
            # the source's own colour keeps UNIQLO's legible colour name
            d_src = EC.delta_e_2000(tuple(src_lab), tuple(c['lab']))
            cells.append(dict(path=path, label=f"{pid}\n{name} ({c['family']}) {int(c['share']*100)}%",
                              swatches=[c['hex']]))
            if d_src <= SAME_AS_SOURCE:
                dropped[pid] = f"the source's own colour (dE {d_src:.1f}): the real photo is {st['source']}"
                os.remove(path)
                continue
            if pid in DROPPED:
                dropped[pid] = DROPPED[pid]
                os.remove(path)
                continue
            legible = src_row['colour_name_text'] if d_src <= 12 else ''
            L, Cc, h = EC.lab_to_lch(tuple(c['lab']))
            variants.append(dict(
                product_id=pid, source=st['source'], style=style,
                garment_type=src_row['garment_type'], slot=src_row['slot'],
                colour=dict(hex=c['hex'], family=c['family'], name=name, share=c['share'],
                            L=round(L, 1), C=round(Cc, 1), h=round(h, 1), rel=c['rel'],
                            neutral=c['neutral']),
                colour_name_text=legible, asset_path=f'content/catalogue/variants/{pid}.webp',
                recoloured_share=round(share, 3),
                delta_e_to_source=round(d_src, 1)))
            made.append(pid)
        sheet(cells, f'{CAT}/sheets/uniqlo-{style}.jpg', cols=5, cell=230, label_h=44, swatch_h=14,
              title=f'UNIQLO {style}: all-colours picture, source, variants')
        report[style] = dict(source=st['source'], colours_picture=st['colours'],
                             colours=[(c['name'], c['share']) for c in colours], variants=made,
                             source_lab=[round(float(v), 1) for v in (src_lab_guess if src_lab_guess is not None else [0, 0, 0])])
        print(f'{style}: {len(colours)} colours -> {len(made)} variants', flush=True)
    json.dump(dict(variants=variants, report=report, dropped=dropped),
              open(CAT + '/_variants.json', 'w'), indent=1)
    print('variants kept:', len(variants), ' dropped:', len(dropped))
    for k, why in dropped.items():
        print('  dropped', k, '—', why)


if __name__ == '__main__':
    main()
