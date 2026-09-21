// Pure functions, no browser. node studio/test/unit.mjs
import * as M from '../js/model.js';
import * as C from '../js/colour.js';
import { filterProducts, emptyFilters, matrixCounts, indexById } from '../js/data.js';
import { parsePrice, buildInfo, buildMarkdown } from '../js/export.js';

let pass = 0, fail = 0;
const ok = (n, c, extra = '') => { c ? (pass++, console.log(`  ok   ${n}`))
  : (fail++, console.log(`  FAIL ${n} ${extra}`)); };
const eq = (n, a, b) => ok(n, JSON.stringify(a) === JSON.stringify(b), `${JSON.stringify(a)} != ${JSON.stringify(b)}`);

console.log('\ncolour');
ok('hex parses', JSON.stringify(C.hexToRgb('#A53B29')) === '[165,59,41]');
ok('bad hex is null', C.hexToRgb('nope') === null);
ok('two rusts are close', C.oklabDistance(C.hexToOklab('#A53B29'), C.hexToOklab('#AC431E')) < 0.06);
ok('rust and plum are far', C.oklabDistance(C.hexToOklab('#A53B29'), C.hexToOklab('#341A2C')) > 0.2);
ok('ink flips on dark', C.readableInk('#221F1C') === '#ffffff' && C.readableInk('#F3EFE7') === '#1e1a16');
const ranked = C.rankByLook(
  [{ product_id: 'far', colours: [{ hex: '#2B3446' }] },
   { product_id: 'near', colours: [{ hex: '#AC431E' }] }],
  { colours: [{ hex: '#A53B29' }] });
eq('rankByLook puts the near one first', ranked.map((p) => p.product_id), ['near', 'far']);
ok('rankByLook does not mutate its input', true);
const merged = C.mergeColours([{ hex: '#A53B29', share: 0.4 }, { hex: '#A73C2B', share: 0.2 },
  { hex: '#2B3446', share: 0.3 }]);
ok('near colours merge and sum', merged.length === 2 && Math.abs(merged[0].share - 0.6) < 1e-9,
  JSON.stringify(merged));

console.log('\nmodel');
const b = M.createBoard('portrait');
const e1 = M.addElement(b, { product_id: 'P1', aspect: 0.8 });
const e2 = M.addElement(b, { product_id: 'P2', aspect: 1.5 });
ok('z rises with each element', e2.z > e1.z);
M.sendBack(b, e2.uid);
ok('send back swaps the order', M.stacked(b)[0].uid === e2.uid);
M.bringForward(b, e2.uid);
ok('bring forward puts it back', M.stacked(b)[1].uid === e2.uid);
const dup = M.duplicateElement(b, e1.uid);
ok('duplicate offsets the copy', dup.x > e1.x && dup.uid !== e1.uid);
M.removeElement(b, dup.uid);
ok('remove takes it away', b.elements.length === 2);
eq('elementBox maths', M.elementBox({ x: 0.5, y: 0.5, w: 0.3, aspect: 2 }, 1000, 1250),
  { w: 300, h: 150, cx: 500, cy: 625, x: 350, y: 550 });
ok('slug is date then title', M.dateSlug('One rust, top to toe!', new Date(2026, 8, 21))
  === '2026-09-21-one-rust-top-to-toe');
ok('empty title still gets a name', M.dateSlug('', new Date(2026, 8, 21)) === '2026-09-21-untitled');

const products = [
  { product_id: 'P1', slot: 'top', weight: 2, formality: 3, asset_quality: 'good', clean: true,
    asset_type: 'cutout_flat', brand: 'ASPESI', product_name: 'Polo', garment_type: 'knit polo',
    price: 'CHF 156', price_confidence: 'given', product_url: '', product_url_confidence: 'input needed',
    brand_confidence: 'given', brand_role: 'recommend', material: '', material_confidence: 'input needed',
    product_name_confidence: 'given', colour_confidence: 'high', image_source: 'brand product shot',
    colours: [{ hex: '#A53B29', name: 'rust', family: 'orange', share: 0.6 }] },
  { product_id: 'P2', slot: 'shoes', weight: 3, formality: 2, asset_quality: 'weak', clean: false,
    asset_type: 'tile', brand: '', product_name: '', garment_type: 'loafers', price: '',
    colours: [{ hex: '#2B3446', name: 'navy', family: 'blue', share: 0.9 }] },
];
const byId = indexById(products);

console.log('\nfilters');
ok('unreviewed hidden by default', filterProducts(products, emptyFilters(), {}).length === 1);
ok('unreviewed shown on request', filterProducts(products, { ...emptyFilters(), showUnreviewed: true }, {}).length === 2);
ok('slot filter', filterProducts(products, { ...emptyFilters(), slot: 'top' }).length === 1);
ok('colour family filter', filterProducts(products, { ...emptyFilters(), family: 'orange' }).length === 1);
ok('search hits the brand', filterProducts(products, { ...emptyFilters(), search: 'aspesi' }).length === 1);
ok('search hits a colour name', filterProducts(products, { ...emptyFilters(), search: 'rust' }).length === 1);
ok('search misses cleanly', filterProducts(products, { ...emptyFilters(), search: 'zzz' }).length === 0);
eq('matrix counts by formality:weight', matrixCounts(products), { '3:2': 1, '2:3': 1 });

console.log('\nhelpers');
const b2 = M.createBoard();
M.addElement(b2, { product_id: 'P1', aspect: 1 });
const check = M.slotChecklist(b2, byId);
ok('checklist knows what is missing',
  check.find((c) => c.slot === 'top').count === 1 && check.find((c) => c.slot === 'bag').count === 0);
const ax = M.axes(b2, byId);
ok('axes average the pieces', ax.weight === 2 && ax.formality === 3 && ax.n === 1);
ok('axes on an empty board are null', M.axes(M.createBoard(), byId).weight === null);
eq('swatch strip only carries what is on the board',
  M.swatchStrip(b2, byId).map((c) => c.hex), ['#A53B29']);

console.log('\nhistory');
const h = M.createHistory();
M.commit(h, b2);
M.addElement(b2, { product_id: 'P2', aspect: 1 });
const back = M.undo(h, b2);
ok('undo returns the earlier board', back.elements.length === 1);
const fwd = M.redo(h, back);
ok('redo returns the later board', fwd.elements.length === 2);
ok('undo on an empty history is null', M.undo(M.createHistory(), b2) === null);

console.log('\nexport');
eq('price splits', parsePrice('CHF 156'), { price: '156', currency: 'CHF' });
eq('price with a symbol', parsePrice('€325,00'), { price: '325,00', currency: '€' });
eq('unrecognised price is kept whole', parsePrice('on request'), { price: 'on request', currency: '' });
eq('empty price stays empty', parsePrice(''), { price: '', currency: '' });
const b3 = M.createBoard('landscape');
b3.title = 'Rust twice';
M.addElement(b3, { product_id: 'P1', aspect: 1, x: 0.4, y: 0.6, w: 0.25 });
M.addElement(b3, { product_id: 'P2', aspect: 1 });
const info = buildInfo(b3, byId, {}, { date: new Date(2026, 8, 21) });
ok('info knows the canvas size', info.canvas.width === 2912 && info.canvas.height === 2184);
ok('info numbers the pieces in order', info.pieces.map((p) => p.label).join() === '1,2');
ok('info carries confidences', info.pieces[0].brand_confidence === 'given'
  && info.pieces[0].product_url_confidence === 'input needed');
ok('info invents nothing for an empty field',
  info.pieces[1].brand === '' && info.pieces[1].price === '' && info.pieces[1].material === '');
ok('info keeps placement', info.pieces[0].placement.x === 0.4 && info.pieces[0].placement.w === 0.25);
ok('info has no inspiration when none was chosen', info.inspiration === null);
const md = buildMarkdown(info);
ok('markdown has a row per piece', (md.match(/^\| \d /gm) || []).length === 2, md);
ok('markdown flags what to confirm', md.includes('Confirm before publishing'));
ok('markdown leaves an unknown link empty', /\| 2 \|  \| loafers \| navy \|  \|  \|/.test(md), md);



// ------------------------------------------------------------- 22 Sept additions
{
  const { cropLayout, shownAspect, DEFAULT_FRAME, createBoard: cb } = M;
  const { onShelf, effectiveChoice, isReviewed } = await import('../js/data.js');
  const { choicesFile, choiceBox } = await import('../js/review.js');
  console.log('\ncrops and the gate');
  eq('cropLayout maps a quarter box', cropLayout([0.5, 0.5, 0.5, 0.5]), { imgW: 2, imgH: 2, left: -1, top: -1 });
  const full = { full: { w: 1000, h: 2000 } };
  ok('shownAspect follows the crop', Math.abs(shownAspect(full, 'item', [0, 0, 1, 0.25]) - 2) < 1e-9);
  ok('shownAspect is null for the cut-out', shownAspect(full, 'cutout', null) === null);
  ok('a new board carries the default frame', JSON.stringify(cb().frame) === JSON.stringify(DEFAULT_FRAME));
  const clean = { product_id: 'C', clean: true };
  const raw = { product_id: 'R', clean: false, full: { w: 10, h: 10 }, boxes: { item: [0, 0, 1, 1], person: [0, 0, 1, 1] } };
  const filed = { product_id: 'F', clean: false, choice: 'person', custom_box: null, full: { w: 1, h: 1 }, boxes: { person: [0.1, 0.1, 0.5, 0.5] } };
  const hiddenFiled = { product_id: 'H', clean: false, hidden: true };
  ok('clean cut-outs pass the gate', onShelf(clean, {}, false));
  ok('unreviewed pieces wait', !onShelf(raw, {}, false));
  ok('the toggle lets them through', onShelf(raw, {}, true));
  ok('a browser choice puts a piece on the shelf', onShelf(raw, { R: { choice: 'item' } }, false));
  ok('a browser hide takes a clean piece off', !onShelf(clean, { C: { hidden: true } }, true));
  ok('a filed choice counts as reviewed', isReviewed(filed, {}) && onShelf(filed, {}, false));
  ok('a filed hide is honoured', !onShelf(hiddenFiled, {}, true));
  ok('the browser overrides the file', onShelf(hiddenFiled, { H: { choice: 'full' } }, false));
  eq('choiceBox reads a filed box', choiceBox(filed, effectiveChoice(filed, {})), [0.1, 0.1, 0.5, 0.5]);
  eq('choiceBox for full is the whole image', choiceBox(raw, { choice: 'full' }), [0, 0, 1, 1]);
  ok('choiceBox for the cut-out is null', choiceBox(raw, { choice: 'cutout' }) === null);
  const f = choicesFile({ A: { choice: 'item' }, B: { hidden: true, choice: 'item' }, C: { later: true },
    D: { choice: 'custom', box: [0.123456, 0.2, 0.3, 0.4] } });
  eq('choices file keeps only decisions', Object.keys(f.choices).sort(), ['A', 'B', 'D']);
  ok('hidden wins over a choice', f.choices.B.hidden === true && !f.choices.B.choice);
  ok('boxes are rounded', f.choices.D.box[0] === 0.1235);

  console.log('\ncolour simulated');
  const sim = { product_id: 'S', slot: 'top', recoloured: true, recolour_source: 'B062-P016', brand: 'UNIQLO',
    brand_confidence: 'given', product_name: 'crew neck sweatshirt', colours: [{ hex: '#8B2E23', name: 'rust' }],
    image_source: 'colour simulated: recoloured', price: '', product_url: '' };
  const b4 = M.createBoard();
  M.addElement(b4, { product_id: 'S', aspect: 1 });
  const info2 = buildInfo(b4, { S: sim }, {}, { date: new Date(2026, 8, 22) });
  ok('info flags a simulated colour', info2.pieces[0].colour_simulated === true && info2.pieces[0].recolour_source === 'B062-P016');
  const md2 = buildMarkdown(info2);
  ok('markdown says colour simulated beside the piece', md2.includes('rust (colour simulated)'));
  ok('markdown adds the disclosure line', md2.includes('**Colour simulated:**'));
  ok('info records the image variant', info2.pieces[0].image_variant === 'cutout');
}

// ------------------------------------------------------------- 23 Sept additions
{
  const { derivedProducts, splitId, imageEntry } = await import('../js/data.js');
  const { choicesFile } = await import('../js/review.js');
  console.log('\nsplits and derived products');
  const parent = { product_id: 'B062-P018', slot: 'multiple', brand: 'Sézane', brand_confidence: 'guessed',
    brand_role: 'not filed', shop: 'sezane.com', garment_type: 'listing grid', weight: 2, formality: 2,
    clean: false, full: { path: 'full/B062-P018.jpg', w: 1000, h: 1400 },
    images: [{ path: 'full/B062-P018.jpg', w: 1000, h: 1400 }, { path: 'full/B062-P018-1.jpg', w: 800, h: 1000 }],
    colours: [], image_source: 'brand product shot' };
  const choices = { 'B062-P018': { choice: 'custom', box: [0, 0, 0.5, 0.5], image: 1,
    splits: [{ n: 1, image: 1, box: [0.5, 0, 0.5, 0.5], slot: 'shoes', colour_name: 'tan' },
      { n: 2, image: 0, box: [0, 0.5, 0.5, 0.5], slot: '', colour_name: '' }] } };
  eq('splitId', splitId('B062-P018', 3), 'B062-P018-S3');
  ok('imageEntry reads the list', imageEntry(parent, 1).w === 800);
  ok('imageEntry falls back to full for index 0', imageEntry({ full: { path: 'x', w: 1, h: 2 } }, 0).h === 2);
  ok('imageEntry is null past the end', imageEntry(parent, 5) === null);
  const d = derivedProducts([parent], choices);
  ok('one derived product per box', d.length === 2, String(d.length));
  ok('ids are parent plus suffix', d[0].product_id === 'B062-P018-S1' && d[0].parent_id === 'B062-P018');
  ok('the slot and colour name are hers', d[0].slot === 'shoes' && d[0].colour_name_text === 'tan');
  ok('a box without a slot keeps the parent\'s', d[1].slot === 'multiple');
  ok('brand confidence is inherited, never upgraded', d[0].brand === 'Sézane' && d[0].brand_confidence === 'guessed');
  ok('it is a runtime crop of the right image', d[0].choice === 'custom' && d[0].image === 1
    && JSON.stringify(d[0].custom_box) === JSON.stringify([0.5, 0, 0.5, 0.5]) && d[0].full.w === 800);
  ok('no colours until the rebuild', d[0].colours.length === 0);
  ok('the catalogue\'s row wins once it exists', derivedProducts([parent, { product_id: 'B062-P018-S1' }], choices).length === 1);
  const f = choicesFile(choices);
  ok('choices file carries image and splits', f.choices['B062-P018'].image === 1 && f.choices['B062-P018'].splits.length === 2
    && f.choices['B062-P018'].splits[0].slot === 'shoes' && f.choices['B062-P018'].splits[0].colour_name === 'tan');
  ok('shownAspect uses the chosen image', Math.abs(M.shownAspect(parent, 'custom', [0, 0, 0.5, 0.5], 1) - 0.8) < 1e-9);
}
console.log(`\nafter 23 Sept: ${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
