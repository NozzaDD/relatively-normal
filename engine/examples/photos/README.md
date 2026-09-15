# Photos in, items out

Put one photo per piece in a folder and run

```sh
python -m engine.run --season soft_autumn --direction teal_ochre --photos path/to/folder --out result.html
```

Intake (`engine/intake.py`) writes `items.csv` and `contact-sheet.html` into the
folder, then the run continues from that CSV. Open the contact sheet first and
check every swatch against its photo — the engine is only as honest as the hex.
Then fill in `dressiness`, `weight` and `near_face` in the CSV; intake leaves
them blank on purpose.

## Naming

`slot_item-name.jpg` — the slot, an underscore, then the name with hyphens for
spaces.

| Filename | Slot | Name |
|---|---|---|
| `top_deep-teal-knit.jpg` | top | deep teal knit |
| `bottom_black-trousers.png` | bottom | black trousers |
| `layer_camel-coat.jpg` | layer | camel coat |
| `accessory_rust-scarf.png` | accessory | rust scarf |

Slots are `top`, `bottom`, `layer`, `shoes`, `bag`, `accessory`. A file whose
prefix is not one of those still gets its colour extracted, but its slot is
left blank in the CSV and it is listed in the warnings — nothing is guessed.

## Photographing

Either of these works; the second is better.

**A flat photo.** Each piece laid flat, in indirect daylight (near a window, no
direct sun, no lamps), on a plain background that is not the colour of the
garment — a white wall or a sheet — and cropped so the garment fills most of
the frame. Intake estimates the background from the four corners and removes
it, so keep the corners clear of the garment and of anything else.

**A transparent cutout.** On the iPad, touch and hold the garment in Photos,
choose *Copy* or *Share* on the lifted subject, and save it as a PNG. The
background is already gone, so intake uses the cutout's own edge instead of
guessing. This is more accurate, and it is what the canvas will do later.

Whichever you use: no filters, no beauty mode, and the same light for every
piece, so the hexes are comparable with each other.
