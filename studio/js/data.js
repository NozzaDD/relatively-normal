// Where the desk gets its items from.
//
// The UI never reads a file path or a CSV column. It asks a source for
// products and looks, and gets the same shape back whatever the source is.
// Today that is the static catalogue built by content/tools/build_studio.py;
// later it can be a signed-in user's own wardrobe, and nothing above this line
// has to change.

/** @typedef {{products: Array, inspiration: Array, meta: Object, palettes: Object|null}} Catalogue */

export function createStaticSource(base = '.') {
  const url = (p) => `${base.replace(/\/$/, '')}/${p}`;
  return {
    name: 'catalogue',
    /** @returns {Promise<Catalogue>} */
    async load() {
      const [products, inspiration, meta, palettes] = await Promise.all([
        fetch(url('data/products.json')).then((r) => r.json()),
        fetch(url('data/inspiration.json')).then((r) => r.json()),
        fetch(url('data/meta.json')).then((r) => r.json()).catch(() => ({})),
        // the palettes are a working aid: without them the desk still works
        fetch(url('data/palettes.json')).then((r) => (r.ok ? r.json() : null)).catch(() => null),
      ]);
      return { products, inspiration, meta, palettes };
    },
    assetUrl: (p) => url(p.asset),
    thumbUrl: (p) => url(p.thumb),
    fullUrl: (p, idx = 0) => { const e = imageEntry(p, idx); return url(e ? e.path : p.asset); },
    wholeUrl: (p, idx = 0) => { const e = imageEntry(p, idx); return e && e.whole ? url(e.whole.path) : null; },
    inspirationUrl: (i) => url(i.image),
    inspirationThumbUrl: (i) => url(i.thumb),
  };
}

/** An in-memory source, for tests and for a future "my own items" mode. */
export function createMemorySource(catalogue, urls = {}) {
  return {
    name: 'memory',
    async load() { return catalogue; },
    assetUrl: urls.assetUrl || ((p) => p.asset),
    thumbUrl: urls.thumbUrl || ((p) => p.thumb),
    fullUrl: urls.fullUrl || ((p, idx = 0) => { const e = imageEntry(p, idx); return e ? e.path : p.asset; }),
    wholeUrl: urls.wholeUrl || ((p, idx = 0) => { const e = imageEntry(p, idx); return e && e.whole ? e.whole.path : null; }),
    inspirationUrl: urls.inspirationUrl || ((i) => i.image),
    inspirationThumbUrl: urls.inspirationThumbUrl || ((i) => i.thumb),
  };
}

/** One of a product's screenshots: index 0 is the best one, the "full" image. */
export function imageEntry(p, idx = 0) {
  if (p.images && p.images[idx]) return p.images[idx];
  if (idx === 0 && p.full) return { path: p.full.path, w: p.full.w, h: p.full.h, ...(p.boxes || {}) };
  return null;
}

/**
 * Every version of a product the stylist can choose between: its cut-out, and
 * for each screenshot the item box, the person box, the whole photo and the
 * whole cut-out. `base` says which image a box is drawn on — the photo, or the
 * cut-out, where a box keeps the transparency.
 */
export function productVersions(p, { details = false } = {}) {
  const out = [];
  if (p.asset && p.asset_type !== 'crop') {
    out.push({ kind: 'cutout', image: 0, base: 'asset', label: 'cut-out' });
  }
  const imgs = (p.images && p.images.length) ? p.images : (imageEntry(p, 0) ? [imageEntry(p, 0)] : []);
  // a picture that cuts the piece off at its edge is offered after the ones that do not
  clearFirst(imgs.map((e, i) => i), imgs).forEach((i) => {
    const e = imgs[i];
    // A fabric close-up is not a version of the garment — it is a swatch of it —
    // so it stays in the data and out of the filmstrip unless asked for.
    if (isDetail(e) && !details) return;
    // the picture's own type leads the label: a product page that held a flat
    // lay and a shot on the model is two pictures now, and which is which is
    // the thing worth knowing at a glance
    const t = e.type && e.type !== 'whole page' ? `${e.type} · ` : '';
    const n = imgs.length > 1 ? ` ${i + 1}` : '';
    if (e.whole) out.push({ kind: 'whole', image: i, base: 'whole', label: `${t}whole cut-out${n}` });
    if (e.item) out.push({ kind: 'item', image: i, base: 'photo', label: `${t}item box${n}` });
    if (e.person) out.push({ kind: 'person', image: i, base: 'photo', label: `${t}person box${n}` });
    out.push({ kind: 'full', image: i, base: 'photo', label: `${t}full photo${n}` });
  });
  return out;
}

/** A fabric close-up or a panel of page type: real, kept, but not a version. */
export const isDetail = (e) => e && (e.type === 'detail' || e.type === 'text' || e.type === 'other');

/** The pictures a piece can be switched between: one per picture of the product. */
export function productPictures(p) {
  const all = p.images || [];
  const imgs = clearFirst(all.map((e, i) => i), all).map((i) => ({ i, type: all[i].type || 'whole page', entry: all[i] }))
    .filter((x) => !isDetail(x.entry));
  return imgs.length > 1 ? imgs : [];
}

/**
 * Picture indices, those where the piece is clear of the frame first — a bag
 * whose handles run out of the top of one photo is offered from the other.
 * `clipped` is measured by edge_clip.py; the order is otherwise kept.
 */
export function clearFirst(indices, images) {
  const clipped = (i) => !!(images[i] && images[i].clipped && images[i].clipped.length);
  return [...indices.filter((i) => !clipped(i)), ...indices.filter(clipped)];
}

/** The picture a Review card shows its boxes on: the first real one clear of the frame. */
export function firstPicture(p) {
  const imgs = p.images || [];
  const real = imgs.map((e, i) => i).filter((i) => !isDetail(imgs[i]));
  return clearFirst(real, imgs)[0] ?? 0;
}

/** The sides of the frame the piece runs out of in every picture, or [] when one shows it whole. */
export function clippedSides(p) {
  if (!p.clipped) return [];
  return [...new Set((p.images || []).flatMap((e) => e.clipped || []))];
}

/** A stable id for the n-th box cut out of a product's image. */
export const splitId = (pid, n) => `${pid}-S${n}`;

/**
 * Products the stylist cut out of another product's image, as the desk sees
 * them before a rebuild: a runtime crop with the parent's brand and batch,
 * the slot and colour name she gave, and no colour fields yet. Once the build
 * script has made the row, the catalogue's version wins and this one steps
 * aside.
 */
export function derivedProducts(products, choices) {
  const byId = indexById(products);
  const out = [];
  for (const [pid, c] of Object.entries(choices || {})) {
    const parent = byId[pid];
    if (!parent || !Array.isArray(c.splits)) continue;
    for (const sp of c.splits) {
      const id = splitId(pid, sp.n);
      if (byId[id] || !sp.box) continue;
      const img = imageEntry(parent, sp.image || 0);
      if (!img) continue;
      const base = sp.base || 'photo';
      // a box drawn on the cut-out crops the parent's cut-out, never the photo
      const src = base === 'asset' ? { path: parent.asset, w: null, h: null }
        : base === 'whole' && img.whole ? img.whole : img;
      out.push({
        product_id: id, parent_id: pid, local: true,
        slot: sp.slot || parent.slot || '', garment_type: parent.garment_type || '',
        pattern: '', weight: parent.weight ?? null, formality: parent.formality ?? null,
        colours: [], colour_confidence: '', colour_stability: '',
        colour_name_text: sp.colour_name || '',
        asset: src.path, thumb: null, asset_type: 'crop', asset_quality: 'good',
        base,
        brand: parent.brand || '', brand_confidence: parent.brand_confidence || '',
        brand_role: parent.brand_role || '',
        product_name: '', product_name_confidence: 'input needed',
        material: '', material_confidence: 'input needed',
        price: '', price_confidence: 'input needed',
        product_url: '', product_url_confidence: 'input needed',
        image_source: parent.image_source || '', shop: parent.shop || '', used_in: [],
        clean: false, full: { path: src.path, w: src.w, h: src.h }, boxes: null,
        images: parent.images || null, image: sp.image || 0,
        choice: 'custom', custom_box: sp.box, hidden: false,
        recoloured: false, recolour_source: '',
      });
    }
  }
  return out;
}

export function indexById(products) {
  const m = Object.create(null);
  for (const p of products) m[p.product_id] = p;
  return m;
}

export function indexInspiration(items) {
  const m = Object.create(null);
  for (const i of items) m[i.inspiration_id] = i;
  return m;
}

// ------------------------------------------------------------------ filters
export const WEIGHT_LABELS = { 1: 'light', 2: 'light–mid', 3: 'mid–heavy', 4: 'heavy' };
export const FORMALITY_LABELS = { 1: 'casual', 2: 'easy', 3: 'smart', 4: 'dressy' };

export const emptyFilters = () => ({
  slot: '', family: '', weight: '', formality: '', assetType: '', brand: '',
  search: '', showUnreviewed: false,
});

/**
 * What the stylist decided about a product's image, if anything: the choice
 * made in the browser first, then the one filed in the catalogue.
 */
/** Every slot the desk can set, in the order the buttons read. */
export const SLOT_PICK = ['layer', 'top', 'bottom', 'dress', 'shoes', 'bag', 'accessory', 'base'];

/**
 * The slot a product has right now: the one picked on the desk if there is one,
 * else the one the catalogue holds. A slot is not a picture decision, so
 * picking one never marks a product reviewed.
 */
export function effectiveSlot(p, local) {
  const l = local && local[p.product_id];
  return (l && l.slot) || p.slot || '';
}

/** Put the desk's slot picks onto the products, so every list sees them. */
export function applySlots(products, local) {
  let n = 0;
  for (const p of products) {
    const l = local && local[p.product_id];
    if (l && l.slot && l.slot !== p.slot) {
      p.slot = l.slot;
      p.slot_confidence = 'given';
      n++;
    }
  }
  return n;
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
  // a box drawn on the cut-out in Adjust box is a box on the cut-out
  if (c.base === 'asset') return 'asset';
  return c.base === 'whole' ? 'whole' : 'photo';
}

/**
 * THE picture a product shows on the shelf, and so the picture a tap places.
 * The tile and the canvas both read this and nothing else: another picture
 * picked with the badge, else the stylist's choice (the browser's first, then
 * the catalogue's), else the cut-out.
 * @returns {{variant: string, crop: number[]|null, image: number, base: string}}
 */
export function shelfView(p, local, picture, type) {
  if (picture === 'cut') {
    const base = shelfView(p, local, undefined, type);
    return cutoutOf(p, base) || base;
  }
  if (picture !== undefined && picture !== null && p.images && p.images[picture]) {
    const e = p.images[picture];
    return e.whole ? { variant: 'whole', crop: [0, 0, 1, 1], image: picture, base: 'whole' }
      : { variant: 'full', crop: [0, 0, 1, 1], image: picture, base: 'photo' };
  }
  // a filter that names a picture type decides the picture, for the tile and
  // for the tap alike; the stylist's own choice is what shows without one
  if (type) {
    const v = pictureOfType(p, type);
    if (v) return v;
  }
  return primaryView(p, local);
}

/** The product's own picture on the shelf: her choice, else the cut-out. */
function primaryView(p, local) {
  const c = effectiveChoice(p, local);
  const box = choiceBox(p, c);
  const image = (c && c.image) || p.image || 0;
  if (box) return { variant: c.choice, crop: box, image, base: choiceBase(c) };
  if (c && c.choice === 'whole') return { variant: 'whole', crop: [0, 0, 1, 1], image, base: 'whole' };
  return { variant: 'cutout', crop: null, image: 0, base: 'photo' };
}

const CUTOUT = Object.freeze({ variant: 'cutout', crop: null, image: 0, base: 'photo' });
/** The picture types the image filter names, and the pictures that are of each. */
export const PICTURE_TYPES = { cutout_flat: ['flat lay', 'cell'], cutout_model: ['on-model'] };

/**
 * The view of a product in the picture type a filter names, or null when it
 * has no picture of that type. The catalogue cut-out counts when it is that
 * type and was not cut from a picture typed as another; otherwise a whole
 * cut-out of a picture of that type.
 */
export function pictureOfType(p, type) {
  if (!type) return null;
  if (type === 'tile') return p.asset_type === 'tile' ? { ...CUTOUT } : null;
  const want = PICTURE_TYPES[type] || [];
  const imgs = p.images || [];
  const src = imgs[p.image || 0];
  const other = src && src.type && !want.includes(src.type) && src.type !== 'whole page'
    && src.type !== 'listing grid';
  if (p.asset_type === type && !other) return { ...CUTOUT };
  const i = imgs.findIndex((e) => want.includes(e.type) && e.whole);
  if (i >= 0) return { variant: 'whole', crop: [0, 0, 1, 1], image: i, base: 'whole' };
  return p.asset_type === type ? { ...CUTOUT } : null;
}

/**
 * The cut-out of the picture a view shows, when the view is a box or a crop
 * tile and the catalogue holds a cut-out of that same picture: the picture's
 * whole cut-out, else the product's own cut-out where it was cut from it.
 */
export function cutoutOf(p, view) {
  if (!view) return null;
  const boxed = view.variant !== 'cutout' && view.variant !== 'whole' && view.base === 'photo';
  const tile = view.variant === 'cutout' && p.asset_type === 'tile';
  if (!boxed && !tile) return null;
  const e = (p.images || [])[view.image || 0];
  if (e && e.whole) return { variant: 'whole', crop: [0, 0, 1, 1], image: view.image || 0, base: 'whole' };
  if (boxed && p.asset_type && p.asset_type.startsWith('cutout') && (p.image || 0) === (view.image || 0)) {
    return { ...CUTOUT };
  }
  return null;
}

/**
 * What "Other picture" and the shelf badge cycle through after the shelf's
 * own picture: every picture of the product (fabric close-ups and page text
 * aside) when there is more than one, and the cut-out of the shelf picture
 * when that picture is a box or a crop tile. Each is { pick, label }; `pick`
 * is what shelfView takes as its picture.
 */
export function pictureChoices(p, local, type) {
  const keep = ((p && p.images) || []).map((e, i) => ({ pick: i, label: e.type || 'whole page', entry: e }))
    .filter((x) => !isDetail(x.entry));
  const out = keep.length > 1 ? keep : [];
  if (p && cutoutOf(p, shelfView(p, local, undefined, type))) out.push({ pick: 'cut', label: 'cut-out' });
  return out;
}

export const sameView = (a, b) => a.variant === b.variant && a.image === b.image && a.base === b.base
  && JSON.stringify(a.crop) === JSON.stringify(b.crop);

/**
 * Several garments in the picture — a listing-grid page, an all-colours fan.
 * Never a single product: off the shelf and back in Review until a box she
 * drew cuts one garment out of it.
 */
export function isSeveral(p, local) {
  if (!p.several || !p.several.length) return false;
  const c = effectiveChoice(p, local);
  if (c && c.choice === 'custom') return false;
  // a listing-grid cell is one cell of the page by construction: a tap on it
  // is her decision that it is one garment, and it stands
  const l = local && local[p.product_id];
  return !(l && l.choice && p.parent_id && /-C\d+$/.test(p.product_id));
}

/** Sent back to Review — from the shelf, the canvas, or by the build — and not decided since. */
export const isBackToReview = (p, local) => !!effectiveChoice(p, local)?.review;

/** Why it is back in Review, in words. */
export function reviewReason(p, local) {
  const r = effectiveChoice(p, local)?.review;
  return typeof r === 'string' ? r : (r ? 'sent back to Review' : '');
}

/**
 * Removed by her — on the shelf, the canvas or in Review — as opposed to
 * hidden by the build (a grid page once its cells exist, a UNIQLO style's
 * other pictures). Only these are listed under Removed.
 */
export function isRemoved(p, local) {
  const l = local && local[p.product_id];
  if (l && l.hidden) return true;
  return !!p.removed && effectiveChoice(p, local)?.hidden === true;
}

/**
 * The two shelf actions, as the choice they leave behind. Nothing is deleted:
 * both are entries in asset-choices.json, and the slot, the boxes cut out of
 * the picture and "not a duplicate" are kept.
 */
export function removeChoice(prev) {
  const { choice, box, base, image, review, restored, later, ...keep } = prev || {};
  return { ...keep, hidden: true };
}
export function backToReviewChoice(prev, reason = 'sent back from the shelf') {
  const { choice, box, base, image, hidden, restored, later, ...keep } = prev || {};
  return { ...keep, review: reason };
}
/** Out of Removed: back in Review, undecided, whatever the catalogue had filed. */
export function restoreChoice(prev) {
  const { hidden, choice, box, base, image, later, ...keep } = prev || {};
  return { ...keep, review: 'restored from Removed', restored: true };
}

/**
 * The build sends products back to Review (data/review-sends.json): a re-cut
 * to look at again, page text found in the picture. A decision kept in this
 * browser would otherwise hide that, so each send is applied here once — the
 * browser remembers the last version it applied — and only to what was
 * decided before it. Returns { n, version }.
 */
export function applyReviewSends(local, sends, applied = '') {
  let n = 0, version = applied || '';
  if (!sends || !Array.isArray(sends.versions)) return { n, version };
  for (const v of sends.versions) {
    if (!v.version || v.version <= version) continue;
    for (const [pid, reason] of Object.entries(v.products || {})) {
      const l = local[pid];
      if (!l) continue;                  // nothing decided here: the catalogue says it
      local[pid] = backToReviewChoice(l, reason);
      n++;
    }
    version = v.version;
  }
  return { n, version };
}

/** Marked as another row again. Kept, hidden from the shelf, until she says otherwise. */
export function isDuplicate(p, local) {
  if (!p.duplicate_of) return false;
  const l = local && local[p.product_id];
  return !(l && l.notDuplicate);
}

export function effectiveChoice(p, local) {
  const l = local && local[p.product_id];
  if (l && (l.hidden || l.choice || l.review)) return l;
  // sent back to Review by the build (a re-cut, page text found in the
  // picture): undecided again until she decides
  if (p.review && !(l && l.restored)) return { review: p.review };
  if (p.hidden && !(l && l.restored)) return { hidden: true };
  // the catalogue's choice is on the picture it names (asset_image), not
  // always the first: without it a box filed on picture 2 was read off picture 1
  if (p.choice) return { choice: p.choice, box: p.custom_box, image: p.image || 0, base: p.base };
  return null;
}

/**
 * The gate. By default the shelf shows clean flat cut-outs plus everything
 * that has been reviewed; unreviewed pieces wait in Review until asked for.
 * A hidden product never shows, and a product without a full photo cannot be
 * reviewed, so its cut-out is what there is.
 */
export function onShelf(p, local, showUnreviewed) {
  const c = effectiveChoice(p, local);
  if (c?.hidden) return false;
  if (c?.review) return false;                 // back in Review: off the shelf until decided
  if (isDuplicate(p, local) || isSeveral(p, local)) return false;
  if (p.clean || (c && c.choice)) return true;
  return !!showUnreviewed;
}

export function isReviewed(p, local) {
  const c = effectiveChoice(p, local);
  if (c?.review) return false;
  // taking a several-garment picture whole was the mistake; only a box counts
  if (isSeveral(p, local)) return !!(c && c.hidden);
  return !!(c && (c.hidden || c.choice));
}

export function filterProducts(products, f, local) {
  const q = (f.search || '').trim().toLowerCase();
  return products.filter((p) => {
    if (!onShelf(p, local, f.showUnreviewed)) return false;
    if (f.slot && p.slot !== f.slot) return false;
    if (f.assetType && !pictureOfType(p, f.assetType)) return false;
    if (f.brand && p.brand !== f.brand) return false;
    if (f.weight && String(p.weight) !== String(f.weight)) return false;
    if (f.formality && String(p.formality) !== String(f.formality)) return false;
    if (f.family && !(p.colours || []).some((c) => c.family === f.family)) return false;
    if (q) {
      const hay = [p.product_id, p.brand, p.product_name, p.garment_type, p.slot,
        ...(p.colours || []).map((c) => c.name)].join(' ').toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });
}

/** counts for the casual→dressy by light→heavy grid */
export function matrixCounts(products) {
  const cells = {};
  for (const p of products) {
    if (!p.formality || !p.weight) continue;
    const k = `${p.formality}:${p.weight}`;
    cells[k] = (cells[k] || 0) + 1;
  }
  return cells;
}
