"""Contact sheets on mid-grey, for checking many images by eye in one look.

Mid-grey because a white sheet makes every pale garment look darker than it is
and a black one does the reverse; 50% grey is the one ground that does not push
the reading either way. Used for the colour-name check (step 5), the inspiration
pass (step 6) and the per-slot sheets (step 10).
"""
import os, sys
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(HERE, '..', 'boards', 'fonts')
GREY = (128, 128, 128)


def _font(size, bold=False):
    for n in (('Inter-SemiBold.ttf' if bold else 'Inter-Regular.ttf'),
              'Inter-Regular.ttf'):
        p = os.path.join(FONTS, n)
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def sheet(cells, out, cols=6, cell=300, label_h=54, swatch_h=0, title=''):
    """cells: [{'path', 'label', 'swatches': [hex,...]}] -> one JPEG."""
    rows = (len(cells) + cols - 1) // cols
    pad = 10
    th = 46 if title else 0
    W = cols * (cell + pad) + pad
    H = th + rows * (cell + label_h + swatch_h + pad) + pad
    im = Image.new('RGB', (W, H), GREY)
    d = ImageDraw.Draw(im)
    if title:
        d.text((pad, 12), title, font=_font(24, True), fill=(20, 20, 20))
    f = _font(15)
    for i, c in enumerate(cells):
        r, k = divmod(i, cols)
        x = pad + k * (cell + pad)
        y = th + pad + r * (cell + label_h + swatch_h + pad)
        try:
            with Image.open(c['path']) as t0:
                t = t0.convert('RGBA')
                t.thumbnail((cell, cell), Image.LANCZOS)
                bg = Image.new('RGBA', (cell, cell), GREY + (255,))
                bg.alpha_composite(t, ((cell - t.width) // 2, (cell - t.height) // 2))
                im.paste(bg.convert('RGB'), (x, y))
        except Exception as e:
            d.text((x + 6, y + 6), 'missing', font=f, fill=(200, 60, 60))
        yy = y + cell
        if swatch_h and c.get('swatches'):
            w = cell // max(1, len(c['swatches']))
            for j, hx in enumerate(c['swatches']):
                d.rectangle([x + j * w, yy, x + (j + 1) * w - 1, yy + swatch_h - 1],
                            fill='#' + hx.lstrip('#'))
            yy += swatch_h
        for j, ln in enumerate((c.get('label') or '').split('\n')[:3]):
            d.text((x + 2, yy + 2 + j * 17), ln[:46], font=f, fill=(25, 25, 25))
    im.save(out, 'JPEG', quality=82, optimize=True)
    return out
