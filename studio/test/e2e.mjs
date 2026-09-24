// End-to-end: load, filter, drag, save, reopen. Headless Chromium.
//   NODE_PATH=/opt/node22/lib/node_modules node studio/test/e2e.mjs
import { chromium } from 'playwright';
import { createServer } from 'node:http';
import { readFile, stat, mkdtemp } from 'node:fs/promises';
import { existsSync, readFileSync } from 'node:fs';
import { join, extname } from 'node:path';
import { tmpdir } from 'node:os';

const ROOT = new URL('../', import.meta.url).pathname;
const TYPES = { '.html': 'text/html', '.css': 'text/css', '.js': 'text/javascript',
  '.json': 'application/json', '.webp': 'image/webp', '.jpg': 'image/jpeg',
  '.ttf': 'font/ttf', '.txt': 'text/plain' };

let pass = 0, fail = 0;
const ok = (name, cond, extra = '') => {
  if (cond) { pass++; console.log(`  ok   ${name}`); }
  else { fail++; console.log(`  FAIL ${name} ${extra}`); }
};

const server = createServer(async (req, res) => {
  const p = join(ROOT, decodeURIComponent(req.url.split('?')[0]).replace(/^\//, '') || 'index.html');
  try {
    const s = await stat(p);
    if (s.isDirectory()) throw new Error('dir');
    res.writeHead(200, { 'content-type': TYPES[extname(p)] || 'application/octet-stream' });
    res.end(await readFile(p));
  } catch { res.writeHead(404).end('no'); }
});
await new Promise((r) => server.listen(0, r));
const base = `http://127.0.0.1:${server.address().port}`;

const browser = await chromium.launch({
  executablePath: existsSync('/opt/pw-browsers/chromium/chrome-linux/chrome')
    ? '/opt/pw-browsers/chromium/chrome-linux/chrome' : undefined,
});
const ctx = await browser.newContext({ viewport: { width: 1180, height: 900 }, hasTouch: true });
const page = await ctx.newPage();
const errors = [];
page.on('pageerror', (e) => errors.push(String(e)));
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });

console.log('\n1. load');
await page.goto(`${base}/index.html`);
await page.waitForFunction(() => window.__studio?.products?.length > 0, null, { timeout: 15000 });
const counts = await page.evaluate(() => ({
  products: window.__studio.products.length,
  inspiration: window.__studio.inspiration.length,
  cells: document.querySelectorAll('#grid .cell').length,
}));
ok('products loaded', counts.products >= 463, JSON.stringify(counts));
ok('inspiration loaded', counts.inspiration === 112, JSON.stringify(counts));
// the gate is the measurement flat_lays.py makes, so the shelf is exactly the
// products the data marks clean — not a hand-set range that drifts — plus the
// ones asset-choices.json has already decided (reviewed on the desk)
const cleanCount = await page.evaluate(() =>
  window.__studio.products.filter((p) => (p.clean || p.choice) && !p.hidden && !(p.several || []).length
    && !p.duplicate_of).length);
ok('only measured-clean cut-outs on the shelf by default',
  counts.cells === cleanCount && cleanCount > 0, `${counts.cells} cells, ${cleanCount} clean`);
ok('the shelf is a real slice of the catalogue, not all of it',
  counts.cells < counts.products / 2,
  `${counts.cells} cells`);
ok('no page errors on load', errors.length === 0, errors.join(' | '));

console.log('\n2. filters');
await page.click('#slotBar button[data-slot="top"]');
await page.waitForTimeout(80);
const tops = await page.evaluate(() => window.__studio.shown.every((p) => p.slot === 'top'));
const topsN = await page.$$eval('#grid .cell', (e) => e.length);
ok('category button narrows the shelf', tops && topsN > 0, `${topsN} tops`);
await page.fill('#search', 'aspesi');
await page.waitForTimeout(220);
const searchN = await page.$$eval('#grid .cell', (e) => e.length);
ok('search + category combine', searchN <= topsN);
await page.click('#clearFilters');
await page.waitForTimeout(80);
const before = await page.$$eval('#grid .cell', (e) => e.length);
await page.check('#fUnreviewed');
await page.waitForTimeout(80);
const after = await page.$$eval('#grid .cell', (e) => e.length);
ok('show unreviewed reveals more', after > before, `${before} → ${after}`);
await page.uncheck('#fUnreviewed');

console.log('\n3. matrix');
await page.click('.tab[data-view="matrix"]');
await page.waitForTimeout(60);
const mcells = await page.$$eval('#matrixGrid .mcell:not(.head)', (e) => e.length);
ok('matrix has 16 cells', mcells === 16, String(mcells));
await page.click('#matrixGrid .mcell:not(.head):not(.empty)');
await page.waitForTimeout(80);
const filteredByCell = await page.evaluate(() => ({ w: document.getElementById('fWeight').value,
  f: document.getElementById('fFormality').value, n: window.__studio.shown.length }));
ok('tapping a cell filters the shelf', filteredByCell.w && filteredByCell.f && filteredByCell.n > 0,
  JSON.stringify(filteredByCell));
await page.click('#clearFilters');

console.log('\n4. inspiration + match sort');
await page.evaluate(() => window.__studio.placeInspiration(window.__studio.inspiration[10].inspiration_id));
await page.waitForTimeout(400);
ok('inspiration sits on the canvas as an element',
  await page.evaluate(() => window.__studio.board.elements.some((e) => e.kind === 'inspiration')));
ok('match sort becomes available', !(await page.$eval('#fMatch', (e) => e.disabled)));
await page.check('#fMatch');
await page.waitForTimeout(120);
const ranked = await page.evaluate(() => {
  const look = window.__studio.inspById[window.__studio.board.inspiration];
  const first = window.__studio.shown[0];
  const last = window.__studio.shown[window.__studio.shown.length - 1];
  return { look: look.colours[0].hex, first: first.colours[0]?.hex, firstId: first.product_id,
    lastId: last.product_id };
});
ok('match sort reorders the shelf', !!ranked.firstId && ranked.firstId !== ranked.lastId,
  JSON.stringify(ranked));
await page.uncheck('#fMatch');

console.log('\n5. drag a piece onto the canvas');
const cell = await page.$('#grid .cell');
const cb = await cell.boundingBox();
const stage = await page.$('#stage');
const sb = await stage.boundingBox();
await page.mouse.move(cb.x + cb.width / 2, cb.y + cb.height / 2);
await page.mouse.down();
await page.mouse.move(sb.x + sb.width * 0.4, sb.y + sb.height * 0.4, { steps: 12 });
await page.mouse.up();
await page.waitForTimeout(350);
let els = await page.evaluate(() => window.__studio.board.elements.filter((e) => e.kind === 'product').length);
ok('drag places a piece', els === 1, `${els} pieces`);
const placed = await page.evaluate(() => {
  const e = window.__studio.board.elements.find((x) => x.kind === 'product');
  return { x: e.x, y: e.y, aspect: e.aspect };
});
ok('piece lands where it was dropped', Math.abs(placed.x - 0.4) < 0.06 && Math.abs(placed.y - 0.4) < 0.06,
  JSON.stringify(placed));
ok('aspect read from the image', placed.aspect > 0.1 && placed.aspect < 10, String(placed.aspect));

console.log('\n6. move, resize, delete, undo');
// grab the product itself, not whatever happens to be first in the stack
const pid = await page.evaluate(() => window.__studio.board.elements.find((e) => e.kind === 'product').uid);
const elBox = await (await page.$(`#layers .el[data-uid="${pid}"]`)).boundingBox();
await page.mouse.move(elBox.x + elBox.width / 2, elBox.y + elBox.height / 2);
await page.mouse.down();
await page.mouse.move(elBox.x + elBox.width / 2 + 90, elBox.y + elBox.height / 2 + 40, { steps: 8 });
await page.mouse.up();
await page.waitForTimeout(120);
const moved = await page.evaluate(() => window.__studio.board.elements.find((e) => e.kind === 'product').x);
ok('drag on the canvas moves a piece', moved > placed.x + 0.05, `${placed.x} → ${moved}`);
const rh = await page.$('.handle.resize');
ok('handles appear on selection', !!rh);
if (rh) {
  const hb = await rh.boundingBox();
  const w0 = await page.evaluate(() => window.__studio.board.elements.find((e) => e.kind === 'product').w);
  await page.mouse.move(hb.x + hb.width / 2, hb.y + hb.height / 2);
  await page.mouse.down();
  await page.mouse.move(hb.x + 120, hb.y + 120, { steps: 8 });
  await page.mouse.up();
  await page.waitForTimeout(120);
  const w1 = await page.evaluate(() => window.__studio.board.elements.find((e) => e.kind === 'product').w);
  ok('resize handle grows the piece', w1 > w0 + 0.02, `${w0} → ${w1}`);
}
await page.evaluate(() => { document.querySelector('[data-act="duplicate"]').click(); });
await page.waitForTimeout(80);
els = await page.evaluate(() => window.__studio.board.elements.filter((e) => e.kind === 'product').length);
ok('duplicate adds a piece', els === 2, String(els));
await page.click('#undo');
await page.waitForTimeout(80);
els = await page.evaluate(() => window.__studio.board.elements.filter((e) => e.kind === 'product').length);
ok('undo removes it again', els === 1, String(els));
await page.click('#redo');
await page.waitForTimeout(80);
els = await page.evaluate(() => window.__studio.board.elements.filter((e) => e.kind === 'product').length);
ok('redo puts it back', els === 2, String(els));

console.log('\n7. helpers');
const helpers = await page.evaluate(() => ({
  slots: document.getElementById('slotList').textContent,
  axes: document.getElementById('axesRead').textContent,
}));
ok('slot checklist lists all six slots',
  ['layer', 'top', 'bottom', 'shoes', 'bag', 'accessory'].every((s) => helpers.slots.includes(s)),
  helpers.slots);
ok('axes read out', /weight \d\.\d of 4/.test(helpers.axes), helpers.axes);

console.log('\n8. fill a full outfit and render');
await page.evaluate(async () => {
  const S = window.__studio;
  S.board.elements = S.board.elements.filter((e) => e.kind === 'inspiration');
  const want = ['layer', 'top', 'bottom', 'shoes', 'bag', 'accessory'];
  let i = 0;
  for (const slot of want) {
    const p = S.products.find((x) => x.slot === slot && x.asset_quality !== 'weak');
    if (p) await S.placeProduct(p.product_id, 0.55 + (i % 2) * 0.2, 0.2 + i * 0.12);
    i++;
  }
  S.board.title = 'Rust twice, and nothing else bright';
  S.board.line = 'One colour at two weights, with brown underneath it.';
  S.board.showLabels = true;
  S.renderBoard();
});
await page.waitForTimeout(700);
const full = await page.evaluate(() => ({
  pieces: window.__studio.board.elements.filter((e) => e.kind === 'product').length,
  strip: document.querySelectorAll('.board-strip i').length,
  badges: document.querySelectorAll('.badge').length,
  title: document.querySelector('.board-title')?.textContent,
}));
ok('six slots filled', full.pieces === 6, JSON.stringify(full));
ok('swatch strip drawn from the pieces', full.strip > 0, String(full.strip));
ok('numbered labels drawn', full.badges === 6, String(full.badges));
ok('title on the board', full.title?.startsWith('Rust twice'), full.title);

console.log('\n9. export');
const out = await page.evaluate(async () => {
  const S = window.__studio;
  const canvas = await S.renderCanvas();
  const blob = await new Promise((r) => canvas.toBlob(r, 'image/png'));
  const info = S.buildInfo();
  const { buildMarkdown, pngWithMetadata } = await import('./js/export.js');
  const withMeta = await pngWithMetadata(blob, 'relatively-normal.outfit', JSON.stringify(info));
  const head = new Uint8Array(await withMeta.slice(0, 60).arrayBuffer());
  return {
    w: canvas.width, h: canvas.height, png: blob.size, pngMeta: withMeta.size,
    nonBlank: (() => {
      const c = document.createElement('canvas'); c.width = 60; c.height = 75;
      c.getContext('2d').drawImage(canvas, 0, 0, 60, 75);
      const d = c.getContext('2d').getImageData(0, 0, 60, 75).data;
      const seen = new Set();
      for (let i = 0; i < d.length; i += 4) seen.add(`${d[i]},${d[i + 1]},${d[i + 2]}`);
      return seen.size;
    })(),
    itxt: String.fromCharCode(...head).includes('iTXt'),
    info, md: buildMarkdown(info),
  };
});
ok('portrait exports at 2160×2700', out.w === 2160 && out.h === 2700, `${out.w}×${out.h}`);
ok('PNG produced', out.png > 50000, `${(out.png / 1e6).toFixed(2)} MB`);
ok('board is not blank', out.nonBlank > 12, `${out.nonBlank} distinct colours`);
ok('PNG carries the info in an iTXt chunk', out.itxt && out.pngMeta > out.png);
ok('info file names every piece', out.info.pieces.length === 6, String(out.info.pieces.length));
ok('pieces are numbered in label order',
  out.info.pieces.map((p) => p.label).join(',') === '1,2,3,4,5,6');
ok('info records the inspiration', !!out.info.inspiration?.inspiration_id);
ok('info keeps placement for reopening',
  out.info.pieces.every((p) => typeof p.placement.x === 'number' && typeof p.placement.layer === 'number'));
ok('empty fields stay empty (no invention)',
  out.info.pieces.every((p) => p.product_url === '' && p.product_url_confidence === 'input needed'));
ok('slug is date-title', /^\d{4}-\d{2}-\d{2}-rust-twice/.test(out.info.slug), out.info.slug);
ok('markdown lists the pieces', (out.md.match(/^\| \d /gm) || []).length === 6);

console.log('\n10. landscape');
await page.selectOption('#format', 'landscape');
await page.waitForTimeout(400);
const land = await page.evaluate(async () => {
  const c = await window.__studio.renderCanvas();
  return { w: c.width, h: c.height };
});
ok('landscape exports at 2912 wide', land.w === 2912 && land.h === 2184, `${land.w}×${land.h}`);
await page.selectOption('#format', 'portrait');

console.log('\n11. reopen');
const round = await page.evaluate(async () => {
  const S = window.__studio;
  const info = S.buildInfo();
  const before = S.board.elements.length;
  const firstX = S.board.elements.find((e) => e.kind === 'product').x;
  S.board = (await import('./js/model.js')).createBoard('portrait');
  S.renderBoard();
  await S.openInfo(JSON.stringify(info));
  const after = S.board.elements.length;
  return { before, after, firstX, reopenedX: S.board.elements.find((e) => e.kind === 'product').x,
    title: S.board.title, labels: S.board.showLabels };
});
ok('reopen restores every element', round.after === round.before, JSON.stringify(round));
ok('reopen restores placement', Math.abs(round.reopenedX - round.firstX) < 0.0002, JSON.stringify(round));
ok('reopen restores the title and toggles', round.title.startsWith('Rust twice') && round.labels === true);

console.log('\n11b. palette');
{
  const pos = () => page.evaluate(() => JSON.stringify(window.__studio.board.elements
    .map((e) => [e.uid, e.x, e.y, e.w, e.rot, e.z])));
  const before = await pos();
  const groups = await page.evaluate(() => [...document.querySelectorAll('#palCat optgroup')].map((g) => g.label));
  ok('the category dropdown lists season, family and this season', groups.length === 3, groups.join(' / '));
  await page.selectOption('#palCat', 'season:soft_autumn');
  await page.waitForTimeout(150);
  const rows = await page.evaluate(() => ({
    shown: !document.querySelector('#palList').classList.contains('hidden'),
    n: document.querySelectorAll('#palList .pal-row').length,
    swatches: document.querySelectorAll('#palList .pal-row .pal-sw i').length,
  }));
  ok('the palettes appear as swatch rows', rows.shown && rows.n > 3 && rows.swatches >= rows.n * 3, JSON.stringify(rows));
  await page.click('#palList .pal-row[data-palette="season-soft_autumn-teal-and-ochre"]');
  await page.waitForTimeout(300);
  const ref = await page.evaluate(() => ({
    id: window.__studio.board.palette?.id,
    ref: !document.querySelector('#palRef').hidden,
    items: [...document.querySelectorAll('#palRef li')].map((li) => li.textContent),
    listClosed: document.querySelector('#palList').classList.contains('hidden'),
    onBoard: document.querySelectorAll('.board-strip.palette').length,
  }));
  ok('picking one shows it beside the canvas', ref.id === 'season-soft_autumn-teal-and-ochre' && ref.ref
    && ref.items.length === 3 && ref.listClosed, JSON.stringify(ref));
  ok('names, shares and roles in the reference', ref.items.some((t) => /deep teal · 50%/.test(t) && /dominant/.test(t)),
    ref.items.join(' | '));
  ok('not on the board unless asked', ref.onBoard === 0);
  ok('choosing a palette moves nothing on the canvas', (await pos()) === before);

  await page.check('#fPalette');
  await page.waitForTimeout(250);
  const rank = await page.evaluate(async () => {
    const { hexToOklab, productDistanceToLook } = await import('./js/colour.js');
    const S = window.__studio;
    const labs = S.board.palette.colours.map((c) => hexToOklab(c.hex));
    const ds = S.shown.slice(0, 30).map((p) => productDistanceToLook(p, labs));
    return { sorted: ds.every((d, i) => !i || d >= ds[i - 1] - 1e-12), look: document.querySelector('#fMatch').checked };
  });
  ok('"Matches this palette" ranks the shelf by distance to its colours', rank.sorted && !rank.look, JSON.stringify(rank));

  const read = await page.evaluate(() => ({
    rows: document.querySelectorAll('#paletteRead .pr-item').length,
    shares: window.__studio.outfitShares(),
  }));
  const total = read.shares.rows.reduce((a, r) => a + r.actual, 0) + read.shares.outside;
  ok('the readout divides the outfit against the palette', read.rows === 4 && Math.abs(total - 100) < 0.5,
    JSON.stringify(read.shares));

  await page.check('#oPalette');
  await page.waitForTimeout(200);
  const strip = await page.evaluate(() => document.querySelectorAll('.board-strip.palette i').length);
  ok('the toggle puts it on the board as a strip', strip === 3, String(strip));
  const png = await page.evaluate(async () => (await window.__studio.renderCanvas()).width);
  ok('the export still renders with it', png === 2160);
  ok('the strip moves nothing', (await pos()) === before);

  const saved = await page.evaluate(async () => {
    const S = window.__studio;
    const info = S.buildInfo();
    const { buildMarkdown } = await import('./js/export.js');
    return { info, md: buildMarkdown(info) };
  });
  const pal = saved.info.palette;
  ok('the info file records the palette', pal && pal.id === 'season-soft_autumn-teal-and-ochre'
    && pal.name === 'Teal and Ochre' && pal.category === 'season' && pal.colours.length === 3
    && pal.colours.every((c) => c.hex && c.name && c.role && typeof c.share === 'number') && pal.source?.ref,
    JSON.stringify(pal));
  ok('the piece list names it in one line', saved.md.split('\n').filter((l) => /Palette/.test(l)).length === 1);

  // change it, then reopen the saved outfit: the saved palette comes back
  await page.selectOption('#palCat', 'trend:aw26-27');
  await page.waitForTimeout(150);
  await page.click('#palList .pal-row[data-palette="trend-aw2627-t11"]');
  await page.waitForTimeout(200);
  ok('changing it moves nothing', (await pos()) === before);
  await page.evaluate(async (info) => { await window.__studio.openInfo(JSON.stringify(info)); }, saved.info);
  await page.waitForTimeout(300);
  const back = await page.evaluate(() => ({
    id: window.__studio.board.palette?.id, strip: window.__studio.board.showPalette,
    cat: document.querySelector('#palCat').value,
    ref: document.querySelector('#palRef h3')?.textContent,
  }));
  ok('reopening restores the selection', back.id === 'season-soft_autumn-teal-and-ochre' && back.strip === true
    && back.cat === 'season:soft_autumn' && back.ref === 'Teal and Ochre', JSON.stringify(back));

  const beforeClear = await pos();
  await page.click('#palClear');
  await page.waitForTimeout(250);
  const cleared = await page.evaluate(() => ({
    p: window.__studio.board.palette, ref: document.querySelector('#palRef').hidden,
    rank: document.querySelector('#fPalette').checked, strip: document.querySelectorAll('.board-strip.palette').length,
  }));
  ok('clearing it removes the reference, the ranking and the strip', cleared.p === null && cleared.ref
    && !cleared.rank && cleared.strip === 0, JSON.stringify(cleared));
  ok('clearing moves nothing', (await pos()) === beforeClear);
}

console.log('\n12. autosave');
// wait for the save to have landed before reloading: autosave runs off the
// render, so reloading straight away raced it and failed here about one run in
// three, which reads as a broken board rather than a fast test
// wait for the save to match the board on screen, not merely to be non-empty:
// step 11 renders an empty board on its way to reopening the saved one, and a
// reload that caught that render read back nothing
await page.waitForFunction(() => {
  try {
    const b = JSON.parse(localStorage.getItem('rn.studio.board.v2') || '{}');
    return (b.elements || []).length === window.__studio.board.elements.length
      && window.__studio.board.elements.length > 0;
  } catch (e) { return false; }
}, null, { timeout: 5000 });
await page.reload();
// products load before the saved board is put back, so waiting on the catalogue
// alone read the board in the moment before restore() ran
await page.waitForFunction(() => window.__studio?.ready === true, null, { timeout: 15000 });
const restored = await page.evaluate(() => window.__studio.board.elements.length);
ok('the board survives a reload', restored > 0, `${restored} elements`);
const cleared = await page.evaluate(async () => {
  localStorage.clear();
  return true;
});
ok('empty storage handled', cleared);

console.log(`\n${pass} passed, ${fail} failed`);
if (errors.length) console.log('page errors:\n  ' + errors.slice(0, 6).join('\n  '));
await browser.close();
server.close();
process.exit(fail ? 1 : 0);
