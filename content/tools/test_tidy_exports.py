"""Tests for tidy_exports.py. No images, no network: a throwaway repository
layout in a temporary folder.

    python3 content/tools/test_tidy_exports.py
"""
import json, os, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tidy_exports as T


def read(path):
    with open(path) as f:
        return f.read()


def load(path):
    return json.loads(read(path))


def export(exported, choices):
    return dict(kind=T.KIND, version=1, exported=exported, choices=choices)


class TidyExports(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        self.cat = os.path.join(self.root, 'content/catalogue')
        os.makedirs(self.cat)
        os.makedirs(os.path.join(self.root, 'content/outfits'))

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, rel, data):
        path = os.path.join(self.root, rel)
        with open(path, 'w') as f:
            f.write(data if isinstance(data, str) else json.dumps(data, indent=1))
        return path

    def listing(self, rel):
        return sorted(os.listdir(os.path.join(self.root, rel)))

    def test_conflicting_exports_newest_wins_and_stubs_go(self):
        # the NEWER export is saved under the "older-looking" name: the time
        # inside the file decides, not the -2 / -3 in the name
        self.write('content/catalogue/asset-choices.json', export('2026-09-24T09:00:00.000Z', {
            'B001-P001': {'hidden': True},
            'B001-P002': {'choice': 'item'},
            'B001-P003': {'slot': 'top'}}))
        self.write('content/catalogue/asset-choices-3.json', export('2026-09-24T10:00:00.000Z', {
            'B001-P001': {'choice': 'cutout'},          # she un-hid it at 10:00
            'B001-P004': {'hidden': True}}))
        self.write('content/catalogue/asset-choices-2.json', export('2026-09-24T18:30:00.000Z', {
            'B001-P001': {'review': 'sent back from the shelf'},   # newest of all
            'B001-P002': {'hidden': True}}))
        self.write('content/catalogue/text.txt', 'share sheet')
        self.write('content/catalogue/text-2.txt', 'share sheet')
        self.write('content/outfits/text.txt', 'share sheet')
        self.write('content/outfits/2026-09-24-untitled.md', '# a board')
        self.write('content/catalogue/products.csv', 'product_id\n')

        T.tidy(self.root)

        doc = load(os.path.join(self.cat, 'asset-choices.json'))
        ch = doc['choices']
        self.assertEqual(ch['B001-P001'], {'review': 'sent back from the shelf'})
        self.assertEqual(ch['B001-P002'], {'hidden': True})
        self.assertEqual(ch['B001-P003'], {'slot': 'top'})           # only the oldest had it
        self.assertEqual(ch['B001-P004'], {'hidden': True})
        self.assertEqual(doc['exported'], '2026-09-24T18:30:00.000Z')
        self.assertEqual(doc['kind'], T.KIND)
        self.assertEqual(self.listing('content/catalogue'), ['asset-choices.json', 'products.csv'])
        self.assertEqual(self.listing('content/outfits'), ['2026-09-24-untitled.md'])

    def test_date_only_tie_goes_to_the_copy(self):
        # exports made before full times were written: same day, so the copy
        # (saved beside an existing asset-choices.json) is the newer one
        self.write('content/catalogue/asset-choices.json', export('2026-09-23', {'A': {'hidden': True}}))
        self.write('content/catalogue/asset-choices 2.json', export('2026-09-23', {'A': {'choice': 'full'}}))
        T.tidy(self.root)
        ch = load(os.path.join(self.cat, 'asset-choices.json'))['choices']
        self.assertEqual(ch['A'], {'choice': 'full'})
        self.assertEqual(self.listing('content/catalogue'), ['asset-choices.json'])

    def test_broken_export_changes_nothing(self):
        good = self.write('content/catalogue/asset-choices.json',
                          export('2026-09-24T09:00:00Z', {'A': {'hidden': True}}))
        before = read(good)
        self.write('content/catalogue/asset-choices-2.json', '{"kind": "relatively-normal.asset-ch')
        self.write('content/catalogue/text.txt', 'share sheet')
        with self.assertRaises(T.BrokenExport) as e:
            T.tidy(self.root)
        self.assertIn('asset-choices-2.json', str(e.exception))
        self.assertEqual(read(good), before)
        self.assertEqual(self.listing('content/catalogue'),
                         ['asset-choices-2.json', 'asset-choices.json', 'text.txt'])

    def test_not_an_export_is_broken(self):
        self.write('content/catalogue/asset-choices.json', export('2026-09-24', {}))
        self.write('content/catalogue/asset-choices-2.json', json.dumps({'hello': 1}))
        with self.assertRaises(T.BrokenExport):
            T.tidy(self.root)

    def test_only_the_main_file_is_left_alone(self):
        path = self.write('content/catalogue/asset-choices.json', export('2026-09-24', {'A': {'hidden': True}}))
        before = read(path)
        T.tidy(self.root)
        self.assertEqual(read(path), before)


if __name__ == '__main__':
    unittest.main(verbosity=2)
