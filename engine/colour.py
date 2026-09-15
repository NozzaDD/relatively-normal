"""Colour maths — sRGB to CIELAB (D65), CIELAB to LCh, ΔE2000, relative chroma.

Pure functions, standard library only. Everything downstream (palette,
generators, matcher, horizons) computes distance and hue through this module,
so the constants here are the constants the whole engine agrees on.

Lab is always a (L*, a*, b*) tuple; LCh is (L*, C*, h°) with h in [0, 360).
"""
import math

_D65 = (0.95047, 1.0, 1.08883)
_RGB_TO_XYZ = ((0.4124564, 0.3575761, 0.1804375),
               (0.2126729, 0.7151522, 0.0721750),
               (0.0193339, 0.1191920, 0.9503041))
_XYZ_TO_RGB = ((3.2404542, -1.5371385, -0.4985314),
               (-0.9692660, 1.8760108, 0.0415560),
               (0.0556434, -0.2040259, 1.0572252))
_DELTA = 6.0 / 29.0


# ---------------------------------------------------------------- sRGB <-> Lab

def hex_to_rgb(hex_str):
    """'1F5F63' or '#1F5F63' -> (31, 95, 99)."""
    h = hex_str.strip().lstrip('#')
    if len(h) != 6:
        raise ValueError(f"not a 6-digit hex colour: {hex_str!r}")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def rgb_to_hex(rgb):
    return ''.join(f"{max(0, min(255, round(c))):02X}" for c in rgb)


def _to_linear(c):
    c = c / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _from_linear(c):
    return 12.92 * c if c <= 0.0031308 else 1.055 * (c ** (1 / 2.4)) - 0.055


def _f(t):
    return t ** (1.0 / 3.0) if t > _DELTA ** 3 else t / (3 * _DELTA * _DELTA) + 4.0 / 29.0


def _f_inv(t):
    return t ** 3 if t > _DELTA else 3 * _DELTA * _DELTA * (t - 4.0 / 29.0)


def srgb_to_lab(rgb):
    """(r, g, b) in 0-255 -> (L*, a*, b*), D65."""
    r, g, b = (_to_linear(v) for v in rgb)
    xyz = [m[0] * r + m[1] * g + m[2] * b for m in _RGB_TO_XYZ]
    fx, fy, fz = (_f(v / n) for v, n in zip(xyz, _D65))
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def hex_to_lab(hex_str):
    return srgb_to_lab(hex_to_rgb(hex_str))


def lab_to_linear_rgb(lab):
    """(L*, a*, b*) -> linear (r, g, b) in nominal 0-1. Out-of-gamut values
    fall outside 0-1; that is what the gamut search relies on."""
    L, a, b = lab
    fy = (L + 16) / 116.0
    fx = fy + a / 500.0
    fz = fy - b / 200.0
    X, Y, Z = (_f_inv(v) * n for v, n in zip((fx, fy, fz), _D65))
    return tuple(m[0] * X + m[1] * Y + m[2] * Z for m in _XYZ_TO_RGB)


def lab_to_hex(lab):
    return rgb_to_hex(tuple(_from_linear(max(0.0, min(1.0, c))) * 255 for c in lab_to_linear_rgb(lab)))


# ---------------------------------------------------------------- Lab <-> LCh

def lab_to_lch(lab):
    L, a, b = lab
    C = math.hypot(a, b)
    h = math.degrees(math.atan2(b, a))
    return (L, C, h + 360 if h < 0 else h)


def lch_to_lab(lch):
    L, C, h = lch
    return (L, C * math.cos(math.radians(h)), C * math.sin(math.radians(h)))


def hue_gap(h1, h2):
    """Smallest angle between two hues, 0-180."""
    d = abs(h1 - h2) % 360
    return 360 - d if d > 180 else d


# ---------------------------------------------------------------- ΔE2000

def delta_e_2000(lab1, lab2, kL=1.0, kC=1.0, kH=1.0):
    L1, a1, b1 = lab1
    L2, a2, b2 = lab2
    C1, C2 = math.hypot(a1, b1), math.hypot(a2, b2)
    Cb = (C1 + C2) / 2.0
    G = 0.5 * (1 - math.sqrt(Cb ** 7 / (Cb ** 7 + 25.0 ** 7))) if Cb > 0 else 0.5
    a1p, a2p = (1 + G) * a1, (1 + G) * a2
    C1p, C2p = math.hypot(a1p, b1), math.hypot(a2p, b2)

    def hp(ap, bp):
        if ap == 0 and bp == 0:
            return 0.0
        h = math.degrees(math.atan2(bp, ap))
        return h + 360 if h < 0 else h

    h1p, h2p = hp(a1p, b1), hp(a2p, b2)
    dLp = L2 - L1
    dCp = C2p - C1p
    if C1p * C2p == 0:
        dhp = 0.0
    else:
        dhp = h2p - h1p
        if dhp > 180:
            dhp -= 360
        elif dhp < -180:
            dhp += 360
    dHp = 2 * math.sqrt(C1p * C2p) * math.sin(math.radians(dhp) / 2.0)
    Lbp = (L1 + L2) / 2.0
    Cbp = (C1p + C2p) / 2.0
    if C1p * C2p == 0:
        hbp = h1p + h2p
    else:
        s = h1p + h2p
        if abs(h1p - h2p) > 180:
            hbp = (s + 360) / 2.0 if s < 360 else (s - 360) / 2.0
        else:
            hbp = s / 2.0
    T = (1 - 0.17 * math.cos(math.radians(hbp - 30))
         + 0.24 * math.cos(math.radians(2 * hbp))
         + 0.32 * math.cos(math.radians(3 * hbp + 6))
         - 0.20 * math.cos(math.radians(4 * hbp - 63)))
    d_theta = 30 * math.exp(-(((hbp - 275) / 25.0) ** 2))
    Rc = 2 * math.sqrt(Cbp ** 7 / (Cbp ** 7 + 25.0 ** 7)) if Cbp > 0 else 0.0
    Sl = 1 + (0.015 * (Lbp - 50) ** 2) / math.sqrt(20 + (Lbp - 50) ** 2)
    Sc = 1 + 0.045 * Cbp
    Sh = 1 + 0.015 * Cbp * T
    Rt = -math.sin(math.radians(2 * d_theta)) * Rc
    return math.sqrt((dLp / (kL * Sl)) ** 2 + (dCp / (kC * Sc)) ** 2 + (dHp / (kH * Sh)) ** 2
                     + Rt * (dCp / (kC * Sc)) * (dHp / (kH * Sh)))


# ---------------------------------------------------------------- relative chroma

def in_gamut(L, C, h, eps=1e-6):
    return all(-eps <= v <= 1 + eps for v in lab_to_linear_rgb(lch_to_lab((L, C, h))))


def max_chroma(L, h, iterations=60):
    """C*max(L*, h): the sRGB gamut boundary at this lightness and hue, found
    by bisection on chroma. Gamut is convex along a ray of constant L and h, so
    bisection is exact to the tolerance the iteration count gives."""
    lo, hi = 0.0, 200.0
    for _ in range(iterations):
        mid = (lo + hi) / 2.0
        if in_gamut(L, mid, h):
            lo = mid
        else:
            hi = mid
    return lo


def relative_chroma(L, C, h):
    """C* / C*max(L*, h) — the fraction of the available saturation a colour
    uses (combinations.md §2). Returns 0.0 where no chroma is displayable."""
    cmax = max_chroma(L, h)
    return C / cmax if cmax > 0 else 0.0
