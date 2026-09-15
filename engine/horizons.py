"""Horizons — horizons.md §2 to §4. The result screen as data.

Take a season, a direction, the items and (optionally) the person's saved
outfits with their occasions; return the matcher's JSON (matching.md §6)
extended with the long-term horizon (ideal palette, combinations, rules,
direction of travel) and the short-term horizon (current palette sorted into
tiers, the distance figure, works-now outfits, ranked next moves). The
language model writes the sentences; nothing here is prose.
"""
from itertools import product

from . import generators, matcher, palette
from .palette import TIERS, TIER_SHARE

DISTANCE_BANDS = ((10, "matches"), (18, "mostly there"), (28, "real gap"), (float("inf"), "disagree"))
MIN_PAIRS_FOR_NEXT_MOVE = 2   # §3d constraint
COMBINATIONS_SHOWN = 5        # §2: three to five named pairs
MIN_ITEMS_FOR_MISSING = 10    # §3b: below this the "missing" list is not judged
NOT_ENOUGH_ITEMS = "not enough items to judge — add more before reading this"
AUTO_OUTFIT = "auto: first item per slot"


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
                 "dressiness": r.get("dressiness"), "weight": r.get("weight"),
                 "share": share.get(r["item_id"], 1.0)}
        (tiers[r["tier"]] if r["tier"] else unplaced).append(entry)
    total = sum(share.values()) or 1.0
    proportions = {t: round(sum(e["share"] for e in tiers[t]) / total, 2) for t in TIERS}
    return {"tiers": tiers, "unplaced": unplaced, "proportions": proportions}


def distance(closet_scored, closet_items):
    """§3b — share-weighted mean of each item's contribution: its ΔE to the
    nearest anchor that would be "in" for that item's slot after the slot
    rules, never to the colour that triggered a hard miss. Black trousers
    admitted below the waist contribute 0; a white shirt at the face
    contributes its ΔE to cream; out items contribute their ΔE to the nearest
    palette anchor."""
    share = {i.get("id"): float(i.get("share", 1.0)) for i in closet_items}
    num = sum(r["admitted_delta_e"] * share.get(r["item_id"], 1.0) for r in closet_scored)
    den = sum(share.get(r["item_id"], 1.0) for r in closet_scored)
    d = round(num / den, 1) if den else 0.0
    return {"palette_distance": d, "reading": _reading(d)}


def pulling_against(closet_scored):
    """§3b — the items whose verdict is not "in", each with its verdict, where
    the rule caught it, and its nearest admitted anchor as the fix; ordered by
    contribution to the distance, largest first."""
    over = [{"item": r["item_id"], "verdict": r["verdict"], "where": r["where"],
             "nearest": r["admitted_nearest"], "delta_e": r["admitted_delta_e"]}
            for r in closet_scored if r["verdict"] != "in"]
    over.sort(key=lambda o: -o["delta_e"])
    return over


def missing(closet_scored, season):
    """§3b — foundation-tier anchors no in/near item lands on. Judged only
    when the closet holds MIN_ITEMS_FOR_MISSING items or more; below that the
    list is null and `note` says so."""
    if len(closet_scored) < MIN_ITEMS_FOR_MISSING:
        return {"anchors": None, "note": NOT_ENOUGH_ITEMS, "items_in_closet": len(closet_scored)}
    landed = {r["nearest"] for r in closet_scored if r["verdict"] in ("in", "near")}
    return {"anchors": [a.name for a in season.anchors if a.tier == "foundations" and a.name not in landed],
            "note": None, "items_in_closet": len(closet_scored)}


# ---------------------------------------------------------------- §3c works now

def _closeness_to_named(scored):
    """How close an outfit sits to a named combination: the largest ΔE from any
    chromatic item to its nearest anchor. 0 when the outfit is all neutrals."""
    ds = [r["delta_e"] for r in scored if not matcher.is_neutral_item(r)]
    return max(ds) if ds else 0.0


def works_now_generated(closet_scored, gen_lists, limit=None):
    """§3c without saved outfits — outfits buildable today from in-palette
    items under the outfit pairing rules (combinations.md §5). A top and a
    bottom that form a valid pair are the core; layer, shoes, bag and
    accessory join when the outfit stays valid with them in it. Ranked by
    items used, then by closeness to a named combination."""
    ok = [r for r in closet_scored if r["verdict"] == "in"]
    by_slot = {s: [r for r in ok if r["slot"] == s] for s in matcher.SLOTS}
    pairs = [p for lst in gen_lists.values() for p in lst]
    outfits = []
    for top, bottom in product(by_slot["top"], by_slot["bottom"]):
        core = matcher.pair_valid(top, bottom, pairs)
        if not core["valid"]:
            continue
        items = [top, bottom]
        for slot in ("layer", "shoes", "bag", "accessory"):
            for cand in by_slot[slot]:
                if matcher.outfit_valid(items + [cand], pairs)["valid"]:
                    items.append(cand)
                    break
        check = matcher.outfit_valid(items, pairs)
        outfits.append({"name": None, "occasion": None, "items": [r["item_id"] for r in items],
                        "core_pair": [top["item_id"], bottom["item_id"]],
                        "pairing": core["kind"], "generator": core["generator"],
                        "matched_pair": core["pair"], "flags": check["flags"],
                        "closeness_to_named": round(_closeness_to_named(items), 1)})
    outfits.sort(key=lambda o: (-len(o["items"]), o["closeness_to_named"]))
    return outfits[:limit] if limit else outfits


def works_now_saved(outfits):
    """§3c with saved outfits — the ones that pass the pairing rules and both
    the zone and weather checks, in the order given."""
    return [{"name": o["name"], "occasion": o["occasion"], "dress_code": o["dress_code"],
             "weather": o["weather"], "items": [r["item_id"] for r in o["slots"].values() if r],
             "flags": []} for o in outfits if o["passes"]]


# ---------------------------------------------------------------- §3d next moves

def next_moves(gaps_ranked, outfits, closet_scored, pairs, limit=3):
    """§3d — the one to three moves that would do the most, scored
    value = outfits_unlocked × palette_improvement ÷ price_band.

    With sources 2 and 3 stubbed, every fill comes from the closet, so:
    outfits_unlocked is the number of closet items the piece forms a valid
    pair with under the pairing rules (combinations.md §5);
    palette_improvement is how far the outfit's mean contribution falls when
    the piece takes the gap's slot; price_band is 1 (already owned). A move
    must pair with at least two owned items (§3d constraint) or it is dropped.
    """
    by_name = {o["name"]: o for o in outfits}
    moves = []
    for gap in gaps_ranked:
        fill = gap.get("fill")
        if not fill or fill["source"] != "closet":
            continue
        o = by_name.get(gap.get("outfit"))
        outfit_scored = [r for r in o["slots"].values() if r] if o else []
        before = sum(r["admitted_delta_e"] for r in outfit_scored) / len(outfit_scored) if outfit_scored else 0.0
        piece = next(r for r in closet_scored if r["item_id"] == fill["item_id"])
        others = [r for r in closet_scored if r["item_id"] != piece["item_id"]]
        unlocked = matcher._pairs_with(piece, others, pairs)
        if unlocked < MIN_PAIRS_FOR_NEXT_MOVE:
            continue
        after_items = [r for r in outfit_scored if r["slot"] != gap["slot"]] + [piece]
        after = sum(r["admitted_delta_e"] for r in after_items) / len(after_items)
        improvement = round(before - after, 2)
        moves.append({"source": fill["source"], "item_id": piece["item_id"], "slot": gap["slot"],
                      "for_gap": gap["type"], "outfit": gap.get("outfit"), "nearest": piece["nearest"],
                      "outfits_unlocked": unlocked, "palette_improvement": improvement,
                      "price_band": 1, "value": round(unlocked * improvement / 1, 2)})
    moves.sort(key=lambda m: -m["value"])
    return moves[:limit]


# ---------------------------------------------------------------- direction of travel

def direction_of_travel(current, over, missing_):
    """§2 — the data behind the one-paragraph steer: which tier should grow
    (largest shortfall against 55/30/15), which items are pulling against the
    palette and could fade, which colours are missing. The investment piece
    needs the brand database and is null."""
    shortfall = {t: TIER_SHARE[t] - current["proportions"][t] for t in TIERS}
    grow = max(shortfall, key=shortfall.get)
    return {"grow_tier": grow if shortfall[grow] > 0 else None,
            "tier_shortfall": {t: round(v, 2) for t, v in shortfall.items()},
            "fade_items": [o["item"] for o in over],
            "missing_colours": missing_["anchors"],
            "missing_note": missing_["note"],
            "investment_piece": None}


# ---------------------------------------------------------------- the result

def _auto_spec(items):
    """No outfits file: one outfit from the first closet item in each slot."""
    chosen = []
    seen = set()
    for i in items:
        if i["slot"] not in seen:
            seen.add(i["slot"])
            chosen.append(i)
    return {"name": AUTO_OUTFIT, "occasion": None, "dress_code": None, "weather": None, "items": chosen}


def result(season_key, direction, items, outfits=None, mood=None, confidence=None,
           outfit_id=None, seasons_path=None):
    """The full result screen as JSON-ready data.

    - `season_key`, `direction`: from colour-system.md.
    - `items`: the closet — every uploaded item, as matcher item dicts.
    - `outfits`: saved outfit specs {"name", "occasion", "dress_code",
      "weather", "slots": {slot: item id or None}}; when absent, one outfit is
      built from the first item per slot and works-now is generated.
    - `mood`: the free-text answer to intake question 2.
    - `confidence`: axis -> high/medium/low, for the runner-up season.
    """
    season = palette.get_season(season_key, seasons_path)
    if direction:
        season = palette.apply_direction(season, direction)
    closet_scored = matcher.score_items(items, season)
    lt = long_term(season, confidence=confidence, mood=mood)
    gen_lists = generators.run(season.anchors)
    pairs = [p for lst in gen_lists.values() for p in lst]
    by_id = {i.get("id"): i for i in items}

    if outfits:
        mode = "saved"
        specs = []
        for o in outfits:
            names = [o["slots"].get(s) for s in matcher.SLOTS]
            specs.append({"name": o["name"], "occasion": o.get("occasion"), "dress_code": o.get("dress_code"),
                          "weather": o.get("weather"), "items": [by_id[n] for n in names if n]})
    else:
        mode = "auto"
        specs = [_auto_spec(items)]

    wardrobe = matcher.score_outfits(specs, season, items, pairs)
    works = works_now_saved(wardrobe["outfits"]) if mode == "saved" else works_now_generated(closet_scored, gen_lists)

    current = current_palette(closet_scored, items)
    over = pulling_against(closet_scored)
    miss = missing(closet_scored, season)
    first = wardrobe["outfits"][0]
    return {
        "outfit_id": outfit_id or first["name"],
        "season": season.key,
        "mode": mode,
        "outfits": wardrobe["outfits"],
        "slots": first["slots"],
        "checks": first["checks"],
        "gaps_ranked": wardrobe["gaps_ranked"],
        "long_term": {**lt, "direction_of_travel": direction_of_travel(current, over, miss)},
        "short_term": {
            "current_palette": current,
            "distance": distance(closet_scored, items),
            "over_represented": over,
            "missing": miss,
            "works_now": works,
            "next_moves": next_moves(wardrobe["gaps_ranked"], wardrobe["outfits"], closet_scored, pairs),
        },
    }
