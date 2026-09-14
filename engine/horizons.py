"""Horizons — horizons.md §2 to §4. The result screen as data.

Take a season, a direction and the items; return the matcher's JSON for the
outfit in hand (matching.md §6) extended with the long-term horizon (ideal
palette, combinations, rules, direction of travel) and the short-term horizon
(current palette sorted into tiers, the distance figure, works-now outfits,
ranked next moves). The language model writes the sentences; nothing here is
prose.
"""
from itertools import product

from . import colour, generators, matcher, palette
from .palette import TIERS, TIER_SHARE

DISTANCE_BANDS = ((10, "matches"), (18, "mostly there"), (28, "real gap"), (float("inf"), "disagree"))
MIN_PAIRS_FOR_NEXT_MOVE = 2   # §3d constraint
COMBINATIONS_SHOWN = 5        # §2: three to five named pairs


def _reading(distance):
    for limit, label in DISTANCE_BANDS:
        if distance <= limit:
            return label
    return "disagree"


# ---------------------------------------------------------------- §2 long-term

def long_term(season, confidence=None, mood=None):
    """Season, ideal palette, combinations, rules in force. `confidence` (axis
    -> high/medium/low) is needed for the runner-up; without it the runner-up
    is null rather than guessed."""
    direction = season.direction
    direction_anchor = season.directions[direction]["anchor"] if direction else None
    gen = generators.generate(season.anchors, mood=mood, direction_anchor=direction_anchor)
    runner = palette.runner_up(season.key, confidence) if confidence else None
    return {
        "season": season.key,
        "primary": season.primary,
        "secondary": season.secondary,
        "direction": direction,
        "direction_note": season.directions[direction]["note"] if direction else None,
        "runner_up": runner,
        "confidence": confidence,
        "ideal_palette": {t: [a.as_dict() for a in season.tier(t)] for t in TIERS},
        "tier_share": dict(TIER_SHARE),
        "combinations": [p.as_dict() for p in gen["ranked"][:COMBINATIONS_SHOWN]],
        "combinations_all": {name: [p.as_dict() for p in pairs] for name, pairs in gen["lists"].items()},
        "generator_order": gen["order"],
        "rules_in_force": season.rules(),
    }


# ---------------------------------------------------------------- §3a-b current palette and delta

def current_palette(closet_scored, closet_items):
    """Every item's dominant colour sorted into the ideal's tiers by nearest
    anchor (§3a), with share-weighted tier proportions. Items with no tier
    (hard misses, rule hits on colours that are not tier anchors) are listed
    under `unplaced`."""
    share = {i.get("id"): float(i.get("share", 1.0)) for i in closet_items}
    tiers = {t: [] for t in TIERS}
    unplaced = []
    for r in closet_scored:
        entry = {"item_id": r["item_id"], "slot": r["slot"], "hex": r["dominant"]["hex"],
                 "verdict": r["verdict"], "nearest": r["nearest"], "delta_e": r["delta_e"],
                 "share": share.get(r["item_id"], 1.0)}
        (tiers[r["tier"]] if r["tier"] else unplaced).append(entry)
    total = sum(share.values()) or 1.0
    proportions = {t: round(sum(e["share"] for e in tiers[t]) / total, 2) for t in TIERS}
    return {"tiers": tiers, "unplaced": unplaced, "proportions": proportions}


def distance(closet_scored, closet_items):
    """§3b — share-weighted mean ΔE from each item's colour to its nearest
    ideal anchor. Uses the ΔE each verdict reported, so an item allowed by a
    slot rule (black below the waist) counts at its distance to the rule
    colour rather than to a far-off tier anchor."""
    share = {i.get("id"): float(i.get("share", 1.0)) for i in closet_items}
    num = sum(r["delta_e"] * share.get(r["item_id"], 1.0) for r in closet_scored)
    den = sum(share.get(r["item_id"], 1.0) for r in closet_scored)
    d = round(num / den, 1) if den else 0.0
    return {"palette_distance": d, "reading": _reading(d)}


def over_and_missing(closet_scored, season):
    """§3b — over-represented: closet colours whose nearest anchor is accent-tier
    or that are out / hard miss. Missing: foundation or supporting anchors no
    in/near item lands on."""
    over = {}
    for r in closet_scored:
        if r["verdict"] in ("out", "hard_miss") or r["tier"] == "accents":
            over[r["nearest"]] = over.get(r["nearest"], 0) + 1
    landed = {r["nearest"] for r in closet_scored if r["verdict"] in ("in", "near")}
    missing = [a.name for a in season.anchors if a.tier in ("foundations", "supporting")
               and a.name not in landed]
    return {"over_represented": [{"colour": k, "items": v} for k, v in
                                 sorted(over.items(), key=lambda kv: -kv[1])],
            "missing": missing}


# ---------------------------------------------------------------- §3c works now

def _closeness_to_named(lab_a, lab_b, pairs):
    """How close an item pair sits to the nearest generated anchor pair: the
    larger of the two item-to-anchor ΔEs, minimised over the list."""
    best = float("inf")
    for p in pairs:
        for x, y in ((p.dominant.lab, p.counter.lab), (p.counter.lab, p.dominant.lab)):
            d = max(colour.delta_e_2000(lab_a, x), colour.delta_e_2000(lab_b, y))
            best = min(best, d)
    return best


def works_now(closet_scored, season, gen_lists, limit=None):
    """§3c — outfits buildable today from in-palette items. A top and a bottom
    that make a Wada pair are the core; shoes, bag and accessory join when
    they pair with the top or the bottom. Ranked by items used, then by
    closeness to a named combination."""
    ok = [r for r in closet_scored if r["verdict"] == "in"]
    by_slot = {s: [r for r in ok if r["slot"] == s] for s in matcher.SLOTS}
    all_pairs = [p for pairs in gen_lists.values() for p in pairs]
    lab = lambda r: tuple(r["dominant"]["lab"])
    outfits = []
    for top, bottom in product(by_slot["top"], by_slot["bottom"]):
        gen = generators.pair_passes(lab(top), lab(bottom))
        if not gen:
            continue
        items = [top, bottom]
        for slot in ("shoes", "bag", "accessory"):
            for cand in by_slot[slot]:
                if generators.pair_passes(lab(cand), lab(top)) or generators.pair_passes(lab(cand), lab(bottom)):
                    items.append(cand)
                    break
        outfits.append({"items": [r["item_id"] for r in items],
                        "core_pair": [top["item_id"], bottom["item_id"]],
                        "generator": gen,
                        "closeness_to_named": round(_closeness_to_named(lab(top), lab(bottom), all_pairs), 1)})
    outfits.sort(key=lambda o: (-len(o["items"]), o["closeness_to_named"]))
    return outfits[:limit] if limit else outfits


# ---------------------------------------------------------------- §3d next moves

def next_moves(outfit_result, closet_scored, closet_items, season, limit=3):
    """§3d — the one to three moves that would do the most, scored
    value = outfits_unlocked × palette_improvement ÷ price_band.

    With sources 2 and 3 stubbed, every fill comes from the closet, so:
    outfits_unlocked is the number of closet items the piece pairs with;
    palette_improvement is how far the outfit's mean ΔE falls when the piece
    takes the gap's slot; price_band is 1 (already owned). A move must pair
    with at least two owned items (§3d constraint) or it is dropped.
    """
    moves = []
    outfit_scored = [r for r in outfit_result["slots"].values() if r]
    before = sum(r["delta_e"] for r in outfit_scored) / len(outfit_scored) if outfit_scored else 0.0
    for gap in outfit_result["gaps_ranked"]:
        fill = gap.get("fill")
        if not fill or fill["source"] != "closet":
            continue
        piece = next(r for r in closet_scored if r["item_id"] == fill["item_id"])
        others = [r for r in closet_scored if r["item_id"] != piece["item_id"]]
        unlocked = matcher._pairs_with(tuple(piece["dominant"]["lab"]), others)
        if unlocked < MIN_PAIRS_FOR_NEXT_MOVE:
            continue
        after_items = [r for r in outfit_scored if r["slot"] != gap["slot"]] + [piece]
        after = sum(r["delta_e"] for r in after_items) / len(after_items)
        improvement = round(before - after, 2)
        moves.append({"source": fill["source"], "item_id": piece["item_id"], "slot": gap["slot"],
                      "for_gap": gap["type"], "nearest": piece["nearest"],
                      "outfits_unlocked": unlocked, "palette_improvement": improvement,
                      "price_band": 1, "value": round(unlocked * improvement / 1, 2)})
    moves.sort(key=lambda m: -m["value"])
    return moves[:limit]


# ---------------------------------------------------------------- direction of travel

def direction_of_travel(current, over_missing):
    """§2 — the data behind the one-paragraph steer: which tier should grow
    (largest shortfall against 55/30/15), which colours should fade, which are
    missing. The investment piece needs the brand database and is null."""
    shortfall = {t: TIER_SHARE[t] - current["proportions"][t] for t in TIERS}
    grow = max(shortfall, key=shortfall.get)
    return {"grow_tier": grow if shortfall[grow] > 0 else None,
            "tier_shortfall": {t: round(v, 2) for t, v in shortfall.items()},
            "fade_colours": [o["colour"] for o in over_missing["over_represented"]],
            "missing_colours": over_missing["missing"],
            "investment_piece": None}


# ---------------------------------------------------------------- the result

def result(season_key, direction, items, outfit=None, mood=None, confidence=None,
           saved_outfits=None, outfit_id=None, seasons_path=None):
    """The full result screen as JSON-ready data.

    - `season_key`, `direction`: from colour-system.md.
    - `items`: the closet — every uploaded item, as matcher item dicts.
    - `outfit`: item ids on the canvas; defaults to the best works-now outfit,
      or an empty canvas if none works.
    - `mood`: the free-text answer to intake question 2.
    - `confidence`: axis -> high/medium/low, for the runner-up season.
    """
    season = palette.get_season(season_key, seasons_path)
    if direction:
        season = palette.apply_direction(season, direction)
    closet_scored = matcher.score_items(items, season)
    lt = long_term(season, confidence=confidence, mood=mood)
    gen_lists = generators.run(season.anchors)
    works = works_now(closet_scored, season, gen_lists)

    if outfit is None:
        outfit = works[0]["items"] if works else []
    by_id = {i.get("id"): i for i in items}
    outfit_items = [by_id[i] for i in outfit]
    result_ = matcher.score_outfit(outfit_items, season, closet_items=items,
                                   saved_outfits=saved_outfits, outfit_id=outfit_id)

    current = current_palette(closet_scored, items)
    om = over_and_missing(closet_scored, season)
    result_.update({
        "long_term": {**lt, "direction_of_travel": direction_of_travel(current, om)},
        "short_term": {
            "current_palette": current,
            "distance": distance(closet_scored, items),
            **om,
            "works_now": works,
            "next_moves": next_moves(result_, closet_scored, items, season),
        },
    })
    return result_
