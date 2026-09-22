// The Review tab: decide what goes on the shelf, one product at a time.
//
// Every product that is not a clean flat cut-out is shown four ways — the
// cut-out, a box around the item, a box around the whole person, the full
// photo — and the stylist taps one, draws her own box, hides it, or leaves it
// for later. Choices apply at once in the browser and can be exported for the
// build script. Nothing here deletes anything.

import { cropLayout, SLOT_ORDER } from './model.js';
import { isReviewed, effectiveChoice, imageEntry, splitId, productVersions } from './data.js';

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

/** A box in the old crop's fractions -> the new crop's fractions. */
export function remapBox(box, prev, now) {
  const [px, py, pw, ph] = prev;
  const [nx, ny, nw, nh] = now;
  if (!pw || !ph || !nw || !nh) return box;
  const f = (v, o, s) => Math.min(1, Math.max(0, (v - o) / s));
  const a = f(px + box[0] * pw, nx, nw);
  const b = f(py + box[1] * ph, ny, nh);
  const c = f(px + (box[0] + box[2]) * pw, nx, nw);
  const d = f(py + (box[1] + box[3]) * ph, ny, nh);
  if (c - a < 0.01 || d - b < 0.01) return null;
  return [a, b, c - a, d - b].map((v) => Math.round(v * 1e4) / 1e4);
}

/**
 * Move every box kept in this browser onto the new trim. Work done on the iPad
 * and never exported is worth as much as work in the repository, so it is moved
 * the same way and marked so it is never moved twice.
 */
export function migrateChoices(choices, migration) {
  if (!migration || !migration.products) return 0;
  let moved = 0;
  for (const [pid, c] of Object.entries(choices)) {
    const t = migration.products[pid];
    if (!t || (c.trim || 1) >= migration.trim_version) continue;
    const at = (i) => t[String(i || 0)];
    if (c.box && (c.base || 'photo') === 'photo' && at(c.image)) {
      const nb = remapBox(c.box, at(c.image).prev, at(c.image).now);
      if (nb) { c.box = nb; moved++; } else { delete c.choice; delete c.box; }
    }
    for (const sp of c.splits || []) {
      if ((sp.base || 'photo') !== 'photo' || !sp.box || !at(sp.image)) continue;
      const nb = remapBox(sp.box, at(sp.image).prev, at(sp.image).now);
      if (nb) { sp.box = nb; moved++; } else { sp.box = null; }
    }
    if (c.splits) c.splits = c.splits.filter((s) => s.box);
    c.trim = migration.trim_version;
  }
  return moved;
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
      ...(c.image ? { image: c.image } : {}), ...(c.base && c.base !== 'photo' ? { base: c.base } : {}) };
    const splits = (c.splits || []).filter((s) => s.box && s.n).map((s) => ({
      n: s.n, image: s.image || 0, box: s.box.map((v) => Math.round(v * 1e4) / 1e4),
      slot: s.slot || '', colour_name: s.colour_name || '',
      ...(s.base && s.base !== 'photo' ? { base: s.base } : {}) }));
    if (splits.length) e = { ...(e || {}), splits };
    if (e) out[pid] = e;
  }
  return { kind: 'relatively-normal.asset-choices', version: 1,
    exported: new Date().toISOString().slice(0, 10), choices: out };
}

/**
 * The box a choice means, as [x, y, w, h] of its base image — or null when the
 * version is a whole image with no crop (the cut-out, or a whole cut-out).
 */
export function choiceBox(p, c) {
  if (!c || !c.choice || c.choice === 'cutout' || c.choice === 'whole') return null;
  const e = imageEntry(p, c.image || 0) || p.full;
  if (!e) return null;
  if (c.choice === 'full') return [0, 0, 1, 1];
  if (c.choice === 'custom') return c.box || null;
  return e[c.choice] || p.boxes?.[c.choice] || null;
}

/** Which image a choice is drawn on: the photo, the whole cut-out, or the asset. */
export function choiceBase(c) {
  if (!c || !c.choice) return 'asset';
  if (c.choice === 'cutout') return 'asset';
  if (c.choice === 'whole') return 'whole';
  return c.base === 'whole' ? 'whole' : 'photo';
}

/** The URL of a choice's base image. */
export function baseUrl(source, p, c) {
  const base = choiceBase(c);
  if (base === 'asset') return source.assetUrl(p);
  if (base === 'whole') return source.wholeUrl(p, (c && c.image) || 0) || source.assetUrl(p);
  return source.fullUrl(p, (c && c.image) || 0);
}

/** The size of a choice's base image, for aspect maths. */
export function baseSize(p, c) {
  const e = imageEntry(p, (c && c.image) || 0);
  if (choiceBase(c) === 'whole' && e && e.whole) return { w: e.whole.w, h: e.whole.h };
  if (e) return { w: e.w, h: e.h };
  return p.full || { w: 1, h: 1 };
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
  const state = { slot: '', multi: false, adjusting: null };

  function pending(list) {
    return list.filter((p) => !p.clean && p.full && !p.parent_id);
  }

  function render() {
    const all = pending(api.products());
    let list = state.slot ? all.filter((p) => p.slot === state.slot) : all;
    if (state.multi) list = list.filter((p) => productImages(p).length > 1);
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
    const e = imageEntry(p, 0);
    const box = kind === 'cutout' ? null : kind === 'full' ? [0, 0, 1, 1]
      : (e && e[kind]) || (p.boxes && p.boxes[kind]) || [0, 0, 1, 1];
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
    const who = document.createElement('span');
    who.className = 'rwho';
    who.textContent = `${p.product_id} · ${p.slot || '—'} · ${[p.brand, p.garment_type].filter(Boolean).join(' · ')}`;
    const cnt = document.createElement('span');
    cnt.className = 'rphotos' + (nimg > 1 ? ' many' : '');
    cnt.textContent = `${nimg} photo${nimg === 1 ? '' : 's'}`;
    head.append(who, cnt);
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

  // --------------------------------- draw your own boxes, on any version
  //
  // The filmstrip holds every version of the product: its cut-out, and for
  // each screenshot the whole cut-out, the item box, the person box and the
  // whole photo. Picking one shows the WHOLE image it is drawn on with the box
  // on top, so a crop that cut too much can be widened as well as tightened.
  // Nothing but boxes and their handles is drawn over the picture — the labels
  // live in the header.
  function openAdjust(p) {
    const m = $('adjust');
    const wrap = $('adjustWrap');
    const vers = productVersions(p);
    if (!vers.length) { api.toast('No image to draw on.'); return; }
    const prev = api.choices[p.product_id] || {};
    const eff = effectiveChoice(p, api.choices);
    const startBox = choiceBox(p, eff);
    const st = {
      cur: 0,
      main: startBox ? { image: (eff.image || 0), base: choiceBase(eff), rect: [...startBox] } : null,
      splits: (prev.splits || []).map((x) => ({ ...x, rect: [...x.box] })),
      sel: null,
      arm: false,
      drag: null,
    };
    // open on the version she is already using
    if (eff && eff.choice) {
      const i = vers.findIndex((v) => v.kind === (eff.choice === 'custom' ? 'full' : eff.choice)
        && v.image === (eff.image || 0) && v.base === choiceBase(eff));
      if (i >= 0) st.cur = i;
      else {
        const j = vers.findIndex((v) => v.image === (eff.image || 0) && v.base === choiceBase(eff));
        if (j >= 0) st.cur = j;
      }
    }
    let img = null;
    const V = () => vers[st.cur];
    const sameBase = (v, o) => v.base === (o.base || 'photo') && (v.base === 'asset' || v.image === (o.image || 0));

    const boxesOn = () => {
      const v = V();
      return [
        ...(st.main && sameBase(v, st.main) ? [{ kind: 'main', rect: st.main.rect }] : []),
        ...st.splits.map((x, k) => ({ kind: 'split', i: k, rect: x.rect, s: x }))
          .filter((b) => sameBase(v, b.s)),
      ];
    };
    const selected = () => {
      if (!st.sel) return null;
      if (st.sel.kind === 'main') return st.main ? { kind: 'main', rect: st.main.rect } : null;
      const x = st.splits[st.sel.i];
      return x ? { kind: 'split', i: st.sel.i, rect: x.rect, s: x } : null;
    };
    const nextN = () => st.splits.reduce((m2, x) => Math.max(m2, x.n || 0), 0) + 1;
    const versionUrl = (v) => (v.base === 'asset' ? api.source.assetUrl(p)
      : v.base === 'whole' ? api.source.wholeUrl(p, v.image) : api.source.fullUrl(p, v.image));

    function showImage() {
      const v = V();
      wrap.replaceChildren();
      wrap.classList.toggle('on-ground', v.base !== 'photo');
      img = document.createElement('img');
      img.src = versionUrl(v);
      img.draggable = false;
      wrap.appendChild(img);
      $('adjCounter').textContent = `${st.cur + 1} of ${vers.length}`;
      $('adjVersion').textContent = v.label;
      $('adjPrev').disabled = st.cur === 0;
      $('adjNext').disabled = st.cur === vers.length - 1;
      const e = imageEntry(p, v.image);
      const sug = v.base === 'photo' && e && e.suggested && e.suggested.length;
      $('adjSuggest').hidden = !sug;
      $('adjSuggest').textContent = sug ? `Suggested boxes (${e.suggested.length})` : '';
      $('adjUseImage').classList.toggle('on', !!st.main && sameBase(v, st.main));
      const strip = $('adjStrip');
      strip.replaceChildren();
      vers.forEach((vv, i) => {
        const t = document.createElement('img');
        t.src = versionUrl(vv);
        t.className = i === st.cur ? 'on' : '';
        t.title = vv.label;
        t.addEventListener('click', () => { st.cur = i; st.sel = null; showImage(); });
        strip.appendChild(t);
      });
      paint();
    }

    function paint() { paintBoxes(); panel(); }

    function paintBoxes() {
      wrap.querySelectorAll('.adjust-box').forEach((d) => d.remove());
      const sel = selected();
      for (const b of boxesOn()) {
        const d = document.createElement('div');
        d.className = `adjust-box ${b.kind}`;
        if (sel && sel.kind === b.kind && (b.kind === 'main' || sel.i === b.i)) d.classList.add('sel');
        d.style.left = `${b.rect[0] * 100}%`; d.style.top = `${b.rect[1] * 100}%`;
        d.style.width = `${b.rect[2] * 100}%`; d.style.height = `${b.rect[3] * 100}%`;
        wrap.appendChild(d);                 // no label: nothing over the photo
      }
      const sl = $('adjSelLabel');
      sl.textContent = !sel ? '' : sel.kind === 'main' ? 'this product'
        : ['box ' + (sel.i + 1), sel.s.slot, sel.s.colour_name].filter(Boolean).join(' · ');
      sl.hidden = !sel;
    }

    function panel() {
      const pn = $('adjPanel');
      pn.replaceChildren();
      const sel = selected();
      const hint = (t) => { const h = document.createElement('span'); h.className = 'adj-hint'; h.textContent = t; pn.appendChild(h); };
      if (!sel) {
        hint(st.arm ? 'Drag on the image to draw a box.'
          : 'Drag a rectangle to set this product, or tap "Use this one" to take this version whole.');
        return;
      }
      if (sel.kind === 'main') {
        hint('This product\'s own image. Drag its corner to widen or tighten it.');
      } else {
        const x = sel.s;
        const slots = document.createElement('div');
        slots.className = 'slots';
        for (const slot of SLOT_ORDER) {
          const b = document.createElement('button');
          b.className = 'ghost' + (x.slot === slot ? ' on' : '');
          b.textContent = slot;
          b.addEventListener('click', () => { x.slot = slot; paint(); });
          slots.appendChild(b);
        }
        pn.appendChild(slots);
        const inp = document.createElement('input');
        inp.className = 'field';
        inp.placeholder = 'colour name';
        inp.value = x.colour_name || '';
        inp.addEventListener('input', () => { x.colour_name = inp.value; paintBoxes(); });
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
    const hit = (x, y) => boxesOn().reverse()
      .find((b) => x >= b.rect[0] && x <= b.rect[0] + b.rect[2] && y >= b.rect[1] && y <= b.rect[1] + b.rect[3]) || null;

    wrap.onpointerdown = (ev) => {
      ev.preventDefault();
      const [x, y] = pt(ev);
      const h = st.arm ? null : hit(x, y);
      const v = V();
      if (h) {
        st.sel = h.kind === 'main' ? { kind: 'main' } : { kind: 'split', i: h.i };
        const r = h.rect;
        const nearCorner = Math.abs(x - (r[0] + r[2])) < 0.06 && Math.abs(y - (r[1] + r[3])) < 0.06;
        const whole = r[2] > 0.95 && r[3] > 0.95;
        st.drag = whole && !nearCorner ? { mode: 'new', x0: x, y0: y } : nearCorner
          ? { mode: 'resize', rect: r } : { mode: 'move', rect: r, dx: x - r[0], dy: y - r[1] };
      } else {
        st.drag = { mode: 'new', x0: x, y0: y };
      }
      if (st.drag.mode === 'new') {
        const rect = [x, y, 0.001, 0.001];
        if (!st.main || (!sameBase(v, st.main) && !st.arm && !boxesOn().length)) {
          st.main = { image: v.image, base: v.base === 'asset' ? 'asset' : v.base, rect };
          st.sel = { kind: 'main' };
        } else {
          st.splits.push({ n: nextN(), image: v.image, base: v.base, rect,
            slot: p.slot || '', colour_name: '' });
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

    const go = (d) => { const n = st.cur + d; if (n >= 0 && n < vers.length) { st.cur = n; st.sel = null; showImage(); } };
    $('adjPrev').onclick = () => go(-1);
    $('adjNext').onclick = () => go(1);
    $('adjUseImage').onclick = () => {
      // take this version whole: a box over all of it, which she can then tighten
      const v = V();
      const e = imageEntry(p, v.image);
      const rect = v.base === 'photo' && e && e[v.kind] ? [...e[v.kind]] : [0, 0, 1, 1];
      st.main = { image: v.image, base: v.base, rect };
      st.sel = { kind: 'main' };
      showImage();
    };
    $('adjAddBox').onclick = () => { st.arm = !st.arm; st.sel = null; $('adjAddBox').classList.toggle('on', st.arm); paint(); };
    $('adjSuggest').onclick = () => {
      const v = V();
      const e = imageEntry(p, v.image);
      for (const rect of (e && e.suggested) || []) {
        st.splits.push({ n: nextN(), image: v.image, base: 'photo', rect: [...rect],
          slot: p.slot === 'multiple' ? '' : (p.slot || ''), colour_name: '' });
      }
      st.sel = null; paint();
    };
    let sw = null;
    const bar = $('adjStrip');
    bar.onpointerdown = (ev) => { sw = ev.clientX; };
    bar.onpointerup = (ev) => {
      if (sw === null) return;
      const dx = ev.clientX - sw; sw = null;
      if (dx < -40) go(1); else if (dx > 40) go(-1);
    };
    $('adjustUse').onclick = () => {
      const r4 = (v) => Math.round(v * 1e4) / 1e4;
      const patch = { splits: st.splits.map((x) => ({ n: x.n, image: x.image || 0, base: x.base || 'photo',
        box: x.rect.map(r4), slot: x.slot || '', colour_name: (x.colour_name || '').trim() })) };
      if (st.main) {
        const whole = st.main.rect[2] > 0.985 && st.main.rect[3] > 0.985;
        Object.assign(patch, {
          choice: whole && st.main.base === 'whole' ? 'whole' : whole && st.main.base === 'asset' ? 'cutout' : 'custom',
          box: whole && st.main.base !== 'photo' ? null : st.main.rect.map(r4),
          image: st.main.image || 0, base: st.main.base || 'photo' });
      } else if (eff?.choice === 'custom') {
        Object.assign(patch, { choice: null, box: null });
      }
      decide(p, patch);
      m.classList.add('hidden');
    };
    $('adjustCancel').onclick = () => m.classList.add('hidden');
    m.classList.remove('hidden');
    showImage();
  }

  document.getElementById('rMulti').addEventListener('change', (ev) => {
    state.multi = ev.target.checked;
    render();
  });

  return { render, state };
}
