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
  { product_id: 'P1', slot: 'top', weight: 2, formality: 3, asset_quality: 'good',
    asset_type: 'cutout_flat', brand: 'ASPESI', product_name: 'Polo', garment_type: 'knit polo',
    price: 'CHF 156', price_confidence: 'given', product_url: '', product_url_confidence: 'input needed',
    brand_confidence: 'given', brand_role: 'recommend', material: '', material_confidence: 'input needed',
    product_name_confidence: 'given', colour_confidence: 'high', image_source: 'brand product shot',
    colours: [{ hex: '#A53B29', name: 'rust', family: 'orange', share: 0.6 }] },
  { product_id: 'P2', slot: 'shoes', weight: 3, formality: 2, asset_quality: 'weak',
    asset_type: 'tile', brand: '', product_name: '', garment_type: 'loafers', price: '',
    colours: [{ hex: '#2B3446', name: 'navy', family: 'blue', share: 0.9 }] },
];
const byId = indexById(products);

console.log('\nfilters');
ok('weak hidden by default', filterProducts(products, emptyFilters()).length === 1);
ok('weak shown on request', filterProducts(products, { ...emptyFilters(), showWeak: true }).length === 2);
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

console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
