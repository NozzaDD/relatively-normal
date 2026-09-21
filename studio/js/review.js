// The Review tab: decide what goes on the shelf, one product at a time.
//
// Every product that is not a clean flat cut-out is shown four ways — the
// cut-out, a box around the item, a box around the whole person, the full
// photo — and the stylist taps one, draws her own box, hides it, or leaves it
// for later. Choices apply at once in the browser and can be exported for the
// build script. Nothing here deletes anything.

import { cropLayout, SLOT_ORDER } from './model.js';
import { isReviewed, effectiveChoice } from './data.js';

const STORE = 'rn.studio.choices.v1';
const $ = (id) => document.getElementById(id);

export function loadChoices() {
  try {
    const raw = localStorage.getItem(STORE);
    const c = raw ? JSON.parse(raw) : {};
    return c && typeof c === 'object' ? c : {};
  } catch (e) { return {}; }
}

export function saveChoices(choices) {
  try { localStorage.setItem(STORE, JSON.stringify(choices)); } catch (e) { /* fine */ }
}

/** The file the build script reads: content/catalogue/asset-choices.json */
export function choicesFile(choices) {
  const out = {};
  for (const [pid, c] of Object.entries(choices)) {
    if (c.hidden) out[pid] = { hidden: true };
    else if (c.choice) out[pid] = { choice: c.choice, ...(c.box ? { box: c.box.map((v) => Math.round(v * 1e4) / 1e4) } : {}) };
  }
  return { kind: 'relatively-normal.asset-choices', version: 1,
    exported: new Date().toISOString().slice(0, 10), choices: out };
}

/** The box a choice means, as [x, y, w, h] of the full image, or null for the cut-out. */
export function choiceBox(p, c) {
  if (!c || !c.choice || c.choice === 'cutout' || !p.full) return null;
  if (c.choice === 'full') return [0, 0, 1, 1];
  if (c.choice === 'custom') return c.box || null;
  return p.boxes?.[c.choice] || null;
}

/** Style an <img> inside a box so only `crop` of it shows, fitted to the box. */
export function applyCrop(img, crop, boxW, boxH, fullW, fullH) {
  const [, , cw, ch] = crop;
  const aspect = (cw * fullW) / (ch * fullH);
  let dw = boxW, dh = boxW / aspect;
  if (dh > boxH) { dh = boxH; dw = boxH * aspect; }
  const l = cropLayout(crop);
  img.style.position = 'absolute';
  img.style.width = `${dw * l.imgW}px`;
  img.style.height = `${dh * l.imgH}px`;
  img.style.left = `${(boxW - dw) / 2 + dw * l.left}px`;
  img.style.top = `${(boxH - dh) / 2 + dh * l.top}px`;
  img.style.maxWidth = 'none';
}

// ---------------------------------------------------------------- the tab
export function createReview(api) {
  // api: { source, products(), choices, onChange(), toast() }
  const state = { slot: '', adjusting: null };

  function pending(list) {
    return list.filter((p) => !p.clean && p.full);
  }

  function render() {
    const root = $('review');
    const all = pending(api.products());
    const list = state.slot ? all.filter((p) => p.slot === state.slot) : all;
    const done = list.filter((p) => isReviewed(p, api.choices)).length;
    const later = list.filter((p) => api.choices[p.product_id]?.later && !isReviewed(p, api.choices)).length;
    $('reviewProgress').textContent = `${done} of ${list.length} decided${later ? `, ${later} for later` : ''}`;
    const bar = $('reviewSlots');
    bar.replaceChildren();
    for (const s of ['', ...SLOT_ORDER, 'multiple', 'base']) {
      const n = s ? all.filter((p) => p.slot === s).length : all.length;
      if (s && !n) continue;
      const b = document.createElement('button');
      b.className = 'chip' + (state.slot === s ? ' on' : '');
      b.textContent = `${s || 'all'} ${n}`;
      b.addEventListener('click', () => { state.slot = s; render(); });
      bar.appendChild(b);
    }
    const cards = $('reviewCards');
    cards.replaceChildren();
    const todo = list.filter((p) => !isReviewed(p, api.choices));
    const doneList = list.filter((p) => isReviewed(p, api.choices));
    for (const p of [...todo, ...doneList]) cards.appendChild(card(p));
  }

  function version(p, kind, label) {
    const box = kind === 'cutout' ? null : kind === 'full' ? [0, 0, 1, 1] : p.boxes[kind];
    const v = document.createElement('button');
    v.className = 'version';
    v.dataset.kind = kind;
    const frame = document.createElement('div');
    frame.className = 'vframe';
    const img = document.createElement('img');
    img.loading = 'lazy';
    img.alt = label;
    if (box) {
      img.src = api.source.fullUrl(p);
      img.onload = () => applyCrop(img, box, 72, 88, p.full.w, p.full.h);
    } else {
      img.src = api.source.thumbUrl(p);
      img.className = 'contain';
    }
    frame.appendChild(img);
    v.appendChild(frame);
    const t = document.createElement('span');
    t.textContent = label;
    v.appendChild(t);
    return v;
  }

  function card(p) {
    const c = api.choices[p.product_id] || {};
    const eff = effectiveChoice(p, api.choices);
    const el = document.createElement('div');
    el.className = 'rcard' + (eff?.hidden ? ' hidden-card' : eff?.choice ? ' decided' : '');
    el.dataset.pid = p.product_id;
    const head = document.createElement('div');
    head.className = 'rhead';
    head.textContent = `${p.product_id} · ${p.slot || '—'} · ${[p.brand, p.garment_type].filter(Boolean).join(' · ')}`;
    el.appendChild(head);
    const row = document.createElement('div');
    row.className = 'versions';
    const kinds = [['cutout', 'cut-out'], ['item', 'item box'], ['person', 'person box'], ['full', 'full']];
    for (const [k, label] of kinds) {
      const v = version(p, k, label);
      if (eff?.choice === k) v.classList.add('chosen');
      v.addEventListener('click', () => decide(p, { choice: k, box: null }));
      row.appendChild(v);
    }
    if (eff?.choice === 'custom') {
      const v = version(p, 'full', 'my box');
      v.classList.add('chosen');
      const img = v.querySelector('img');
      img.onload = () => applyCrop(img, eff.box, 72, 88, p.full.w, p.full.h);
      row.appendChild(v);
    }
    el.appendChild(row);
    const acts = document.createElement('div');
    acts.className = 'racts';
    const mk = (label, cls, fn) => {
      const b = document.createElement('button');
      b.className = 'ghost small ' + cls; b.textContent = label;
      b.addEventListener('click', fn);
      acts.appendChild(b);
    };
    mk('Adjust box', '', () => openAdjust(p));
    mk(eff?.hidden ? 'Unhide' : 'Hide', 'danger', () => decide(p, eff?.hidden ? { hidden: false } : { hidden: true, choice: null }));
    mk('Later', '', () => { api.choices[p.product_id] = { ...c, later: true }; saveChoices(api.choices); render(); });
    if (eff && !eff.hidden && eff.choice) mk('Undo choice', '', () => { delete api.choices[p.product_id]; saveChoices(api.choices); api.onChange(); render(); });
    el.appendChild(acts);
    return el;
  }

  function decide(p, patch) {
    const prev = api.choices[p.product_id] || {};
    api.choices[p.product_id] = { ...prev, later: false, ...patch };
    saveChoices(api.choices);
    api.onChange();
    render();
  }

  // ------------------------------------------------- draw your own rectangle
  function openAdjust(p) {
    const m = $('adjust');
    const wrap = $('adjustWrap');
    wrap.replaceChildren();
    const img = document.createElement('img');
    img.src = api.source.fullUrl(p);
    img.draggable = false;
    wrap.appendChild(img);
    const box = document.createElement('div');
    box.className = 'adjust-box';
    wrap.appendChild(box);
    const eff = effectiveChoice(p, api.choices);
    let rect = choiceBox(p, eff) || p.boxes?.item || [0.1, 0.1, 0.8, 0.8];
    const paint = () => {
      box.style.left = `${rect[0] * 100}%`; box.style.top = `${rect[1] * 100}%`;
      box.style.width = `${rect[2] * 100}%`; box.style.height = `${rect[3] * 100}%`;
    };
    paint();
    let drag = null;
    const pt = (ev) => {
      const r = img.getBoundingClientRect();
      return [Math.min(1, Math.max(0, (ev.clientX - r.left) / r.width)),
        Math.min(1, Math.max(0, (ev.clientY - r.top) / r.height))];
    };
    wrap.onpointerdown = (ev) => {
      ev.preventDefault();
      const [x, y] = pt(ev);
      const inside = x >= rect[0] && x <= rect[0] + rect[2] && y >= rect[1] && y <= rect[1] + rect[3];
      const nearCorner = Math.abs(x - (rect[0] + rect[2])) < 0.06 && Math.abs(y - (rect[1] + rect[3])) < 0.06;
      // a rectangle that is the whole photo cannot be moved anywhere, so a drag
      // on it draws a new one instead
      const whole = rect[2] > 0.95 && rect[3] > 0.95;
      drag = nearCorner && !whole ? { mode: 'resize' } : inside && !whole ? { mode: 'move', dx: x - rect[0], dy: y - rect[1] }
        : { mode: 'new', x0: x, y0: y };
      if (drag.mode === 'new') rect = [x, y, 0.001, 0.001];
      try { wrap.setPointerCapture(ev.pointerId); } catch (e) { /* pointer already gone */ }
    };
    wrap.onpointermove = (ev) => {
      if (!drag) return;
      const [x, y] = pt(ev);
      if (drag.mode === 'move') {
        rect = [Math.min(1 - rect[2], Math.max(0, x - drag.dx)), Math.min(1 - rect[3], Math.max(0, y - drag.dy)), rect[2], rect[3]];
      } else if (drag.mode === 'resize') {
        rect = [rect[0], rect[1], Math.max(0.03, x - rect[0]), Math.max(0.03, y - rect[1])];
      } else {
        rect = [Math.min(drag.x0, x), Math.min(drag.y0, y), Math.max(0.03, Math.abs(x - drag.x0)), Math.max(0.03, Math.abs(y - drag.y0))];
      }
      paint();
    };
    wrap.onpointerup = () => { drag = null; };
    $('adjustUse').onclick = () => {
      decide(p, { choice: 'custom', box: rect.map((v) => Math.round(v * 1e4) / 1e4) });
      m.classList.add('hidden');
    };
    $('adjustCancel').onclick = () => m.classList.add('hidden');
    m.classList.remove('hidden');
  }

  return { render, state };
}
