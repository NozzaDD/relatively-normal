"""Which products a tool still has to look at: new or changed ones only.

panels.py, flat_lays.py, asset_quality.py and crop_figures.py re-cut, re-rate
and re-measure.
Run over everything, they rewrite cut-outs and verdicts the owner has already
reviewed on the desk. So by default each of them only touches a product it has
never processed, or one whose screenshots have changed since it did; `--all`
on the command line is the only way to reprocess everything.

What "processed" means is kept in content/catalogue/_processed.json:

    {"panels": {"B068-P045": "<fingerprint>", ...}, "flat_lays": {...}, ...}

A product's fingerprint is its list of screenshots in batches.json with each
file's size — a merge that adds a screenshot to a row, or a screenshot replaced
under the same name, changes it. A row with no batch entry (a variant, a split,
a cell) is fingerprinted by its asset file instead. Sizes, not hashes: reading
two gigabytes of screenshots to decide there is nothing to do is the thing this
file exists to avoid, and a replacement with the identical byte count is not a
case worth the cost.
"""
import os, sys, json, hashlib

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CAT = ROOT + '/content/catalogue'
STAMP = CAT + '/_processed.json'
FORCE_FLAGS = ('--all', '--redo')


def forced(argv=None):
    """True when the command line asks for a full run."""
    return any(a in (argv if argv is not None else sys.argv) for a in FORCE_FLAGS)


def _size(rel):
    p = ROOT + '/' + rel
    return os.path.getsize(p) if os.path.exists(p) else -1


def fingerprints(pids=None):
    """pid -> fingerprint, for every product in batches.json and every asset
    in _assets.json that has no batch entry."""
    batches = json.load(open(CAT + '/batches.json'))
    try:
        assets = json.load(open(CAT + '/_assets.json'))
    except (FileNotFoundError, json.JSONDecodeError):
        assets = {}
    out = {}
    for b in batches:
        pid = b['product_id']
        if pids is not None and pid not in pids:
            continue
        out[pid] = ';'.join(f'{p}:{_size(p)}' for p in b['images'])
    for pid, a in assets.items():
        if pid in out or (pids is not None and pid not in pids) or not a.get('asset_path'):
            continue
        out[pid] = 'asset ' + a['asset_path'] + ':' + str(_size(a['asset_path']))
    return {k: hashlib.sha1(v.encode()).hexdigest()[:16] for k, v in out.items()}


def load():
    try:
        return json.load(open(STAMP))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def select(tool, candidates, force=None):
    """The candidates this tool should process now, and the fingerprints to
    stamp once it has. `force` defaults to the command line's --all."""
    force = forced() if force is None else force
    fp = fingerprints(set(candidates))
    done = load().get(tool, {})
    todo = [pid for pid in candidates if force or done.get(pid) != fp.get(pid)]
    return todo, fp


def mark(tool, pids, fp):
    """Record that `tool` has processed these products in their current state."""
    st = load()
    t = st.setdefault(tool, {})
    for pid in pids:
        if pid in fp:
            t[pid] = fp[pid]
    st[tool] = dict(sorted(t.items()))
    json.dump(st, open(STAMP, 'w'), indent=1)


def report(tool, todo, candidates, force=None):
    force = forced() if force is None else force
    how = 'full run (--all)' if force else 'new or changed only; --all for a full run'
    print(f'{tool}: {len(todo)} of {len(candidates)} products to process — {how}', flush=True)


if __name__ == '__main__':
    # `python3 content/tools/incremental.py --stamp-all` records every current
    # product as processed by all four tools: the baseline taken on
    # 23 September 2026 so the committed, reviewed catalogue is never re-run.
    if '--stamp-all' in sys.argv:
        fp = fingerprints()
        for tool in ('panels', 'flat_lays', 'asset_quality', 'crop_figures'):
            mark(tool, list(fp), fp)
        print('stamped', len(fp), 'products for panels, flat_lays, asset_quality, crop_figures')
    else:
        st = load()
        fp = fingerprints()
        for tool, done in sorted(st.items()):
            stale = sum(1 for p, f in fp.items() if done.get(p) != f)
            print(f'{tool}: {len(done)} processed, {stale} new or changed')
