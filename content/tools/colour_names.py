"""A fixed, closed vocabulary of colour families and plain colour names.

Families are broad enough to filter by and narrow enough to be meaningful.
Rust lives in `orange`, plum lives in `purple` — they are never the same family.

Assignment runs on CIELAB LCh plus the engine's relative chroma, so a colour is
a neutral because it uses little of the saturation available at its lightness,
not because it happens to be pale.
"""
import os, sys
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
for _p in (_HERE, _ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)
from engine import colour as C          # noqa: E402

FAMILIES = ['black', 'white', 'grey', 'warm neutral', 'cool neutral', 'brown',
            'red', 'orange', 'yellow', 'green', 'blue', 'purple', 'pink']

# chromatic names: (family, name, hue_lo, hue_hi, L_lo, L_hi, C_min, C_max)
# The chroma gate matters most in the warm band: a low-chroma colour at hue 70
# is a brown, the same hue at high chroma is an ochre.
_CHROMATIC = [
    ('red',    'oxblood',      345, 25,   0, 28,  6, 99),
    ('red',    'burgundy',     345, 25,  28, 42, 10, 99),
    ('red',    'brick',         15, 35,  35, 55, 25, 99),
    ('red',    'red',          345, 35,  42, 70, 30, 99),
    ('orange', 'rust',          25, 55,   0, 50, 28, 99),
    ('orange', 'terracotta',    25, 55,  50, 65, 28, 99),
    ('orange', 'apricot',       35, 62,  65, 100, 22, 99),
    ('brown',  'espresso',      30, 95,   0, 22,  4, 99),
    ('brown',  'chocolate',     30, 82,  22, 38,  4, 28),
    ('brown',  'tobacco',       35, 82,  30, 54,  4, 26),
    ('brown',  'tan',           45, 95,  52, 74,  4, 30),
    ('yellow', 'ochre',         58, 95,  35, 62, 26, 99),
    ('yellow', 'mustard',       75, 105, 55, 78, 30, 99),
    ('yellow', 'gold',          58, 100, 62, 82, 30, 99),
    ('yellow', 'butter',        75, 110, 78, 100, 14, 99),
    ('green',  'olive',         78, 132,  0, 52,  8, 99),
    ('green',  'moss',         100, 145, 30, 62, 12, 99),
    ('green',  'sage',          95, 165, 55, 88,  6, 99),
    ('green',  'forest',       130, 185,  0, 42,  8, 99),
    ('green',  'emerald',      140, 195, 35, 72, 14, 99),
    ('blue',   'petrol',       185, 235,  0, 45,  8, 99),
    ('blue',   'navy',         230, 305,  0, 28,  5, 99),
    ('blue',   'denim blue',   235, 295, 28, 54,  8, 99),
    ('blue',   'steel blue',   195, 268, 40, 72,  6, 99),
    ('blue',   'sky',          195, 285, 70, 100,  6, 99),
    ('purple', 'aubergine',    288, 348,  0, 25,  8, 99),
    ('purple', 'plum',         300, 358, 20, 46,  8, 99),
    ('purple', 'violet',       278, 322, 35, 66, 14, 99),
    ('purple', 'lilac',        278, 332, 60, 100,  8, 99),
    ('purple', 'mauve',        318, 358, 46, 76,  6, 99),
    ('pink',   'raspberry',    338, 15,  30, 60, 22, 99),
    ('pink',   'dusty rose',   348, 35,  55, 82,  8, 28),
    ('pink',   'blush',        348, 40,  75, 100,  6, 99),
]


def _in_hue(h, lo, hi):
    return (lo <= h < hi) if lo <= hi else (h >= lo or h < hi)


def _neutral_name(L, Cc, h):
    if L <= 19:
        # a dark brown is not black. By eye, 6 of 60 sampled products came back
        # black when the garment was plainly a very dark brown, so a warm hue with
        # real chroma keeps its family down here too.
        if Cc >= 6 and _in_hue(h, 25, 105):
            return ('brown', 'espresso')
        return ('black', 'black' if Cc < 4 else 'off-black')
    if L >= 90:
        return ('white', 'white' if Cc < 4 else 'off-white')
    warm = _in_hue(h, 30, 110)
    if L >= 78:
        return ('warm neutral', 'cream') if warm else ('cool neutral', 'pale grey')
    if warm:
        if L >= 62:
            return ('warm neutral', 'oatmeal')
        if L >= 45:
            return ('warm neutral', 'stone')
        return ('warm neutral', 'taupe')
    if L >= 62:
        return ('grey', 'light grey')
    if L >= 38:
        return ('grey', 'mid grey')
    return ('grey', 'dark grey')


def _table(L, Cc, h):
    best = None
    for fam, name, lo, hi, Llo, Lhi, Cmin, Cmax in _CHROMATIC:
        if _in_hue(h, lo, hi) and Llo <= L < Lhi and Cmin <= Cc < Cmax:
            span = ((hi - lo) % 360) or 360
            mid = (lo + span / 2) % 360
            d = abs(((h - mid + 180) % 360) - 180) / max(1, span / 2)
            d += abs(L - (Llo + Lhi) / 2) / max(1, (Lhi - Llo) / 2) * 0.5
            if best is None or d < best[0]:
                best = (d, fam, name)
    return best


def classify(hex_str):
    """-> (family, name, L, C, h, relative_chroma, is_neutral)"""
    L, Cc, h = C.lab_to_lch(C.hex_to_lab(hex_str))
    rel = C.relative_chroma(L, Cc, h)
    # A pale blue jacket is blue. The engine's neutral flag is about how much of
    # the available chroma a colour uses, which is the right test for pairing and
    # the wrong one for naming: at high L* even an obvious sky blue comes out
    # under 0.15 and used to be filed as `cool neutral`, which then hid it from
    # every colour match. So outside the warm band, where oatmeal and taupe
    # genuinely are neutrals, a colour with real chroma keeps its own family and
    # only carries the neutral flag.
    if rel <= 0.15 and Cc >= 7 and not _in_hue(h, 20, 115):
        t = _table(L, Cc, h)
        if t:
            return (t[1], t[2], L, Cc, h, rel, True)
    if rel <= 0.15:                                   # combinations.md §5
        fam, nm = _neutral_name(L, Cc, h)
        return (fam, nm, L, Cc, h, rel, True)
    best = _table(L, Cc, h)
    if best:
        return (best[1], best[2], L, Cc, h, rel, False)
    # a chromatic that no row fits — almost always a pale warm or a soft grey.
    # Name it the way the neutral branch would; it keeps the vocabulary closed.
    fam, nm = _neutral_name(L, Cc, h)
    return (fam, nm, L, Cc, h, rel, False)


if __name__ == '__main__':
    for hx in ('402427', 'AC431E', '9D7140', '64682E', '4F6684', 'E2C0C4',
               'BB9974', 'E8E7E4', '16151A', '8F8B81', '341A2C', 'AA7C2F', '6A5540'):
        f, n, L, Cc, h, rel, nt = classify(hx)
        print(f'#{hx}  {f:14}{n:14} L{L:5.1f} C{Cc:5.1f} h{h:6.1f} rel{rel:.2f} {"NEUTRAL" if nt else ""}')
