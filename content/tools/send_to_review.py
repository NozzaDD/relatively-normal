"""Send products back to Review from a build: page text found in the picture,
a re-cut to look at again. Nothing is deleted and nothing goes to the shelf.

Two files are written, as the desk's own "Back to Review" would write them:

  content/catalogue/asset-choices.json   the product's entry becomes
      {review: reason}, keeping its slot, the boxes cut out of it and
      "not a duplicate"; the picture choice or the hide it had goes
  content/catalogue/review-sends.json    one version per send, {pid: reason}.
      build_studio.py copies it to studio/data/, and the desk applies each
      version ONCE over a decision kept in an iPad's own storage, which would
      otherwise go on hiding or showing the product as before.

    from send_to_review import send
    send('2026-09-24-pagetext', {'B018-P001': 'page text in the picture: …'})
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
CAT = os.path.abspath(os.path.join(HERE, '..', 'catalogue'))
CHOICES = CAT + '/asset-choices.json'
SENDS = CAT + '/review-sends.json'
PICTURE = ('hidden', 'choice', 'box', 'base', 'image', 'later', 'restored')


def send(version, products, only_if=None):
    """products: {pid: reason}. `only_if(entry)` limits which existing entries
    may be replaced (recut_hidden.py sends only what she hid). Returns the
    products actually sent."""
    doc = json.load(open(CHOICES))
    sent = {}
    for pid, reason in products.items():
        c = doc['choices'].get(pid) or {}
        if only_if is not None and not only_if(c):
            continue
        keep = {k: v for k, v in c.items() if k not in PICTURE and k != 'review'}
        doc['choices'][pid] = {**keep, 'review': reason}
        sent[pid] = reason
    json.dump(doc, open(CHOICES, 'w'), indent=1)
    try:
        sends = json.load(open(SENDS))
    except (FileNotFoundError, json.JSONDecodeError):
        sends = {'versions': []}
    sends['versions'] = [v for v in sends['versions'] if v.get('version') != version]
    sends['versions'].append(dict(version=version, products=sent))
    sends['versions'].sort(key=lambda v: v['version'])
    json.dump(sends, open(SENDS, 'w'), indent=1)
    return sent
