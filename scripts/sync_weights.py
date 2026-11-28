#!/usr/bin/env python3
"""Copy the site's item-type tables into index.html: the item-type / weight table (round 8, 30 Oct 2026) and the
subcategory table (28 Nov 2026).

usage: python3 scripts/sync_weights.py [repo dir]            rewrite the blocks in index.html
       python3 scripts/sync_weights.py [repo dir] --check    exit 1 when an index.html copy differs (nothing written)

functions/_lib/weights.js holds WT_DATA as plain JSON between /* WT-JSON-BEGIN */ and /* WT-JSON-END */; index.html carries
a compact copy between /*WT-DATA-BEGIN*/ and /*WT-DATA-END*/, read by the in-page product view's weight chip and by the
app's itemTypeOf(). functions/_lib/subcats.js holds SUB_DATA the same way (/* SUB-JSON-BEGIN */ ... /* SUB-JSON-END */);
its copy sits between /*SUB-DATA-BEGIN*/ and /*SUB-DATA-END*/ and draws the subcategory chips above All Finds.
Edit weights.js and subcats.js only.
"""
import json, os, re, sys

args = [a for a in sys.argv[1:] if not a.startswith("--")]
R = args[0] if args else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
check = "--check" in sys.argv

# (source file, its marker and const name, the marker in index.html, what the report calls it)
BLOCKS = [
    ("functions/_lib/weights.js", "WT-JSON", "WT_DATA", "WT-DATA", "weight table"),
    ("functions/_lib/subcats.js", "SUB-JSON", "SUB_DATA", "SUB-DATA", "subcategory table"),
]

f = os.path.join(R, "index.html")
s = open(f, encoding="utf-8").read()
bad = False
for src, mark, name, dst, label in BLOCKS:
    w = open(os.path.join(R, src), encoding="utf-8").read()
    m = re.search(r"/\* %s-BEGIN \*/\s*export const %s = (.*?);\s*/\* %s-END \*/" % (mark, name, mark), w, re.S)
    assert m, "no %s block in %s" % (mark, src)
    blob = json.dumps(json.loads(m.group(1)), ensure_ascii=False, separators=(",", ":"))
    pat = re.compile(r"/\*%s-BEGIN\*/.*?/\*%s-END\*/" % (dst, dst), re.S)
    assert len(pat.findall(s)) == 1, "index.html needs exactly one /*%s-BEGIN*/ ... /*%s-END*/ block" % (dst, dst)
    new = "/*%s-BEGIN*/" % dst + blob + "/*%s-END*/" % dst
    cur = pat.search(s).group(0)
    if check:
        print("index.html %s: %s" % (label, "in sync" if cur == new else "OUT OF SYNC, run scripts/sync_weights.py"))
        bad = bad or cur != new
    elif cur != new:
        s = pat.sub(lambda _: new, s, count=1)
        print("index.html %s updated" % label)
    else:
        print("index.html %s already in sync" % label)
if check:
    sys.exit(1 if bad else 0)
if s != open(f, encoding="utf-8").read():
    open(f, "w", encoding="utf-8").write(s)
