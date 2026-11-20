# -*- coding: utf-8 -*-
"""Candidate store photos for the partner's finds (owner, 20 Nov 2026: "every one of the partner's finds should get the
real store's product photos": a clean front shot as the main photo, then the rest of the store gallery, then on-model
shots of the same design).

Step 1 of 2. Runs where the Brave Search API is reachable (the Claude Code container; GitHub Actions has no Brave key).
Per partner find (keys of data/link_swaps.json "swaps"), most viewed first (data/stats.json "p"[id][0]):
  1. two Brave image searches: the find's title (brand + words + colour), then the title without the colour plus a
     category word (so the brand's iconic colour turns up when the find's own colour has no store photos)
  2. any result page that looks like a Shopify product (/products/...) is asked for <page>.json, which lists the whole
     store gallery at full size
  3. secondhand and marketplace hosts (eBay, Etsy, Vinted, Depop, Grailed, Reddit, Pinterest, ...) and small images
     (longest side < 800 px) are dropped; at most 25 candidates are kept
Writes data/store_photo_candidates.json {"items": {id: {"q": [queries], "p": [pages], "c": [[img, page index, w, h,
"b" Brave hit | "s" Shopify gallery], ...]}}}. Step 2 (scripts/store_photos_pick.py, GitHub Actions) chooses from these.

  python scripts/store_photos_collect.py [--limit 300] [--offset 0] [--ids 1,2] [--redo]
"""
import argparse, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from catalog_common import COLOURS, ROOT, load_catalog, load_json  # noqa: E402

OUT = os.path.join(ROOT, "data", "store_photo_candidates.json")
BRAVE = "https://api.search.brave.com/res/v1/images/search?count=30&safesearch=strict&q="
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36"
MAX_C = 25
MIN_SIDE = 800
BAD_HOSTS = ("ebay.", "etsy.", "vinted.", "depop.", "grailed.", "reddit.", "redd.it", "pinterest.", "pinimg.", "poshmark.",
             "mercari.", "aliexpress.", "alicdn.", "dhgate.", "weidian.", "geilicdn.", "taobao.", "1688.", "yupoo.",
             "instagram.", "tiktok.", "facebook.", "fbcdn.", "twitter.", "youtube.", "ytimg.", "vestiairecollective.",
             "therealreal.", "tradesy.", "thredup.", "kidizen.", "carousell.", "olx.", "wallapop.", "kleinanzeigen.",
             "marktplaats.", "gumtree.", "craigslist.", "offerup.", "shpock.", "tise.", "finn.no", "blocket.", "quora.",
             "stockx.", "goat.com", "flightclub.", "kicksonfire.", "sneakernews.", "hypebeast.", "highsnobiety.", "wikipedia.",
             "wikimedia.", "fandom.", "lyst.", "temu.", "shein.", "wish.com", "joom.", "pandabuy", "cnfans", "kakobuy",
             "superbuy", "sugargoo", "hoobuy", "allchinabuy", "mulebuy", "acbuy", "litbuy", "oopbuy", "orientdig", "rep")
CAT_WORD = {"Shoes": "sneakers", "Outerwear": "jacket", "Tops": "", "Pants": "pants", "Shorts": "shorts", "Bags": "bag",
            "Accessories": "", "Headwear": "cap", "Toys": "toy"}
PAUSE = 1.05
_last = [0.0]


def get_json(url, headers, timeout=20):
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout) as r:
        return json.load(r)


def brave(q):
    wait = PAUSE - (time.time() - _last[0])
    if wait > 0: time.sleep(wait)
    for k in range(3):
        _last[0] = time.time()
        try:
            return get_json(BRAVE + urllib.parse.quote(q), {"X-Subscription-Token": "x", "Accept": "application/json"}).get("results") or []
        except urllib.error.HTTPError as e:
            if e.code != 429: print("  brave", e.code, q, flush=True); return []
        except Exception as e:
            print("  brave", e, flush=True)
        time.sleep(3 * (k + 1))
    return []


def bad_host(h):
    h = (h or "").lower()
    if h.startswith("rep") or ".rep" in h or h == "x.com" or h.endswith(".x.com"): return True
    return any(b in h for b in BAD_HOSTS if b != "rep")


def colour_of(title):
    t = " " + title.lower() + " "
    return [c for c in sorted(COLOURS, key=len, reverse=True) if " " + c + " " in t]


def queries(p):
    title = re.sub(r"\s+", " ", p.get("title") or "").strip()
    brand = p.get("brand") or ""
    q1 = title if brand.lower() in title.lower() else f"{brand} {title}"
    q2 = q1
    for c in colour_of(q1): q2 = re.sub(r"(?i)\b" + re.escape(c) + r"\b", " ", q2)
    w = CAT_WORD.get(p.get("cat"), "")
    if w and w not in q2.lower(): q2 += " " + w
    q2 = re.sub(r"\s+", " ", q2).strip()
    return [q1] if q2.lower() == q1.lower() else [q1, q2]


def shopify(page):
    """The store gallery of a Shopify product page: [(src, w, h)] at full size, or []."""
    u = urllib.parse.urlsplit(page)
    m = re.search(r"/products/([^/?#]+)", u.path)
    if not m: return []
    url = f"{u.scheme}://{u.netloc}{u.path[:m.end()]}.json"
    try:
        d = get_json(url, {"User-Agent": UA, "Accept": "application/json"}, timeout=15)
    except Exception:
        return []
    out = []
    for im in ((d.get("product") or {}).get("images") or [])[:12]:
        s = im.get("src") or ""
        if s.startswith("//"): s = "https:" + s
        if s: out.append((s, im.get("width") or 0, im.get("height") or 0))
    return out


def collect(p):
    qs = queries(p)
    pages, cands, seen, shop_pages = [], [], set(), []

    def page_i(u):
        if u not in pages: pages.append(u)
        return pages.index(u)

    def add(img, page, w, h, kind):
        key = re.sub(r"[?#].*$", "", img)
        if key in seen or len(cands) >= MAX_C * 2: return
        if max(w or 0, h or 0) and max(w, h) < MIN_SIDE: return
        seen.add(key); cands.append([img, page_i(page), int(w or 0), int(h or 0), kind])

    for q in qs:
        for r in brave(q):
            host = (r.get("meta_url") or {}).get("hostname") or r.get("source") or ""
            img = (r.get("properties") or {}).get("url") or ""
            page = r.get("url") or ""
            if not img or bad_host(host) or bad_host(urllib.parse.urlsplit(img).netloc): continue
            pr = r.get("properties") or {}
            add(img, page, pr.get("width") or 0, pr.get("height") or 0, "b")
            if "/products/" in page and page not in shop_pages and len(shop_pages) < 3: shop_pages.append(page)
    # store galleries first (whole sets of angles + on-model), then the remaining Brave hits
    gal = []
    for page in shop_pages:
        for s, w, h in shopify(page):
            gal.append((s, page, w, h))
    brave_c = cands; cands, seen = [], set()
    for s, page, w, h in gal: add(s, page, w, h, "s")
    for c in brave_c: add(c[0], pages[c[1]], c[2], c[3], c[4])
    # keep a mix: up to 15 gallery shots, Brave hits fill the rest
    g = [c for c in cands if c[4] == "s"][:15]
    b = [c for c in cands if c[4] == "b"][:MAX_C - len(g)]
    keep = g + b
    used = sorted({c[1] for c in keep})
    remap = {o: n for n, o in enumerate(used)}
    return {"q": qs, "p": [pages[o] for o in used], "c": [[c[0], remap[c[1]], c[2], c[3], c[4]] for c in keep]}


def partner_ids(items):
    swaps = (load_json(os.path.join(ROOT, "data", "link_swaps.json"), {}) or {}).get("swaps") or {}
    stats = (load_json(os.path.join(ROOT, "data", "stats.json"), {}) or {}).get("p") or {}
    by = {p["id"]: p for p in items}
    ids = [i for i in swaps if i in by]
    ids.sort(key=lambda i: (-(stats.get(i) or [0])[0], i))
    return ids, by


def save(data):
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("{\"items\": {\n")
        rows = [json.dumps(k) + ": " + json.dumps(v, ensure_ascii=False, separators=(",", ":")) for k, v in data["items"].items()]
        f.write(",\n".join(rows))
        f.write("\n}}\n")
    os.replace(tmp, OUT)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=300)
    ap.add_argument("--offset", type=int, default=0)
    ap.add_argument("--ids", default="")
    ap.add_argument("--redo", action="store_true")
    a = ap.parse_args()
    ids, by = partner_ids(load_catalog()[1])
    ids = [i for i in a.ids.split(",") if i] if a.ids else ids[a.offset:a.offset + a.limit]
    data = load_json(OUT, {"items": {}})
    todo = [i for i in ids if a.redo or i not in data["items"]]
    print(f"{len(ids)} partner finds asked, {len(todo)} to search", flush=True)
    for n, i in enumerate(todo, 1):
        p = by[i]
        try:
            data["items"][i] = collect(p)
        except Exception as e:
            print(f"  {i} failed: {e}", flush=True); continue
        print(f"[{n}/{len(todo)}] {i} {p.get('title')}: {len(data['items'][i]['c'])} candidates", flush=True)
        if n % 10 == 0: save(data)
    save(data)
    print("done,", len(data["items"]), "finds in", os.path.relpath(OUT, ROOT))


if __name__ == "__main__":
    main()
