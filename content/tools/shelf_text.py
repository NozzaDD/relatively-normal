"""Page text on the shelf: OCR every shelf picture as the tile shows it.

Point 3 of 24 September. Some shelf products were cut from a product page's
colour-swatch thumbnails, or from a crop that took in the buy panel, and their
picture carries the page's own words: "Colore", "Taglia 36", size numbers, a
price. This reads every picture on the shelf — the cut-out, or the box she chose
on the full photo — and lists the ones with page text in them, with the words.

A word sitting ON the garment (a printed logo, a slogan tee) is not page text.
What decides is the vocabulary and the shape of the text, never the colour
(CLAUDE.md rule 6 is about fibres, but the same caution applies): a page word
("colore", "taglia", "size", "add to bag"), a price, or a run of size labels.
A lone confident word that is none of those is recorded but does not send the
product back; the contact sheet shows them for a person to look at.

    python3 content/tools/shelf_text.py              # read, write _shelf_text.json
    python3 content/tools/shelf_text.py --sheets DIR # and contact sheets of the hits
    python3 content/tools/shelf_text.py --cached     # re-judge from the cached words

Writes content/catalogue/_shelf_text.json: per product, the words read, the
verdict and the reason. `send_to_review.py` turns the verdicts into
asset-choices.json entries and a review-sends.json version.
"""
import json, os, re, sys, argparse
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
CAT = ROOT + '/content/catalogue'
STUDIO = ROOT + '/studio'
OUT = CAT + '/_shelf_text.json'

# words a product page prints round its photographs, in the shops' languages
PAGE_WORDS = {
    'colore', 'colori', 'colour', 'colours', 'color', 'colors', 'farbe', 'farben', 'couleur',
    'taglia', 'taglie', 'size', 'sizes', 'grösse', 'größe', 'grosse', 'groesse', 'taille',
    'aggiungi', 'carrello', 'cart', 'basket', 'warenkorb', 'bag', 'add', 'buy', 'kaufen',
    'shop', 'select', 'seleziona', 'wählen', 'wahlen', 'choose', 'guide', 'guida', 'sold',
    'esaurito', 'ausverkauft', 'description', 'descrizione', 'beschreibung', 'details',
    'dettagli', 'composition', 'composizione', 'material', 'materiale', 'delivery',
    'spedizione', 'versand', 'returns', 'resi', 'wishlist', 'preferiti', 'new', 'nuovo',
    'price', 'prezzo', 'preis', 'eur', 'chf', 'usd', 'gbp', 'fit', 'vestibilità',
    'model', 'modella', 'wears', 'indossa', 'trägt',
}
PRICE = re.compile(r'^(?:[€$£]\s?\d|\d+[.,]\d{2}$|\d+\s?(?:€|chf|eur)$|chf\d)', re.I)
SIZE = re.compile(r'^(?:xxs|xs|s|m|l|xl|xxl|3[2-9]|4[0-8]|3[5-9][.,]5|one|os|tu)$', re.I)


def shelf_rows(products):
    """The shelf by default, as the desk's gate reads the catalogue (data.js onShelf)."""
    out = []
    for p in products:
        if p.get('hidden') or p.get('review') or p.get('duplicate_of'):
            continue
        if p.get('several') and p.get('choice') != 'custom':
            continue
        if p.get('clean') or p.get('choice'):
            out.append(p)
    return out


def shelf_picture(p):
    """The picture the shelf tile shows (data.js shelfView with no badge or filter),
    as a PIL image on white, and a word for what it is."""
    from PIL import Image
    ch = p.get('choice')
    imgs = p.get('images') or []
    i = p.get('image') or 0
    e = imgs[i] if i < len(imgs) else (p.get('full') or None)
    box = None
    path = STUDIO + '/' + p['asset']
    kind = 'cut-out'
    if ch == 'whole' and e and e.get('whole'):
        path, kind = STUDIO + '/' + e['whole']['path'], 'whole cut-out'
    elif ch in ('item', 'person', 'full', 'custom') and e:
        base = p.get('base') or 'photo'
        if base == 'whole' and e.get('whole'):
            path = STUDIO + '/' + e['whole']['path']
        elif base != 'asset':
            path = STUDIO + '/' + e['path']
        box = [0, 0, 1, 1] if ch == 'full' else (p.get('custom_box') if ch == 'custom'
                                                  else (e.get(ch) or (p.get('boxes') or {}).get(ch)))
        kind = f'{ch} box'
    im = Image.open(path)
    im.load()
    if box:
        W, H = im.size
        x, y, w, h = box
        im = im.crop((int(x * W), int(y * H), int((x + w) * W), int((y + h) * H)))
    if im.mode in ('RGBA', 'LA', 'P'):
        im = im.convert('RGBA')
        bg = Image.new('RGBA', im.size, (255, 255, 255, 255))
        bg.alpha_composite(im)
        im = bg
    return im.convert('RGB'), kind


def other_pictures(p):
    """The other pictures a tile can show — the image filter's picture type or
    Other picture (data.js pictureChoices, pictureOfType): each picture's whole
    cut-out, fabric close-ups and page text aside."""
    out = []
    for i, e in enumerate(p.get('images') or []):
        if e.get('type') in ('detail', 'text', 'other'):
            continue
        if e.get('whole'):
            out.append((i, STUDIO + '/' + e['whole']['path']))
    return out


def open_on_white(path):
    from PIL import Image
    im = Image.open(path).convert('RGBA')
    bg = Image.new('RGBA', im.size, (255, 255, 255, 255))
    bg.alpha_composite(im)
    return bg.convert('RGB')


def read_words(args):
    pid, p = args
    rec = read_one(pid, p, None)
    rec['pictures'] = {}
    for i, path in other_pictures(p):
        rec['pictures'][str(i)] = read_one(pid, p, path)
    return pid, rec


def read_one(pid, p, path):
    import pytesseract
    from PIL import Image
    try:
        im, kind = (shelf_picture(p) if path is None else (open_on_white(path), 'whole cut-out'))
    except Exception as e:
        return dict(error=f'{type(e).__name__}: {e}')
    W, H = im.size
    # page type is 11-16 px on a screenshot; at 1100 px on the long side even
    # a 300 px cut-out's words are big enough, and tesseract stays quick
    k = 1100 / max(W, H)
    im = im.resize((max(1, int(W * k)), max(1, int(H * k))), Image.LANCZOS)
    words = []
    # sparse text only, English letters (the Italian and German page words are
    # plain Latin letters), 25 s at most: a knit texture kept psm 6 busy for a
    # quarter of an hour on the first run
    for psm in (11,):
        try:
            d = pytesseract.image_to_data(im, lang='eng', config=f'--psm {psm}',
                                          output_type=pytesseract.Output.DICT, timeout=25)
        except RuntimeError:
            return dict(kind=kind, size=[W, H], words=words, timeout=True)
        except Exception as e:
            return dict(error=f'tesseract: {e}')
        for j, t in enumerate(d['text']):
            t = (t or '').strip()
            try:
                c = float(d['conf'][j])
            except (TypeError, ValueError):
                continue
            if not t or c < 60:
                continue
            words.append(dict(t=t, c=round(c), x=round(d['left'][j] / im.width, 3),
                              y=round(d['top'][j] / im.height, 3),
                              h=round(d['height'][j] / im.height, 3), psm=psm))
    return dict(kind=kind, size=[W, H], words=words)


def clean_token(t):
    return re.sub(r'^[^\w€$£]+|[^\w€$£]+$', '', t.lower())


LONG_PAGE_WORDS = sorted(w for w in PAGE_WORDS if len(w) >= 5)


def fragment(t):
    """A page word cut by the crop: "Guid" of "Guida", "Tagl" of "Taglie"
    read at the box's edge. Four letters at least, and the start or end of a
    page word of five or more — "tag" alone is too common on a garment."""
    return len(t) >= 4 and t.isalpha() and any(w.startswith(t) or w.endswith(t) for w in LONG_PAGE_WORDS)


def judge(rec):
    """Page text or not, and why. Deliberately narrow: a false 'yes' sends a
    good product to Review, where she can put it back with one tap; a false
    'no' leaves page text on the shelf, which is what the owner asked to fix."""
    if not rec or rec.get('error'):
        return False, ''
    seen = {}
    for w in rec['words']:
        t = clean_token(w['t'])
        if len(t) < 1:
            continue
        # one reading per word place: psm 11 and 6 often read the same word
        key = (t, round(w['x'], 2), round(w['y'], 2))
        seen[key] = max(seen.get(key, 0), w['c'])
    toks = [(t, c) for (t, _x, _y), c in seen.items()]
    page = sorted({t for t, c in toks if c >= 70 and len(t) >= 3 and (t in PAGE_WORDS or fragment(t))})
    prices = sorted({t for t, c in toks if PRICE.match(t) and c >= 70})
    sizes = sorted({t for t, c in toks if SIZE.match(t) and c >= 80 and len(t) >= 2})
    why = []
    if page:
        why.append('page words: ' + ', '.join(page))
    if prices:
        why.append('price: ' + ', '.join(prices))
    if len(sizes) >= 2:
        why.append('size labels: ' + ', '.join(sizes))
    return bool(why), '; '.join(why)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sheets', help='write contact sheets of the hits here')
    ap.add_argument('--cached', action='store_true', help='re-judge the words already read')
    ap.add_argument('--only', nargs='*', help='product ids')
    a = ap.parse_args()
    products = json.load(open(STUDIO + '/data/products.json'))
    rows = shelf_rows(products)
    if a.only:
        rows = [p for p in rows if p['product_id'] in set(a.only)]
    old = {}
    if os.path.exists(OUT):
        old = json.load(open(OUT)).get('products', {})
    if a.cached:
        res = {pid: old[pid] for pid in (p['product_id'] for p in rows) if pid in old}
    else:
        os.environ['OMP_THREAD_LIMIT'] = '1'
        done = lambda pid: (old.get(pid) or {}).get('words_v') == 3
        todo = [(p['product_id'], p) for p in rows if not done(p['product_id'])]
        res = {p['product_id']: old[p['product_id']] for p in rows if done(p['product_id'])}
        with Pool(os.cpu_count() or 2) as pool:
            for n, (pid, rec) in enumerate(pool.imap_unordered(read_words, todo, chunksize=4), 1):
                rec['words_v'] = 3
                res[pid] = rec
                if n % 100 == 0:
                    json.dump(dict(products={**old, **res}), open(OUT, 'w'), indent=0)
                    print(f'  {n}/{len(todo)} read', flush=True)
    hits, pic_hits = {}, {}
    for pid, rec in res.items():
        yes, why = judge(rec)
        rec['page_text'] = yes
        rec['why'] = why
        if yes:
            hits[pid] = why
        for i, r2 in (rec.get('pictures') or {}).items():
            y2, w2 = judge(r2)
            r2['page_text'], r2['why'] = y2, w2
            if y2:
                pic_hits[f'{pid}#{i}'] = w2
    merged = {**old, **res}
    json.dump(dict(read=len(res), hits=len(hits), picture_hits=pic_hits, products=merged), open(OUT, 'w'), indent=0)
    by_id = {p['product_id']: p for p in products}
    print(f'{len(res)} shelf products read, {len(hits)} whose tile has page text; '
          f'{len(pic_hits)} other pictures with page text')
    for pid, why in sorted(hits.items()):
        print(' ', pid, by_id[pid]['shop'], '—', why)
    for k, why in sorted(pic_hits.items()):
        print('  picture', k, by_id[k.split('#')[0]]['shop'], '—', why)
    if a.sheets:
        sys.path.insert(0, HERE)
        from contact_sheet import sheet
        os.makedirs(a.sheets, exist_ok=True)
        ids = sorted(hits)
        for k in range(0, len(ids), 30):
            cells = []
            for pid in ids[k:k + 30]:
                p = by_id[pid]
                im, kind = shelf_picture(p)
                tmp = f'{a.sheets}/_t_{pid}.jpg'
                im.save(tmp, quality=85)
                cells.append(dict(path=tmp, label=f'{pid} {p["shop"]}\n{kind}\n{hits[pid][:44]}'))
            sheet(cells, f'{a.sheets}/shelf-text-{k // 30 + 1}.jpg', cols=6, cell=220,
                  title=f'page text on the shelf {k + 1}-{k + len(cells)} of {len(ids)}')
            for c in cells:
                os.remove(c['path'])


if __name__ == '__main__':
    main()
