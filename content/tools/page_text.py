"""Read what a product page says about itself: name, colour or wash, product ID, shop.

Two screenshots are of one product when the page says so, not when the pages
look alike. Consecutive pages from one shop share every pixel of their layout,
so layout cannot tell a 501 '90s from a 501 Curve; the name printed above the
price can. This reads, per screenshot:

  name      the product's name: the line(s) set just above the first price in
            the buy panel, or, where a page sets the price first, just below it
  colour    the page's colour or wash name: what follows "Colour"/"Color"/
            "Farbe"/"Wash", or the part after " | " in a name like
            "FRANKIE Faux Fur Jacket | Olive"
  pid       a visible product number: "Product ID: 485303", "Ref. 1402/850",
            "Art.-Nr. 12345", "Style # AB123"
  domain    the shop, from Safari's address bar (url_bar.py). Safari shows the
            domain only, never the path, so it separates shops, not products.

A field that is not legible is empty, and an empty field never disagrees with
anything. `agree(a, b)` says which legible fields two screenshots disagree on.

Writes content/catalogue/_page_text.json, keyed by image path: the OCR lines
with their positions, so the fields can be read again from them without
running tesseract twice, and a later reader can check what was read. Needs tesseract;
OMP_THREAD_LIMIT=1 is set here because tesseract's own threads make four
parallel readers forty times slower, not four times faster.

  python3 content/tools/page_text.py [paths...]      # read what is not read yet
"""
import os, sys, re, json, difflib
os.environ.setdefault('OMP_THREAD_LIMIT', '1')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CAT = ROOT + '/content/catalogue'
OUT = CAT + '/_page_text.json'

CUR = r'(?:€|EUR|CHF|£|GBP|\$|USD|SEK|DKK|kr)'
PRICE_RE = re.compile(r'(?:' + CUR + r'\s?\d{1,5}(?:[.,\']\d{2,3})*(?:[.,]\d{2})?'
                      r'|\d{1,5}(?:[.,\']\d{3})*(?:[.,]\d{2})?\s?' + CUR + r')')
COLOUR_KEY = re.compile(r'^\s*(?:selected\s+)?(?:colou?r|farbe|couleur|colore|kleur|wash)\b\s*[:;\-]?\s*(.*)$', re.I)
PID_RE = re.compile(r'(?:product\s*(?:id|code|no\.?|number)|referenz|r[ée]f[ée]rence|ref\.?|art(?:ikel)?\.?\s*-?\s*(?:nr|no)\.?'
                    r'|style\s*(?:no\.?|#|number|code)|item\s*(?:no\.?|#|number)|sku|model(?:l)?\s*(?:nr|no)\.?)'
                    r'\s*[:#.]?\s*([A-Z0-9][A-Z0-9/\-.]{4,})', re.I)
# lines that sit near a price and are never a name
NOT_NAME = re.compile(r'(klarna|shipping|delivery|returns|size|select|add to|bag|basket|cart|'
                      r'review|rating|stars|tax|vat|incl|included|free|wishlist|colou?r\b|'
                      r'farbe|pay later|interest|member|sale|new in|back|home|women|men\b|'
                      r'abonnieren|sparen|newsletter|subscribe|sign up|e-mail|payments|filter|sort)', re.I)
RATING = re.compile(r'[★☆*]{2,}|\(\d+\)\s*$|^\W*[kK*]{3,}')
NAME_MAX = 70                       # longer is a carousel's captions run together


def clean_name(t):
    t = PID_RE.split(t)[0] if PID_RE.search(t) else t
    # a provenance label set on the name's line, and swatch rows read as text
    t = re.sub(r'^\s*made in \w+\s*', '', t, flags=re.I)
    t = ' '.join(w for w in t.split() if not (w.isalpha() and w.isupper() and len(set(w)) <= 2 and len(w) >= 3))
    m = PRICE_RE.search(t)
    if m:
        t = t[:m.start()]
    return t.strip(' |-')


def clean_colour(v):
    v = re.sub(r"[^\w\s\-()%:'/]", ' ', v)
    toks = v.split()
    while toks and not toks[0].isdigit() and len(toks[0]) <= 3 and sum(ch.isalpha() for ch in toks[0]) < 3:
        toks.pop(0)
    # a heart or a chevron after the name reads as "9" or "v"
    while len(toks) > 1 and len(toks[-1]) == 1:
        toks.pop()
    return ' '.join(toks)[:80]


def load():
    try:
        return json.load(open(OUT))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def norm(s):
    return re.sub(r'[^a-z0-9]', '', (s or '').lower())


def _letters(s):
    return sum(ch.isalpha() for ch in s)


def _junk(tok):
    """OCR's reading of a row of swatches or icons: EEEE, ERR, REE, SE."""
    t = re.sub(r'[^A-Za-z]', '', tok)
    return len(t) < 3 or len(set(t.lower())) <= 2


def words(s):
    return [w.lower() for w in re.findall(r"[^\W\d_][\w'’\-]*", s or '') if not _junk(w)]


# words that only ever name a colour: a "name" made of nothing else is the
# colour line read as the name (Colorful Standard sets "SOFT YELLOW" above the
# price, Longchamp its scarf's "Mokka", tricot its "DARK NAVY")
COLOUR_WORDS = set('''
black white grey gray navy blue green red brown beige cream ivory ecru khaki camel olive
tan taupe sand stone charcoal burgundy bordeaux wine plum pink rose yellow orange rust
mustard ochre chocolate coffee mocha mokka cognac caramel natural nature oatmeal ecru
dark light pale deep soft heather melange mélange marl lava ocean pacific marine petrol
hunter dusty ultra violet purple lilac lavender mauve teal turquoise sky forest moss sage
emerald indigo denim chambray off nero bianco blu marrone grigio verde rosso beige panna
schwarz weiss weiß grau braun blau grün rot noir blanc gris bleu vert rouge marron
'''.split())


def colour_only(nm):
    ws = [w for w in re.findall(r"[^\W\d_]+", (nm or '').lower()) if len(w) > 2]
    return bool(ws) and all(w in COLOUR_WORDS for w in ws)


def name_ok(nm):
    """A name is words: two of four letters or more, or one of five. "New",
    "ARH" and "COs ae eas" are a badge, a logo and the header read as text."""
    if not nm or len(nm) > NAME_MAX:
        return False
    ws = [w for w in words(nm)]
    return sum(len(w) >= 4 for w in ws) >= 2 or any(len(w) >= 5 for w in ws)


def read_fields(lines, width):
    """name, colour, pid off a page's OCR lines (uniqlo_pages.lines_of shape)."""
    got = dict(name='', colour='', pid='', price='')
    # the price: the first line that is mostly a price, below the top chrome
    pi = None
    for i, l in enumerate(lines):
        t = l['text'].strip()
        m = PRICE_RE.search(t)
        if not m or l['top'] < 60:
            continue
        # a price line is short: the price plus a strike-through or a badge,
        # not a sentence about free shipping over CHF 85
        if len(t) - len(m.group(0)) > 24 or NOT_NAME.search(t.replace(m.group(0), '')) and len(t) > 30:
            continue
        pi = i
        got['price'] = m.group(0)
        break
    if pi is not None:
        p = lines[pi]
        name = []
        # above the price, in the same column: the name, possibly wrapped
        j, below = pi - 1, p
        while j >= 0 and len(name) < 3:
            l = lines[j]
            t = l['text'].strip()
            close = below['top'] - l['bottom'] < 2.8 * max(l['height'], 12)
            same_col = abs(l['left'] - p['left']) < max(60, 0.08 * width)
            if not (close and same_col):
                break
            if NOT_NAME.search(t) or _letters(t) < 3 or RATING.search(t):
                if name:
                    break
                below, j = l, j - 1
                continue
            name.insert(0, t)
            below, j = l, j - 1
        if not name:
            # a page that sets the price above the name
            j, above = pi + 1, p
            while j < len(lines) and len(name) < 2:
                l = lines[j]
                t = l['text'].strip()
                if l['top'] - above['bottom'] > 2.8 * max(l['height'], 12):
                    break
                if (abs(l['left'] - p['left']) >= max(60, 0.08 * width) or NOT_NAME.search(t)
                        or _letters(t) < 3 or RATING.search(t)):
                    break
                name.append(t)
                above, j = l, j + 1
        got['name'] = clean_name(' '.join(name))

    # the colour: after a Colour key, on its line or the next
    for i, l in enumerate(lines):
        m = COLOUR_KEY.match(l['text'])
        if not m:
            continue
        v = m.group(1).strip(' :;-')
        if _letters(v) < 3 and i + 1 < len(lines) and lines[i + 1]['top'] - l['bottom'] < 3 * l['height']:
            v = lines[i + 1]['text'].strip()
        v = clean_colour(v)
        if _letters(v) >= 4:
            got['colour'] = v
            break
    if not got['colour'] and ' | ' in got['name']:
        a, b = got['name'].rsplit(' | ', 1)
        if 0 < _letters(b) <= 24:
            got['name'], got['colour'] = a.strip(), clean_colour(b)
    if colour_only(got['name']):
        got['colour'] = got['colour'] or clean_colour(got['name'])
        got['name'] = ''
    if not name_ok(got['name']):
        got['name'] = ''
    if _letters(got['colour']) < 4:
        got['colour'] = ''
    for l in lines:
        m = PID_RE.search(l['text'])
        if m and sum(ch.isdigit() for ch in m.group(1)) >= 3:
            got['pid'] = m.group(1).strip('.-/')
            break
    return got


def read(path):
    from PIL import Image
    import imglib
    import uniqlo_pages as U
    with Image.open(ROOT + '/' + path) as im0:
        im = im0.convert('RGB')
    box = imglib.trim_chrome(im)
    page = im.crop(box)
    lines = U.lines_of(page)
    return dict(width=page.width, ocr=[dict(l) for l in lines])


def domains():
    try:
        return {k: v.get('domain', '') for k, v in json.load(open(CAT + '/_url_bars.json'))['images'].items()}
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return {}


def ensure(paths, jobs=4):
    """Read every path not read yet; returns the whole table."""
    have = load()
    todo = [p for p in paths if p not in have]
    if todo:
        from multiprocessing import Pool
        with Pool(jobs) as pool:
            for p, f in zip(todo, pool.imap(read, todo)):
                have[p] = f
        json.dump(have, open(OUT, 'w'), indent=0)
    dm = domains()
    out = {}
    for p in paths:
        f = read_fields(have[p]['ocr'], have[p]['width'])
        f['domain'] = dm.get(p, '')
        # the shop's own logo read as a name
        if f['name'] and f['domain'] and norm(f['name'].split()[0]) in norm(f['domain']):
            f['name'] = '' if len(words(f['name'])) <= 2 else f['name']
        out[p] = f
    return out


SIM = dict(name=0.8, colour=0.75, pid=0.9, domain=1.0)


def similar(a, b, cut):
    a, b = norm(a), norm(b)
    if not a or not b:
        return True
    if a == b:
        return True
    if cut >= 1.0:
        return False
    return difflib.SequenceMatcher(None, a, b).ratio() >= cut


def same_words(a, b):
    """Every real word of each is in the other, allowing OCR's misreadings
    (FOULONNE for FOULONNÉ). A colour set on the name's own line ("... DARK
    NAVY" against "... DARK GRAY") is a different product."""
    wa, wb = words(a), words(b)
    if not wa or not wb:
        return True
    near = lambda w, ws: any(difflib.SequenceMatcher(None, w, x).ratio() >= 0.8 for x in ws)  # noqa: E731
    return all(near(w, wb) for w in wa) and all(near(w, wa) for w in wb)


def disagree(a, b):
    """The legible fields on which two screenshots' pages say different things."""
    out = []
    for k, cut in SIM.items():
        if not (a.get(k) and b.get(k)):
            continue
        if not similar(a[k], b[k], cut):
            out.append(k)
        elif k == 'name' and not same_words(a[k], b[k]):
            out.append(k)
        elif k == 'colour' and colour_only(a[k]) and colour_only(b[k]) and not same_words(a[k], b[k]):
            # DARK NAVY and DARK GRAY are 0.75 alike letter by letter
            out.append(k)
    return out


def legible_in_both(a, b):
    return [k for k in SIM if a.get(k) and b.get(k) and k != 'domain']


if __name__ == '__main__':
    ps = sys.argv[1:]
    t = ensure(ps)
    for p in ps:
        f = t[p]
        print(os.path.basename(p), '|', f['name'], '|', f['colour'], '|', f['pid'], '|', f['price'], '|', f['domain'])
