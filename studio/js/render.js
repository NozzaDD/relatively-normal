// Draws a board onto a canvas at any size. The live preview is DOM, this is
// the export, and both read the same model — so the file you save is the board
// you arranged.
//
// The rules come from content/boards/style-spec.md part B5:
//   one border in the whole board — the inspiration image and any crop tile
//   share a white mat and a thin warm keyline; cut-outs have no border at all
//   and no box behind them, only a shadow taken from their own alpha.

import { GROUND, KEYLINE, INK, DEFAULT_FRAME, stacked, elementBox, labelOrder, swatchStrip,
  pixelAspect } from './model.js';

export const metrics = (W, H) => ({
  margin: Math.round(W * 0.055),
  title: Math.round(W * 0.052),
  line: Math.round(W * 0.0195),
  mat: Math.max(2, Math.round(W * 0.0065)),
  strip: Math.round(W * 0.026),
  disc: Math.round(W * 0.013),
  shadow: Math.round(W * 0.013),
});

/**
 * Framed: the inspiration image, a page tile, or a box drawn on a photograph.
 * A box drawn on a cut-out keeps its transparency, so it is not framed.
 */
export function isTile(kind, assetType, variant, base) {
  if (kind === 'inspiration') return true;
  if (base === 'whole' || base === 'asset') return false;
  return assetType === 'tile' || (!!variant && variant !== 'cutout');
}

function roundedRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  if (r <= 0) { ctx.rect(x, y, w, h); return; }
  const rr = Math.min(r, w / 2, h / 2);
  ctx.moveTo(x + rr, y);
  ctx.arcTo(x + w, y, x + w, y + h, rr);
  ctx.arcTo(x + w, y + h, x, y + h, rr);
  ctx.arcTo(x, y + h, x, y, rr);
  ctx.arcTo(x, y, x + w, y, rr);
  ctx.closePath();
}

/** The part of the source image to draw: all of it, or the element's crop. */
function sourceRect(img, el) {
  const iw = img.naturalWidth || img.width, ih = img.naturalHeight || img.height;
  const [x, y, w, h] = el.crop || [0, 0, 1, 1];
  return [x * iw, y * ih, w * iw, h * ih];
}

/** The mat a framed picture gets, in pixels: the preview and the file share it. */
export function matOf(framed, frame, m) {
  return framed && (frame || DEFAULT_FRAME).mat ? m.mat : 0;
}

function drawImageEl(ctx, img, el, W, H, m, framed, frame) {
  // proportions from the pixels being drawn, never from a stored number
  const aspect = pixelAspect(img.naturalWidth || img.width, img.naturalHeight || img.height, el.crop) || el.aspect;
  const mat = matOf(framed, frame, m);
  const b = elementBox({ ...el, aspect }, W, H, mat);
  const src = sourceRect(img, el);
  ctx.save();
  ctx.translate(b.cx, b.cy);
  if (el.rot) ctx.rotate((el.rot * Math.PI) / 180);
  if (el.flip) ctx.scale(-1, 1);
  if (framed) {
    const f = frame || DEFAULT_FRAME;
    const radius = (f.radius || 0) * (W / 1080);
    roundedRect(ctx, -b.w / 2, -b.h / 2, b.w, b.h, radius);
    if (f.mat) { ctx.fillStyle = '#ffffff'; ctx.fill(); }
    ctx.save();
    ctx.clip();
    ctx.drawImage(img, ...src, -b.w / 2 + mat, -b.h / 2 + mat, b.w - mat * 2, b.h - mat * 2);
    ctx.restore();
    if (f.border) {
      ctx.lineWidth = Math.max(1, W / 1400);
      ctx.strokeStyle = KEYLINE;
      roundedRect(ctx, -b.w / 2, -b.h / 2, b.w, b.h, radius);
      ctx.stroke();
    }
  } else {
    ctx.shadowColor = 'rgba(58,50,42,0.22)';
    ctx.shadowBlur = m.shadow;
    ctx.shadowOffsetX = m.shadow * 0.45;
    ctx.shadowOffsetY = m.shadow * 0.65;
    ctx.drawImage(img, ...src, -b.w / 2, -b.h / 2, b.w, b.h);
  }
  ctx.restore();
}

/**
 * @param images  {uid: HTMLImageElement|ImageBitmap} already decoded
 */
export function drawBoard(ctx, board, productsById, images, W, H) {
  const m = metrics(W, H);
  ctx.save();
  ctx.fillStyle = board.ground || GROUND;
  ctx.fillRect(0, 0, W, H);

  let y = m.margin;
  if (board.showTitle && board.title) {
    ctx.fillStyle = INK;
    ctx.textBaseline = 'top';
    ctx.font = `600 ${m.title}px "EB Garamond", Georgia, serif`;
    ctx.fillText(board.title, m.margin, y);
    y += Math.round(m.title * 1.16);
  }
  if (board.showLine && board.line) {
    ctx.fillStyle = '#5C544C';
    ctx.textBaseline = 'top';
    ctx.font = `400 ${m.line}px Inter, system-ui, sans-serif`;
    ctx.fillText(board.line, m.margin, y);
  }

  for (const el of stacked(board)) {
    const img = images[el.uid];
    if (!img) continue;
    const p = el.kind === 'product' ? productsById[el.product_id] : null;
    drawImageEl(ctx, img, el, W, H, m, isTile(el.kind, p?.asset_type, el.variant, el.base), board.frame);
  }

  if (board.showSwatches) {
    const chips = swatchStrip(board, productsById);
    if (chips.length) {
      const total = chips.reduce((a, c) => a + (c.share || 1), 0) || 1;
      let x = m.margin;
      const top = H - m.margin - m.strip;
      const avail = W - m.margin * 2;
      chips.forEach((c, i) => {
        const w = Math.round((avail * (c.share || 1)) / total);
        ctx.fillStyle = c.hex;
        ctx.fillRect(x, top, i === chips.length - 1 ? W - m.margin - x : w - 2, m.strip);
        x += w;
      });
    }
  }

  if (board.showLabels) {
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    labelOrder(board).forEach((el, i) => {
      const b = elementBox(el, W, H);
      const cx = b.x + b.w - m.disc;
      const cy = b.y + m.disc;
      ctx.beginPath();
      ctx.arc(cx, cy, m.disc, 0, Math.PI * 2);
      ctx.fillStyle = '#ffffff';
      ctx.fill();
      ctx.lineWidth = Math.max(1, W / 1600);
      ctx.strokeStyle = KEYLINE;
      ctx.stroke();
      ctx.fillStyle = INK;
      ctx.font = `600 ${Math.round(m.disc * 1.15)}px Inter, system-ui, sans-serif`;
      ctx.fillText(String(i + 1), cx, cy + m.disc * 0.05);
    });
    ctx.textAlign = 'start';
  }
  ctx.restore();
}
