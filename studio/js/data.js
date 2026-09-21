// Where the desk gets its items from.
//
// The UI never reads a file path or a CSV column. It asks a source for
// products and looks, and gets the same shape back whatever the source is.
// Today that is the static catalogue built by content/tools/build_studio.py;
// later it can be a signed-in user's own wardrobe, and nothing above this line
// has to change.

/** @typedef {{products: Array, inspiration: Array, meta: Object}} Catalogue */

export function createStaticSource(base = '.') {
  const url = (p) => `${base.replace(/\/$/, '')}/${p}`;
  return {
    name: 'catalogue',
    /** @returns {Promise<Catalogue>} */
    async load() {
      const [products, inspiration, meta] = await Promise.all([
        fetch(url('data/products.json')).then((r) => r.json()),
        fetch(url('data/inspiration.json')).then((r) => r.json()),
        fetch(url('data/meta.json')).then((r) => r.json()).catch(() => ({})),
      ]);
      return { products, inspiration, meta };
    },
    assetUrl: (p) => url(p.asset),
    thumbUrl: (p) => url(p.thumb),
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
    inspirationUrl: urls.inspirationUrl || ((i) => i.image),
    inspirationThumbUrl: urls.inspirationThumbUrl || ((i) => i.thumb),
  };
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
  search: '', showWeak: false,
});

export function filterProducts(products, f) {
  const q = (f.search || '').trim().toLowerCase();
  return products.filter((p) => {
    if (!f.showWeak && p.asset_quality === 'weak') return false;
    if (f.slot && p.slot !== f.slot) return false;
    if (f.assetType && p.asset_type !== f.assetType) return false;
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
