"""Build content/palettes/palettes.json — the palettes the styling desk offers
as a working reference beside the canvas.

Three categories:

  season  (a) — per season in frameworks/seasons.yaml: each direction's colour
                on the season's neutral ground, each direction's best generated
                pair, and the top pair of every generator list. Soft Autumn also
                carries the four worked examples of combinations.md §4.
  family  (b) — per colour family (content/tools/colour_names.py), the version
                of that family each season holds, with every generated pair it
                takes part in.
  trend   (c) — autumn/winter 2026/27, seeded from
                content/palettes/trends-aw26-27.yaml (external sources), each
                with a Soft Summer version where the frameworks allow one.

Nothing in (a) or (b) is chosen by hand: the pairs are engine/generators.py
output, the bridges are its §3.6 rule, the shares are the splits the
frameworks give, and the placements are the rules the frameworks state. Where
the repository has no material, the gap is written into `gaps`, never filled.

  python3 content/tools/build_palettes.py
"""
import os, re, sys, json, itertools
from pathlib import Path

_HERE = Path(__file__).resolve().parent
ROOT = _HERE.parent.parent
for p in (str(_HERE), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

import yaml                                           # noqa: E402
from engine import colour, palette, generators       # noqa: E402
from colour_names import classify                     # noqa: E402

OUT = ROOT / 'content' / 'palettes' / 'palettes.json'
TRENDS = ROOT / 'content' / 'palettes' / 'trends-aw26-27.yaml'

SEASON_LABEL = {k: k.replace('_', ' ').title() for k in palette.load_seasons()}
FAMILIES = ['red', 'orange', 'yellow', 'brown', 'green', 'blue', 'purple', 'pink']
IN_SEASON_DE = 15.0      # combinations.md §6: in season when every colour is within ΔE 15
OUT_DE = 16.0            # matching.md §2 stage 3: beyond 16 a colour is out
MONO_DE = 12.0           # combinations.md §5: two colours within ΔE 12 are one colour

# Shares the frameworks give. combinations.md §3.5-6: a pair is 60-70 / 30-40,
# with a bridge 50 / 30 / 20. colour-system.md §4: foundations 55, supporting
# 30, accents 15 — used for four colours and more.
SPLIT3 = (50, 30, 20)


def r(v, n=1):
    return round(v, n)


def engine_view(hex_str):
    """A colour in the engine's space: CIELAB D65, LCh, relative chroma."""
    lab = colour.hex_to_lab(hex_str)
    L, C, h = colour.lab_to_lch(lab)
    rel = colour.relative_chroma(L, C, h)
    return {'lab': [r(v, 2) for v in lab], 'lch': [r(L), r(C), r(h)],
            'relative_chroma': r(rel, 3), 'neutral': rel <= generators.NEUTRAL_REL}


def de(hex_a, hex_b):
    return colour.delta_e_2000(colour.hex_to_lab(hex_a), colour.hex_to_lab(hex_b))


# ----------------------------------------------------------------- placement

def placement_for(anchor, season):
    """The placement the frameworks give for an anchor in a season, or None.

    - colour-system.md §6: an accent-tier colour goes in small pieces, never a
      full garment near the face -> accessory.
    - seasons.yaml `black` (matching.md §2): below_waist_or_hardware and
      away_from_face keep black to bottoms, shoes, bags and hardware.
    Nothing else in the frameworks places a colour without knowing the person.
    """
    if anchor.hex == '000000':
        if season.black in ('below_waist_or_hardware', 'away_from_face'):
            return ['lower', 'accessory']
        return None
    if anchor.tier == 'accents':
        return ['accessory']
    return None


def colour_entry(name, hex_str, role, share, placement=None, **extra):
    e = {'hex': '#' + hex_str.upper(), 'name': name, 'role': role, 'share': share,
         'placement': placement}
    e.update(extra)
    return e


def assign_roles(members, season):
    """members: [(Anchor, kind)] in dominant / counter / bridge order.

    The frameworks' split is 50 / 30 / 20 (combinations.md §3.6). colour-system
    §6 keeps an accent-tier colour to small pieces, so an accent-tier dominant
    or counter takes the 20 and the bridge moves up. Two accent-tier colours in
    one palette cannot both be small: returns None and the caller records it.
    """
    accents = [m for m in members if m[0].tier == 'accents']
    if len(accents) > 1:
        return None
    order = list(members)
    if accents and order[-1][0].tier != 'accents':
        a = accents[0]
        order.remove(a)
        order.append(a)
    roles = ('dominant', 'secondary', 'accent')
    out = []
    for (a, kind), role, share in zip(order, roles, SPLIT3):
        out.append(colour_entry(a.name, a.hex, role, share, placement_for(a, season),
                                tier=a.tier, part=kind))
    return out


def pair_members(p):
    m = [(p.dominant, 'dominant'), (p.counter, 'counter')]
    if p.bridge:
        m.append((p.bridge, 'bridge'))
    return m


def pair_facts(p):
    return {'generator': p.generator, 'hue_gap': r(p.hue_gap), 'delta_L': r(p.delta_L),
            'delta_rel_chroma': r(p.delta_rel, 2)}


WHEN = {
    'opposition': '{d} carries the outfit and {c} answers it: opposed hues at matched chroma, far apart in value{b}.',
    'tonal': 'One hue family at two weights, {d} deep and {c} light{b}.',
    'muted': 'Both colours stay quiet and the value gap does the work, {d} deep and {c} light{b}.',
}


def when_for_pair(p):
    b = f', with {p.bridge.name} between them' if p.bridge else ''
    return WHEN[p.generator].format(d=p.dominant.name.capitalize(), c=p.counter.name, b=b)


def ground_for(anchor, season):
    """Two of the season's neutrals for one colour to sit on (combinations.md
    §5: chromatic + neutral is valid when both are in palette; neutral +
    neutral needs ΔL* >= 15). The first is the neutral with the largest
    lightness gap to the colour — the §3.6 bridge criterion; the second the one
    with the largest gap to both. None when the season cannot supply two."""
    neutrals = [a for a in season.anchors if generators.is_neutral(a.rel) and a.name != anchor.name]
    if len(neutrals) < 2:
        return None
    n1 = max(neutrals, key=lambda n: (abs(n.L - anchor.L), -n.rel))
    rest = [n for n in neutrals if n.name != n1.name and abs(n.L - n1.L) >= 15]
    if not rest:
        return None
    n2 = max(rest, key=lambda n: (min(abs(n.L - anchor.L), abs(n.L - n1.L)), -n.rel))
    return n1, n2


def ground_palette(anchor, season):
    g = ground_for(anchor, season)
    if not g:
        return None
    n1, n2 = g
    if anchor.tier == 'accents':
        members = [(n1, 'ground'), (n2, 'ground'), (anchor, 'colour')]
    else:
        members = [(anchor, 'colour'), (n1, 'ground'), (n2, 'ground')]
    cols = []
    for (a, kind), role, share in zip(members, ('dominant', 'secondary', 'accent'), SPLIT3):
        cols.append(colour_entry(a.name, a.hex, role, share, placement_for(a, season),
                                 tier=a.tier, part=kind))
    return cols


# ------------------------------------------------------------- (a) seasons

# combinations.md §4 — the owner's four, with the placement that section gives.
WORKED = [
    {'slug': 'teal-and-ochre', 'name': 'Teal and Ochre', 'pair': ('deep teal', 'ochre'), 'bridge': 'stone',
     'when': 'The reference pair: deep teal kept deep and green-leaning, ochre lighter, stone between.',
     'placement': {}},
    {'slug': 'petrol-and-cinnamon', 'name': 'Petrol and Cinnamon', 'pair': ('petrol', 'cinnamon'), 'bridge': 'stone',
     'when': 'A warmer counter than ochre that reads richer; good for outerwear.',
     'placement': {}},
    {'slug': 'olive-and-faded-rose', 'name': 'Olive and Faded Rose', 'pair': ('dark olive', 'dusty rose'), 'bridge': 'cream',
     'when': 'The quietest pair: rose near the face, olive as the body.',
     'placement': {'dusty rose': ['upper'], 'dark olive': ['mid', 'lower']}},
    {'slug': 'plum-and-old-gold', 'name': 'Plum and Old Gold', 'pair': ('soft plum', 'old gold'), 'bridge': 'stone',
     'when': 'The most evening of the four; gold in small pieces only.',
     'placement': {'old gold': ['accessory']},
     'outside_generators': True},
]


def worked_palettes(season, lists):
    out = []
    for w in WORKED:
        d, c = (season.find(n) for n in w['pair'])
        b = season.find(w['bridge'])
        found = generators.find_pair(lists, *w['pair'])
        if w.get('outside_generators'):
            # "gold in small pieces only": old gold takes the smallest share
            members = [(d, 'dominant'), (b, 'bridge'), (c, 'counter')]
        else:
            members = [(d, 'dominant'), (c, 'counter'), (b, 'bridge')]
        cols = []
        for (a, kind), role, share in zip(members, ('dominant', 'secondary', 'accent'), SPLIT3):
            pl = w['placement'].get(a.name) or placement_for(a, season)
            cols.append(colour_entry(a.name, a.hex, role, share, pl, tier=a.tier, part=kind))
        facts = pair_facts(found[2]) if found else {
            'generator': None, 'hue_gap': r(colour.hue_gap(d.h, c.h)), 'delta_L': r(abs(d.L - c.L)),
            'delta_rel_chroma': r(abs(d.rel - c.rel), 2)}
        out.append({
            'id': f'season-{season.key}-{w["slug"]}', 'name': w['name'], 'category': 'season',
            'group': season.key, 'group_label': SEASON_LABEL[season.key],
            'when': w['when'], 'colours': cols, 'basis': 'worked example', 'pair': facts,
            'source': {'kind': 'repo', 'confidence': 'repo',
                       'ref': 'frameworks/combinations.md §4; frameworks/seasons.yaml ' + season.key},
        })
    return out


def season_palettes(season, gaps):
    lists = generators.run(season.anchors)
    out, seen = [], set()

    def key_of(cols):
        return frozenset(c['hex'] for c in cols)

    def add(p):
        k = key_of(p['colours'])
        if k in seen:
            return False
        seen.add(k)
        out.append(p)
        return True

    if season.key == 'soft_autumn':
        for p in worked_palettes(season, lists):
            add(p)

    def pair_palette(p, basis, label=None):
        cols = assign_roles(pair_members(p), season)
        if cols is None:
            gaps.append({'category': 'season', 'group': season.key, 'kind': 'framework conflict',
                         'detail': f'{p.name} ({p.generator}) pairs two accent-tier colours; '
                                   'colour-system.md §6 keeps each to small pieces, so no 50/30/20 split holds.'})
            return None
        if len(cols) < 3:
            gaps.append({'category': 'season', 'group': season.key, 'kind': 'no bridge',
                         'detail': f'{p.name}: no anchor qualifies as a bridge (§3.6), two colours only.'})
            return None
        slug = generators_slug(p)
        return {'id': f'season-{season.key}-{slug}', 'name': label or p.name, 'category': 'season',
                'group': season.key, 'group_label': SEASON_LABEL[season.key],
                'when': when_for_pair(p), 'colours': cols, 'basis': basis, 'pair': pair_facts(p),
                'source': {'kind': 'repo', 'confidence': 'repo',
                           'ref': f'engine/generators.py over frameworks/seasons.yaml {season.key}; '
                                  'split and bridge from frameworks/combinations.md §3'}}

    for dkey, d in season.directions.items():
        anchor = season.find(d['anchor'])
        dlabel = dkey.replace('_', ' ')
        if generators.is_neutral(anchor.rel):
            gaps.append({'category': 'season', 'group': season.key, 'kind': 'neutral direction',
                         'detail': f'direction {dkey} is anchored on {anchor.name}, a neutral '
                                   f'(relative chroma {anchor.rel:.2f}); it enters no generator pair.'})
        else:
            cols = ground_palette(anchor, season)
            if cols:
                add({'id': f'season-{season.key}-{dkey}-ground', 'name': f'{anchor.name.capitalize()} on neutrals',
                     'category': 'season', 'group': season.key, 'group_label': SEASON_LABEL[season.key],
                     'when': f'The {dlabel} direction ({d["note"]}) at its simplest: '
                             f'{anchor.name} as the one colour, {cols[1]["name"] if cols[0]["name"] == anchor.name else cols[0]["name"]} '
                             f'and {cols[2]["name"] if cols[0]["name"] == anchor.name else cols[1]["name"]} as the ground.',
                     'colours': cols, 'basis': f'direction {dkey}, on neutral ground', 'direction': dkey,
                     'source': {'kind': 'repo', 'confidence': 'repo',
                                'ref': f'frameworks/seasons.yaml {season.key} directions.{dkey}; '
                                       'frameworks/combinations.md §5 (chromatic + neutral, neutral ΔL* >= 15)'}})
            else:
                gaps.append({'category': 'season', 'group': season.key, 'kind': 'no ground',
                             'detail': f'direction {dkey}: fewer than two neutrals 15 L* apart to carry {anchor.name}.'})
        ranked = [p for name in generators.DEFAULT_ORDER for p in lists[name] if anchor.name in p.names]
        built = None
        for p in ranked:
            built = pair_palette(p, f'direction {dkey}, best generated pair')
            if built:
                built['direction'] = dkey
                break
        if built:
            add(built)
        elif not generators.is_neutral(anchor.rel):
            gaps.append({'category': 'season', 'group': season.key, 'kind': 'no pair',
                         'detail': f'direction {dkey}: no generator pair contains {anchor.name}.' if not ranked
                         else f'direction {dkey}: every generator pair with {anchor.name} is unusable '
                              f'({", ".join(p.name for p in ranked)}; see the conflicts above).'})

    for name in generators.DEFAULT_ORDER:
        for p in lists[name]:
            built = pair_palette(p, f'top of the {name} list')
            if built:
                add(built)
                break
        if not lists[name]:
            gaps.append({'category': 'season', 'group': season.key, 'kind': 'empty generator',
                         'detail': f'the {name} generator produces no pair for {SEASON_LABEL[season.key]}.'})
    return out, lists


def generators_slug(p):
    return f'{p.dominant.name}-and-{p.counter.name}'.replace(' ', '-')


# -------------------------------------------------------------- (b) families

# The words colour_names.py uses for each family: its family name, its plain
# names and its named exceptions. Only used to report where an anchor's own
# name points elsewhere; the family itself is the measured one. `denim` is
# left out on purpose — denim is a fibre, never a colour (hard rule 6).
FAMILY_WORDS = {
    'red': {'red', 'oxblood', 'burgundy', 'brick'},
    'orange': {'orange', 'rust', 'terracotta', 'apricot', 'coral'},
    'brown': {'brown', 'espresso', 'chocolate', 'tobacco', 'tan', 'camel'},
    'yellow': {'yellow', 'ochre', 'mustard', 'gold', 'butter'},
    'green': {'green', 'olive', 'moss', 'sage', 'forest', 'emerald', 'lime'},
    'blue': {'blue', 'navy', 'steel', 'sky', 'petrol', 'teal', 'cobalt'},
    'purple': {'purple', 'aubergine', 'plum', 'violet', 'lilac', 'mauve'},
    'pink': {'pink', 'raspberry', 'rose', 'blush'},
}


def family_of(anchor):
    """(family or None, measured family, named family or None).

    The family is the one colour_names.py measures from hue and chroma. The
    name is read only to report disagreement."""
    measured = classify(anchor.hex)[0]
    words = set(re.split(r'[^a-z]+', anchor.name.lower()))
    named = [f for f, ws in FAMILY_WORDS.items() if words & ws]
    named = named[0] if len(named) == 1 else None
    return (measured if measured in FAMILIES else None), measured, named


def family_palettes(seasons, lists_by_season, gaps):
    out = []
    unfiled = []
    differs = []
    filed = {}
    for key, season in seasons.items():
        for a in season.anchors:
            fam, measured, named = family_of(a)
            if fam:
                filed.setdefault((fam, key), []).append(a)
                if named and named != fam:
                    differs.append((key, a, fam, named))
            elif not generators.is_neutral(a.rel):
                unfiled.append((key, a, measured, named))
    for fam in FAMILIES:
        for key, season in seasons.items():
            lists = lists_by_season[key]
            members = filed.get((fam, key), [])
            if not members:
                gaps.append({'category': 'family', 'group': fam, 'kind': 'no anchor',
                             'detail': f'{SEASON_LABEL[key]} has no {fam} anchor.'})
                continue
            for a in members:
                pairs = [p for name in generators.DEFAULT_ORDER for p in lists[name] if a.name in p.names]
                as_bridge = [p for name in generators.DEFAULT_ORDER for p in lists[name]
                             if p.bridge and p.bridge.name == a.name]
                combos = [{'with': (p.counter if p.dominant.name == a.name else p.dominant).name,
                           'with_hex': '#' + (p.counter if p.dominant.name == a.name else p.dominant).hex,
                           'bridge': p.bridge.name if p.bridge else None,
                           **pair_facts(p)} for p in pairs]
                combos += [{'with': f'{p.dominant.name} and {p.counter.name}', 'with_hex': None,
                            'bridge': a.name, 'as': 'bridge', **pair_facts(p)} for p in as_bridge]
                cols, basis, when = None, None, None
                for p in pairs + as_bridge:
                    cols = assign_roles(pair_members(p), season)
                    if cols and len(cols) == 3:
                        basis = f'{p.generator} pair' if p in pairs else f'bridge of a {p.generator} pair'
                        when = when_for_pair(p)
                        break
                    cols = None
                if cols is None and not generators.is_neutral(a.rel):
                    cols = ground_palette(a, season)
                    if cols:
                        basis = 'on neutral ground'
                        rest = [c['name'] for c in cols if c['name'] != a.name]
                        when = f'{a.name.capitalize()} as the one colour, {rest[0]} and {rest[1]} as the ground.'
                if cols is None:
                    gaps.append({'category': 'family', 'group': fam, 'kind': 'no palette',
                                 'detail': f'{SEASON_LABEL[key]} {a.name}: no generator pair, no bridge role '
                                           'and no neutral ground — nothing to build it from.'})
                    continue
                if not pairs:
                    gaps.append({'category': 'family', 'group': fam, 'kind': 'no pair',
                                 'detail': f'{SEASON_LABEL[key]} {a.name}: no generator pair; '
                                           'offered on neutral ground only.' if basis == 'on neutral ground'
                                 else f'{SEASON_LABEL[key]} {a.name}: works only as a bridge.'})
                out.append({
                    'id': f'family-{fam}-{key}-{a.name.replace(" ", "-")}',
                    'name': f'{a.name.capitalize()} · {SEASON_LABEL[key]}', 'category': 'family',
                    'group': fam, 'group_label': fam.capitalize(), 'season': key,
                    'focus': {'name': a.name, 'hex': '#' + a.hex, 'tier': a.tier},
                    'when': when, 'colours': cols, 'basis': basis, 'combinations': combos,
                    'source': {'kind': 'repo', 'confidence': 'repo',
                               'ref': f'frameworks/seasons.yaml {key}; engine/generators.py; '
                                      'family from content/tools/colour_names.py'}})
    for key, a, measured, named in unfiled:
        f, plain, *_ = classify(a.hex)
        gaps.append({'category': 'family', 'group': 'unfiled', 'kind': 'unfiled',
                     'detail': f'{SEASON_LABEL[key]} {a.name} #{a.hex}: chromatic by the engine, filed by '
                               f'colour_names.py as {f} / {plain}, a neutral name, so in no colour family.'})
    for key, a, fam, named in differs:
        gaps.append({'category': 'family', 'group': fam, 'kind': 'name differs',
                     'detail': f'{SEASON_LABEL[key]} {a.name} #{a.hex}: filed as {fam} by hue and chroma; '
                               f'its name points to {named}.'})
    return out


# ---------------------------------------------------------------- (c) trends

def trend_members(t, colours):
    """[(key, kind)] per palette variant, dominant first."""
    if 'pairs' in t:
        return [[(k, 'pair') for k in pair] for pair in t['pairs']]
    return [[(k, 'colour') for k in t['colours']]]


def bridge_from_set(pair_keys, colours, set_neutrals):
    """combinations.md §3.6 applied to the AW26/27 set's own neutrals (the
    seed's `set_neutrals`): one that adds no third voice — a neutral by the
    engine, or a Tonal partner of either — with the largest lightness gap to
    the pair; ties to the lower relative chroma. Drawing from the other trend
    palettes would bring in another trend's colour."""
    used = {colours[k]['hex'].upper() for k in pair_keys}
    views = {k: engine_view(colours[k]['hex']) for k in set(pair_keys) | set(set_neutrals)}
    a, b = (views[k] for k in pair_keys)
    cands = []
    for k in set_neutrals:
        c = colours[k]
        if c['hex'].upper() in used or k in pair_keys:
            continue
        v = views[k]
        L, h, rel = v['lch'][0], v['lch'][2], v['relative_chroma']
        ok = rel <= generators.NEUTRAL_REL
        for o in (a, b):
            name, _ = generators.test_pair(L, h, rel, o['lch'][0], o['lch'][2], o['relative_chroma'])
            ok = ok or name == 'tonal'
        if ok:
            gap = min(abs(L - a['lch'][0]), abs(L - b['lch'][0]))
            cands.append((gap, -rel, k))
    if not cands:
        return None
    # one entry per hex: two names for one colour are one candidate
    return max(cands)[2]


def trend_shares(keys, t):
    """Shares by the frameworks' splits: three colours 50/30/20 (combinations.md
    §3.6), four or more 55 / 30 / 15 (colour-system.md §4) with the middle
    tier divided evenly. Roles follow the source's wording where it names a
    dominant or an accent, otherwise the listed order."""
    order = list(keys)
    dom = t.get('dominant')
    acc = t.get('accent')
    if dom in order:
        order.remove(dom)
        order.insert(0, dom)
    if acc in order:
        order.remove(acc)
        order.append(acc)
    n = len(order)
    if n == 3:
        return list(zip(order, ('dominant', 'secondary', 'accent'), SPLIT3))
    mids = n - 2
    base = 30 // mids
    mid_shares = [base + (1 if i < 30 - base * mids else 0) for i in range(mids)]
    return ([(order[0], 'dominant', 55)] + [(k, 'secondary', s) for k, s in zip(order[1:-1], mid_shares)]
            + [(order[-1], 'accent', 15)])


def nearest_anchor(hex_str, season):
    best = min(season.anchors, key=lambda a: de(hex_str, a.hex))
    return best, de(hex_str, best.hex)


def seasons_fit(hexes, seasons):
    """combinations.md §6 filter: in season when every colour is within ΔE 15
    of an anchor, near when all but one are."""
    inn, near = [], []
    for key, s in seasons.items():
        far = sum(1 for h in hexes if nearest_anchor(h, s)[1] > IN_SEASON_DE)
        if far == 0:
            inn.append(key)
        elif far == 1:
            near.append(key)
    return inn, near


def soft_summer_version(base, seasons):
    """The same idea in Soft Summer's anchors, or the reason it cannot be.
    Every colour moves to its nearest Soft Summer anchor (ΔE2000). The result
    must then pass the rules any palette in that season would: nothing beyond
    ΔE 16 (out), at least three distinct colours, every chromatic pair valid
    under combinations.md §5, neutral pairs 15 L* apart, and no accent-tier
    anchor in more than a small share (colour-system.md §6)."""
    ss = seasons['soft_summer']
    reasons, mapped = [], []
    for c in base['colours']:
        hx = c['hex'].lstrip('#')
        if hx.upper() == '000000':
            # black is governed by the rule, not by an anchor: away from the face
            mapped.append({'from': c['name'], 'anchor': None, 'hex': '000000', 'name': 'black',
                           'delta_e': 0.0, 'role': c['role'], 'share': c['share'], 'tier': None,
                           'placement': ['lower', 'accessory']})
            continue
        a, d = nearest_anchor(hx, ss)
        mapped.append({'from': c['name'], 'anchor': a, 'hex': a.hex, 'name': a.name, 'delta_e': d,
                       'role': c['role'], 'share': c['share'], 'tier': a.tier,
                       'placement': placement_for(a, ss)})
        if d > OUT_DE:
            reasons.append(f'{c["name"]} has no Soft Summer counterpart: nearest is {a.name} at ΔE {d:.1f} (out beyond 16).')
    merged = {}
    for m in mapped:
        if m['hex'] in merged:
            merged[m['hex']]['share'] += m['share']
            merged[m['hex']]['from'] += ' + ' + m['from']
        else:
            merged[m['hex']] = dict(m)
    distinct = list(merged.values())
    adjusted = []
    accents = [m for m in distinct if m['tier'] == 'accents']
    smallest = min(distinct, key=lambda m: m['share'])
    if len(accents) == 1 and accents[0] is not smallest and len(distinct) >= 3:
        # colour-system.md §6, applied as in the season palettes: the accent
        # takes the small share and the smallest colour moves up
        a = accents[0]
        a['share'], smallest['share'] = smallest['share'], a['share']
        a['role'], smallest['role'] = smallest['role'], a['role']
        adjusted.append(f'{a["name"]} is a Soft Summer accent (colour-system.md §6): it takes the '
                        f'{a["share"]}% share and {smallest["name"]} moves up to {smallest["share"]}%.')
    collapsed = [m for m in distinct if '+' in m['from']]
    for m in collapsed:
        reasons.append(f'{m["from"]} all become {m["name"]}; the contrast between them is lost.')
    if len(distinct) < 3:
        reasons.append(f'only {len(distinct)} distinct Soft Summer colour(s) remain.')
    anchors = [m['anchor'] for m in distinct if m['anchor']]
    chrom = [a for a in anchors if not generators.is_neutral(a.rel)]
    neut = [a for a in anchors if generators.is_neutral(a.rel)]
    for a, b in itertools.combinations(chrom, 2):
        if colour.delta_e_2000(a.lab, b.lab) <= MONO_DE:
            continue
        g, m = generators.test_pair(a.L, a.h, a.rel, b.L, b.h, b.rel)
        if g is None:
            reasons.append(f'{a.name} with {b.name} is no valid pair (§5): {generators.band_of(m["hue_gap"])} band, '
                           f'ΔL* {m["delta_L"]:.1f}, Δ relative chroma {m["delta_rel"]:.2f}.')
    for a, b in itertools.combinations(neut, 2):
        if abs(a.L - b.L) < 15:
            reasons.append(f'{a.name} with {b.name} is flat: ΔL* {abs(a.L - b.L):.1f} (needs 15).')
    for m in distinct:
        if m['tier'] == 'accents' and m['share'] > 20:
            reasons.append(f'{m["name"]} is a Soft Summer accent (small pieces only) but would carry {m["share"]}%.')
    if reasons:
        return None, reasons
    distinct.sort(key=lambda m: -m['share'])
    cols = [colour_entry(m['name'], m['hex'], m['role'], m['share'], m['placement'],
                         tier=m['tier'], from_trend=m['from'], delta_e=r(m['delta_e'])) for m in distinct]
    return cols, adjusted


def trend_palettes(seasons, gaps):
    d = yaml.safe_load(open(TRENDS))
    colours, srcs = d['colours'], d['sources']
    out, untranslated = [], []
    for t in d['palettes']:
        variants = trend_members(t, colours)
        for vi, members in enumerate(variants):
            keys = [k for k, _ in members]
            bridge = None
            if 'pairs' in t:
                bridge = bridge_from_set(keys, colours, d.get('set_neutrals', []))
                if bridge is None:
                    gaps.append({'category': 'trend', 'group': 'aw26-27', 'kind': 'no bridge',
                                 'detail': f'{t["id"]} {" + ".join(colours[k]["name"] for k in keys)}: '
                                           'neither of the set\'s neutrals bridges the pair (§3.6), '
                                           'so it stays two colours and is not offered.'})
                    continue
                keys = keys + [bridge]
            tt = dict(t)
            if 'pairs' in t:
                # in a pair the source's dominant or accent is honoured; otherwise
                # the first of the pair leads and the bridge is the small share
                if t.get('accent') in keys:
                    tt['dominant'] = t.get('dominant') or keys[0]
                    keys_order = [tt['dominant']] + [bridge] + [t['accent']]
                    keys_order = [k for k in keys_order if k in keys] + [k for k in keys if k not in keys_order]
                    shares = list(zip(keys_order, ('dominant', 'secondary', 'accent'), SPLIT3))
                else:
                    shares = trend_shares(keys, {'dominant': t.get('dominant') or keys[0], 'accent': bridge})
            else:
                shares = trend_shares(keys, t)
            cols = []
            for k, role, share in shares:
                c = colours[k]
                v = engine_view(c['hex'])
                extra = {'engine': v}
                if not c.get('hex_given', True):
                    extra['hex_given'] = False
                    extra['stand_in'] = c['stand_in']
                if (t.get('worn_as') or {}).get(k):
                    extra['worn_as'] = t['worn_as'][k]
                if k == bridge:
                    extra['part'] = 'bridge (combinations.md §3.6, from the AW26/27 set)'
                cols.append(colour_entry(c['name'], c['hex'], role, share, None, **extra))
            suffix = 'abcdefgh'[vi] if len(variants) > 1 else ''
            pid = f'{t["id"]}{suffix}'
            names = ' + '.join(colours[k]['name'] for k in keys)
            inn, near = seasons_fit([c['hex'].lstrip('#') for c in cols], seasons)
            urls = [srcs[s] for s in t['sources']]
            base = {
                'id': f'trend-aw2627-{pid.lower()}', 'trend_id': pid,
                'name': t['name'] + (f' — {" + ".join(colours[k]["name"] for k, _ in members)}' if suffix else ''),
                'category': 'trend', 'group': 'aw26-27', 'group_label': 'AW26/27',
                'when': t['when'], 'colours': cols,
                'share_basis': 'assigned by the frameworks\' splits (combinations.md §3.6, colour-system.md §4); '
                               'the source gives no shares',
                'placement_note': 'frameworks give no placement for a palette outside a season; see worn_as',
                'in_season': inn, 'near_season': near,
                'source': {'kind': 'external', 'confidence': 'external',
                           'ref': '; '.join(f'{d["collected"]}, {u}' for u in urls),
                           'entries': [f'{d["collected"]}, {u}' for u in urls]},
            }
            for extra in ('runway', 'trade_names'):
                if t.get(extra):
                    base[extra] = t[extra]
            out.append(base)
            ss_cols, reasons = soft_summer_version(base, seasons)
            if ss_cols:
                note = {'adjusted': reasons} if reasons else {}
                out.append({**note,
                    'id': base['id'] + '-soft-summer', 'trend_id': pid,
                    'name': base['name'] + ' · Soft Summer', 'category': 'trend',
                    'group': 'aw26-27-soft-summer', 'group_label': 'AW26/27 in Soft Summer',
                    'when': base['when'], 'colours': ss_cols, 'derived': True, 'derived_from': base['id'],
                    'source': {**base['source'], 'derived': 'each colour moved to its nearest Soft Summer '
                               'anchor (ΔE2000) in frameworks/seasons.yaml'}})
            else:
                untranslated.append({'trend_id': pid, 'name': base['name'], 'reasons': reasons})
    return out, untranslated, d.get('notes', [])


# --------------------------------------------------------------------- main

def check(p):
    cols = p['colours']
    assert 3 <= len(cols) <= 6, (p['id'], len(cols))
    assert sum(c['share'] for c in cols) == 100, (p['id'], [c['share'] for c in cols])
    assert all(c['role'] in ('dominant', 'secondary', 'accent') for c in cols), p['id']
    assert p['source'], p['id']


def main():
    seasons = palette.load_seasons()
    gaps = []
    season_list, lists_by = [], {}
    for key, s in seasons.items():
        ps, lists = season_palettes(s, gaps)
        season_list += ps
        lists_by[key] = lists
    family_list = family_palettes(seasons, lists_by, gaps)
    trend_list, untranslated, notes = trend_palettes(seasons, gaps)
    allp = season_list + family_list + trend_list
    ids = [p['id'] for p in allp]
    assert len(ids) == len(set(ids)), 'duplicate palette ids'
    for p in allp:
        check(p)
    doc = {
        'kind': 'relatively-normal.palettes', 'version': 1,
        'built_by': 'content/tools/build_palettes.py',
        'colour_space': 'hex is sRGB; engine fields are CIELAB D65, LCh and relative chroma (engine/colour.py)',
        'categories': [
            {'key': 'season', 'label': 'Colour season', 'groups': [
                {'key': k, 'label': SEASON_LABEL[k]} for k in seasons]},
            {'key': 'family', 'label': 'Colour family', 'groups': [
                {'key': f, 'label': f.capitalize()} for f in FAMILIES]},
            {'key': 'trend', 'label': 'This season, AW26/27', 'groups': [
                {'key': 'aw26-27', 'label': 'AW26/27'},
                {'key': 'aw26-27-soft-summer', 'label': 'AW26/27 in Soft Summer'}]},
        ],
        'counts': {
            'season': len(season_list), 'family': len(family_list),
            'trend': sum(1 for p in trend_list if not p.get('derived')),
            'trend_soft_summer': sum(1 for p in trend_list if p.get('derived')),
            'trend_not_translated': len(untranslated), 'gaps': len(gaps),
        },
        'palettes': allp,
        'gaps': gaps,
        'soft_summer_not_translated': untranslated,
        'notes': [{'kind': 'louder runway pair, not a palette', **n} for n in notes],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, 'w') as fh:
        json.dump(doc, fh, indent=1, ensure_ascii=False)
        fh.write('\n')
    print(json.dumps(doc['counts']))


if __name__ == '__main__':
    main()
