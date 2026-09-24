"""A fixed, closed vocabulary of colour families and plain colour names.

Families are broad enough to filter by and narrow enough to be meaningful.
Rust lives in `orange`, plum lives in `purple` — they are never the same family.

Assignment runs on CIELAB LCh plus the engine's relative chroma, so a colour is
a neutral because it uses little of the saturation available at its lightness,
not because it happens to be pale.

Families follow hue and chroma (`_family`), with four named exceptions filed by
convention: cream (warm neutral), camel (brown), coral (orange) and teal (blue).
Until 24 Sept 2026 the family was whichever name row a colour fell inside, and
rows drawn for muted garments missed saturated colours: true red came out
orange, cobalt and turquoise grey. Below C* 12 those original rows still decide.
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

# Plain names inside each family: (family, name, hue_lo, hue_hi, L_lo, L_hi, C_min, C_max).
# These only NAME a colour once its family is decided; they never decide the
# family. A colour takes the first row of its family whose ranges hold it, and
# otherwise the nearest row of its family by hue and lightness.
_CHROMATIC = [
    ('red',    'oxblood',      345, 25,   0, 28,  6, 99),
    ('red',    'burgundy',     345, 30,  28, 42, 10, 99),
    ('red',    'brick',         20, 42,  35, 55, 25, 55),
    ('red',    'red',          345, 42,  38, 75, 30, 200),
    ('orange', 'rust',          42, 65,   0, 50, 28, 200),
    ('orange', 'terracotta',    42, 65,  50, 65, 28, 200),
    ('orange', 'apricot',       35, 70,  65, 100, 22, 200),
    ('orange', 'coral',         25, 45,  58, 100, 40, 200),
    ('brown',  'espresso',      20, 105,  0, 22,  4, 200),
    ('brown',  'chocolate',     20, 90,  22, 38,  4, 200),
    ('brown',  'tobacco',       35, 90,  38, 54,  4, 200),
    ('brown',  'tan',           40, 105, 54, 80,  4, 200),
    ('brown',  'camel',         65, 90,  55, 75, 25, 42),
    ('yellow', 'ochre',         58, 105, 35, 62, 26, 200),
    ('yellow', 'mustard',       75, 105, 55, 78, 30, 200),
    ('yellow', 'gold',          58, 100, 62, 82, 30, 200),
    ('yellow', 'butter',        75, 110, 78, 100, 14, 200),
    ('green',  'olive',         78, 132,  0, 52,  8, 200),
    ('green',  'moss',         100, 145, 30, 62, 12, 200),
    ('green',  'sage',          95, 165, 55, 88,  6, 60),
    ('green',  'lime',         105, 140, 70, 100, 60, 200),
    ('green',  'forest',       130, 180,  0, 42,  8, 200),
    ('green',  'emerald',      135, 180, 35, 72, 14, 200),
    ('blue',   'petrol',       175, 235,  0, 40,  8, 200),
    ('blue',   'teal',         175, 215, 40, 100,  6, 200),
    ('blue',   'navy',         230, 307,  0, 28,  5, 200),
    ('blue',   'cobalt',       255, 307, 25, 65, 45, 200),
    ('blue',   'denim blue',   235, 295, 28, 60,  8, 45),
    ('blue',   'steel blue',   215, 292, 40, 74,  6, 45),
    ('blue',   'sky',          215, 292, 70, 100,  6, 200),
    ('purple', 'aubergine',    288, 345,  0, 25,  8, 200),
    ('purple', 'plum',         300, 345, 20, 46,  8, 200),
    ('purple', 'violet',       285, 322, 35, 66, 14, 200),
    ('purple', 'lilac',        285, 332, 60, 100,  8, 200),
    ('purple', 'mauve',        318, 345, 46, 76,  6, 200),
    ('pink',   'raspberry',    335, 20,  30, 60, 22, 200),
    ('pink',   'hot pink',     335, 15,  45, 75, 55, 200),
    ('pink',   'dusty rose',   335, 45,  55, 82,  8, 28),
    ('pink',   'blush',        335, 45,  75, 100,  6, 200),
]


def _in_hue(h, lo, hi):
    return (lo <= h < hi) if lo <= hi else (h >= lo or h < hi)


# ------------------------------------------------------------ named exceptions
# Four colours whose family is a convention rather than a hue: each is a
# region of LCh that is filed by name before the hue rule runs.
def _exception(L, Cc, h):
    # cream: a warm off-white. Its relative chroma is high only because the
    # gamut is tiny near white, so the hue rule would call it a yellow.
    if L >= 85 and _in_hue(h, 60, 110) and 6 <= Cc < 22:
        return ('warm neutral', 'cream')
    # camel: a mid, moderately chromatic warm tan — a brown by convention.
    if 55 <= L < 75 and _in_hue(h, 65, 90) and 25 <= Cc < 42:
        return ('brown', 'camel')
    # coral: a light, clear red-orange — filed with orange, not red.
    if L >= 58 and _in_hue(h, 25, 45) and Cc >= 40:
        return ('orange', 'coral')
    # teal: the blue-green band, filed with blue (petrol when deep).
    if _in_hue(h, 175, 215):
        return ('blue', 'petrol' if L < 40 else 'teal')
    return None


# ------------------------------------------------------------ family by hue
def _family(L, Cc, h):
    """The family of a chromatic colour, from its CIELAB hue, chroma and
    lightness. Boundaries are in Lab h°, where sRGB red sits near 40°, yellow
    near 100°, cyan near 196° and the blue primary near 306°."""
    if _in_hue(h, 335, 345):
        return 'pink' if Cc >= 35 else 'purple'        # fuchsia vs plum, mauve
    if _in_hue(h, 345, 20):
        return 'red' if L < 38 else 'pink'             # burgundy vs raspberry, rose
    if _in_hue(h, 20, 42):
        if Cc >= 25:
            return 'red'                               # true red, tomato, cherry
        return 'pink' if L >= 55 else 'brown'          # a greyed light red reads pink
    if _in_hue(h, 42, 65):
        if Cc >= 45:
            return 'orange'
        if Cc < 28:
            return 'brown'
        return 'brown' if L < 50 else 'orange'         # cognac vs salmon
    yellow_top = 110 if L >= 80 else 105
    if _in_hue(h, 65, yellow_top):
        if Cc < 28:
            return 'brown'
        return 'brown' if (Cc < 45 and L < 52) else 'yellow'
    if _in_hue(h, yellow_top, 175):
        return 'green'
    if _in_hue(h, 175, 292):
        return 'blue'
    if _in_hue(h, 292, 307):
        return 'blue' if Cc >= 45 else 'purple'        # cobalt vs lavender
    return 'purple'


def _name_in(fam, L, Cc, h):
    rows = [r for r in _CHROMATIC if r[0] == fam]
    best = None
    for f, name, lo, hi, Llo, Lhi, Cmin, Cmax in rows:
        span = ((hi - lo) % 360) or 360
        mid = (lo + span / 2) % 360
        d = abs(((h - mid + 180) % 360) - 180) / max(1, span / 2)
        d += abs(L - (Llo + Lhi) / 2) / max(1, (Lhi - Llo) / 2) * 0.5
        fits = _in_hue(h, lo, hi) and Llo <= L < Lhi and Cmin <= Cc < Cmax
        key = (0 if fits else 1, d)
        if best is None or key < best[0]:
            best = (key, name)
    return best[1]


# Below this absolute chroma the original rows decide, exactly as before: they
# were tuned by eye on the catalogue's dark and greyed garments (navies at C* 6,
# espressos at C* 5), and those were not what went wrong. Above it, the family
# follows hue and chroma.
CHROMA_FLOOR = 12.0

# The original rows, unchanged: (family, name, hue_lo, hue_hi, L_lo, L_hi, C_min, C_max).
_LOW_CHROMA = [
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
    ('blue',   'denim blue',   235, 295, 28, 60,  8, 99),
    ('blue',   'steel blue',   195, 290, 40, 74,  6, 99),
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


def _low_chroma(L, Cc, h):
    best = None
    for fam, name, lo, hi, Llo, Lhi, Cmin, Cmax in _LOW_CHROMA:
        if _in_hue(h, lo, hi) and Llo <= L < Lhi and Cmin <= Cc < Cmax:
            span = ((hi - lo) % 360) or 360
            mid = (lo + span / 2) % 360
            d = abs(((h - mid + 180) % 360) - 180) / max(1, span / 2)
            d += abs(L - (Llo + Lhi) / 2) / max(1, (Lhi - Llo) / 2) * 0.5
            if best is None or d < best[0]:
                best = (d, fam, name)
    return (best[1], best[2]) if best else _neutral_name(L, Cc, h)


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


def classify(hex_str):
    """-> (family, name, L, C, h, relative_chroma, is_neutral)

    The neutral flag is the engine's (relative chroma <= 0.15, combinations.md
    §5) and is never changed here. Cream is filed first. Below C* 12 the
    original rows decide, as they always have. Above it the family follows hue
    and chroma (_family), after the named exceptions for camel, coral and teal."""
    L, Cc, h = C.lab_to_lch(C.hex_to_lab(hex_str))
    rel = C.relative_chroma(L, Cc, h)
    neutral = rel <= 0.15
    ex = _exception(L, Cc, h)
    if ex and ex[1] == 'cream':
        return (ex[0], ex[1], L, Cc, h, rel, neutral)
    if Cc < CHROMA_FLOOR:
        if neutral:
            # A pale blue jacket is blue: outside the warm band a neutral with
            # real chroma keeps its hue family and only carries the flag; in the
            # warm band oatmeal and taupe genuinely are neutrals.
            if Cc >= 7 and not _in_hue(h, 20, 115):
                fam, nm = _low_chroma(L, Cc, h)
                if fam in ('grey', 'cool neutral', 'white', 'black', 'warm neutral'):
                    fam, nm = _neutral_name(L, Cc, h)
                return (fam, nm, L, Cc, h, rel, True)
            fam, nm = _neutral_name(L, Cc, h)
            return (fam, nm, L, Cc, h, rel, True)
        fam, nm = _low_chroma(L, Cc, h)
        return (fam, nm, L, Cc, h, rel, False)
    if neutral and _in_hue(h, 20, 115):
        fam, nm = _neutral_name(L, Cc, h)
        return (fam, nm, L, Cc, h, rel, True)
    if ex:
        return (ex[0], ex[1], L, Cc, h, rel, neutral)
    fam = _family(L, Cc, h)
    return (fam, _name_in(fam, L, Cc, h), L, Cc, h, rel, neutral)


if __name__ == '__main__':
    for hx in ('402427', 'AC431E', '9D7140', '64682E', '4F6684', 'E2C0C4',
               'BB9974', 'E8E7E4', '16151A', '8F8B81', '341A2C', 'AA7C2F', '6A5540',
               'D0021B', '2540B8', '0047FF', '3FBFBF', 'FF4F9A', 'B5693C', '1F5F63',
               'C19A6B', 'F0766B', 'EFE6D3', 'F0EBE0', '8E44FF', 'B9A9D6'):
        f, n, L, Cc, h, rel, nt = classify(hx)
        print(f'#{hx}  {f:14}{n:14} L{L:5.1f} C{Cc:5.1f} h{h:6.1f} rel{rel:.2f} {"NEUTRAL" if nt else ""}')
