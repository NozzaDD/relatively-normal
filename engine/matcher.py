"""Matching — matching.md §1 to §5. From item colours to verdicts, outfit
checks, ranked gaps and closet fills.

Items are dicts: {"id": str, "hex": str, "slot": str, "near_face": bool|None,
"share": float}. `slot` is one of SLOTS. `near_face` is read only for the
accessory slot (matching.md §2, stage 1); an accessory with no flag is scored
as hardware and the missing flag is reported. `share` defaults to 1.0 and is
the item's weight in share-weighted figures.

No language model runs here. Every verdict can be explained by pointing at a
number.
"""
import math
import random

from . import colour, generators
from .palette import TIERS, TIER_SHARE

SLOTS = ("top", "bottom", "shoes", "bag", "accessory")
BODY_WEIGHT = {"top": 2, "bottom": 2, "shoes": 1, "bag": 1, "accessory": 1}  # §3 tier balance

RULE_TRIGGER_DE = 8.0     # stage 1: item within ΔE 8 of 000000 / FFFFFF
HARD_MISS_DE = 8.0        # stage 2: ΔE to an avoid colour
IN_DE = 12.0              # stage 3
NEAR_DE = 16.0

# §3 contrast — the lightness spread above which a season's contrast level is
# exceeded. Starting values, to be tuned against the beta consultations like
# the ΔE thresholds; matching.md only specifies the flag, not the numbers.
CONTRAST_MAX_RANGE = {"low": 35, "low-medium": 45, "medium": 55, "medium-high": 65,
                      "high": 100, "very_high": 100}
ACCENT_HEAVY_SHARE = 0.30      # twice the 15% target
FOUNDATION_LIGHT_SHARE = 0.30  # roughly half the 55% target

FACE_REASON = "black works on you, just not next to your face"
GAP_SEVERITY = {"empty_slot": 0, "hard_miss": 1, "out": 2, "near": 3,
                "tier_imbalance": 4, "contrast_mismatch": 5}


# ================================================================ §1 extraction

def extract_colours(pixels, k=3, floor=0.08, alpha_min=200, sample=20000, seed=0):
    """matching.md §1 on an iterable of (r, g, b, a) pixels from a cutout.
    PNG decoding is the caller's job; this is the arithmetic.

    Keeps alpha > alpha_min, downsamples to ~`sample` pixels, converts to Lab,
    runs k-means (k=3, seeded k-means++ so results are reproducible), drops
    clusters under `floor`, and returns up to k colours as
    {"lab", "hex", "share"} ordered by share. The first is the dominant colour.
    """
    opaque = [p[:3] for p in pixels if p[3] > alpha_min]
    if not opaque:
        return []
    rng = random.Random(seed)
    if len(opaque) > sample:
        opaque = rng.sample(opaque, sample)
    pts = [colour.srgb_to_lab(p) for p in opaque]
    k = min(k, len(pts))

    def d2(p, q):
        return (p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 + (p[2] - q[2]) ** 2

    centres = [pts[rng.randrange(len(pts))]]                # k-means++
    while len(centres) < k:
        dists = [min(d2(p, c) for c in centres) for p in pts]
        total = sum(dists)
        r = rng.random() * total if total > 0 else 0
        acc = 0.0
        for p, d in zip(pts, dists):
            acc += d
            if acc >= r:
                centres.append(p)
                break
        else:
            centres.append(pts[-1])
    for _ in range(50):
        buckets = [[] for _ in centres]
        for p in pts:
            buckets[min(range(k), key=lambda i: d2(p, centres[i]))].append(p)
        new = [tuple(sum(v[i] for v in b) / len(b) for i in range(3)) if b else c
               for b, c in zip(buckets, centres)]
        if all(d2(a, b) < 1e-6 for a, b in zip(new, centres)):
            break
        centres = new
    n = len(pts)
    out = [{"lab": c, "hex": colour.lab_to_hex(c), "share": len(b) / n}
           for c, b in zip(centres, buckets) if len(b) / n > floor]
    return sorted(out, key=lambda x: -x["share"])


# ================================================================ §2 scoring

def _is_face(slot, near_face):
    return slot == "top" or (slot == "accessory" and bool(near_face))


def _black_rule(season, slot, near_face):
    """Stage 1 black table. Returns (verdict, nearest, reason) or None."""
    rule, face = season.black, _is_face(slot, near_face)
    if rule == "anywhere":
        return "in", "black", None
    if rule == "anywhere_with_warm_partner":
        return "in", "black", "pair with a warm-tier item"
    if rule == "avoid":
        return "hard_miss", "black", "black is on this season's avoid list"
    if rule in ("below_waist_or_hardware", "away_from_face"):
        if face:
            return "out", "black", FACE_REASON
        if rule == "below_waist_or_hardware":
            where = "below waist" if slot in ("bottom", "shoes") else "hardware"
        else:
            where = "away from face"
        return "in", f"black ({where})", None
    raise ValueError(f"{season.key}: unknown black rule {rule!r}")


def _white_rule(season, slot, near_face):
    """Stage 1 white table. Returns (verdict, nearest, reason) or None."""
    rule, face = season.white, _is_face(slot, near_face)
    anchor = season.white_anchor().name
    if rule in ("pure_white", "anywhere"):
        return "in", anchor, None
    if not face:
        return "in", anchor, None
    if rule == "soft_white":
        return "near", anchor, "a softer white next to your face"
    if rule == "cream_or_warm_white":
        return "near", anchor, "cream or a warm white next to your face"
    if rule == "cream_only":
        return "hard_miss", anchor, "cream, not white, next to your face"
    raise ValueError(f"{season.key}: unknown white rule {rule!r}")


def _shift_hint(lab, anchor):
    """Stage 3 near: what would need to shift — lighter/deeper, softer/clearer,
    warmer/cooler — read from the sign of the Lab difference to the anchor."""
    L, C, _ = colour.lab_to_lch(lab)
    hints = []
    if anchor.L - L >= 5:
        hints.append("lighter")
    elif L - anchor.L >= 5:
        hints.append("deeper")
    if C - anchor.C >= 5:
        hints.append("softer")
    elif anchor.C - C >= 5:
        hints.append("clearer")
    if anchor.lab[2] - lab[2] >= 5:
        hints.append("warmer")
    elif lab[2] - anchor.lab[2] >= 5:
        hints.append("cooler")
    return hints


def nearest_anchor(lab, season):
    """(Anchor, ΔE2000) for the nearest tier anchor."""
    return min(((a, colour.delta_e_2000(lab, a.lab)) for a in season.anchors), key=lambda x: x[1])


def score_item(item, season):
    """matching.md §2 — the three-stage evaluation of one item's dominant colour.
    Stage 1 slot rules, then stage 2 avoid list, then stage 3 anchors. The first
    stage that returns a verdict wins."""
    slot = item["slot"]
    if slot not in SLOTS:
        raise ValueError(f"item {item.get('id')!r}: unknown slot {slot!r}")
    lab = colour.hex_to_lab(item["hex"])
    near_face = item.get("near_face")
    result = {"item_id": item.get("id"), "slot": slot,
              "near_face": near_face if slot == "accessory" else None,
              "dominant": {"hex": item["hex"].upper().lstrip('#'), "lab": [round(v, 2) for v in lab]},
              "verdict": None, "nearest": None, "delta_e": None, "tier": None,
              "stage": None, "reason": None, "shift": None, "flags": []}
    if slot == "accessory" and near_face is None:
        result["flags"].append("near_face not set; scored as hardware")

    # -- stage 1: slot-conditional rules
    for rule_hex, rule_fn in (("000000", _black_rule), ("FFFFFF", _white_rule)):
        de = colour.delta_e_2000(lab, colour.hex_to_lab(rule_hex))
        if de <= RULE_TRIGGER_DE:
            verdict, nearest, reason = rule_fn(season, slot, near_face)
            base = nearest.split(" (")[0]
            named = season.find(base)
            result.update(verdict=verdict, nearest=nearest, delta_e=round(de, 1), stage=1,
                          reason=reason, tier=named.tier if named else None)
            return result

    # -- stage 2: avoid list
    avoid_hex, avoid_de = min(((h, colour.delta_e_2000(lab, colour.hex_to_lab(h))) for h in season.avoid),
                              key=lambda x: x[1])
    if avoid_de <= HARD_MISS_DE:
        result.update(verdict="hard_miss", nearest=f"avoid {avoid_hex}", delta_e=round(avoid_de, 1),
                      stage=2, reason="within reach of an avoid colour")
        return result

    # -- stage 3: palette anchors
    anchor, de = nearest_anchor(lab, season)
    verdict = "in" if de <= IN_DE else "near" if de <= NEAR_DE else "out"
    result.update(verdict=verdict, nearest=anchor.name, delta_e=round(de, 1), stage=3, tier=anchor.tier,
                  shift=_shift_hint(lab, anchor) if verdict == "near" else None)
    return result


def score_items(items, season):
    return [score_item(i, season) for i in items]


# ================================================================ §3 outfit checks

def _share(item):
    return float(item.get("share", 1.0))


def outfit_checks(scored, season):
    """The four checks on a set of scored items that sit in the five slots.
    `scored` is one item per slot at most (an outfit, not a closet)."""
    by_slot = {s: None for s in SLOTS}
    for r in scored:
        if by_slot[r["slot"]] is None:
            by_slot[r["slot"]] = r
    filled = [r for r in by_slot.values() if r]

    # coverage
    missing = [s for s in SLOTS if by_slot[s] is None]

    # palette share
    palette = {"in": 0, "near": 0, "out": 0, "hard_miss": 0}
    for r in filled:
        palette[r["verdict"]] += 1

    # tier balance — in/near items with a tier, weighted by body coverage
    counted = [r for r in filled if r["verdict"] in ("in", "near") and r["tier"]]
    total = sum(BODY_WEIGHT[r["slot"]] for r in counted)
    mix = {t: 0.0 for t in TIERS}
    for r in counted:
        mix[r["tier"]] += BODY_WEIGHT[r["slot"]]
    if total:
        mix = {t: round(v / total, 2) for t, v in mix.items()}
    tier_flag = None
    if total and mix["accents"] > ACCENT_HEAVY_SHARE:
        tier_flag = "accent-heavy"
    elif len(counted) >= 2 and mix["foundations"] < FOUNDATION_LIGHT_SHARE:
        tier_flag = "foundation-light"

    # contrast
    Ls = [r["dominant"]["lab"][0] for r in filled]
    spread = round(max(Ls) - min(Ls), 1) if len(Ls) >= 2 else 0.0
    limit = CONTRAST_MAX_RANGE.get(season.contrast, 100)
    contrast_flag = "higher contrast than your natural colouring" if spread > limit else None

    # black with warm partner (stage 1 note)
    warm_flag = None
    if season.black == "anywhere_with_warm_partner" and any(
            r["stage"] == 1 and r["nearest"].startswith("black") for r in filled):
        if not any(r["tier"] in ("foundations", "supporting") and not r["nearest"].startswith("black")
                   for r in filled):
            warm_flag = "black needs a warm-tier partner in this outfit"

    return {"coverage": {"missing": missing},
            "palette": palette,
            "tier_mix": {"foundation": mix["foundations"], "supporting": mix["supporting"],
                         "accent": mix["accents"], "flag": tier_flag},
            "contrast": {"lightness_range": spread, "season_target": season.contrast,
                         "flag": contrast_flag},
            "warm_partner": {"flag": warm_flag}}


# ================================================================ §4 ranked gaps

def find_gaps(scored, checks):
    gaps = []
    for slot in checks["coverage"]["missing"]:
        gaps.append({"type": "empty_slot", "slot": slot})
    for r in scored:
        if r["verdict"] in ("near", "out", "hard_miss"):
            gaps.append({"type": r["verdict"], "slot": r["slot"], "item_id": r["item_id"],
                         "nearest": r["nearest"], "delta_e": r["delta_e"]})
    if checks["tier_mix"]["flag"]:
        gaps.append({"type": "tier_imbalance", "slot": None, "flag": checks["tier_mix"]["flag"]})
    if checks["contrast"]["flag"]:
        gaps.append({"type": "contrast_mismatch", "slot": None, "flag": checks["contrast"]["flag"]})
    return gaps


def rank_gaps(gaps, saved_outfits=None):
    """§4 — rank by how many outfits the fix would unlock. `saved_outfits` is a
    list of scored outfits (lists of scored items); a gap's `unlocks` is the
    number of them that share it, at least 1 for the outfit in hand. Ties break
    by severity: empty slot, hard miss, out, near, tier, contrast."""
    saved_outfits = saved_outfits or []
    for g in gaps:
        n = 1
        for outfit in saved_outfits:
            slots = {r["slot"] for r in outfit}
            if g["type"] == "empty_slot" and g["slot"] not in slots:
                n += 1
            elif g.get("item_id") and any(r["item_id"] == g["item_id"] for r in outfit):
                n += 1
        g["unlocks"] = n
    return sorted(gaps, key=lambda g: (-g["unlocks"], GAP_SEVERITY[g["type"]]))


# ================================================================ §5 fills

def _pairs_with(lab, others):
    """How many of `others` (scored items) the colour makes a Wada pair with."""
    return sum(1 for o in others if generators.pair_passes(lab, tuple(o["dominant"]["lab"])))


def fill_from_closet(gap, outfit_scored, closet_scored):
    """Source 1 — the user's own closet. Filter to the gap's slot, keep
    in-palette candidates not already in the outfit, require a Wada pair with
    at least one item already there, and take the one that pairs with most."""
    if not gap.get("slot"):
        return None
    in_outfit = {r["item_id"] for r in outfit_scored}
    others = [r for r in outfit_scored if r["slot"] != gap["slot"]]
    best = None
    for c in closet_scored:
        if c["slot"] != gap["slot"] or c["item_id"] in in_outfit or c["verdict"] != "in":
            continue
        n = _pairs_with(tuple(c["dominant"]["lab"]), others)
        if n == 0 and others:
            continue
        key = (n, -c["delta_e"])
        if best is None or key > best[0]:
            best = (key, c, n)
    if best is None:
        return None
    _, c, n = best
    tier = (c["tier"] or "").rstrip("s")
    return {"source": "closet", "item_id": c["item_id"], "nearest": c["nearest"], "pairs_with": n,
            "reason": f"in palette ({tier} tier), pairs with {n} item{'s' if n != 1 else ''} in the outfit"}


def fill_from_staples(gap, season):
    """Source 2 — the staples catalogue. Stub: returns None until staples/ is
    researched and hex-sampled."""
    return None


def fill_from_brands(gap, season):
    """Source 3 — the brand database, live. Stub: returns None until affiliate
    feeds exist (Phase B)."""
    return None


def fill_gap(gap, outfit_scored, closet_scored, season):
    """§5 — the three sources in strict order; stop at the first that answers."""
    for fn in (lambda: fill_from_closet(gap, outfit_scored, closet_scored),
               lambda: fill_from_staples(gap, season),
               lambda: fill_from_brands(gap, season)):
        fill = fn()
        if fill:
            return fill
    return None


# ================================================================ the outfit call

def score_outfit(outfit_items, season, closet_items=None, saved_outfits=None, outfit_id=None):
    """matching.md §6 — the matcher's output for one outfit.

    `outfit_items`: the items on the canvas, at most one per slot.
    `closet_items`: everything uploaded (defaults to the outfit); source 1
    searches it. `saved_outfits`: other outfits (lists of items) for ranking
    gaps by how many they appear in.
    """
    scored = score_items(outfit_items, season)
    closet_scored = score_items(closet_items, season) if closet_items is not None else scored
    saved_scored = [score_items(o, season) for o in (saved_outfits or [])]
    checks = outfit_checks(scored, season)
    gaps = rank_gaps(find_gaps(scored, checks), saved_scored)
    for g in gaps:
        g["fill"] = fill_gap(g, scored, closet_scored, season)
    slots = {s: None for s in SLOTS}
    for r in scored:
        if slots[r["slot"]] is None:
            slots[r["slot"]] = r
    return {"outfit_id": outfit_id, "season": season.key, "slots": slots,
            "checks": checks, "gaps_ranked": gaps}
