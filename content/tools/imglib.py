"""Shared image helpers for the swipe library.

Pure helpers over Pillow + the engine's colour module. Nothing here writes to
content/swipe/ — originals are never moved, renamed, deleted or re-encoded.
"""
import math, io, os, sys
from PIL import Image, ImageFilter
Image.MAX_IMAGE_PIXELS = None
_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(_HERE))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from engine import colour as C          # noqa: E402


# ------------------------------------------------------------------ chrome
def _row_stats(row):
    labs = [C.srgb_to_lab(p) for p in row]
    Ls = [l[0] for l in labs]
    m = sum(Ls) / len(Ls)
    var = sum((x - m) ** 2 for x in Ls) / len(Ls)
    ch = sum(math.hypot(l[1], l[2]) for l in labs) / len(labs)
    return m, var, ch


def is_chrome_row(row):
    m, var, ch = _row_stats(row)
    return var < 30 and ch < 9 and (m < 28 or m > 93)


def trim_chrome(im):
    """Bounding box of the page once iOS/Safari chrome is trimmed off."""
    w, h = im.size
    px = im.load()
    step = max(1, w // 40)
    row = lambda y: [px[x, y] for x in range(0, w, step)]          # noqa: E731
    t = 0
    while t < h * 0.25 and is_chrome_row(row(t)):
        t += 1
    b = h - 1
    while b > h * 0.72 and is_chrome_row(row(b)):
        b -= 1
    col = lambda x: [px[x, y] for y in range(t, b + 1, max(1, (b - t) // 40 or 1))]  # noqa: E731
    l = 0
    while l < w * 0.2 and is_chrome_row(col(l)):
        l += 1
    r = w - 1
    while r > w * 0.8 and is_chrome_row(col(r)):
        r -= 1
    return (l, t, r + 1, b + 1)


def photo_box(im, dark=26, thresh=0.10):
    """Grow out from the centre to the edge of the bright block — strips an
    in-page black lightbox AND the bright browser chrome outside it."""
    g = im.convert('L')
    w, h = g.size
    px = g.load()
    sx = max(1, w // 260)
    sy = max(1, h // 260)
    rb = lambda y: sum(1 for x in range(0, w, sx) if px[x, y] > dark) / len(range(0, w, sx))   # noqa: E731
    cb = lambda x: sum(1 for y in range(0, h, sy) if px[x, y] > dark) / len(range(0, h, sy))   # noqa: E731
    cy, cx = h // 2, w // 2
    t = cy
    while t > 0 and rb(t - 1) >= thresh:
        t -= 1
    b = cy
    while b < h - 1 and rb(b + 1) >= thresh:
        b += 1
    l = cx
    while l > 0 and cb(l - 1) >= thresh:
        l -= 1
    r = cx
    while r < w - 1 and cb(r + 1) >= thresh:
        r += 1
    return (l, t, r + 1, b + 1)


# ------------------------------------------------------------------ hashing
def dhash(im, s=8):
    g = im.convert('L').resize((s + 1, s), Image.LANCZOS)
    px = list(g.getdata())
    bits = 0
    for y in range(s):
        for x in range(s):
            bits = (bits << 1) | (1 if px[y * (s + 1) + x] < px[y * (s + 1) + x + 1] else 0)
    return bits


def ham(a, b):
    return bin(a ^ b).count('1')


# ------------------------------------------------------------------ colour
# A skin band wide enough to catch most skin. It overlaps genuinely warm
# garment colours (rose, salmon, tan), so callers record how much was masked
# rather than trusting the mask silently — CLAUDE.md hard rule 6.
def is_skin(L, ch, h):
    return (18 <= h <= 62) and (8 <= ch <= 40) and (25 <= L <= 92)


def lch(hex_str):
    L, Cc, h = C.lab_to_lch(C.hex_to_lab(hex_str))
    return L, Cc, h, C.relative_chroma(L, Cc, h)


def is_neutral(rel):
    return rel <= 0.15          # combinations.md §5


def white_balance(im, ref_rgb, strength=1.0):
    """Scale channels so `ref_rgb` (the studio backdrop) becomes neutral."""
    r, g, b = ref_rgb
    m = (r + g + b) / 3.0
    if min(r, g, b) < 8:
        return im
    fr, fg, fb = m / r, m / g, m / b
    fr = 1 + (fr - 1) * strength
    fg = 1 + (fg - 1) * strength
    fb = 1 + (fb - 1) * strength
    return im.point([min(255, int(i * fr)) for i in range(256)] +
                    [min(255, int(i * fg)) for i in range(256)] +
                    [min(255, int(i * fb)) for i in range(256)])


def backdrop_rgb(im, frac=0.06):
    """Modal colour of the outer frame — the studio backdrop on a packshot."""
    from collections import Counter
    w, h = im.size
    px = im.load()
    bw, bh = max(2, int(w * frac)), max(2, int(h * frac))
    samp = []
    for y in range(0, h, max(1, h // 120)):
        for x in list(range(0, bw)) + list(range(w - bw, w)):
            samp.append(px[x, y])
    for x in range(0, w, max(1, w // 120)):
        for y in list(range(0, bh)) + list(range(h - bh, h)):
            samp.append(px[x, y])
    q = Counter((r // 8, g // 8, b // 8) for r, g, b in samp)
    (r, g, b), _ = q.most_common(1)[0]
    return (r * 8 + 4, g * 8 + 4, b * 8 + 4)


# ------------------------------------------------------------------ cut-out
_SESSION = None


def session():
    global _SESSION
    if _SESSION is None:
        from rembg import new_session
        _SESSION = new_session('u2net')
    return _SESSION


def keep_main_blobs(im, rel=0.06, max_blobs=8):
    """Drop disconnected alpha islands far smaller than the biggest one.

    `rel` is deliberately low: a second shoe, a strap or a belt is a small but
    real component, and an aggressive filter deletes exactly those.
    """
    w, h = im.size
    a = im.getchannel('A').load()
    lab = [[0] * w for _ in range(h)]
    sizes = {}
    nxt = 0
    for y in range(h):
        for x in range(w):
            if a[x, y] < 128 or lab[y][x]:
                continue
            nxt += 1
            n = 0
            stack = [(x, y)]
            lab[y][x] = nxt
            while stack:
                cx, cy = stack.pop()
                n += 1
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ux, uy = cx + dx, cy + dy
                    if 0 <= ux < w and 0 <= uy < h and not lab[uy][ux] and a[ux, uy] >= 128:
                        lab[uy][ux] = nxt
                        stack.append((ux, uy))
            sizes[nxt] = n
    if not sizes:
        return im, 0
    big = max(sizes.values())
    keep = {k for k, v in sorted(sizes.items(), key=lambda kv: -kv[1])[:max_blobs] if v >= rel * big}
    out = im.copy()
    px = out.load()
    for y in range(h):
        for x in range(w):
            if a[x, y] >= 128 and lab[y][x] not in keep:
                r, g, b, _ = px[x, y]
                px[x, y] = (r, g, b, 0)
    return out, len(keep)


def cutout(im, max_side=1200, alpha_cut=200, blob_rel=0.06):
    """rembg cut-out of a PIL RGB image, alpha hard-thresholded and tidied."""
    from rembg import remove
    work = im.copy()
    work.thumbnail((max_side, max_side), Image.LANCZOS)
    buf = io.BytesIO()
    work.save(buf, 'PNG')
    out = Image.open(io.BytesIO(remove(buf.getvalue(), session=session()))).convert('RGBA')
    a = out.getchannel('A').point(lambda v: 255 if v >= alpha_cut else 0)
    out.putalpha(a)
    out, nblobs = keep_main_blobs(out, rel=blob_rel)
    bb = out.getbbox()
    if bb:
        out = out.crop(bb)
    return out, nblobs
