"""Horizons — horizons.md §2 to §4. The result screen as data.

Take a season, a direction, the items and (optionally) the person's saved
outfits with their occasions; return the matcher's JSON (matching.md §6)
extended with the long-term horizon (ideal palette, combinations, rules,
direction of travel) and the short-term horizon (current palette sorted into
tiers, the distance figure, works-now outfits, ranked next moves). The
language model writes the sentences; nothing here is prose.
"""
from itertools import product

from . import colour, generators, matcher, palette
from .palette import TIERS, TIER_SHARE

DISTANCE_BANDS = ((10, "matches"), (18, "mostly there"), (28, "real gap"), (float("inf"), "disagree"))
MIN_PAIRS_FOR_NEXT_MOVE = 2   # §3d constraint
COMBINATIONS_SHOWN = 5        # §2: three to five named pairs
MIN_ITEMS_FOR_MISSING = 10    # §3b: below this the "missing" list is not judged

# §3c — works-now is ranked by pairing kind first. The three generator names come
# from combinations.md §3; the other three are the pairing kinds of §5.
WORKS_NOW_ORDER = ("opposition", "muted", "tonal", "monochrome", "chromatic+neutral", "neutral+neutral")
# A calm / quiet / grounded mood promotes tonal and monochrome above opposition, and
# keeps the generators in the order combinations.md gives them under that mood
# (tonal, then muted, then opposition).
WORKS_NOW_ORDER_CALM = ("tonal", "monochrome", "muted", "opposition", "chromatic+neutral", "neutral+neutral")
NOT_ENOUGH_ITEMS = "not enough items to judge — add more before reading this"
HIGH_CARE_SHARE = 0.25        # §3d materials: over this share, "you said easy" is a contradiction
EASY_WORDS = ("easy", "low-maintenance", "low maintenance", "no fuss", "fuss-free", "throw on")
STRATEGIC_PIECES = 3          # §2b: strongest pieces shown per direction
DIRECTION_COMBINATIONS = 3    # §2b: combinations shown per direction
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

def _pair_kind(check):
    """The ranking kind of one pair: the generator's name for a pair the
    generators produced, otherwise the pair's own kind (§5)."""
    if check["kind"] == "chromatic+chromatic" and check.get("generator"):
        return check["generator"]
    return check["kind"]


def _ranking_kind(core, check, order):
    """An outfit's kind for ranking. A top-and-bottom core is its own pair's
    kind. A dress core has no pair of its own, so it takes the best kind among
    the outfit's actual pairs; a dress worn alone has none and sorts last."""
    if core["kind"] != "dress":
        return _pair_kind(core)
    kinds = [k for k in (_pair_kind(c) for c in check["pairs"] if c["valid"]) if k in order]
    return min(kinds, key=order.index) if kinds else None


def _closeness_to_named(scored):
    """How close an outfit sits to a named combination: the largest ΔE from any
    chromatic item to its nearest anchor. 0 when the outfit is all neutrals."""
    ds = [r["delta_e"] for r in scored if not matcher.is_neutral_item(r)]
    return max(ds) if ds else 0.0


def works_now_generated(closet_scored, gen_lists, limit=None, mood=None):
    """§3c without saved outfits — outfits buildable today from in-palette
    items under the outfit pairing rules (combinations.md §5). A top and a
    bottom that form a valid pair are the core; layer, shoes, bag and
    accessory join when the outfit stays valid with them in it.

    Ranked by pairing kind first (WORKS_NOW_ORDER, or WORKS_NOW_ORDER_CALM
    when the mood answer is calm, quiet or grounded), then by items used,
    then by closeness to a named combination."""
    order = WORKS_NOW_ORDER_CALM if generators.is_calm(mood) else WORKS_NOW_ORDER
    ok = [r for r in closet_scored if r["verdict"] == "in"]
    by_slot = {s: [r for r in ok if r["slot"] == s] for s in matcher.SLOTS}
    pairs = [p for lst in gen_lists.values() for p in lst]
    outfits = []
    cores = [((top, bottom), matcher.pair_valid(top, bottom, pairs))
             for top, bottom in product(by_slot["top"], by_slot["bottom"])]
    cores += [((dress,), {"valid": True, "kind": "dress", "generator": None, "pair": None})
              for dress in by_slot["dress"]]
    for core_items, core in cores:
        if not core["valid"]:
            continue
        items = list(core_items)
        for slot in ("layer", "shoes", "bag", "accessory"):
            for cand in by_slot[slot]:
                if matcher.outfit_valid(items + [cand], pairs)["valid"]:
                    items.append(cand)
                    break
        check = matcher.outfit_valid(items, pairs)
        outfits.append({"name": None, "occasion": None, "items": [r["item_id"] for r in items],
                        "core_pair": [r["item_id"] for r in core_items],
                        "pairing": core["kind"], "generator": core["generator"],
                        "kind": _ranking_kind(core, check, order),
                        "matched_pair": core["pair"], "flags": check["flags"],
                        "closeness_to_named": round(_closeness_to_named(items), 1)})
    outfits.sort(key=lambda o: (order.index(o["kind"]) if o["kind"] in order else len(order),
                                -len(o["items"]), o["closeness_to_named"]))
    return outfits[:limit] if limit else outfits


def works_now_saved(outfits):
    """§3c with saved outfits — the ones that pass the pairing rules and the
    zone, weather and context checks, in the order given. Saved outfits keep
    the person's own order; the kind ranking applies to the generated list."""
    return [{"name": o["name"], "occasion": o["occasion"], "dress_code": o["dress_code"],
             "weather": o["weather"], "formality": o.get("formality"), "setting": o.get("setting"),
             "items": [r["item_id"] for r in o["slots"].values() if r],
             "flags": []} for o in outfits if o["passes"]]


# ---------------------------------------------------------------- colour shares and improvement

def colour_shares(scored):
    """Every item's dominant colour weighted by the area of the body it covers
    (matcher.AREA_WEIGHT), as shares summing to 1. This is the outfit's
    colour-share bar."""
    total = sum(r["area"] for r in scored) or 1.0
    return [{"item_id": r["item_id"], "slot": r["slot"], "hex": r["dominant"]["hex"],
             "verdict": r["verdict"], "nearest": r["nearest"], "delta_e": r["delta_e"],
             "fibre": r.get("fibre"), "surface": r.get("surface"),
             "area": r["area"], "share": round(r["area"] / total, 3)}
            for r in sorted(scored, key=lambda r: -r["area"])]


def outfit_distance(scored):
    """The outfit's own distance: the mean of its items' admitted ΔE."""
    return round(sum(r["admitted_delta_e"] for r in scored) / len(scored), 2) if scored else 0.0


def best_improvement(outfit, closet_scored, season, pairs):
    """The single addition that most lowers this outfit's distance — one item
    into an empty slot, from the closet, then the staples catalogue, then the
    brand database (the last two are stubs, so today every answer is a closet
    item). Returns the piece, the distance before and after, and the shares the
    outfit would then have."""
    scored = [r for r in outfit["slots"].values() if r]
    before = outfit_distance(scored)
    in_outfit = {r["item_id"] for r in scored}
    empty = [s for s in matcher.COVERAGE_SLOTS if outfit["slots"][s] is None
             and not (s in ("top", "bottom") and outfit["slots"]["dress"])]
    dress_code = outfit.get("dress_code")
    best = None
    for c in closet_scored:
        if c["slot"] not in empty or c["item_id"] in in_outfit or c["verdict"] != "in":
            continue
        if dress_code is not None and (c.get("dressiness") is None
                                       or abs(c["dressiness"] - dress_code) > matcher.ZONE_TOLERANCE):
            continue
        if not matcher.outfit_valid(scored + [c], pairs)["valid"]:
            continue
        after = outfit_distance(scored + [c])
        if best is None or after < best[0]:
            best = (after, c)
    if best is None:
        for stub in (matcher.fill_from_staples, matcher.fill_from_brands):
            if stub({"slot": empty[0] if empty else None}, season):
                break
        return {"source": None, "item_id": None, "before": before, "after": before,
                "improvement": 0.0, "shares": None,
                "reason": "nothing in the closet improves this outfit; staples and brands are not wired up yet"}
    after, c = best
    return {"source": "closet", "item_id": c["item_id"], "slot": c["slot"], "hex": c["dominant"]["hex"],
            "before": before, "after": after, "improvement": round(before - after, 2),
            "shares": colour_shares(scored + [c]),
            "reason": f"adds a {c['slot']} in palette ({c['nearest']})"}


def compositions(outfits):
    """§3c summary — the shapes people actually wear, weighted by life weight.
    A composition is the set of slots an outfit fills."""
    tally = {}
    for o in outfits:
        shape = tuple(s for s in matcher.SLOTS if o["slots"][s])
        w = o.get("life_weight") or matcher.DEFAULT_LIFE_WEIGHT
        e = tally.setdefault(shape, {"composition": " + ".join(shape), "outfits": [], "count": 0,
                                     "life_weight": 0, "passes": 0})
        e["outfits"].append(o["name"])
        e["count"] += 1
        e["life_weight"] += w
        e["passes"] += 1 if o["passes"] else 0
    out = sorted(tally.values(), key=lambda e: (-e["life_weight"], -e["count"]))
    for e in out:
        e["mean_life_weight"] = round(e["life_weight"] / e["count"], 1)
    return out


def where_they_should_head(comps, gaps_ranked):
    """For each composition, the highest-scoring gap that affects one of its
    outfits — where that shape of outfit should go next."""
    out = []
    for c in comps:
        names = set(c["outfits"])
        gap = next((g for g in gaps_ranked if names & set(g.get("outfits") or [])), None)
        out.append({**c, "heads_toward": None if not gap else
                    {"type": gap["type"], "slot": gap.get("slot"), "flag": gap.get("flag"),
                     "score": gap["score"],
                     "fill": (gap.get("fill") or {}).get("item_id")}})
    return out


# ---------------------------------------------------------------- §2b directions, side by side

def directions_block(season, closet_scored, pairs, mood=None):
    """§2b — every direction in the season, side by side: its re-weighted
    palette, its top combinations, and the pieces that would do most for this
    closet. The person picks; the engine does not."""
    owned = [r for r in closet_scored if r["verdict"] in ("in", "near")]
    out = []
    for key in season.directions:
        leaned = palette.apply_direction(season, key)
        gen = generators.generate(leaned.anchors, mood=mood,
                                  direction_anchor=season.directions[key]["anchor"])
        # strategic pieces: anchors this closet has nothing near, ranked by how many
        # owned items each would pair with, then by the direction's own weighting
        strategic = []
        for a in leaned.anchors:
            if any(colour.delta_e_2000(tuple(r["dominant"]["lab"]), a.lab) <= matcher.IN_DE for r in owned):
                continue
            fake = {"item_id": a.name, "slot": "top", "verdict": "in", "near_face": None,
                    "dominant": {"hex": a.hex, "lab": list(a.lab), "relative_chroma": a.rel,
                                 "neutral": generators.is_neutral(a.rel)}}
            pairs_with = matcher._pairs_with(fake, owned, pairs)
            strategic.append({"anchor": a.name, "hex": a.hex, "tier": a.tier,
                              "weight": a.weight, "pairs_with": pairs_with})
        strategic.sort(key=lambda s: (-s["pairs_with"], -s["weight"], s["anchor"]))
        out.append({"direction": key,
                    "note": season.directions[key]["note"],
                    "anchor": season.directions[key]["anchor"],
                    "palette": {t: [a.as_dict() for a in leaned.tier(t)] for t in TIERS},
                    "combinations": [p.as_dict() for p in gen["ranked"][:DIRECTION_COMBINATIONS]],
                    "strategic_pieces": strategic[:STRATEGIC_PIECES]})
    return out


# ---------------------------------------------------------------- §3d materials

def material_notes(materials, closet_scored, outfits, pairs):
    """§3d — two readings of the stated material preferences. Neither changes a
    verdict: they are things to say, not scores."""
    materials = materials or {}
    loves = [f for f in (materials.get("loves") or [])]
    avoids = [f for f in (materials.get("avoids") or [])]
    sentence = (materials.get("note") or materials.get("sentence") or "").strip()
    notes = []

    # 1. a loved fibre that could dress the person head to toe, and never does
    for fibre in loves:
        owned = [r for r in closet_scored if r.get("fibre") == fibre and r["verdict"] == "in"]
        tops = [r for r in owned if r["slot"] == "top"]
        bottoms = [r for r in owned if r["slot"] == "bottom"]
        dresses = [r for r in owned if r["slot"] == "dress"]
        combo = None
        for a, b in [(t, bt) for t in tops for bt in bottoms]:
            if matcher.outfit_valid([a, b], pairs)["valid"]:
                combo = [a["item_id"], b["item_id"]]
                break
        if combo is None and dresses:
            combo = [dresses[0]["item_id"]]
        if not combo:
            continue
        already = any(all((o["slots"][s] is None or o["slots"][s].get("fibre") == fibre)
                          for s in matcher.SLOTS) and any(o["slots"][s] for s in matcher.SLOTS)
                      for o in outfits)
        if not already:
            notes.append({"kind": "suggestion", "fibre": fibre, "items": combo,
                          "text": f"you said you love {fibre} — you can build a whole outfit from it: "
                                  + " + ".join(combo)})

    # 2. "easy" said out loud, against a wardrobe that is not
    if sentence and any(w in sentence.lower() for w in EASY_WORDS):
        total = len(closet_scored)
        high = [r for r in closet_scored if r.get("fibre") in matcher.HIGH_CARE_FIBRES]
        share = len(high) / total if total else 0.0
        if share > HIGH_CARE_SHARE:
            notes.append({"kind": "challenge", "share": round(share, 2),
                          "items": [r["item_id"] for r in high],
                          "text": f"you said easy; {round(share * 100)}% of your wardrobe is high-maintenance "
                                  f"({', '.join(sorted(set(r['fibre'] for r in high)))})"})
    return {"loves": loves, "avoids": avoids, "sentence": sentence or None, "notes": notes}


# ---------------------------------------------------------------- §3d next moves

def next_moves(gaps_ranked, outfits, closet_scored, pairs, limit=3):
    """§3d — the one to three moves that would do the most, scored
    value = outfits_unlocked × palette_improvement ÷ price_band. At equal
    value, a move filling a context gap ranks above one filling a zone gap.

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
    # equal value: the gap's rank order decides, so a context-gap fill sits above a
    # zone-gap fill of the same unlock count (horizons.md §3d)
    moves.sort(key=lambda m: (-m["value"], matcher.GAP_SEVERITY.get(m["for_gap"], 99)))
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
           materials=None, outfit_id=None, seasons_path=None):
    """The full result screen as JSON-ready data.

    - `season_key`, `direction`: from colour-system.md.
    - `items`: the closet — every uploaded item, as matcher item dicts.
    - `outfits`: saved outfit specs {"name", "occasion", "dress_code",
      "weather", "slots": {slot: item id or None}}; when absent, one outfit is
      built from the first item per slot and works-now is generated.
    - `mood`: the free-text answer to intake question 2.
    - `confidence`: axis -> high/medium/low, for the runner-up season.
    - `materials`: the intake file's material preferences (loves, avoids, note).
      They are reported, never scored — no verdict moves because of them.
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
                          "weather": o.get("weather"), "formality": o.get("formality"), "setting": o.get("setting"),
                          "life_weight": o.get("life_weight"),
                          "items": [by_id[n] for n in names if n]})
    else:
        mode = "auto"
        specs = [_auto_spec(items)]

    wardrobe = matcher.score_outfits(specs, season, items, pairs)
    works = (works_now_saved(wardrobe["outfits"]) if mode == "saved"
             else works_now_generated(closet_scored, gen_lists, mood=mood))

    # each outfit gets its colour-share bar, its own distance and the one addition
    # that would most lower it (horizons.md §3c)
    for o in wardrobe["outfits"]:
        scored = [r for r in o["slots"].values() if r]
        o["shares"] = colour_shares(scored)
        o["distance"] = outfit_distance(scored)
        o["improvement"] = best_improvement(o, closet_scored, season, pairs)

    current = current_palette(closet_scored, items)
    over = pulling_against(closet_scored)
    miss = missing(closet_scored, season)
    comps = where_they_should_head(compositions(wardrobe["outfits"]), wardrobe["gaps_ranked"])
    first = wardrobe["outfits"][0]
    return {
        "outfit_id": outfit_id or first["name"],
        "season": season.key,
        "mode": mode,
        "outfits": wardrobe["outfits"],
        "slots": first["slots"],
        "checks": first["checks"],
        "gaps_ranked": wardrobe["gaps_ranked"],
        "long_term": {**lt, "direction_of_travel": direction_of_travel(current, over, miss),
                      "directions": directions_block(season, closet_scored, pairs, mood)},
        "short_term": {
            "current_palette": current,
            "distance": distance(closet_scored, items),
            "over_represented": over,
            "missing": miss,
            "works_now": works,
            "next_moves": next_moves(wardrobe["gaps_ranked"], wardrobe["outfits"], closet_scored, pairs),
            "compositions": comps,
            "materials": material_notes(materials, closet_scored, wardrobe["outfits"], pairs),
        },
    }
