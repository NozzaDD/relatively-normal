"""One question per batch where the brand is not legible — not one per product."""
import sys, os, csv, collections, json, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CAT = ROOT + '/content/catalogue'
THUMBS = CAT + '/brand-questions'


def main():
    rows = list(csv.DictReader(open(CAT + '/products.csv')))
    by = collections.defaultdict(list)
    for r in rows:
        by[r['batch_id']].append(r)
    os.makedirs(THUMBS, exist_ok=True)
    L = ['# brand-questions.md', '',
         'One question per shop batch, not per product — a batch is a run of screenshots',
         'from the same shop, so one answer fills in every row in it. Numbered so you can',
         'answer in one message: *1 Toteme, 4 no idea, 7 Lemaire*.', '',
         'Nothing here is guessed into the catalogue. Where I had to guess, the row says',
         '`guessed` and the evidence is below.', '']
    n = 0
    for bid, rs in sorted(by.items()):
        unknown = [r for r in rs if r['brand_confidence'] in ('input needed', 'guessed')]
        if not unknown:
            continue
        n += 1
        guessed = [r for r in rs if r['brand_confidence'] == 'guessed']
        given = {r['brand'] for r in rs if r['brand_confidence'] == 'given'}
        shop = rs[0]['shop'] or 'not legible'
        pics = []
        for r in unknown[:2]:
            if not r['asset_path']:
                continue
            with Image.open(ROOT + '/' + r['asset_path']) as im:
                t = im.convert('RGB')
                t.thumbnail((300, 300), Image.LANCZOS)
                p = f'{THUMBS}/{r["product_id"]}.jpg'
                t.save(p, 'JPEG', quality=80, optimize=True)
            pics.append('<img src="%s" width="150">' % urllib.parse.quote('brand-questions/%s.jpg' % r['product_id']))
        L += ['### %d. Batch `%s` — %d product%s' % (n, bid, len(unknown), '' if len(unknown) == 1 else 's'),
              '', ' '.join(pics) or '*(no usable image)*', '',
              '- **Shop text on the page:** %s' % shop,
              '- **Layout:** %s' % rs[0]['shop_type'],
              '- **Brands legible elsewhere in this batch:** %s' % (', '.join(sorted(given)) or 'none'),
              '- **My best guess:** %s' % (guessed[0]['brand'] if guessed
                                           else '*none — nothing in the batch names a brand*'),
              '- **Evidence:** %s' % ('the shop is mono-brand and every legible brand in the batch is the same'
                                      if guessed else 'a multi-brand layout tells you the retailer, not the brand'),
              '- **Products waiting on this:** %s' % ', '.join(r['product_id'] for r in unknown),
              '']
    open(CAT + '/brand-questions.md', 'w').write('\n'.join(L) + '\n')
    print(n, 'questions')


if __name__ == '__main__':
    main()
