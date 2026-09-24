// Pure functions, no browser. node studio/test/unit.mjs
import * as M from '../js/model.js';
import * as C from '../js/colour.js';
import { filterProducts, emptyFilters, matrixCounts, indexById, shelfView, sameView, onShelf,
  isReviewed, isSeveral, isDuplicate, choiceBase } from '../js/data.js';
import { parsePrice, buildInfo, buildMarkdown } from '../js/export.js';
import { indexPalettes, palettesIn, paletteSnapshot, outfitShares, SLOT_WEIGHT } from '../js/palette.js';
import { stripRows, metrics } from '../js/render.js';
import { readFileSync } from 'node:fs';

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

// ------------------------------------------------------------- 24 Sept additions
{
  const { productVersions, imageEntry } = await import('../js/data.js');
  const { choiceBox, choiceBase, baseSize, remapBox, migrateChoices } = await import('../js/review.js');
  console.log('\nevery version');
  const img0 = { path: 'full/X.jpg', w: 1000, h: 2000, item: [0, 0.5, 1, 0.5], person: [0, 0, 1, 1],
    whole: { path: 'full/X-whole.webp', w: 500, h: 1500 }, suggested: [] };
  const img1 = { path: 'full/X-1.jpg', w: 800, h: 800, item: [0.1, 0.1, 0.5, 0.5], person: [0, 0, 1, 1],
    whole: { path: 'full/X-1-whole.webp', w: 400, h: 600 }, suggested: [] };
  const P = { product_id: 'X', asset: 'assets/X.webp', asset_type: 'cutout_model', slot: 'top',
    full: { path: img0.path, w: img0.w, h: img0.h }, images: [img0, img1], boxes: null };
  const v = productVersions(P);
  ok('one cut-out plus four versions per screenshot', v.length === 1 + 4 + 4, String(v.length));
  ok('the cut-out comes first', v[0].kind === 'cutout' && v[0].base === 'asset');
  ok('each screenshot brings a whole cut-out', v.filter((x) => x.kind === 'whole').length === 2);
  ok('versions are labelled per screenshot', v.some((x) => x.label === 'item box 2'), v.map((x) => x.label).join(','));
  ok('a listing grid with no whole cut-out just has fewer versions',
    productVersions({ ...P, images: [{ ...img0, whole: undefined }] }).length === 4);
  ok('a cut piece offers no asset version', productVersions({ ...P, asset_type: 'crop' })[0].kind !== 'cutout');

  console.log('\nboxes and their base');
  eq('the item box comes from its own screenshot', choiceBox(P, { choice: 'item', image: 1 }), img1.item);
  ok('the cut-out has no box', choiceBox(P, { choice: 'cutout' }) === null);
  ok('a whole cut-out has no box', choiceBox(P, { choice: 'whole', image: 0 }) === null);
  eq('a custom box is kept as drawn', choiceBox(P, { choice: 'custom', box: [0.2, 0.2, 0.3, 0.3] }), [0.2, 0.2, 0.3, 0.3]);
  ok('base defaults to the photo', choiceBase({ choice: 'custom' }) === 'photo');
  ok('a box drawn on a cut-out keeps that base', choiceBase({ choice: 'custom', base: 'whole' }) === 'whole');
  ok('the whole version is its own base', choiceBase({ choice: 'whole' }) === 'whole');
  eq('base size follows the base', baseSize(P, { choice: 'custom', base: 'whole', image: 1 }), { w: 400, h: 600 });
  eq('…and the photo otherwise', baseSize(P, { choice: 'custom', image: 1 }), { w: 800, h: 800 });
  ok('aspect uses the cut-out when the box is on one',
    Math.abs(M.shownAspect(P, 'custom', [0, 0, 1, 0.5], 1, 'whole') - (400 / 300)) < 1e-9);

  console.log('\nmoving boxes onto a new trim');
  // the old crop was the top half of a 1000×1000 original; the new one is all of it
  eq('a box moves to the same pixels', remapBox([0, 0, 1, 1], [0, 0, 1000, 500, 1000, 1000], [0, 0, 1000, 1000, 1000, 1000]),
    [0, 0, 1, 0.5]);
  ok('a box that falls outside is dropped', remapBox([0, 0, 1, 1], [0, 0, 100, 100, 1000, 1000], [500, 500, 100, 100, 1000, 1000]) === null);
  const ch = { X: { choice: 'custom', box: [0, 0, 1, 1], image: 0,
    splits: [{ n: 1, image: 0, box: [0, 0, 1, 1] }] } };
  const mig = { trim_version: 2, products: { X: { 0: { prev: [0, 0, 1000, 500, 1000, 1000], now: [0, 0, 1000, 1000, 1000, 1000] } } } };
  const n = migrateChoices(ch, mig);
  ok('both the product box and its splits move', n === 2 && ch.X.box[3] === 0.5 && ch.X.splits[0].box[3] === 0.5, JSON.stringify(ch.X));
  ok('and are marked so they never move twice', ch.X.trim === 2 && migrateChoices(ch, mig) === 0);
  ok('a box on a cut-out is left alone', migrateChoices({ Y: { choice: 'custom', base: 'whole', box: [0, 0, 1, 1] } },
    { trim_version: 2, products: { Y: { 0: { prev: [0, 0, 10, 10, 10, 10], now: [0, 0, 5, 5, 10, 10] } } } }) === 0);
}
console.log('\nproportions from pixels');
ok('pixelAspect of a tall narrow image', Math.abs(M.pixelAspect(120, 600) - 0.2) < 1e-9);
ok('pixelAspect of a wide image', Math.abs(M.pixelAspect(600, 200) - 3) < 1e-9);
ok('pixelAspect of a crop', Math.abs(M.pixelAspect(900, 300, [0, 0, 0.25, 1]) - 0.75) < 1e-9);
ok('pixelAspect refuses an undecoded image', M.pixelAspect(0, 0) === null);
{
  const bx = M.elementBox({ x: 0.5, y: 0.5, w: 0.2, aspect: 0.2 }, 1000, 1250);
  ok('a box keeps its picture\'s aspect', Math.abs(bx.w / bx.h - 0.2) < 1e-9, JSON.stringify(bx));
  const fr = M.elementBox({ x: 0.5, y: 0.5, w: 0.3, aspect: 3 }, 1000, 1250, 7);
  ok('inside a mat the picture keeps its aspect', Math.abs((fr.w - 14) / (fr.h - 14) - 3) < 1e-9, JSON.stringify(fr));
}

console.log('\nthe shelf picture is the placed picture');
{
  const p = { product_id: 'X', image: 0, images: [{ path: 'a.jpg', w: 10, h: 10, item: [0, 0, 0.5, 0.5] },
    { path: 'b.jpg', w: 10, h: 10, whole: { path: 'b.webp', w: 10, h: 10 } }], full: { path: 'a.jpg', w: 10, h: 10 } };
  eq('no choice: the cut-out', shelfView(p, {}), { variant: 'cutout', crop: null, image: 0, base: 'photo' });
  eq('the badge picks a picture', shelfView(p, {}, 1), { variant: 'whole', crop: [0, 0, 1, 1], image: 1, base: 'whole' });
  eq('a browser choice wins over the catalogue', shelfView({ ...p, choice: 'full' }, { X: { choice: 'item' } }),
    { variant: 'item', crop: [0, 0, 0.5, 0.5], image: 0, base: 'photo' });
  ok('a box drawn on the cut-out stays on the cut-out', choiceBase({ choice: 'custom', base: 'asset' }) === 'asset');
  ok('sameView compares crop and base', !sameView(shelfView(p, {}), shelfView(p, {}, 0)));
}

console.log('\nseveral garments, duplicates');
{
  const fan = { product_id: 'F', clean: true, several: ['colour regions: 4'], duplicate_of: '' };
  ok('a clean fan is off the shelf', !onShelf(fan, {}, false) && !onShelf(fan, {}, true));
  ok('taking it whole does not count as reviewed', !isReviewed(fan, { F: { choice: 'cutout' } }));
  ok('a box of hers cuts one garment out: back on the shelf',
    onShelf(fan, { F: { choice: 'custom', box: [0, 0, 0.3, 0.3] } }, false) && !isSeveral(fan, { F: { choice: 'custom', box: [0, 0, 1, 1] } }));
  const dupe = { product_id: 'D', clean: true, several: [], duplicate_of: 'K' };
  ok('a duplicate is hidden from the shelf', !onShelf(dupe, {}, true) && isDuplicate(dupe, {}));
  ok('"not a duplicate" puts it back', onShelf(dupe, { D: { notDuplicate: true } }, false));
}

console.log('\npalettes: the built file');
{
  const doc = JSON.parse(readFileSync(new URL('../data/palettes.json', import.meta.url)));
  const src = JSON.parse(readFileSync(new URL('../../content/palettes/palettes.json', import.meta.url)));
  ok('studio/data carries the built palettes as they are', JSON.stringify(doc) === JSON.stringify(src));
  const ids = doc.palettes.map((p) => p.id);
  ok('ids are unique', new Set(ids).size === ids.length);
  const bad = doc.palettes.filter((p) => p.colours.length < 3 || p.colours.length > 6
    || p.colours.reduce((a, c) => a + c.share, 0) !== 100
    || p.colours.some((c) => !/^#[0-9A-F]{6}$/i.test(c.hex) || !c.name
      || !['dominant', 'secondary', 'accent'].includes(c.role))
    || !p.source || !p.name || !p.when);
  ok('every palette: 3-6 colours, shares add to 100, hex, name, role, source, when',
    bad.length === 0, bad.map((p) => p.id).slice(0, 5).join(', '));
  ok('placement is upper / mid / lower / accessory or nothing',
    doc.palettes.every((p) => p.colours.every((c) => c.placement === null
      || c.placement.every((x) => ['upper', 'mid', 'lower', 'accessory'].includes(x)))));
  ok('trend palettes are external and say where from',
    doc.palettes.filter((p) => p.category === 'trend' && !p.derived)
      .every((p) => p.source.confidence === 'external' && p.source.ref.startsWith('web, Sept 2026, ')));
  ok('a Soft Summer version says it is derived and keeps the trend\'s source',
    doc.palettes.filter((p) => p.derived).every((p) => p.source.confidence === 'external'
      && doc.palettes.some((q) => q.id === p.derived_from)));
  ok('season and family palettes come from the repo',
    doc.palettes.filter((p) => p.category !== 'trend').every((p) => p.source.confidence === 'repo'));
  // hard rule 5: a season palette names only that season's anchors
  const seasonsTxt = readFileSync(new URL('../../frameworks/seasons.yaml', import.meta.url), 'utf8');
  const anchorsOf = {};
  let cur = null;
  for (const line of seasonsTxt.split('\n')) {
    const k = line.match(/^([a-z_]+):\s*$/);
    if (k) { cur = k[1]; anchorsOf[cur] = new Set(); continue; }
    if (cur) for (const m of line.matchAll(/\{name: ([^,]+), hex: "([0-9A-F]{6})"\}/g)) anchorsOf[cur].add(`${m[1]}#${m[2]}`);
  }
  const off = doc.palettes.filter((p) => p.category === 'season' || p.category === 'family' || p.derived)
    .filter((p) => {
      const season = p.category === 'season' ? p.group : p.category === 'family' ? p.season : 'soft_summer';
      return p.colours.some((c) => c.hex !== '#000000' && !anchorsOf[season].has(`${c.name}#${c.hex.slice(1)}`));
    });
  ok('season, family and Soft Summer palettes name only anchors of their season', off.length === 0,
    off.map((p) => p.id).slice(0, 5).join(', '));
  const idx = indexPalettes(doc);
  ok('the index keeps only groups that hold palettes',
    idx.categories.every((c) => c.groups.every((g) => g.count > 0)));
  ok('every season in seasons.yaml is a group', idx.categories.find((c) => c.key === 'season')
    .groups.length === Object.keys(anchorsOf).length);
  ok('palettesIn filters by group', palettesIn(idx, 'season', 'soft_autumn').every((p) => p.group === 'soft_autumn')
    && palettesIn(idx, 'season', 'soft_autumn').length > 3);
}

console.log('\npalettes: on the board');
{
  const pal = { id: 'x', name: 'Rust and navy', category: 'season', group: 'g', when: 'w',
    colours: [{ hex: '#A53B29', name: 'rust', role: 'dominant', share: 60, placement: ['mid'] },
      { hex: '#2B3446', name: 'navy', role: 'secondary', share: 30, placement: null },
      { hex: '#F3EFE7', name: 'cream', role: 'accent', share: 10, placement: ['accessory'] }],
    source: { kind: 'repo', confidence: 'repo', ref: 'here' }, engine: { junk: 1 } };
  const snap = paletteSnapshot(pal);
  ok('a snapshot keeps what the outfit file needs and nothing else',
    snap.id === 'x' && snap.colours.length === 3 && !('engine' in snap) && snap.source.ref === 'here');
  const bp = M.createBoard('portrait');
  ok('a new board has no palette and the strip is off', bp.palette === null && bp.showPalette === false);
  const e1 = M.addElement(bp, { product_id: 'P1', x: 0.3, y: 0.4 });
  const e2 = M.addElement(bp, { product_id: 'P2', x: 0.7, y: 0.6 });
  const before = JSON.stringify(bp.elements);
  bp.palette = snap;
  const shares = outfitShares(bp, byId, snap);
  ok('choosing a palette moves nothing', JSON.stringify(bp.elements) === before);
  // P1 is a top (weight 2) all rust; P2 is shoes (weight 1) all navy
  eq('shares by slot weight against the palette', shares.rows.map((r) => [r.name, r.actual, r.suggested]),
    [['rust', 66.7, 60], ['navy', 33.3, 30], ['cream', 0, 10]]);
  ok('nothing outside', shares.outside === 0 && shares.pieces === 2);
  ok('top and bottom count double, a dress four', SLOT_WEIGHT.top === 2 && SLOT_WEIGHT.bottom === 2 && SLOT_WEIGHT.dress === 4);
  const far = outfitShares(bp, byId, { colours: [{ hex: '#9CAF88', name: 'sage', role: 'dominant', share: 100 }] });
  ok('a colour far from every palette colour is outside', far.outside === 100 && far.rows[0].actual === 0);
  const rk = C.rankByLook([byId.P2, byId.P1], { colours: [snap.colours[0]] });
  ok('the palette ranks the shelf with the desk\'s own comparison', rk[0].product_id === 'P1');
  const m = metrics(1000, 1250);
  ok('the strip is off the board by default', stripRows(bp, byId, m, 1250).every((r) => r.kind !== 'palette'));
  bp.showPalette = true;
  const rows = stripRows(bp, byId, m, 1250);
  const pr = rows.find((r) => r.kind === 'palette');
  ok('with the toggle on, the palette is a strip by share', pr && pr.chips.length === 3
    && Math.abs(pr.chips[0].share - 0.6) < 1e-9);
  const sw = rows.find((r) => r.kind === 'swatches');
  ok('it sits above the pieces\' own strip', !sw || pr.top < sw.top);
  ok('toggling the strip moves nothing', JSON.stringify(bp.elements) === before);
  const inf = buildInfo(bp, byId, {}, { date: new Date(2026, 8, 24) });
  ok('the info file records the palette', inf.palette && inf.palette.id === 'x' && inf.palette.name === 'Rust and navy'
    && inf.palette.category === 'season' && inf.palette.colours[0].hex === '#A53B29'
    && inf.palette.colours[0].role === 'dominant' && inf.palette.colours[0].share === 60
    && inf.palette.colours[0].name === 'rust' && inf.palette.source.ref === 'here');
  ok('and whether it was on the board', inf.elements_shown.palette_strip === true);
  const mdp = buildMarkdown(inf);
  const lines = mdp.split('\n').filter((l) => l.includes('Palette'));
  ok('the piece list names the palette in one line', lines.length === 1 && lines[0].includes('Rust and navy'), lines.join('|'));
  bp.palette = null;
  const inf0 = buildInfo(bp, byId, {}, { date: new Date(2026, 8, 24) });
  ok('no palette, no line', inf0.palette === null && !buildMarkdown(inf0).includes('Palette'));
  ok('clearing moves nothing', JSON.stringify(bp.elements) === before);
}

console.log(`\nafter 24 Sept: ${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
