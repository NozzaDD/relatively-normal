"""Per-style variant sheets: the source flat lay and every colourway made from it.

The first sheets were a plain grid: the source, a cell of numbered swatch
dots, then the variants in any order, so a variant could not be checked
against the swatch it was made from without counting. Both layouts here put
each variant next to its own swatch, with every swatch drawn the same size,
and print under it the dE2000 between the swatch and the variant's measured
garment colour — how close the recolour (or the real photo) came.

  rows    source large on the left; then one row per variant:
          swatch | variant | number, real or simulated, dE
  grid    source large on the left; the swatches in the page's own order
          across the top of each column, each variant straight under its
          swatch, dE under the variant

  python3 content/tools/variant_sheets.py --choose     # both layouts, two styles, one sheet
  python3 content/tools/variant_sheets.py [rows|grid]  # every style, into sheets/ (rows is the chosen one)

Reads _variants.json and _colourway_variants.json; draws nothing it has not
measured.
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from PIL import Image, ImageDraw
from contact_sheet import _font, GREY
from engine import colour as EC

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CAT = ROOT + '/content/catalogue'
SW = 84          # every swatch, every row, this size
INK = (22, 22, 22)


def measured_de(v):
    """dE2000 between the swatch and the variant's own garment colour."""
    if v.get('swatch_to_variant_de') is not None:
        return v['swatch_to_variant_de']
    from uniqlo_variants import garment_lab
    lab, _ = garment_lab(Image.open(ROOT + '/' + v['asset_path']))
    sw = EC.hex_to_lab(v['swatch_hex']) if hasattr(EC, 'hex_to_lab') else EC.srgb_to_lab(
        tuple(int(v['swatch_hex'][i:i + 2], 16) for i in (0, 2, 4)))
    v['swatch_to_variant_de'] = round(EC.delta_e_2000(tuple(float(x) for x in lab), tuple(sw)), 1)
    return v['swatch_to_variant_de']


def styles(only=None):
    """[(title, source_path, source_hex, [variant rec]), ...] from both variant files."""
    out = []
    for fn, shop in (('_variants.json', 'UNIQLO'), ('_colourway_variants.json', None)):
        if only and fn != only:
            continue
        p = CAT + '/' + fn
        if not os.path.exists(p):
            continue
        d = json.load(open(p))
        by = {}
        for v in d['variants']:
            by.setdefault(v['style'], []).append(v)
        pages = {}
        if shop == 'UNIQLO' and os.path.exists(CAT + '/_uniqlo_pages.json'):
            pages = json.load(open(CAT + '/_uniqlo_pages.json'))
        for style, rep in d['report'].items():
            vs = sorted(by.get(style, []), key=lambda v: v['swatch'])
            for v in vs:
                measured_de(v)
            if not rep.get('own_hex') and pages.get(rep.get('source_image')):
                sws = pages[rep['source_image']]['swatches']
                o = (rep.get('own_swatch') or 0) - 1
                if 0 <= o < len(sws):
                    rep['own_hex'] = sws[o]['hex']
            title = f"{rep.get('shop_label') or shop} {style}"
            out.append(dict(title=title, style=style, source=ROOT + '/' + rep['source_cut'],
                            source_id=rep['source'], own=rep.get('own_swatch'),
                            own_hex=rep.get('own_hex', ''), variants=vs,
                            slug=rep.get('sheet') or ''))
    return out


def fit(path, w, h):
    im = Image.open(path).convert('RGBA')
    im.thumbnail((w, h), Image.LANCZOS)
    bg = Image.new('RGBA', (w, h), GREY + (255,))
    bg.alpha_composite(im, ((w - im.width) // 2, (h - im.height) // 2))
    return bg.convert('RGB')


def de_label(v):
    d = v.get('swatch_to_variant_de')
    return f'dE {d:.1f}' if d is not None else 'dE -'


def kind(v):
    return 'real photo' if v.get('real') else 'simulated'


def swatch(d, x, y, v, im=None):
    """A fabric swatch as its colour; a photo swatch as the thumbnail itself,
    at the same size, since the thumbnail is what the variant was cut from."""
    if v.get('tile') and v.get('real_from') and im is not None:
        t = Image.open(ROOT + '/' + v['real_from']).convert('RGB').crop(tuple(v['tile']))
        t.thumbnail((SW, SW), Image.LANCZOS)
        bg = Image.new('RGB', (SW, SW), (235, 235, 235))
        bg.paste(t, ((SW - t.width) // 2, (SW - t.height) // 2))
        im.paste(bg, (x, y))
        d.rectangle([x, y, x + SW - 1, y + SW - 1], outline=(60, 60, 60))
        return
    d.rectangle([x, y, x + SW - 1, y + SW - 1], fill='#' + v['swatch_hex'], outline=(60, 60, 60))


def rows_layout(st, width=1180):
    """Source left; one row per variant: swatch | variant | text."""
    f, fb = _font(15), _font(17, True)
    src_w, row_h, var_w = 380, SW + 56, 120
    col_w = SW + 12 + var_w + 12 + 150
    cols = max(1, (width - src_w - 30) // col_w)
    n = len(st['variants'])
    per_col = max(1, -(-n // cols))
    H = max(60 + src_w * 5 // 4 + 60, 60 + per_col * row_h + 20)
    im = Image.new('RGB', (width, H), GREY)
    d = ImageDraw.Draw(im)
    d.text((12, 12), st['title'], font=_font(22, True), fill=INK)
    im.paste(fit(st['source'], src_w, src_w * 5 // 4), (12, 52))
    y0 = 52 + src_w * 5 // 4 + 6
    d.text((12, y0), f"SOURCE {st['source_id']}", font=fb, fill=INK)
    if st['own_hex']:
        d.rectangle([12, y0 + 24, 12 + SW - 1, y0 + 24 + SW // 3], fill='#' + st['own_hex'])
        d.text((20 + SW, y0 + 26), f"its own swatch, #{st['own']}", font=f, fill=INK)
    for i, v in enumerate(st['variants']):
        c, r = divmod(i, per_col)
        x = src_w + 30 + c * col_w
        y = 52 + r * row_h
        swatch(d, x, y, v, im)
        im.paste(fit(ROOT + '/' + v['asset_path'], var_w, row_h - 12), (x + SW + 12, y))
        tx = x + SW + 12 + var_w + 12
        d.text((tx, y + 4), f"#{v['swatch']}", font=fb, fill=INK)
        d.text((tx, y + 28), kind(v), font=f, fill=INK)
        d.text((tx, y + 48), de_label(v), font=f, fill=INK)
        if v.get('colour_name_text'):
            d.text((tx, y + 66), v['colour_name_text'][:18], font=f, fill=INK)
    return im


def grid_layout(st, width=1180):
    """Source left; swatches across the top of each column in page order,
    each variant straight under its swatch."""
    f, fb = _font(14), _font(15, True)
    src_w, cell_w, var_h = 330, 118, 150
    cols = max(1, (width - src_w - 30) // cell_w)
    items = st['variants']
    rows = max(1, -(-len(items) // cols))
    cell_h = SW + 6 + var_h + 42
    H = max(52 + src_w * 5 // 4 + 60, 52 + rows * cell_h + 10)
    im = Image.new('RGB', (width, H), GREY)
    d = ImageDraw.Draw(im)
    d.text((12, 12), st['title'], font=_font(22, True), fill=INK)
    im.paste(fit(st['source'], src_w, src_w * 5 // 4), (12, 52))
    y0 = 52 + src_w * 5 // 4 + 6
    d.text((12, y0), f"SOURCE {st['source_id']}", font=fb, fill=INK)
    if st['own_hex']:
        d.rectangle([12, y0 + 22, 12 + SW - 1, y0 + 22 + SW // 3], fill='#' + st['own_hex'])
        d.text((20 + SW, y0 + 24), f"its own swatch, #{st['own']}", font=f, fill=INK)
    for i, v in enumerate(items):
        r, c = divmod(i, cols)
        x = src_w + 30 + c * cell_w
        y = 52 + r * cell_h
        swatch(d, x + (cell_w - 8 - SW) // 2, y, v, im)
        d.text((x + 2, y + 2), str(v['swatch']), font=fb, fill=(255, 255, 255))
        im.paste(fit(ROOT + '/' + v['asset_path'], cell_w - 8, var_h), (x, y + SW + 6))
        ty = y + SW + 6 + var_h + 2
        d.text((x + 2, ty), de_label(v), font=f, fill=INK)
        d.text((x + 2, ty + 18), kind(v), font=f, fill=INK)
    return im


LAYOUTS = dict(rows=rows_layout, grid=grid_layout)


def stack(ims, gap=24, title=''):
    W = max(i.width for i in ims)
    H = sum(i.height for i in ims) + gap * (len(ims) - 1) + (56 if title else 0)
    out = Image.new('RGB', (W, H), (96, 96, 96))
    d = ImageDraw.Draw(out)
    y = 0
    if title:
        d.text((12, 14), title, font=_font(26, True), fill=(250, 250, 250))
        y = 56
    for i in ims:
        out.paste(i, (0, y))
        y += i.height + gap
    return out


def main():
    a = sys.argv[1:]
    sts = styles()
    if not sts:
        print('no variants yet')
        return
    if '--choose' in a:
        names = [x for x in a if x != '--choose'] or [sts[0]['style']]
        pick = [s for s in sts if s['style'] in names] or sts[:2]
        ims = []
        for s in pick:
            for k in ('rows', 'grid'):
                one = LAYOUTS[k](s)
                lab = Image.new('RGB', (one.width, 40), (60, 60, 60))
                ImageDraw.Draw(lab).text((12, 8), f'Layout {"A — rows" if k == "rows" else "B — grid under swatches"}',
                                         font=_font(22, True), fill=(250, 250, 250))
                ims += [lab, one]
        out = CAT + '/sheets/variant-layouts-choose.jpg'
        stack(ims, gap=6, title='Two layouts for the variant sheets — pick A or B').save(out, 'JPEG', quality=85)
        print(out)
        return
    write(a[0] if a else 'rows')


def write(k='rows', only=None):
    """Every style's sheet in layout k. The owner chose A, rows, on 23 September."""
    sts = styles(only)
    for s in sts:
        slug = s['slug'] or ('uniqlo-' + __import__('uniqlo_variants').slug(s['style']))
        LAYOUTS[k](s).save(f'{CAT}/sheets/{slug}.jpg', 'JPEG', quality=84)
    print(len(sts), 'variant sheets,', k)


if __name__ == '__main__':
    main()
