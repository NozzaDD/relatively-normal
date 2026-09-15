"""Matching — matching.md §1 to §5. From item colours to verdicts, outfit
checks, ranked gaps and closet fills.

Items are dicts: {"id": str, "hex": str, "slot": str, "near_face": bool|None,
"dressiness": int|None, "weight": int|None, "share": float}. `slot` is one of
SLOTS. `near_face` is read only for the accessory slot (matching.md §2,
stage 1); an accessory with no flag is scored as hardware and the missing flag
is reported. `dressiness` (1-4, casual to dressy) and `weight` (1-4, light to
heavy — thermal, not colour temperature) feed the zone and weather checks in
§3. `share` defaults to 1.0 and is the item's weight in share-weighted figures.

Outfits are specs: {"name", "occasion", "dress_code" (1-5), "weather"
("clear" | "rain"), "items": [item dicts]}. Gaps are ranked across all the
outfits given (§4): a gap's `unlocks` is the number of outfits the fix would
complete or repair.

No language model runs here. Every verdict can be explained by pointing at a
number.
"""
import random

from . import colour, generators
from .palette import TIERS, TIER_SHARE

SLOTS = ("top", "bottom", "layer", "shoes", "bag", "accessory")
COVERAGE_SLOTS = ("top", "bottom", "shoes", "bag", "accessory")   # layer is optional, never a coverage gap
FACE_SLOTS = ("top", "layer")                                     # positions next to the face for the slot rules;
                                                                  # a layer yields the face to an in-palette near-face accessory
BODY_WEIGHT = {"top": 2, "bottom": 2, "layer": 2, "shoes": 1, "bag": 1, "accessory": 1}  # §3 tier balance

RULE_TRIGGER_DE = 8.0     # stage 1: item within ΔE 8 of 000000 / FFFFFF
HARD_MISS_DE = 8.0        # stage 2: ΔE to an avoid colour
IN_DE = 12.0              # stage 3
NEAR_DE = 16.0

ZONE_TOLERANCE = 1        # §3 zone fit: dressiness within 1 of the occasion's dress code
RAIN_MIN_WEIGHT = 3       # §3 weather fit: heaviest item at least this in rain

# §3 contrast — the lightness spread above which a season's contrast level is
# exceeded. Starting values, to be tuned against the beta consultations like
# the ΔE thresholds; matching.md only specifies the flag, not the numbers.
CONTRAST_MAX_RANGE = {"low": 35, "low-medium": 45, "medium": 55, "medium-high": 65,
                      "high": 100, "very_high": 100}
ACCENT_HEAVY_SHARE = 0.30      # twice the 15% target
FOUNDATION_LIGHT_SHARE = 0.30  # roughly half the 55% target

FACE_REASON = "black works on you, just not next to your face"
GAP_SEVERITY = {"empty_slot": 0, "hard_miss": 1, "out": 2, "near": 3, "zone_gap": 4,
                "too_casual": 5, "too_dressy": 5, "not_enough_for_rain": 6,
                "tier_imbalance": 7, "contrast_mismatch": 8}


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

def _is_face(slot, near_face, layer_face=True):
    """Whether an item sits next to the face for the slot rules. A layer does
    unless `layer_face` is False — the outfit has an in-palette accessory with
    near_face true, and a scarf sits between the collar and the face."""
    if slot == "layer":
        return layer_face
    return slot == "top" or (slot == "accessory" and bool(near_face))


def _black_rule(season, slot, face):
    """Stage 1 black table. Returns (verdict, nearest, reason)."""
    rule = season.black
    if rule == "anywhere":
        return "in", "black", None
    if rule == "anywhere_with_warm_partner":
        return "in", "black", "pair with a warm-tier item"
    if rule == "avoid":
        return "hard_miss", "black", "black is on this season's avoid list"
    if rule in ("below_waist_or_hardware", "away_from_face"):
        if face:
            return "out", "black", FACE_REASON
        if rule == "below_waist_or_hardware" and slot != "layer":
            where = "below waist" if slot in ("bottom", "shoes") else "hardware"
        else:
            where = "away from face"
        return "in", f"black ({where})", None
    raise ValueError(f"{season.key}: unknown black rule {rule!r}")


def _white_rule(season, slot, face):
    """Stage 1 white table. Returns (verdict, nearest, reason)."""
    rule = season.white
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


def score_item(item, season, layer_face=True):
    """matching.md §2 — the three-stage evaluation of one item's dominant colour.
    Stage 1 slot rules, then stage 2 avoid list, then stage 3 anchors. The first
    stage that returns a verdict wins.

    `layer_face` matters only for the layer slot: True (the default, and the
    closet-level reading) treats the layer as a face position; `score_outfits`
    passes False when the outfit has an in-palette near-face accessory."""
    slot = item["slot"]
    if slot not in SLOTS:
        raise ValueError(f"item {item.get('id')!r}: unknown slot {slot!r}")
    lab = colour.hex_to_lab(item["hex"])
    L, C, h = colour.lab_to_lch(lab)
    rel = colour.relative_chroma(L, C, h)
    near_face = item.get("near_face")
    face = _is_face(slot, near_face, layer_face)
    result = {"item_id": item.get("id"), "slot": slot,
              "near_face": near_face if slot == "accessory" else None,
              "dressiness": item.get("dressiness"), "weight": item.get("weight"),
              "dominant": {"hex": item["hex"].upper().lstrip('#'), "lab": [round(v, 2) for v in lab],
                           "relative_chroma": round(rel, 3), "neutral": generators.is_neutral(rel)},
              "verdict": None, "nearest": None, "delta_e": None, "tier": None,
              "stage": None, "reason": None, "shift": None, "flags": [],
              # distance contribution (horizons.md §3b): the nearest anchor that would be
              # "in" for this slot after the slot rules, and the ΔE to it
              "admitted_nearest": None, "admitted_delta_e": None, "where": None}
    if slot == "accessory" and near_face is None:
        result["flags"].append("near_face not set; scored as hardware")

    # -- stage 1: slot-conditional rules
    for rule_hex, rule_fn in (("000000", _black_rule), ("FFFFFF", _white_rule)):
        de = colour.delta_e_2000(lab, colour.hex_to_lab(rule_hex))
        if de <= RULE_TRIGGER_DE:
            verdict, nearest, reason = rule_fn(season, slot, face)
            base = nearest.split(" (")[0]
            named = season.find(base)
            result.update(verdict=verdict, nearest=nearest, delta_e=round(de, 1), stage=1,
                          reason=reason, tier=named.tier if named else None,
                          where="at the face" if face else "away from the face")
            if verdict == "in":
                # admitted here: the rule colour itself is the nearest admitted anchor
                result.update(admitted_nearest=nearest, admitted_delta_e=round(de, 1))
            elif named:
                # not admitted here: the anchor the rule names (cream, soft white, ...)
                result.update(admitted_nearest=named.name,
                              admitted_delta_e=round(colour.delta_e_2000(lab, named.lab), 1))
            else:
                # not admitted and the rule colour is not a tier anchor: nearest tier anchor
                a2, de2 = nearest_anchor(lab, season)
                result.update(admitted_nearest=a2.name, admitted_delta_e=round(de2, 1))
            return result

    # -- stage 2: avoid list
    avoid_hex, avoid_de = min(((h, colour.delta_e_2000(lab, colour.hex_to_lab(h))) for h in season.avoid),
                              key=lambda x: x[1])
    if avoid_de <= HARD_MISS_DE:
        a2, de2 = nearest_anchor(lab, season)
        result.update(verdict="hard_miss", nearest=f"avoid {avoid_hex}", delta_e=round(avoid_de, 1),
                      stage=2, reason="within reach of an avoid colour",
                      admitted_nearest=a2.name, admitted_delta_e=round(de2, 1))
        return result

    # -- stage 3: palette anchors
    anchor, de = nearest_anchor(lab, season)
    verdict = "in" if de <= IN_DE else "near" if de <= NEAR_DE else "out"
    result.update(verdict=verdict, nearest=anchor.name, delta_e=round(de, 1), stage=3, tier=anchor.tier,
                  shift=_shift_hint(lab, anchor) if verdict == "near" else None,
                  admitted_nearest=anchor.name, admitted_delta_e=round(de, 1))
    return result


def score_items(items, season):
    return [score_item(i, season) for i in items]


# ================================================================ neutrals are the ground (combinations.md §5)

PAIR_MATCH_DE = 12.0      # chromatic + chromatic: each item within ΔE 12 of a generated pair's anchor
NEUTRAL_MIN_DL = 15.0     # neutral + neutral: ΔL* at or above this, else "flat"


def is_neutral_item(r):
    return r["dominant"]["neutral"]


def _matched_pair(a, b, pairs):
    """The generated pair the two chromatic items match, if any: each within
    ΔE 12 of one of that pair's two anchors, one anchor each."""
    la, lb = tuple(a["dominant"]["lab"]), tuple(b["dominant"]["lab"])
    for p in pairs:
        for x, y in ((p.dominant.lab, p.counter.lab), (p.counter.lab, p.dominant.lab)):
            if colour.delta_e_2000(la, x) <= PAIR_MATCH_DE and colour.delta_e_2000(lb, y) <= PAIR_MATCH_DE:
                return p
    return None


def pair_valid(a, b, pairs):
    """The outfit pairing rules for two scored items (combinations.md §5).
    Slot rules for black and white have already been applied — the verdicts
    are on the items. Returns {"valid", "kind", "flag", "pair", "generator"}."""
    na, nb = is_neutral_item(a), is_neutral_item(b)
    if not na and not nb:
        p = _matched_pair(a, b, pairs)
        return {"valid": p is not None, "kind": "chromatic+chromatic",
                "flag": None if p else "no generated pair",
                "pair": p.name if p else None, "generator": p.generator if p else None}
    if na and nb:
        d_L = abs(a["dominant"]["lab"][0] - b["dominant"]["lab"][0])
        ok = d_L >= NEUTRAL_MIN_DL
        return {"valid": ok, "kind": "neutral+neutral", "flag": None if ok else "flat",
                "pair": None, "generator": None}
    ok = a["verdict"] == "in" and b["verdict"] == "in"
    return {"valid": ok, "kind": "chromatic+neutral", "flag": None if ok else "not in palette",
            "pair": None, "generator": "ground" if ok else None}


def outfit_valid(scored, pairs):
    """Every pair in the outfit must be valid. Three or more chromatic items
    with any invalid chromatic pair flags "too many colours"."""
    checks, flags = [], []
    for i in range(len(scored)):
        for j in range(i + 1, len(scored)):
            v = pair_valid(scored[i], scored[j], pairs)
            checks.append({"items": [scored[i]["item_id"], scored[j]["item_id"]], **v})
            if v["flag"]:
                flags.append(v["flag"])
    chromatic = [r for r in scored if not is_neutral_item(r)]
    if len(chromatic) >= 3 and any(c["kind"] == "chromatic+chromatic" and not c["valid"] for c in checks):
        flags.append("too many colours")
    return {"valid": all(c["valid"] for c in checks), "flags": flags, "pairs": checks}


# ================================================================ §3 outfit checks

def _by_slot(scored):
    by_slot = {s: None for s in SLOTS}
    for r in scored:
        if by_slot[r["slot"]] is None:
            by_slot[r["slot"]] = r
    return by_slot


def zone_fit(filled, dress_code):
    """§3 zone fit — every filled item's dressiness within ZONE_TOLERANCE of
    the occasion's dress code, else "too casual" / "too dressy" per item.
    Not checked when the outfit has no occasion."""
    if dress_code is None:
        return {"dress_code": None, "checked": False, "flags": []}
    flags = []
    for r in filled:
        d = r.get("dressiness")
        if d is None:
            flags.append({"item_id": r["item_id"], "slot": r["slot"], "dressiness": None, "flag": "dressiness not set"})
        elif d < dress_code - ZONE_TOLERANCE:
            flags.append({"item_id": r["item_id"], "slot": r["slot"], "dressiness": d, "flag": "too casual"})
        elif d > dress_code + ZONE_TOLERANCE:
            flags.append({"item_id": r["item_id"], "slot": r["slot"], "dressiness": d, "flag": "too dressy"})
    return {"dress_code": dress_code, "checked": True, "flags": flags}


def weather_fit(by_slot, weather):
    """§3 weather fit — in rain the layer slot is required and the outfit's
    heaviest item must weigh at least RAIN_MIN_WEIGHT, else "not enough for
    rain". The layer is otherwise optional and never a coverage gap."""
    filled = [r for r in by_slot.values() if r]
    weights = [r["weight"] for r in filled if r.get("weight") is not None]
    heaviest = max(weights) if weights else None
    layer = by_slot["layer"] is not None
    if weather != "rain":
        return {"weather": weather, "checked": weather is not None, "layer_present": layer,
                "heaviest": heaviest, "flag": None}
    ok = layer and heaviest is not None and heaviest >= RAIN_MIN_WEIGHT
    return {"weather": weather, "checked": True, "layer_present": layer, "heaviest": heaviest,
            "flag": None if ok else "not enough for rain"}


def outfit_checks(scored, season, dress_code=None, weather=None):
    """The checks on a set of scored items that sit in the slots (one item per
    slot at most): coverage, palette share, tier balance, contrast, the warm
    partner note, zone fit and weather fit."""
    by_slot = _by_slot(scored)
    filled = [r for r in by_slot.values() if r]

    # coverage — the five body slots; layer is optional
    missing = [s for s in COVERAGE_SLOTS if by_slot[s] is None]

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
            "warm_partner": {"flag": warm_flag},
            "zone": zone_fit(filled, dress_code),
            "weather": weather_fit(by_slot, weather)}


# ================================================================ §4 gaps

def find_gaps(scored, checks):
    """The gaps in one outfit. Each carries a `key` so the same gap can be
    recognised across outfits when unlock counts are taken."""
    gaps = []
    for slot in checks["coverage"]["missing"]:
        gaps.append({"type": "empty_slot", "slot": slot, "key": ("empty_slot", slot)})
    for r in scored:
        if r["verdict"] in ("near", "out", "hard_miss"):
            gaps.append({"type": r["verdict"], "slot": r["slot"], "item_id": r["item_id"],
                         "nearest": r["admitted_nearest"], "delta_e": r["admitted_delta_e"],
                         "where": r["where"], "key": (r["verdict"], r["item_id"])})
    for z in checks["zone"]["flags"]:
        t = z["flag"].replace(" ", "_")
        gaps.append({"type": t, "slot": z["slot"], "item_id": z["item_id"], "flag": z["flag"],
                     "dressiness": z["dressiness"], "key": (t, z["item_id"])})
    if checks["weather"]["flag"]:
        gaps.append({"type": "not_enough_for_rain", "slot": "layer", "flag": checks["weather"]["flag"],
                     "key": ("not_enough_for_rain",)})
    if checks["tier_mix"]["flag"]:
        gaps.append({"type": "tier_imbalance", "slot": None, "flag": checks["tier_mix"]["flag"],
                     "key": ("tier_imbalance", checks["tier_mix"]["flag"])})
    if checks["contrast"]["flag"]:
        gaps.append({"type": "contrast_mismatch", "slot": None, "flag": checks["contrast"]["flag"],
                     "key": ("contrast_mismatch",)})
    return gaps


def zone_gaps(closet_scored, outfits):
    """§4 zone gap — for each occasion, a slot where the closet holds no item
    within ZONE_TOLERANCE of the dress code, phrased "no [slot] dressy enough
    for [occasion]". Only raised where the closet holds items in that slot at
    all: an empty closet slot is already the empty-slot gap. The layer slot is
    checked for occasions that have a rain outfit, since the layer is required
    there. `unlocks` is the number of outfits with that occasion."""
    gaps = []
    seen = set()
    for o in outfits:
        occ, dc = o.get("occasion"), o.get("dress_code")
        if occ is None or dc is None or (occ, dc) in seen:
            continue
        seen.add((occ, dc))
        same = [x for x in outfits if x.get("occasion") == occ and x.get("dress_code") == dc]
        slots = list(COVERAGE_SLOTS) + (["layer"] if any(x.get("weather") == "rain" for x in same) else [])
        for slot in slots:
            in_slot = [r for r in closet_scored if r["slot"] == slot]
            if not in_slot:
                continue
            if not any(r.get("dressiness") is not None and abs(r["dressiness"] - dc) <= ZONE_TOLERANCE
                       for r in in_slot):
                gaps.append({"type": "zone_gap", "slot": slot, "occasion": occ, "dress_code": dc,
                             "flag": f"no {slot} dressy enough for {occ}", "unlocks": len(same),
                             "key": ("zone_gap", slot, occ, dc), "outfit": same[0]["name"]})
    return gaps


def rank_gaps(outfits, closet_scored):
    """§4 — one list of gaps across all outfits, ranked by how many outfits
    the fix would complete or repair (`unlocks`); ties break by severity:
    empty slot, hard miss, out, near, zone gap, too casual / too dressy, not
    enough for rain, tier, contrast. Each gap names the first outfit it was
    found in, which is the outfit its fill is searched against."""
    merged = {}
    for o in outfits:
        for g in o["gaps"]:
            key = g["key"]
            if key not in merged:
                merged[key] = {k: v for k, v in g.items() if k != "key"}
                merged[key]["unlocks"] = 0
                merged[key]["outfit"] = o["name"]
                merged[key]["outfits"] = []
            merged[key]["unlocks"] += 1
            merged[key]["outfits"].append(o["name"])
    ranked = list(merged.values())
    for z in zone_gaps(closet_scored, outfits):
        z.pop("key", None)
        z["outfits"] = [x["name"] for x in outfits if x.get("occasion") == z["occasion"]]
        ranked.append(z)
    return sorted(ranked, key=lambda g: (-g["unlocks"], GAP_SEVERITY[g["type"]]))


# ================================================================ §5 fills

def _pairs_with(r, others, pairs):
    """How many of `others` (scored items) `r` forms a valid pair with."""
    return sum(1 for o in others if pair_valid(r, o, pairs)["valid"])


def fill_from_closet(gap, outfit_scored, closet_scored, pairs, dress_code=None):
    """Source 1 — the user's own closet. Filter to the gap's slot, keep
    in-palette candidates not already in the outfit (and within the occasion's
    dress code when there is one), require the outfit to stay valid under the
    pairing rules with the candidate in it, and take the one that pairs with
    most of what is there."""
    if not gap.get("slot"):
        return None
    in_outfit = {r["item_id"] for r in outfit_scored}
    others = [r for r in outfit_scored if r["slot"] != gap["slot"]]
    best = None
    for c in closet_scored:
        if c["slot"] != gap["slot"] or c["item_id"] in in_outfit or c["verdict"] != "in":
            continue
        if dress_code is not None and (c.get("dressiness") is None
                                       or abs(c["dressiness"] - dress_code) > ZONE_TOLERANCE):
            continue
        if others and not outfit_valid(others + [c], pairs)["valid"]:
            continue
        n = _pairs_with(c, others, pairs)
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


def fill_gap(gap, outfit_scored, closet_scored, season, pairs, dress_code=None):
    """§5 — the three sources in strict order; stop at the first that answers."""
    for fn in (lambda: fill_from_closet(gap, outfit_scored, closet_scored, pairs, dress_code),
               lambda: fill_from_staples(gap, season),
               lambda: fill_from_brands(gap, season)):
        fill = fn()
        if fill:
            return fill
    return None


# ================================================================ outfits

def score_outfits(specs, season, closet_items, pairs=None):
    """Score every outfit spec and rank the gaps across them (§3, §4, §5).

    Each spec: {"name", "occasion", "dress_code", "weather", "items": [...]}.
    Returns {"outfits": [...], "gaps_ranked": [...]}. An outfit `passes` when
    it is valid under the pairing rules and carries no zone or weather flag.
    """
    if pairs is None:
        pairs = [p for lst in generators.run(season.anchors).values() for p in lst]
    closet_scored = score_items(closet_items, season)
    by_id = {r["item_id"]: r for r in closet_scored}
    outfits = []
    for spec in specs:
        scored = [by_id[i["id"]] if i.get("id") in by_id else score_item(i, season) for i in spec["items"]]
        # the layer yields the face to an in-palette near-face accessory (§2):
        # the accessory is the face colour, so the layer is re-scored away from it
        face_colour = next((r["item_id"] for r in scored
                            if r["slot"] == "accessory" and r["near_face"] and r["verdict"] == "in"), None)
        if face_colour:
            scored = [score_item(i, season, layer_face=False) if i["slot"] == "layer" else r
                      for i, r in zip(spec["items"], scored)]
        checks = outfit_checks(scored, season, spec.get("dress_code"), spec.get("weather"))
        pairing = outfit_valid(scored, pairs)
        passes = pairing["valid"] and not checks["zone"]["flags"] and not checks["weather"]["flag"]
        outfits.append({"name": spec.get("name"), "occasion": spec.get("occasion"),
                        "dress_code": spec.get("dress_code"), "weather": spec.get("weather"),
                        "face_colour": face_colour,
                        "slots": _by_slot(scored), "checks": checks,
                        "pairing": {"valid": pairing["valid"], "flags": pairing["flags"]},
                        "passes": passes, "gaps": find_gaps(scored, checks)})
    ranked = rank_gaps(outfits, closet_scored)
    by_name = {o["name"]: o for o in outfits}
    for g in ranked:
        o = by_name.get(g.get("outfit"))
        outfit_scored = [r for r in o["slots"].values() if r] if o else []
        g["fill"] = fill_gap(g, outfit_scored, closet_scored, season, pairs,
                             o.get("dress_code") if o else None) if g["type"] != "zone_gap" else None
    return {"outfits": outfits, "gaps_ranked": ranked}


def score_outfit(outfit_items, season, closet_items=None, outfit_id=None, occasion=None,
                 dress_code=None, weather=None):
    """matching.md §6 — the matcher's output for one outfit. A convenience
    over `score_outfits` for a single spec."""
    spec = {"name": outfit_id, "occasion": occasion, "dress_code": dress_code,
            "weather": weather, "items": outfit_items}
    out = score_outfits([spec], season, closet_items if closet_items is not None else outfit_items)
    o = out["outfits"][0]
    return {"outfit_id": outfit_id, "season": season.key, "slots": o["slots"], "checks": o["checks"],
            "pairing": o["pairing"], "passes": o["passes"], "gaps_ranked": out["gaps_ranked"]}
