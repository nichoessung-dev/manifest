# -*- coding: utf-8 -*-
"""Tests for the Archive import: python scripts/test_import_archive.py

  - scripts/import_archive.py: original links, row checks, the stage on a small made-up sheet (confirmed originals only,
    the reseller's ids never in the staging file, the private map outside the repository, a run again adds nothing)
  - index.html: swapFirst() puts partner finds first and Archive finds ("ar") right after them; a price sort and a text
    search keep their own order; pcStyleMatch() counts an Archive find as the Archive style (run in node)
"""
import csv, json, os, re, shutil, subprocess, sys, tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import import_archive as IA  # noqa: E402
from catalog_common import ROOT  # noqa: E402

fails = []


def ok(c, m):
    if not c: fails.append(m); print("FAIL", m)


def test_links_and_rows():
    ok(IA.original("https://detail.1688.com/offer/897026768889.html") == ("1688", "897026768889"), "1688 link")
    ok(IA.original("https://item.taobao.com/item.htm?id=760438413422") == ("taobao", "760438413422"), "taobao link")
    ok(IA.original("https://weidian.com/item.html?itemID=7999000009") == (None, None), "a weidian link is no original")
    row = {"id": "897026768889", "platform": "1688", "cat": "Accessories", "brand": "Dior", "title": "Dior Comb", "price": 120}
    ok(IA.row_problems(row) == [], "a good row")
    ok(IA.row_problems(dict(row, title="Dior Comb 1:1")), "1:1 in a title")
    ok(IA.row_problems(dict(row, title="Dior Replica Comb")), "replica in a title")
    ok(IA.row_problems(dict(row, title="Dior \u2014 Comb")), "a dash in a title")
    ok(IA.row_problems(dict(row, platform="weidian")), "weidian platform")
    ok(IA.row_problems(dict(row, price=2)), "a placeholder price")
    ok(IA.price_of(120.4) == 120 and IA.price_of(6.55) == 6.5 or IA.price_of(6.55) == 6.6, "price rounding")


def test_stage():
    tmp = tempfile.mkdtemp()
    try:
        rid = ["7999000001", "7999000002", "7999000003", "7999000004", "7999000005"]
        names = {rid[0]: {"name": "Dior comb", "cat": "Accessories", "g": "m"},
                 rid[1]: {"name": "E.R.D T-SHIRT", "cat": "Tops", "g": "w"},
                 rid[2]: {"name": "Takashi Murakami Sunflower 3D Carpet", "cat": "Accessories", "g": "m"},
                 rid[3]: {"name": "Amiri jeans", "cat": "Pants", "g": "w"},
                 rid[4]: {"name": "Amiri jeans", "cat": "Pants", "g": "m"}}
        json.dump(names, open(os.path.join(tmp, "names.json"), "w"))
        cols = ["id", "name", "reseller_link", "reseller_cny", "original_link", "original_cny", "match", "similarity",
                "best_guess_link", "best_guess_cny"]
        rows = [
            [rid[0], "Dior comb", "https://weidian.com/item.html?itemID=" + rid[0], 250, "https://detail.1688.com/offer/111111111111.html", 120, "same photo", 0.99, "", ""],
            [rid[1], "E.R.D T-SHIRT", "https://weidian.com/item.html?itemID=" + rid[1], 109, "https://item.taobao.com/item.htm?id=222222222222", 75, "likely", 0.85, "", ""],
            [rid[2], "Carpet", "https://weidian.com/item.html?itemID=" + rid[2], 577, "", "", "no match", 0.53, "https://detail.1688.com/offer/333333333333.html", 5.3],
            [rid[3], "Amiri jeans", "https://weidian.com/item.html?itemID=" + rid[3], 135, "https://detail.1688.com/offer/444444444444.html", 129, "same photo", 0.99, "", ""],
            [rid[4], "Amiri jeans", "https://weidian.com/item.html?itemID=" + rid[4], 135, "https://detail.1688.com/offer/444444444444.html", 129, "same photo", 0.97, "", ""],
        ]
        with open(os.path.join(tmp, "scored.csv"), "w", newline="") as f:
            w = csv.writer(f); w.writerow(cols); w.writerows(rows)
        ans = [{"id": rid[0], "c1688": [{"spu": "111111111111", "t": "air cushion comb", "cny": 120, "img": "https://cbu01.alicdn.com/img/ibank/a.jpg"}]},
               {"id": rid[1] + "#c", "taobao": [{"spu": "222222222222", "t": "tee", "cny": 75, "img": "//img.alicdn.com/b.jpg"}]},
               {"id": rid[3], "c1688": [{"spu": "444444444444", "t": "jeans", "cny": 129, "img": "https://cbu01.alicdn.com/img/ibank/c.jpg"}]}]
        with open(os.path.join(tmp, "answers.jsonl"), "w") as f:
            f.write("\n".join(json.dumps(x) for x in ans) + "\n")
        old = IA.STAGE
        IA.STAGE = os.path.join(tmp, "stage.json")
        try:
            IA.main(["stage", os.path.join(tmp, "scored.csv")])
            st = json.load(open(IA.STAGE))["items"]
            ok(sorted(st) == ["111111111111", "222222222222", "444444444444"], "staged the confirmed originals: %s" % sorted(st))
            ok(st["111111111111"]["row"]["platform"] == "1688" and st["222222222222"]["row"]["platform"] == "taobao", "platforms")
            ok(st["222222222222"]["src"] == "https://img.alicdn.com/b.jpg", "a second pass answer gives the photo, https")
            ok(st["222222222222"]["row"]["g"] == "w", "women's tab")
            ok(st["444444444444"]["row"]["g"] == "m", "two sheet items, one original: men's when one of them is")
            ok(st["111111111111"]["row"]["title"] == "Dior Comb" and st["111111111111"]["row"]["brand"] == "Dior", "title and brand")
            text = open(IA.STAGE).read()
            ok(not any(r in text for r in rid) and "weidian" not in text.lower(), "no reseller id or link in the staging file")
            pm = json.load(open(os.path.join(tmp, "archive_map.json")))
            ok(pm[rid[0]]["id"] == "111111111111", "the private map")
            n = len(st)
            IA.main(["stage", os.path.join(tmp, "scored.csv")])
            ok(len(json.load(open(IA.STAGE))["items"]) == n, "a run again adds nothing")
            try:
                IA.main(["stage", os.path.join(tmp, "scored.csv"), "--map", os.path.join(ROOT, "data", "x.json")])
                ok(False, "a map inside the repository is refused")
            except SystemExit:
                pass
        finally:
            IA.STAGE = old
    finally:
        shutil.rmtree(tmp)


JS = r"""
const src = require('fs').readFileSync(process.argv[1], 'utf8');
const grab = name => { const i = src.indexOf('function ' + name + '('); let d = 0, j = src.indexOf('{', i);
  for (let k = j; k < src.length; k++) { if (src[k] === '{') d++; else if (src[k] === '}') { d--; if (!d) return src.slice(i, k + 1); } } };
const SW_MIX = 33; let SWAPPED = new Set(), state = { q: '', sort: 'pop', saved: false, brand: 'all', cats: [] };
eval(grab('arFirst') + ';' + grab('swapFirst'));
const fails = []; const ok = (c, m) => { if (!c) fails.push(m); };
const mk = (n, f) => Array.from({ length: n }, (_, i) => f(i));
const kinds = l => l.map(p => SWAPPED.has(p.id) ? 'P' : p.ar ? 'A' : 'o').join('');
// 100 partner, 20 Archive, 300 others, mixed up
let L = mk(420, i => ({ id: 'x' + i, ar: i % 21 === 5 ? 1 : 0 }));
mk(420, i => i).filter(i => i % 4 === 0 && !L[i].ar).slice(0, 100).forEach(i => SWAPPED.add('x' + i));
const nA = L.filter(p => p.ar).length, nP = SWAPPED.size;
let k = kinds(swapFirst(L));
ok(k.length === L.length, 'browse keeps every find');
ok(k.lastIndexOf('P') < k.indexOf('A'), 'browse: Archive after every partner find');
ok(k.indexOf('A') + nA - 1 === k.lastIndexOf('A'), 'browse: Archive finds together');
ok((k.slice(0, k.indexOf('A')).match(/o/g) || []).length === Math.ceil(nP * 0.03), 'browse: the 3% mix stays other finds');
state.cats = ['Tops']; k = kinds(swapFirst(L));
ok(/^P+A+o+$/.test(k), 'category: partner, Archive, the rest: ' + k.slice(0, 20));
state.cats = []; state.brand = ['X']; k = kinds(swapFirst(L)); ok(/^P+A+o+$/.test(k), 'brand: partner, Archive, the rest');
state.brand = 'all'; state.q = 'hoodie'; k = kinds(swapFirst(L)); ok(/^P+[Ao]+$/.test(k) && !/^P+A+o+$/.test(k), 'text search: Archive not lifted');
state.q = ''; state.sort = 'low'; ok(swapFirst(L) === L, 'price sort: own order');
state.sort = 'pop'; SWAPPED = new Set(); k = kinds(swapFirst(L)); ok(/^A+o+$/.test(k), 'no partner swaps yet: Archive first');
// the Archive style
eval(grab('pcStyleMatch').replace(/^function pcStyleMatch/, 'function _m'));
ok(/if\(k==="archive"&&p\.ar\) return 2;/.test(grab('pcStyleMatch')), 'pcStyleMatch honours ar');
console.log(fails.length ? 'FAIL ' + fails.join('; ') : 'ok');
"""


def test_js():
    r = subprocess.run(["node", "-e", JS, os.path.join(ROOT, "index.html")], capture_output=True, text=True, timeout=120)
    out = (r.stdout + r.stderr).strip()
    ok(r.returncode == 0 and out.endswith("ok"), "index.html ordering: " + out[-400:])


if __name__ == "__main__":
    test_links_and_rows()
    test_stage()
    test_js()
    print("FAILED %d" % len(fails) if fails else "all passed")
    sys.exit(1 if fails else 0)
