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
await page.waitForFunction(() => window.__studio?.products?.length > 0 && window.__studio.review, null, { timeout: 20000 });
await page.evaluate(() => { localStorage.clear(); });
await page.reload();
await page.waitForFunction(() => window.__studio?.products?.length > 0 && window.__studio.review, null, { timeout: 20000 });
await page.waitForTimeout(400);

console.log('\n1. the gate and the category bar');
const gate = await page.evaluate(() => ({
  shown: window.__studio.shown.length,
  total: window.__studio.products.length,
  // clean or decided in asset-choices.json, and neither a picture of several
  // garments nor a duplicate of another row
  clean: window.__studio.products.filter((p) => (p.clean || p.choice) && !p.hidden && !p.review
    && !((p.several || []).length && p.choice !== 'custom') && !p.duplicate_of).length,
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
// every card may already be decided (the owner reviewed them all on 24 Sept):
// send a handful of decided products back to Review in this browser, the way
// "Back to Review" does, so there is something to decide
await page.evaluate(() => {
  const S = window.__studio;
  const undecided = S.products.filter((p) => !p.clean && p.full && !p.parent_id && !p.hidden && !p.choice
    && !p.review && !(p.several || []).length && !p.duplicate_of).length;
  if (undecided >= 6) return;
  const pick = S.products.filter((p) => p.full && !p.parent_id && p.choice && !p.clean && p.boxes
    && !(p.several || []).length && !p.duplicate_of && (p.images || []).length === 1).slice(0, 8);
  for (const p of pick) S.choices[p.product_id] = { review: 'test: sent back' };
  localStorage.setItem('rn.studio.choices.v1', JSON.stringify(S.choices));
});
await page.click('.tab[data-view="review"]');
await page.waitForTimeout(600);
const rv = await page.evaluate(() => ({
  cards: document.querySelectorAll('#reviewCards .rcard').length,
  versions: document.querySelector('#reviewCards .rcard .versions')?.children.length,
  progress: document.getElementById('reviewProgress').textContent,
  // the first card a choice puts on the shelf: a duplicate stays off it until
  // "Not a duplicate", a several-garment picture until a box is drawn
  first: [...document.querySelectorAll('#reviewCards .rcard')].map((c) => c.dataset.pid)
    .find((pid) => { const p = window.__studio.productsById[pid];
      return p && !p.duplicate_of && !(p.several || []).length; }),
}));
ok('review lists every product that needs a decision', rv.cards > 300, JSON.stringify(rv));
ok('a card shows four versions', rv.versions === 4, String(rv.versions));
const decided0 = Number((rv.progress.match(/^(\d+) of/) || [])[1]);
// with nothing chosen in this browser, the only products already decided are
// the ones the catalogue itself settled: a listing grid that has been cut into
// cells is hidden, and so is a UNIQLO image a recoloured variant replaced, and
// so is every product asset-choices.json has a choice for (a several-garment
// picture counts only when hidden, as on the desk)
const settled = await page.evaluate(() => window.__studio.products.filter((p) => {
  const several = (p.several || []).length && p.choice !== 'custom';
  return (!p.clean || several) && p.full && !p.parent_id && !p.review && !window.__studio.choices[p.product_id]?.review
    && (p.hidden || (p.choice && !several));
}).length);
ok('progress counts only what is filed as decided', decided0 === settled,
  `${rv.progress} — ${settled} settled by the catalogue`);
await page.click(`#reviewCards .rcard[data-pid="${rv.first}"] .version[data-kind="item"]`);
await page.waitForTimeout(150);
const afterChoice = await page.evaluate((pid) => ({
  choice: window.__studio.choices[pid]?.choice,
  onShelf: window.__studio.shown.some((p) => p.product_id === pid),
  progress: document.getElementById('reviewProgress').textContent,
  stored: JSON.parse(localStorage.getItem('rn.studio.choices.v1') || '{}')[pid]?.choice,
}), rv.first);
ok('choosing the item box records it', afterChoice.choice === 'item' && afterChoice.stored === 'item', JSON.stringify(afterChoice));
ok('…and the piece appears on the shelf at once', afterChoice.onShelf, rv.first);
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
  // a variant is its source's cut-out in another colour, so it is on the shelf
  // exactly when the source is — the measured verdict is inherited, not re-made
  const vClean = await page.evaluate(() => {
    const by = window.__studio.productsById;
    // a flat lay recoloured to its own model photo names two screenshots, not
    // a source row; its own cut is the one measured
    return window.__studio.products.filter((p) => p.recoloured && by[p.recolour_source])
      .map((p) => [p.product_id, p.clean, !!(by[p.recolour_source] || {}).clean]);
  });
  ok('a variant is on the shelf exactly when its source is',
    vClean.length > 0 && vClean.every(([, c, s]) => c === s), JSON.stringify(vClean.slice(0, 3)));
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
await page.waitForFunction(() => window.__studio?.products?.length > 0 && window.__studio.review, null, { timeout: 20000 });
await page.waitForTimeout(300);
const multi = await page.evaluate(async () => {
  const { productVersions } = await import('./js/data.js');
  // not a grid that has been cut into cells: Review shows those as their cells
  const cut = new Set(window.__studio.products.map((x) => x.parent_id).filter(Boolean));
  const p = window.__studio.products.find((x) => !x.clean && x.images && x.images.length >= 3
    && x.images[1] && x.images[1].item && !cut.has(x.product_id));
  if (!p) return null;
  const v = productVersions(p);
  return { pid: p.product_id, n: p.images.length, vers: v.length, item1: p.images[1].item,
    itemIdx1: v.findIndex((x) => x.kind === 'item' && x.image === 1) };
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
ok('the counter reads 1 of n and the filmstrip shows every version', adj1.counter === `1 of ${multi.vers}`
  && adj1.strip === multi.vers && adj1.prevOff, JSON.stringify(adj1));
await page.click('#adjNext');
await page.waitForTimeout(300);
ok('the arrow moves to the next version', (await page.$eval('#adjCounter', (e) => e.textContent)) === `2 of ${multi.vers}`);
// walk on to the item box of the second screenshot
for (let i = 1; i < multi.itemIdx1; i++) await page.click('#adjNext');
await page.waitForTimeout(300);
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
  // a grid not yet cut into cells: one that has cells shows them instead
  const cut = new Set(window.__studio.products.map((x) => x.parent_id).filter(Boolean));
  const p = window.__studio.products.find((x) => !x.clean && !x.parent_id && !cut.has(x.product_id)
    && x.images && x.images.some((e) => e.suggested && e.suggested.length >= 4));
  return p ? p.product_id : null;
});
// since 24 Sept every listing grid with detected cells has been cut; one
// left uncut would still be boxed here, and the cut ones show as their cells
const gridCards = await page.evaluate(() => { window.__studio.setView('review');
  return document.querySelectorAll('#reviewCards .gridcard').length; });
ok('a listing grid is either cut into cells or still offers its suggested boxes', !!gridPid || gridCards > 0,
  `${gridPid} / ${gridCards} grid cards`);
const target = gridPid || multi.pid;
await page.evaluate((pid) => {
  const card = document.querySelector(`#reviewCards .rcard[data-pid="${pid}"]`);
  card.scrollIntoView();
  card.querySelector('.racts button').click();
}, target);
await page.waitForTimeout(500);
if (gridPid) {
  // the cut-out opens first; the cells belong to the screenshot, so step to it
  const sugIdx = await page.evaluate(async (pid) => {
    const { productVersions } = await import('./js/data.js');
    const p = window.__studio.productsById[pid];
    const i = p.images.findIndex((e) => e.suggested && e.suggested.length >= 4);
    return productVersions(p).findIndex((v) => v.base === 'photo' && v.image === i);
  }, gridPid);
  for (let i = 0; i < sugIdx; i++) await page.click('#adjNext');
  await page.waitForTimeout(300);
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

console.log('\n11. every version, nothing over the photo');
await page.evaluate(() => { localStorage.removeItem('rn.studio.choices.v1'); });
await page.reload();
await page.waitForFunction(() => window.__studio?.products?.length > 0 && window.__studio.review, null, { timeout: 20000 });
await page.evaluate(() => window.__studio.setView('review'));
await page.waitForTimeout(500);
const wp = await page.evaluate(async () => {
  const { productVersions } = await import('./js/data.js');
  const p = window.__studio.products.find((x) => !x.clean && x.images && x.images.some((e) => e.whole));
  return p ? { pid: p.product_id, n: productVersions(p).length, photos: p.images.length } : null;
});
ok('products carry whole cut-outs', !!wp, JSON.stringify(wp));
ok('a one-photo product now has five versions, not one', wp.n >= 5, JSON.stringify(wp));
await page.evaluate((pid) => {
  const c = document.querySelector(`#reviewCards .rcard[data-pid="${pid}"]`);
  c.scrollIntoView(); c.querySelector('.racts button').click();
}, wp.pid);
await page.waitForTimeout(600);
const adj = await page.evaluate(() => ({
  counter: document.getElementById('adjCounter').textContent,
  version: document.getElementById('adjVersion').textContent,
  strip: document.querySelectorAll('#adjStrip img').length,
  overPhoto: [...document.querySelectorAll('#adjustWrap .adjust-box')].some((b) => b.textContent.trim()),
  // nothing else may land on the picture either: .hint is absolute, so a
  // label reusing that class floats over it
  strayOverPhoto: (() => {
    const w = document.getElementById('adjustWrap').getBoundingClientRect();
    return [...document.querySelectorAll('#adjust *')].filter((n) => !n.children.length
      && (n.textContent || '').trim() && !n.closest('#adjustWrap') && !n.closest('.adj-strip'))
      .some((n) => { const r = n.getBoundingClientRect();
        return r.bottom > w.top && r.top < w.bottom && r.right > w.left && r.left < w.right; });
  })(),
  labelHidden: document.getElementById('adjSelLabel').hidden,
}));
ok('the counter counts every version', adj.counter === `1 of ${wp.n}`, JSON.stringify(adj));
ok('the filmstrip holds every version', adj.strip === wp.n, String(adj.strip));
ok('the version is named in the header', adj.version.length > 0, adj.version);
ok('nothing is drawn over the photo', adj.overPhoto === false && adj.strayOverPhoto === false, JSON.stringify(adj));
// step to a whole cut-out and take it
const wholeIdx = await page.evaluate(async (pid) => {
  const { productVersions } = await import('./js/data.js');
  return productVersions(window.__studio.productsById[pid]).findIndex((v) => v.kind === 'whole');
}, wp.pid);
for (let i = 0; i < wholeIdx; i++) await page.click('#adjNext');
await page.waitForTimeout(400);
const onWhole = await page.evaluate(() => ({
  version: document.getElementById('adjVersion').textContent,
  ground: document.getElementById('adjustWrap').classList.contains('on-ground'),
  src: document.querySelector('#adjustWrap img').getAttribute('src'),
}));
ok('a whole cut-out is shown on the off-white ground', onWhole.ground && /whole\.webp$/.test(onWhole.src), JSON.stringify(onWhole));
await page.click('#adjUseImage');
await page.waitForTimeout(200);
ok('taking it whole marks a box over all of it and names it in the header',
  await page.evaluate(() => !document.getElementById('adjSelLabel').hidden
    && document.getElementById('adjSelLabel').textContent === 'this product'));
await page.click('#adjustUse');
await page.waitForTimeout(400);
const wc = await page.evaluate((pid) => window.__studio.choices[pid], wp.pid);
ok('the choice is the whole cut-out', wc.choice === 'whole' && wc.base === 'whole', JSON.stringify(wc));
const wplace = await page.evaluate(async (pid) => {
  const el = await window.__studio.placeProduct(pid, 0.5, 0.5);
  const d = document.querySelector(`[data-uid="${el.uid}"]`);
  return { base: el.base, variant: el.variant, framed: d.classList.contains('tile'),
    src: d.querySelector('img').getAttribute('src') };
}, wp.pid);
ok('placing it uses the cut-out and keeps its transparency',
  wplace.base === 'whole' && !wplace.framed && /whole\.webp$/.test(wplace.src), JSON.stringify(wplace));
const winfo = await page.evaluate(() => window.__studio.buildInfo().pieces.at(-1));
ok('the info file records the base', winfo.image_base === 'whole');

console.log('\n12. widening a crop, photo counts, the multi filter');
await page.evaluate(() => window.__studio.setView('review'));
await page.waitForTimeout(300);
const heads = await page.$$eval('#reviewCards .rhead .rphotos', (e) => e.slice(0, 5).map((x) => x.textContent));
ok('every card says how many photos', heads.length === 5 && heads.every((h) => /^\d+ photos?$/.test(h)), heads[0]);
const nBefore = await page.$$eval('#reviewCards .rcard', (e) => e.length);
await page.check('#rMulti');
await page.waitForTimeout(300);
const nAfter = await page.$$eval('#reviewCards .rcard', (e) => e.length);
// a grid cut into cells is shown as its cells, not as a card
const multiCount = await page.evaluate(() => {
  // a grid's cells are its -C rows; a box cut by hand (-S) leaves its parent a card
  const cut = new Set(window.__studio.products.filter((x) => /-C\d+$/.test(x.product_id))
    .map((x) => x.parent_id).filter(Boolean));
  return window.__studio.products.filter((p) => (!p.clean || ((p.several || []).length && p.choice !== 'custom') || p.review)
    && p.full && !p.parent_id && !cut.has(p.product_id) && (p.images || []).length > 1).length;
});
ok('"more than one photo" narrows to those', nAfter === multiCount && nAfter < nBefore, `${nBefore} → ${nAfter} (expect ${multiCount})`);
await page.uncheck('#rMulti');
await page.waitForTimeout(200);
// widen a box beyond the crop it started from: the stylist must be able to
// take back what a box cut off, not only tighten it
const widen = await page.evaluate(async () => {
  const { productVersions } = await import('./js/data.js');
  for (const p of window.__studio.products) {
    if (p.clean || p.parent_id || !(p.images || []).length) continue;
    const v = productVersions(p);
    const i = v.findIndex((x) => x.base === 'photo' && x.kind !== 'full'
      && (p.images[x.image] || {})[x.kind] && p.images[x.image][x.kind][3] < 0.9);
    if (i >= 0) return { pid: p.product_id, idx: i };
  }
  return null;
});
ok('there is a crop to widen', !!widen, JSON.stringify(widen));
if (widen) {
  await page.evaluate((pid) => {
    const c = document.querySelector(`#reviewCards .rcard[data-pid="${pid}"]`);
    c.scrollIntoView(); c.querySelector('.racts button').click();
  }, widen.pid);
  await page.waitForTimeout(500);
  await page.click(`#adjStrip img:nth-child(${widen.idx + 1})`);
  await page.waitForTimeout(300);
  await page.click('#adjUseImage');
  await page.waitForTimeout(200);
  const h0 = await page.$eval('.adjust-box.main', (b) => parseFloat(b.style.height));
  // take the bottom-right handle and pull it down past where the box stopped
  const h1 = await page.evaluate(() => {
    const wrap = document.getElementById('adjustWrap');
    const img = wrap.querySelector('img');
    const b = document.querySelector('.adjust-box.main');
    const fx = parseFloat(b.style.left) / 100 + parseFloat(b.style.width) / 100;
    const fy = parseFloat(b.style.top) / 100 + parseFloat(b.style.height) / 100;
    const at = (x, y) => {
      const r = img.getBoundingClientRect();
      return { clientX: r.left + x * r.width, clientY: r.top + y * r.height };
    };
    const ev = (type, x, y) => wrap.dispatchEvent(new PointerEvent(type,
      { bubbles: true, cancelable: true, pointerId: 1, ...at(x, y) }));
    wrap.scrollTop = Math.max(0, fy * img.clientHeight - wrap.clientHeight / 2);
    ev('pointerdown', fx - 0.005, fy - 0.005);
    ev('pointermove', fx, Math.min(1, fy + 0.2));
    ev('pointerup', fx, Math.min(1, fy + 0.2));
    return parseFloat(document.querySelector('.adjust-box.main').style.height);
  });
  ok('a crop that cut too much can be widened', h1 > h0 + 2, `${h0}% -> ${h1}%`);
  await page.click('#adjustCancel');
}


console.log('\n13. resize handles and precision');
// two fingers, for pinch and two-finger pan
async function twoFinger(a0, b0, a1, b1, steps = 10) {
  await cdp.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [
    { x: a0[0], y: a0[1], id: 1 }, { x: b0[0], y: b0[1], id: 2 }] });
  for (let s = 1; s <= steps; s++) {
    const k = s / steps;
    await cdp.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [
      { x: a0[0] + (a1[0] - a0[0]) * k, y: a0[1] + (a1[1] - a0[1]) * k, id: 1 },
      { x: b0[0] + (b1[0] - b0[0]) * k, y: b0[1] + (b1[1] - b0[1]) * k, id: 2 }] });
  }
  await cdp.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
}
const geom = () => page.evaluate(() => {
  const st = document.getElementById('adjStage');
  const b = document.querySelector('.adjust-box.sel') || document.querySelector('.adjust-box');
  const r = st.getBoundingClientRect();
  const f = (s) => parseFloat(s) / 100;
  return { stage: { x: r.left, y: r.top, w: r.width, h: r.height },
    rect: b ? [f(b.style.left), f(b.style.top), f(b.style.width), f(b.style.height)] : null,
    boxes: document.querySelectorAll('.adjust-box').length,
    handles: document.querySelectorAll('.adjust-handle').length };
});
const handlePoint = (g, name) => {
  const hx = name === 'n' || name === 's' ? 0.5 : name.includes('w') ? 0 : name.includes('e') ? 1 : 0.5;
  const hy = name === 'w' || name === 'e' ? 0.5 : name.includes('n') ? 0 : 1;
  return [g.stage.x + (g.rect[0] + g.rect[2] * hx) * g.stage.w,
    g.stage.y + (g.rect[1] + g.rect[3] * hy) * g.stage.h];
};
await page.evaluate(() => { localStorage.removeItem('rn.studio.choices.v1'); });
await page.reload();
await page.waitForFunction(() => window.__studio?.products?.length > 0 && window.__studio.review,
  null, { timeout: 20000 });
await page.evaluate(() => window.__studio.setView('review'));
await page.waitForTimeout(500);
const rp = await page.evaluate(async () => {
  const { productVersions } = await import('./js/data.js');
  const p = window.__studio.products.find((x) => !x.clean && !x.parent_id && (x.images || []).length);
  return { pid: p.product_id, full: productVersions(p).findIndex((v) => v.kind === 'full') };
});
await page.evaluate((pid) => {
  const c = document.querySelector(`#reviewCards .rcard[data-pid="${pid}"]`);
  c.scrollIntoView(); c.querySelector('.racts button').click();
}, rp.pid);
await page.waitForTimeout(700);
await page.click(`#adjStrip img:nth-child(${rp.full + 1})`);
await page.waitForTimeout(500);
await page.click('#adjUseImage');
await page.waitForTimeout(300);

const g0 = await geom();
ok('the box is painted on the picture, not the scrolling wrapper', g0.stage.h > 0
  && Math.abs(g0.rect[3] * g0.stage.h - g0.stage.h) < 2, JSON.stringify(g0.rect));
ok('a selected box has eight handles', g0.handles === 8, String(g0.handles));
// nothing is on top of them
const covered = await page.evaluate(() => {
  const st = document.getElementById('adjStage');
  const b = document.querySelector('.adjust-box.sel');
  const r = st.getBoundingClientRect(), f = (s) => parseFloat(s) / 100;
  const rect = [f(b.style.left), f(b.style.top), f(b.style.width), f(b.style.height)];
  const bad = [];
  for (const h of document.querySelectorAll('.adjust-handle')) {
    const hr = h.getBoundingClientRect();
    const el = document.elementFromPoint(hr.left + hr.width / 2, hr.top + hr.height / 2);
    if (el && !el.closest('#adjustWrap')) bad.push(h.dataset.handle + ':' + (el.id || el.className));
  }
  return { bad, rect };
});
ok('nothing covers the handles', covered.bad.length === 0, covered.bad.join(' '));

// every one of the eight, on a box that touches all four edges of the picture
const EDGES = { nw: [0, 1], n: [1], ne: [0, 1], w: [0], e: [0], sw: [0, 1], s: [1], se: [0, 1] };
const pulls = { nw: [40, 40], n: [0, 40], ne: [-40, 40], w: [40, 0], e: [-40, 0],
  sw: [40, -40], s: [0, -40], se: [-40, -40] };
let handlesOk = 0, moved = [];
for (const name of ['nw', 'n', 'ne', 'w', 'e', 'sw', 's', 'se']) {
  await page.click('#adjUseImage');            // back to the whole picture each time
  await page.waitForTimeout(150);
  const g = await geom();
  const [hx, hy] = handlePoint(g, name);
  const [dx, dy] = pulls[name];
  await touch([[hx, hy], [hx + dx, hy + dy]], { steps: 8 });
  await page.waitForTimeout(150);
  const after = (await geom()).rect;
  const wantW = dx !== 0, wantH = dy !== 0;
  const gotW = Math.abs(after[2] - g.rect[2]) > 0.01;
  const gotH = Math.abs(after[3] - g.rect[3]) > 0.01;
  // the far side must not have travelled: a handle resizes, it never moves the box
  const farX = name.includes('w') ? Math.abs((after[0] + after[2]) - (g.rect[0] + g.rect[2]))
    : Math.abs(after[0] - g.rect[0]);
  const farY = name.includes('n') ? Math.abs((after[1] + after[3]) - (g.rect[1] + g.rect[3]))
    : Math.abs(after[1] - g.rect[1]);
  if (gotW === wantW && gotH === wantH && farX < 0.01 && farY < 0.01) handlesOk++;
  else moved.push(`${name} ${JSON.stringify(g.rect)}->${JSON.stringify(after)}`);
}
ok('all eight handles resize, from a box on the picture\'s own edges', handlesOk === 8, moved.join(' | '));

// drawing a new box still works
await page.click('#adjAddBox');
const gd = await geom();
await touch([[gd.stage.x + gd.stage.w * 0.3, gd.stage.y + gd.stage.h * 0.3],
  [gd.stage.x + gd.stage.w * 0.6, gd.stage.y + gd.stage.h * 0.6]], { steps: 8 });
await page.waitForTimeout(200);
const gnew = await geom();
ok('a new box is drawn where the finger went', gnew.boxes === 2
  && Math.abs(gnew.rect[2] - 0.3) < 0.05 && Math.abs(gnew.rect[3] - 0.3) < 0.05, JSON.stringify(gnew.rect));

// moving that box: both edges travel together
const gm = await geom();
const mid = [gm.stage.x + (gm.rect[0] + gm.rect[2] / 2) * gm.stage.w,
  gm.stage.y + (gm.rect[1] + gm.rect[3] / 2) * gm.stage.h];
await touch([mid, [mid[0] + 30, mid[1] + 30]], { steps: 8 });
await page.waitForTimeout(200);
const gmv = await geom();
ok('a drag inside a box moves it and keeps its size',
  Math.abs(gmv.rect[2] - gm.rect[2]) < 0.005 && Math.abs(gmv.rect[3] - gm.rect[3]) < 0.005
  && gmv.rect[0] > gm.rect[0] + 0.01, `${JSON.stringify(gm.rect)} -> ${JSON.stringify(gmv.rect)}`);

// pinch to zoom, then the same handles again
const gz = await geom();
const cx = gz.stage.x + gz.stage.w / 2, cy = gz.stage.y + Math.min(gz.stage.h, 400) / 2;
await twoFinger([cx - 40, cy], [cx + 40, cy], [cx - 130, cy], [cx + 130, cy], 12);
await page.waitForTimeout(300);
const zoom = await page.evaluate(() => document.getElementById('adjZoom').textContent);
const gzz = await geom();
ok('pinch zooms the picture in', gzz.stage.w > gz.stage.w * 1.4, `${Math.round(gz.stage.w)} -> ${Math.round(gzz.stage.w)} (${zoom})`);
ok('the boxes scale with it', gzz.boxes === 2 && Math.abs(gzz.rect[2] - gmv.rect[2]) < 0.005,
  JSON.stringify([gmv.rect, gzz.rect]));
// zoomed in, the corner may be off the screen: pan to it the way a finger would
await page.evaluate(() => {
  const w = document.getElementById('adjustWrap');
  const st = document.getElementById('adjStage');
  const b = document.querySelector('.adjust-box.sel');
  const f = (v) => parseFloat(v) / 100;
  const x = (f(b.style.left) + f(b.style.width)) * st.offsetWidth;
  const y = (f(b.style.top) + f(b.style.height)) * st.offsetHeight;
  w.scrollLeft = x - w.clientWidth / 2;
  w.scrollTop = y - w.clientHeight / 2;
});
await page.waitForTimeout(150);
const gh = await geom();
const [zx, zy] = handlePoint(gh, 'se');
const before13 = gh.rect.slice();
await touch([[zx, zy], [zx - 60, zy - 60]], { steps: 8 });
await page.waitForTimeout(200);
const gha = (await geom()).rect;
ok('a handle still resizes once zoomed in', gha[2] < before13[2] - 0.005 && gha[3] < before13[3] - 0.005
  && Math.abs(gha[0] - before13[0]) < 0.005, `${JSON.stringify(before13)} -> ${JSON.stringify(gha)}`);
// and the drag follows the finger one to one
const px = 60 / gh.stage.w, py = 60 / gh.stage.h;
ok('dragging follows the finger exactly, with no snapping',
  Math.abs((before13[2] - gha[2]) - px) < 0.006 && Math.abs((before13[3] - gha[3]) - py) < 0.006,
  `asked ${px.toFixed(4)}/${py.toFixed(4)}, got ${(before13[2] - gha[2]).toFixed(4)}/${(before13[3] - gha[3]).toFixed(4)}`);
await page.evaluate(() => document.getElementById('adjZoom').click());
await page.waitForTimeout(200);
ok('the zoom button goes back to fit', (await page.evaluate(() => document.getElementById('adjZoom').textContent)) === 'fit');
await page.screenshot({ path: '/tmp/claude-0/shot-handles.png' });
await page.click('#adjustCancel');


console.log('\n14. panels, other picture, listing-grid cells');
await page.evaluate(() => { localStorage.removeItem('rn.studio.choices.v1'); });
await page.reload();
await page.waitForFunction(() => window.__studio?.products?.length > 0 && window.__studio.review,
  null, { timeout: 20000 });
const pan = await page.evaluate(() => {
  const ps = window.__studio.products;
  const typed = ps.filter((p) => (p.images || []).some((e) => e.type && e.type !== 'whole page'));
  const both = typed.filter((p) => (p.images || []).some((e) => e.type === 'flat lay')
    && (p.images || []).some((e) => e.type === 'on-model'));
  const flatPrimary = both.filter((p) => (p.images[p.primary] || {}).type === 'flat lay');
  return { typed: typed.length, both: both.length, flatPrimary: flatPrimary.length,
    pid: both.length ? both[0].product_id : null };
});
ok('pictures carry the type of photograph they are', pan.typed > 50, JSON.stringify(pan));
ok('some products have both a flat lay and a shot on the model', pan.both > 20, JSON.stringify(pan));
ok('the flat lay is the primary picture wherever there is one',
  pan.flatPrimary === pan.both, JSON.stringify(pan));
const vlab = await page.evaluate(async (pid) => {
  const { productVersions } = await import('./js/data.js');
  return productVersions(window.__studio.productsById[pid]).map((v) => v.label);
}, pan.pid);
ok('the filmstrip names each picture by type',
  vlab.some((l) => l.startsWith('flat lay · ')) && vlab.some((l) => l.startsWith('on-model · ')),
  vlab.slice(0, 5).join(' | '));

// "other picture" keeps where the piece sits and how wide it is
const swap = await page.evaluate(async (pid) => {
  const S = window.__studio;
  S.board = (await import('./js/model.js')).createBoard('portrait');
  const el = await S.placeProduct(pid, 0.42, 0.6);
  el.w = 0.33;
  const before = { x: el.x, y: el.y, w: el.w, image: el.image, variant: el.variant };
  S.selected = el.uid;
  S.renderBoard();
  document.querySelector('#elementBar [data-act="picture"]').click();
  const now = S.board.elements.find((e) => e.uid === el.uid);
  return { before, after: { x: now.x, y: now.y, w: now.w, image: now.image, variant: now.variant },
    hidden: document.getElementById('elPicture').hidden,
    type: (S.productsById[pid].images[now.image] || {}).type };
}, pan.pid);
ok('"other picture" is offered where there is another picture', swap.hidden === false);
ok('it changes the picture and keeps the place and the size',
  (swap.after.image !== swap.before.image || swap.after.variant !== swap.before.variant) && swap.after.x === swap.before.x
  && swap.after.w === swap.before.w, JSON.stringify(swap));
const pinfo = await page.evaluate(() => window.__studio.buildInfo().pieces.at(-1));
ok('the info file records which picture was used',
  pinfo.image_index === swap.after.image && typeof pinfo.image_type === 'string',
  JSON.stringify({ i: pinfo.image_index, t: pinfo.image_type }));

// listing-grid cells, grouped under the grid they came from
const cells = await page.evaluate(() => {
  const ps = window.__studio.products;
  const c = ps.filter((p) => /-C\d+$/.test(p.product_id));
  const parents = new Set(c.map((p) => p.parent_id));
  return { cells: c.length, parents: parents.size,
    named: c.filter((p) => p.product_name).length,
    priced: c.filter((p) => p.price).length,
    twins: c.filter((p) => p.twin).length,
    guessed: c.filter((p) => p.brand_confidence === 'guessed').length,
    given: c.filter((p) => p.brand_confidence === 'given').length,
    onShelf: c.filter((p) => p.clean).length,
    // a cell on the shelf is one whose cut-out measured clean, and its brand
    // confidence is never above the grid row's own
    dirtyOnShelf: c.filter((p) => p.clean && p.asset_type !== 'cutout_flat').length,
    aboveParent: c.filter((p) => p.brand_confidence === 'given'
      && (ps.find((q) => q.product_id === p.parent_id) || {}).brand_confidence !== 'given').length,
    parentHidden: [...parents].every((id) => (ps.find((q) => q.product_id === id) || {}).hidden) };
});
ok('every cell became a product of its own', cells.cells > 300 && cells.parents > 30, JSON.stringify(cells));
ok('a clean cell is on the shelf, the rest wait in Review', cells.onShelf > 100 && cells.onShelf < cells.cells
  && cells.dirtyOnShelf === 0, JSON.stringify(cells));
ok('a cell brand is the grid\'s, at the grid row\'s own confidence and never above it',
  cells.aboveParent === 0 && cells.given + cells.guessed > cells.cells * 0.8, JSON.stringify(cells));
ok('likely twins are flagged, not merged', cells.twins > 0, String(cells.twins));
ok('the grid itself is hidden once its cells exist', cells.parentHidden === true);
await page.evaluate(() => window.__studio.setView('review'));
await page.waitForTimeout(600);
const grp = await page.evaluate(() => {
  const g = document.querySelector('#reviewCards .cellgroup');
  return g ? { picks: g.querySelectorAll('.cellpick').length,
    accept: !![...g.querySelectorAll('button')].find((b) => b.textContent === 'Accept all cells') } : null;
});
ok('Review groups the cells under their grid, with one tap for all', !!grp && grp.picks > 0 && grp.accept,
  JSON.stringify(grp));
const took = await page.evaluate(() => {
  const g = document.querySelector('#reviewCards .cellgroup');
  const n = g.querySelectorAll('.cellpick').length;
  [...g.querySelectorAll('button')].find((b) => b.textContent === 'Accept all cells').click();
  const after = document.querySelector('#reviewCards .cellgroup');
  // a cell whose picture holds several garments is never taken whole
  const S = window.__studio;
  const left = [...after.querySelectorAll('.cellpick:not(.chosen)')].map((b) => b.dataset.pid);
  // accepted cells go to the shelf and leave the list; the heading counts them
  return { n, chosen: after.querySelectorAll('.cellpick.chosen').length,
    leftAreSeveral: left.every((pid) => (S.productsById[pid].several || []).length > 0), left,
    head: after.querySelector('.rwho').textContent };
});
ok('"accept all cells" takes the whole grid in one tap, except several-garment cells',
  took.n > 0 && took.left.length < took.n && took.leftAreSeveral
  && took.head.includes(`${took.left.length} in Review`), JSON.stringify(took));



console.log('\n15. details hidden, mixed products split apart');
await page.evaluate(() => { localStorage.removeItem('rn.studio.choices.v1'); });
await page.reload();
await page.waitForFunction(() => window.__studio?.products?.length > 0 && window.__studio.review,
  null, { timeout: 20000 });
const det = await page.evaluate(async () => {
  const { productVersions } = await import('./js/data.js');
  const p = window.__studio.products.find((x) => (x.images || []).some((e) => e.type === 'detail')
    && (x.images || []).some((e) => e.type !== 'detail'));
  if (!p) return null;
  return { pid: p.product_id,
    without: productVersions(p).length,
    with: productVersions(p, { details: true }).length,
    labels: productVersions(p).map((v) => v.label),
    primaryType: (p.images[p.primary] || {}).type };
});
ok('a product has fabric close-ups alongside real pictures', !!det, JSON.stringify(det));
ok('the filmstrip leaves the close-ups out', det.with > det.without
  && !det.labels.some((l) => l.startsWith('detail')), JSON.stringify(det));
ok('the shelf never shows a close-up as the product', det.primaryType !== 'detail', det.primaryType);
const detPics = await page.evaluate((pid) => {
  const p = window.__studio.productsById[pid];
  return { all: (p.images || []).length,
    offered: (p.images || []).filter((e) => !['detail', 'text', 'other'].includes(e.type)).length };
}, det.pid);
ok('the close-ups are kept in the data, not thrown away', detPics.all > detPics.offered,
  JSON.stringify(detPics));
// the toggle brings them back in Adjust box
await page.evaluate(() => window.__studio.setView('review'));
await page.waitForTimeout(500);
const opened = await page.evaluate((pid) => {
  const c = document.querySelector(`#reviewCards .rcard[data-pid="${pid}"]`);
  if (!c) return false;
  c.scrollIntoView(); c.querySelector('.racts button').click(); return true;
}, det.pid);
if (opened) {
  await page.waitForTimeout(700);
  const before = await page.$$eval('#adjStrip img', (e) => e.length);
  ok('"show details" is offered where there are details',
    (await page.$eval('#adjDetailsWrap', (e) => e.hidden)) === false);
  await page.check('#adjDetails');
  await page.waitForTimeout(400);
  const after = await page.$$eval('#adjStrip img', (e) => e.length);
  ok('...and brings them into the filmstrip', after > before, `${before} → ${after}`);
  await page.click('#adjustCancel');
}

const sp = await page.evaluate(() => {
  const ps = window.__studio.products;
  const sib = ps.filter((p) => /-V\d+$/.test(p.product_id));
  const pairs = sib.map((p) => {
    const parent = ps.find((q) => q.product_id === p.product_id.replace(/-V\d+$/, ''));
    return parent ? { a: parent, b: p } : null;
  }).filter(Boolean);
  const sameName = pairs.filter(({ a, b }) => a.product_name && a.product_name === b.product_name);
  const diffColour = pairs.filter(({ a, b }) => (a.colours[0] || {}).hex !== (b.colours[0] || {}).hex);
  // a split row that measured clean is its own screenshot's cut-out and, like
  // every clean flat lay, needs no pictures to review
  const ownPics = sib.filter((p) => (p.images || []).length > 0 || p.clean);
  return { siblings: sib.length, pairs: pairs.length, sameName: sameName.length,
    diffColour: diffColour.length, ownPics: ownPics.length,
    derived: sib.filter((p) => p.parent_id).length };
});
ok('mixed products were split into rows of their own', sp.siblings > 20, JSON.stringify(sp));
ok('each split row has its own pictures', sp.ownPics === sp.siblings, JSON.stringify(sp));
ok('each split row has its own colour', sp.diffColour === sp.pairs, JSON.stringify(sp));
ok('a split row is a product, not a piece cut from one', sp.derived === 0, String(sp.derived));
ok('the style name is kept on both so they stay linked', sp.sameName > 0, JSON.stringify(sp));



console.log('\n16. setting the slot from the desk');
await page.evaluate(() => { localStorage.removeItem('rn.studio.choices.v1'); });
await page.reload();
await page.waitForFunction(() => window.__studio?.ready === true, null, { timeout: 20000 });
await page.evaluate(() => window.__studio.setView('review'));
await page.waitForTimeout(600);
const sl0 = await page.evaluate(() => {
  const c = document.querySelector('#reviewCards .rcard');
  return { pid: c.dataset.pid, buttons: [...c.querySelectorAll('.rslots button')].map((b) => b.textContent),
    slot: window.__studio.productsById[c.dataset.pid].slot };
});
ok('a Review card offers the eight slots',
  sl0.buttons.join(' ') === 'layer top bottom dress shoes bag accessory base', sl0.buttons.join(' '));
const want = sl0.slot === 'dress' ? 'shoes' : 'dress';
await page.evaluate((w) => {
  const c = document.querySelector('#reviewCards .rcard');
  [...c.querySelectorAll('.rslots button')].find((b) => b.textContent === w).click();
}, want);
await page.waitForTimeout(300);
const sl1 = await page.evaluate((pid) => ({
  choice: window.__studio.choices[pid],
  live: window.__studio.productsById[pid].slot,
  conf: window.__studio.productsById[pid].slot_confidence,
  reviewed: !!(window.__studio.choices[pid] || {}).choice,
}), sl0.pid);
ok('picking a slot records it', sl1.choice.slot === want, JSON.stringify(sl1));
ok('...and the catalogue in memory follows at once', sl1.live === want, JSON.stringify(sl1));
ok('...as the stylist\'s own, not inherited', sl1.conf === 'given', sl1.conf);
ok('picking a slot does not decide the picture', sl1.reviewed === false);
const slotFile = await page.evaluate(async () => {
  const { choicesFile } = await import('./js/review.js');
  return choicesFile(window.__studio.choices);
});
ok('the slot travels in asset-choices.json', slotFile.choices[sl0.pid].slot === want,
  JSON.stringify(slotFile.choices[sl0.pid]));

// the two filters
const filt = await page.evaluate(async () => {
  const ps = window.__studio.products;
  const inherited = ps.filter((p) => p.slot_confidence === 'inherited').length;
  const guessed = ps.filter((p) => p.slot_confidence === 'guessed').length;
  const none = ps.filter((p) => !p.slot).length;
  return { inherited, guessed, none };
});
ok('the catalogue marks the slots worth a look', filt.inherited > 50 && filt.guessed > 100,
  JSON.stringify(filt));
await page.check('#rCheckSlot');
await page.waitForTimeout(400);
const onlyCheck = await page.evaluate(() => {
  const ids = [...document.querySelectorAll('#reviewCards .rcard')].map((c) => c.dataset.pid);
  const cells = document.querySelectorAll('#reviewCards .cellpick').length;
  // a listing grid is kept when its CELLS are flagged, which is the point
  const cellsBy = {};
  for (const p of window.__studio.products) {
    if (p.parent_id) (cellsBy[p.parent_id] = cellsBy[p.parent_id] || []).push(p);
  }
  return { cards: ids.length, cells,
    allFlagged: ids.every((i) => ['inherited', 'guessed']
      .includes(window.__studio.productsById[i].slot_confidence)
      || (cellsBy[i] || []).some((c) => ['inherited', 'guessed'].includes(c.slot_confidence))) };
});
ok('"slot worth a look" shows only rows whose slot, or whose cells\' slots, were inferred',
  onlyCheck.allFlagged, JSON.stringify(onlyCheck));
await page.uncheck('#rCheckSlot');
await page.check('#rNoSlot');
await page.waitForTimeout(400);
const onlyNone = await page.evaluate(() => {
  const cells = [...document.querySelectorAll('#reviewCards .cellpick .cellslot')];
  return { cells: cells.length, allUnset: cells.every((c) => c.textContent.startsWith('set slot')) };
});
ok('"no slot" reaches the grid cells, which is where the gaps are',
  onlyNone.cells > 0 && onlyNone.allUnset, JSON.stringify(onlyNone));   // read by eye, few cells lack a slot
// a cell can be given a slot too
await page.evaluate(() => document.querySelector('#reviewCards .cellpick .cellslot').click());
await page.waitForTimeout(300);
const cellRow = await page.evaluate(() => {
  const rows = [...document.querySelectorAll('#reviewCards .cellgroup .rslots')];
  if (!rows.length) return null;
  const b = [...rows[0].querySelectorAll('button')].find((x) => x.textContent === 'top');
  b.click();
  return true;
});
await page.waitForTimeout(300);
ok('a grid cell takes a slot the same way', cellRow === true
  && (await page.evaluate(() => Object.values(window.__studio.choices).some((c) => c.slot === 'top'))));
await page.uncheck('#rNoSlot');

// and on the canvas
await page.evaluate(() => window.__studio.setView('grid'));
await page.waitForTimeout(300);
const piece = await page.evaluate(async () => {
  const S = window.__studio;
  S.board = (await import('./js/model.js')).createBoard('portrait');
  const el = await S.placeProduct(S.shown[0].product_id, 0.5, 0.5);
  S.selected = el.uid; S.renderBoard();
  const bar = document.getElementById('pieceSlots');
  return { pid: el.product_id, hidden: bar.hidden,
    buttons: [...bar.querySelectorAll('button')].map((b) => b.textContent) };
});
ok('the selected piece offers the slots too', piece.hidden === false
  && piece.buttons.length === 8, JSON.stringify(piece));
await page.evaluate(() => {
  const bar = document.getElementById('pieceSlots');
  [...bar.querySelectorAll('button')].find((b) => b.textContent === 'bag').click();
});
await page.waitForTimeout(300);
ok('setting it from the canvas records it the same way',
  await page.evaluate((pid) => (window.__studio.choices[pid] || {}).slot === 'bag'
    && window.__studio.productsById[pid].slot === 'bag', piece.pid));


console.log('\n17. "…" on a tile: Remove, Back to Review; the same in the canvas bar; Removed in Review');
await page.click('.tab[data-view="grid"]');
await page.waitForTimeout(300);
await page.evaluate(() => { window.__studio.setSlot(''); document.getElementById('grid').scrollTop = 0; });
await page.waitForTimeout(200);
const n0 = await pieces();
const [pidA, pidB] = await page.$$eval('#grid .cell', (cs) => cs.slice(0, 2).map((c) => c.dataset.pid));
const moreA = await (await page.$(`#grid .cell[data-pid="${pidA}"] .more`)).boundingBox();
// a long press on "…" must not lift the piece, and a tap on it must not place it
await touch([[moreA.x + moreA.width / 2, moreA.y + moreA.height / 2]], { holdMs: 500 });
await page.waitForTimeout(300);
ok('a long press on "…" neither lifts nor places', (await pieces()) === n0
  && (await page.evaluate(() => document.getElementById('drag').hidden)));
await page.evaluate(() => { document.getElementById('tileMenu').hidden = true; });
await tap(moreA.x + moreA.width / 2, moreA.y + moreA.height / 2);
await page.waitForTimeout(300);
ok('a tap on "…" opens the menu and places nothing', (await pieces()) === n0
  && !(await page.evaluate(() => document.getElementById('tileMenu').hidden)));
const rm = await (await page.$('#tileMenu [data-shelf-act="remove"]')).boundingBox();
await tap(rm.x + rm.width / 2, rm.y + rm.height / 2);
await page.waitForTimeout(400);
ok('Remove takes it off the shelf, as a choice', await page.evaluate((pid) => window.__studio.choices[pid]?.hidden === true
  && !window.__studio.shown.some((p) => p.product_id === pid)
  && JSON.parse(localStorage.getItem('rn.studio.choices.v1'))[pid]?.hidden === true, pidA));
ok('…and nothing was placed or deleted', (await pieces()) === n0
  && (await page.evaluate((pid) => !!window.__studio.productsById[pid], pidA)));
const badge0 = await page.evaluate(() => Number(document.getElementById('reviewBadge').textContent || 0));
const moreB = await (await page.$(`#grid .cell[data-pid="${pidB}"] .more`)).boundingBox();
await tap(moreB.x + moreB.width / 2, moreB.y + moreB.height / 2);
await page.waitForTimeout(300);
const bk = await (await page.$('#tileMenu [data-shelf-act="review"]')).boundingBox();
await tap(bk.x + bk.width / 2, bk.y + bk.height / 2);
await page.waitForTimeout(400);
ok('Back to Review takes it off the shelf and makes it undecided', await page.evaluate((pid) => {
  const S = window.__studio;
  return !!S.choices[pid]?.review && !S.choices[pid]?.choice && !S.shown.some((p) => p.product_id === pid);
}, pidB));
ok('…and the Review count goes up by one', (await page.evaluate(() => Number(document.getElementById('reviewBadge').textContent || 0))) === badge0 + 1);
ok('both travel in asset-choices.json', await page.evaluate(async ([a, b]) => {
  const { choicesFile } = await import('./js/review.js');
  const f = choicesFile(window.__studio.choices).choices;
  return f[a]?.hidden === true && typeof f[b]?.review === 'string';
}, [pidA, pidB]));

// the canvas bar: the same two actions for the selected piece, beside Delete
const [pidC, pidD] = await page.evaluate(() => window.__studio.shown.slice(0, 2).map((p) => p.product_id));
await page.evaluate(async (pid) => { const el = await window.__studio.placeProduct(pid, 0.5, 0.5); window.__studio.select(el.uid); }, pidC);
await page.waitForTimeout(300);
ok('the canvas bar has Remove and Back to Review next to Delete', await page.evaluate(() => {
  const acts = [...document.querySelectorAll('#elementBar button')].filter((b) => !b.hidden).map((b) => b.dataset.act);
  const i = acts.indexOf('delete');
  return i >= 0 && acts[i + 1] === 'remove' && acts[i + 2] === 'review' && !document.getElementById('elementBar').hidden;
}));
const eb = await (await page.$('#elRemove')).boundingBox();
await tap(eb.x + eb.width / 2, eb.y + eb.height / 2);
await page.waitForTimeout(300);
ok('Remove on the canvas bar removes the selected piece from the shelf', await page.evaluate((pid) =>
  window.__studio.choices[pid]?.hidden === true && !window.__studio.shown.some((p) => p.product_id === pid), pidC));
await page.evaluate(async (pid) => { const el = await window.__studio.placeProduct(pid, 0.4, 0.4); window.__studio.select(el.uid); }, pidD);
await page.waitForTimeout(300);
const er = await (await page.$('#elReview')).boundingBox();
await tap(er.x + er.width / 2, er.y + er.height / 2);
await page.waitForTimeout(300);
ok('Back to Review on the canvas bar sends it to Review', await page.evaluate((pid) =>
  !!window.__studio.choices[pid]?.review && !window.__studio.shown.some((p) => p.product_id === pid), pidD));

// Review: Remove, not Hide; Removed lists what was removed; Restore sends it back to Review
await page.click('.tab[data-view="review"]');
await page.waitForTimeout(400);
ok('Review says Remove, never Hide', await page.evaluate(() => {
  const labels = [...document.querySelectorAll('#reviewCards .racts button')].map((b) => b.textContent);
  return labels.includes('Remove') && !labels.includes('Hide') && !labels.includes('Unhide');
}));
ok('a piece sent back shows why', await page.evaluate((pid) => /sent back/.test(
  document.querySelector(`#reviewCards .rcard[data-pid="${pid}"] .why.back`)?.textContent || ''), pidB));
await page.check('#rRemoved');
await page.waitForTimeout(400);
const removed = await page.$$eval('#reviewCards .rcard', (cs) => cs.map((c) => c.dataset.pid));
ok('Removed lists what was removed', removed.includes(pidA) && removed.includes(pidC), `${removed.length} cards`);
await page.click(`#reviewCards .rcard[data-pid="${pidA}"] .racts button[data-act="restore"]`);
await page.waitForTimeout(300);
const restoredA = await page.evaluate((pid) => ({ c: window.__studio.choices[pid],
  listed: !!document.querySelector(`#reviewCards .rcard[data-pid="${pid}"]`) }), pidA);
ok('Restore sends it back to Review, undecided', !restoredA.c?.hidden && !!restoredA.c?.review && !restoredA.listed,
  JSON.stringify(restoredA));
await page.uncheck('#rRemoved');
await page.waitForTimeout(300);
await page.click(`#reviewCards .rcard[data-pid="${pidA}"] .version[data-kind="cutout"]`);
await page.waitForTimeout(300);
ok('deciding it again puts it back on the shelf', await page.evaluate((pid) => {
  const c = window.__studio.choices[pid];
  return c?.choice === 'cutout' && !c.review && !c.hidden;
}, pidA));
await page.click('.tab[data-view="grid"]');
await page.waitForTimeout(300);
ok('…where it shows again', await page.evaluate((pid) => window.__studio.shown.some((p) => p.product_id === pid), pidA));

console.log(`\n${pass} passed, ${fail} failed`);
if (errors.length) console.log('page errors:\n  ' + errors.slice(0, 6).join('\n  '));
await browser.close();
server.close();
process.exit(fail ? 1 : 0);
