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
