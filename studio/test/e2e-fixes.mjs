// The five desk fixes of 23 Sept, on the iPad touch profile: proportions,
// one gesture = one piece, tile = placement, several garments, duplicates.
// Real touches through CDP, as in e2e-touch.mjs.
//   node studio/test/e2e-fixes.mjs
import { chromium } from 'playwright';
import { createServer } from 'node:http';
import { readFile, stat } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { join, extname } from 'node:path';

const ROOT = new URL('../', import.meta.url).pathname;
const TYPES = { '.html': 'text/html', '.css': 'text/css', '.js': 'text/javascript',
  '.json': 'application/json', '.webp': 'image/webp', '.png': 'image/png', '.jpg': 'image/jpeg', '.ttf': 'font/ttf' };
let pass = 0, fail = 0;
const ok = (name, cond, extra = '') => {
  if (cond) { pass++; console.log(`  ok   ${name}`); } else { fail++; console.log(`  FAIL ${name} ${extra}`); }
};
const server = createServer(async (req, res) => {
  const p = join(ROOT, decodeURIComponent(req.url.split('?')[0]).replace(/^\//, '') || 'index.html');
  try { const s = await stat(p); if (s.isDirectory()) throw 0;
    res.writeHead(200, { 'content-type': TYPES[extname(p)] || 'application/octet-stream' }); res.end(await readFile(p)); }
  catch { res.writeHead(404).end('no'); }
});
await new Promise((r) => server.listen(0, r));
const base = `http://127.0.0.1:${server.address().port}`;
const browser = await chromium.launch({ executablePath: existsSync('/opt/pw-browsers/chromium/chrome-linux/chrome')
  ? '/opt/pw-browsers/chromium/chrome-linux/chrome' : undefined });
// an iPad Pro 11" landscape profile: touch, no mouse
const ctx = await browser.newContext({ viewport: { width: 1194, height: 834 }, hasTouch: true, isMobile: true,
  deviceScaleFactor: 2, userAgent: 'Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1' });
const page = await ctx.newPage();
const errors = [];
page.on('pageerror', (e) => errors.push(String(e)));
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
const cdp = await ctx.newCDPSession(page);

async function touch(points, { steps = 8, holdMs = 0 } = {}) {
  // points: [[x,y], ...] path of one finger
  const [x0, y0] = points[0];
  await cdp.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x: x0, y: y0 }] });
  if (holdMs) await page.waitForTimeout(holdMs);
  for (let i = 1; i < points.length; i++) {
    const [ax, ay] = points[i - 1], [bx, by] = points[i];
    for (let s = 1; s <= steps; s++) {
      await cdp.send('Input.dispatchTouchEvent', { type: 'touchMove',
        touchPoints: [{ x: ax + (bx - ax) * s / steps, y: ay + (by - ay) * s / steps }] });
    }
  }
  await cdp.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
}
const tap = async (x, y) => touch([[x, y]]);
const count = (sel) => page.$$eval(sel, (e) => e.length);

await page.goto(`${base}/index.html`);
await page.waitForFunction(() => window.__studio?.ready, null, { timeout: 20000 });
await page.evaluate(() => { localStorage.clear(); });
await page.reload();
await page.waitForFunction(() => window.__studio?.ready, null, { timeout: 20000 });
await page.waitForTimeout(300);

// Two test pieces: a tall narrow one (jeans) and a wide one (a boot on its
// side). Their thumbnails are padded squares and their stored picture sizes
// are wrong on purpose — the desk must go by the pixels.
await page.evaluate(() => {
  const S = window.__studio;
  const mk = (id, name, slot, images) => ({
    product_id: id, slot, garment_type: name, brand: 'TEST', colours: [], weight: 2, formality: 2,
    asset: `test/fixtures/${name}.png`, thumb: `test/fixtures/${name}-thumb.png`,
    asset_type: 'cutout_flat', asset_quality: 'good', clean: true, hidden: false, several: [],
    duplicate_of: '', image: 0, primary: 0, parent_id: '', choice: null, custom_box: null, base: 'photo',
    images, full: images ? { path: images[0].path, w: 1, h: 1 } : null, boxes: null,
  });
  const pics = [{ path: 'test/fixtures/tall-full.png', w: 1, h: 1, type: 'flat lay' },
    { path: 'test/fixtures/wide-full.png', w: 1, h: 1, type: 'on-model' }];
  for (const p of [mk('T-TALL', 'tall', 'bottom', pics), mk('T-WIDE', 'wide', 'shoes', null)]) {
    S.products.push(p); S.productsById[p.product_id] = p;
  }
  S.filters.search = 'TEST'; S.renderShelf();
});
await page.waitForTimeout(400);
const cellOf = async (pid) => (await page.$(`#grid .cell[data-pid="${pid}"]`)).boundingBox();
const lastEl = () => page.evaluate(() => window.__studio.board.elements.at(-1));
const domRatio = (uid) => page.evaluate((u) => {
  const r = document.querySelector(`#layers .el[data-uid="${u}"]`).getBoundingClientRect();
  return r.width / r.height;
}, uid);
// the drawn piece in the exported PNG, found by its own colour
const exportRatio = (rgb) => page.evaluate(async (rgb) => {
  const c = await window.__studio.renderCanvas();
  const { data, width, height } = c.getContext('2d').getImageData(0, 0, c.width, c.height);
  let x0 = width, x1 = -1, y0 = height, y1 = -1;
  for (let y = 0; y < height; y += 2) for (let x = 0; x < width; x += 2) {
    const i = (y * width + x) * 4;
    if (Math.abs(data[i] - rgb[0]) < 10 && Math.abs(data[i + 1] - rgb[1]) < 10 && Math.abs(data[i + 2] - rgb[2]) < 10) {
      if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y;
    }
  }
  return x1 < 0 ? null : (x1 - x0 + 2) / (y1 - y0 + 2);
}, rgb);
const near = (a, b, tol = 0.03) => a && Math.abs(a - b) / b < tol;
const clearBoard = () => page.evaluate(async () => {
  const S = window.__studio;
  S.board = (await import('./js/model.js')).createBoard('portrait'); S.selected = null; S.renderBoard();
});

console.log('\n1. proportions come from the pixels');
let c = await cellOf('T-TALL');
await tap(c.x + c.width / 2, c.y + c.height / 2);
await page.waitForTimeout(700);
let el = await lastEl();
ok('a tall narrow piece keeps 1:5 in the model', near(el.aspect, 0.2, 0.01), String(el.aspect));
ok('…on the canvas', near(await domRatio(el.uid), 0.2), String(await domRatio(el.uid)));
// at its default width a 1:5 piece is taller than the board; narrow it so the
// whole piece is inside the exported image and can be measured
await page.evaluate(() => { window.__studio.board.elements.at(-1).w = 0.1; window.__studio.renderBoard(); });
let ex = await exportRatio([48, 80, 160]);
ok('…and in the exported image', near(ex, 0.2, 0.04), String(ex));
await clearBoard();
c = await cellOf('T-WIDE');
await tap(c.x + c.width / 2, c.y + c.height / 2);
await page.waitForTimeout(700);
el = await lastEl();
ok('a wide piece keeps 3:1 in the model', near(el.aspect, 3, 0.01), String(el.aspect));
ok('…on the canvas', near(await domRatio(el.uid), 3), String(await domRatio(el.uid)));
ex = await exportRatio([160, 80, 48]);
ok('…and in the exported image', near(ex, 3, 0.04), String(ex));
// resize with the round handle: bigger, same proportions
await page.evaluate((u) => { window.__studio.selected = u; window.__studio.renderBoard(); }, el.uid);
const h = await (await page.$('#layers .handle.resize')).boundingBox();
const w0 = el.w;
await page.evaluate(({ x, y }) => {
  const hd = document.querySelector('#layers .handle.resize');
  const st = document.getElementById('stage');
  const ev = (t, x2, tg) => tg.dispatchEvent(new PointerEvent(t, { pointerId: 9, pointerType: 'touch', isPrimary: true,
    bubbles: true, cancelable: true, clientX: x2, clientY: y }));
  ev('pointerdown', x, hd);
  for (let i = 1; i <= 10; i++) ev('pointermove', x + i * 6, st);
  ev('pointerup', x + 60, st);
}, { x: h.x + h.width / 2, y: h.y + h.height / 2 });
await page.waitForTimeout(300);
el = await lastEl();
ok('resizing changes the size', el.w > w0 * 1.05, `${w0} → ${el.w}`);
ok('…and keeps the proportions', near(await domRatio(el.uid), 3), String(await domRatio(el.uid)));
ex = await exportRatio([160, 80, 48]);
ok('…in the export too', near(ex, 3, 0.04), String(ex));
// other picture: the stored sizes of these pictures say 1×1 — the pixels say otherwise
await clearBoard();
c = await cellOf('T-TALL');
await tap(c.x + c.width / 2, c.y + c.height / 2);
await page.waitForTimeout(600);
el = await lastEl();
await page.evaluate((u) => { window.__studio.selected = u; window.__studio.renderBoard(); }, el.uid);
await page.tap('#elPicture');
await page.waitForTimeout(700);
el = await lastEl();
ok('other picture: a 1:3 photo is 1:3', near(el.aspect, 1 / 3, 0.01) && near(await domRatio(el.uid), 1 / 3), `${el.aspect} ${await domRatio(el.uid)}`);
ex = await exportRatio([40, 140, 70]);
// a photo is framed with a mat: the picture inside it keeps 1:3
ok('…and the export draws it 1:3', near(ex, 1 / 3, 0.05), String(ex));
await page.tap('#elPicture');
await page.waitForTimeout(700);
el = await lastEl();
ok('the next picture, 3:1, is 3:1', near(el.aspect, 3, 0.01), String(el.aspect));
ex = await exportRatio([140, 40, 120]);
ok('…in the export as well', near(ex, 3, 0.05), String(ex));
const info = await page.evaluate(() => window.__studio.buildInfo().pieces.at(-1).placement.aspect);
ok('the info file records the real aspect', near(info, 3, 0.01), String(info));

console.log('\n2. one gesture adds one piece');
await clearBoard();
const onBoard = () => page.evaluate(() => window.__studio.board.elements.length);
c = await cellOf('T-WIDE');
await tap(c.x + c.width / 2, c.y + c.height / 2);
await page.waitForTimeout(400);
ok('a CDP touch tap adds exactly one', (await onBoard()) === 1, String(await onBoard()));
// a storm: one finger down, a burst of moves, the up event delivered nine times
await page.evaluate((pid) => {
  const cell = document.querySelector(`#grid .cell[data-pid="${pid}"]`);
  const r = cell.getBoundingClientRect();
  const ev = (t) => cell.dispatchEvent(new PointerEvent(t, { pointerId: 21, pointerType: 'touch', isPrimary: true,
    bubbles: true, cancelable: true, clientX: r.x + r.width / 2, clientY: r.y + r.height / 2 }));
  ev('pointerdown');
  for (let i = 0; i < 30; i++) ev('pointermove');
  for (let i = 0; i < 9; i++) ev('pointerup');
}, 'T-TALL');
await page.waitForTimeout(400);
ok('nine up events for one gesture add one piece', (await onBoard()) === 2, String(await onBoard()));
// a second finger (a palm) on another tile while the first taps
await page.evaluate(() => {
  const [a, b] = ['T-TALL', 'T-WIDE'].map((p) => document.querySelector(`#grid .cell[data-pid="${p}"]`));
  const ev = (t, cell, id, primary) => { const r = cell.getBoundingClientRect();
    cell.dispatchEvent(new PointerEvent(t, { pointerId: id, pointerType: 'touch', isPrimary: primary,
      bubbles: true, cancelable: true, clientX: r.x + 20, clientY: r.y + 20 })); };
  ev('pointerdown', a, 31, true); ev('pointerdown', b, 32, false);
  ev('pointerup', b, 32, false); ev('pointerup', a, 31, true);
});
await page.waitForTimeout(400);
const two = await page.evaluate(() => window.__studio.board.elements.map((e) => e.product_id));
ok('a second finger adds nothing; the first adds its own piece', two.length === 3 && two[2] === 'T-TALL', JSON.stringify(two));
// a sideways drag onto the canvas, sixty frames of movement
const sb = await (await page.$('#stage')).boundingBox();
c = await cellOf('T-WIDE');
await touch([[c.x + c.width / 2, c.y + c.height / 2], [c.x + c.width / 2 + 60, c.y + c.height / 2 + 3],
  [sb.x + sb.width * 0.3, sb.y + sb.height * 0.3]], { steps: 30 });
await page.waitForTimeout(400);
ok('a drag of sixty frames adds one piece', (await onBoard()) === 4, String(await onBoard()));
// the picture badge switches pictures and never places
const badge = await (await page.$('#grid .cell[data-pid="T-TALL"] .pic-flip')).boundingBox();
await tap(badge.x + badge.width / 2, badge.y + badge.height / 2);
await page.waitForTimeout(400);
ok('tapping the picture badge adds nothing', (await onBoard()) === 4, String(await onBoard()));

console.log('\n3. the tile shows what a tap places');
// the badge above moved T-TALL's tile to its first photo
const tileNow = await page.evaluate(() => {
  const img = document.querySelector('#grid .cell[data-pid="T-TALL"] img');
  return { src: img.getAttribute('src'), view: img.dataset.view };
});
ok('the tile now shows the photo', tileNow.src.endsWith('tall-full.png'), tileNow.src);
c = await cellOf('T-TALL');
await tap(c.x + c.width / 2, c.y + c.height / 2);
await page.waitForTimeout(500);
const placed = await page.evaluate(() => {
  const S = window.__studio; const e = S.board.elements.at(-1);
  return { src: document.querySelector(`#layers .el[data-uid="${e.uid}"] img`).getAttribute('src'),
    view: JSON.stringify({ variant: e.variant, crop: e.crop, image: e.image, base: e.base }) };
});
ok('…and the tap places that photo, not the cut-out', placed.src === tileNow.src, `${placed.src} vs ${tileNow.src}`);
ok('…read from the same view', placed.view === tileNow.view, `${placed.view} vs ${tileNow.view}`);
// a choice made in this browser changes the tile before any rebuild
await page.evaluate(() => {
  const S = window.__studio;
  delete S.shelfPicture['T-TALL'];
  S.choices['T-TALL'] = { choice: 'custom', box: [0, 0, 1, 0.5], image: 1, base: 'photo' };
  S.renderShelf();
});
await page.waitForTimeout(400);
const tileC = await page.evaluate(() => document.querySelector('#grid .cell[data-pid="T-TALL"] img').dataset.view);
const plC = await page.evaluate(() => JSON.stringify(window.__studio.placement(window.__studio.productsById['T-TALL'])));
ok('a box chosen in Review: tile and placement agree', tileC === plC && JSON.parse(tileC).crop[3] === 0.5, `${tileC} vs ${plC}`);
// the real catalogue: every shelf tile reads the same view the tap would place
const agree = await page.evaluate(() => {
  const S = window.__studio;
  S.filters.search = ''; S.renderShelf();
  const cells = [...document.querySelectorAll('#grid .cell')];
  const off = cells.filter((cl) => cl.querySelector('img').dataset.view
    !== JSON.stringify(S.placement(S.productsById[cl.dataset.pid])));
  return { n: cells.length, off: off.length };
});
ok('every tile on the shelf agrees with its placement', agree.n > 100 && agree.off === 0, JSON.stringify(agree));

console.log('\n4. several garments in one picture');
const sev = await page.evaluate(() => {
  const S = window.__studio;
  const rows = S.products.filter((p) => p.several && p.several.length);
  return { n: rows.length, onShelf: S.shown.filter((p) => p.several && p.several.length).map((p) => p.product_id),
    fan: (S.productsById['B062-P001'] || {}).several || [] };
});
// grid pages used to make up most of these; cut into cells they are hidden and no longer counted
ok('the several-garment rows are in the catalogue', sev.n > 20, String(sev.n));
ok('none of them is on the shelf', sev.onShelf.length === 0, JSON.stringify(sev.onShelf));
ok('the fan of colourways B062-P001 is one of them', sev.fan.length > 0, JSON.stringify(sev.fan));
await page.evaluate(() => window.__studio.setView('review'));
await page.check('#rSeveral');
await page.waitForTimeout(500);
const sevView = await page.evaluate(() => ({
  groups: document.querySelectorAll('#reviewCards .cellgroup.several').length,
  fanGroup: !!document.querySelector('#reviewCards .cellgroup.several [data-pid="B062-P001-V2"]'),
  fanCard: !!document.querySelector('#reviewCards .rcard[data-pid="B062-P001"] .why.several'),
}));
ok('Review groups them under the picture they share', sevView.groups > 20 && sevView.fanGroup, JSON.stringify(sevView));
ok('the owning card says why and offers Add box', sevView.fanCard, JSON.stringify(sevView));
await page.uncheck('#rSeveral');

console.log('\n5. duplicates');
const dup = await page.evaluate(() => {
  const S = window.__studio;
  const rows = S.products.filter((p) => p.duplicate_of);
  const k = S.productsById['B013-P001-V2'] || {};
  return { n: rows.length, onShelf: S.shown.filter((p) => p.duplicate_of).length,
    kept: rows.every((p) => !!S.productsById[p.duplicate_of]), b013: k.duplicate_of, cause: k.duplicate_cause,
    scarf: (S.productsById['B021-P001'] || {}).duplicate_of };
});
ok('duplicates are marked, nothing deleted', dup.n > 30 && dup.kept, JSON.stringify(dup));
ok('none is on the shelf', dup.onShelf === 0, String(dup.onShelf));
// 24 Sept: the split that copied its parent's picture now carries a cut of
// its own colour (colourway_pictures.py), so it is no longer the parent again
ok('a colourway split that copied its parent\'s picture now has its own and is not a duplicate',
  dup.b013 === '' && dup.cause === '', JSON.stringify(dup));
ok('the two black Massimo Alba scarves are one', dup.scarf === 'B020-P006', String(dup.scarf));
await page.check('#rDups');
await page.waitForTimeout(500);
const dv = await page.evaluate(() => ({
  groups: document.querySelectorAll('#reviewCards .dupgroup').length,
  keeperFirst: [...document.querySelectorAll('#reviewCards .dupgroup')].every((g) => g.querySelector('.cells').firstChild.classList.contains('keeper')),
}));
ok('the duplicates filter shows each one beside its keeper', dv.groups > 20 && dv.keeperFirst, JSON.stringify(dv));
// any marked duplicate will do (B013-P001-V2 was one until it got its own picture)
const dpid = await page.evaluate(() => {
  const b = document.querySelector('#reviewCards .dupgroup [data-act="notdup"]');
  const pid = b.closest('[data-pid]').dataset.pid;
  b.click();
  return pid;
});
await page.waitForTimeout(300);
const back = await page.evaluate((pid) => {
  const S = window.__studio; S.filters.showUnreviewed = true; S.renderShelf();
  return { pid, shown: S.shown.some((p) => p.product_id === pid), choice: S.choices[pid] };
}, dpid);
ok('"Not a duplicate" puts it back on the shelf and records it', back.shown && back.choice.notDuplicate === true, JSON.stringify(back));

console.log('\n6. the tile follows the image filter (24 Sept)');
// unreviewed pieces too, so every picture type has tiles to check
await page.evaluate(() => {
  const S = window.__studio; S.setView('grid');
  const u = document.getElementById('fUnreviewed'); u.checked = true; u.dispatchEvent(new Event('change', { bubbles: true }));
});
const setAsset = (v) => page.evaluate((v) => {
  const s = document.getElementById('fAsset'); s.value = v;
  s.dispatchEvent(new Event('change', { bubbles: true })); s.dispatchEvent(new Event('input', { bubbles: true }));
}, v);
for (const type of ['cutout_flat', 'cutout_model', 'tile']) {
  await setAsset(type);
  await page.waitForTimeout(600);
  const t = await page.evaluate((type) => {
    const S = window.__studio;
    const cells = [...document.querySelectorAll('#grid .cell')];
    let off = 0, wrongType = 0;
    for (const c of cells) {
      const p = S.productsById[c.dataset.pid];
      const img = c.querySelector('img');
      const pl = S.placement(p);
      if (img.dataset.view !== JSON.stringify(pl)) off++;
      // a flat filter never shows a picture typed as worn, nor an on-model one a flat lay
      const e = (p.images || [])[pl.image];
      if (pl.variant === 'whole' && e && e.type === (type === 'cutout_flat' ? 'on-model' : 'flat lay')) wrongType++;
      if (pl.variant === 'cutout' && p.asset_type !== type) wrongType++;
    }
    return { n: cells.length, off, wrongType };
  }, type);
  ok(`${type}: every tile is what a tap places, and of that type`, t.n > 0 && t.off === 0 && t.wrongType === 0,
    JSON.stringify(t));
}
await setAsset('');
await page.evaluate(() => {
  const u = document.getElementById('fUnreviewed'); u.checked = false; u.dispatchEvent(new Event('change', { bubbles: true }));
});

console.log('\n7. a grid cut into cells, in Review (24 Sept)');
await page.evaluate(() => window.__studio.setView('review'));
for (const id of ['#rDups', '#rSeveral']) if (await page.isChecked(id)) await page.uncheck(id);
await page.waitForTimeout(500);
const gc = await page.evaluate(() => {
  const S = window.__studio;
  const cards = [...document.querySelectorAll('#reviewCards .gridcard')];
  const bad = cards.filter((c) => !/^\S+ · \d+ cells?: \d+ on the shelf, \d+ in Review$/.test(c.querySelector('.rwho').textContent));
  const withCells = new Set(S.products.map((p) => p.parent_id).filter(Boolean));
  const asCard = [...document.querySelectorAll('#reviewCards .rcard')].filter((c) => withCells.has(c.dataset.pid));
  const shelfInList = cards.flatMap((c) => [...c.querySelectorAll('.cellpick')])
    .filter((b) => S.shown.some((p) => p.product_id === b.dataset.pid)).length;
  return { cards: cards.length, bad: bad.length, asCard: asCard.length, shelfInList,
    several: document.querySelectorAll('#reviewCards .gridcard .why.several').length };
});
ok('a cut grid says "N cells: M on the shelf, K in Review" and lists only the K', gc.cards > 50 && gc.bad === 0
  && gc.shelfInList === 0, JSON.stringify(gc));
ok('...and is never a "Several garments, Adjust box" card', gc.asCard === 0 && gc.several === 0, JSON.stringify(gc));

console.log(`\n${pass} passed, ${fail} failed`);
if (errors.length) console.log('page errors:\n  ' + errors.slice(0, 6).join('\n  '));
await browser.close();
server.close();
process.exit(fail ? 1 : 0);
