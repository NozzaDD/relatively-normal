"""The three combination generators — combinations.md §3, exactly as specified.

Opposition, Tonal and Muted partition the hue circle (Tonal <= 40°, Muted
40-100°, Opposition 100-180°), so every pair of chromatic anchors is tested by
exactly one generator. Neutrals — relative chroma <= 0.15 (combinations.md §5)
— do not enter the generators; they are the ground the pairs sit on. Input: a
season's anchors. Output: ranked pairs carrying the computed hue gap, ΔL* and
Δ relative chroma.
"""
from dataclasses import dataclass

from . import colour
from .palette import TIERS

# hue band (lo, hi], per-colour relative-chroma cap, Δ relative chroma limit, ΔL* minimum
GENERATORS = {
    "opposition": {"band": (100.0, 180.0), "cap": None, "d_rel": 0.20, "d_L": 15.0},
    "tonal":      {"band": (0.0, 40.0),    "cap": None, "d_rel": 0.20, "d_L": 25.0},
    "muted":      {"band": (40.0, 100.0),  "cap": 0.45, "d_rel": 0.15, "d_L": 25.0},
}
DEFAULT_ORDER = ("opposition", "tonal", "muted")
CALM_ORDER = ("tonal", "muted", "opposition")
CALM_WORDS = ("calm", "quiet", "grounded")
NEUTRAL_REL = 0.15   # combinations.md §5: a neutral is anything with relative chroma <= 0.15


def is_neutral(rel):
    return rel <= NEUTRAL_REL


def band_of(hue_gap):
    """Which generator's band a hue gap falls in. Boundaries belong to the
    lower band: 40.0 is Tonal, 100.0 is Muted."""
    if hue_gap <= 40.0:
        return "tonal"
    if hue_gap <= 100.0:
        return "muted"
    return "opposition"


def test_pair(L1, h1, rel1, L2, h2, rel2):
    """Apply the band's generator to two colours given as (L*, h°, relative
    chroma). Returns (generator name or None, metrics dict)."""
    hg = colour.hue_gap(h1, h2)
    d_L = abs(L1 - L2)
    d_rel = abs(rel1 - rel2)
    name = band_of(hg)
    g = GENERATORS[name]
    passes = d_rel <= g["d_rel"] and d_L >= g["d_L"]
    if g["cap"] is not None:
        passes = passes and rel1 <= g["cap"] and rel2 <= g["cap"]
    return (name if passes else None), {"hue_gap": hg, "delta_L": d_L, "delta_rel": d_rel}


@dataclass(frozen=True)
class Pair:
    generator: str
    dominant: object     # Anchor — the deeper of the two
    counter: object      # Anchor — the lighter
    hue_gap: float
    delta_L: float
    delta_rel: float
    bridge: object = None  # Anchor or None

    @property
    def name(self):
        return f"{self.dominant.name.title()} and {self.counter.name.title()}"

    @property
    def names(self):
        return frozenset((self.dominant.name, self.counter.name))

    def as_dict(self):
        return {"generator": self.generator, "name": self.name,
                "dominant": self.dominant.name, "counter": self.counter.name,
                "dominant_hex": self.dominant.hex, "counter_hex": self.counter.hex,
                "bridge": self.bridge.name if self.bridge else None,
                "hue_gap": round(self.hue_gap, 1), "delta_L": round(self.delta_L, 1),
                "delta_rel": round(self.delta_rel, 2),
                "split": "60-70 / 30-40" if not self.bridge else "50 / 30 / 20"}


def is_tonal_pair(a, b):
    """Two anchors form a valid Tonal pair: hue gap <= 40°, Δ relative chroma
    <= 0.20, ΔL* >= 25 — the Tonal generator's own test."""
    name, _ = test_pair(a.L, a.h, a.rel, b.L, b.h, b.rel)
    return name == "tonal"


def lightness_gap(a, dominant, counter):
    """A bridge's lightness gap to the pair: its distance to the nearer of the
    two, so a large gap means it is clearly separated from both."""
    return min(abs(a.L - dominant.L), abs(a.L - counter.L))


def bridge_candidates(dominant, counter, anchors):
    """§3.6 — every anchor that adds no third voice: a neutral (§5), or a
    chromatic anchor that forms a valid Tonal pair with the dominant or the
    counter. Any tier, any lightness. Returns [(Anchor, 'neutral' | 'tonal')]."""
    out = []
    for a in anchors:
        if a.name in (dominant.name, counter.name):
            continue
        if is_neutral(a.rel):
            out.append((a, "neutral"))
        elif is_tonal_pair(a, dominant) or is_tonal_pair(a, counter):
            out.append((a, "tonal"))
    return out


def _bridge(dominant, counter, anchors):
    """§3.6 — the bridge: of the candidates, the one with the largest lightness
    gap to the pair; ties go to the lower relative chroma. None if no anchor
    qualifies."""
    candidates = bridge_candidates(dominant, counter, anchors)
    if not candidates:
        return None
    return max(candidates, key=lambda ac: (lightness_gap(ac[0], dominant, counter), -ac[0].rel))[0]


def _rank_key(generator):
    if generator == "opposition":
        return lambda p: (-p.hue_gap, -p.delta_L)      # closer to 180° first, then value contrast
    if generator == "tonal":
        return lambda p: (p.hue_gap, -p.delta_L)       # closer to 0° first, then value contrast
    return lambda p: (-p.delta_L, -p.hue_gap)          # muted: value contrast carries the pair


def run(anchors):
    """Run all three generators over every pair of chromatic anchors (neutrals
    excluded, §5). Returns a dict of generator name -> ranked list of Pair
    (ranked within the generator only). Bridges may still be neutrals."""
    out = {name: [] for name in GENERATORS}
    chromatic = [a for a in anchors if not is_neutral(a.rel)]
    for i in range(len(chromatic)):
        for j in range(i + 1, len(chromatic)):
            a, b = chromatic[i], chromatic[j]
            name, m = test_pair(a.L, a.h, a.rel, b.L, b.h, b.rel)
            if name is None:
                continue
            dominant, counter = (a, b) if a.L < b.L else (b, a)
            out[name].append(Pair(name, dominant, counter, m["hue_gap"], m["delta_L"], m["delta_rel"],
                                  _bridge(dominant, counter, anchors)))
    for name in out:
        out[name].sort(key=_rank_key(name))
    return out


def is_calm(mood):
    """Mood answer keyword check for the promotion rule (§3): calm, quiet or
    grounded promotes Tonal and Muted above Opposition."""
    if not mood:
        return False
    text = mood.lower()
    return any(w in text for w in CALM_WORDS)


def generate(anchors, mood=None, direction_anchor=None):
    """The full generator output for a season's anchors.

    - `mood`: the free-text answer to intake question 2; calm/quiet/grounded
      promotes Tonal and Muted above Opposition, keeping Tonal ahead of Muted.
    - `direction_anchor`: the chosen direction's anchor name; pairs containing
      it rank first within each list (§3, direction re-weighting).

    Returns {"order": [...], "lists": {name: [Pair]}, "ranked": [Pair]} where
    `ranked` is the three lists concatenated in `order`.
    """
    lists = run(anchors)
    if direction_anchor:
        for name in lists:
            lists[name].sort(key=lambda p: 0 if direction_anchor in p.names else 1)  # stable
    order = list(CALM_ORDER if is_calm(mood) else DEFAULT_ORDER)
    ranked = [p for name in order for p in lists[name]]
    return {"order": order, "lists": lists, "ranked": ranked}


def find_pair(lists, name_a, name_b):
    """Locate a pair by its two anchor names across the generator lists.
    Returns (generator, rank from 1, Pair) or None."""
    want = frozenset((name_a, name_b))
    for gen, pairs in lists.items():
        for i, p in enumerate(pairs, 1):
            if p.names == want:
                return gen, i, p
    return None
