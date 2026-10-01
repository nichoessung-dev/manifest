#!/usr/bin/env python3
"""Normalise the catalogue in index.html (the source of truth) in place: brand spellings, import leftovers,
doubled brand names in titles and obvious category mistakes. Idempotent; run after every import, then
python scripts/gen_catalog.py so functions/_lib/catalog.js gets the same data.

Run from the repo root:  python scripts/clean_catalog.py [--dry-run]

Keep BRAND_ALIAS in sync with the load-time copies in index.html (loadProducts) and functions/_lib/site.js.
"""
import json, re, sys

TAG = '<script type="application/json" id="pc-catalog">'

# spelling/case variants -> the one brand name the filters, hubs and POP_BRANDS use
BRAND_ALIAS = {
    "Essential": "Essentials", "Arcteryx": "Arc'teryx", "Cp": "CP Company", "Cdg": "Comme des Garcons",
    "Comme Des Garcons": "Comme des Garcons", "Comme des Garçons": "Comme des Garcons", "Ami Paris": "Ami",
    "Alo": "Alo Yoga", "Purple": "Purple Brand", "Carhart": "Carhartt", "Merta": "Mertra", "Aime": "Aime Leon Dore",
    "PROJECT G/R": "Project GR", "Parajumper": "Parajumpers", "ERD": "Enfants Riches Déprimés", "Polo": "Ralph Lauren",
}
# "<brand> <prefix>" titles where the model name already carries the brand -> drop the leading brand
DOUBLED = [("Jordan", "Air Jordan "), ("Yeezy", "Air Yeezy "), ("Dior", "Christian Dior ")]

# (target category, title pattern, only move from these categories, unless the title matches this)
CAT_RULES = [
    ("Bags", r"\b(bags?|backpack|tote|duffel|duffle|handbag|crossbody|suitcase|luggage)\b", {"Accessories"}, None),
    ("Shorts", r"\bshorts\b", {"Pants", "Tops", "Accessories"}, r"\b(set|tracksuit)\b"),
    ("Headwear", r"\b(beanie|cap|hat|balaclava)\b", {"Tops", "Accessories"}, r"\bjacket\b"),
    ("Shoes", r"\b(sneakers?|shoes?|boots?|trainers?|slides|sandals?|loafers?|runner)\b", {"Tops", "Pants", "Outerwear"},
     r"\b(t-shirt|tee|shirt|hoodie|socks?)\b"),
    ("Outerwear", r"\b(puffer|parka|coat|windbreaker|jacket|gilet|anorak)\b", {"Tops", "Pants", "Shoes"}, r"\b(set|tracksuit)\b"),
    ("Pants", r"\b(track pants|sweatpants|trousers|jeans|joggers)\b", {"Tops"}, r"\bset\b"),
]


def clean_item(p):
    """Returns a list of human-readable changes made to p."""
    ch = []
    b, t = p.get("brand") or "", p.get("title") or ""
    if b == "Uncategorized":                      # import fallback written into brand + title
        p["brand"], p["title"] = "", re.sub(r"^Uncategorized\s+", "", t)
    elif b in BRAND_ALIAS:
        nb = BRAND_ALIAS[b]
        if b == "Polo" and t.startswith("Polo Polo "):
            t = "Polo " + t[len("Polo Polo "):]
        if t.startswith(b + " ") and not t.lower().startswith(nb.lower() + " "):
            t = nb + " " + (t[len(b) + 1:] if b != "Polo" else t)   # "Polo Puffer" -> "Ralph Lauren Polo Puffer"
        p["brand"], p["title"] = nb, t
    for brand, pre in DOUBLED:
        if p["brand"] == brand and p["title"].startswith(brand + " " + pre):
            p["title"] = p["title"][len(brand) + 1:]
    if p["title"] != t or p["brand"] != b:
        ch.append(f"{b!r}|{t!r} -> {p['brand']!r}|{p['title']!r}")
    cat = p.get("cat")
    for target, rx, src, ex in CAT_RULES:
        if cat in src and re.search(rx, p["title"], re.I) and not (ex and re.search(ex, p["title"], re.I)):
            p["cat"] = target
            ch.append(f"cat {cat} -> {target}: {p['title']}")
            break
    return ch


def main():
    html = open("index.html", encoding="utf-8").read()
    i = html.find(TAG)
    j = html.find("</script>", i)
    if i < 0:
        sys.exit("pc-catalog block not found")
    raw = html[i + len(TAG):j]
    items = json.loads(raw)
    log = []
    for p in items:
        for c in clean_item(p):
            log.append(p["id"] + "  " + c)
    print("\n".join(log))
    print(len(log), "changes")
    out = json.dumps(items, ensure_ascii=False, separators=(",", ":"))
    if "</" in out:
        out = out.replace("</", "<\\/")           # keep the JSON from closing its <script>
    if "--dry-run" in sys.argv or out == raw:
        return
    open("index.html", "w", encoding="utf-8").write(html[:i + len(TAG)] + out + html[j:])
    print("index.html updated")


if __name__ == "__main__":
    main()
