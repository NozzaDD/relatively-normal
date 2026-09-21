// The board model. Pure data and pure functions — no DOM, no canvas.
// Both the live preview and the export renderer read this, so what you see is
// what gets saved.

import { mergeColours } from './colour.js';

export const FORMATS = {
  portrait: { key: 'portrait', ratio: 4 / 5, exportW: 2160, exportH: 2700, label: '4:5 portrait' },
  landscape: { key: 'landscape', ratio: 4 / 3, exportW: 2912, exportH: 2184, label: 'wide landscape' },
};

export const GROUND = '#F3EFE7';      // style-spec.md part B4
export const KEYLINE = '#D6CDBF';
export const INK = '#221F1C';
export const SLOTS = ['layer', 'top', 'bottom', 'shoes', 'bag', 'accessory'];
export const SLOT_ORDER = ['layer', 'top', 'bottom', 'dress', 'shoes', 'bag', 'accessory'];

// How framed things — the inspiration image, crop boxes, page tiles — are
// drawn. One setting for the whole board, never baked into a file.
export const DEFAULT_FRAME = { border: true, radius: 0, mat: true };

let seq = 0;
export const uid = () => `e${Date.now().toString(36)}${(seq++).toString(36)}`;

export function createBoard(format = 'portrait') {
  return {
    version: 1,
    format,
    ground: GROUND,
    title: '',
    line: '',
    showTitle: true,
    showLine: true,
    showSwatches: true,
    showLabels: false,
    inspiration: null,
    frame: { ...DEFAULT_FRAME },
    elements: [],
  };
}

/**
 * Coordinates are normalised: x and y are the element centre as a fraction of
 * board width and height, w is the width as a fraction of board width. Height
 * follows from the image's own aspect, so nothing is ever squashed.
 */
export function addElement(board, el) {
  const z = board.elements.reduce((m, e) => Math.max(m, e.z), 0) + 1;
  const next = {
    uid: uid(), kind: 'product', x: 0.5, y: 0.5, w: 0.3, rot: 0, flip: false,
    aspect: 1, z, variant: 'cutout', crop: null, ...el,
  };
  board.elements.push(next);
  return next;
}

export const byId = (board, uid) => board.elements.find((e) => e.uid === uid);

export function removeElement(board, uid) {
  board.elements = board.elements.filter((e) => e.uid !== uid);
}

export function duplicateElement(board, uid) {
  const e = byId(board, uid);
  if (!e) return null;
  return addElement(board, { ...e, uid: undefined, x: Math.min(0.97, e.x + 0.04), y: Math.min(0.97, e.y + 0.04) });
}

export function bringForward(board, uid) {
  const e = byId(board, uid);
  if (!e) return;
  const above = board.elements.filter((o) => o.z > e.z).sort((a, b) => a.z - b.z)[0];
  if (above) { const t = e.z; e.z = above.z; above.z = t; }
}

export function sendBack(board, uid) {
  const e = byId(board, uid);
  if (!e) return;
  const below = board.elements.filter((o) => o.z < e.z).sort((a, b) => b.z - a.z)[0];
  if (below) { const t = e.z; e.z = below.z; below.z = t; }
}

export const stacked = (board) => [...board.elements].sort((a, b) => a.z - b.z);

/**
 * Where an image sits inside a box that shows only `crop` of it.
 * crop is [x, y, w, h] as fractions of the full image. Returns the image's
 * size and offset as fractions of the box, for CSS and for canvas alike.
 */
export function cropLayout(crop) {
  const [x, y, w, h] = crop || [0, 0, 1, 1];
  return { imgW: 1 / w, imgH: 1 / h, left: -x / w, top: -y / h };
}

/** Aspect (w/h) of what an element shows: the crop of the full image, or the asset. */
export function shownAspect(product, variant, crop) {
  if (variant && variant !== 'cutout' && product?.full && crop) {
    return (crop[2] * product.full.w) / (crop[3] * product.full.h);
  }
  return null;
}

/** Product elements in the order their numbered labels run. */
export function labelOrder(board) {
  return board.elements.filter((e) => e.kind === 'product').sort((a, b) => a.z - b.z);
}

/** Pixel geometry for one element on a board of the given pixel size. */
export function elementBox(el, W, H) {
  const w = el.w * W;
  const h = w / (el.aspect || 1);
  return { w, h, cx: el.x * W, cy: el.y * H, x: el.x * W - w / 2, y: el.y * H - h / 2 };
}

// ---------------------------------------------------------------- helpers
// These report. They never place anything.

export function slotChecklist(board, productsById) {
  const have = {};
  for (const e of board.elements) {
    if (e.kind !== 'product') continue;
    const p = productsById[e.product_id];
    if (p?.slot) have[p.slot] = (have[p.slot] || 0) + 1;
  }
  return SLOTS.map((slot) => ({ slot, count: have[slot] || 0 }));
}

export function axes(board, productsById) {
  const ps = board.elements
    .filter((e) => e.kind === 'product')
    .map((e) => productsById[e.product_id])
    .filter(Boolean);
  const avg = (k) => {
    const v = ps.map((p) => p[k]).filter((x) => typeof x === 'number');
    return v.length ? v.reduce((a, b) => a + b, 0) / v.length : null;
  };
  return { weight: avg('weight'), formality: avg('formality'), n: ps.length };
}

/** The strip carries only colours the pieces on the board actually have. */
export function swatchStrip(board, productsById, max = 5) {
  const list = [];
  for (const e of labelOrder(board)) {
    const p = productsById[e.product_id];
    if (!p) continue;
    for (const c of (p.colours || []).slice(0, 2)) {
      if ((c.share || 0) >= 0.25) list.push({ hex: c.hex, name: c.name, share: c.share });
    }
  }
  return mergeColours(list).slice(0, max);
}

export function slugify(s) {
  return String(s || '').toLowerCase().normalize('NFKD').replace(/[̀-ͯ]/g, '')
    .replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 48);
}

export function dateSlug(title, date = new Date()) {
  const d = [date.getFullYear(), date.getMonth() + 1, date.getDate()]
    .map((x, i) => (i ? String(x).padStart(2, '0') : x)).join('-');
  const s = slugify(title);
  return s ? `${d}-${s}` : `${d}-untitled`;
}

// ------------------------------------------------------------------ history
export function createHistory(limit = 60) {
  return { past: [], future: [], limit };
}

const snap = (board) => JSON.stringify(board);

export function commit(history, board) {
  history.past.push(snap(board));
  if (history.past.length > history.limit) history.past.shift();
  history.future.length = 0;
}

export function undo(history, board) {
  if (!history.past.length) return null;
  history.future.push(snap(board));
  return JSON.parse(history.past.pop());
}

export function redo(history, board) {
  if (!history.future.length) return null;
  history.past.push(snap(board));
  return JSON.parse(history.future.pop());
}
