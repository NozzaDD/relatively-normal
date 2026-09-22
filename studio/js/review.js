// The Review tab: decide what goes on the shelf, one product at a time.
//
// Every product that is not a clean flat cut-out is shown four ways — the
// cut-out, a box around the item, a box around the whole person, the full
// photo — and the stylist taps one, draws her own box, hides it, or leaves it
// for later. Choices apply at once in the browser and can be exported for the
// build script. Nothing here deletes anything.

import { cropLayout, SLOT_ORDER } from './model.js';
import { isReviewed, effectiveChoice, imageEntry, splitId } from './data.js';

/** Every screenshot of a product the desk can draw on, best first. */
export function productImages(p) {
  if (p.images && p.images.length) return p.images;
  const e = imageEntry(p, 0);
  return e ? [e] : [];
}

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
    let e = null;
    if (c.hidden) e = { hidden: true };
    else if (c.choice) e = { choice: c.choice, ...(c.box ? { box: c.box.map((v) => Math.round(v * 1e4) / 1e4) } : {}),
      ...(c.image ? { image: c.image } : {}) };
    const splits = (c.splits || []).filter((s) => s.box && s.n).map((s) => ({
      n: s.n, image: s.image || 0, box: s.box.map((v) => Math.round(v * 1e4) / 1e4),
      slot: s.slot || '', colour_name: s.colour_name || '' }));
    if (splits.length) e = { ...(e || {}), splits };
    if (e) out[pid] = e;
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
    return list.filter((p) => !p.clean && p.full && !p.parent_id);
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
    const box = kind === 'cutout' ? null : kind === 'full' ? [0, 0, 1, 1] : (p.boxes && p.boxes[kind]) || [0, 0, 1, 1];
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
    const nimg = productImages(p).length;
    head.textContent = `${p.product_id} · ${p.slot || '—'} · ${[p.brand, p.garment_type].filter(Boolean).join(' · ')}`
      + (nimg > 1 ? ` · ${nimg} images` : '');
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
      const ie = imageEntry(p, eff.image || 0) || p.full;
      const img = v.querySelector('img');
      img.src = api.source.fullUrl(p, eff.image || 0);
      img.onload = () => applyCrop(img, eff.box, 72, 88, ie.w, ie.h);
      row.appendChild(v);
    }
    const nsplit = (c.splits || []).length;
    if (nsplit) {
      const t = document.createElement('span');
      t.className = 'count';
      t.textContent = `${nsplit} cut out`;
      row.appendChild(t);
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

  // ------------------------------------- draw your own boxes, on any screenshot
  //
  // A product may have several screenshots; the stylist swipes to the one she
  // wants and draws on it. One box is the product's own image (the main box);
  // any further boxes are pieces cut out of the same image, each with a slot
  // and an optional colour name, and each becomes a product of its own.
  function openAdjust(p) {
    const m = $('adjust');
    const wrap = $('adjustWrap');
    const imgs = productImages(p);
    if (!imgs.length) { api.toast('No screenshot to draw on.'); return; }
    const prev = api.choices[p.product_id] || {};
    const eff = effectiveChoice(p, api.choices);
    const mainBox = choiceBox(p, eff);
    const st = {
      cur: Math.min(imgs.length - 1, (eff && eff.image) || 0),
      main: mainBox && eff.choice === 'custom' ? { image: (eff.image || 0), rect: [...mainBox] }
        : mainBox ? { image: 0, rect: [...mainBox] } : null,
      splits: (prev.splits || []).map((s) => ({ ...s, rect: [...s.box] })),
      sel: null,            // {kind:'main'} | {kind:'split', i}
      arm: false,           // next drag draws a new box whatever it starts on
      drag: null,
    };
    let img = null;

    const boxesOn = (i) => [
      ...(st.main && st.main.image === i ? [{ kind: 'main', rect: st.main.rect }] : []),
      ...st.splits.map((s, k) => ({ kind: 'split', i: k, rect: s.rect, s })).filter((b) => (b.s.image || 0) === i),
    ];
    const selected = () => {
      if (!st.sel) return null;
      if (st.sel.kind === 'main') return st.main ? { kind: 'main', rect: st.main.rect } : null;
      const s = st.splits[st.sel.i];
      return s ? { kind: 'split', i: st.sel.i, rect: s.rect, s } : null;
    };
    const nextN = () => st.splits.reduce((m2, s) => Math.max(m2, s.n || 0), 0) + 1;

    function showImage() {
      wrap.replaceChildren();
      img = document.createElement('img');
      img.src = api.source.fullUrl(p, st.cur);
      img.draggable = false;
      wrap.appendChild(img);
      const e = imgs[st.cur];
      $('adjCounter').textContent = `${st.cur + 1} of ${imgs.length}`;
      $('adjPrev').disabled = st.cur === 0;
      $('adjNext').disabled = st.cur === imgs.length - 1;
      $('adjSuggest').hidden = !(e.suggested && e.suggested.length);
      $('adjSuggest').textContent = e.suggested?.length ? `Suggested boxes (${e.suggested.length})` : '';
      $('adjUseImage').classList.toggle('on', !!st.main && st.main.image === st.cur);
      const strip = $('adjStrip');
      strip.replaceChildren();
      if (imgs.length > 1) {
        imgs.forEach((ie, i) => {
          const t = document.createElement('img');
          t.src = api.source.fullUrl(p, i);
          t.className = i === st.cur ? 'on' : '';
          t.addEventListener('click', () => { st.cur = i; st.sel = null; showImage(); });
          strip.appendChild(t);
        });
      }
      paint();
    }

    function paint() { paintBoxes(); panel(); }

    function paintBoxes() {
      wrap.querySelectorAll('.adjust-box').forEach((d) => d.remove());
      const sel = selected();
      for (const b of boxesOn(st.cur)) {
        const d = document.createElement('div');
        d.className = `adjust-box ${b.kind}`;
        if (sel && sel.kind === b.kind && (b.kind === 'main' || sel.i === b.i)) d.classList.add('sel');
        d.style.left = `${b.rect[0] * 100}%`; d.style.top = `${b.rect[1] * 100}%`;
        d.style.width = `${b.rect[2] * 100}%`; d.style.height = `${b.rect[3] * 100}%`;
        const l = document.createElement('span');
        l.className = 'bl';
        l.textContent = b.kind === 'main' ? 'this product'
          : [`box ${b.i + 1}`, b.s.slot, b.s.colour_name].filter(Boolean).join(' · ');
        d.appendChild(l);
        wrap.appendChild(d);
      }
    }

    function panel() {
      const pn = $('adjPanel');
      pn.replaceChildren();
      const sel = selected();
      const hint = (t) => { const h = document.createElement('span'); h.className = 'hint'; h.textContent = t; pn.appendChild(h); };
      if (!sel) {
        hint(st.arm ? 'Drag on the image to draw a box.'
          : st.main && st.main.image === st.cur ? 'Drag inside a box to move it, its corner to resize, elsewhere to draw a new box.'
          : 'Drag a rectangle around this product, or tap "Use this one" to start from the item box.');
        return;
      }
      if (sel.kind === 'main') {
        hint('This product\'s own image.');
      } else {
        const s = sel.s;
        const lab = document.createElement('span');
        lab.textContent = `Box ${sel.i + 1}:`;
        pn.appendChild(lab);
        const slots = document.createElement('div');
        slots.className = 'slots';
        for (const slot of SLOT_ORDER) {
          const b = document.createElement('button');
          b.className = 'ghost' + (s.slot === slot ? ' on' : '');
          b.textContent = slot;
          b.addEventListener('click', () => { s.slot = slot; paint(); });
          slots.appendChild(b);
        }
        pn.appendChild(slots);
        const inp = document.createElement('input');
        inp.className = 'field';
        inp.placeholder = 'colour name';
        inp.value = s.colour_name || '';
        inp.addEventListener('input', () => { s.colour_name = inp.value; paintBoxes(); });
        pn.appendChild(inp);
      }
      const del = document.createElement('button');
      del.className = 'ghost small danger';
      del.textContent = 'Delete box';
      del.addEventListener('click', () => {
        if (sel.kind === 'main') st.main = null; else st.splits.splice(sel.i, 1);
        st.sel = null; paint();
      });
      pn.appendChild(del);
    }

    const pt = (ev) => {
      const r = img.getBoundingClientRect();
      return [Math.min(1, Math.max(0, (ev.clientX - r.left) / r.width)),
        Math.min(1, Math.max(0, (ev.clientY - r.top) / r.height))];
    };
    const hit = (x, y) => {
      const list = boxesOn(st.cur).reverse();      // topmost first
      return list.find((b) => x >= b.rect[0] && x <= b.rect[0] + b.rect[2] && y >= b.rect[1] && y <= b.rect[1] + b.rect[3]) || null;
    };

    wrap.onpointerdown = (ev) => {
      ev.preventDefault();
      const [x, y] = pt(ev);
      const h = st.arm ? null : hit(x, y);
      if (h) {
        st.sel = h.kind === 'main' ? { kind: 'main' } : { kind: 'split', i: h.i };
        const r = h.rect;
        const nearCorner = Math.abs(x - (r[0] + r[2])) < 0.06 && Math.abs(y - (r[1] + r[3])) < 0.06;
        const whole = r[2] > 0.95 && r[3] > 0.95;
        st.drag = whole ? { mode: 'new', x0: x, y0: y } : nearCorner ? { mode: 'resize', rect: r }
          : { mode: 'move', rect: r, dx: x - r[0], dy: y - r[1] };
      } else {
        st.drag = { mode: 'new', x0: x, y0: y };
      }
      if (st.drag.mode === 'new') {
        // the first box on an image is the product's own; any later one is a cut
        const rect = [x, y, 0.001, 0.001];
        if (!st.main || (st.main.image !== st.cur && !st.arm && !boxesOn(st.cur).length)) {
          st.main = { image: st.cur, rect };
          st.sel = { kind: 'main' };
        } else {
          st.splits.push({ n: nextN(), image: st.cur, rect, slot: p.slot || '', colour_name: '' });
          st.sel = { kind: 'split', i: st.splits.length - 1 };
        }
        st.drag.rect = rect;
        st.arm = false;
        $('adjAddBox').classList.remove('on');
      }
      try { wrap.setPointerCapture(ev.pointerId); } catch (e) { /* pointer already gone */ }
      paint();
    };
    wrap.onpointermove = (ev) => {
      const d = st.drag;
      if (!d) return;
      const [x, y] = pt(ev);
      const r = d.rect;
      if (d.mode === 'move') {
        r[0] = Math.min(1 - r[2], Math.max(0, x - d.dx)); r[1] = Math.min(1 - r[3], Math.max(0, y - d.dy));
      } else if (d.mode === 'resize') {
        r[2] = Math.max(0.03, x - r[0]); r[3] = Math.max(0.03, y - r[1]);
      } else {
        r[0] = Math.min(d.x0, x); r[1] = Math.min(d.y0, y);
        r[2] = Math.max(0.03, Math.abs(x - d.x0)); r[3] = Math.max(0.03, Math.abs(y - d.y0));
      }
      paintBoxes();
    };
    wrap.onpointerup = () => { st.drag = null; };

    $('adjPrev').onclick = () => { if (st.cur > 0) { st.cur--; st.sel = null; showImage(); } };
    $('adjNext').onclick = () => { if (st.cur < imgs.length - 1) { st.cur++; st.sel = null; showImage(); } };
    $('adjUseImage').onclick = () => {
      // the product's own box moves to this image, starting from its item box
      const e = imgs[st.cur];
      st.main = { image: st.cur, rect: [...(e.item || [0.1, 0.1, 0.8, 0.8])] };
      st.sel = { kind: 'main' };
      showImage();
    };
    $('adjAddBox').onclick = () => { st.arm = !st.arm; st.sel = null; $('adjAddBox').classList.toggle('on', st.arm); paint(); };
    $('adjSuggest').onclick = () => {
      const e = imgs[st.cur];
      for (const rect of e.suggested || []) {
        st.splits.push({ n: nextN(), image: st.cur, rect: [...rect], slot: p.slot === 'multiple' ? '' : (p.slot || ''), colour_name: '' });
      }
      st.sel = null; paint();
    };
    // swipe on the filmstrip or the bar moves between images
    let sw = null;
    const bar = $('adjStrip');
    bar.onpointerdown = (ev) => { sw = ev.clientX; };
    bar.onpointerup = (ev) => {
      if (sw === null) return;
      const dx = ev.clientX - sw; sw = null;
      if (dx < -40) $('adjNext').click(); else if (dx > 40) $('adjPrev').click();
    };
    $('adjustUse').onclick = () => {
      const r4 = (v) => Math.round(v * 1e4) / 1e4;
      const patch = { splits: st.splits.map((s) => ({ n: s.n, image: s.image || 0, box: s.rect.map(r4),
        slot: s.slot || '', colour_name: (s.colour_name || '').trim() })) };
      if (st.main) Object.assign(patch, { choice: 'custom', box: st.main.rect.map(r4), image: st.main.image || 0 });
      else if (eff?.choice === 'custom') Object.assign(patch, { choice: null, box: null });
      decide(p, patch);
      m.classList.add('hidden');
    };
    $('adjustCancel').onclick = () => m.classList.add('hidden');
    m.classList.remove('hidden');
    showImage();
  }

  return { render, state };
}
