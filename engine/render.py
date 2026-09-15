"""Render the result screen — horizons.md §6 as a single self-contained HTML file.

Takes the dict `horizons.result` returns and lays it out: colouring and
runner-up at the top; the ideal palette and the current wardrobe as two
columns of proportional colour blocks, the current one sorted into the
ideal's tiers with out and hard-miss items set apart; the distance figure;
works-now outfits and next moves side by side; combinations as swatch pairs;
the long-term data. Inline CSS, no external assets, readable on a tablet in
portrait.

The renderer computes nothing. Every number, verdict, share and colour on the
page is read from the JSON; the only transformations are formatting (a season
key to its name, an underscore to a space, a share to a percentage width).
The sentences are not written here either: the four distance readings are
the owner's, quoted from horizons.md §3b, and the long-term paragraph is
left for the owner to write.
"""
import html
import json

TIERS = ("foundations", "supporting", "accents")
SLOTS = ("top", "bottom", "layer", "shoes", "bag", "accessory")

# horizons.md §3b, quoted; keyed by the `reading` the engine reports.
DISTANCE_READINGS = {
    "matches": "Your wardrobe already matches your colouring. The work is combinations, not colours.",
    "mostly there": "Mostly there. One or two colours are pulling against you.",
    "real gap": "A real gap. Worth steering deliberately over the next year.",
    "disagree": "Your wardrobe and your colouring disagree. Start with the pieces nearest your face.",
}

CSS = """
:root { --ink:#1f1d1a; --muted:#6b665e; --line:#dcd6cc; --bg:#faf8f4; --card:#ffffff;
        --in:#3f6b4a; --near:#a8752a; --out:#6b665e; --miss:#a33a2f; }
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--ink);
       font:16px/1.45 -apple-system, "Helvetica Neue", Helvetica, Arial, sans-serif; }
main { max-width:900px; margin:0 auto; padding:24px 20px 60px; }
h1 { font-size:26px; margin:0 0 4px; letter-spacing:-0.01em; }
h2 { font-size:12px; letter-spacing:0.12em; text-transform:uppercase; color:var(--muted); margin:0 0 10px; }
h3 { font-size:15px; margin:0 0 6px; }
section { background:var(--card); border:1px solid var(--line); border-radius:10px; padding:16px 18px; margin:14px 0; }
.sub { color:var(--muted); }
.grid2 { display:grid; grid-template-columns:1fr 1fr; gap:14px; }
@media (max-width:640px) { .grid2 { grid-template-columns:1fr; } }
.tier { margin:10px 0 14px; }
.tier-head { display:flex; justify-content:space-between; font-size:13px; color:var(--muted); margin-bottom:4px; }
.bar { height:10px; background:var(--line); border-radius:5px; overflow:hidden; margin-bottom:8px; }
.bar > i { display:block; height:100%; background:var(--ink); }
.swatches { display:flex; flex-wrap:wrap; gap:8px; }
.sw { width:64px; text-align:center; font-size:11px; line-height:1.2; color:var(--ink); }
.sw .c { height:40px; border-radius:6px; border:1px solid rgba(0,0,0,0.12); margin-bottom:3px; }
.sw.dim .c { opacity:0.55; }
.sw .v { display:block; font-weight:600; }
.sep { width:100%; border-top:1px dashed var(--line); margin:4px 0; font-size:11px; color:var(--muted); padding-top:4px; }
.badge { display:inline-block; font-size:11px; font-weight:600; padding:1px 7px; border-radius:10px; color:#fff; vertical-align:middle; }
.b-in { background:var(--in); } .b-near { background:var(--near); } .b-out { background:var(--out); } .b-hard_miss { background:var(--miss); }
.big { font-size:34px; font-weight:700; letter-spacing:-0.02em; }
ul { margin:6px 0 0 18px; padding:0; } li { margin:4px 0; }
.pair { display:flex; align-items:center; gap:10px; padding:8px 0; border-top:1px solid var(--line); }
.pair:first-of-type { border-top:0; }
.pair .c { width:44px; height:44px; border-radius:8px; border:1px solid rgba(0,0,0,0.12); flex:none; }
.pair .c.bridge { width:26px; height:26px; }
.pair .t { flex:1; font-size:14px; }
.pair .n { font-size:12px; color:var(--muted); }
.kv { display:grid; grid-template-columns:auto 1fr; gap:4px 14px; font-size:14px; }
.kv dt { color:var(--muted); } .kv dd { margin:0; }
.flag { color:var(--miss); font-weight:600; }
.slots { display:flex; flex-wrap:wrap; gap:10px; }
.slot { width:120px; font-size:12px; }
.slot .c { height:48px; border-radius:6px; border:1px solid rgba(0,0,0,0.12); margin-bottom:4px; }
.slot .c.empty { background:repeating-linear-gradient(45deg,#f1ede6,#f1ede6 6px,#e6e0d6 6px,#e6e0d6 12px); }
.note { font-size:13px; color:var(--muted); border-left:3px solid var(--line); padding-left:10px; margin-top:10px; }
footer { font-size:12px; color:var(--muted); margin-top:20px; }
"""


# ---------------------------------------------------------------- formatting only

def _e(x):
    return html.escape("" if x is None else str(x))


def _name(key):
    """'soft_autumn' -> 'Soft Autumn'; 'below_waist_or_hardware' -> 'below waist or hardware'."""
    return "" if key is None else str(key).replace("_", " ")


def _title(key):
    return _name(key).title()


def _pct(share):
    return f"{round(float(share) * 100)}%"


def _badge(verdict):
    return f'<span class="badge b-{_e(verdict)}">{_e(_name(verdict))}</span>'


def _swatch(hex_, label, verdict=None, dim=False, sub=None):
    cls = "sw dim" if dim else "sw"
    v = f'<span class="v">{_badge(verdict)}</span>' if verdict else ""
    s = f'<span class="sub">{_e(sub)}</span>' if sub else ""
    return (f'<div class="{cls}"><div class="c" style="background:#{_e(hex_)}"></div>'
            f'{v}{_e(label)}{("<br>" + s) if s else ""}</div>')


# ---------------------------------------------------------------- sections

def _header(r):
    lt = r["long_term"]
    runner = lt.get("runner_up") or {}
    conf = lt.get("confidence") or {}
    conf_txt = ", ".join(f"{k} {v}" for k, v in conf.items()) if conf else "not given"
    runner_txt = _title(runner.get("season")) if runner.get("season") else "not derived (no confidence given)"
    return f"""
<section>
  <h2>Your colouring</h2>
  <h1>{_e(_title(lt["season"]))} · {_e(_name(lt["direction"]))}</h1>
  <div class="sub">runner-up: {_e(runner_txt)}{(" — on the " + _e(runner["axis"]) + " axis") if runner.get("axis") else ""}</div>
  <div class="sub">{_e(lt.get("direction_note") or "")}</div>
  <div class="sub">confidence: {_e(conf_txt)} · primary {_e(lt["primary"])}, secondary {_e(lt["secondary"])}</div>
</section>"""


def _ideal_column(lt):
    out = ['<div><h2>Ideal palette</h2>']
    for t in TIERS:
        share = lt["tier_share"][t]
        sw = "".join(_swatch(a["hex"], a["name"]) for a in lt["ideal_palette"][t])
        out.append(f'<div class="tier"><div class="tier-head"><span>{_e(t)}</span><span>{_pct(share)}</span></div>'
                   f'<div class="bar"><i style="width:{_pct(share)}"></i></div><div class="swatches">{sw}</div></div>')
    out.append('</div>')
    return "".join(out)


def _current_column(st):
    cp = st["current_palette"]
    out = ['<div><h2>Your wardrobe today</h2>']
    for t in TIERS:
        share = cp["proportions"][t]
        entries = cp["tiers"][t]
        kept = [x for x in entries if x["verdict"] in ("in", "near")]
        apart = [x for x in entries if x["verdict"] not in ("in", "near")]
        sw = "".join(_swatch(x["hex"], x["item_id"], x["verdict"], sub=_attrs(x) + f'nearest {x["nearest"]} · ΔE {x["delta_e"]}') for x in kept)
        if apart:
            sw += '<div class="sep">out or hard miss — nearest anchor in this tier, not in palette</div>'
            sw += "".join(_swatch(x["hex"], x["item_id"], x["verdict"], dim=True,
                                  sub=_attrs(x) + f'nearest {x["nearest"]} · ΔE {x["delta_e"]}') for x in apart)
        if not entries:
            sw = '<div class="sub" style="font-size:12px">nothing here</div>'
        out.append(f'<div class="tier"><div class="tier-head"><span>{_e(t)}</span><span>{_pct(share)}</span></div>'
                   f'<div class="bar"><i style="width:{_pct(share)}"></i></div><div class="swatches">{sw}</div></div>')
    if cp["unplaced"]:
        sw = "".join(_swatch(x["hex"], x["item_id"], x["verdict"], sub=_attrs(x) + f'{x["nearest"]} · ΔE {x["delta_e"]}') for x in cp["unplaced"])
        out.append(f'<div class="tier"><div class="tier-head"><span>allowed by a slot rule — no tier</span></div>'
                   f'<div class="swatches">{sw}</div></div>')
    out.append('</div>')
    return "".join(out)


def _attrs(x):
    """'d3 · w2 · ' when an item carries dressiness and weight, else ''."""
    parts = []
    if x.get("dressiness") is not None:
        parts.append(f'd{x["dressiness"]}')
    if x.get("weight") is not None:
        parts.append(f'w{x["weight"]}')
    return (" · ".join(parts) + " · ") if parts else ""


def _distance(st):
    d = st["distance"]
    reading = d["reading"]
    if st["over_represented"]:
        over = "<ul style=\"margin:0 0 0 16px\">" + "".join(
            f'<li><b>{_e(o["item"])}</b> — {_e(_name(o["verdict"]))}{(" " + _e(o["where"])) if o.get("where") else ""}; '
            f'nearest: {_e(o["nearest"])} <span class="sub">(ΔE {_e(o["delta_e"])})</span></li>'
            for o in st["over_represented"]) + "</ul>"
    else:
        over = "none"
    miss = st["missing"]
    missing = miss["note"] if miss.get("note") else (", ".join(miss["anchors"]) or "none")
    return f"""
<section>
  <h2>Distance</h2>
  <div><span class="big">{_e(d["palette_distance"])}</span> &nbsp;<span class="sub">— {_e(reading)}</span></div>
  <div>{_e(DISTANCE_READINGS.get(reading, ""))}</div>
  <dl class="kv" style="margin-top:10px">
    <dt>pulling against you</dt><dd>{over}</dd>
    <dt>missing from the closet</dt><dd>{_e(missing)}</dd>
  </dl>
</section>"""


def _outfit_block(o):
    slots = "".join(
        (f'<div class="slot"><div class="c" style="background:#{_e(s["dominant"]["hex"])}"></div>'
         f'<b>{_e(slot)}</b> {_badge(s["verdict"])}<br>{_e(s["item_id"])}<br>'
         f'<span class="sub">{_e(_attrs(s))}{_e(s["nearest"])} · ΔE {_e(s["delta_e"])}'
         f'{(" · " + _e(s["reason"])) if s.get("reason") else ""}</span></div>')
        if s else f'<div class="slot"><div class="c empty"></div><b>{_e(slot)}</b><br><span class="sub">empty'
                  f'{" (optional)" if slot == "layer" else ""}</span></div>'
        for slot, s in ((k, o["slots"][k]) for k in SLOTS))
    c = o["checks"]
    tm = c["tier_mix"]
    rows = [
        ("coverage", "missing: " + (", ".join(c["coverage"]["missing"]) or "none")),
        ("palette", ", ".join(f'{k.replace("_", " ")} {v}' for k, v in c["palette"].items())),
        ("tier mix", f'foundation {tm["foundation"]} · supporting {tm["supporting"]} · accent {tm["accent"]}'
                     + (f' · <span class="flag">{_e(tm["flag"])}</span>' if tm["flag"] else "")),
        ("contrast", f'lightness range {c["contrast"]["lightness_range"]} · season target {c["contrast"]["season_target"]}'
                     + (f' · <span class="flag">{_e(c["contrast"]["flag"])}</span>' if c["contrast"]["flag"] else "")),
    ]
    z = c["zone"]
    if z["checked"]:
        zf = ", ".join(f'{x["item_id"]} {x["flag"]}' for x in z["flags"])
        rows.append(("zone fit", f'dress code {_e(z["dress_code"])} · ' + (f'<span class="flag">{_e(zf)}</span>' if zf else "fits")))
    w = c["weather"]
    if w["checked"]:
        rows.append(("weather", f'{_e(w["weather"])} · layer {"present" if w["layer_present"] else "absent"} · heaviest {_e(w["heaviest"])}'
                     + (f' · <span class="flag">{_e(w["flag"])}</span>' if w["flag"] else " · fits")))
    pf = ", ".join(o["pairing"]["flags"])
    rows.append(("pairing", "valid" if o["pairing"]["valid"] else f'<span class="flag">{_e(pf or "invalid")}</span>'))
    if c.get("warm_partner", {}).get("flag"):
        rows.append(("black", f'<span class="flag">{_e(c["warm_partner"]["flag"])}</span>'))
    kv = "".join(f"<dt>{_e(k)}</dt><dd>{v}</dd>" for k, v in rows)
    meta = " · ".join(x for x in (
        _e(o["occasion"]) if o.get("occasion") else "",
        f'dress code {_e(o["dress_code"])}' if o.get("dress_code") is not None else "",
        _e(o["weather"]) if o.get("weather") else "") if x)
    status = '<span class="badge b-in">works now</span>' if o["passes"] else '<span class="badge b-out">not yet</span>'
    return (f'<div style="margin:0 0 18px"><h3>{_e(o["name"])} {status}</h3>'
            f'<div class="sub" style="margin-bottom:8px">{meta}</div>'
            f'<div class="slots">{slots}</div><dl class="kv" style="margin-top:12px">{kv}</dl></div>')


def _outfits(r):
    head = "Your outfits" if r.get("mode") == "saved" else "Outfit in hand"
    return f'<section><h2>{_e(head)}</h2>{"".join(_outfit_block(o) for o in r["outfits"])}</section>'


def _works_now(st):
    outfits = st["works_now"]
    if not outfits:
        body = '<div class="sub">No outfit builds from the uploaded items yet.</div>'
    else:
        li = []
        for o in outfits:
            flags = f' · <span class="flag">{_e(", ".join(o["flags"]))}</span>' if o.get("flags") else ""
            if o.get("name"):
                meta = " · ".join(x for x in (o.get("occasion") or "", f'dress code {o["dress_code"]}' if o.get("dress_code") is not None else "", o.get("weather") or "") if x)
                li.append(f'<li><b>{_e(o["name"])}</b> — {_e(" + ".join(o["items"]))}<br><span class="sub">{_e(meta)}</span>{flags}</li>')
            else:
                how = o.get("matched_pair") or _name(o.get("pairing"))
                li.append(f'<li><b>{_e(" + ".join(o["items"]))}</b><br><span class="sub">{_e(how)}'
                          f'{(" · " + _e(o["generator"])) if o.get("generator") else ""} · closeness {_e(o["closeness_to_named"])}</span>{flags}</li>')
        body = f'<ul>{"".join(li)}</ul>'
    return f'<div><h2>Works now</h2>{body}</div>'


def _next_moves(r):
    moves = r["short_term"]["next_moves"]
    if not moves:
        body = '<div class="sub">No next move from the closet. Sources 2 and 3 (staples, brands) are not yet available.</div>'
    else:
        li = "".join(
            f'<li><b>{_e(m["item_id"])}</b> → {_e(m["slot"])} <span class="sub">({_e(m["source"])})</span><br>'
            f'<span class="sub">pairs with {_e(m["outfits_unlocked"])} · improvement {_e(m["palette_improvement"])} · value {_e(m["value"])}</span></li>'
            for m in moves)
        body = f'<ol>{li}</ol>'
    gaps = r["gaps_ranked"]
    if gaps:
        gl = "".join(
            f'<li>{_e(_name(g["type"]))}{(" — " + _e(g["slot"])) if g.get("slot") and g["type"] != "zone_gap" else ""}'
            f'{(" — " + _e(g["item_id"])) if g.get("item_id") else ""}'
            f'{(" — " + _e(g["flag"])) if g.get("flag") else ""}'
            f'{(" — nearest " + _e(g["nearest"])) if g.get("nearest") else ""}'
            f' · <b>unlocks {_e(g["unlocks"])}</b>'
            f'{(" <span class=sub>(" + _e(", ".join(g["outfits"])) + ")</span>") if g.get("outfits") else ""}'
            f'{(" · fill: " + _e(g["fill"]["item_id"]) + " (" + _e(g["fill"]["source"]) + ")") if g.get("fill") else " · no fill yet"}</li>'
            for g in gaps)
        body += f'<h3 style="margin-top:12px">Gaps, ranked</h3><ul>{gl}</ul>'
    return f'<div><h2>Next move</h2>{body}</div>'


def _combinations(lt):
    # the bridge's hex is looked up by name from the ideal palette in the same JSON
    hex_of = {a["name"]: a["hex"] for t in TIERS for a in lt["ideal_palette"][t]}
    rows = []
    for p in lt["combinations"]:
        bridge_hex = hex_of.get(p["bridge"]) if p.get("bridge") else None
        bridge = (f'<div class="c bridge" style="background:#{_e(bridge_hex)}" title="bridge"></div>'
                  if bridge_hex else "")
        bridge_txt = f' · bridge {_e(p["bridge"])}' if p.get("bridge") else ""
        rows.append(f'<div class="pair"><div class="c" style="background:#{_e(p["dominant_hex"])}"></div>'
                    f'<div class="c" style="background:#{_e(p["counter_hex"])}"></div>{bridge}'
                    f'<div class="t"><b>{_e(p["name"])}</b><br><span class="n">{_e(p["generator"])} · hue {_e(p["hue_gap"])}° · '
                    f'ΔL* {_e(p["delta_L"])} · Δrel {_e(p["delta_rel"])} · {_e(p["split"])}{bridge_txt}</span></div></div>')
    counts = " · ".join(f'{k} {len(v)}' for k, v in lt["combinations_all"].items())
    order = " → ".join(lt["generator_order"])
    return (f'<section><h2>Your combinations</h2>{"".join(rows)}'
            f'<div class="note">ranked {_e(order)} · all pairs: {_e(counts)}</div></section>')


def _long_term(lt):
    rules = lt["rules_in_force"]
    dt = lt["direction_of_travel"]
    kv = [
        ("black", _name(rules["black"])), ("white", _name(rules["white"])),
        ("contrast", _name(rules["contrast"])), ("metal", _name(rules["metal"])),
        ("grow", _name(dt["grow_tier"]) if dt["grow_tier"] else "—"),
        ("let fade", ", ".join(dt["fade_items"]) or "—"),
        ("missing", dt["missing_note"] if dt.get("missing_note") else (", ".join(dt["missing_colours"] or []) or "—")),
        ("investment piece", dt["investment_piece"] or "— (needs the brand database)"),
    ]
    body = "".join(f"<dt>{_e(k)}</dt><dd>{_e(v)}</dd>" for k, v in kv)
    return (f'<section><h2>Long-term</h2><dl class="kv">{body}</dl>'
            f'<div class="note">The paragraph is the owner\'s to write. These are its inputs.</div></section>')


# ---------------------------------------------------------------- page

def render(result):
    """The result dict from horizons.result -> a complete HTML document (str)."""
    lt, st = result["long_term"], result["short_term"]
    title = f'{_title(lt["season"])} · {_name(lt["direction"])}'
    body = "".join([
        _header(result),
        f'<section><div class="grid2">{_ideal_column(lt)}{_current_column(st)}</div></section>',
        _distance(st),
        _outfits(result),
        f'<section><div class="grid2">{_works_now(st)}{_next_moves(result)}</div></section>',
        _combinations(lt),
        _long_term(lt),
        '<footer>Every number, verdict and ranking on this page came from the engine; the page only lays them out.</footer>',
    ])
    return (f'<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>{_e(title)}</title><style>{CSS}</style></head>'
            f'<body><main>{body}</main></body></html>\n')


def render_file(result, path):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(render(result))
    return path


if __name__ == "__main__":  # python -m engine.render result.json > result.html
    import sys
    sys.stdout.write(render(json.load(open(sys.argv[1]))))
