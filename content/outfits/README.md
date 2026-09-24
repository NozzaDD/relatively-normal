# content/outfits/

Boards made on the styling desk. Three files per board, all with the same
date-slug name:

```
2026-09-21-rust-twice.png    the image, 2160×2700 (or 2912×2184 landscape)
2026-09-21-rust-twice.jpg    the same board, for uploading
2026-09-21-rust-twice.json   what is on it — the source of truth
2026-09-21-rust-twice.md     the numbered piece list, ready to paste
```

Put the files here as they come off the iPad, then run:

```
python3 content/tools/collect_outfits.py          # fills used_in
python3 content/tools/collect_outfits.py --check  # says what it would change
```

That fills `used_in` in `content/catalogue/products.csv` and
`inspiration.csv` with the slugs of the boards each piece appears on. Filter on
it to see what a week's content actually used, check those rows first, and fill
in `validated`.

The `.json` is what reopens a board: **Open** on the desk reads it back and
refreshes every piece's brand, name, price and link from the catalogue as it is
now. Nothing in this folder is ever edited by a script.
