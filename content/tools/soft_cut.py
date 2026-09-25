"""Cut-outs with a soft edge, at full resolution — Part B of 24 September.

The owner hid 206 products. Read against those, the cut-out method had four
faults, and this module is the answer to each:

1. **Jagged outlines.** imglib.cutout() and flat_lays.raw_cut() thresholded
   rembg's alpha at 200 into 0/255, on a picture already shrunk to the review
   copy (≤ 1200 px, often ~500 px across the garment). Every edge became a
   staircase. Here the model runs on the screenshot itself (full resolution,
   the crop the review copy was made from), its alpha is kept soft, the edge
   colours are decontaminated against the backdrop, and the result is scaled
   down only at the end, premultiplied, so the anti-aliasing survives.
2. **Background left inside the garment** (between the legs, between an arm
   and the body): enclosed regions the model kept opaque but whose colour is
   the backdrop's are removed. Not when the garment itself is the backdrop's
   colour — a cream coat on a cream page cannot be told from the page by
   colour (the same caution as CLAUDE.md rule 6), and then nothing is punched.
3. **Thin parts lost** (handles, straps, belts): isnet-general-use keeps fine
   structure that u2net loses, and a piece that touches or overlaps the main
   one is kept whatever its size; only islands clear of it are dropped.
4. **A garment on a person**: u2net_cloth_seg separates upper-body, lower-body
   and full-body clothing, so a top, a bottom, a dress or a coat can be cut off
   the model it is worn by. Shoes, bags and accessories on a person cannot be,
   and are said to be so.

    from soft_cut import recut
    rgba, info = recut(pid)          # the product's own picture, re-cut

Nothing here writes into the catalogue; recut_hidden.py decides what to keep.
"""
import io, os, json
import numpy as np
from PIL import Image, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
CAT = ROOT + '/content/catalogue'
STUDIO = ROOT + '/studio'
MAX_OUT = 1200          # the catalogue's asset size, as before

_SESS = {}


def session(name):
    if name not in _SESS:
        from rembg import new_session
        _SESS[name] = new_session(name)
    return _SESS[name]


# ------------------------------------------------------------------ source
def _load(name, default):
    try:
        return json.load(open(CAT + '/' + name))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def source_picture(p, idx=None, review=None):
    """The full-resolution picture behind a product's picture `idx`: the
    screenshot, cut to the crop the review copy was made from (`origin`, in
    screenshot pixels), then to the panel's box where the page was split.
    Returns (PIL RGB, entry) or (None, entry) when the screenshot is missing."""
    review = review if review is not None else _load('_review_boxes.json', {})
    imgs = p.get('images') or []
    if idx is None:
        idx = p.get('image') or 0
    if idx >= len(imgs):
        return None, None
    e = imgs[idx]
    src = e.get('source')
    if not src or not os.path.exists(ROOT + '/' + src):
        return None, e
    rv = review.get(p['product_id']) or review.get(p.get('parent_id') or '') or {}
    rimgs = rv.get('images') or []
    j = e.get('panel_of', idx) or 0
    origin = (rimgs[j].get('origin') if j < len(rimgs) else None) or rv.get('origin')
    im = Image.open(ROOT + '/' + src).convert('RGB')
    if origin:
        x, y, w, h = origin[:4]
        W0, H0 = origin[4:6] if len(origin) >= 6 else im.size
        if (W0, H0) != im.size:          # the screenshot was re-exported at another size
            k = im.width / W0
            x, y, w, h = x * k, y * k, w * k, h * k
        im = im.crop((int(x), int(y), int(x + w), int(y + h)))
    pb = e.get('panel_box') or [0, 0, 1, 1]
    if pb != [0, 0, 1, 1]:
        W, H = im.size
        im = im.crop((int(pb[0] * W), int(pb[1] * H), int((pb[0] + pb[2]) * W), int((pb[1] + pb[3]) * H)))
    return im, e


# ------------------------------------------------------------------ colour
def _lab(rgb):
    """sRGB (..., 3) uint8 -> CIELAB (..., 3), D65."""
    c = rgb.astype(np.float32) / 255.0
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    M = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]], np.float32)
    xyz = c @ M.T / np.array([0.95047, 1.0, 1.08883], np.float32)
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


def backdrop(im, frac=0.04):
    """The backdrop's colour from the four corners (not a ring: a packshot is
    cropped close and a ring runs through the garment's shoulders)."""
    a = np.asarray(im.convert('RGB'))
    H, W = a.shape[:2]
    k = max(2, int(min(W, H) * frac))
    corners = np.concatenate([a[:k, :k].reshape(-1, 3), a[:k, -k:].reshape(-1, 3),
                              a[-k:, :k].reshape(-1, 3), a[-k:, -k:].reshape(-1, 3)])
    return np.median(corners, 0).astype(np.uint8), float(corners.std(0).mean())


# ------------------------------------------------------------------ masks
def model_alpha(im, model='isnet-general-use'):
    """The segmentation model's own alpha, soft, at the picture's resolution."""
    from rembg import remove
    buf = io.BytesIO()
    im.save(buf, 'PNG')
    out = Image.open(io.BytesIO(remove(buf.getvalue(), session=session(model),
                                       post_process_mask=False))).convert('RGBA')
    return np.asarray(out)[..., 3].astype(np.float32) / 255.0


def flood_alpha(im, bg, de=8.0):
    """Background by topology, not by a model: everything connected to the
    picture's border that is within `de` of the backdrop's colour. For a
    packshot on a plain page that fills the frame — the case isnet reads as
    all background (Lilysilk's cream pages, 24 Sept)."""
    from scipy import ndimage
    lab = _lab(np.asarray(im.convert('RGB')))
    blab = _lab(bg.reshape(1, 1, 3))[0, 0]
    near = np.sqrt(((lab - blab) ** 2).sum(-1)) < de
    lab_c, n = ndimage.label(near)
    border = set(np.unique(np.concatenate([lab_c[0], lab_c[-1], lab_c[:, 0], lab_c[:, -1]]))) - {0}
    back = np.isin(lab_c, list(border))
    fg = ~back
    fg = ndimage.binary_opening(fg, iterations=1)
    return np.clip(ndimage.gaussian_filter(fg.astype(np.float32), 0.7), 0, 1)


def coverage(alpha):
    return float((alpha > 0.5).mean())


def best_alpha(im, bg, noise, model):
    """isnet first; where it plainly failed (it kept almost nothing, or
    almost everything), u2net, then the border flood on a plain backdrop."""
    tried = []
    a = model_alpha(im, model)
    tried.append((model, a))
    if 0.04 <= coverage(a) <= 0.97:
        return a, model
    b = model_alpha(im, 'u2net')
    tried.append(('u2net', b))
    if 0.04 <= coverage(b) <= 0.97:
        return b, 'u2net'
    if noise < 4:
        f = flood_alpha(im, bg)
        if 0.04 <= coverage(f) <= 0.97:
            return f, 'backdrop flood'
    return tried[0][1], model


CLOTH_CLASSES = {          # u2net_cloth_seg: 1 upper body, 2 lower body, 3 full body
    'top': (1,), 'base': (1,), 'layer': (1, 3), 'bottom': (2,), 'dress': (3, 1, 2),
    'multiple': (1, 2, 3),
}


def cloth_alpha(im, slot):
    """The clothes on a person, by slot, off u2net_cloth_seg; None where the
    slot is not clothing (shoes, a bag, an accessory). The class map is read
    straight off the model and scaled NEAREST: rembg's own predict() scales the
    class indices with LANCZOS, which rings at every class boundary and draws
    one-pixel "upper body" outlines round the legs."""
    want = CLOTH_CLASSES.get(slot)
    if not want:
        return None
    from scipy import ndimage
    sess = session('u2net_cloth_seg')
    out = sess.inner_session.run(None, sess.normalize(im.convert('RGB'), (0.485, 0.456, 0.406),
                                                      (0.229, 0.224, 0.225), (768, 768)))
    pred = np.argmax(out[0], axis=1)[0].astype(np.uint8)
    m = np.isin(pred, want).astype(np.uint8) * 255
    m = np.asarray(Image.fromarray(m).resize(im.size, Image.NEAREST)) > 127
    m = ndimage.binary_opening(m, iterations=2)
    return m.astype(np.float32)


def skin_share(rgb, alpha, exclude=None, tol=15.0):
    """Share of the cut that is skin, leaving out the garment's own colour: a
    burgundy, rust or tan garment sits in the skin band, and without this a
    burgundy cami on a white page reads as someone wearing it."""
    import sys
    sys.path.insert(0, HERE)
    lab = _lab(rgb)
    solid = alpha > 0.5
    if solid.sum() < 100:
        return 0.0
    L, A, B = lab[..., 0], lab[..., 1], lab[..., 2]
    C = np.hypot(A, B)
    h = (np.degrees(np.arctan2(B, A)) + 360) % 360
    skin = (L > 25) & (L < 85) & (C > 10) & (C < 45) & (h > 25) & (h < 70)
    # the garment's own colours: its median, and any colour the caller read
    # off it (a tan bag in shade and in light is two browns, both its own)
    refs = [np.median(lab[solid], 0)] + [np.asarray(c, np.float32) for c in (exclude or [])]
    own = np.zeros(solid.shape, bool)
    for r in refs:
        own |= np.sqrt(((lab - r) ** 2).sum(-1)) < tol
    return float((skin & solid & ~own).sum() / solid.sum())


def refine_with(general, cloth):
    """The clothes mask decides WHICH pixels are garment; the general model's
    soft alpha decides the edge, which it draws far better. Where the clothes
    mask is sure and the general alpha is too, the result is the general alpha;
    skin and hair (general yes, clothes no) go."""
    from scipy import ndimage
    core = ndimage.binary_dilation(cloth > 0.5, iterations=3)
    return np.where(core, general, 0.0) * np.clip(ndimage.gaussian_filter(core.astype(np.float32), 1.2) * 1.4, 0, 1)


def solid_core(alpha, lo=0.2, depth=3):
    """A garment is opaque. On a pale page isnet sometimes returns 0.3-0.5
    across a whole dark garment (a Lilysilk cardigan came out a grey ghost),
    so everything well inside the outline — `depth` pixels in from where the
    alpha rises past `lo` — is made opaque, and only the edge keeps the
    model's soft values."""
    from scipy import ndimage
    core = ndimage.binary_erosion(alpha > lo, iterations=depth)
    core = ndimage.gaussian_filter(core.astype(np.float32), 1.0)
    return np.maximum(alpha, np.clip(core * 1.3, 0, 1))


def keep_attached(alpha, lo=0.08, near=0.02):
    """Keep the main piece and everything touching or overlapping it (a
    handle, a strap, a belt, a second shoe beside the first); drop islands
    clear of it. Connectivity is read at a LOW alpha, so a strap the model drew
    faintly still counts as attached."""
    from scipy import ndimage
    m = alpha > lo
    lab, n = ndimage.label(m)
    if n <= 1:
        return alpha, n
    sizes = ndimage.sum(m, lab, range(1, n + 1))
    big = 1 + int(np.argmax(sizes))
    H, W = alpha.shape
    grow = max(2, int(near * max(H, W)))
    zone = ndimage.binary_dilation(lab == big, iterations=grow)
    keep = np.zeros(n + 1, bool)
    keep[big] = True
    for k in range(1, n + 1):
        if k == big:
            continue
        piece = lab == k
        # attached or overlapping the main piece, or a real second piece (a pair)
        if (piece & zone).any() or sizes[k - 1] >= 0.25 * sizes[big - 1]:
            keep[k] = True
    return np.where(keep[lab], alpha, 0.0), int(keep.sum())


def punch_holes(rgb, alpha, bg, bg_noise, de=6.0, min_frac=0.002):
    """Backdrop left inside the garment: pixels the model kept but whose colour
    is the backdrop's, in pieces big enough to be a gap (between legs, arm and
    body) rather than a highlight. Nothing is punched when the garment's own
    colour is within 2·de of the backdrop — then colour cannot tell them apart.
    Returns (alpha, share of the garment removed)."""
    from scipy import ndimage
    lab = _lab(rgb)
    blab = _lab(bg.reshape(1, 1, 3))[0, 0]
    d = np.sqrt(((lab - blab) ** 2).sum(-1))
    solid = alpha > 0.5
    if solid.sum() < 200:
        return alpha, 0.0
    garment = np.median(d[solid & (d > de)]) if (solid & (d > de)).any() else 0.0
    if garment < 2 * de:
        return alpha, 0.0
    tol = de + min(6.0, bg_noise)
    cand = solid & (d < tol)
    # a gap is flat: the backdrop has no texture, a pale fabric does
    g = lab[..., 0]
    tex = np.abs(ndimage.gaussian_filter(g, 1.0) - ndimage.gaussian_filter(g, 3.0))
    cand &= tex < 1.5
    cand = ndimage.binary_opening(cand, iterations=2)
    lab_c, n = ndimage.label(cand)
    if not n:
        return alpha, 0.0
    sizes = ndimage.sum(cand, lab_c, range(1, n + 1))
    thr = min_frac * solid.sum()
    holes = np.isin(lab_c, 1 + np.nonzero(sizes >= thr)[0])
    if not holes.any():
        return alpha, 0.0
    holes = ndimage.binary_dilation(holes, iterations=1)
    soft = ndimage.gaussian_filter(holes.astype(np.float32), 0.8)
    out = alpha * (1 - np.clip(soft * 1.5, 0, 1))
    return out, float(holes.sum() / solid.sum())


def decontaminate(rgb, alpha, bg):
    """Take the backdrop's colour back out of the half-transparent edge pixels:
    F = (I - (1 - a)·B) / a. Without it a dark coat cut from a pale page wears
    a pale fringe."""
    a = alpha[..., None]
    f = rgb.astype(np.float32)
    B = bg.astype(np.float32)[None, None, :]
    edge = (a > 0.02) & (a < 0.98)
    F = np.where(edge, (f - (1 - a) * B) / np.maximum(a, 0.02), f)
    return np.clip(F, 0, 255).astype(np.uint8)


def finish(rgb, alpha, pad=0.02, max_side=MAX_OUT):
    """Crop to the garment plus a small margin and scale down premultiplied, so
    the soft edge survives and no dark or pale halo creeps in."""
    a8 = (np.clip(alpha, 0, 1) * 255 + 0.5).astype(np.uint8)
    ys, xs = np.nonzero(a8 > 3)
    if not len(xs):
        return None
    H, W = a8.shape
    m = int(pad * max(H, W))
    x0, x1 = max(0, xs.min() - m), min(W, xs.max() + 1 + m)
    y0, y1 = max(0, ys.min() - m), min(H, ys.max() + 1 + m)
    im = Image.fromarray(np.dstack([rgb, a8]).astype(np.uint8), 'RGBA').crop((x0, y0, x1, y1))
    if max(im.size) > max_side:
        k = max_side / max(im.size)
        im = im.convert('RGBa').resize((round(im.width * k), round(im.height * k)), Image.LANCZOS).convert('RGBA')
    return im


def measure(im):
    """What the flat-lay questions ask, on the new cut: pieces, edge, skin."""
    from scipy import ndimage
    a = np.asarray(im)[..., 3]
    solid = a > 128
    lab, n = ndimage.label(solid)
    sizes = ndimage.sum(solid, lab, range(1, n + 1)) if n else []
    big = max(sizes) if n else 0
    pieces = int(sum(1 for s in sizes if s >= 0.02 * big))
    # share of the outline that is anti-aliased: the old cut had none
    edge = solid ^ ndimage.binary_erosion(solid)
    ring = ndimage.binary_dilation(edge, iterations=1)
    soft = float(((a > 8) & (a < 247) & ring).sum() / max(1, ring.sum()))
    fill = float(solid.sum() / max(1, solid.size))
    return dict(pieces=pieces, soft_edge=round(soft, 3), fill=round(fill, 3), size=list(im.size))


# ------------------------------------------------------------------ the cut
def cut(im, slot='', worn=False, model='isnet-general-use'):
    """One picture -> (RGBA, info). `worn`: the picture shows the garment on a
    person, so the clothes model picks the garment and the general model draws
    its edge."""
    rgb = np.asarray(im.convert('RGB'))
    bg, noise = backdrop(im)
    alpha, used = best_alpha(im, bg, noise, model)
    sk = skin_share(rgb, alpha)
    # someone is in the picture when the cut shows skin that is not the
    # garment's own colour; the caller's word (a picture typed on-model) counts too
    worn = bool(worn) or sk > 0.04
    info = dict(model=used, backdrop='#%02X%02X%02X' % tuple(int(v) for v in bg), worn=worn,
                skin=round(sk, 3))
    if worn:
        cloth = cloth_alpha(im, slot)
        if cloth is None:
            info['worn_note'] = f'a {slot or "piece"} on a person: the clothes model cannot separate it'
        elif (cloth > 0.5).sum() > 0.01 * cloth.size:
            alpha = refine_with(alpha, cloth)
            info['cloth'] = True
        else:
            info['worn_note'] = 'the clothes model found no garment for this slot'
    alpha = np.where(alpha < 0.03, 0.0, alpha)
    alpha = solid_core(alpha)
    alpha, kept = keep_attached(alpha)
    alpha, holed = punch_holes(rgb, alpha, bg, noise)
    info.update(pieces_kept=kept, holes_removed=round(holed, 4))
    out = finish(decontaminate(rgb, alpha, bg), alpha)
    if out is None:
        return None, info
    info.update(measure(out))
    return out, info


def hard_cut_like_before(im):
    """The old method, for the before/after sheet: review-size picture, u2net,
    alpha thresholded at 200."""
    work = im.copy()
    work.thumbnail((1200, 1200), Image.LANCZOS)
    from rembg import remove
    buf = io.BytesIO()
    work.save(buf, 'PNG')
    out = Image.open(io.BytesIO(remove(buf.getvalue(), session=session('u2net')))).convert('RGBA')
    out.putalpha(out.getchannel('A').point(lambda v: 255 if v >= 200 else 0))
    bb = out.getbbox()
    return out.crop(bb) if bb else out
