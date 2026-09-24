// Saving. Two files with one name: the image, and the info file that can
// reopen the board and be pasted under it.
//
// Empty stays empty. Every field here is copied from the catalogue or from the
// board; nothing is filled in with a plausible guess.

import { FORMATS, dateSlug, labelOrder, swatchStrip } from './model.js';
import { drawBoard } from './render.js';

/** The picture an element shows: its asset, a screenshot, or a whole cut-out. */
export function elementUrl(source, p, el) {
  if (!el.crop) return source.assetUrl(p);
  if (el.base === 'whole') return source.wholeUrl(p, el.image || 0) || source.assetUrl(p);
  if (el.base === 'asset') return source.assetUrl(p);
  return source.fullUrl(p, el.image || 0);
}

export function loadImage(src) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.decoding = 'async';
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error(`image failed: ${src}`));
    img.src = src;
  });
}

/** Decode every image a board needs, at full size. */
export async function loadBoardImages(board, source, productsById, inspById) {
  const out = {};
  await Promise.all(board.elements.map(async (el) => {
    try {
      if (el.kind === 'inspiration') {
        const i = inspById[el.inspiration_id];
        if (i) out[el.uid] = await loadImage(source.inspirationUrl(i));
      } else {
        const p = productsById[el.product_id];
        // a crop is drawn from the image it was drawn on: a screenshot, or a
        // whole cut-out, which keeps its transparency
        if (p) out[el.uid] = await loadImage(elementUrl(source, p, el));
      }
    } catch (e) { /* a missing image just does not draw */ }
  }));
  return out;
}

export async function renderBoardCanvas(board, productsById, images, scale = 1) {
  const f = FORMATS[board.format] || FORMATS.portrait;
  const W = Math.round(f.exportW * scale);
  const H = Math.round(f.exportH * scale);
  const c = document.createElement('canvas');
  c.width = W; c.height = H;
  const ctx = c.getContext('2d');
  ctx.imageSmoothingQuality = 'high';
  if (document.fonts?.ready) { try { await document.fonts.ready; } catch (e) { /* ignore */ } }
  drawBoard(ctx, board, productsById, images, W, H);
  return c;
}

export const canvasToBlob = (canvas, type, quality) =>
  new Promise((res) => canvas.toBlob(res, type, quality));

// --------------------------------------------------------------- the info file
const CURRENCIES = ['CHF', 'EUR', 'USD', 'GBP', '€', '£', '$', 'kr', 'SEK', 'DKK'];

/** Split "CHF 156" into a currency and a number, and give up cleanly if unsure. */
export function parsePrice(raw) {
  const s = String(raw || '').trim();
  if (!s) return { price: '', currency: '' };
  const cur = CURRENCIES.find((c) => s.toUpperCase().startsWith(c.toUpperCase()) ||
    s.toUpperCase().endsWith(c.toUpperCase()) || s.includes(c));
  if (!cur) return { price: s, currency: '' };
  const num = s.replace(cur, '').replace(/ /g, ' ').trim();
  return num ? { price: num, currency: cur } : { price: s, currency: '' };
}

export function buildInfo(board, productsById, inspById, { date = new Date() } = {}) {
  const f = FORMATS[board.format] || FORMATS.portrait;
  const insp = board.inspiration ? inspById[board.inspiration] : null;
  const pieces = labelOrder(board).map((el, i) => {
    const p = productsById[el.product_id] || {};
    const c0 = (p.colours || [])[0] || {};
    const { price, currency } = parsePrice(p.price);
    return {
      label: i + 1,
      product_id: el.product_id,
      slot: p.slot || '',
      garment_type: p.garment_type || '',
      brand: p.brand || '',
      brand_confidence: p.brand_confidence || '',
      brand_role: p.brand_role || '',
      product_name: p.product_name || '',
      product_name_confidence: p.product_name_confidence || '',
      colour_name: c0.name || '',
      colour_hex: c0.hex || '',
      colour_confidence: p.colour_confidence || '',
      material: p.material || '',
      material_confidence: p.material_confidence || '',
      price,
      currency,
      price_confidence: p.price_confidence || '',
      product_url: p.product_url || '',
      product_url_confidence: p.product_url_confidence || '',
      shop_product_id: p.shop_product_id || '',
      shop_product_id_confidence: p.shop_product_id_confidence || '',
      image_source: p.image_source || '',
      // a recoloured piece is not the brand's photo of that colour — say so
      colour_simulated: !!p.recoloured,
      recolour_source: p.recolour_source || '',
      image_variant: el.variant || 'cutout',
      image_crop: el.crop ? el.crop.map(round4) : null,
      image_index: el.image || 0,
      image_base: el.base || 'photo',
      // which of the product's pictures this piece shows, for reopening
      image_type: ((p.images || [])[el.image || 0] || {}).type || '',
      // a piece cut out of another product's screenshot carries its parent
      parent_id: p.parent_id || '',
      source_image: (p.images && p.images[el.image || 0] && p.images[el.image || 0].source) || '',
      placement: {
        x: round4(el.x), y: round4(el.y), w: round4(el.w),
        rotation: el.rot || 0, flip: !!el.flip, layer: el.z, aspect: round4(el.aspect),
      },
    };
  });
  const inspEl = board.elements.find((e) => e.kind === 'inspiration');
  return {
    kind: 'relatively-normal.outfit',
    version: 1,
    title: board.title || '',
    line: board.line || '',
    format: board.format,
    canvas: { width: f.exportW, height: f.exportH, ground: board.ground,
      frame: board.frame || null },
    date: isoDate(date),
    slug: dateSlug(board.title, date),
    elements_shown: {
      title: !!board.showTitle, line: !!board.showLine,
      swatch_strip: !!board.showSwatches, numbered_labels: !!board.showLabels,
      palette_strip: !!(board.showPalette && board.palette),
    },
    // the palette chosen as the board's inspiration: a working aid, recorded
    // so the outfit can be reopened with it and read against it later
    palette: board.palette ? {
      id: board.palette.id,
      name: board.palette.name,
      category: board.palette.category,
      group: board.palette.group || '',
      colours: (board.palette.colours || []).map((c) => ({
        hex: c.hex, name: c.name, role: c.role, share: c.share, placement: c.placement || null,
      })),
      source: board.palette.source || null,
      ...(board.palette.derived ? { derived: true, derived_from: board.palette.derived_from } : {}),
    } : null,
    inspiration: insp ? {
      inspiration_id: insp.inspiration_id,
      path: insp.source_path,
      house: insp.house || '',
      house_confidence: insp.house_confidence || '',
      image_source: insp.image_source || '',
      placement: inspEl ? {
        x: round4(inspEl.x), y: round4(inspEl.y), w: round4(inspEl.w),
        rotation: inspEl.rot || 0, flip: !!inspEl.flip, layer: inspEl.z,
        aspect: round4(inspEl.aspect),
      } : null,
    } : null,
    swatch_strip: swatchStrip(board, productsById).map((c) => ({ hex: c.hex, name: c.name })),
    pieces,
  };
}

const round4 = (v) => Math.round((Number(v) || 0) * 10000) / 10000;
const isoDate = (d) => [d.getFullYear(), String(d.getMonth() + 1).padStart(2, '0'),
  String(d.getDate()).padStart(2, '0')].join('-');

export function buildMarkdown(info) {
  const L = [];
  L.push(`# ${info.title || info.slug}`, '');
  if (info.line) L.push(info.line, '');
  if (info.inspiration) {
    const h = info.inspiration.house
      ? `${info.inspiration.house} (${info.inspiration.house_confidence})` : 'house not legible';
    L.push(`*Inspiration: ${h} — ${info.inspiration.image_source}.*`, '');
  }
  if (info.palette) {
    const cat = { season: 'colour season', family: 'colour family', trend: 'AW26/27' }[info.palette.category]
      || info.palette.category;
    const src = info.palette.source ? ` — ${info.palette.source.confidence}` : '';
    L.push(`*Palette: ${info.palette.name} (${cat}${src}).*`, '');
  }
  L.push('| # | Brand | Piece | Colour | Price | Link |', '|---|---|---|---|---|---|');
  for (const p of info.pieces) {
    const price = [p.currency, p.price].filter(Boolean).join(' ');
    const link = p.product_url ? `[link](${p.product_url})` : '';
    const colour = p.colour_simulated ? `${p.colour_name} (colour simulated)` : p.colour_name;
    L.push(`| ${p.label} | ${p.brand} | ${p.product_name || p.garment_type} | ${colour} | ${price} | ${link} |`);
  }
  L.push('');
  const simulated = info.pieces.filter((p) => p.colour_simulated);
  if (simulated.length) {
    L.push('**Colour simulated:** ' + simulated.map((p) => `${p.label}`).join(', ')
      + ' — recoloured from the brand\'s photo of another colour, not the brand\'s photo of this one. '
      + 'Disclose it, or swap in the real photo before publishing.', '');
  }
  const missing = info.pieces.filter((p) => !p.brand || p.brand_confidence === 'guessed');
  if (missing.length) {
    L.push('**Confirm before publishing:** ' + missing
      .map((p) => `${p.label} (${p.brand ? p.brand + ', guessed' : 'brand unknown'})`).join(', '), '');
  }
  return L.join('\n');
}

// ------------------------------------------------------- PNG metadata (iTXt)
const CRC_TABLE = (() => {
  const t = new Uint32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    t[n] = c >>> 0;
  }
  return t;
})();

function crc32(bytes) {
  let c = 0xffffffff;
  for (let i = 0; i < bytes.length; i++) c = CRC_TABLE[(c ^ bytes[i]) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}

/** Put the info JSON inside the PNG as an iTXt chunk. The .json file stays the
 *  source of truth; this is only so a stray PNG can still say what it is. */
export async function pngWithMetadata(blob, keyword, text) {
  const buf = new Uint8Array(await blob.arrayBuffer());
  if (buf.length < 8 || buf[1] !== 0x50 || buf[2] !== 0x4e || buf[3] !== 0x47) return blob;
  const enc = new TextEncoder();
  const kw = enc.encode(keyword);
  const txt = enc.encode(text);
  const data = new Uint8Array(kw.length + 5 + txt.length);
  data.set(kw, 0);
  // keyword\0 compressionFlag compressionMethod languageTag\0 translatedKeyword\0
  data[kw.length] = 0; data[kw.length + 1] = 0; data[kw.length + 2] = 0;
  data[kw.length + 3] = 0; data[kw.length + 4] = 0;
  data.set(txt, kw.length + 5);
  const type = enc.encode('iTXt');
  const chunk = new Uint8Array(12 + data.length);
  const dv = new DataView(chunk.buffer);
  dv.setUint32(0, data.length);
  chunk.set(type, 4);
  chunk.set(data, 8);
  const crcInput = new Uint8Array(type.length + data.length);
  crcInput.set(type, 0); crcInput.set(data, type.length);
  dv.setUint32(8 + data.length, crc32(crcInput));
  // IHDR is always the first chunk: 8 byte signature + 4 length + 4 type + 13 + 4 crc
  const at = 8 + 25;
  const out = new Uint8Array(buf.length + chunk.length);
  out.set(buf.subarray(0, at), 0);
  out.set(chunk, at);
  out.set(buf.subarray(at), at + chunk.length);
  return new Blob([out], { type: 'image/png' });
}

// ------------------------------------------------------------------ handing over
export function downloadFile(file) {
  const url = URL.createObjectURL(file);
  const a = document.createElement('a');
  a.href = url;
  a.download = file.name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 4000);
}

/** Share sheet first — that is how the files reach Photos, Files or Working
 *  Copy on an iPad. Plain downloads when sharing is not available or refused. */
export async function handOver(files, { title }) {
  const canShare = typeof navigator !== 'undefined' && navigator.canShare
    && navigator.canShare({ files });
  if (canShare) {
    try {
      await navigator.share({ files, title });
      return 'shared';
    } catch (err) {
      if (err && err.name === 'AbortError') return 'cancelled';
    }
  }
  files.forEach(downloadFile);
  return 'downloaded';
}
