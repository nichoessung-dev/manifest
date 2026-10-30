#!/usr/bin/env python3
"""Copy the site's one item-type / weight table (functions/_lib/weights.js WT_DATA) into index.html (round 8, 30 Oct 2026).

usage: python3 scripts/sync_weights.py [repo dir]            rewrite the block in index.html
       python3 scripts/sync_weights.py [repo dir] --check    exit 1 when index.html's copy differs (nothing written)

weights.js holds WT_DATA as plain JSON between /* WT-JSON-BEGIN */ and /* WT-JSON-END */. index.html carries a compact
copy between /*WT-DATA-BEGIN*/ and /*WT-DATA-END*/, read by the in-page product view's weight chip. Edit weights.js only.
"""
import json, os, re, sys

args = [a for a in sys.argv[1:] if not a.startswith("--")]
R = args[0] if args else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
check = "--check" in sys.argv

w = open(os.path.join(R, "functions/_lib/weights.js"), encoding="utf-8").read()
m = re.search(r"/\* WT-JSON-BEGIN \*/\s*export const WT_DATA = (.*?);\s*/\* WT-JSON-END \*/", w, re.S)
assert m, "no WT-JSON block in weights.js"
data = json.loads(m.group(1))
blob = json.dumps(data, ensure_ascii=False, separators=(",", ":"))

f = os.path.join(R, "index.html")
s = open(f, encoding="utf-8").read()
pat = re.compile(r"/\*WT-DATA-BEGIN\*/.*?/\*WT-DATA-END\*/", re.S)
assert len(pat.findall(s)) == 1, "index.html needs exactly one /*WT-DATA-BEGIN*/ ... /*WT-DATA-END*/ block"
new = "/*WT-DATA-BEGIN*/" + blob + "/*WT-DATA-END*/"
cur = pat.search(s).group(0)
if check:
    print("index.html weight table: " + ("in sync" if cur == new else "OUT OF SYNC, run scripts/sync_weights.py"))
    sys.exit(0 if cur == new else 1)
if cur != new:
    open(f, "w", encoding="utf-8").write(pat.sub(lambda _: new, s, count=1))
    print("index.html weight table updated")
else:
    print("index.html weight table already in sync")
