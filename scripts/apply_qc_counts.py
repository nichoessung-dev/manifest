# -*- coding: utf-8 -*-
"""Catalogue QC counts from the QC photo bank (19 Nov 2026, bulk QC banking). The app only looks for QC photos on finds
whose catalogue row has "qc" above 0, and those counts are old. For every find the bank looked up (data/qc_bank.json,
scripts/qc_bank.py) with stored photos, the row's "qc" becomes the bank's count when that is higher.
Surgical string edits inside the pc-catalog block of index.html (only the "qc" number of the rows that change), like
apply_catalog_ai.py; run gen_catalog.py and sync_catalog.py after it.

  python scripts/apply_qc_counts.py [--dry]
"""
import json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from catalog_common import ROOT, load_catalog  # noqa: E402


def main():
    bank = json.load(open(os.path.join(ROOT, "data", "qc_bank.json"), encoding="utf-8")).get("items") or {}
    html, items, s, e = load_catalog()
    block = html[s:e]
    changed = 0
    for p in items:
        sid = str(p.get("itemId") or p.get("id")).lstrip("0")
        b = bank.get("%s/%s" % (p.get("platform"), sid))
        if not b or not b[1]: continue
        n = max(int(b[0] or 0), int(b[1]))
        if n <= int(p.get("qc") or 0): continue
        head = '{"id":%s' % json.dumps(str(p["id"]))
        i = block.find(head)
        if i < 0: continue
        j = block.find('{"id":', i + len(head)); j = len(block) if j < 0 else j
        row = block[i:j]
        new, k = re.subn(r'"qc":\d+', '"qc":%d' % n, row, count=1)
        if not k: continue
        block = block[:i] + new + block[j:]; changed += 1
    print("catalogue QC counts raised from the bank:", changed)
    if changed and "--dry" not in sys.argv:
        json.loads(block)                                   # still valid JSON
        open(os.path.join(ROOT, "index.html"), "w", encoding="utf-8").write(html[:s] + block + html[e:])


if __name__ == "__main__":
    main()
