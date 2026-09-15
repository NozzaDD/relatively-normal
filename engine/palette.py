"""Palettes — load seasons.yaml, expose a season's anchors in Lab with tier,
its rules (black, white, contrast, avoid) and directions, apply a direction
re-weighting, and derive the runner-up season (colour-system.md §2).

Requires PyYAML to read the file; everything else is standard library.
"""
from dataclasses import dataclass, replace
from pathlib import Path

import yaml

from . import colour

REPO_ROOT = Path(__file__).resolve().parents[1]
SEASONS_PATH = REPO_ROOT / "frameworks" / "seasons.yaml"

TIERS = ("foundations", "supporting", "accents")
TIER_SHARE = {"foundations": 0.55, "supporting": 0.30, "accents": 0.15}

# Which axis each characteristic word belongs to, and its opposite pole.
AXIS_OF = {"warm": "temperature", "cool": "temperature",
           "light": "value", "deep": "value",
           "soft": "chroma", "bright": "chroma"}
OPPOSITE = {"warm": "cool", "cool": "warm", "light": "deep", "deep": "light",
            "soft": "bright", "bright": "soft"}
POLES = {"temperature": ("warm", "cool"), "value": ("light", "deep"), "chroma": ("soft", "bright")}
CONFIDENCE_RANK = {"low": 0, "medium": 1, "high": 2}

# How a `white` rule names its anchor (matching.md §2, stage 1).
WHITE_ANCHOR_FOR_RULE = {
    "pure_white": ("pure white",),
    "soft_white": ("soft white",),
    "cream_only": ("cream",),
    "cream_or_warm_white": ("warm white",),
    "anywhere": ("warm white", "pure white", "soft white", "cream"),
}


@dataclass(frozen=True)
class Anchor:
    name: str
    hex: str
    tier: str
    lab: tuple
    L: float
    C: float
    h: float
    rel: float          # relative chroma, colour.relative_chroma
    weight: float = 1.0  # set by apply_direction; 1.0 in the base palette

    @classmethod
    def from_hex(cls, name, hex_str, tier, weight=1.0):
        lab = colour.hex_to_lab(hex_str)
        L, C, h = colour.lab_to_lch(lab)
        return cls(name, hex_str.upper(), tier, lab, L, C, h, colour.relative_chroma(L, C, h), weight)

    def as_dict(self):
        return {"name": self.name, "hex": self.hex, "tier": self.tier,
                "lab": [round(v, 2) for v in self.lab], "relative_chroma": round(self.rel, 3),
                "weight": self.weight}


@dataclass
class Season:
    key: str
    primary: str
    secondary: str
    metal: str
    contrast: str
    black: str
    white: str
    anchors: list          # Anchor, all three tiers, tier order then file order
    avoid: list            # hex strings
    directions: dict       # key -> {"anchor": name, "note": str}
    corporate: list = None # anchor names that read as appropriate in a formal workplace
    direction: str = None  # set by apply_direction

    # -- lookups ---------------------------------------------------------
    def tier(self, tier):
        return [a for a in self.anchors if a.tier == tier]

    def find(self, name):
        for a in self.anchors:
            if a.name == name:
                return a
        return None

    def white_anchor(self):
        """The anchor the season's `white` rule resolves to. Hard rule 5 says
        it always exists; raise loudly if a palette edit breaks that."""
        for name in WHITE_ANCHOR_FOR_RULE[self.white]:
            a = self.find(name)
            if a:
                return a
        raise ValueError(f"{self.key}: white rule {self.white!r} names no anchor in the tiers")

    def rules(self):
        return {"black": self.black, "white": self.white, "contrast": self.contrast,
                "metal": self.metal, "avoid": list(self.avoid), "corporate": list(self.corporate or [])}

    def axes(self):
        """The season as readings on the three axes. The axis not named by
        primary or secondary sits at centre."""
        readings = {"temperature": "neutral", "value": "medium", "chroma": "medium"}
        for word in (self.primary, self.secondary):
            readings[AXIS_OF[word]] = word
        return readings

    def as_dict(self):
        return {"season": self.key, "primary": self.primary, "secondary": self.secondary,
                "direction": self.direction, "rules": self.rules(),
                "tiers": {t: [a.as_dict() for a in self.tier(t)] for t in TIERS},
                "tier_share": dict(TIER_SHARE),
                "directions": {k: dict(v) for k, v in self.directions.items()}}


# ---------------------------------------------------------------- loading

_cache = {}


def load_seasons(path=None):
    """All twelve seasons, keyed as in seasons.yaml. Cached per path."""
    path = Path(path) if path else SEASONS_PATH
    if path in _cache:
        return _cache[path]
    with open(path) as fh:
        raw = yaml.safe_load(fh)
    seasons = {}
    for key, s in raw.items():
        anchors = [Anchor.from_hex(a["name"], a["hex"], tier) for tier in TIERS for a in s[tier]]
        seasons[key] = Season(key=key, primary=s["primary"], secondary=s["secondary"],
                              metal=s["metal"], contrast=s["contrast"], black=s["black"],
                              white=s["white"], anchors=anchors,
                              avoid=[h.upper() for h in s["avoid"]],
                              directions={k: dict(v) for k, v in s.get("directions", {}).items()},
                              corporate=list(s.get("corporate", [])))
    _cache[path] = seasons
    return seasons


def get_season(key, path=None):
    seasons = load_seasons(path)
    if key not in seasons:
        raise KeyError(f"unknown season {key!r}; have {sorted(seasons)}")
    return seasons[key]


# ---------------------------------------------------------------- direction

def apply_direction(season, direction_key, family_gap=40.0):
    """Re-weight the palette toward a named direction (colour-system.md §5).

    The specification says the output palette is the base tiers "re-weighted
    toward the chosen direction" without defining the weights. This module's
    interpretation: the direction's anchor gets weight 2.0; anchors in its hue
    family (hue gap <= family_gap, the Tonal band) get 1.5; everything else
    stays at 1.0. Anchors are then ordered by weight within each tier, so the
    direction's colours lead every tier. Nothing is added or removed — a
    direction is a lean, not a filter.
    """
    if direction_key not in season.directions:
        raise KeyError(f"{season.key}: unknown direction {direction_key!r}; "
                       f"have {sorted(season.directions)}")
    target = season.find(season.directions[direction_key]["anchor"])
    if target is None:
        raise ValueError(f"{season.key}: direction {direction_key!r} names an anchor "
                         f"that is not in the tiers")
    weighted = []
    for a in season.anchors:
        if a.name == target.name:
            w = 2.0
        elif colour.hue_gap(a.h, target.h) <= family_gap:
            w = 1.5
        else:
            w = 1.0
        weighted.append(replace(a, weight=w))
    ordered = [a for t in TIERS for a in sorted((x for x in weighted if x.tier == t),
                                                key=lambda x: -x.weight)]
    return replace(season, anchors=ordered, direction=direction_key)


# ---------------------------------------------------------------- runner-up season

def _season_for(primary, secondary, seasons):
    """Find the season whose (primary, secondary) matches; fall back to the
    same two words in the other order, since the table lists each pair once."""
    for s in seasons.values():
        if (s.primary, s.secondary) == (primary, secondary):
            return s.key
    for s in seasons.values():
        if {s.primary, s.secondary} == {primary, secondary}:
            return s.key
    return None


def runner_up(season_key, confidence, path=None):
    """The runner-up season (colour-system.md §2): the season that differs from
    the winner on exactly one axis, choosing the axis with the lowest
    confidence. Ties go to temperature.

    `confidence` maps each axis to 'high' | 'medium' | 'low'.

    Returns {"season", "axis", "candidates"}. When the least-confident axis is
    the one the winner holds at centre, moving it to either pole is a one-axis
    change, so both are candidates; the first in table order is returned and
    both are listed.
    """
    seasons = load_seasons(path)
    winner = seasons[season_key]
    ranks = {ax: CONFIDENCE_RANK[confidence[ax]] for ax in ("temperature", "value", "chroma")}
    lowest = min(ranks.values())
    tied = [ax for ax, r in ranks.items() if r == lowest]
    axes = winner.axes()
    temp_word = axes["temperature"]
    other_word = winner.secondary if AXIS_OF[winner.primary] == "temperature" else winner.primary
    other_axis = AXIS_OF[other_word]
    centre_axis = [ax for ax in POLES if ax not in ("temperature", other_axis)][0]

    if "temperature" in tied:
        axis = "temperature"
    elif other_axis in tied:
        axis = other_axis
    else:
        axis = centre_axis

    if axis == "temperature":
        flipped = OPPOSITE[temp_word]
        pair = (flipped, winner.secondary) if winner.primary == temp_word else (winner.primary, flipped)
        candidates = [_season_for(*pair, seasons)]
    elif axis == other_axis:
        flipped = OPPOSITE[other_word]
        pair = (flipped, winner.secondary) if winner.primary == other_word else (winner.primary, flipped)
        candidates = [_season_for(*pair, seasons)]
    else:
        candidates = []
        for pole in POLES[centre_axis]:
            pair = (pole, winner.secondary) if winner.primary == other_word else (winner.primary, pole)
            found = _season_for(*pair, seasons)
            if found:
                candidates.append(found)
    candidates = [c for c in candidates if c]
    return {"season": candidates[0] if candidates else None, "axis": axis, "candidates": candidates}
