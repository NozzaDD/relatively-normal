"""Move boxes drawn under an older trim onto the same pixels under the new one.

The trim decides what a screenshot's "full" image is. When it changes, a box
the stylist drew is still stored as fractions of the old image, and would land
somewhere else on the new one. Both crops are recorded in _review_boxes.json in
the ORIGINAL file's pixels — `origin_prev` and `origin` — so a box can be moved
exactly: old fractions -> original pixels -> new fractions.

  python3 content/tools/migrate_trim.py            # rewrites asset-choices.json
  python3 content/tools/migrate_trim.py --check    # says what it would change

It also writes studio/data/trim-migration.json, which the desk applies once to
the choices in the browser's own storage, so work done on the iPad and never
exported is moved too.
"""
import os, sys, json, argparse

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CAT = ROOT + '/content/catalogue'
TRIM_VERSION = 2          # bump when the trim changes again


def remap(box, prev, now):
    """A box in the old image's fractions -> the new image's fractions."""
    px, py, pw, ph = prev[:4]
    nx, ny, nw, nh = now[:4]
    if not pw or not ph or not nw or not nh:
        return box
    # old fractions -> pixels of the original screenshot
    x0 = px + box[0] * pw
    y0 = py + box[1] * ph
    x1 = px + (box[0] + box[2]) * pw
    y1 = py + (box[1] + box[3]) * ph
    # -> fractions of the new crop, clamped to it
    def f(v, o, s):
        return min(1.0, max(0.0, (v - o) / s))
    a, b = f(x0, nx, nw), f(y0, ny, nh)
    c, d = f(x1, nx, nw), f(y1, ny, nh)
    if c - a < 0.01 or d - b < 0.01:        # the box fell outside the new crop
        return None
    return [round(a, 4), round(b, 4), round(c - a, 4), round(d - b, 4)]


def table(review):
    """{pid: {image index: {prev, now}}} for every image whose crop moved."""
    out = {}
    for pid, v in review.items():
        for i, e in enumerate(v.get('images') or []):
            if not e or 'error' in e or 'origin' not in e or 'origin_prev' not in e:
                continue
            if e['origin'][:4] == e['origin_prev'][:4]:
                continue
            out.setdefault(pid, {})[str(i)] = dict(prev=e['origin_prev'], now=e['origin'])
    return out


def migrate_choices(choices, tab):
    moved, dropped = 0, 0
    for pid, c in choices.items():
        t = tab.get(pid)
        if not t or c.get('trim', 1) >= TRIM_VERSION:
            continue
        for key in ('box',):
            if c.get(key) and c.get('base', 'photo') == 'photo':
                m = t.get(str(c.get('image', 0)))
                if m:
                    nb = remap(c[key], m['prev'], m['now'])
                    if nb:
                        c[key] = nb; moved += 1
                    else:
                        c.pop('choice', None); c.pop(key, None); dropped += 1
        for sp in c.get('splits', []):
            if sp.get('base', 'photo') != 'photo':
                continue
            m = t.get(str(sp.get('image', 0)))
            if m and sp.get('box'):
                nb = remap(sp['box'], m['prev'], m['now'])
                if nb:
                    sp['box'] = nb; moved += 1
                else:
                    sp['box'] = None; dropped += 1
        c['splits'] = [s for s in c.get('splits', []) if s.get('box')]
        c['trim'] = TRIM_VERSION
    return moved, dropped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    a = ap.parse_args()
    review = json.load(open(CAT + '/_review_boxes.json'))
    tab = table(review)
    print(f'{len(tab)} products whose crop moved')
    os.makedirs(ROOT + '/studio/data', exist_ok=True)
    if not a.check:
        json.dump(dict(trim_version=TRIM_VERSION, products=tab),
                  open(ROOT + '/studio/data/trim-migration.json', 'w'), separators=(',', ':'))
    path = CAT + '/asset-choices.json'
    if not os.path.exists(path):
        print('no asset-choices.json yet; nothing to move')
        return
    doc = json.load(open(path))
    moved, dropped = migrate_choices(doc.get('choices', {}), tab)
    print(f'boxes moved: {moved}, dropped as outside the new crop: {dropped}')
    if not a.check:
        json.dump(doc, open(path, 'w'), indent=1)


if __name__ == '__main__':
    main()
