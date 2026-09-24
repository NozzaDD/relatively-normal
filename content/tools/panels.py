"""Split a product-page screenshot into its separate photo panels.

A shop's product page often stacks two or three photographs: the flat packshot,
then the same garment on a model, sometimes a fabric close-up. The cutter saw
one picture and took the lot, so a cut-out came out as the garment with a small
figure standing under it, and a perfectly good flat lay was sent to Review.

The split is deliberately timid. A gutter is a run of rows (or columns) that is
almost entirely the page's own backdrop; a panel is what lies between two
gutters. Where that does not give a clean answer — panels too small, too many,
too unequal — the screenshot is left whole and the reason is recorded, because
a wrong split costs more than no split.

  python3 content/tools/panels.py [--limit N] [--all]

Only new or changed products are looked at (incremental.py); --all (or --redo)
looks at every one again, reviewed ones included.

Writes content/catalogue/_panels.json and one JPEG per panel into
content/catalogue/review/. The originals are never touched, and the whole
screenshot's own review copy stays exactly where it is.
"""
import os, sys, re, csv, json, argparse, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from PIL import Image
import imglib
import flat_lays as FL
import incremental as INC

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CAT = ROOT + '/content/catalogue'
OUT = CAT + '/review'
PAN = CAT + '/_panels.json'

SMALL = 320              # the page is measured at this width
GUTTER_SPREAD = 42       # a gutter line is this flat, 5th to 95th percentile
GUTTER_LUM = 198         # ...and this light
GUTTER_MIN = 0.012       # ...and a gutter is this deep, as a share of the side
QUIET_LUM = 120          # a line with no content in it is at least this light
MARGIN = 0.10            # the strip down each side where the page shows through
TONE_STEP = 6            # two backdrops differ when their margin tones differ by this
TONE_RUN = 0.05          # ...held steady over this much of the side, each way
TONE_SHARP = 10          # ...and the change happens IN ONE LINE, not over many
PANEL_MIN = 0.10         # a panel is at least this much of the side
AREA_MIN = 0.035        # ...and this much of the picture, once the two splits are made
MAX_PANELS = 6


def gutter_runs(im, axis):
    """Runs of flat, light lines along `axis` (0 rows, 1 columns).

    A gutter is read from the line's own evenness rather than from a single
    page-wide backdrop colour. Two panels often sit on two different whites —
    one photographic, one the page's own — so a colour match against one modal
    colour misses the band between them, which is exactly the line that matters.
    """
    w = SMALL
    h = max(8, int(im.height * SMALL / im.width))
    s = im.convert('L').resize((w, h), Image.BILINEAR)
    px = list(s.getdata())
    n = h if axis == 0 else w
    m = w if axis == 0 else h
    flat = []
    for i in range(n):
        line = sorted(px[i * w:(i + 1) * w] if axis == 0 else [px[j * w + i] for j in range(h)])
        spread = line[int(m * 0.95)] - line[int(m * 0.05)]
        flat.append(spread <= GUTTER_SPREAD and (sum(line) / m) >= GUTTER_LUM)
    runs, start = [], None
    for i, v in enumerate(flat + [False]):
        if v and start is None:
            start = i
        elif not v and start is not None:
            runs.append((start, i))
            start = None
    return runs, n


def tone_joins(im, axis):
    """Where one backdrop ends and a different one begins, with no band between.

    A packshot on one grey above a shot on another grey has no gutter at all:
    the page simply changes tone, and neither side holds a run of empty lines to
    find it by — the garment fills the frame nearly all the way down. What does
    stay empty is the MARGIN: the strip down each side where the page shows past
    the photograph. Its tone is the backdrop at that height, and the line where
    it steps is the join.

    Kept tight on purpose, and tighter than it first looks it should be. A
    looser version of this test split nine screenshots and was wrong on eight:
    a studio backdrop shading from pale wall to warm floor steps the margin tone
    by six or eight levels over a dozen lines, and the cut landed across a
    model's chest. A page boundary steps in ONE line. That is the difference,
    so that is what is tested, along with steady backdrop on both sides.
    """
    w = SMALL
    h = max(8, int(im.height * SMALL / im.width))
    s = im.convert('L').resize((w, h), Image.BILINEAR)
    px = list(s.getdata())
    n = h if axis == 0 else w
    m = w if axis == 0 else h
    k = max(2, int(m * MARGIN))
    prof = []
    for i in range(n):
        line = px[i * w:(i + 1) * w] if axis == 0 else [px[j * w + i] for j in range(h)]
        side = sorted(line[:k] + line[-k:])
        q = len(side)
        prof.append((side[q // 2], side[int(q * 0.9)] - side[int(q * 0.1)]))
    need = max(3, int(n * TONE_RUN))
    joins = []
    for i in range(need, n - need):
        before = [t for t, sp in prof[i - need:i] if sp <= 18]
        after = [t for t, sp in prof[i:i + need] if sp <= 18]
        if len(before) < need * 0.8 or len(after) < need * 0.8:
            continue          # the margin is busy here: it is photograph, not page
        a, b = sum(before) / len(before), sum(after) / len(after)
        if abs(a - b) < TONE_STEP:
            continue
        if max(before) - min(before) > TONE_STEP or max(after) - min(after) > TONE_STEP:
            continue
        if abs(prof[i][0] - prof[i - 1][0]) < TONE_SHARP:
            continue          # a gradient inside one photograph, not a join
        joins.append(i)
    out = []
    for j in joins:                       # one cut per step, not one per line
        if not out or j - out[-1] > need:
            out.append(j)
    return out


def split_axis(im, axis):
    """-> [(lo, hi), ...] as fractions along `axis`, or [] to leave it whole."""
    runs, n = gutter_runs(im, axis)
    deep = [r for r in runs if (r[1] - r[0]) / n >= GUTTER_MIN]
    joins = [j for j in tone_joins(im, axis) if PANEL_MIN < j / n < 1 - PANEL_MIN]
    # Cut through the MIDDLE of each gutter, not at its edges. A panel that
    # begins where the backdrop stops has the garment against its frame from
    # the first row, and the "clear of the frame" measurement then rejects
    # every panel there is; half the gutter on each side gives it air.
    cuts = [(lo + hi) // 2 for lo, hi in deep if lo > 1 and hi < n - 1]
    # ...and where one backdrop simply becomes another, cut on the join itself
    for j in joins:
        if j > 1 and j < n - 1 and all(abs(j - c) > n * GUTTER_MIN for c in cuts):
            cuts.append(j)
    cuts.sort()
    if not cuts:
        return []
    bounds, prev = [], 0
    for c in cuts:
        bounds.append((prev, c))
        prev = c
    bounds.append((prev, n))
    panels = [(a / n, b / n) for a, b in bounds if (b - a) / n >= PANEL_MIN]
    if len(panels) < 2 or len(panels) > MAX_PANELS:
        return []
    return panels


def find_panels(im):
    """-> (boxes as fractions of the picture, why it was left whole).

    Rows first, then columns inside each band. A product page is usually a
    stack of photographs, but on a tablet it is a stack beside a column of
    details, and splitting only one way leaves the type in with the garment —
    which is what made a good flat lay read as "other" and go to Review.
    """
    W, H = im.size
    bands = split_axis(im, 0) or [(0.0, 1.0)]
    out = []
    for a, b in bands:
        sub = im.crop((0, int(a * H), W, int(b * H)))
        cols = split_axis(sub, 1) if min(sub.size) >= 60 else []
        if cols:
            out += [[c, a, d - c, b - a] for c, d in cols]
        else:
            out.append([0.0, a, 1.0, b - a])
    if len(out) < 2 or len(out) > MAX_PANELS:
        return [], 'no clear gutter' if len(out) < 2 else 'too many panels'
    return out, ''


def text_share(im, count=False):
    """How much of a panel confident OCR words cover (and, with `count`, how
    many words there are)."""
    boxes = FL.word_boxes(im, conf=55)
    if not boxes:
        return (0.0, 0) if count else 0.0
    area = sum(w * h for _x, _y, w, h, _t in boxes)
    share = min(1.0, area / float(im.width * im.height))
    return (share, len(boxes)) if count else share


TEXT_WORDS = 8           # a panel with this many confident words is page text


def slivery(cut, panel_size):
    """True when the cut-out cannot be a garment: too little of its panel, or a
    thin band lying across it. rembg sometimes returns a diagonal strip of
    fabric that passes every other test — one piece, clear of the frame, no
    text — so its shape is measured too."""
    bb = cut.getbbox()
    if not bb:
        return True, 'nothing cut'
    bw, bh = bb[2] - bb[0], bb[3] - bb[1]
    a = cut.getchannel('A')
    small = a.resize((120, 120), Image.NEAREST)
    fill = sum(1 for p in small.getdata() if p) / (120.0 * 120.0)
    share = (bw * bh) / float(panel_size[0] * panel_size[1]) * fill
    if share < 0.06:
        return True, 'covers %.1f%% of its panel' % (share * 100)
    long_side = max(bw, bh) / float(max(1, min(bw, bh)))
    if long_side >= 3.2 and fill <= 0.72:
        return True, 'a thin band, %.1f:1 and %.0f%% filled' % (long_side, fill * 100)
    return False, ''


def classify(panel, cut, cut_skin, text, words=0):
    """flat lay | on-model | detail | text | other.

    Once the page has been split, the panel IS the photograph, so the corner
    test that decides a plain backdrop on a whole page reads the garment's own
    shoulders instead and calls a good packshot "other". What is left to ask of
    a panel is whether anyone is in it and whether what came out of it could be
    a garment at all.
    """
    bb = cut.getbbox()
    covered = ((bb[2] - bb[0]) * (bb[3] - bb[1]) / float(panel.width * panel.height)) if bb else 0
    # page text set small covers little area: B018-P001's "Composizione"
    # block covered 3.7% of its panel, cut into one clean piece and went on the
    # shelf as a flat lay. Counting the words catches what the area misses.
    if text >= 0.16 or (text >= 0.05 and covered < 0.12) or words >= TEXT_WORDS:
        return 'text'
    if cut_skin > FL.SKIN_MAX:
        return 'on-model'
    if not bb:
        return 'other'
    sliver, _why = slivery(cut, panel.size)
    if sliver:
        return 'detail' if min(panel.size) < 300 else 'other'
    return 'flat lay'


def cut_panel(panel):
    """Badges painted out with the backdrop's own colour, then cut."""
    _plain, _lum, _sd, _spread, col = FL.plain_backdrop(panel)
    first = FL.raw_cut(panel)
    mask = first.getchannel('A').resize(panel.size, Image.NEAREST)
    painted_im, painted = FL.paint_out(panel, FL.word_boxes(panel), col, keep=mask)
    return (FL.raw_cut(painted_im) if painted else first), painted


def measure_flat(cut, px, stem):
    """The shelf gate's three measurements on a flat-lay panel's cut, and the
    cut saved when it passes."""
    m = FL.measure(cut)
    sliver, sw = slivery(cut, px.size)
    ok = (m['components'] == 1 and m['edge_pixels'] == 0 and m['words_inside'] == 0
          and not sliver)
    rec = dict(m)
    rec['clean'] = bool(ok)
    rec['why'] = '' if ok else ', '.join(filter(None, [
        'more than one piece' if m['components'] != 1 else '',
        'touches the frame' if m['edge_pixels'] else '',
        'text inside it' if m['words_inside'] else '', sw]))
    if ok:
        bb = cut.getbbox()
        cut.crop(bb).save(f'{OUT}/{stem}-cut.webp', 'WEBP', quality=90, method=5)
        rec['cut'] = f'review/{stem}-cut.webp'
    return rec


def seam(im):
    """The column where one photograph ends and the next begins, on a page
    whose two photos abut with no gutter: the sharpest change in the columns'
    mean colour within the middle third of the width."""
    import numpy as np
    a = np.asarray(im.convert('RGB').resize((400, max(40, int(400 * im.height / im.width))))).astype(float)
    col = a.mean(axis=0)
    step = np.abs(np.diff(col, axis=0)).sum(axis=1)
    lo, hi = int(0.35 * len(step)), int(0.65 * len(step))
    x = lo + int(np.argmax(step[lo:hi]))
    return (x + 1) / 400.0, float(step[x])


def side_by_side(out, layouts, review=None):
    """On a side-by-side page the left photograph is the flat lay and the right
    one the same garment on a model (Toast, Care of Carl). Position decides
    there, not the skin test: rembg often cuts the model away and leaves only
    the jumper, which then reads as a clean flat lay, and a rust or coral
    jumper falls inside the skin band and reads as a person. The layout is the
    viewing pass's `layout=side-by-side`, read off the page."""
    n = 0
    for key, v in out.items():
        pid = key.split('#')[0]
        if layouts.get(pid) != 'side-by-side':
            continue
        if not v.get('split') and review:
            # two photos that abut: no gutter to find, so cut at the seam
            i = int(key.split('#')[1])
            e = ((review.get(pid) or {}).get('images') or [None] * (i + 1))[i]
            if not e or not os.path.exists(f"{CAT}/{e['path']}"):
                continue
            with Image.open(f"{CAT}/{e['path']}") as f:
                im = f.convert('RGB')
            fx, strength = seam(im)
            stem = os.path.basename(e['path'])[:-4]
            W, H = im.size
            panels = []
            for j, (bx, bw) in enumerate(((0.0, fx), (fx, 1.0 - fx))):
                px = im.crop((int(bx * W), 0, int((bx + bw) * W), H))
                name = f'{stem}p{j}.jpg'
                px.save(f'{OUT}/{name}', 'JPEG', quality=86, optimize=True)
                panels.append({'box': [round(bx, 4), 0.0, round(bw, 4), 1.0], 'type': 'other',
                               'path': f'review/{name}', 'w': px.width, 'h': px.height,
                               'text_share': 0.0, 'skin': 0.0, 'badges_painted': 0})
            v.clear()
            v.update(split=True, panels=panels, split_by='seam', seam_strength=round(strength, 1))
        if not v.get('split'):
            continue
        major = [p for p in v['panels'] if p['box'][3] >= 0.4 and p['box'][2] >= 0.2]
        if len(major) < 2:
            continue
        major.sort(key=lambda p: p['box'][0])
        left, right = major[0], major[1:]
        if left.get('typed_by') != 'position':
            with Image.open(f"{CAT}/{left['path']}") as f:
                px = f.convert('RGB')
            cut, _ = cut_panel(px)
            for k in ('clean', 'why', 'cut', 'components', 'edge_pixels', 'words_inside'):
                left.pop(k, None)
            left.update(type='flat lay', typed_by='position',
                        **measure_flat(cut, px, os.path.basename(left['path'])[:-4]))
        for p in right:
            for k in ('clean', 'why', 'cut'):
                p.pop(k, None)
            p.update(type='on-model', typed_by='position')
        n += 1
    return n


def primary_of(panels):
    """The picture the shelf shows: a clean flat lay, else a flat lay, else the
    person wearing it, else whatever came first."""
    for want in (lambda p: p['type'] == 'flat lay' and p.get('clean'),
                 lambda p: p['type'] == 'flat lay',
                 lambda p: p['type'] == 'on-model',
                 lambda p: True):
        for i, p in enumerate(panels):
            if want(p):
                return i
    return 0


def promote(out, only=None):
    """Give a product whose flat-lay panel is clean that panel as its cut-out.

    This is the whole point of splitting: the product's own picture stops being
    the garment with a small figure standing under it. The verdict is written
    where the shelf gate reads it, so the product leaves Review.
    """
    try:
        flats = json.load(open(CAT + '/_flat_lays.json'))
    except (FileNotFoundError, json.JSONDecodeError):
        flats = {}
    try:
        assets = json.load(open(CAT + '/_assets.json'))
    except (FileNotFoundError, json.JSONDecodeError):
        assets = {}
    promoted = 0
    best = {}
    for key, v in out.items():
        if not v.get('split'):
            continue
        pid = key.split('#')[0]
        if only is not None and pid not in only:
            continue
        for p in v['panels']:
            if p.get('clean') and p.get('cut'):
                prev = best.get(pid)
                if prev is None or p['w'] * p['h'] > prev['w'] * prev['h']:
                    best[pid] = p
    for pid, p in best.items():
        src = f"{CAT}/{p['cut']}"
        if not os.path.exists(src):
            continue
        with Image.open(src) as f:
            f.convert('RGBA').save(f'{CAT}/assets/{pid}.webp', 'WEBP', quality=90, method=5)
        rec = flats.setdefault(pid, {})
        rec.update({'clean': True, 'why': '', 'flat': True, 'from_panel': p['path']})
        a = assets.get(pid)
        if a:
            a['asset_type'] = 'cutout_flat'
            a['measured'] = 'clean'
            a['bytes'] = os.path.getsize(f'{CAT}/assets/{pid}.webp')
            a['note'] = 'cut from the flat-lay panel of a split product page'
        promoted += 1
    json.dump(flats, open(CAT + '/_flat_lays.json', 'w'), indent=1)
    json.dump(assets, open(CAT + '/_assets.json', 'w'), indent=1)
    print('products given a flat-lay panel as their cut-out:', promoted)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--all', action='store_true',
                    help='process every product, including ones already reviewed; '
                         'without it only new or changed products are looked at')
    ap.add_argument('--redo', dest='all', action='store_true', help='same as --all')
    args = ap.parse_args()
    import csv
    review = json.load(open(CAT + '/_review_boxes.json'))
    shots = {r['product_id']: r['shot_type'] for r in csv.DictReader(open(CAT + '/products.csv'))}
    try:
        out = json.load(open(PAN))
    except (FileNotFoundError, json.JSONDecodeError):
        out = {}
    # new or changed products only, unless --all: a product the owner has
    # reviewed keeps its panels and its cut-out exactly as they are
    cands = [pid for pid in sorted(review) if shots.get(pid) != 'listing grid']
    todo, fp = INC.select('panels', cands, args.all)
    INC.report('panels', todo, cands, args.all)
    mine = set(todo)
    for key in [k for k in out if k.split('#')[0] in mine]:
        del out[key]                     # a changed product is looked at afresh
    jobs = []
    for pid in todo:
        rec = review[pid]
        for i, e in enumerate(rec.get('images') or []):
            if not e or 'error' in e or e.get('panel_of') is not None:
                continue
            if f'{pid}#{i}' in out:
                continue
            jobs.append((pid, i, e))
    if args.limit:
        # a product cut short by --limit is not stamped: the next run finishes it
        todo = [pid for pid in todo if pid not in {j[0] for j in jobs[args.limit:]}]
        mine = set(todo)
        jobs = jobs[:args.limit]
    print(f'{len(jobs)} screenshots to look at, {len(out)} already done', flush=True)
    for k, (pid, i, e) in enumerate(jobs, 1):
        key = f'{pid}#{i}'
        src = f"{CAT}/{e['path']}"
        if not os.path.exists(src):
            out[key] = {'split': False, 'why': 'no review copy'}
            continue
        with Image.open(src) as f:
            im = f.convert('RGB')
        boxes, why = find_panels(im)
        if not boxes:
            out[key] = {'split': False, 'why': why}
        else:
            W, H = im.size
            stem = os.path.basename(e['path'])[:-4]
            panels = []
            for j, (bx, by, bw, bh) in enumerate(boxes):
                px = im.crop((int(bx * W), int(by * H), int((bx + bw) * W), int((by + bh) * H)))
                if min(px.size) < 80 or (px.width * px.height) < AREA_MIN * W * H:
                    continue
                txt, nwords = text_share(px, count=True)
                cut, painted = cut_panel(px)
                cs = round(FL.cutout_skin(cut), 4)
                kind = classify(px, cut, cs, txt, nwords)
                name = f'{stem}p{j}.jpg'
                px.save(f'{OUT}/{name}', 'JPEG', quality=86, optimize=True)
                rec = {'box': [round(v, 4) for v in (bx, by, bw, bh)], 'type': kind,
                       'path': f'review/{name}', 'w': px.width, 'h': px.height,
                       'text_share': round(txt, 3), 'skin': cs, 'badges_painted': painted}
                if kind == 'flat lay':
                    rec.update(measure_flat(cut, px, f'{stem}p{j}'))
                panels.append(rec)
            if len(panels) < 2:
                out[key] = {'split': False, 'why': 'panels too small once cropped'}
            else:
                out[key] = {'split': True, 'panels': panels}
        if k % 10 == 0 or k == len(jobs):
            json.dump(out, open(PAN, 'w'), indent=1)
            print(f'  {k}/{len(jobs)}', flush=True)
    layouts = {}
    for r in csv.DictReader(open(CAT + '/products.csv')):
        m = re.search(r'layout=([\w-]+)', r.get('notes', ''))
        if m:
            layouts[r['product_id']] = m.group(1)
    print('side-by-side pages typed by position:',
          side_by_side({k: v for k, v in out.items() if k.split('#')[0] in mine}, layouts, review))
    json.dump(out, open(PAN, 'w'), indent=1)
    promote(out, mine)
    INC.mark('panels', todo, fp)
    split = [v for v in out.values() if v.get('split')]
    kinds = collections.Counter(p['type'] for v in split for p in v['panels'])
    print(f'split: {len(split)} of {len(out)} screenshots into {sum(len(v["panels"]) for v in split)} panels')
    print('panels by type:', dict(kinds))
    print('flat-lay panels that measure clean:',
          sum(1 for v in split for p in v['panels'] if p.get('clean')))
    print('left whole:', collections.Counter(v.get('why', '') for v in out.values()
                                             if not v.get('split')).most_common(5))


if __name__ == '__main__':
    main()
