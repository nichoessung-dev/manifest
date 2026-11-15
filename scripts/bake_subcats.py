# -*- coding: utf-8 -*-
"""Subcategories for the category pages (owner, 15 Nov 2026: "what product category they are in", "view more ... a page
where you only see tops").

No new AI run: the vision pass (scripts/catalog_ai.py) already named every find's item type in data/catalog_ai.json
("items": id -> {"cat", "item"}). This folds those ~120 raw types into a short list of subcategories per category and
writes data/subcats.json, which the page loads to draw the chip row (T-shirts, Hoodies, Sweaters ...) above the grid.

  {"v": 1, "subs": {"Tops": ["T-shirts", "Hoodies", ...]}, "m": {"<id>": "T-shirts", ...}}

A subcategory needs at least MIN finds to get a chip; smaller ones fall into "Other" (no chip). The category in the
live catalogue (index.html pc-catalog) wins over the AI's: a find whose AI cat differs keeps no subcategory.

  python scripts/bake_subcats.py [--check]
"""
import json, re, sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MIN = 12

# raw item type -> subcategory, per category. Types not listed map to themselves (pluralised) when big enough.
MAP = {
    "Tops": {"T-Shirt": "T-shirts", "Hoodie": "Hoodies", "Zip Hoodie": "Zip hoodies", "Sweatshirt": "Sweatshirts",
             "Sweater": "Knitwear", "Cardigan": "Knitwear", "Tracksuit": "Tracksuits", "Set": "Tracksuits",
             "Polo": "Polos", "Long Sleeve": "Long sleeves", "Jersey": "Jerseys", "Shirt": "Shirts",
             "Tank Top": "Tank tops", "Quarter Zip": "Knitwear", "Fleece": "Sweatshirts"},
    "Outerwear": {"Puffer Jacket": "Puffers", "Down Jacket": "Puffers", "Vest": "Vests", "Jacket": "Jackets",
                  "Windbreaker": "Windbreakers", "Track Jacket": "Windbreakers", "Varsity Jacket": "Varsity & bombers",
                  "Bomber Jacket": "Varsity & bombers", "Denim Jacket": "Denim jackets", "Fleece": "Fleece",
                  "Coat": "Coats", "Blazer": "Coats", "Overshirt": "Overshirts", "Zip Hoodie": "Fleece"},
    "Shoes": {"Sneakers": "Sneakers", "Boots": "Boots", "Slides": "Slides & sandals", "Sandals": "Slides & sandals",
              "Slippers": "Slides & sandals", "Clogs": "Slides & sandals", "Clog": "Slides & sandals",
              "Loafers": "Loafers & dress shoes", "Shoes": "Loafers & dress shoes", "Pumps": "Heels & pumps",
              "Heels": "Heels & pumps", "Mules": "Heels & pumps"},
    "Pants": {"Jeans": "Jeans", "Sweatpants": "Sweatpants", "Joggers": "Sweatpants", "Track Pants": "Track pants",
              "Cargo Pants": "Cargos", "Pants": "Trousers", "Trousers": "Trousers"},
    "Shorts": {"Shorts": "Shorts", "Swim Shorts": "Swim shorts"},
    "Bags": {"Backpack": "Backpacks", "Crossbody Bag": "Crossbody", "Messenger Bag": "Crossbody",
             "Belt Bag": "Crossbody", "Shoulder Bag": "Shoulder bags", "Handbag": "Shoulder bags",
             "Bag": "Shoulder bags", "Tote Bag": "Totes", "Duffle Bag": "Travel", "Luggage": "Travel",
             "Pouch": "Pouches & wallets", "Wallet": "Pouches & wallets", "Clutch": "Pouches & wallets",
             "Clutch Bag": "Pouches & wallets"},
    "Headwear": {"Cap": "Caps", "Trucker Cap": "Caps", "Trucker Hat": "Caps", "Beanie": "Beanies",
                 "Bucket Hat": "Bucket hats", "Hat": "Bucket hats", "Balaclava": "Beanies"},
    "Accessories": {"Watch": "Watches", "Belt": "Belts", "Sunglasses": "Sunglasses", "Scarf": "Scarves",
                    "Socks": "Socks & underwear", "Underwear": "Socks & underwear", "Bracelet": "Jewellery",
                    "Necklace": "Jewellery", "Earrings": "Jewellery", "Ring": "Jewellery", "Wallet": "Wallets",
                    "Card Holder": "Wallets", "Tie": "Ties", "Perfume": "Perfume", "Phone Case": "Phone cases"},
}


def catalog_cats():
    s = (ROOT / "index.html").read_text(encoding="utf-8")
    m = re.search(r'<script type="application/json" id="pc-catalog">(.*?)</script>', s, re.S)
    return {str(p["id"]): p.get("cat") for p in json.loads(m.group(1))}


def build():
    live = catalog_cats()
    items = json.loads((ROOT / "data/catalog_ai.json").read_text(encoding="utf-8"))["items"]
    raw = {}
    for pid, v in items.items():
        cat, item = v.get("cat"), v.get("item")
        if pid not in live or not item or live[pid] != cat or cat not in MAP:
            continue
        sub = MAP[cat].get(item)
        if sub:
            raw[pid] = (cat, sub)
    count = Counter(raw.values())
    subs = defaultdict(list)
    for (cat, sub), n in count.most_common():
        if n >= MIN:
            subs[cat].append(sub)
    m = {pid: sub for pid, (cat, sub) in sorted(raw.items()) if sub in subs[cat]}
    order = [c for c in MAP if len(subs.get(c, [])) >= 2]
    return {"v": 1, "subs": {c: subs[c] for c in order}, "m": {k: v for k, v in m.items() if raw[k][0] in order}}


if __name__ == "__main__":
    out = build()
    text = json.dumps(out, ensure_ascii=False, separators=(",", ":"))
    path = ROOT / "data/subcats.json"
    if "--check" in sys.argv:
        ok = path.exists() and path.read_text(encoding="utf-8") == text
        print("subcats.json up to date" if ok else "subcats.json is stale: run python scripts/bake_subcats.py")
        sys.exit(0 if ok else 1)
    path.write_text(text, encoding="utf-8")
    for c, l in out["subs"].items():
        print(c, l)
    print(len(out["m"]), "finds,", len(text) // 1024, "KB")
