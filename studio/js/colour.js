// Pure colour maths. No DOM. Used for ranking only — never for deciding
// whether something is allowed on a board. That decision is the stylist's.

export function hexToRgb(hex) {
  const h = String(hex || '').replace('#', '').trim();
  if (h.length !== 6) return null;
  const v = parseInt(h, 16);
  if (Number.isNaN(v)) return null;
  return [(v >> 16) & 255, (v >> 8) & 255, v & 255];
}

const srgbToLinear = (c) => {
  c /= 255;
  return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
};

// OKLab — perceptually even enough for "which of these is closest", and cheap.
export function hexToOklab(hex) {
  const rgb = hexToRgb(hex);
  if (!rgb) return null;
  const [r, g, b] = rgb.map(srgbToLinear);
  const l = Math.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b);
  const m = Math.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b);
  const s = Math.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b);
  return [
    0.2104542553 * l + 0.793617785 * m - 0.0040720468 * s,
    1.9779984951 * l - 2.428592205 * m + 0.4505937099 * s,
    0.0259040371 * l + 0.7827717662 * m - 0.808675766 * s,
  ];
}

export function oklabDistance(a, b) {
  if (!a || !b) return Infinity;
  const dl = a[0] - b[0], da = a[1] - b[1], db = a[2] - b[2];
  return Math.sqrt(dl * dl + da * da + db * db);
}

/** Distance from a product to the nearest of a look's colours. */
export function productDistanceToLook(product, lookLabs) {
  if (!lookLabs || !lookLabs.length) return Infinity;
  let best = Infinity;
  for (const c of product.colours || []) {
    const lab = hexToOklab(c.hex);
    for (const ll of lookLabs) {
      const d = oklabDistance(lab, ll);
      if (d < best) best = d;
    }
  }
  return best;
}

/**
 * Rank products by how close they come to a look's colours.
 * Returns a new array; ties keep the incoming order.
 */
export function rankByLook(products, look) {
  const labs = (look?.colours || []).map((c) => hexToOklab(c.hex)).filter(Boolean);
  return products
    .map((p, i) => ({ p, i, d: productDistanceToLook(p, labs) }))
    .sort((x, y) => x.d - y.d || x.i - y.i)
    .map((x) => x.p);
}

/** Merge colours that are near neighbours, summing their shares. */
export function mergeColours(list, tol = 0.055) {
  const out = [];
  for (const c of list) {
    const lab = hexToOklab(c.hex);
    const hit = out.find((o) => oklabDistance(lab, o._lab) <= tol);
    if (hit) hit.share += c.share || 0;
    else out.push({ hex: c.hex, name: c.name || '', share: c.share || 0, _lab: lab });
  }
  out.sort((a, b) => b.share - a.share);
  return out.map(({ hex, name, share }) => ({ hex, name, share }));
}

export function readableInk(hex) {
  const rgb = hexToRgb(hex) || [255, 255, 255];
  const lum = 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2];
  return lum < 150 ? '#ffffff' : '#1e1a16';
}
