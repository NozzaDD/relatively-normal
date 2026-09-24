"""Re-render the four made visuals from PR #5 with the owner's words only.

The first versions printed hexes under every chip and a caption reading
"hue gap 27.1 degrees, delta relative chroma 0.12, delta L* 42.3". That is the
engine talking. A reader does not need the arithmetic to see that a tan dress
steps forward out of green grass, and nothing on a published image should look
like a debug print.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from PIL import Image, ImageDraw
import make_boards as MB
import inspiration_colours as I

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = ROOT + '/content/boards/v2'
W, H = 1080, 1350
GROUND = MB.GROUND
INK = MB.INK


def wrap(d, text, font, width):
    out, line = [], ''
    for w in text.split():
        t = (line + ' ' + w).strip()
        if d.textlength(t, font=font) <= width:
            line = t
        else:
            out.append(line); line = w
    if line:
        out.append(line)
    return out


def frame(title, line):
    im = Image.new('RGB', (W, H), GROUND)
    d = ImageDraw.Draw(im)
    d.rectangle([18, 18, W - 19, H - 19], outline=(224, 216, 202), width=1)
    d.text((64, 62), title, font=MB.serif(46), fill=INK)
    d.text((64, 118), line, font=MB.sans(22), fill=(112, 104, 95))
    return im, d


def card(name, title, line, rows, caption):
    """rows: [(hex, label)] — a colour and what it is, no code."""
    im, d = frame(title, line)
    top, bot = 168, H - 230
    gap = 12
    hh = (bot - top - gap * (len(rows) - 1)) // len(rows)
    y = top
    for hx, label in rows:
        d.rectangle([64, y, W - 64, y + hh], fill='#' + hx)
        L = MB.C_LUM(hx) if hasattr(MB, 'C_LUM') else None
        r, g, b = (int(hx[i:i + 2], 16) for i in (0, 2, 4))
        ink = (255, 255, 255) if (0.299 * r + 0.587 * g + 0.114 * b) < 150 else (30, 26, 22)
        d.text((90, y + 26), label, font=MB.sans(26, True), fill=ink)
        y += hh + gap
    yy = bot + 34
    for ln in wrap(d, caption, MB.sans(22), W - 128):
        d.text((64, yy), ln, font=MB.sans(22), fill=(92, 84, 76))
        yy += 30
    im.save(f'{OUT}/note-{name}.jpg', 'JPEG', quality=88, optimize=True, progressive=True)


def photo(name, title, line, src, hexes, caption):
    im, d = frame(title, line)
    with Image.open(src) as p0:
        p = I.photo_only(p0.convert('RGB'))
    box = (64, 168, W - 64, H - 300)
    p = MB.cover(p, box)
    d.rectangle([box[0] - 7, box[1] - 7, box[2] + 6, box[3] + 6], fill=(255, 255, 255))
    im.paste(p, (box[0], box[1]))
    d.rectangle([box[0] - 7, box[1] - 7, box[2] + 6, box[3] + 6], outline=MB.KEYLINE, width=1)
    sy = box[3] + 34
    w = (W - 128) // len(hexes)
    for i, hx in enumerate(hexes):
        d.rectangle([64 + i * w, sy, 64 + (i + 1) * w - 8, sy + 54], fill='#' + hx)
    yy = sy + 82
    for ln in wrap(d, caption, MB.sans(22), W - 128):
        d.text((64, yy), ln, font=MB.sans(22), fill=(92, 84, 76))
        yy += 30
    im.save(f'{OUT}/note-{name}.jpg', 'JPEG', quality=88, optimize=True, progressive=True)


def main():
    card('a-four-right-pieces', 'Four colours. Every one of them fine.',
         'And no valid pair between any two of them.',
         [('402427', 'oxblood wool gabardine'), ('C6BBA9', 'oatmeal fine knit'),
          ('8C7351', 'taupe cotton corduroy'), ('3A2A20', 'dark brown leather')],
         'Four colours sampled from four product photographs. Each one is good on its own. '
         'Put any two of them together and nothing happens.')
    card('c-denim-is-not-a-colour', 'Denim is not a colour.',
         'Which is why a colour test keeps getting it wrong.',
         [('2B3446', 'dark indigo, declared as denim'), ('5E6F8C', 'a mid blue that is not denim'),
          ('2C5A66', 'petrol, a green-leaning blue'), ('1F3A93', 'a bright navy')],
         'Two of these are the same blue to any test drawn around colour. One of them is denim. '
         'The only thing that separates them is what the cloth is made of, so it has to be '
         'declared rather than guessed.')
    photo('b-tan-on-green', 'Tan on green should be camouflage.',
          "It isn't, and it is not an accident.",
          ROOT + '/content/swipe/visuals/IMG_0066.png',
          ['D9A46E', '7C7144', '494520', 'A8A69A', '121409'],
          'The dress and the grass are near neighbours and about equally strong in colour. '
          'What separates them is light: the dress is far paler than anything behind it, so it '
          'steps forward instead of disappearing.')
    photo('d-two-reds-one-step', 'Two reds, one step apart.',
          'When is a rule worth ignoring?',
          ROOT + '/content/swipe/fashion shows ss27/IMG_0843.png',
          ['953E2D', '66261D', '291612', 'D4CAC0', '7B6D6D'],
          'Rust on rust with a deeper red beside it. The two reds sit closer together than you '
          'would expect to work. It holds because the knit, the wrap and the leather each catch '
          'the light in a different way, and no colour test can see that.')
    print('re-rendered four note visuals without engine numbers')


if __name__ == '__main__':
    main()
