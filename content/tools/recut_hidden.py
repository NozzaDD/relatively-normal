"""Re-cut the products the owner hid, and send the ones that now look right
back to Review — Part B of 24 September.

The owner's hidden products are the ground truth for what the cut-out method
got wrong. `_hidden_reasons.json` holds one reason per product, read off
contact sheets by eye (point 4). This re-cuts every one of them with
soft_cut.py (point 5), from the right picture — a split panel rather than the
whole screenshot, a row's own screenshot rather than its parent's — and writes:

  content/catalogue/assets/{pid}.webp            the new cut
  content/catalogue/assets-before-recut/{pid}.webp   the old one, kept
  content/catalogue/_recut.json                 per product: picture, measures, verdict
  content/catalogue/sheets/recut-*.jpg           before/after contact sheets

Nothing goes to the shelf. A product whose new cut looks right goes back to
REVIEW (asset-choices.json `review`, and a review-sends.json version so an
iPad that still holds the old "hidden" hears about it); every other hidden
product stays hidden exactly as it was. "Looks right" is decided by a person
from the sheets (LOOKS_RIGHT below), with the measurements as a first filter.

    python3 content/tools/recut_hidden.py --cut        # re-cut, measure, sheets
    python3 content/tools/recut_hidden.py --send       # apply LOOKS_RIGHT
"""
import os, sys, json, shutil, argparse, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image
import soft_cut as S

ROOT = S.ROOT
CAT = S.CAT
REASONS = CAT + '/_hidden_reasons.json'
OUT = CAT + '/_recut.json'
BEFORE = CAT + '/assets-before-recut'
VERSION = '2026-09-24-recut'

# the kinds of picture, best first for a re-cut: a packshot, a grid cell, the
# page it was on, a photo of it worn. Close-ups and page text never.
ORDER = {'flat lay': 0, 'cell': 1, 'whole page': 2, 'listing grid': 3, 'on-model': 4}
REASON_WORDS = {
    'jagged': 'jagged outline', 'holes': 'background left inside the garment',
    'thin': 'thin parts lost', 'colourways': 'row mixed colourways',
    'products': 'row mixed different products', 'panels': 'panels not split',
    'model': 'on a model', 'page': 'page text or a page screenshot', 'broken': 'the cut lost the garment',
    'clipped': 'cut off at the edge of the picture', 'swatch': 'a fabric close-up',
    'notgarment': 'not a garment',
}

# What the new cut did, by the reason she hid it — the words the Review card shows.
FIXED = {
    'model': 'cut off the model, the garment alone', 'jagged': 'a soft, anti-aliased edge',
    'holes': 'the backdrop between the legs removed', 'panels': 'cut from its own panel of the page',
    'colourways': "cut from its own colour's picture", 'broken': 'cut again from the full screenshot',
    'clipped': 'cut again from the full screenshot, whole', 'swatch': 'cut from the garment, not the close-up',
    'products': 'the row is split; cut from its own picture', 'thin': 'handles kept',
}

# From the before/after sheets of 24 Sept (evening), read by eye: the 73
# re-cuts that look right. They go back to Review; the other 133 hidden
# products keep their old cut and stay hidden, exactly as she left them.
LOOKS_RIGHT = set('''
    B002-P001 B003-P001 B004-P001 B007-P001 B007-P002 B008-P003
    B012-P002 B014-P001-V4 B015-P003 B015-P005 B016-P003 B017-P001-V2
    B019-P004 B021-P001-V2 B021-P001-V3 B021-P005 B021-P012 B021-P014
    B025-P001 B025-P003 B031-P002 B031-P005 B031-P007 B032-P001
    B037-P003 B037-P004 B037-P007 B038-P002 B039-P002 B040-P003
    B042-P017 B042-P024 B042-P026 B045-P002 B045-P003 B047-P003
    B048-P001 B048-P003 B051-P004 B052-P001 B052-P003 B053-P003
    B053-P006 B055-P005 B055-P008 B055-P009 B055-P014 B056-P001
    B062-P001 B062-P008-V2 B065-P003 B065-P005 B065-P007 B067-P001
    B070-P011 B070-P012 B072-P001 B073-P006 B073-P009 B074-P001
    B076-P005 B077-P005 B077-P007 B077-P008 B078-P001 B082-P003
    B088-P001 B088-P002 B088-P003 B088-P004 B054-P005 B077-P010
    B077-P011
'''.split())


# rows split out of hidden rows (not hidden themselves, already in Review)
# whose re-cut is better than the cut the split gave them
KEEP_NEW = {'B032-P001-V3', 'B075-P007-V3', 'B090-P010-V4'}


def pictures(p):
    imgs = p.get('images') or []
    cand = [(ORDER.get(e.get('type') or 'whole page', 5), i) for i, e in enumerate(imgs)
            if (e.get('type') or 'whole page') in ORDER]
    return [i for _, i in sorted(cand)]


def subtle_panels(p, idx):
    """The review copy of a picture split with panels.py's subtle joins, as
    fractions: a flat lay and a model shot on two slightly different greys."""
    import panels as P
    e = (p.get('images') or [])[idx]
    try:
        im = Image.open(S.STUDIO + '/' + e['path']).convert('RGB')
    except Exception:
        return []
    boxes, _ = P.find_panels(im, subtle=True)
    return boxes


def recut_one(p, reason, review):
    """-> (RGBA or None, record). Tries the product's pictures best first and,
    inside a picture holding two panels, each panel; keeps the cut that is one
    piece with the least skin, preferring packshots."""
    tried = []
    best = None
    order = pictures(p)[:3]
    # a fault in the CUT (jagged, holes, lost handles) is fixed on the same
    # picture: another picture of the row is not what she hid it for
    if reason in ('jagged', 'holes', 'thin') and (p.get('image') or 0) < len(p.get('images') or []):
        order = [p.get('image') or 0]
    for idx in order:
        src, e = S.source_picture(p, idx, review)
        if src is None:
            tried.append(dict(image=idx, error='screenshot missing'))
            continue
        worn = (e.get('type') == 'on-model') or reason == 'model'
        boxes = subtle_panels(p, idx) or [[0, 0, 1, 1]]
        for b in boxes:
            W, H = src.size
            part = src.crop((int(b[0] * W), int(b[1] * H), int((b[0] + b[2]) * W), int((b[1] + b[3]) * H)))
            if min(part.size) < 80:
                continue
            t = time.time()
            cut, info = S.cut(part, p.get('slot') or '', worn=worn)
            info.update(image=idx, panel=[round(v, 4) for v in b], type=e.get('type') or 'whole page',
                        seconds=round(time.time() - t, 1))
            tried.append(info)
            if cut is None:
                continue
            a = np.asarray(cut)[..., 3]
            rgb = np.asarray(cut)[..., :3]
            skin = S.skin_share(rgb, a.astype(np.float32) / 255)
            info['skin_after'] = round(skin, 3)
            score = (info.get('pieces', 9) != 1) * 4 + skin * 10 + ORDER.get(info['type'], 5) * 0.3 \
                + (info.get('fill', 0) < 0.15) * 3 + (len(boxes) > 1 and b[2] * b[3] < 0.25) * 1
            if best is None or score < best[0]:
                best = (score, cut, info)
    rec = dict(reason=reason, tried=tried)
    if best is None:
        return None, rec
    rec['chosen'] = best[2]
    return best[1], rec


def cut_all(only=None):
    reasons = json.load(open(REASONS))['products']
    products = {p['product_id']: p for p in json.load(open(S.STUDIO + '/data/products.json'))}
    review = S._load('_review_boxes.json', {})
    prev = S._load('_recut.json', {}).get('products', {})
    os.makedirs(BEFORE, exist_ok=True)
    out = dict(prev)
    ids = [k for k in reasons if (not only or k in only)]
    for n, pid in enumerate(ids, 1):
        p = products.get(pid)
        if not p:
            out[pid] = dict(reason=reasons[pid], error='not in the catalogue')
            continue
        cut, rec = recut_one(p, reasons[pid], review)
        asset = CAT + f'/assets/{pid}.webp'
        if cut is not None:
            if os.path.exists(asset) and not os.path.exists(f'{BEFORE}/{pid}.webp'):
                shutil.copyfile(asset, f'{BEFORE}/{pid}.webp')
            cut.save(asset, 'WEBP', quality=92, method=5)
            rec['asset'] = os.path.relpath(asset, ROOT)
        out[pid] = rec
        c = rec.get('chosen') or {}
        print(f'{n}/{len(ids)} {pid} {reasons[pid]:10s} img {c.get("image")} {c.get("type", "")[:8]:8s} '
              f'pieces {c.get("pieces")} skin {c.get("skin_after")} worn {c.get("worn")} {c.get("worn_note", "")}',
              flush=True)
        json.dump(dict(version=VERSION, products=out), open(OUT, 'w'), indent=0)
    return out


def sheets(ids, name, per=20, cols=4):
    """Before (left) and after (right) on mid-grey, one pair per cell."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from contact_sheet import sheet
    rec = S._load('_recut.json', {}).get('products', {})
    reasons = json.load(open(REASONS))['products']
    tmp = CAT + '/sheets/_tmp'
    os.makedirs(tmp, exist_ok=True)
    made = []
    for k in range(0, len(ids), per):
        cells = []
        for pid in ids[k:k + per]:
            T = Image.new('RGBA', (620, 320), (128, 128, 128, 255))
            for j, path in enumerate([f'{BEFORE}/{pid}.webp', CAT + f'/assets/{pid}.webp']):
                if os.path.exists(path):
                    im = Image.open(path).convert('RGBA')
                    im.thumbnail((300, 310), Image.LANCZOS)
                    T.alpha_composite(im, (5 + j * 310 + (300 - im.width) // 2, 5 + (310 - im.height) // 2))
            f = f'{tmp}/{pid}.png'
            T.convert('RGB').save(f)
            c = (rec.get(pid) or {}).get('chosen') or {}
            cells.append(dict(path=f, label=f'{pid} · {REASON_WORDS.get(reasons.get(pid), reasons.get(pid))}\n'
                                            f'before | after · {c.get("type", "")} {"worn" if c.get("worn") else ""}'))
        out = CAT + f'/sheets/{name}-{k // per + 1}.jpg'
        sheet(cells, out, cols=cols, cell=620, label_h=44,
              title=f'{name}: before | after, {k + 1}-{k + len(cells)} of {len(ids)}')
        made.append(out)
    shutil.rmtree(tmp, ignore_errors=True)
    return made


def send(looks_right):
    """The re-cuts that look right go back to Review — asset-choices.json and a
    review-sends.json version (send_to_review.py). Only a product she hid is
    touched; every other decision is left exactly as it is."""
    from send_to_review import send as send_back
    reasons = json.load(open(REASONS))['products']
    sent = send_back(VERSION, {
        pid: (f're-cut 24 Sept — you hid it for: {REASON_WORDS.get(reasons.get(pid), reasons.get(pid))}; '
              f'now {FIXED.get(reasons.get(pid), "cut again")}. Decide again.')
        for pid in sorted(looks_right)}, only_if=lambda c: bool(c.get('hidden')))
    print(len(sent), 'sent back to Review')
    return sent


def restore_others(looks_right, keep_new=()):
    """Every hidden product whose re-cut does NOT look right gets its old cut
    back: it stays hidden, and exactly as it was. `keep_new` are rows that were
    not hidden (a split's new rows) whose re-cut is the better one."""
    back = 0
    for f in sorted(os.listdir(BEFORE)):
        pid = f[:-5]
        if pid in looks_right or pid in keep_new:
            continue
        shutil.copyfile(f'{BEFORE}/{f}', CAT + f'/assets/{pid}.webp')
        back += 1
    print(back, 'old cuts put back')
    return back


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cut', action='store_true')
    ap.add_argument('--only', nargs='*')
    ap.add_argument('--sheets', action='store_true')
    ap.add_argument('--send', action='store_true')
    a = ap.parse_args()
    if a.cut:
        cut_all(a.only)
    if a.sheets:
        reasons = json.load(open(REASONS))['products']
        print(sheets(sorted(reasons), 'recut'))
    if a.send:
        restore_others(LOOKS_RIGHT, KEEP_NEW)
        send(LOOKS_RIGHT)


if __name__ == '__main__':
    main()
