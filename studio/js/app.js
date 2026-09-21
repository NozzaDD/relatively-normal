// The desk. Loads a catalogue through a source, draws the shelf and the
// canvas, and hands the finished board over as files.
//
// The machine sorts, suggests and renders. It never places anything.

import { createStaticSource, indexById, indexInspiration, emptyFilters,
  filterProducts, WEIGHT_LABELS, FORMALITY_LABELS } from './data.js';
import * as M from './model.js';
import { metrics, isTile } from './render.js';
import { rankByLook } from './colour.js';
import * as X from './export.js';

const $ = (id) => document.getElementById(id);
const STORE = 'rn.studio.board.v2';

const S = {
  source: createStaticSource('.'),
  products: [], inspiration: [], productsById: {}, inspById: {},
  board: M.createBoard('portrait'),
  history: M.createHistory(),
  filters: emptyFilters(),
  matchSort: false,
  view: 'grid',
  selected: null,
  shown: [],
};
window.__studio = S;                      // the test harness reaches in here

// ------------------------------------------------------------------ start
init().catch((e) => toast(`Could not load the catalogue: ${e.message}`, 6000));

async function init() {
  const cat = await S.source.load();
  S.products = cat.products;
  S.inspiration = cat.inspiration;
  S.productsById = indexById(S.products);
  S.inspById = indexInspiration(S.inspiration);
  buildFilterOptions(cat.meta);
  restore();
  wire();
  renderShelf();
  renderMatrix();
  layoutStage();
  renderBoard();
}

// --------------------------------------------------------------- filters UI
function buildFilterOptions(meta) {
  const add = (sel, values, label = (v) => v) => {
    for (const v of values) {
      const o = document.createElement('option');
      o.value = v; o.textContent = label(v);
      sel.appendChild(o);
    }
  };
  add($('fSlot'), meta.slots || [...new Set(S.products.map((p) => p.slot).filter(Boolean))].sort());
  add($('fFamily'), meta.families || []);
  add($('fWeight'), [1, 2, 3, 4], (v) => `${v} · ${WEIGHT_LABELS[v]}`);
  add($('fFormality'), [1, 2, 3, 4], (v) => `${v} · ${FORMALITY_LABELS[v]}`);
  add($('fAsset'), meta.asset_types || [], (v) => ({
    cutout_flat: 'flat cut-out', cutout_model: 'on-model cut-out', tile: 'tile',
  }[v] || v));
  add($('fBrand'), meta.brands || []);
}

function readFilters() {
  S.filters = {
    slot: $('fSlot').value, family: $('fFamily').value, weight: $('fWeight').value,
    formality: $('fFormality').value, assetType: $('fAsset').value, brand: $('fBrand').value,
    search: $('search').value, showWeak: $('fWeak').checked,
  };
  S.matchSort = $('fMatch').checked;
}

// -------------------------------------------------------------------- shelf
// Default order: the pieces that cut out cleanly first, then the page tiles.
// It is a suggestion about picture quality, not about taste — a tile is still
// one tap away and can go on a board like anything else.
const imageRank = (p) => (p.asset_type === 'tile' ? 2 : 0)
  + (p.asset_quality === 'good' ? 0 : 1);

function currentList() {
  let list = filterProducts(S.products, S.filters);
  const look = S.board.inspiration ? S.inspById[S.board.inspiration] : null;
  if (S.matchSort && look) list = rankByLook(list, look);
  else list = list.map((p, i) => ({ p, i })).sort((a, b) => imageRank(a.p) - imageRank(b.p) || a.i - b.i)
    .map((x) => x.p);
  return list;
}

function renderShelf() {
  const grid = $('grid');
  const list = currentList();
  S.shown = list;
  $('shelfCount').textContent = `${list.length} of ${S.products.length}`;
  grid.replaceChildren();
  const frag = document.createDocumentFragment();
  for (const p of list) {
    const cell = document.createElement('div');
    cell.className = 'cell';
    cell.dataset.pid = p.product_id;
    const img = document.createElement('img');
    img.loading = 'lazy';
    img.src = S.source.thumbUrl(p);
    img.alt = p.garment_type || p.product_id;
    cell.appendChild(img);
    if (p.colour_confidence === 'low') {
      const d = document.createElement('span');
      d.className = 'dot';
      d.title = 'colour read with low confidence';
      cell.appendChild(d);
    }
    if (p.asset_quality === 'weak') {
      const w = document.createElement('span');
      w.className = 'weak'; w.textContent = 'weak';
      cell.appendChild(w);
    }
    const tag = document.createElement('span');
    tag.className = 'tag';
    tag.textContent = [p.brand, (p.colours[0] || {}).name].filter(Boolean).join(' · ')
      || p.garment_type || p.product_id;
    cell.appendChild(tag);
    frag.appendChild(cell);
  }
  grid.appendChild(frag);
}

function renderMatrix() {
  const g = $('matrixGrid');
  g.replaceChildren();
  const head = (t) => {
    const d = document.createElement('div');
    d.className = 'mcell head'; d.textContent = t;
    return d;
  };
  g.appendChild(head(''));
  for (let f = 1; f <= 4; f++) g.appendChild(head(FORMALITY_LABELS[f]));
  const pool = filterProducts(S.products, { ...S.filters, weight: '', formality: '' });
  for (let w = 1; w <= 4; w++) {
    g.appendChild(head(WEIGHT_LABELS[w]));
    for (let f = 1; f <= 4; f++) {
      const inCell = pool.filter((p) => p.weight === w && p.formality === f);
      const c = document.createElement('div');
      c.className = 'mcell' + (inCell.length ? '' : ' empty');
      const b = document.createElement('b');
      b.textContent = inCell.length;
      c.appendChild(b);
      const sw = document.createElement('div');
      sw.className = 'mswatches';
      for (const p of inCell.slice(0, 6)) {
        const i = document.createElement('i');
        i.style.background = (p.colours[0] || {}).hex || '#ccc';
        sw.appendChild(i);
      }
      c.appendChild(sw);
      c.addEventListener('click', () => {
        $('fWeight').value = String(w);
        $('fFormality').value = String(f);
        readFilters(); renderShelf(); setView('grid');
      });
      g.appendChild(c);
    }
  }
}

function setView(v) {
  S.view = v;
  $('grid').classList.toggle('hidden', v !== 'grid');
  $('matrix').classList.toggle('hidden', v !== 'matrix');
  document.querySelectorAll('.tab').forEach((t) => t.classList.toggle('on', t.dataset.view === v));
  if (v === 'matrix') renderMatrix();
}

// -------------------------------------------------------------------- stage
function stageSize() {
  const f = M.FORMATS[S.board.format];
  const wrap = $('stageWrap');
  const availW = wrap.clientWidth - 28;
  const availH = wrap.clientHeight - 28;
  let w = availW;
  let h = w / f.ratio;
  if (h > availH) { h = availH; w = h * f.ratio; }
  return { w: Math.max(120, Math.round(w)), h: Math.max(120, Math.round(h)) };
}

function layoutStage() {
  const { w, h } = stageSize();
  const st = $('stage');
  st.style.width = `${w}px`;
  st.style.height = `${h}px`;
}

function renderBoard() {
  const st = $('stage');
  const W = st.clientWidth;
  const H = st.clientHeight;
  const m = metrics(W, H);
  st.style.background = S.board.ground;
  $('hint').classList.toggle('gone', S.board.elements.length > 0);

  // pieces
  const layers = $('layers');
  layers.replaceChildren();
  for (const el of M.stacked(S.board)) {
    const p = el.kind === 'product' ? S.productsById[el.product_id] : null;
    const insp = el.kind === 'inspiration' ? S.inspById[el.inspiration_id] : null;
    const framed = isTile(el.kind, p?.asset_type);
    const d = document.createElement('div');
    d.className = `el ${framed ? 'tile' : 'cut'}${S.selected === el.uid ? ' sel' : ''}`;
    d.dataset.uid = el.uid;
    d.style.left = `${el.x * 100}%`;
    d.style.top = `${el.y * 100}%`;
    d.style.width = `${el.w * 100}%`;
    d.style.aspectRatio = String(el.aspect || 1);
    d.style.zIndex = String(el.z);
    d.style.transform = `translate(-50%,-50%) rotate(${el.rot || 0}deg) scaleX(${el.flip ? -1 : 1})`;
    if (framed) d.style.padding = `${m.mat}px`;
    const img = document.createElement('img');
    img.src = p ? S.source.assetUrl(p) : (insp ? S.source.inspirationUrl(insp) : '');
    img.alt = '';
    img.draggable = false;
    d.appendChild(img);
    if (S.selected === el.uid) {
      for (const k of ['resize', 'rotate']) {
        const h2 = document.createElement('div');
        h2.className = `handle ${k}`;
        h2.dataset.handle = k;
        h2.dataset.uid = el.uid;
        h2.textContent = k === 'resize' ? '⤡' : '⟳';
        d.appendChild(h2);
      }
    }
    layers.appendChild(d);
  }

  // title, line, strip, numbers
  const ov = $('overlay');
  ov.replaceChildren();
  let ty = m.margin;
  if (S.board.showTitle && S.board.title) {
    const t = document.createElement('div');
    t.className = 'board-text board-title';
    t.style.top = `${ty}px`;
    t.style.fontSize = `${m.title}px`;
    t.style.lineHeight = '1.05';
    t.textContent = S.board.title;
    ov.appendChild(t);
    ty += Math.round(m.title * 1.16);
  }
  if (S.board.showLine && S.board.line) {
    const l = document.createElement('div');
    l.className = 'board-text board-line';
    l.style.top = `${ty}px`;
    l.style.fontSize = `${m.line}px`;
    l.textContent = S.board.line;
    ov.appendChild(l);
  }
  if (S.board.showSwatches) {
    const chips = M.swatchStrip(S.board, S.productsById);
    if (chips.length) {
      const strip = document.createElement('div');
      strip.className = 'board-strip';
      strip.style.bottom = `${m.margin}px`;
      strip.style.height = `${m.strip}px`;
      const total = chips.reduce((a, c) => a + (c.share || 1), 0) || 1;
      chips.forEach((c) => {
        const i = document.createElement('i');
        i.style.background = c.hex;
        i.style.width = `${((c.share || 1) / total) * 100}%`;
        strip.appendChild(i);
      });
      ov.appendChild(strip);
    }
  }
  if (S.board.showLabels) {
    M.labelOrder(S.board).forEach((el, i) => {
      const b = M.elementBox(el, W, H);
      const d = document.createElement('div');
      d.className = 'badge';
      d.style.width = d.style.height = `${m.disc * 2}px`;
      d.style.left = `${b.x + b.w - m.disc * 2}px`;
      d.style.top = `${b.y}px`;
      d.style.fontSize = `${Math.round(m.disc * 1.15)}px`;
      d.style.zIndex = '9999';
      d.textContent = String(i + 1);
      ov.appendChild(d);
    });
  }

  renderHelpers();
  $('elementBar').hidden = !S.selected;
  autosave();
}

function renderHelpers() {
  const list = M.slotChecklist(S.board, S.productsById);
  const sl = $('slotList');
  sl.replaceChildren();
  for (const s of list) {
    const c = document.createElement('span');
    c.className = 'slot-chip' + (s.count ? ' has' : '');
    c.textContent = s.count ? `${s.slot} ${s.count > 1 ? `×${s.count}` : ''}`.trim() : s.slot;
    sl.appendChild(c);
  }
  const a = M.axes(S.board, S.productsById);
  $('axesRead').textContent = a.n
    ? `${a.n} piece${a.n > 1 ? 's' : ''} · weight ${a.weight.toFixed(1)} of 4 · formality ${a.formality.toFixed(1)} of 4`
    : 'nothing on the canvas yet';
}

// ---------------------------------------------------------------- placing
function defaultWidth(slot) {
  return ({ layer: 0.42, dress: 0.5, top: 0.34, base: 0.32, bottom: 0.38,
    shoes: 0.2, bag: 0.22, accessory: 0.2, multiple: 0.34 }[slot]) || 0.3;
}

async function aspectOf(src) {
  try {
    const img = await X.loadImage(src);
    return img.naturalWidth / img.naturalHeight || 1;
  } catch (e) { return 1; }
}

async function placeProduct(pid, x, y) {
  const p = S.productsById[pid];
  if (!p) return;
  M.commit(S.history, S.board);
  const aspect = await aspectOf(S.source.thumbUrl(p));
  M.addElement(S.board, {
    kind: 'product', product_id: pid, x: clamp01(x), y: clamp01(y),
    w: defaultWidth(p.slot), aspect,
  });
  renderBoard();
}

async function placeInspiration(iid) {
  const insp = S.inspById[iid];
  M.commit(S.history, S.board);
  S.board.elements = S.board.elements.filter((e) => e.kind !== 'inspiration');
  S.board.inspiration = iid || null;
  if (insp) {
    const aspect = await aspectOf(S.source.thumbUrl ? S.source.inspirationThumbUrl(insp) : insp.image);
    M.addElement(S.board, {
      kind: 'inspiration', inspiration_id: iid, x: 0.27, y: 0.52, w: 0.40, aspect, z: 0,
    });
    // the look sits under the pieces by default; the stylist can raise it
    S.board.elements.forEach((e) => { if (e.kind !== 'inspiration') e.z = Math.max(e.z, 1); });
  }
  $('fMatch').disabled = !iid;
  if (!iid) { $('fMatch').checked = false; S.matchSort = false; }
  renderBoard();
  renderShelf();
}

const clamp01 = (v) => Math.min(0.99, Math.max(0.01, v));

// -------------------------------------------------------------- gestures
let drag = null;

function stagePoint(ev) {
  const r = $('stage').getBoundingClientRect();
  return { x: (ev.clientX - r.left) / r.width, y: (ev.clientY - r.top) / r.height, r };
}

function onShelfDown(ev) {
  const cell = ev.target.closest('.cell');
  if (!cell) return;
  ev.preventDefault();
  const pid = cell.dataset.pid;
  const p = S.productsById[pid];
  if (!p) return;
  drag = { type: 'shelf', pid, moved: false, pointerId: ev.pointerId };
  const g = $('drag');
  g.replaceChildren();
  const img = document.createElement('img');
  img.src = S.source.thumbUrl(p);
  g.appendChild(img);
  g.style.left = `${ev.clientX}px`;
  g.style.top = `${ev.clientY}px`;
  g.hidden = false;
  cell.setPointerCapture?.(ev.pointerId);
}

function onShelfMove(ev) {
  if (!drag || drag.type !== 'shelf') return;
  drag.moved = true;
  const g = $('drag');
  g.style.left = `${ev.clientX}px`;
  g.style.top = `${ev.clientY}px`;
}

async function onShelfUp(ev) {
  if (!drag || drag.type !== 'shelf') return;
  const d = drag;
  drag = null;
  $('drag').hidden = true;
  const r = $('stage').getBoundingClientRect();
  const inside = ev.clientX >= r.left && ev.clientX <= r.right
    && ev.clientY >= r.top && ev.clientY <= r.bottom;
  if (inside) {
    await placeProduct(d.pid, (ev.clientX - r.left) / r.width, (ev.clientY - r.top) / r.height);
  } else if (!d.moved) {
    await placeProduct(d.pid, 0.5, 0.5);        // a tap drops it in the middle
  }
}

function onStageDown(ev) {
  const handle = ev.target.closest('.handle');
  const elDiv = ev.target.closest('.el');
  const pt = stagePoint(ev);
  // Without this the browser starts its own image drag on the first move and
  // sends pointercancel, which ends the gesture after a single frame.
  if (handle || elDiv) ev.preventDefault();
  if (handle) {
    const el = M.byId(S.board, handle.dataset.uid);
    M.commit(S.history, S.board);
    drag = { type: handle.dataset.handle, uid: el.uid, start: pt, w0: el.w, rot0: el.rot || 0 };
    $('stage').setPointerCapture(ev.pointerId);
    return;
  }
  if (!elDiv) { setSelection(null); return; }
  const el = M.byId(S.board, elDiv.dataset.uid);
  setSelection(el.uid);
  M.commit(S.history, S.board);
  drag = { type: 'move', uid: el.uid, dx: el.x - pt.x, dy: el.y - pt.y };
  $('stage').setPointerCapture(ev.pointerId);
}

function onStageMove(ev) {
  if (!drag || drag.type === 'shelf') return;
  const el = M.byId(S.board, drag.uid);
  if (!el) return;
  const pt = stagePoint(ev);
  if (drag.type === 'move') {
    el.x = clamp01(pt.x + drag.dx);
    el.y = clamp01(pt.y + drag.dy);
  } else if (drag.type === 'resize') {
    const dx = (pt.x - drag.start.x);
    el.w = Math.min(2.2, Math.max(0.04, drag.w0 + dx * 2));
  } else if (drag.type === 'rotate') {
    const a0 = Math.atan2(drag.start.y - el.y, drag.start.x - el.x);
    const a1 = Math.atan2(pt.y - el.y, pt.x - el.x);
    el.rot = Math.round((drag.rot0 + ((a1 - a0) * 180) / Math.PI) * 10) / 10;
  }
  applyElementStyle(el);
}

function applyElementStyle(el) {
  const d = $('layers').querySelector(`[data-uid="${el.uid}"]`);
  if (!d) return;
  d.style.left = `${el.x * 100}%`;
  d.style.top = `${el.y * 100}%`;
  d.style.width = `${el.w * 100}%`;
  d.style.transform = `translate(-50%,-50%) rotate(${el.rot || 0}deg) scaleX(${el.flip ? -1 : 1})`;
}

function onStageUp() {
  if (drag && drag.type !== 'shelf') {
    drag = null;
    renderBoard();
  }
}

/**
 * Selection is applied in place rather than by redrawing the board.
 * Replacing the node under the finger mid-gesture makes the browser fire
 * pointercancel, and the drag dies after one frame.
 */
function setSelection(uid) {
  S.selected = uid;
  const layers = $('layers');
  layers.querySelectorAll('.el.sel').forEach((d) => {
    d.classList.remove('sel');
    d.querySelectorAll('.handle').forEach((h) => h.remove());
  });
  const d = uid && layers.querySelector(`[data-uid="${uid}"]`);
  if (d) {
    d.classList.add('sel');
    for (const k of ['resize', 'rotate']) {
      const h = document.createElement('div');
      h.className = `handle ${k}`;
      h.dataset.handle = k;
      h.dataset.uid = uid;
      h.textContent = k === 'resize' ? '⤡' : '⟳';
      d.appendChild(h);
    }
  }
  $('elementBar').hidden = !uid;
}

// ------------------------------------------------------------------- save
async function save() {
  if (!S.board.elements.length) { toast('Nothing on the canvas yet.'); return; }
  const btn = $('save');
  btn.disabled = true;
  btn.textContent = 'Saving…';
  try {
    const date = new Date();
    const info = X.buildInfo(S.board, S.productsById, S.inspById, { date });
    const name = info.slug;
    const images = await X.loadBoardImages(S.board, S.source, S.productsById, S.inspById);
    const canvas = await X.renderBoardCanvas(S.board, S.productsById, images, 1);
    let png = await X.canvasToBlob(canvas, 'image/png');
    try {
      png = await X.pngWithMetadata(png, 'relatively-normal.outfit', JSON.stringify(info));
    } catch (e) { /* the JSON file is the source of truth anyway */ }
    const jpeg = await X.canvasToBlob(canvas, 'image/jpeg', 0.92);
    const md = X.buildMarkdown(info);
    const files = [
      new File([png], `${name}.png`, { type: 'image/png' }),
      new File([jpeg], `${name}.jpg`, { type: 'image/jpeg' }),
      new File([JSON.stringify(info, null, 1)], `${name}.json`, { type: 'application/json' }),
      new File([md], `${name}.md`, { type: 'text/markdown' }),
    ];
    const how = await X.handOver(files, { title: info.title || name });
    toast(how === 'shared' ? 'Sent to the share sheet.'
      : how === 'cancelled' ? 'Sharing cancelled.' : `Saved ${name} (4 files).`);
  } catch (e) {
    toast(`Save failed: ${e.message}`, 6000);
  } finally {
    btn.disabled = false;
    btn.textContent = 'Save';
  }
}

async function openInfo(text) {
  const info = JSON.parse(text);
  if (info.kind !== 'relatively-normal.outfit') throw new Error('not an outfit file');
  M.commit(S.history, S.board);
  const b = M.createBoard(info.format || 'portrait');
  b.title = info.title || '';
  b.line = info.line || '';
  b.ground = info.canvas?.ground || M.GROUND;
  const shown = info.elements_shown || {};
  b.showTitle = shown.title !== false;
  b.showLine = shown.line !== false;
  b.showSwatches = shown.swatch_strip !== false;
  b.showLabels = !!shown.numbered_labels;
  b.inspiration = info.inspiration?.inspiration_id || null;
  if (b.inspiration && info.inspiration.placement) {
    const pl = info.inspiration.placement;
    M.addElement(b, { kind: 'inspiration', inspiration_id: b.inspiration, x: pl.x, y: pl.y,
      w: pl.w, rot: pl.rotation, flip: pl.flip, z: pl.layer, aspect: pl.aspect || 1 });
  }
  const missing = [];
  for (const p of info.pieces || []) {
    if (!S.productsById[p.product_id]) { missing.push(p.product_id); continue; }
    const pl = p.placement || {};
    M.addElement(b, { kind: 'product', product_id: p.product_id, x: pl.x ?? 0.5, y: pl.y ?? 0.5,
      w: pl.w ?? 0.3, rot: pl.rotation || 0, flip: !!pl.flip, z: pl.layer ?? 1,
      aspect: pl.aspect || 1 });
  }
  S.board = b;
  S.selected = null;
  syncControls();
  $('fMatch').disabled = !b.inspiration;
  layoutStage();
  renderBoard();
  // details always come from the catalogue as it is now, never from the file
  toast(missing.length
    ? `Opened. ${missing.length} piece(s) are no longer in the catalogue: ${missing.join(', ')}`
    : 'Opened. Piece details refreshed from the catalogue.', missing.length ? 7000 : 3000);
}

// ------------------------------------------------------------- persistence
function autosave() {
  try {
    localStorage.setItem(STORE, JSON.stringify(S.board));
  } catch (e) { /* private mode, full quota — the desk still works */ }
}

function restore() {
  let raw = null;
  try { raw = localStorage.getItem(STORE); } catch (e) { raw = null; }
  if (!raw) return;
  try {
    const b = JSON.parse(raw);
    if (b && Array.isArray(b.elements)) {
      b.elements = b.elements.filter((e) => e.kind === 'inspiration'
        ? !!S.inspById[e.inspiration_id] : !!S.productsById[e.product_id]);
      S.board = { ...M.createBoard(b.format || 'portrait'), ...b };
    }
  } catch (e) { /* corrupt or from an older version: start clean */ }
}

// -------------------------------------------------------------------- wiring
function syncControls() {
  $('title').value = S.board.title;
  $('line').value = S.board.line;
  $('format').value = S.board.format;
  $('ground').value = S.board.ground;
  $('oTitle').checked = S.board.showTitle;
  $('oLine').checked = S.board.showLine;
  $('oSwatch').checked = S.board.showSwatches;
  $('oLabels').checked = S.board.showLabels;
}

function wire() {
  syncControls();
  $('fMatch').disabled = !S.board.inspiration;

  for (const id of ['fSlot', 'fFamily', 'fWeight', 'fFormality', 'fAsset', 'fBrand', 'fWeak', 'fMatch']) {
    $(id).addEventListener('change', () => { readFilters(); renderShelf(); if (S.view === 'matrix') renderMatrix(); });
  }
  let t;
  $('search').addEventListener('input', () => {
    clearTimeout(t);
    t = setTimeout(() => { readFilters(); renderShelf(); }, 140);
  });
  $('clearFilters').addEventListener('click', () => {
    for (const id of ['fSlot', 'fFamily', 'fWeight', 'fFormality', 'fAsset', 'fBrand']) $(id).value = '';
    $('search').value = ''; $('fWeak').checked = false; $('fMatch').checked = false;
    readFilters(); renderShelf(); renderMatrix();
  });
  document.querySelectorAll('.tab').forEach((b) => b.addEventListener('click', () => setView(b.dataset.view)));
  $('toggleShelf').addEventListener('click', () => {
    $('shelf').classList.toggle('hidden');
    requestAnimationFrame(() => { layoutStage(); renderBoard(); });
  });

  // shelf drag
  const grid = $('grid');
  grid.addEventListener('pointerdown', onShelfDown);
  grid.addEventListener('pointermove', onShelfMove);
  grid.addEventListener('pointerup', onShelfUp);
  grid.addEventListener('pointercancel', () => { drag = null; $('drag').hidden = true; });

  // canvas
  const stage = $('stage');
  stage.addEventListener('pointerdown', onStageDown);
  stage.addEventListener('pointermove', onStageMove);
  stage.addEventListener('pointerup', onStageUp);
  stage.addEventListener('pointercancel', onStageUp);

  $('elementBar').addEventListener('click', (ev) => {
    const act = ev.target.dataset.act;
    if (!act || !S.selected) return;
    M.commit(S.history, S.board);
    const el = M.byId(S.board, S.selected);
    if (act === 'forward') M.bringForward(S.board, S.selected);
    if (act === 'back') M.sendBack(S.board, S.selected);
    if (act === 'flip' && el) el.flip = !el.flip;
    if (act === 'duplicate') { const d = M.duplicateElement(S.board, S.selected); if (d) S.selected = d.uid; }
    if (act === 'delete') { M.removeElement(S.board, S.selected); S.selected = null; }
    renderBoard();
  });

  $('title').addEventListener('input', (e) => { S.board.title = e.target.value; renderBoard(); });
  $('line').addEventListener('input', (e) => { S.board.line = e.target.value; renderBoard(); });
  $('ground').addEventListener('input', (e) => { S.board.ground = e.target.value; renderBoard(); });
  $('format').addEventListener('change', (e) => {
    M.commit(S.history, S.board);
    S.board.format = e.target.value;
    layoutStage(); renderBoard();
  });
  for (const [id, key] of [['oTitle', 'showTitle'], ['oLine', 'showLine'],
    ['oSwatch', 'showSwatches'], ['oLabels', 'showLabels']]) {
    $(id).addEventListener('change', (e) => { S.board[key] = e.target.checked; renderBoard(); });
  }

  $('undo').addEventListener('click', () => {
    const b = M.undo(S.history, S.board);
    if (b) { S.board = b; S.selected = null; syncControls(); layoutStage(); renderBoard(); }
  });
  $('redo').addEventListener('click', () => {
    const b = M.redo(S.history, S.board);
    if (b) { S.board = b; S.selected = null; syncControls(); layoutStage(); renderBoard(); }
  });
  $('newBoard').addEventListener('click', () => {
    if (S.board.elements.length && !confirm('Start a new board? The current one is not saved to a file.')) return;
    M.commit(S.history, S.board);
    S.board = M.createBoard(S.board.format);
    S.selected = null;
    syncControls(); renderBoard();
  });
  $('save').addEventListener('click', save);
  $('openBoard').addEventListener('click', () => $('openFile').click());
  $('openFile').addEventListener('change', async (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    try { await openInfo(await f.text()); } catch (err) { toast(`Could not open: ${err.message}`, 6000); }
    e.target.value = '';
  });

  // inspiration picker
  $('pickInspiration').addEventListener('click', openPicker);
  $('pickerClose').addEventListener('click', () => $('picker').classList.add('hidden'));
  $('pickerNone').addEventListener('click', () => {
    placeInspiration(null);
    $('picker').classList.add('hidden');
  });
  $('pickerSearch').addEventListener('input', () => renderPicker($('pickerSearch').value));

  window.addEventListener('resize', () => { layoutStage(); renderBoard(); });
  window.addEventListener('keydown', (e) => {
    if (e.target.matches('input, select, textarea')) return;
    if ((e.metaKey || e.ctrlKey) && e.key === 'z') { e.preventDefault(); $(e.shiftKey ? 'redo' : 'undo').click(); }
    if ((e.key === 'Backspace' || e.key === 'Delete') && S.selected) {
      e.preventDefault();
      M.commit(S.history, S.board);
      M.removeElement(S.board, S.selected);
      S.selected = null;
      renderBoard();
    }
  });
}

function openPicker() {
  $('picker').classList.remove('hidden');
  renderPicker($('pickerSearch').value);
}

function renderPicker(q = '') {
  const grid = $('pickerGrid');
  grid.replaceChildren();
  const needle = q.trim().toLowerCase();
  const list = S.inspiration.filter((i) => !needle || [
    i.house, i.colour_story, i.folder, ...(i.colours || []).map((c) => c.name),
  ].join(' ').toLowerCase().includes(needle));
  for (const i of list) {
    const b = document.createElement('button');
    b.className = 'pick';
    const img = document.createElement('img');
    img.loading = 'lazy';
    img.src = S.source.inspirationThumbUrl(i);
    b.appendChild(img);
    const cols = document.createElement('div');
    cols.className = 'pcols';
    for (const c of i.colours || []) {
      const s = document.createElement('i');
      s.style.background = c.hex;
      cols.appendChild(s);
    }
    b.appendChild(cols);
    const k = document.createElement('div');
    k.className = 'pk';
    k.textContent = [(i.colours || []).map((c) => c.name).slice(0, 3).join(', '),
      i.house || ''].filter(Boolean).join(' — ');
    b.appendChild(k);
    b.addEventListener('click', () => {
      placeInspiration(i.inspiration_id);
      $('picker').classList.add('hidden');
    });
    grid.appendChild(b);
  }
}

let toastTimer;
function toast(msg, ms = 2600) {
  const t = $('toast');
  t.textContent = msg;
  t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { t.hidden = true; }, ms);
}

// exposed for the headless test
Object.assign(S, { placeProduct, placeInspiration, renderShelf, renderBoard, save, openInfo,
  buildInfo: () => X.buildInfo(S.board, S.productsById, S.inspById),
  renderCanvas: async () => {
    const images = await X.loadBoardImages(S.board, S.source, S.productsById, S.inspById);
    return X.renderBoardCanvas(S.board, S.productsById, images, 1);
  } });
