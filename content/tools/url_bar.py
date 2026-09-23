"""The shop's domain, read off Safari's address bar in each screenshot.

The address bar is the one part of a shop screenshot that says, without
interpretation, which shop it is. The viewing pass recorded whatever shop text
was legible somewhere on the page, which is not the same thing: a batch could
end up filed under a brand whose name happened to appear in a footer. This
reads the top band of the ORIGINAL file — never touching it — and takes the
domain from it.

  python3 content/tools/url_bar.py            # resumable; writes _url_bars.json

Output: {"images": {path: {domain, raw}}, "batches": {batch_id: {domain, n, of}}}
A batch's domain is the one most of its screenshots agree on; where they do not
agree the batch keeps the majority and records how thin it was, because a batch
that spans two shops is a clustering fault worth seeing rather than hiding.
"""
import os, sys, json, re, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image

try:
    import pytesseract
except ImportError:                                   # nothing to read with
    pytesseract = None

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CAT = ROOT + '/content/catalogue'
OUT = CAT + '/_url_bars.json'

BAND = 0.13                  # deep enough to hold the tab strip AND the bar below it
TLDS = ('com', 'co.uk', 'net', 'org', 'it', 'de', 'fr', 'ch', 'nl', 'se', 'dk',
        'eu', 'us', 'store', 'shop', 'fashion', 'jp', 'at', 'be', 'es', 'io', 'st')
NOT_A_SHOP = {'google.com', 'apple.com', 'icloud.com', 'safari.com'}
TOKEN = re.compile(r'\b((?:[a-z0-9][a-z0-9-]{1,30}\.)+[a-z]{2,10})\b')


def domain_of(text):
    """The likeliest shop domain in a scrap of address-bar text, or ''.

    The text is read as it stands, spaces and all. Squeezing the spaces out
    first glues the status bar's clock onto the domain — 15:13 Sat 19 Sep
    closed.com became 13sat19sepclosed.com — and a run of digits in the first
    label is the tell, so it is rejected outright as well.
    """
    best = ''
    for m in TOKEN.finditer((text or '').lower()):
        d = m.group(1).strip('.')
        if len(d) < 6 or d in NOT_A_SHOP:
            continue
        if d.rsplit('.', 1)[-1] not in TLDS and '.' not in d.rsplit('.', 2)[0]:
            continue
        d = re.sub(r'^(www|m|shop|store)\.', '', d)
        if len(d) < 6 or re.search(r'\d', d.split('.')[0]):
            continue
        if not best or len(d) > len(best):
            best = d
    return best


def vocabulary():
    """Domains the catalogue already knows, to snap an OCR slip back onto."""
    import csv, glob
    v = set()
    try:
        for r in csv.DictReader(open(CAT + '/products.csv')):
            s = (r.get('shop') or '').strip().lower()
            if '.' in s and ' ' not in s:
                v.add(s)
    except FileNotFoundError:
        pass
    for f in glob.glob(ROOT + '/brands/*.yaml'):
        slug = os.path.basename(f)[:-5].replace('-', '')
        v.update({slug + '.com', slug + '.it', slug + '.de'})
    return v


def eye_read():
    """Domains the viewing pass read off the pages by eye. These outrank the
    catalogue's own shop column, which is built from this file's readings and
    so can carry an OCR slip back into the vocabulary (ilysilk.com)."""
    import glob
    v = set()
    for f in glob.glob(CAT + '/_viewing_rows/rows_*.txt'):
        for ln in open(f):
            p = [x.strip().lower() for x in ln.split('|')]
            if len(p) > 9 and WORD.match(p[9]):
                v.add(p[9])
    return v


def edits(a, b):
    """Levenshtein, small strings only."""
    if abs(len(a) - len(b)) > 2:
        return 9
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def snap(d, vocab, eye=()):
    """unigqlo.com is uniqlo.com with one letter hallucinated; snap it back."""
    if not d or d in eye:
        return d
    # two slips only on a long name: tods.com is two edits from bode.com, and
    # snapping it filed a page of Tod's loafers under Bode
    room = 2 if len(d.split('.')[0]) >= 8 else 1
    near = sorted((edits(d, v), v) for v in eye)
    if near and near[0][0] <= room:
        return near[0][1]
    if d in vocab:
        return d
    near = sorted((edits(d, v), v) for v in vocab)
    return near[0][1] if near and near[0][0] <= room else d


WORD = re.compile(r'^(?:[a-z0-9][a-z0-9-]{1,30}\.)+[a-z]{2,10}$')


def read_bar(path):
    """-> (domain, raw text). The original file is only ever opened to read.

    A screenshot with tabs open shows other shops' domains in the tab strip,
    and the first one down the page is one of those, not the page you are
    looking at: reading the top of the band filed nine Max Mara products under
    boglioli.it. The address bar's text is set larger than a tab title, so the
    tallest domain wins, and the lowest of equals.
    """
    if pytesseract is None:
        return '', ''
    with Image.open(path) as im0:
        im = im0.convert('RGB')
        W, H = im.size
        band = im.crop((0, 0, W, max(60, int(H * BAND))))
    band = band.resize((band.width * 2, band.height * 2), Image.LANCZOS)
    try:
        d = pytesseract.image_to_data(band, output_type=pytesseract.Output.DICT)
    except Exception:
        return '', ''
    best, words = None, []
    for i, t in enumerate(d['text']):
        t = (t or '').strip()
        if t:
            words.append(t)
        t = t.lower().strip('/')
        if not WORD.match(t):
            continue
        try:
            conf = float(d['conf'][i])
        except (TypeError, ValueError):
            conf = -1
        if conf < 40:
            continue
        key = (d['height'][i], d['top'][i])
        if best is None or key > best[0]:
            best = (key, t)
    return (domain_of(best[1]) if best else ''), ' '.join(words)[:200]


def main():
    batches = json.load(open(CAT + '/batches.json'))
    try:
        out = json.load(open(OUT))
    except (FileNotFoundError, json.JSONDecodeError):
        out = {'images': {}, 'batches': {}}
    imgs = out.setdefault('images', {})
    if '--redo' in sys.argv:                 # re-read the domains off cached text
        for v in imgs.values():
            v['domain'] = domain_of(v.get('raw', ''))
    todo = [im for b in batches for im in b['images'] if im not in imgs]
    print(f'{len(todo)} screenshots to read, {len(imgs)} already read', flush=True)
    for k, path in enumerate(todo, 1):
        if not os.path.exists(ROOT + '/' + path):
            imgs[path] = {'domain': '', 'raw': 'missing'}
            continue
        d, raw = read_bar(ROOT + '/' + path)
        imgs[path] = {'domain': d, 'raw': raw}
        if k % 20 == 0 or k == len(todo):
            json.dump(out, open(OUT, 'w'), indent=1)
            print(f'  {k}/{len(todo)}', flush=True)
    vocab, eye = vocabulary(), eye_read()
    for v in imgs.values():
        v['domain'] = snap(v.get('domain', ''), vocab, eye)
    per = {}
    for b in batches:
        c = collections.Counter(imgs.get(i, {}).get('domain', '') for i in b['images'])
        c.pop('', None)
        bid = b['batch_id']
        if not c:
            per.setdefault(bid, {'domain': '', 'n': 0, 'of': 0})
            per[bid]['of'] += len(b['images'])
            continue
        e = per.setdefault(bid, {'counts': collections.Counter(), 'of': 0})
        e.setdefault('counts', collections.Counter()).update(c)
        e['of'] += len(b['images'])
    final = {}
    for bid, e in per.items():
        c = e.get('counts')
        if not c:
            final[bid] = {'domain': '', 'n': 0, 'of': e['of'], 'others': []}
            continue
        d, n = c.most_common(1)[0]
        final[bid] = {'domain': d, 'n': n, 'of': e['of'],
                      'others': [k for k, _ in c.most_common()[1:]]}
    out['batches'] = final
    json.dump(out, open(OUT, 'w'), indent=1)
    got = sum(1 for v in final.values() if v['domain'])
    split = sum(1 for v in final.values() if v['others'])
    print(f'{got} of {len(final)} batches have a domain; {split} batches disagree with themselves')
    print(collections.Counter(v['domain'] for v in final.values() if v['domain']).most_common(12))


if __name__ == '__main__':
    main()
