// Palettes — a working reference beside the canvas. Pure data and pure
// functions, no DOM. The palettes come from content/palettes/palettes.json
// (built by content/tools/build_palettes.py); nothing here invents one.
//
// A palette never moves anything on the board. It ranks the shelf and it
// reads the outfit; that is all it does.

import { hexToOklab, oklabDistance } from './colour.js';

/** Index the built file: palettes by id, and each category's groups in order. */
export function indexPalettes(doc) {
  const palettes = (doc && doc.palettes) || [];
  const byId = {};
  for (const p of palettes) byId[p.id] = p;
  const categories = ((doc && doc.categories) || []).map((c) => ({
    ...c,
    groups: (c.groups || []).map((g) => ({
      ...g, count: palettes.filter((p) => p.category === c.key && p.group === g.key).length,
    })).filter((g) => g.count > 0),
  }));
  return { byId, categories, palettes };
}

/** The palettes in one category group, in file order. */
export function palettesIn(index, category, group) {
  return index.palettes.filter((p) => p.category === category && (!group || p.group === group));
}

/** What travels with a board and an outfit file: enough to show and to reopen. */
export function paletteSnapshot(p) {
  if (!p) return null;
  return {
    id: p.id,
    name: p.name,
    category: p.category,
    group: p.group || '',
    group_label: p.group_label || '',
    when: p.when || '',
    colours: (p.colours || []).map((c) => ({
      hex: c.hex, name: c.name, role: c.role, share: c.share, placement: c.placement || null,
    })),
    source: p.source ? { kind: p.source.kind, confidence: p.source.confidence, ref: p.source.ref } : null,
    ...(p.derived ? { derived: true, derived_from: p.derived_from } : {}),
  };
}

/** A placement list as words: "upper, mid" — or empty when the frameworks give none. */
export const placementText = (pl) => (Array.isArray(pl) && pl.length ? pl.join(', ') : '');

// How much of the body each slot covers, for the colour-share readout.
// matching.md §3, tier balance: top and bottom count double, a dress counts
// as four; everything else counts once.
export const SLOT_WEIGHT = { top: 2, bottom: 2, dress: 4 };

// OKLab distance within which a piece's colour counts as one of the palette's.
// A reading aid on the desk, not a verdict: the engine's own test is ΔE2000.
export const SHARE_MATCH = 0.12;

/**
 * How the pieces on the canvas divide by colour, against the palette's
 * suggested shares. Each piece contributes its slot weight, split over its
 * own measured colours by their shares; each colour goes to the nearest
 * palette colour when it is within SHARE_MATCH, and to `outside` when not.
 *
 * Returns { rows: [{hex, name, role, suggested, actual}], outside, pieces }.
 * Shares are percentages of the outfit; they add to 100 with `outside`.
 */
export function outfitShares(board, productsById, palette) {
  const cols = (palette?.colours || []).map((c) => ({ ...c, lab: hexToOklab(c.hex), got: 0 }));
  let outside = 0, total = 0, pieces = 0;
  for (const el of board.elements || []) {
    if (el.kind !== 'product') continue;
    const p = productsById[el.product_id];
    if (!p) continue;
    const own = (p.colours || []).filter((c) => c.hex && (c.share || 0) > 0);
    if (!own.length) continue;
    pieces++;
    const w = SLOT_WEIGHT[p.slot] || 1;
    const sum = own.reduce((a, c) => a + c.share, 0);
    for (const c of own) {
      const part = (w * c.share) / sum;
      total += part;
      const lab = hexToOklab(c.hex);
      let best = null, bd = Infinity;
      for (const pc of cols) {
        const d = oklabDistance(lab, pc.lab);
        if (d < bd) { bd = d; best = pc; }
      }
      if (best && bd <= SHARE_MATCH) best.got += part;
      else outside += part;
    }
  }
  const pct = (v) => (total ? Math.round((v / total) * 1000) / 10 : 0);
  return {
    rows: cols.map((c) => ({ hex: c.hex, name: c.name, role: c.role, suggested: c.share, actual: pct(c.got) })),
    outside: pct(outside),
    pieces,
  };
}

// ------------------------------------------------------------ shelf matching
// "Matches this palette" and the swatch filter. Calibrated by eye on 24 Sept
// against Plum and Old Gold (soft plum #5C3A4E, stone #D6CEC2, old gold
// #B8963E) over the 1,380 pieces then on the shelf.
//
// Two things went wrong with ranking by plain OKLab distance to the nearest
// palette colour:
//  - a light neutral swatch (stone) sits within 0.02 of every cream, white and
//    oatmeal in the catalogue, so it filled the whole top of the list, and a
//    5% cream trim counted as much as the garment itself;
//  - a muted chromatic swatch (soft plum, chroma 0.056) sits as close to navy,
//    chocolate and olive as to a real plum, because plain distance barely
//    charges for hue when chroma is low.
// So: a colour counts only when it is a fifth of the piece or more; hue
// differences cost HUE_WEIGHT times what they would in OKLab; a neutral swatch
// matches only a piece whose main colour is neutral, and a chromatic swatch
// only a chromatic colour; anything further than PALETTE_MATCH drops out.

/** OKLab chroma below which a colour is a neutral (stone is 0.019, soft plum 0.056). */
export const NEUTRAL_CHROMA = 0.035;
/** A piece's colour must cover this share of it to count toward a match. */
export const MIN_MATCH_SHARE = 0.2;
/** How much more a hue difference costs than in plain OKLab. */
export const HUE_WEIGHT = 2.5;
/**
 * The cut-off, in hue-weighted OKLab. At 0.10 soft plum keeps its plums,
 * burgundies and oxbloods and loses the chocolate browns that start at ~0.10;
 * old gold keeps mustard, ochre, camel and golden tan and loses pale beige,
 * which starts at ~0.10.
 */
export const PALETTE_MATCH = 0.10;
/**
 * The cut-off for a neutral swatch. Tighter: past 0.07 stone takes in bright
 * white and pale pink, which sit a whole step lighter than it.
 */
export const NEUTRAL_MATCH = 0.07;

const ROLE_ORDER = { dominant: 0, secondary: 1, accent: 2 };
const chromaOf = (lab) => Math.hypot(lab[1], lab[2]);
export const isNeutralLab = (lab) => !!lab && chromaOf(lab) < NEUTRAL_CHROMA;

/** OKLab distance with the hue term weighted (ΔH as in CIE: 2·√(C1C2)·sin(Δh/2)). */
export function hueWeightedDistance(a, b, k = HUE_WEIGHT) {
  if (!a || !b) return Infinity;
  const c1 = chromaOf(a), c2 = chromaOf(b);
  let dh = Math.abs(Math.atan2(a[2], a[1]) - Math.atan2(b[2], b[1]));
  if (dh > Math.PI) dh = 2 * Math.PI - dh;
  const dH = 2 * Math.sqrt(c1 * c2) * Math.sin(dh / 2);
  const dL = a[0] - b[0], dC = c1 - c2;
  return Math.sqrt(dL * dL + dC * dC + k * k * dH * dH);
}

/**
 * How close a piece comes to one palette colour, or Infinity when it does not
 * match it at all. A neutral swatch reads only the piece's main colour, and
 * only when that colour is itself neutral; a chromatic swatch reads every
 * chromatic colour that covers MIN_MATCH_SHARE of the piece.
 */
export function swatchDistance(product, swatch) {
  const target = swatch._lab || hexToOklab(swatch.hex);
  if (!target) return Infinity;
  const own = (product.colours || []).filter((c) => c.hex);
  if (!own.length) return Infinity;
  if (isNeutralLab(target)) {
    const main = own.reduce((a, c) => ((c.share || 0) > (a.share || 0) ? c : a), own[0]);
    const lab = hexToOklab(main.hex);
    if (!isNeutralLab(lab)) return Infinity;
    const d = hueWeightedDistance(lab, target);
    return d <= NEUTRAL_MATCH ? d : Infinity;
  }
  let best = Infinity;
  for (const c of own) {
    if ((c.share || 0) < MIN_MATCH_SHARE) continue;
    const lab = hexToOklab(c.hex);
    if (!lab || isNeutralLab(lab)) continue;
    const d = hueWeightedDistance(lab, target);
    if (d < best) best = d;
  }
  return best <= PALETTE_MATCH ? best : Infinity;
}

/** The pieces that match one swatch, closest first. Ties keep incoming order. */
export function matchSwatch(products, swatch) {
  const s = { ...swatch, _lab: hexToOklab(swatch.hex) };
  return products.map((p, i) => ({ p, i, d: swatchDistance(p, s) }))
    .filter((x) => x.d < Infinity)
    .sort((x, y) => x.d - y.d || x.i - y.i)
    .map((x) => x.p);
}

/** The palette's colours in matching order: chromatic by role, then neutrals by role. */
export function matchOrder(palette) {
  return (palette?.colours || []).map((c, i) => ({ ...c, _i: i, _lab: hexToOklab(c.hex) }))
    .filter((c) => c._lab)
    .sort((a, b) => (isNeutralLab(a._lab) - isNeutralLab(b._lab))
      || ((ROLE_ORDER[a.role] ?? 3) - (ROLE_ORDER[b.role] ?? 3)) || a._i - b._i);
}

/**
 * "Matches this palette": the pieces that match the chromatic colours first
 * (dominant, then secondary, then accent), each group closest first, then the
 * pieces that match a neutral swatch. A piece is listed once, under the first
 * colour in that order it matches. Pieces that match nothing are left out.
 */
export function rankByPalette(products, palette) {
  const order = matchOrder(palette);
  const scored = products.map((p, i) => {
    for (let g = 0; g < order.length; g++) {
      const d = swatchDistance(p, order[g]);
      if (d < Infinity) return { p, i, g, d };
    }
    return null;
  }).filter(Boolean);
  scored.sort((x, y) => x.g - y.g || x.d - y.d || x.i - y.i);
  return scored.map((x) => x.p);
}

/** Per palette colour (in the palette's own order): how many pieces match it. */
export function swatchCounts(products, palette) {
  return (palette?.colours || []).map((c) => matchSwatch(products, c).length);
}
