// The Review tab: decide what goes on the shelf, one product at a time.
//
// Every product that is not a clean flat cut-out is shown four ways — the
// cut-out, a box around the item, a box around the whole person, the full
// photo — and the stylist taps one, draws her own box, hides it, or leaves it
// for later. Choices apply at once in the browser and can be exported for the
// build script. Nothing here deletes anything.

import { cropLayout, SLOT_ORDER } from './model.js';
import { isReviewed, effectiveChoice, imageEntry, splitId, productVersions,
  SLOT_PICK, choiceBox, choiceBase, isSeveral, isDuplicate, onShelf,
  isBackToReview, reviewReason, isRemoved, removeChoice, restoreChoice } from './data.js';

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

/**
 * Decisions follow their picture. When a split or a colourway assignment
 * moves a picture to another row, or to another place in its row's list, a
 * box or a whole-picture choice made on it moves with it
 * (data/picture-migration.json, one version per build that moved anything).
 * Hiding, taking the cut-out and a slot are decisions about the row, and stay.
 */
export function migratePictures(choices, migration) {
  if (!migration || !Array.isArray(migration.versions)) return 0;
  const onPicture = (c) => ['item', 'person', 'full', 'custom', 'whole'].includes(c.choice);
  let moved = 0;
  for (const v of migration.versions) {
    for (const [pid, c] of Object.entries({ ...choices })) {
      if (!c || (c.pmig || 0) >= v.version) continue;
      c.pmig = v.version;
      for (const sp of c.splits || []) {
        const t = v.moved[`${pid}#${sp.image || 0}`];
        if (t && t.product_id === pid) { sp.image = t.image; moved++; }
      }
      if (!onPicture(c)) continue;
      const t = v.moved[`${pid}#${c.image || 0}`];
      if (!t) continue;
      if (t.product_id === pid) { c.image = t.image; moved++; continue; }
      const there = choices[t.product_id];
      if (there && there.choice) continue;          // she decided there already
      const { choice, box, base } = c;
      choices[t.product_id] = { ...(there || {}), choice, box, base, image: t.image, pmig: v.version };
      delete c.choice; delete c.box; delete c.base; delete c.image;
      moved++;
    }
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
    else if (c.review) e = { review: typeof c.review === 'string' ? c.review : 'sent back to Review' };
    else if (c.choice) e = { choice: c.choice, ...(c.box ? { box: c.box.map((v) => Math.round(v * 1e4) / 1e4) } : {}),
      ...(c.image ? { image: c.image } : {}), ...(c.base && c.base !== 'photo' ? { base: c.base } : {}) };
    const splits = (c.splits || []).filter((s) => s.box && s.n).map((s) => ({
      n: s.n, image: s.image || 0, box: s.box.map((v) => Math.round(v * 1e4) / 1e4),
      slot: s.slot || '', colour_name: s.colour_name || '',
      ...(s.base && s.base !== 'photo' ? { base: s.base } : {}) }));
    if (splits.length) e = { ...(e || {}), splits };
    if (c.slot) e = { ...(e || {}), slot: c.slot };
    if (c.notDuplicate) e = { ...(e || {}), not_duplicate: true };
    if (e) out[pid] = e;
  }
  return { kind: 'relatively-normal.asset-choices', version: 1,
    exported: new Date().toISOString().slice(0, 10), choices: out };
}

// choiceBox and choiceBase live in data.js now, next to shelfView, which the
// shelf tile and the canvas both read.
export { choiceBox, choiceBase };

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
  const state = { slot: '', multi: false, noSlot: false, checkSlot: false,
    several: false, dups: false, removed: false, cellSel: null, adjusting: null };

  const isCell = (p) => !!p.parent_id && /-C\d+$/.test(p.product_id);

  function pending(list) {
    // a clean cut-out of several garments is back here: clean is not single
    const out = list.filter((p) => (!p.clean || isSeveral(p, api.choices) || isBackToReview(p, api.choices))
      && p.full && !p.parent_id);
    // a piece sent back from the shelf gets its own card, wherever it came
    // from — except a grid cell, which waits under its grid's card
    const have = new Set(out.map((p) => p.product_id));
    for (const p of list) {
      if (!p.parent_id || have.has(p.product_id) || !isBackToReview(p, api.choices)) continue;
      if (isCell(p) && have.has(p.parent_id)) continue;
      out.push(p);
    }
    return out;
  }

  /** Everything she removed, to look at again and restore. */
  function renderRemoved() {
    const rows = api.products().filter((p) => isRemoved(p, api.choices));
    $('reviewProgress').textContent = `${rows.length} removed — Restore sends one back to Review; `
      + 'nothing is deleted from the catalogue';
    $('reviewSlots').replaceChildren();
    const cards = $('reviewCards');
    cards.replaceChildren();
    for (const p of rows) cards.appendChild(card(p));
  }

  /** A small picture of a row, with a caption, for the grouped views. */
  function tile(p, caption, cls = '') {
    const b = document.createElement('div');
    b.className = 'cellpick ' + cls;
    const im = document.createElement('img');
    im.loading = 'lazy';
    im.src = p.thumb ? api.source.thumbUrl(p) : api.source.assetUrl(p);
    b.appendChild(im);
    const t = document.createElement('span');
    t.className = 'cellcap';
    t.textContent = caption;
    b.appendChild(t);
    b.title = `${p.product_id} · ${[p.brand, p.product_name, p.price].filter(Boolean).join(' · ')}`;
    return b;
  }

  /**
   * Several garments in one picture, grouped under the row that owns the
   * picture — the grid, or the product a split or a recolour came from — so a
   * whole group is cut up once, with Add box on that row's card.
   */
  function renderSeveral() {
    const all = api.products();
    const byId = Object.fromEntries(all.map((p) => [p.product_id, p]));
    const rows = all.filter((p) => p.several && p.several.length && !p.hidden);
    const groups = {};
    for (const p of rows) (groups[p.several_group || p.product_id] ||= []).push(p);
    const left = rows.filter((p) => isSeveral(p, api.choices) && !isReviewed(p, api.choices)).length;
    $('reviewProgress').textContent = `${rows.length} rows show several garments in one picture, ${left} still to cut`;
    $('reviewSlots').replaceChildren();
    const cards = $('reviewCards');
    cards.replaceChildren();
    for (const [g, members] of Object.entries(groups)) {
      const root = byId[g];
      if (root && root.full) cards.appendChild(card(root));
      const wrap = document.createElement('div');
      wrap.className = 'cellgroup several';
      wrap.dataset.group = g;
      const head = document.createElement('div');
      head.className = 'rhead';
      const who = document.createElement('span');
      who.className = 'rwho';
      who.textContent = `${members.length} row${members.length === 1 ? '' : 's'} with this picture of several garments`
        + (root && root.full ? ' — cut them with Add box on the card above' : '');
      head.appendChild(who);
      wrap.appendChild(head);
      const row = document.createElement('div');
      row.className = 'cells';
      for (const p of members) {
        const t = tile(p, `${p.product_id} · ${p.several.map((w) => w.split(':')[0]).join(', ')}`,
          isSeveral(p, api.choices) ? '' : 'chosen');
        t.dataset.pid = p.product_id;
        row.appendChild(t);
      }
      wrap.appendChild(row);
      const why = document.createElement('div');
      why.className = 'why';
      why.textContent = [...new Set(members.flatMap((p) => p.several))].join(' · ');
      wrap.appendChild(why);
      cards.appendChild(wrap);
    }
  }

  /**
   * Duplicates beside their keepers. Nothing was deleted: a duplicate is only
   * hidden from the shelf, and "Not a duplicate" puts it back.
   */
  function renderDuplicates() {
    const all = api.products();
    const byId = Object.fromEntries(all.map((p) => [p.product_id, p]));
    const rows = all.filter((p) => p.duplicate_of);
    const released = rows.filter((p) => !isDuplicate(p, api.choices)).length;
    $('reviewProgress').textContent = `${rows.length} marked as duplicates`
      + (released ? `, ${released} put back as not duplicates` : '');
    $('reviewSlots').replaceChildren();
    const cards = $('reviewCards');
    cards.replaceChildren();
    const groups = {};
    for (const p of rows) (groups[p.duplicate_of] ||= []).push(p);
    for (const [keep, members] of Object.entries(groups)) {
      const wrap = document.createElement('div');
      wrap.className = 'cellgroup dupgroup';
      wrap.dataset.keeper = keep;
      const row = document.createElement('div');
      row.className = 'cells';
      if (byId[keep]) row.appendChild(tile(byId[keep], `keeper · ${keep}`, 'keeper'));
      for (const p of members) {
        const dup = isDuplicate(p, api.choices);
        const t = tile(p, `${p.product_id} · ${p.duplicate_cause}`, dup ? 'dup' : 'chosen');
        t.dataset.pid = p.product_id;
        const b = document.createElement('button');
        b.className = 'ghost small';
        b.dataset.act = 'notdup';
        b.textContent = dup ? 'Not a duplicate' : 'Is a duplicate';
        b.addEventListener('click', () => {
          const cur = api.choices[p.product_id] || {};
          api.choices[p.product_id] = { ...cur, notDuplicate: dup };
          if (!dup) delete api.choices[p.product_id].notDuplicate;
          saveChoices(api.choices); api.onChange(); render();
        });
        t.appendChild(b);
        row.appendChild(t);
      }
      wrap.appendChild(row);
      cards.appendChild(wrap);
    }
  }

  /** Does this product match whichever slot filters are on? */
  function matchesSlotFilters(p) {
    if (state.noSlot && p.slot) return false;
    if (state.checkSlot && !['inherited', 'guessed'].includes(p.slot_confidence)) return false;
    if (state.slot && p.slot !== state.slot) return false;
    return true;
  }

  /** The cells cut out of a listing grid, by the grid they came from. */
  function cellsByParent(list) {
    const by = {};
    for (const p of list) {
      if (!p.parent_id || !/-C\d+$/.test(p.product_id)) continue;
      (by[p.parent_id] = by[p.parent_id] || []).push(p);
    }
    return by;
  }

  function render() {
    if (state.removed) { renderRemoved(); return; }
    if (state.dups) { renderDuplicates(); return; }
    if (state.several) { renderSeveral(); return; }
    const all = pending(api.products());
    let list = state.slot ? all.filter((p) => p.slot === state.slot) : all;
    if (state.multi) list = list.filter((p) => productImages(p).length > 1);
    if (state.noSlot) list = list.filter((p) => !p.slot);
    // the rows whose slot came from somewhere that might be wrong about it:
    // a listing-grid caption, or the product this one was split out of
    if (state.checkSlot) list = list.filter((p) => p.slot_confidence === 'inherited'
      || p.slot_confidence === 'guessed');
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
    const cells = cellsByParent(api.products());
    // A slot filter is about products, and a grid's cells are products even
    // though the grid itself is one row: keep a grid whose cells match, or the
    // filter that finds the missing slots would find nothing, because every
    // grid is filed as `multiple`.
    if (state.noSlot || state.checkSlot) {
      const have = new Set(list.map((p) => p.product_id));
      for (const p of all) {
        if (have.has(p.product_id)) continue;
        if ((cells[p.product_id] || []).some((c) => matchesSlotFilters(c))) list.push(p);
      }
    }
    const todo = list.filter((p) => !isReviewed(p, api.choices));
    const doneList = list.filter((p) => isReviewed(p, api.choices));
    for (const p of [...todo, ...doneList]) {
      // a grid that has been cut into cells is its cells now, not a picture of
      // several garments to box: say where they are and show the ones left
      const mine = cells[p.product_id];
      if (mine && mine.length) {
        const g = gridCard(p, mine);
        if (g) cards.appendChild(g);
        continue;
      }
      cards.appendChild(card(p));
    }
  }

  /**
   * A listing grid's cells, under the grid they were cut from. One tap takes
   * the whole grid: a shop's page of twelve is twelve decisions otherwise, and
   * they are the same decision twelve times.
   */
  /**
   * A grid already cut into cells: "N cells: M on the shelf, K in Review",
   * the K underneath with Accept all cells. A cell is on the shelf when the
   * gate passed it or she accepted it; the rest wait here, each saying why.
   */
  function gridCard(parent, all) {
    const shelf = all.filter((c) => onShelf(c, api.choices, false));
    const waiting = all.filter((c) => !onShelf(c, api.choices, false) && !isDuplicate(c, api.choices)
      && !effectiveChoice(c, api.choices)?.hidden);
    const shown = (state.noSlot || state.checkSlot || state.slot) ? waiting.filter(matchesSlotFilters) : waiting;
    if (!shown.length && (state.noSlot || state.checkSlot || state.slot)) return null;
    const head = `${all.length} cell${all.length === 1 ? '' : 's'}: ${shelf.length} on the shelf, `
      + `${waiting.length} in Review`;
    const g = cellGroup(parent, shown, head);
    g.classList.add('gridcard');
    g.dataset.pid = parent.product_id;
    return g;
  }

  function cellGroup(parent, all, heading) {
    // the slot filters reach the cells too: they are where the missing slots are
    const cells = heading ? all : (state.noSlot || state.checkSlot || state.slot)
      ? all.filter(matchesSlotFilters) : all;
    if (!cells.length && !heading) return null;
    const wrap = document.createElement('div');
    wrap.className = 'cellgroup';
    const head = document.createElement('div');
    head.className = 'rhead';
    const left = cells.filter((c) => !isReviewed(c, api.choices)).length;
    const who = document.createElement('span');
    who.className = 'rwho';
    who.textContent = heading ? `${parent.product_id} · ${heading}`
      : `${cells.length} cell${cells.length === 1 ? '' : 's'} cut from this grid`
      + (left ? `, ${left} still to decide` : ', all decided');
    head.appendChild(who);
    const takeAll = document.createElement('button');
    takeAll.className = 'ghost small';
    takeAll.textContent = 'Accept all cells';
    takeAll.addEventListener('click', () => {
      for (const c of cells) api.choices[c.product_id] = { ...(api.choices[c.product_id] || {}), choice: 'cutout' };
      saveChoices(api.choices); api.onChange(); render();
    });
    if (cells.length) head.appendChild(takeAll);
    wrap.appendChild(head);
    const row = document.createElement('div');
    row.className = 'cells';
    for (const c of cells) {
      const b = document.createElement('button');
      b.className = 'cellpick' + (isReviewed(c, api.choices) ? ' chosen' : '');
      b.dataset.pid = c.product_id;
      const im = document.createElement('img');
      im.loading = 'lazy';
      im.src = api.source.assetUrl(c);
      b.appendChild(im);
      const t = document.createElement('button');
      t.className = 'cellslot' + (state.cellSel === c.product_id ? ' on' : '');
      t.textContent = [c.slot || 'set slot', c.price].filter(Boolean).join(' · ');
      t.title = 'Set this cell\'s slot';
      t.addEventListener('click', (ev) => {
        ev.stopPropagation();
        state.cellSel = state.cellSel === c.product_id ? null : c.product_id;
        render();
      });
      if (c.validated === 'possible duplicate') {
        const d = document.createElement('i');
        d.className = 'twin';
        d.textContent = 'twin?';
        b.appendChild(d);
      }
      b.appendChild(t);
      if (c.hold && !isReviewed(c, api.choices)) {
        const w = document.createElement('span');
        w.className = 'cellcap';
        w.textContent = c.hold;                  // why the gate kept it here
        b.appendChild(w);
      }
      b.title = [c.product_name, c.price, c.hold].filter(Boolean).join(' — ') || c.product_id;
      b.addEventListener('click', () => {
        const had = isReviewed(c, api.choices);
        if (had) delete api.choices[c.product_id];
        else api.choices[c.product_id] = { choice: 'cutout' };
        saveChoices(api.choices); api.onChange(); render();
      });
      row.appendChild(b);
    }
    wrap.appendChild(row);
    const chosen = cells.find((c) => c.product_id === state.cellSel);
    if (chosen) wrap.appendChild(slotRow(chosen, `${chosen.product_id} · `
      + (chosen.product_name || 'this cell')));
    return wrap;
  }

  /** The eight slots, as buttons, for one product. */
  function slotRow(p, label) {
    const slots = document.createElement('div');
    slots.className = 'rslots';
    if (label) {
      const l = document.createElement('span');
      l.className = 'slotfor';
      l.textContent = label;
      slots.appendChild(l);
    }
    if (p.slot_confidence === 'inherited' || p.slot_confidence === 'guessed') {
      const w = document.createElement('i');
      w.className = 'slotwarn';
      w.textContent = p.slot_confidence === 'inherited' ? 'slot inherited' : 'slot from a caption';
      slots.appendChild(w);
    }
    for (const slot of SLOT_PICK) {
      const b = document.createElement('button');
      b.className = 'ghost small' + (p.slot === slot ? ' on' : '');
      b.textContent = slot;
      b.addEventListener('click', () => {
        const cur = api.choices[p.product_id] || {};
        api.choices[p.product_id] = { ...cur, slot: cur.slot === slot ? '' : slot };
        saveChoices(api.choices);
        api.onChange();
        render();
      });
      slots.appendChild(b);
    }
    return slots;
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
    const back = reviewReason(p, api.choices) || (!eff?.hidden && !isReviewed(p, api.choices) && p.hold) || '';
    if (back) {
      const w = document.createElement('div');
      w.className = 'why back';
      w.textContent = back;
      el.appendChild(w);
    }
    if (isSeveral(p, api.choices)) {
      const w = document.createElement('div');
      w.className = 'why several';
      // a product page's colour-swatch thumbnails are one product's colour
      // picker, not products: nothing to cut out of them
      w.textContent = p.several.some((x) => x.startsWith('swatch row'))
        ? 'Colour-swatch thumbnails on a product page — not products. Remove it, or keep the colour the page shows with Adjust box.'
        : `Several garments in this picture (${p.several.map((x) => x.split(':')[0]).join(', ')})`
          + ' — not a single product. Adjust box, then Add box, one per garment.';
      el.appendChild(w);
    }
    const row = document.createElement('div');
    row.className = 'versions';
    // a piece with no full photo (a clean flat cut-out sent back) has only its cut-out
    const kinds = p.full ? [['cutout', 'cut-out'], ['item', 'item box'], ['person', 'person box'], ['full', 'full']]
      : [['cutout', 'cut-out']];
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
    el.appendChild(slotRow(p, ''));
    const acts = document.createElement('div');
    acts.className = 'racts';
    const mk = (label, cls, fn) => {
      const b = document.createElement('button');
      b.className = 'ghost small ' + cls; b.textContent = label;
      b.dataset.act = label.toLowerCase().replace(/\s+/g, '-');
      b.addEventListener('click', fn);
      acts.appendChild(b);
    };
    if (p.full || (p.images && p.images.length)) mk('Adjust box', '', () => openAdjust(p));
    if (eff?.hidden) mk('Restore', '', () => setChoice(p, restoreChoice(api.choices[p.product_id])));
    else mk('Remove', 'danger', () => setChoice(p, removeChoice(api.choices[p.product_id])));
    mk('Later', '', () => { api.choices[p.product_id] = { ...c, later: true }; saveChoices(api.choices); render(); });
    if (eff && !eff.hidden && !eff.review && eff.choice) mk('Undo choice', '', () => { delete api.choices[p.product_id]; saveChoices(api.choices); api.onChange(); render(); });
    el.appendChild(acts);
    return el;
  }

  function setChoice(p, c) {
    api.choices[p.product_id] = c;
    saveChoices(api.choices);
    api.onChange();
    render();
  }

  function decide(p, patch) {
    const prev = api.choices[p.product_id] || {};
    // any decision here answers "back to Review"
    const { review, ...rest } = prev;
    api.choices[p.product_id] = { ...rest, later: false, ...patch };
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
    // the fabric close-ups are kept, and kept out of the way until asked for
    const hasDetails = (p.images || []).some((e) => e.type === 'detail' || e.type === 'text'
      || e.type === 'other');
    $('adjDetailsWrap').hidden = !hasDetails;
    $('adjDetails').checked = false;
    let vers = productVersions(p);
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
      undo: null,
      zoom: 1,
      pointers: new Map(),
      pinch: null,
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
    let stage = null;
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

    // ---------------------------------------------------------------- the stage
    //
    // The picture and the boxes live in one element, sized in pixels. That is
    // the whole of the geometry: a box is a percentage of the stage, and the
    // stage IS the picture, so what is drawn and what is pointed at are the
    // same rectangle. (They were not before: boxes were percentages of the
    // scrolling wrapper, whose height is the visible strip, not the picture's,
    // so on any picture taller than the wrapper every box was painted short
    // and the resize corner sat nowhere near the corner you could see.)
    const PAD = 26;                 // room for a handle that hangs off the picture
    function baseWidth() {
      const cw = wrap.clientWidth - PAD * 2, ch = wrap.clientHeight - PAD * 2;
      const nw = img && img.naturalWidth ? img.naturalWidth : 3;
      const nh = img && img.naturalHeight ? img.naturalHeight : 4;
      if (!cw || !ch) return cw || 320;
      return Math.max(80, Math.min(cw, ch * (nw / nh)));   // the whole picture, as large as it fits
    }
    function layout(zoom) {
      if (zoom !== undefined) st.zoom = Math.max(1, Math.min(8, zoom));
      if (stage) stage.style.width = `${Math.round(baseWidth() * st.zoom)}px`;
      $('adjZoom').textContent = st.zoom > 1.01 ? `${st.zoom.toFixed(1)}×` : 'fit';
    }

    function showImage() {
      const v = V();
      wrap.replaceChildren();
      wrap.classList.toggle('on-ground', v.base !== 'photo');
      stage = document.createElement('div');
      stage.className = 'adjust-stage';
      stage.id = 'adjStage';
      img = document.createElement('img');
      img.src = versionUrl(v);
      img.draggable = false;
      img.addEventListener('load', () => { layout(); paintBoxes(); });
      stage.appendChild(img);
      wrap.appendChild(stage);
      st.zoom = 1;
      layout();
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

    // corners first, then edges: on a small box the targets overlap and the
    // corner is what the finger means
    const HANDLES = [['nw', 0, 0], ['ne', 1, 0], ['sw', 0, 1], ['se', 1, 1],
      ['n', 0.5, 0], ['s', 0.5, 1], ['w', 0, 0.5], ['e', 1, 0.5]];
    const GRAB = 22;              // half of a 44 px target, and it reaches outside the box
    const MINSIDE = 0.004;

    function paintBoxes() {
      if (!stage) return;
      stage.querySelectorAll('.adjust-box').forEach((d) => d.remove());
      const sel = selected();
      for (const b of boxesOn()) {
        const d = document.createElement('div');
        d.className = `adjust-box ${b.kind}`;
        const isSel = sel && sel.kind === b.kind && (b.kind === 'main' || sel.i === b.i);
        if (isSel) d.classList.add('sel');
        d.style.left = `${b.rect[0] * 100}%`; d.style.top = `${b.rect[1] * 100}%`;
        d.style.width = `${b.rect[2] * 100}%`; d.style.height = `${b.rect[3] * 100}%`;
        if (isSel) {
          for (const [name, hx, hy] of HANDLES) {
            const h = document.createElement('i');
            h.className = `adjust-handle h-${name}`;
            h.dataset.handle = name;
            h.style.left = `${hx * 100}%`; h.style.top = `${hy * 100}%`;
            d.appendChild(h);                 // above the box's own dimming shadow
          }
        }
        stage.appendChild(d);                 // no label: nothing over the photo
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
        hint('This product\'s own image. Drag any handle to widen or tighten it; pinch to zoom in first.');
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

    // ------------------------------------------------- the loupe, while dragging
    const loupe = $('adjLoupe');
    function showLoupe(cx, cy, x, y) {
      if (!stage) return;
      const r = stage.getBoundingClientRect();
      const M = 2.5;
      loupe.style.backgroundImage = `url("${img.getAttribute('src')}")`;
      loupe.style.backgroundSize = `${r.width * M}px ${r.height * M}px`;
      loupe.style.backgroundPosition = `${60 - x * r.width * M}px ${60 - y * r.height * M}px`;
      const near = cx < 200 && cy < 220;
      loupe.style.left = `${cx + (near ? 24 : -144)}px`;
      loupe.style.top = `${Math.max(8, cy - 148)}px`;
      const w = img.naturalWidth || 0, h = img.naturalHeight || 0;
      const sel = selected();
      $('adjNumbers').textContent = sel
        ? `${Math.round(sel.rect[2] * w)} × ${Math.round(sel.rect[3] * h)} px` : '';
      loupe.hidden = false;
    }
    const hideLoupe = () => { loupe.hidden = true; };

    // --------------------------------------------------------- pointers
    const pt = (ev) => {
      const r = stage.getBoundingClientRect();
      return [Math.min(1, Math.max(0, (ev.clientX - r.left) / r.width)),
        Math.min(1, Math.max(0, (ev.clientY - r.top) / r.height))];
    };
    // 1. a handle of a box — tested in screen pixels, so it reaches outside the
    //    box and a handle on the picture's own edge is still grabbable
    const handleAt = (cx, cy, rect) => {
      const r = stage.getBoundingClientRect();
      for (const [name, hx, hy] of HANDLES) {
        const px = r.left + (rect[0] + rect[2] * hx) * r.width;
        const py = r.top + (rect[1] + rect[3] * hy) * r.height;
        if (Math.abs(cx - px) <= GRAB && Math.abs(cy - py) <= GRAB) return name;
      }
      return null;
    };
    // 2. inside a box
    const inside = (x, y) => boxesOn().reverse()
      .find((b) => x >= b.rect[0] && x <= b.rect[0] + b.rect[2] && y >= b.rect[1] && y <= b.rect[1] + b.rect[3]) || null;

    const clamp01 = (v) => Math.min(1, Math.max(0, v));
    function resized(name, x, y, r0) {
      let [x0, y0] = r0;
      let x1 = x0 + r0[2], y1 = y0 + r0[3];
      if (name.includes('w')) x0 = x;
      if (name.includes('e')) x1 = x;
      if (name.includes('n')) y0 = y;
      if (name.includes('s')) y1 = y;
      const a = clamp01(Math.min(x0, x1)), b = clamp01(Math.max(x0, x1));
      const c = clamp01(Math.min(y0, y1)), d = clamp01(Math.max(y0, y1));
      return [a, c, Math.max(MINSIDE, b - a), Math.max(MINSIDE, d - c)];
    }
    const setRect = (target, r) => { for (let i = 0; i < 4; i++) target[i] = r[i]; };

    // Two fingers always mean zoom and pan, never an edit. The second finger
    // lands a moment after the first, which has already begun a box, so the
    // first finger's work is put back before the pinch starts.
    function revertTouch() {
      const u = st.undo;
      st.undo = null;
      if (!u) return;
      st.main = u.main;
      st.splits.length = u.splits;
      if (u.target && u.rect) setRect(u.target, u.rect);
      st.sel = u.sel;
      paint();
    }
    function startPinch() {
      revertTouch();
      const [[ax, ay], [bx, by]] = [...st.pointers.values()];
      const r = stage.getBoundingClientRect();
      const mx = (ax + bx) / 2, my = (ay + by) / 2;
      st.pinch = { d: Math.hypot(bx - ax, by - ay), zoom: st.zoom,
        fx: (mx - r.left) / r.width, fy: (my - r.top) / r.height };
    }
    function movePinch() {
      if (!st.pinch || st.pointers.size < 2) return;
      const [[ax, ay], [bx, by]] = [...st.pointers.values()];
      const d = Math.hypot(bx - ax, by - ay);
      const mx = (ax + bx) / 2, my = (ay + by) / 2;
      layout(st.pinch.d > 8 ? st.pinch.zoom * (d / st.pinch.d) : st.zoom);
      // the picture point the fingers started on stays under the fingers: that
      // is the zoom, and moving the fingers together is the pan
      const r = stage.getBoundingClientRect();
      wrap.scrollLeft += (r.left + st.pinch.fx * r.width) - mx;
      wrap.scrollTop += (r.top + st.pinch.fy * r.height) - my;
      paintBoxes();
    }

    wrap.onpointerdown = (ev) => {
      ev.preventDefault();
      // the first finger of a gesture clears whatever the last one left behind:
      // a touch released off the wrapper never reports back, and one stale id
      // would make the next single-finger drag look like a pinch
      if (ev.isPrimary !== false) { st.pointers.clear(); st.pinch = null; }
      st.pointers.set(ev.pointerId, [ev.clientX, ev.clientY]);
      if (st.pointers.size === 2) { st.drag = null; hideLoupe(); startPinch(); return; }
      if (st.pointers.size > 2) return;
      const [x, y] = pt(ev);
      const sel = selected();
      const wasSel = st.sel, wasMain = st.main, wasSplits = st.splits.length;
      // the hit test, in order: a handle, then inside a box, then a new box
      let h = null, on = null;
      if (!st.arm && sel) { h = handleAt(ev.clientX, ev.clientY, sel.rect); if (h) on = sel; }
      if (!h && !st.arm) {
        for (const b of boxesOn().reverse()) {
          const n = handleAt(ev.clientX, ev.clientY, b.rect);
          if (n) { h = n; on = b; break; }
        }
      }
      if (!h && !st.arm) on = inside(x, y);
      if (on) st.sel = on.kind === 'main' ? { kind: 'main' } : { kind: 'split', i: on.i };
      const r = on ? on.rect : null;
      const covers = r && r[2] > 0.99 && r[3] > 0.99;
      if (h) {
        st.drag = { mode: 'resize', rect: r, handle: h };
      } else if (on && !covers) {
        st.drag = { mode: 'move', rect: r, dx: x - r[0], dy: y - r[1] };
      } else {
        st.drag = { mode: 'new', x0: x, y0: y };
      }
      if (st.drag.mode === 'new') {
        const rect = [x, y, MINSIDE, MINSIDE];
        const v = V();
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
      st.undo = { sel: wasSel, main: wasMain, splits: wasSplits,
        rect: st.drag.mode === 'new' ? null : [...st.drag.rect], target: st.drag.rect };
      try { wrap.setPointerCapture(ev.pointerId); } catch (e) { /* pointer already gone */ }
      paint();
      if (st.drag.mode === 'resize') showLoupe(ev.clientX, ev.clientY, x, y);
    };
    wrap.onpointermove = (ev) => {
      if (st.pointers.has(ev.pointerId)) st.pointers.set(ev.pointerId, [ev.clientX, ev.clientY]);
      if (st.pinch) { movePinch(); return; }
      const d = st.drag;
      if (!d) return;
      const [x, y] = pt(ev);              // one to one with the finger, no snapping
      const r = d.rect;
      if (d.mode === 'move') {
        r[0] = Math.min(1 - r[2], Math.max(0, x - d.dx)); r[1] = Math.min(1 - r[3], Math.max(0, y - d.dy));
      } else if (d.mode === 'resize') {
        setRect(r, resized(d.handle, x, y, r));
      } else {
        r[0] = Math.min(d.x0, x); r[1] = Math.min(d.y0, y);
        r[2] = Math.max(MINSIDE, Math.abs(x - d.x0)); r[3] = Math.max(MINSIDE, Math.abs(y - d.y0));
      }
      paintBoxes();
      if (d.mode === 'resize') showLoupe(ev.clientX, ev.clientY, x, y); else hideLoupe();
    };
    const letGo = (ev) => {
      st.pointers.delete(ev.pointerId);
      if (st.pointers.size < 2) st.pinch = null;
      if (!st.pointers.size) { st.drag = null; st.undo = null; hideLoupe(); }
    };
    wrap.onpointerup = letGo;
    wrap.onpointercancel = letGo;
    wrap.onlostpointercapture = letGo;
    window.addEventListener('pointerup', letGo);      // a finger let go off the picture
    $('adjZoom').onclick = () => { layout(st.zoom > 1.01 ? 1 : 2.5); paintBoxes(); };
    window.addEventListener('resize', () => { if (!m.classList.contains('hidden')) { layout(); paintBoxes(); } });

    $('adjDetails').onchange = (ev) => {
      const was = vers[st.cur];
      vers = productVersions(p, { details: ev.target.checked });
      const i = vers.findIndex((v) => v.kind === was.kind && v.image === was.image && v.base === was.base);
      st.cur = i >= 0 ? i : 0;
      st.sel = null;
      showImage();
    };
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

  for (const [id, key] of [['rMulti', 'multi'], ['rNoSlot', 'noSlot'], ['rCheckSlot', 'checkSlot'],
    ['rSeveral', 'several'], ['rDups', 'dups'], ['rRemoved', 'removed']]) {
    document.getElementById(id).addEventListener('change', (ev) => {
      state[key] = ev.target.checked;
      render();
    });
  }

  return { render, state };
}
