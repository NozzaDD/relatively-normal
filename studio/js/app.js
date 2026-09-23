// The desk. Loads a catalogue through a source, draws the shelf and the
// canvas, and hands the finished board over as files.
//
// The machine sorts, suggests and renders. It never places anything.

import { createStaticSource, indexById, indexInspiration, emptyFilters,
  filterProducts, onShelf, effectiveChoice, isReviewed, derivedProducts,
  WEIGHT_LABELS, FORMALITY_LABELS, isDetail, applySlots, SLOT_PICK } from './data.js';
import * as M from './model.js';
import { metrics, isTile } from './render.js';
import { rankByLook } from './colour.js';
import * as X from './export.js';
import { createReview, loadChoices, saveChoices, choicesFile, choiceBox, choiceBase,
  applyCrop, migrateChoices } from './review.js';

const $ = (id) => document.getElementById(id);
const STORE = 'rn.studio.board.v2';
const SETTINGS = 'rn.studio.settings.v1';
const LONG_PRESS_MS = 300;
const SIDEWAYS_PX = 12;

const S = {
  source: createStaticSource('.'),
  products: [], inspiration: [], productsById: {}, inspById: {},
  board: M.createBoard('portrait'),
  history: M.createHistory(),
  filters: emptyFilters(),
  choices: {},
  settings: { frame: { ...M.DEFAULT_FRAME } },
  matchSort: false,
  view: 'grid',
  selected: null,
  shown: [],
  taps: 0,
  review: null,
  shelfPicture: {},                       // per product: which picture the shelf shows
  ready: false,
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
  S.choices = loadChoices();
  try {
    const mig = await fetch('data/trim-migration.json').then((r) => (r.ok ? r.json() : null));
    const moved = migrateChoices(S.choices, mig);
    if (moved) { saveChoices(S.choices); toast(`Moved ${moved} box(es) onto the new trim.`, 4000); }
  } catch (e) { /* no migration file: nothing to move */ }
  loadSettings();
  buildFilterOptions(cat.meta);
  refreshDerived();
  restore();
  S.review = createReview({
    source: S.source, choices: S.choices, products: () => S.products, toast,
    onChange: () => { refreshDerived(); renderSlotBar(); renderShelf(); renderReviewBadge(); },
  });
  wire();
  renderSlotBar();
  renderShelf();
  renderMatrix();
  renderReviewBadge();
  layoutStage();
  renderBoard();
  S.ready = true;               // the saved board is back: the desk is up
}

/** Pieces cut out of other products' images appear on the shelf at once. */
function refreshDerived() {
  S.products = S.products.filter((p) => !p.local);
  S.products.push(...derivedProducts(S.products, S.choices));
  applySlots(S.products, S.choices);        // a slot set here shows everywhere at once
  S.productsById = indexById(S.products);
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
    ...S.filters,
    family: $('fFamily').value, weight: $('fWeight').value,
    formality: $('fFormality').value, assetType: $('fAsset').value, brand: $('fBrand').value,
    search: $('search').value, showUnreviewed: $('fUnreviewed').checked,
  };
  S.matchSort = $('fMatch').checked;
}

/** Category buttons with counts. Counts respect every other filter and the
 *  gate, so the number is what tapping the button will show. */
function renderSlotBar() {
  const bar = $('slotBar');
  bar.replaceChildren();
  const pool = filterProducts(S.products, { ...S.filters, slot: '' }, S.choices);
  const counts = {};
  for (const p of pool) counts[p.slot] = (counts[p.slot] || 0) + 1;
  for (const slot of ['', ...M.SLOT_ORDER]) {
    const n = slot ? counts[slot] || 0 : pool.length;
    const b = document.createElement('button');
    b.className = 'ghost' + (S.filters.slot === slot ? ' on' : '');
    b.dataset.slot = slot;
    b.innerHTML = `${slot || 'All'}<small>${n}</small>`;
    b.addEventListener('click', () => setSlot(slot));
    bar.appendChild(b);
  }
}

function setSlot(slot) {
  S.filters.slot = S.filters.slot === slot ? '' : slot;
  if (!slot) S.filters.slot = '';
  renderSlotBar();
  renderShelf();
  renderHelpers();
  if (S.view !== 'grid') setView('grid');
}

// -------------------------------------------------------------------- shelf
// Default order: the pieces that cut out cleanly first, then the page tiles.
// It is a suggestion about picture quality, not about taste — a tile is still
// one tap away and can go on a board like anything else.
const imageRank = (p) => (p.asset_type === 'tile' ? 2 : 0)
  + (p.asset_quality === 'good' ? 0 : 1);

function currentList() {
  let list = filterProducts(S.products, S.filters, S.choices);
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
  const gate = S.products.filter((p) => onShelf(p, S.choices, S.filters.showUnreviewed)).length;
  $('shelfCount').textContent = `${list.length} of ${gate}`;
  grid.replaceChildren();
  const frag = document.createDocumentFragment();
  for (const p of list) {
    const cell = document.createElement('div');
    cell.className = 'cell';
    cell.dataset.pid = p.product_id;
    const img = document.createElement('img');
    img.loading = 'lazy';
    img.alt = p.garment_type || p.product_id;
    const pics = X_pictures(p);
    const shown = S.shelfPicture[p.product_id];
    if (p.thumb && shown === undefined) {
      img.src = S.source.thumbUrl(p);
      cell.appendChild(img);
    } else if (shown !== undefined) {
      // the stylist has flipped this one to another of its pictures
      img.src = S.source.wholeUrl(p, shown) || S.source.fullUrl(p, shown);
      cell.appendChild(img);
    } else {
      // no thumbnail file yet: show the crop straight from the screenshot
      const wrap = document.createElement('div');
      wrap.className = 'cropwrap';
      img.src = p.base === 'whole' ? (S.source.wholeUrl(p, p.image || 0) || S.source.fullUrl(p, p.image || 0))
        : S.source.fullUrl(p, p.image || 0);
      // p.full already points at whichever image the box was drawn on
      img.onload = () => applyCrop(img, p.custom_box || [0, 0, 1, 1], cell.clientWidth, cell.clientHeight - 18, p.full.w, p.full.h);
      wrap.appendChild(img);
      cell.appendChild(wrap);
    }
    if (p.colour_confidence === 'low') {
      const d = document.createElement('span');
      d.className = 'dot';
      d.title = 'colour read with low confidence';
      cell.appendChild(d);
    }
    const flag = p.recoloured ? 'simulated' : p.local ? 'new' : p.parent_id ? 'cut'
      : (!p.clean && !isReviewed(p, S.choices)) ? 'unreviewed'
      : p.asset_quality === 'weak' ? 'weak' : '';
    if (pics.length > 1) {
      const b = document.createElement('button');
      b.className = 'pic-flip';
      b.dataset.pic = p.product_id;
      b.title = 'Show another picture of this product';
      b.textContent = `${(shown ?? p.primary ?? 0) + 1}/${pics.length}`;
      cell.appendChild(b);
    }
    if (flag) {
      const w = document.createElement('span');
      w.className = 'weak'; w.textContent = flag;
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

function renderReviewBadge() {
  const pending = S.products.filter((p) => !p.clean && p.full && !isReviewed(p, S.choices)).length;
  $('reviewBadge').textContent = pending ? String(pending) : '';
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
  const pool = filterProducts(S.products, { ...S.filters, weight: '', formality: '' }, S.choices);
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
        readFilters(); renderSlotBar(); renderShelf(); setView('grid');
      });
      g.appendChild(c);
    }
  }
}

function setView(v) {
  S.view = v;
  $('shelfPane').classList.toggle('hidden', v !== 'grid');
  $('matrix').classList.toggle('hidden', v !== 'matrix');
  $('review').classList.toggle('hidden', v !== 'review');
  document.querySelectorAll('.tab').forEach((t) => t.classList.toggle('on', t.dataset.view === v));
  if (v === 'matrix') renderMatrix();
  if (v === 'review') S.review.render();
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

function frameStyles(d, m) {
  const f = S.board.frame || M.DEFAULT_FRAME;
  d.style.padding = f.mat ? `${m.mat}px` : '0';
  d.style.background = f.mat ? '#ffffff' : 'transparent';
  d.style.borderColor = f.border ? M.KEYLINE : 'transparent';
  const r = (f.radius || 0) * ($('stage').clientWidth / 1080);
  d.style.borderRadius = `${r}px`;
  d.style.overflow = 'hidden';
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
    const framed = isTile(el.kind, p?.asset_type, el.variant, el.base);
    const d = document.createElement('div');
    d.className = `el ${framed ? 'tile' : 'cut'}${S.selected === el.uid ? ' sel' : ''}`;
    d.dataset.uid = el.uid;
    d.style.left = `${el.x * 100}%`;
    d.style.top = `${el.y * 100}%`;
    d.style.width = `${el.w * 100}%`;
    d.style.aspectRatio = String(el.aspect || 1);
    d.style.zIndex = String(el.z);
    d.style.transform = `translate(-50%,-50%) rotate(${el.rot || 0}deg) scaleX(${el.flip ? -1 : 1})`;
    if (framed) frameStyles(d, m);
    const img = document.createElement('img');
    img.alt = '';
    img.draggable = false;
    if (el.crop && p) {
      // a crop of the full photo: the image sits inside a clipping box
      const wrap = document.createElement('div');
      wrap.className = 'cropwrap';
      const l = M.cropLayout(el.crop);
      img.src = X.elementUrl(S.source, p, el);
      img.style.width = `${l.imgW * 100}%`;
      img.style.height = `${l.imgH * 100}%`;
      img.style.left = `${l.left * 100}%`;
      img.style.top = `${l.top * 100}%`;
      wrap.appendChild(img);
      d.appendChild(wrap);
    } else {
      img.src = p ? S.source.assetUrl(p) : (insp ? S.source.inspirationUrl(insp) : '');
      d.appendChild(img);
    }
    if (S.selected === el.uid) addHandles(d, el.uid);
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
  showPictureButton(S.selected);
  renderPieceSlots();
  autosave();
}

function addHandles(d, uid) {
  for (const k of ['resize', 'rotate']) {
    const h = document.createElement('div');
    h.className = `handle ${k}`;
    h.dataset.handle = k;
    h.dataset.uid = uid;
    h.textContent = k === 'resize' ? '⤡' : '⟳';
    d.appendChild(h);
  }
}

function renderHelpers() {
  const list = M.slotChecklist(S.board, S.productsById);
  const sl = $('slotList');
  sl.replaceChildren();
  for (const s of list) {
    const c = document.createElement('button');
    c.className = 'slot-chip' + (s.count ? ' has' : '') + (S.filters.slot === s.slot ? ' filtering' : '');
    c.textContent = s.count ? `${s.slot} ${s.count > 1 ? `×${s.count}` : ''}`.trim() : s.slot;
    c.title = `Show ${s.slot} on the shelf`;
    c.addEventListener('click', () => setSlot(s.slot));
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

/** What the shelf places for a product: its cut-out, or the crop she chose. */
/**
 * Show a piece with another of its pictures, keeping where it sits and how big
 * it is. A product page that held a flat lay and a shot on the model is two
 * pictures of one thing; which one belongs on the board is a styling decision,
 * not a cataloguing one.
 */
function nextPicture(el) {
  const p = S.productsById[el.product_id];
  const pics = X_pictures(p);
  if (!pics.length) return;
  const at = pics.findIndex((q) => q.i === (el.image || 0));
  const next = pics[(at + 1 + pics.length) % pics.length];
  el.image = next.i;
  el.base = next.entry.whole ? 'whole' : 'photo';
  el.variant = next.entry.whole ? 'whole' : 'full';
  el.crop = [0, 0, 1, 1];
  const a = M.shownAspect(p, el.variant, el.crop, el.image, el.base);
  if (a) el.aspect = a;                    // the width the stylist set is kept
}

/**
 * Set a piece's slot from the desk. It goes into the choices, so it travels in
 * asset-choices.json and the build writes it to the catalogue as `given` — the
 * stylist looking at the garment is a better authority than anything inferred
 * from a caption or inherited from the row a product was split out of.
 */
function setPieceSlot(pid, slot) {
  if (!pid || !slot) return;
  const c = S.choices[pid] || {};
  S.choices[pid] = { ...c, slot: c.slot === slot ? '' : slot };
  saveChoices(S.choices);
  refreshDerived();
  renderSlotBar(); renderShelf(); renderPieceSlots(); renderHelpers();
  if (S.review) S.review.render();
  toast(`${pid} · ${S.choices[pid].slot || 'no slot'}`, 1600);
}

function renderPieceSlots() {
  const bar = $('pieceSlots');
  const el = S.selected ? M.byId(S.board, S.selected) : null;
  const p = el && el.kind === 'product' ? S.productsById[el.product_id] : null;
  bar.hidden = !p;
  if (!p) return;
  bar.replaceChildren();
  const lab = document.createElement('span');
  lab.className = 'hint-inline';
  lab.textContent = 'slot';
  bar.appendChild(lab);
  for (const slot of SLOT_PICK) {
    const b = document.createElement('button');
    b.className = 'ghost small' + (p.slot === slot ? ' on' : '');
    b.dataset.act = 'slot';
    b.dataset.slot = slot;
    b.textContent = slot;
    bar.appendChild(b);
  }
}

function showPictureButton(uid) {
  const el = uid ? M.byId(S.board, uid) : null;
  $('elPicture').hidden = !(el && el.kind === 'product'
    && X_pictures(S.productsById[el.product_id]).length > 1);
}

const X_pictures = (p) => {
  const all = (p && p.images) || [];
  const keep = all.map((e, i) => ({ i, type: e.type || 'whole page', entry: e }))
    .filter((x) => !isDetail(x.entry));
  return keep.length > 1 ? keep : [];
};

function placement(p) {
  const c = effectiveChoice(p, S.choices);
  const box = choiceBox(p, c);
  const image = (c && c.image) || p.image || 0;
  const base = c ? choiceBase(c) : 'photo';
  if (box) {
    return { variant: c.choice, crop: box, image, base,
      aspect: M.shownAspect(p, c.choice, box, image, base) };
  }
  // a whole cut-out with no box is placed as it is, like the catalogue's own
  if (c && c.choice === 'whole') {
    return { variant: 'whole', crop: [0, 0, 1, 1], image, base: 'whole',
      aspect: M.shownAspect(p, 'whole', [0, 0, 1, 1], image, 'whole') };
  }
  return { variant: 'cutout', crop: null, image: 0, base: 'photo', aspect: null };
}

async function placeProduct(pid, x, y) {
  const p = S.productsById[pid];
  if (!p) return;
  M.commit(S.history, S.board);
  const pl = placement(p);
  const aspect = pl.aspect || await aspectOf(S.source.thumbUrl(p));
  const el = M.addElement(S.board, {
    kind: 'product', product_id: pid, x: clamp01(x), y: clamp01(y),
    w: defaultWidth(p.slot), aspect, variant: pl.variant, crop: pl.crop, image: pl.image,
    base: pl.base,
  });
  renderBoard();
  return el;
}

/** A tap adds the piece to the middle, each new one a little further along. */
async function placeByTap(pid) {
  const k = S.taps++ % 6;
  return placeProduct(pid, 0.5 + (k - 2.5) * 0.035, 0.5 + (k - 2.5) * 0.03);
}

async function placeInspiration(iid) {
  const insp = S.inspById[iid];
  M.commit(S.history, S.board);
  S.board.elements = S.board.elements.filter((e) => e.kind !== 'inspiration');
  S.board.inspiration = iid || null;
  if (insp) {
    const aspect = await aspectOf(S.source.inspirationThumbUrl(insp));
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
const pointers = new Map();          // active pointers on the stage, for pinch

function stagePoint(ev) {
  const r = $('stage').getBoundingClientRect();
  return { x: (ev.clientX - r.left) / r.width, y: (ev.clientY - r.top) / r.height, r };
}

// The shelf: a vertical swipe scrolls (the browser's pan-y), a tap adds to the
// middle, a long press or a mostly sideways drag picks the piece up.
function onShelfDown(ev) {
  const cell = ev.target.closest('.cell');
  if (!cell) return;
  const pid = cell.dataset.pid;
  if (!S.productsById[pid]) return;
  drag = { type: 'shelf', pid, cell, x0: ev.clientX, y0: ev.clientY, lifted: false,
    pointerId: ev.pointerId, timer: 0 };
  drag.timer = setTimeout(() => { if (drag && drag.type === 'shelf' && !drag.lifted) lift(ev); }, LONG_PRESS_MS);
}

function lift(ev) {
  const d = drag;
  if (!d || d.lifted) return;
  d.lifted = true;
  clearTimeout(d.timer);
  const p = S.productsById[d.pid];
  const g = $('drag');
  g.replaceChildren();
  const img = document.createElement('img');
  img.src = S.source.thumbUrl(p);
  g.appendChild(img);
  g.style.left = `${ev.clientX}px`;
  g.style.top = `${ev.clientY}px`;
  g.hidden = false;
  d.cell.classList.add('lifting');
  try { d.cell.setPointerCapture(d.pointerId); } catch (e) { /* touch already panning */ }
}

function onShelfMove(ev) {
  if (!drag || drag.type !== 'shelf') return;
  if (!drag.lifted) {
    const dx = ev.clientX - drag.x0, dy = ev.clientY - drag.y0;
    if (Math.abs(dx) > SIDEWAYS_PX && Math.abs(dx) > Math.abs(dy) * 1.2) lift(ev);
    else if (Math.abs(dy) > SIDEWAYS_PX) { clearTimeout(drag.timer); drag.scrolling = true; }
    return;
  }
  ev.preventDefault();
  const g = $('drag');
  g.style.left = `${ev.clientX}px`;
  g.style.top = `${ev.clientY}px`;
}

async function onShelfUp(ev) {
  if (!drag || drag.type !== 'shelf') return;
  const d = drag;
  drag = null;
  clearTimeout(d.timer);
  d.cell.classList.remove('lifting');
  $('drag').hidden = true;
  if (d.lifted) {
    const r = $('stage').getBoundingClientRect();
    const inside = ev.clientX >= r.left && ev.clientX <= r.right
      && ev.clientY >= r.top && ev.clientY <= r.bottom;
    if (inside) await placeProduct(d.pid, (ev.clientX - r.left) / r.width, (ev.clientY - r.top) / r.height);
  } else if (!d.scrolling) {
    await placeByTap(d.pid);
  }
}

function onShelfCancel() {
  if (drag && drag.type === 'shelf') {           // the browser took the swipe: a scroll
    clearTimeout(drag.timer);
    drag.cell.classList.remove('lifting');
    drag = null;
    $('drag').hidden = true;
  }
}

function onStageDown(ev) {
  pointers.set(ev.pointerId, { x: ev.clientX, y: ev.clientY });
  const handle = ev.target.closest('.handle');
  const elDiv = ev.target.closest('.el');
  const pt = stagePoint(ev);
  // Without this the browser starts its own image drag on the first move and
  // sends pointercancel, which ends the gesture after a single frame.
  if (handle || elDiv) ev.preventDefault();
  if (pointers.size === 2 && S.selected) {       // second finger: pinch the selected piece
    const el = M.byId(S.board, S.selected);
    const [a, b] = [...pointers.values()];
    M.commit(S.history, S.board);
    drag = { type: 'pinch', uid: el.uid, d0: Math.hypot(b.x - a.x, b.y - a.y),
      a0: Math.atan2(b.y - a.y, b.x - a.x), w0: el.w, rot0: el.rot || 0 };
    capture(ev);
    return;
  }
  if (handle) {
    const el = M.byId(S.board, handle.dataset.uid);
    M.commit(S.history, S.board);
    drag = { type: handle.dataset.handle, uid: el.uid, start: pt, w0: el.w, rot0: el.rot || 0 };
    capture(ev);
    return;
  }
  if (!elDiv) { setSelection(null); return; }
  const el = M.byId(S.board, elDiv.dataset.uid);
  setSelection(el.uid);
  M.commit(S.history, S.board);
  drag = { type: 'move', uid: el.uid, dx: el.x - pt.x, dy: el.y - pt.y };
  capture(ev);
}

/** Capture is a courtesy, not a requirement: a touch can end before it lands. */
function capture(ev) {
  try { $('stage').setPointerCapture(ev.pointerId); } catch (e) { /* fine */ }
}

function onStageMove(ev) {
  if (pointers.has(ev.pointerId)) pointers.set(ev.pointerId, { x: ev.clientX, y: ev.clientY });
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
  } else if (drag.type === 'pinch' && pointers.size >= 2) {
    const [a, b] = [...pointers.values()];
    const d1 = Math.hypot(b.x - a.x, b.y - a.y);
    const a1 = Math.atan2(b.y - a.y, b.x - a.x);
    el.w = Math.min(2.2, Math.max(0.04, drag.w0 * (d1 / Math.max(1, drag.d0))));
    el.rot = Math.round((drag.rot0 + ((a1 - drag.a0) * 180) / Math.PI) * 10) / 10;
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

function onStageUp(ev) {
  pointers.delete(ev.pointerId);
  if (drag && drag.type === 'pinch' && pointers.size >= 1) return;   // one finger still down
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
  if (d) { d.classList.add('sel'); addHandles(d, uid); }
  $('elementBar').hidden = !uid;
  showPictureButton(uid);
  renderPieceSlots();
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

async function exportChoices() {
  const file = new File([JSON.stringify(choicesFile(S.choices), null, 1)], 'asset-choices.json',
    { type: 'application/json' });
  const how = await X.handOver([file], { title: 'asset-choices.json' });
  toast(how === 'shared' ? 'Choices sent to the share sheet.' : how === 'cancelled' ? 'Cancelled.'
    : 'asset-choices.json downloaded. Put it in content/catalogue/.');
}

async function openInfo(text) {
  const info = JSON.parse(text);
  if (info.kind !== 'relatively-normal.outfit') throw new Error('not an outfit file');
  M.commit(S.history, S.board);
  const b = M.createBoard(info.format || 'portrait');
  b.title = info.title || '';
  b.line = info.line || '';
  b.ground = info.canvas?.ground || M.GROUND;
  b.frame = { ...M.DEFAULT_FRAME, ...(info.canvas?.frame || S.settings.frame) };
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
      aspect: pl.aspect || 1, variant: p.image_variant || 'cutout', crop: p.image_crop || null,
      image: p.image_index || 0, base: p.image_base || 'photo' });
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
  if (!raw) { S.board.frame = { ...S.settings.frame }; return; }
  try {
    const b = JSON.parse(raw);
    if (b && Array.isArray(b.elements)) {
      b.elements = b.elements.filter((e) => e.kind === 'inspiration'
        ? !!S.inspById[e.inspiration_id] : !!S.productsById[e.product_id]);
      S.board = { ...M.createBoard(b.format || 'portrait'), ...b };
      S.board.frame = { ...M.DEFAULT_FRAME, ...(b.frame || S.settings.frame) };
    }
  } catch (e) { /* corrupt or from an older version: start clean */ }
}

function loadSettings() {
  try {
    const s = JSON.parse(localStorage.getItem(SETTINGS) || '{}');
    if (s && s.frame) S.settings.frame = { ...M.DEFAULT_FRAME, ...s.frame };
  } catch (e) { /* defaults */ }
}

function saveSettings() {
  try { localStorage.setItem(SETTINGS, JSON.stringify(S.settings)); } catch (e) { /* fine */ }
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
  const f = S.board.frame || M.DEFAULT_FRAME;
  $('frBorder').checked = !!f.border;
  $('frMat').checked = !!f.mat;
  $('frRadius').value = String(f.radius || 0);
}

function wire() {
  syncControls();
  $('fMatch').disabled = !S.board.inspiration;

  for (const id of ['fFamily', 'fWeight', 'fFormality', 'fAsset', 'fBrand', 'fUnreviewed', 'fMatch']) {
    $(id).addEventListener('change', () => { readFilters(); renderSlotBar(); renderShelf(); if (S.view === 'matrix') renderMatrix(); });
  }
  let t;
  $('search').addEventListener('input', () => {
    clearTimeout(t);
    t = setTimeout(() => { readFilters(); renderSlotBar(); renderShelf(); }, 140);
  });
  $('clearFilters').addEventListener('click', () => {
    for (const id of ['fFamily', 'fWeight', 'fFormality', 'fAsset', 'fBrand']) $(id).value = '';
    $('search').value = ''; $('fUnreviewed').checked = false; $('fMatch').checked = false;
    readFilters(); S.filters.slot = ''; renderSlotBar(); renderShelf(); renderMatrix(); renderHelpers();
  });
  document.querySelectorAll('.tab').forEach((b) => b.addEventListener('click', () => setView(b.dataset.view)));
  $('toggleShelf').addEventListener('click', () => {
    $('shelf').classList.toggle('hidden');
    requestAnimationFrame(() => { layoutStage(); renderBoard(); });
  });
  $('exportChoices').addEventListener('click', exportChoices);

  // shelf gestures
  const grid = $('grid');
  grid.addEventListener('pointerdown', onShelfDown);
  grid.addEventListener('pointermove', onShelfMove);
  grid.addEventListener('pointerup', onShelfUp);
  grid.addEventListener('pointercancel', onShelfCancel);
  grid.addEventListener('contextmenu', (e) => e.preventDefault());

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
    if (act === 'picture' && el) nextPicture(el);
    if (act === 'slot' && el) {
      setPieceSlot(el.product_id, ev.target.dataset.slot);
      return;                                 // the board did not change, the shelf did
    }
    if (act === 'duplicate') { const d = M.duplicateElement(S.board, S.selected); if (d) S.selected = d.uid; }
    if (act === 'delete') { M.removeElement(S.board, S.selected); S.selected = null; }
    renderBoard();
  });

  $('grid').addEventListener('click', (ev) => {
    const b = ev.target.closest('[data-pic]');
    if (!b) return;
    ev.stopPropagation();
    const p = S.productsById[b.dataset.pic];
    if (!p) return;
    const pics = X_pictures(p);
    if (!pics.length) return;
    const at = pics.findIndex((q) => q.i === (S.shelfPicture[p.product_id] ?? p.primary ?? 0));
    S.shelfPicture[p.product_id] = pics[(at + 1 + pics.length) % pics.length].i;
    renderShelf();
  });

  $('pieceSlots').addEventListener('click', (ev) => {
    const b = ev.target.closest('[data-slot]');
    if (!b || !S.selected) return;
    const el = M.byId(S.board, S.selected);
    if (el && el.kind === 'product') setPieceSlot(el.product_id, b.dataset.slot);
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

  // the frame setting: one for the board, remembered as the default for the next
  $('frameBtn').addEventListener('click', () => $('framePop').classList.toggle('hidden'));
  const readFrame = () => {
    S.board.frame = { border: $('frBorder').checked, mat: $('frMat').checked,
      radius: Number($('frRadius').value) || 0 };
    S.settings.frame = { ...S.board.frame };
    saveSettings();
    renderBoard();
  };
  for (const id of ['frBorder', 'frMat', 'frRadius']) $(id).addEventListener('change', readFrame);

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
    S.board.frame = { ...S.settings.frame };
    S.selected = null;
    S.taps = 0;
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
Object.assign(S, { placeProduct, placeByTap, placeInspiration, renderShelf, renderBoard, save, openInfo,
  setSlot, setView, exportChoices, saveChoices: () => saveChoices(S.choices),
  buildInfo: () => X.buildInfo(S.board, S.productsById, S.inspById),
  renderCanvas: async () => {
    const images = await X.loadBoardImages(S.board, S.source, S.productsById, S.inspById);
    return X.renderBoardCanvas(S.board, S.productsById, images, 1);
  } });
