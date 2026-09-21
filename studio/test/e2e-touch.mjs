// Touch, categories, review, frame, pinch, simulated colours — headless
// Chromium with an iPad-sized touch context. Real touches go through CDP so the
// browser's own pan-y handling is exercised, not a mouse pretending.
//   node studio/test/e2e-touch.mjs
import { chromium } from 'playwright';
import { createServer } from 'node:http';
import { readFile, stat } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { join, extname } from 'node:path';

const ROOT = new URL('../', import.meta.url).pathname;
const TYPES = { '.html': 'text/html', '.css': 'text/css', '.js': 'text/javascript',
  '.json': 'application/json', '.webp': 'image/webp', '.jpg': 'image/jpeg', '.ttf': 'font/ttf' };
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
const pieces = () => page.evaluate(() => window.__studio.board.elements.filter((e) => e.kind === 'product').length);

await page.goto(`${base}/index.html`);
await page.waitForFunction(() => window.__studio?.products?.length > 0, null, { timeout: 20000 });
await page.evaluate(() => { localStorage.clear(); });
await page.reload();
await page.waitForFunction(() => window.__studio?.products?.length > 0, null, { timeout: 20000 });
await page.waitForTimeout(400);

console.log('\n1. the gate and the category bar');
const gate = await page.evaluate(() => ({
  shown: window.__studio.shown.length,
  total: window.__studio.products.length,
  clean: window.__studio.products.filter((p) => p.clean && !p.hidden).length,
  buttons: [...document.querySelectorAll('#slotBar button')].map((b) => b.textContent),
}));
ok('by default only clean cut-outs show', gate.shown === gate.clean, JSON.stringify(gate));
ok('slot bar has All + seven slots with counts', gate.buttons.length === 8 && /^All\d+$/.test(gate.buttons[0]), gate.buttons.join(' '));
await page.click('#slotBar button[data-slot="top"]');
await page.waitForTimeout(80);
ok('tapping a category filters the shelf', await page.evaluate(() => window.__studio.shown.every((p) => p.slot === 'top') && window.__studio.shown.length > 0));
await page.click('#slotBar button[data-slot="top"]');
await page.waitForTimeout(80);
ok('tapping it again clears', await page.evaluate(() => !window.__studio.filters.slot));
await page.check('#fUnreviewed');
await page.waitForTimeout(100);
const withUnreviewed = await page.evaluate(() => window.__studio.shown.length);
ok('show unreviewed brings the rest in', withUnreviewed > gate.shown, `${gate.shown} → ${withUnreviewed}`);
await page.uncheck('#fUnreviewed');
await page.waitForTimeout(80);

console.log('\n2. touch on the shelf');
const grid = await page.$('#grid');
const gb = await grid.boundingBox();
const scroll0 = await page.$eval('#grid', (g) => g.scrollTop);
await touch([[gb.x + gb.width / 2, gb.y + gb.height - 40], [gb.x + gb.width / 2, gb.y + 40]], { steps: 12 });
await page.waitForTimeout(400);
const scroll1 = await page.$eval('#grid', (g) => g.scrollTop);
ok('a vertical swipe scrolls the shelf', scroll1 > scroll0 + 50, `${scroll0} → ${scroll1}`);
ok('…and adds nothing', (await pieces()) === 0);
await page.$eval('#grid', (g) => { g.scrollTop = 0; });
const cell = await page.$('#grid .cell');
const cb = await cell.boundingBox();
await tap(cb.x + cb.width / 2, cb.y + cb.height / 2);
await page.waitForTimeout(500);
ok('a tap adds the piece', (await pieces()) === 1);
const c2 = await (await page.$$('#grid .cell'))[1].boundingBox();
await tap(c2.x + c2.width / 2, c2.y + c2.height / 2);
await page.waitForTimeout(500);
const centres = await page.evaluate(() => window.__studio.board.elements.filter((e) => e.kind === 'product').map((e) => [e.x, e.y]));
ok('taps land near the middle, each one offset', centres.length === 2 && Math.abs(centres[0][0] - 0.5) < 0.12
  && (centres[0][0] !== centres[1][0] || centres[0][1] !== centres[1][1]), JSON.stringify(centres));
const stage = await page.$('#stage');
const sb = await stage.boundingBox();
const c3 = await (await page.$$('#grid .cell'))[2].boundingBox();
await touch([[c3.x + c3.width / 2, c3.y + c3.height / 2], [sb.x + sb.width * 0.7, sb.y + sb.height * 0.3]], { steps: 14, holdMs: 400 });
await page.waitForTimeout(500);
const lp = await page.evaluate(() => { const e = window.__studio.board.elements.filter((x) => x.kind === 'product').at(-1); return [e.x, e.y]; });
ok('a long press picks up and drops where released', (await pieces()) === 3 && Math.abs(lp[0] - 0.7) < 0.08 && Math.abs(lp[1] - 0.3) < 0.08, JSON.stringify(lp));
const c4 = await (await page.$$('#grid .cell'))[3].boundingBox();
await touch([[c4.x + c4.width / 2, c4.y + c4.height / 2], [c4.x + c4.width / 2 + 60, c4.y + c4.height / 2 + 4],
  [sb.x + sb.width * 0.4, sb.y + sb.height * 0.7]], { steps: 10 });
await page.waitForTimeout(500);
const sd = await page.evaluate(() => { const e = window.__studio.board.elements.filter((x) => x.kind === 'product').at(-1); return [e.x, e.y]; });
ok('a sideways drag picks up without waiting', (await pieces()) === 4 && Math.abs(sd[0] - 0.4) < 0.08 && Math.abs(sd[1] - 0.7) < 0.08, JSON.stringify(sd));

console.log('\n3. two fingers on the selected piece');
const uid = await page.evaluate(() => window.__studio.board.elements.find((e) => e.kind === 'product').uid);
const before = await page.evaluate((u) => { const e = window.__studio.board.elements.find((x) => x.uid === u); return { w: e.w, rot: e.rot }; }, uid);
await page.evaluate((u) => {
  // synthetic pointers: one finger on the piece, a second one, then spread and turn
  const st = document.getElementById('stage'), el = st.querySelector(`[data-uid="${u}"]`);
  const r = el.getBoundingClientRect();
  const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
  const ev = (type, id, x, y, target = st) => target.dispatchEvent(new PointerEvent(type, { pointerId: id, pointerType: 'touch',
    clientX: x, clientY: y, bubbles: true, isPrimary: id === 1 }));
  ev('pointerdown', 1, cx - 20, cy, el);
  ev('pointerdown', 2, cx + 20, cy, el);
  for (let i = 1; i <= 6; i++) {
    ev('pointermove', 1, cx - 20 - i * 10, cy + i * 3);
    ev('pointermove', 2, cx + 20 + i * 10, cy - i * 3);
  }
  ev('pointerup', 1, cx - 80, cy + 18);
  ev('pointerup', 2, cx + 80, cy - 18);
}, uid);
await page.waitForTimeout(200);
const after = await page.evaluate((u) => { const e = window.__studio.board.elements.find((x) => x.uid === u); return { w: e.w, rot: e.rot }; }, uid);
ok('pinch grows the piece', after.w > before.w * 1.5, `${before.w} → ${after.w}`);
ok('pinch turns it', Math.abs(after.rot - before.rot) > 5, `${before.rot} → ${after.rot}`);
ok('the handles are still there', (await count('.handle')) === 2);

console.log('\n4. checklist chips filter the shelf');
await page.click('#slotList .slot-chip:nth-child(4)');   // shoes
await page.waitForTimeout(100);
ok('a checklist chip sets the category', await page.evaluate(() => window.__studio.filters.slot === 'shoes' && window.__studio.shown.every((p) => p.slot === 'shoes')));
await page.evaluate(() => window.__studio.setSlot(''));

console.log('\n5. review');
await page.click('.tab[data-view="review"]');
await page.waitForTimeout(600);
const rv = await page.evaluate(() => ({
  cards: document.querySelectorAll('#reviewCards .rcard').length,
  versions: document.querySelector('#reviewCards .rcard .versions')?.children.length,
  progress: document.getElementById('reviewProgress').textContent,
  first: document.querySelector('#reviewCards .rcard')?.dataset.pid,
}));
ok('review lists every product that needs a decision', rv.cards > 300, JSON.stringify(rv));
ok('a card shows four versions', rv.versions === 4, String(rv.versions));
const decided0 = Number((rv.progress.match(/^(\d+) of/) || [])[1]);
ok('progress counts only what is filed as decided', decided0 >= 0 && decided0 < 10, rv.progress);
await page.click('#reviewCards .rcard .version[data-kind="item"]');
await page.waitForTimeout(150);
const afterChoice = await page.evaluate((pid) => ({
  choice: window.__studio.choices[pid]?.choice,
  onShelf: window.__studio.shown.some((p) => p.product_id === pid),
  progress: document.getElementById('reviewProgress').textContent,
  stored: JSON.parse(localStorage.getItem('rn.studio.choices.v1') || '{}')[pid]?.choice,
}), rv.first);
ok('choosing the item box records it', afterChoice.choice === 'item' && afterChoice.stored === 'item', JSON.stringify(afterChoice));
ok('…and the piece appears on the shelf at once', afterChoice.onShelf);
ok('progress moves', Number((afterChoice.progress.match(/^(\d+) of/) || [])[1]) === decided0 + 1, afterChoice.progress);
const placed = await page.evaluate(async (pid) => {
  const el = await window.__studio.placeProduct(pid, 0.5, 0.5);
  const p = window.__studio.productsById[pid];
  return { variant: el.variant, crop: el.crop, aspect: el.aspect, box: p.boxes.item,
    dom: !!document.querySelector(`[data-uid="${el.uid}"] .cropwrap`) };
}, rv.first);
ok('placing it uses the item box as a runtime crop', placed.variant === 'item' && JSON.stringify(placed.crop) === JSON.stringify(placed.box) && placed.dom, JSON.stringify(placed));
const second = await page.evaluate(() => document.querySelectorAll('#reviewCards .rcard')[0]?.dataset.pid);   // first undecided is now the next one
await page.click('#reviewCards .rcard .racts .danger');
await page.waitForTimeout(150);
ok('hide takes it off the shelf', await page.evaluate((pid) => window.__studio.choices[pid]?.hidden === true && !window.__studio.shown.some((p) => p.product_id === pid), second));
await page.click('#reviewCards .rcard:not(.decided):not(.hidden-card) .racts button:nth-child(3)');   // Later
await page.waitForTimeout(150);
ok('later is remembered without deciding', await page.evaluate(() => Object.values(window.__studio.choices).some((c) => c.later && !c.choice && !c.hidden)));
await page.click('#reviewCards .rcard:not(.decided):not(.hidden-card) .racts button:nth-child(1)');   // Adjust box
await page.waitForTimeout(400);
ok('adjust opens on the full photo', !(await page.$eval('#adjust', (m) => m.classList.contains('hidden'))));
const aw = await (await page.$('#adjustWrap img')).boundingBox();
await page.mouse.move(aw.x + aw.width * 0.2, aw.y + aw.height * 0.2);
await page.mouse.down();
await page.mouse.move(aw.x + aw.width * 0.7, aw.y + aw.height * 0.8, { steps: 6 });
await page.mouse.up();
await page.click('#adjustUse');
await page.waitForTimeout(150);
const custom = await page.evaluate(() => Object.values(window.__studio.choices).find((c) => c.choice === 'custom'));
ok('a drawn rectangle becomes a custom box', !!custom && Math.abs(custom.box[0] - 0.2) < 0.03 && Math.abs(custom.box[2] - 0.5) < 0.05, JSON.stringify(custom));
const file = await page.evaluate(async () => {
  const { choicesFile } = await import('./js/review.js');
  return choicesFile(window.__studio.choices);
});
ok('export choices produces the file the build script reads', file.kind === 'relatively-normal.asset-choices'
  && Object.values(file.choices).some((c) => c.choice === 'item') && Object.values(file.choices).some((c) => c.hidden));
await page.click('.tab[data-view="grid"]');

console.log('\n6. frame setting');
await page.evaluate(async () => { await window.__studio.placeInspiration(window.__studio.inspiration[3].inspiration_id); });
await page.waitForTimeout(300);
await page.click('#frameBtn');
await page.uncheck('#frMat');
await page.selectOption('#frRadius', '22');
await page.waitForTimeout(150);
const fr = await page.evaluate(() => ({ frame: window.__studio.board.frame,
  pad: getComputedStyle(document.querySelector('.el.tile')).paddingLeft,
  radius: getComputedStyle(document.querySelector('.el.tile')).borderRadius,
  settings: JSON.parse(localStorage.getItem('rn.studio.settings.v1')).frame }));
ok('frame setting changes every framed element', fr.frame.mat === false && fr.frame.radius === 22 && fr.pad === '0px' && fr.radius !== '0px', JSON.stringify(fr));
ok('…and is remembered as the default', fr.settings.radius === 22);
const info = await page.evaluate(() => window.__studio.buildInfo());
ok('the info file carries the frame', info.canvas.frame.radius === 22 && info.canvas.frame.mat === false);
ok('the info file carries the crop', info.pieces.some((p) => p.image_variant === 'item' && Array.isArray(p.image_crop)));
const exp = await page.evaluate(async () => { const c = await window.__studio.renderCanvas(); return [c.width, c.height]; });
ok('export still renders with crops on the board', exp[0] === 2160 && exp[1] === 2700);

console.log('\n7. simulated colour');
const simId = await page.evaluate(() => window.__studio.products.find((p) => p.recoloured)?.product_id);
ok('recoloured variants are in the catalogue', !!simId, String(simId));
if (simId) {
  await page.evaluate(async (id) => { await window.__studio.placeProduct(id, 0.6, 0.6); }, simId);
  const md = await page.evaluate(async () => { const { buildMarkdown } = await import('./js/export.js'); return buildMarkdown(window.__studio.buildInfo()); });
  ok('the piece list says colour simulated', md.includes('(colour simulated)') && md.includes('**Colour simulated:**'));
  ok('the variant is on the shelf as a clean cut-out', await page.evaluate((id) => window.__studio.products.find((p) => p.product_id === id).clean, simId));
  ok('the replaced UNIQLO images are hidden', await page.evaluate(() => window.__studio.products.some((p) => p.hidden && p.brand === 'UNIQLO')));
}

console.log('\n8. reopen keeps crops');
const round = await page.evaluate(async () => {
  const S = window.__studio;
  const info = S.buildInfo();
  const n = S.board.elements.length;
  S.board = (await import('./js/model.js')).createBoard('portrait');
  await S.openInfo(JSON.stringify(info));
  const e = S.board.elements.find((x) => x.variant === 'item');
  return { n, after: S.board.elements.length, crop: e?.crop, frame: S.board.frame.radius };
});
ok('every element comes back', round.n === round.after, JSON.stringify(round));
ok('with its crop and frame', Array.isArray(round.crop) && round.frame === 22);

console.log('\n9. adjust box on any image');
await page.evaluate(() => { localStorage.removeItem('rn.studio.choices.v1'); });
await page.reload();
await page.waitForFunction(() => window.__studio?.products?.length > 0, null, { timeout: 20000 });
await page.waitForTimeout(300);
const multi = await page.evaluate(() => {
  const p = window.__studio.products.find((x) => !x.clean && x.images && x.images.length >= 3);
  return p ? { pid: p.product_id, n: p.images.length, item1: p.images[1].item } : null;
});
ok('products with several screenshots carry them all', !!multi && multi.n >= 3, JSON.stringify(multi));
await page.evaluate(() => window.__studio.setView('review'));
await page.waitForTimeout(400);
await page.evaluate((pid) => {
  const card = document.querySelector(`#reviewCards .rcard[data-pid="${pid}"]`);
  card.scrollIntoView();
  card.querySelector('.racts button').click();     // Adjust box
}, multi.pid);
await page.waitForTimeout(500);
const adj1 = await page.evaluate(() => ({ counter: document.getElementById('adjCounter').textContent,
  strip: document.querySelectorAll('#adjStrip img').length, prevOff: document.getElementById('adjPrev').disabled }));
ok('the counter reads 1 of n and the filmstrip shows every image', adj1.counter === `1 of ${multi.n}` && adj1.strip === multi.n && adj1.prevOff, JSON.stringify(adj1));
await page.click('#adjNext');
await page.waitForTimeout(300);
ok('the arrow moves to the next image', (await page.$eval('#adjCounter', (e) => e.textContent)) === `2 of ${multi.n}`);
await page.click('#adjUseImage');
await page.waitForTimeout(200);
const useOne = await page.evaluate(() => {
  const b = document.querySelector('.adjust-box.main');
  return b ? { left: parseFloat(b.style.left), width: parseFloat(b.style.width) } : null;
});
ok('"Use this one" starts the box on this image, prefilled with its item box', !!useOne
  && Math.abs(useOne.left - multi.item1[0] * 100) < 0.5 && Math.abs(useOne.width - multi.item1[2] * 100) < 0.5, JSON.stringify(useOne));
await page.click('#adjustUse');
await page.waitForTimeout(300);
const saved = await page.evaluate((pid) => window.__studio.choices[pid], multi.pid);
ok('the choice records the image it was drawn on', saved.choice === 'custom' && saved.image === 1, JSON.stringify(saved));
const placed2 = await page.evaluate(async (pid) => {
  const el = await window.__studio.placeProduct(pid, 0.5, 0.5);
  const src = document.querySelector(`[data-uid="${el.uid}"] .cropwrap img`)?.getAttribute('src') || '';
  return { image: el.image, src };
}, multi.pid);
ok('placing it crops the chosen screenshot, not the first', placed2.image === 1 && placed2.src.endsWith('-1.jpg'), JSON.stringify(placed2));

console.log('\n10. several products in one image');
const gridPid = await page.evaluate(() => {
  const p = window.__studio.products.find((x) => !x.clean && x.images && x.images.some((e) => e.suggested && e.suggested.length >= 4));
  return p ? p.product_id : null;
});
ok('cell detection found at least one listing grid', !!gridPid, String(gridPid));
const target = gridPid || multi.pid;
await page.evaluate((pid) => {
  const card = document.querySelector(`#reviewCards .rcard[data-pid="${pid}"]`);
  card.scrollIntoView();
  card.querySelector('.racts button').click();
}, target);
await page.waitForTimeout(500);
if (gridPid) {
  await page.click('#adjSuggest');
  await page.waitForTimeout(200);
  const nsug = await page.$$eval('.adjust-box.split', (e) => e.length);
  ok('suggested cells appear as boxes', nsug >= 4, String(nsug));
  // delete one, keep the rest
  await page.evaluate(() => document.querySelector('.adjust-box.split').dispatchEvent(new PointerEvent('pointerdown', { bubbles: true, clientX: 0, clientY: 0 })));
}
await page.click('#adjAddBox');
const aw2 = await (await page.$('#adjustWrap img')).boundingBox();
await page.mouse.move(aw2.x + aw2.width * 0.55, aw2.y + aw2.height * 0.55);
await page.mouse.down();
await page.mouse.move(aw2.x + aw2.width * 0.9, aw2.y + aw2.height * 0.9, { steps: 6 });
await page.mouse.up();
await page.waitForTimeout(200);
ok('"Add box" draws a new box and selects it', await page.evaluate(() => !!document.querySelector('.adjust-box.split.sel') && !!document.querySelector('#adjPanel .slots')));
await page.click('#adjPanel .slots button:nth-child(5)');   // shoes
await page.fill('#adjPanel input.field', 'tan');

await page.waitForTimeout(100);
await page.click('#adjustUse');
await page.waitForTimeout(400);
const split = await page.evaluate((pid) => {
  const c = window.__studio.choices[pid];
  const last = c.splits[c.splits.length - 1];
  const id = `${pid}-S${last.n}`;
  const d = window.__studio.productsById[id];
  return { n: c.splits.length, slot: last.slot, colour: last.colour_name, id, onShelf: window.__studio.shown.some((p) => p.product_id === id),
    derived: d ? { parent: d.parent_id, brand: d.brand, brand_confidence: d.brand_confidence, slot: d.slot, colours: d.colours.length, local: d.local } : null };
}, target);
ok('the box is saved with its slot and colour name', split.slot === 'shoes' && split.colour === 'tan', JSON.stringify(split));
ok('the new piece is on the shelf at once', split.onShelf && split.derived && split.derived.local === true, JSON.stringify(split));
ok('it inherits the parent\'s brand and confidence, colours empty', split.derived.parent === target && split.derived.colours === 0);
const info3 = await page.evaluate(async (id) => {
  const el = await window.__studio.placeProduct(id, 0.3, 0.3);
  const info = window.__studio.buildInfo();
  const piece = info.pieces.find((p) => p.product_id === id);
  return { variant: el.variant, parent: piece.parent_id, index: piece.image_index, crop: piece.image_crop };
}, split.id);
ok('the info file carries parent_id for a cut piece', info3.parent === target && info3.variant === 'custom' && Array.isArray(info3.crop), JSON.stringify(info3));
const file2 = await page.evaluate(async () => { const { choicesFile } = await import('./js/review.js'); return choicesFile(window.__studio.choices); });
ok('export choices carries the splits', Object.values(file2.choices).some((c) => c.splits && c.splits.some((s) => s.slot === 'shoes' && s.colour_name === 'tan')));
await page.evaluate(() => window.__studio.setView('grid'));
const exp2 = await page.evaluate(async () => { const c = await window.__studio.renderCanvas(); return [c.width, c.height]; });
ok('export renders with a cut piece on the board', exp2[0] === 2160);

console.log(`\n${pass} passed, ${fail} failed`);
if (errors.length) console.log('page errors:\n  ' + errors.slice(0, 6).join('\n  '));
await browser.close();
server.close();
process.exit(fail ? 1 : 0);
