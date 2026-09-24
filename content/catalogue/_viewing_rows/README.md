# _viewing_rows/

Raw output of the per-product viewing pass, one file per batch of 29 products,
in the order the subagents returned them. Kept so the pass never has to be
re-run: `products.csv` is built from these.

Columns, pipe-delimited:

`product_id | slot | garment_type | material_visible | pattern | weight |
formality | shot_type | complete_in_frame | shop_text | brand_text |
product_name_text | colour_name_text | composition_text | price_text | notes`

Every `*_text` column is **literal transcription only** — `NONE` wherever the
text was not readable on the page. Nothing in these files is inferred.
`_prompt.txt` is the exact instruction the pass ran under.
