// Draws a board onto a canvas at any size. The live preview is DOM, this is
// the export, and both read the same model — so the file you save is the board
// you arranged.
//
// The rules come from content/boards/style-spec.md part B5:
//   one border in the whole board — the inspiration image and any crop tile
//   share a white mat and a thin warm keyline; cut-outs have no border at all
//   and no box behind them, only a shadow taken from their own alpha.

import { GROUND, KEYLINE, INK, stacked, elementBox, labelOrder, swatchStrip } from './model.js';

export const metrics = (W, H) => ({
  margin: Math.round(W * 0.055),
  title: Math.round(W * 0.052),
  line: Math.round(W * 0.0195),
  mat: Math.max(2, Math.round(W * 0.0065)),
  strip: Math.round(W * 0.026),
  disc: Math.round(W * 0.013),
  shadow: Math.round(W * 0.013),
});

export function isTile(kind, assetType) {
  return kind === 'inspiration' || assetType === 'tile';
}

function drawImageEl(ctx, img, el, W, H, m, framed) {
  const b = elementBox(el, W, H);
  ctx.save();
  ctx.translate(b.cx, b.cy);
  if (el.rot) ctx.rotate((el.rot * Math.PI) / 180);
  if (el.flip) ctx.scale(-1, 1);
  if (framed) {
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(-b.w / 2, -b.h / 2, b.w, b.h);
    ctx.drawImage(img, -b.w / 2 + m.mat, -b.h / 2 + m.mat, b.w - m.mat * 2, b.h - m.mat * 2);
    ctx.lineWidth = Math.max(1, W / 1400);
    ctx.strokeStyle = KEYLINE;
    ctx.strokeRect(-b.w / 2, -b.h / 2, b.w, b.h);
  } else {
    ctx.shadowColor = 'rgba(58,50,42,0.22)';
    ctx.shadowBlur = m.shadow;
    ctx.shadowOffsetX = m.shadow * 0.45;
    ctx.shadowOffsetY = m.shadow * 0.65;
    ctx.drawImage(img, -b.w / 2, -b.h / 2, b.w, b.h);
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
    drawImageEl(ctx, img, el, W, H, m, isTile(el.kind, p?.asset_type));
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
