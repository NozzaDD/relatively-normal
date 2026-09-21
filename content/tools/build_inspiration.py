"""inspiration.csv — one row per inspiration image, clothes-only."""
import sys, os, json, csv
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, '/home/user/relatively-normal')

ROOT = '/home/user/relatively-normal'
CAT = ROOT + '/content/catalogue'
F = ['path', 'folder', 'house', 'house_confidence',
     'colour1_hex', 'colour1_name', 'colour1_family', 'colour1_share', 'colour1_role', 'colour1_sits',
     'colour2_hex', 'colour2_name', 'colour2_family', 'colour2_share', 'colour2_role', 'colour2_sits',
     'colour3_hex', 'colour3_name', 'colour3_family', 'colour3_share', 'colour3_role', 'colour3_sits',
     'colour4_hex', 'colour4_name', 'colour4_family', 'colour4_share', 'colour4_role', 'colour4_sits',
     'accent_sits', 'pattern', 'pattern_confidence', 'colour_story', 'colour_story_confidence',
     'non_clothing_dominant_hex', 'non_clothing_dominant_name', 'frame_edge_colours',
     'clothes_share', 'skin_share', 'background_share', 'colour_confidence', 'used_in']


def main():
    d = json.load(open(CAT + '/_inspiration.json'))
    rows = []
    for path, v in sorted(d.items()):
        if 'colours' not in v:
            continue
        cols = v['colours']
        acc = [c for c in cols if c['role'] == 'accent']
        # clothes_share is the honest confidence signal: a low one means the
        # centre band was mostly not the outfit
        cs = v['clothes_share']
        conf = 'high' if cs >= 0.6 else ('medium' if cs >= 0.35 else 'low')
        r = dict.fromkeys(F, '')
        r.update(path=path, folder=v.get('folder', ''),
                 house=v.get('brand_legible', '') or '',
                 house_confidence='given' if v.get('brand_legible') else 'input needed',
                 accent_sits='; '.join(f"{c['name']} {c['sits']}" for c in acc) or 'no accent',
                 pattern='', pattern_confidence='input needed',
                 colour_story=v.get('colour_words', ''),
                 colour_story_confidence='given' if v.get('colour_words') else 'input needed',
                 non_clothing_dominant_hex=v['background_hex'],
                 non_clothing_dominant_name=v['background_name'],
                 frame_edge_colours=';'.join(v.get('ring_hexes', [])),
                 clothes_share=cs, skin_share=v['skin_share'],
                 background_share=v['background_share'], colour_confidence=conf, used_in='')
        for i, c in enumerate(cols[:4], 1):
            r[f'colour{i}_hex'] = c['hex']; r[f'colour{i}_name'] = c['name']
            r[f'colour{i}_family'] = c['family']; r[f'colour{i}_share'] = c['share']
            r[f'colour{i}_role'] = c['role']; r[f'colour{i}_sits'] = c['sits']
        rows.append(r)
    with open(CAT + '/inspiration.csv', 'w', newline='') as f:
        w = csv.DictWriter(f, F); w.writeheader(); w.writerows(rows)
    import collections
    print(len(rows), 'inspiration rows')
    print('colour_confidence', collections.Counter(r['colour_confidence'] for r in rows))


if __name__ == '__main__':
    main()
