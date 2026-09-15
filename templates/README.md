# Input templates

Two spreadsheets. Fill them in Numbers or Google Sheets, export as CSV, commit.
They are the same data the canvas will write later; nothing gets retyped.

## items.csv — one row per piece

| column | values | meaning |
|---|---|---|
| name | text | how you'd refer to it |
| slot | top · bottom · dress · layer · shoes · bag · accessory | dress = one piece that fills top and bottom; layer = coat, jacket, cardigan, anything over the top |
| hex | six characters, no # | sampled from the garment in flat daylight |
| dressiness | 1–4 | 1 casual → 4 dressy. Where it sits left-to-right on the worksheet grid |
| weight | 1–4 | 1 light → 4 heavy. How much warmth it gives, not colour temperature |
| near_face | true / false / blank | accessories only: scarves and hats true, belts and jewellery false (blank is read as false) |
| notes | text | fibre, fit, anything |

## outfits.csv — one row per outfit you'd actually wear

| column | values | meaning |
|---|---|---|
| outfit | text | a name |
| occasion | text | from the worksheet cards, or your own |
| dress_code | 1–5 | the dot rating on the occasion card |
| weather | clear · rain | rain changes more than people admit |
| formality | corporate · casual | corporate means every face-visible item must come from the season's corporate list; blank means casual |
| setting | office · home | at home only top, layer and accessory are face-visible (the camera); in the office every slot is; blank means office |
| top … accessory | item names from items.csv, or blank | one per slot, dress included; blank means empty. A dress completes top and bottom; a dress with a top or bottom is warned as *dress plus separates* |

Each file holds its header row and one example row to show the format; replace the example. The filled-in test case lives in `engine/examples/nora-items.csv` and `nora-outfits.csv`, and

```sh
python -m engine.run --season soft_autumn --direction teal_ochre --items engine/examples/nora-items.csv --outfits engine/examples/nora-outfits.csv --out result.html
```

turns the two spreadsheets into the result screen.
