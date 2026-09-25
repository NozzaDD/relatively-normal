"""Tidy what the iPad's share sheet leaves in the repository, so nothing has to
be renamed or deleted by hand.

1. Every `content/catalogue/asset-choices*.json` is an export from the desk:
   `asset-choices.json` itself, and the `asset-choices-2.json`,
   `asset-choices 3.json` … the Files app makes when a name is taken. They
   are merged into `asset-choices.json`, keyed by product ID. Where two
   exports disagree about a product, the NEWEST export wins — judged by the
   `exported` time written inside the file, never by the file's name (the
   share sheet numbers copies in the order it found free names, not in the
   order they were made). A product only one export mentions keeps that
   export's decision. The extra copies are then deleted.
2. The share sheet's stubs — `text.txt`, `text-2.txt`, `text 3.txt` … — in
   `content/catalogue/` and `content/outfits/` are deleted.

If any export is unreadable (not JSON, not a desk export, a choice that is not
an object), nothing is written and nothing deleted: the error names the file
and the run stops.

    python3 content/tools/tidy_exports.py            # tidy
    python3 content/tools/tidy_exports.py --check    # say what it would do

build_products.py runs this first, and so does the Apply shelf choices workflow.
"""
import json, os, re, sys, glob, argparse
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
KIND = 'relatively-normal.asset-choices'
MAIN = 'asset-choices.json'
EXPORT = re.compile(r'^asset-choices.*\.json$')
STUB = re.compile(r'^text(?:[ _-]?\d+)?\.txt$')
STUB_DIRS = ('content/catalogue', 'content/outfits')


class BrokenExport(Exception):
    pass


def export_time(doc, name):
    """The export's own time. The desk writes a full ISO time since 24 Sept;
    older exports carry a date only, which reads as that day's midnight."""
    t = doc.get('exported')
    if not t:
        raise BrokenExport(f'{name}: no "exported" time inside it')
    try:
        d = datetime.fromisoformat(str(t).replace('Z', '+00:00'))
    except ValueError:
        raise BrokenExport(f'{name}: "exported" is not a time: {t!r}')
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d


def read_export(path):
    name = os.path.relpath(path, ROOT)
    try:
        with open(path, encoding='utf-8') as f:
            doc = json.load(f)
    except (OSError, UnicodeDecodeError) as e:
        raise BrokenExport(f'{name}: cannot be read ({e})')
    except json.JSONDecodeError as e:
        raise BrokenExport(f'{name}: not valid JSON ({e})')
    if not isinstance(doc, dict) or doc.get('kind') != KIND:
        raise BrokenExport(f'{name}: not a desk export (kind should be "{KIND}")')
    ch = doc.get('choices')
    if not isinstance(ch, dict):
        raise BrokenExport(f'{name}: "choices" is missing or not an object')
    bad = [pid for pid, c in ch.items() if not isinstance(c, dict)]
    if bad:
        raise BrokenExport(f'{name}: the choice for {bad[0]} is not an object')
    return doc, export_time(doc, name)


def exports(cat):
    return sorted(os.path.join(cat, f) for f in os.listdir(cat) if EXPORT.match(f))


def stubs(root):
    out = []
    for d in STUB_DIRS:
        full = os.path.join(root, d)
        if os.path.isdir(full):
            out += [os.path.join(full, f) for f in sorted(os.listdir(full)) if STUB.match(f)]
    return out


def plan(root=ROOT):
    """-> (merged document or None, export files to delete, stubs to delete).
    Raises BrokenExport before anything is touched."""
    cat = os.path.join(root, 'content/catalogue')
    files = exports(cat)
    read = [(p, *read_export(p)) for p in files]
    extra = [p for p in files if os.path.basename(p) != MAIN]
    if not extra:
        return None, [], stubs(root)
    # oldest first, so a newer export overwrites; at an equal time the file
    # already called asset-choices.json counts as the older one — a copy only
    # exists because a new export was saved beside it
    read.sort(key=lambda r: (r[2], os.path.basename(r[0]) != MAIN, r[0]))
    merged = {}
    for _p, doc, _t in read:
        merged.update(doc['choices'])
    newest = read[-1]
    out = {k: v for k, v in newest[1].items() if k != 'choices'}
    out.update(kind=KIND, version=newest[1].get('version', 1),
               exported=newest[1]["exported"], choices=merged)
    return out, extra, stubs(root)


def tidy(root=ROOT, check=False):
    doc, extra, junk = plan(root)
    for p in extra:
        print('merged into asset-choices.json:', os.path.relpath(p, root))
    for p in junk:
        print('share-sheet stub:', os.path.relpath(p, root))
    if check:
        return doc, extra, junk
    if doc is not None:
        with open(os.path.join(root, 'content/catalogue', MAIN), 'w', encoding='utf-8') as f:
            json.dump(doc, f, indent=1)          # as the desk writes it
    for p in extra + junk:
        os.remove(p)
    if doc is None and not junk:
        print('nothing to tidy')
    return doc, extra, junk


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    a = ap.parse_args()
    try:
        tidy(check=a.check)
    except BrokenExport as e:
        # the ::error:: line shows on the Actions run page
        print(f'::error::Export not applied, nothing changed — {e}')
        sys.exit(1)


if __name__ == '__main__':
    main()
