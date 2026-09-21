"""Render a board from a spec, to style-spec.md part B4 and B5.

A board is: the inspiration image (version A) or a palette card (version B) on
the left, the outfit on the right in body order, a swatch strip along the
bottom carrying only colours the pieces actually have, and the owner's words at
the top. Tiles share one border and corner style with the inspiration image and
sit on a grid; cut-outs sit free, overlap, and cast a shadow shaped by their own
alpha. Nothing is drawn behind a cut-out.
"""
import sys, os, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(HERE, '..', 'boards', 'fonts')
ROOT = '/home/user/relatively-normal'

GROUND = (243, 239, 231)
KEYLINE = (214, 205, 191)
INK = (34, 31, 28)
BORDER = 7                      # the one border: white mat, thin warm keyline
RADIUS = 0                      # square corners; a rounded corner reads as a UI card


def font(name, size):
    return ImageFont.truetype(os.path.join(FONTS, name), size)


def serif(size):
    return font('EBGaramond-SemiBold.ttf', size)


def sans(size, bold=False):
    return font('Inter-SemiBold.ttf' if bold else 'Inter-Regular.ttf', size)


# ------------------------------------------------------------------ placement
def cover(im, box):
    """Fill the box, crop the overflow — for bordered tiles."""
    w, h = box[2] - box[0], box[3] - box[1]
    r = max(w / im.width, h / im.height)
    im = im.resize((max(1, round(im.width * r)), max(1, round(im.height * r))), Image.LANCZOS)
    x = (im.width - w) // 2
    y = int((im.height - h) * 0.42)             # bias up: garments sit high
    return im.crop((x, max(0, y), x + w, max(0, y) + h))


def contain(im, box, scale=1.0):
    w, h = (box[2] - box[0]) * scale, (box[3] - box[1]) * scale
    r = min(w / im.width, h / im.height)
    return im.resize((max(1, round(im.width * r)), max(1, round(im.height * r))), Image.LANCZOS)


def framed(page, im, box):
    """A tile: white mat, thin warm keyline, square corners — the same frame the
    inspiration image gets, so the two read as one family."""
    d = ImageDraw.Draw(page)
    d.rectangle(box, fill=(255, 255, 255))
    inner = (box[0] + BORDER, box[1] + BORDER, box[2] - BORDER, box[3] - BORDER)
    page.paste(cover(im.convert('RGB'), inner), (inner[0], inner[1]))
    d.rectangle(box, outline=KEYLINE, width=1)


def drop(page, im, xy, blur=14, alpha=52, off=(7, 10)):
    """Shadow from the alpha shape only — never a rectangle."""
    a = im.getchannel('A').point(lambda v: min(255, v * 2))
    sh = Image.new('RGBA', im.size, (60, 52, 44, 0))
    sh.putalpha(a.point(lambda v: v * alpha // 255))
    sh = sh.filter(ImageFilter.GaussianBlur(blur))
    page.alpha_composite(sh, (xy[0] + off[0], xy[1] + off[1]))
    page.alpha_composite(im, xy)


# --------------------------------------------------------------------- pieces
# right-hand zone, normalised boxes, loose body order
SLOTBOX = {
    'layer':     (0.00, 0.00, 0.58, 0.46),
    'top':       (0.54, 0.02, 1.00, 0.34),
    'dress':     (0.00, 0.00, 0.58, 0.60),
    'bottom':    (0.02, 0.42, 0.56, 0.86),
    'bag':       (0.60, 0.36, 1.00, 0.64),
    'shoes':     (0.52, 0.66, 0.86, 0.88),
    'accessory': (0.80, 0.62, 1.00, 0.82),
    'accessory2': (0.00, 0.80, 0.30, 1.00),
    'base':      (0.60, 0.36, 1.00, 0.62),
    'multiple':  (0.58, 0.36, 1.00, 0.68),
}
ORDER = ['layer', 'dress', 'top', 'bottom', 'bag', 'base', 'multiple', 'shoes',
         'accessory', 'accessory2']


def palette_card(size, swatches):
    """Version B: the palette in place of the photograph."""
    w, h = size
    im = Image.new('RGB', (w, h), (255, 255, 255))
    d = ImageDraw.Draw(im)
    n = max(1, len(swatches))
    y = 0
    for i, s in enumerate(swatches):
        y1 = round(h * (i + 1) / n)
        d.rectangle([0, y, w, y1], fill='#' + s['hex'])
        y = y1
    return im


def strip(page, box, swatches, show_hex=False):
    """Only colours the pieces carry, dominant -> accent, widths by share."""
    x0, y0, x1, y1 = box
    tot = sum(s.get('share', 1) for s in swatches) or 1
    x = x0
    d = ImageDraw.Draw(page)
    for s in swatches:
        w = round((x1 - x0) * s.get('share', 1) / tot)
        d.rectangle([x, y0, x + w - 2, y1], fill='#' + s['hex'])
        if show_hex:
            d.text((x, y1 + 6), s['name'], font=sans(15), fill=INK)
        x += w


def render(spec, version='a', size=(1080, 1350), labels=False, out=None):
    W, H = size
    page = Image.new('RGBA', (W, H), GROUND + (255,))
    d = ImageDraw.Draw(page)
    M = round(W * 0.055)
    y = M

    d.text((M, y), spec['title'], font=serif(round(W * 0.052)), fill=INK)
    y += round(W * 0.062)
    if spec.get('line'):
        d.text((M, y), spec['line'], font=sans(round(W * 0.0195)), fill=(92, 84, 76))
        y += round(W * 0.036)

    strip_h = round(W * 0.026)
    strip_y = H - M - strip_h - (26 if labels else 0)
    main = (M, y + round(W * 0.012), W - M, strip_y - round(W * 0.030))
    mw, mh = main[2] - main[0], main[3] - main[1]

    lw = round(mw * 0.40)
    left = (main[0], main[1], main[0] + lw, main[3])
    if version == 'a':
        with Image.open(ROOT + '/' + spec['inspiration']) as im:
            framed(page, im.copy(), left)
    else:
        card = palette_card((left[2] - left[0] - 2 * BORDER, left[3] - left[1] - 2 * BORDER),
                            spec['swatches'])
        d.rectangle(left, fill=(255, 255, 255))
        page.paste(card, (left[0] + BORDER, left[1] + BORDER))
        d.rectangle(left, outline=KEYLINE, width=1)

    zx0 = left[2] + round(mw * 0.045)
    zone = (zx0, main[1], main[2], main[3])
    zw, zh = zone[2] - zone[0], zone[3] - zone[1]

    used, marks = set(), []
    for p in sorted(spec['pieces'], key=lambda p: ORDER.index(p['slot'])
                    if p['slot'] in ORDER else 99):
        slot = p['slot']
        if slot in used and slot == 'accessory':
            slot = 'accessory2'
        used.add(slot)
        bx = SLOTBOX.get(slot, SLOTBOX['multiple'])
        box = (zone[0] + round(bx[0] * zw), zone[1] + round(bx[1] * zh),
               zone[0] + round(bx[2] * zw), zone[1] + round(bx[3] * zh))
        im = Image.open(ROOT + '/' + p['asset_path'])
        if p['asset_type'].startswith('cutout'):
            im = im.convert('RGBA')
            im = contain(im, box, scale=p.get('scale', 1.12))
            xy = ((box[0] + box[2] - im.width) // 2, (box[1] + box[3] - im.height) // 2)
            drop(page, im, xy)
            marks.append((xy[0] + im.width - 16, xy[1] + 8, p))
        else:
            framed(page, im, box)
            marks.append((box[2] - 16, box[1] + 8, p))
        im.close()

    strip(page, (main[0], strip_y, main[2], strip_y + strip_h), spec['swatches'],
          show_hex=False)

    if labels:
        for i, (x, yy, p) in enumerate(marks, 1):
            r = 14
            d.ellipse([x - r, yy, x + r, yy + 2 * r], fill=(255, 255, 255), outline=KEYLINE)
            t = str(i)
            tw = d.textlength(t, font=sans(16, True))
            d.text((x - tw / 2, yy + r - 10), t, font=sans(16, True), fill=INK)

    rgb = page.convert('RGB')
    if out:
        q = 92
        while True:
            rgb.save(out, 'JPEG', quality=q, optimize=True, progressive=True)
            if os.path.getsize(out) < 1_000_000 or q <= 70:
                break
            q -= 6
    return rgb, [p for _, _, p in marks]


if __name__ == '__main__':
    spec = json.load(open(sys.argv[1]))
    render(spec, version=sys.argv[2], out=sys.argv[3],
           size=tuple(json.loads(sys.argv[4])) if len(sys.argv) > 4 else (1080, 1350),
           labels=len(sys.argv) > 5)
