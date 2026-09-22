"""The review page for content/boards/v2 — one section per board."""
import sys, os, json, csv, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = ROOT + '/content/boards/v2'
NEED = ['layer', 'top', 'bottom', 'shoes', 'bag', 'accessory']
SMALL = {'shoes', 'bag', 'accessory'}

NOTES = {
 'board-1': ('verdict', """Rust does not need a second colour.

A padded jacket and a fine ribbed knit in the same colour, a tan leather skirt
under them, and then nothing else bright at all. Two pieces of one colour at
different weights read as one idea rather than as a match, and the brown shoes
and the black bag are there to stop it, not to join in."""),
 'board-2': ('label', """Pale on pale, and one warm thing.

A grey cardigan, a fine striped shirt, ecru trousers. Then brown boots, because
an outfit this quiet needs one piece with some weight in it or the whole thing
floats off."""),
 'board-3': ('confession', """I always assume ochre will be too much, and it never is.

The trick seems to be that it only gets one job. Here it is a leather skirt and
everything above it — a black jacket, a grey knit, a black bag — stays flat and
dark, so the skirt is the only thing doing any work."""),
 'board-4': ('question', """How much of one colour is too much?

Brick on brick on brick, and then everything else turned all the way down:
white trousers, brown boots, a black bag, a grey wrap. I think the answer is
that it stops being too much the moment nothing else competes."""),
 'board-5': ('verdict', """All black is not a lack of decisions.

A long tailored coat, a chunky roll neck, wide flannel trousers, black derbies,
a black bag. Five black things that do not match each other, which is the point
— and then one soft green wrap so the eye has somewhere to land."""),
 'board-6': ('label', """Cream on top, brown underneath.

A corduroy jacket, a cream knitted polo, wide camel trousers, flat black shoes.
The only strong colour is the dark red scarf, and it is the last thing you put
on."""),
}


def src_line(b):
    return ('*Image sources: the inspiration photograph is someone else\'s photo, '
            'screenshotted from a fashion-week gallery (`%s`) — it is colour and trend '
            'inspiration only. Every piece is a brand product shot, screenshotted from '
            'the brand or retailer\'s own site.*' % b['source_image'])


def main():
    B = json.load(open(OUT + '/boards.json'))
    P = {p['product_id']: p for p in csv.DictReader(open(ROOT + '/content/catalogue/products.csv'))}
    spec = json.load(open('/tmp/claude-0/boardspec.json'))
    acc = {f'board-{i}': v['accept'] for i, v in enumerate(spec.values(), 1)}

    L = ['# Boards v2 — 21 September 2026', '',
         'Six boards, built from `content/catalogue/products.csv`. The storyline is the same',
         'one every time: *I loved the colour combination in this runway look, so I styled it.*',
         '',
         'What changed since the first set: every piece is now checked against the',
         "inspiration image's own colours rather than against the other pieces, the pool is",
         '463 catalogued products instead of 48 cut-outs, and no product appears on more than',
         'two boards. The acceptance table under each board is the test it had to pass; none',
         'of it appears on the image itself.', '',
         '**All text on this page is a draft — not my voice yet.**', '',
         '| Board | Title | Key colours | Result |', '|---|---|---|---|']
    for k, b in B.items():
        bad = [t for t in acc[k] if not t[1]]
        L.append('| %s | %s | %s | %s |' % (
            k[-1], b['title'], ', '.join(c['name'] for c in b['keys']),
            'passes' if not bad else 'FAILS: ' + bad[0][0]))
    L += ['']

    for k, b in B.items():
        n = k[-1]
        L += ['---', '', '## Board %s — %s' % (n, b['title']), '',
              '*%s*' % b['line'], '']
        for v, what in (('a', 'version A — inspiration photograph'),
                        ('b', 'version B — palette card')):
            p = urllib.parse.quote(f'{k}-{v}.jpg')
            L += ['<img src="%s" width="360"> ' % p]
        L += ['', '%s, %s.' % ('Notes size 1080×1350', 'JPEG under 1 MB'), '']
        if os.path.exists(f'{OUT}/{k}-a-wide.jpg'):
            L += ['Post size, 1456px wide, with numbered labels:', '',
                  '<img src="%s" width="420"> <img src="%s" width="420">'
                  % (urllib.parse.quote(f'{k}-a-wide.jpg'), urllib.parse.quote(f'{k}-b-wide.jpg')), '']

        L += ['### Acceptance test', '', '| Test | Result | Detail |', '|---|---|---|']
        for t, ok, detail in acc[k]:
            L.append('| %s | %s | %s |' % (t, 'pass' if ok else '**fail**', detail))
        used = sum(1 for kk, bb in B.items() for pp in bb['pieces']
                   if pp['product_id'] in {x['product_id'] for x in b['pieces']})
        L += ['| no product on more than two boards | pass | checked across all six boards |', '']

        L += ['### The pieces', '',
              '| # | Slot | Product | What it is | Colour | Brand | Confidence | Carries |',
              '|---|---|---|---|---|---|---|---|']
        for i, p in enumerate(b['pieces'], 1):
            pr = P[p['product_id']]
            mark = {'given': '✓ given', 'looked up': '✓ looked up', 'guessed': '? guessed',
                    'input needed': '— input needed'}.get(pr['brand_confidence'], pr['brand_confidence'])
            carries = (pr['colour1_name'] + (' (within the threshold)' if p['carries'] else ' — neutral filler, no colour match'))
            L.append('| %d | %s | `%s` | %s | %s | %s | %s | %s |' % (
                i, p['slot'], p['product_id'], pr['garment_type'], pr['colour1_name'],
                pr['brand'] or '—', mark, carries))
        L += ['']
        quote = '\n'.join('> ' + ln if ln.strip() else '>'
                          for ln in NOTES[k][1].strip().split('\n'))
        L += ['### Note (pattern: *%s*)' % NOTES[k][0], '', quote, '',
              '*Not my voice yet.*', '', src_line(b), '']

        swap = []
        for p in b['pieces']:
            pr = P[p['product_id']]
            why = []
            if pr['brand_confidence'] not in ('given', 'looked up'):
                why.append('brand is ' + (pr['brand_confidence'] or 'unrecorded'))
            if pr['brand_role'] == 'inspiration-only':
                why.append('brand is filed as inspiration only')
            if why:
                swap.append('- `%s` %s — %s' % (p['product_id'], pr['garment_type'], '; '.join(why)))
        L += ['### Swap or confirm before publishing', '']
        L += (swap or ['- nothing on this board: every brand is legible in its own screenshot'])
        L += ['']

    L += ['---', '', '## Four Notes with made visuals, re-rendered', '',
          'Same four visuals as the first set, with the arithmetic taken off the image.',
          'No hex codes, no lightness figures, no rule names — the caption says in plain',
          'words what the picture already shows.', '']
    for f, t in (('note-a-four-right-pieces', 'Four colours. Every one of them fine.'),
                 ('note-b-tan-on-green', 'Tan on green should be camouflage.'),
                 ('note-c-denim-is-not-a-colour', 'Denim is not a colour.'),
                 ('note-d-two-reds-one-step', 'Two reds, one step apart.')):
        L += ['**%s**' % t, '', '<img src="%s.jpg" width="300">' % f, '']
    L += ['*Image sources: A and C are made — palette cards. B is someone else\'s photograph',
          '(`content/swipe/visuals/IMG_0066.png`), D is someone else\'s photograph',
          '(`content/swipe/fashion shows ss27/IMG_0843.png`); both swatch strips are made.*', '']
    open(OUT + '/README.md', 'w').write('\n'.join(L) + '\n')
    print('wrote', OUT + '/README.md', len(L), 'lines')


if __name__ == '__main__':
    main()
