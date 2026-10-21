# -*- coding: utf-8 -*-
"""Eligible finds for factory scripts: in products.json, qc >= 1 in functions/_lib/catalog.js, not DEAD or SOLD_OUT in
functions/_lib/signals.js. Price is CNY; USD = round(cny * 0.14).

  python factory/finds.py search cable knit            # best matches (most QC photos, most views first)
  python factory/finds.py id 891428294916               # one find
  python factory/finds.py dump > /tmp/finds.json        # every eligible find
"""
import json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def usd(cny): return int(round(float(cny) * 0.14))


def _js_list(src, name):
    m = re.search(r"export const %s = (\[.*?\]);" % name, src, re.S)
    return json.loads(m.group(1)) if m else []


def load():
    products = json.load(open(os.path.join(ROOT, "products.json"), encoding="utf-8"))
    sig = open(os.path.join(ROOT, "functions", "_lib", "signals.js"), encoding="utf-8").read()
    dead = set(map(str, _js_list(sig, "DEAD"))); sold = set(map(str, _js_list(sig, "SOLD_OUT")))
    cat = open(os.path.join(ROOT, "functions", "_lib", "catalog.js"), encoding="utf-8").read()
    rows = json.loads(re.search(r"export const ROWS = (\[.*\]);", cat, re.S).group(1))
    # row: [id, title, brand, cat, platform, seller, usd, cny, qc, best, views, img, g, itemId, variants]
    meta = {str(r[0]): {"qc": int(r[8] or 0), "views": int(r[10] or 0), "best": int(r[9] or 0)} for r in rows}
    out = {}
    for pid, p in products.items():
        m = meta.get(pid)
        if not m or m["qc"] < 1 or pid in dead or pid in sold or not p.get("price"): continue
        out[pid] = {"id": pid, "title": p.get("title", ""), "brand": p.get("brand", ""), "cat": p.get("cat", ""), "cny": p["price"],
                    "usd": usd(p["price"]), "qc": m["qc"], "views": m["views"], "g": p.get("g", ""), "img": p.get("img", "")}
    return out, dead, sold, products


def search(words, finds, n=25):
    ws = [w.lower() for w in words]
    hits = [f for f in finds.values() if all(w in (f["title"] + " " + f["cat"]).lower() for w in ws)]
    return sorted(hits, key=lambda f: (-min(f["qc"], 6), -f["views"]))[:n]


if __name__ == "__main__":
    finds, dead, sold, products = load()
    cmd = sys.argv[1] if len(sys.argv) > 1 else "stats"
    if cmd == "search":
        for f in search(sys.argv[2:], finds): print("%-14s $%-4d (%4s CNY) qc=%-2d views=%-5d %s | %s | %s" % (f["id"], f["usd"], f["cny"], f["qc"], f["views"], f["g"], f["cat"], f["title"]))
    elif cmd == "id":
        pid = sys.argv[2]; print(json.dumps(finds.get(pid) or {"eligible": False, "in_products": pid in products, "dead": pid in dead, "sold_out": pid in sold}, ensure_ascii=False))
    elif cmd == "dump": print(json.dumps(finds, ensure_ascii=False))
    else: print("eligible finds:", len(finds), "of", len(products), "| dead:", len(dead), "sold out:", len(sold))
