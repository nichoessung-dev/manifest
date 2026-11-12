#!/usr/bin/env python3
"""Write the approved partner link swaps (/partner, Supabase approved_swaps()) for the app, the server pages and the emails.

Runs in GitHub Actions (.github/workflows/swaps.yml, every 15 minutes) with the SUPABASE_SERVICE_KEY secret. Writes, only
when something in them changed (the "updated" stamp alone never causes a commit):
  data/link_swaps.json
    {"updated": ...,
     "swaps":   {find id: [platform, item id]},
     "price":   {find id: [item id, cny, usd]},      the partner item's own price (Weidian only, see below)
     "hide":    [find id, ...],                      look-alikes of swapped finds, hidden everywhere
     "hide_of": {look-alike id: swapped find id}}
  functions/_lib/link_swaps.js
    export const SWAPS = {...}; export const SWAP_PRICE = {...}; export const SWAP_HIDE = {look-alike: swapped find};
The app (index.html) also reads approved_swaps() itself, so a swap's Buy link and priority show there at once; the price
and the look-alikes come from this file (the app works the look-alikes out itself too, with the same rule).

Price (owner, 12 Nov 2026: "make the price automatically update when switching link"): for a Weidian item the price is
read from Weidian's public item API (the same one scripts/check_links.py uses), the item's lowest price (the "from"
price, what the find cards show), in yuan. Every run looks the items up again, so a partner's price change shows within
15 minutes. A failed lookup keeps the last price read for the same item. Taobao and 1688 have no public price lookup:
those finds keep their catalogue price. usd = cny times the find's own catalogue usd/cny rate (0.1394 when unknown).

Look-alikes (owner: "the links that are like the ones that has been switched to be removed from the spreadsheet"): every
other find of the same brand, category and kind of item (kind_of) as a swapped find; with no readable kind, the same name group (brand + title, lower case, after the same brand clean-up as
functions/_lib/site.js and index.html, the key of idx().groups) AND the same category. A swapped find is never hidden.

Local run without the service key (offline): python3 scripts/bake_swaps.py --from-json data/link_swaps.json
  (takes the swaps from that file, still looks the prices up and works the look-alikes out from index.html).
Ids, item ids and prices only, no emails.
"""
import argparse, datetime, json, os, re, sys, time, urllib.parse, urllib.request

SUPA = "https://uptpghuduqjqmrxwatbm.supabase.co"
OUT, JS = "data/link_swaps.json", "functions/_lib/link_swaps.js"
TAG = '<script type="application/json" id="pc-catalog">'
WD_API = "https://thor.weidian.com/detail/getItemSkuInfo/1.0?param="
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
MAX_LOOKUPS = 150      # Weidian lookups per run (one per swapped Weidian find); the rest keep their last price
PAUSE = 0.6            # seconds between lookups: Weidian refuses bursts
USD_RATE = 0.1394      # catalogue rate, used when the find has no usd/cny of its own
# Same map as functions/_lib/site.js BRAND_ALIAS and index.html (loadProducts): the group key must match theirs.
BRAND_ALIAS = {"Essential": "Essentials", "Arcteryx": "Arc'teryx", "Cp": "CP Company", "Cdg": "Comme des Garcons",
               "Comme Des Garcons": "Comme des Garcons", "Comme des Garçons": "Comme des Garcons", "Ami Paris": "Ami", "Alo": "Alo Yoga",
               "Purple": "Purple Brand", "Carhart": "Carhartt", "Merta": "Mertra", "Aime": "Aime Leon Dore", "PROJECT G/R": "Project GR",
               "Parajumper": "Parajumpers", "ERD": "Enfants Riches Déprimés", "Polo": "Ralph Lauren"}


def norm(p):
    """(brand, title) after the site's clean-up (site.js normBrand)."""
    brand, title = str(p.get("brand") or ""), str(p.get("title") or "")
    if brand == "Uncategorized":
        brand, title = "", re.sub(r"^Uncategorized\s+", "", title)
    nb = BRAND_ALIAS.get(brand)
    if nb:
        if title.startswith(brand + " ") and not title.lower().startswith(nb.lower() + " "): title = nb + title[len(brand):]
        brand = nb
    return brand, title


# kinds of item, first match wins (so "Down Jacket" is a jacket, "Zip Hoodie" a hoodie); read from the title
KINDS = [
    ("jacket", r"jacket|coat|parka|puffer|down|windbreaker|shell|gilet|vest|anorak|bomber|overshirt|blazer"),
    ("hoodie", r"hoodie|hoody|hooded"),
    ("sweater", r"sweater|knit|knitwear|cardigan|jumper|sweatshirt|crewneck|crew neck|quarter zip|half zip|fleece"),
    ("long sleeve", r"long ?sleeve|longsleeve"),
    ("tee", r"t-?shirt|tee|tees|tank|polo|jersey|shirt|top"),
    ("tracksuit", r"tracksuit|track suit|set"),
    ("pants", r"pants|trousers|jeans|joggers|sweatpants|cargos?|leggings"),
    ("shorts", r"shorts|swim ?shorts|trunks"),
    ("shoes", r"shoes?|sneakers?|trainers?|boots?|slides?|sandals?|loafers?|runners?|clogs?|slippers?"),
    ("bag", r"bags?|backpack|tote|wallet|cardholder|card holder|purse|pouch|duffel|crossbody"),
    ("hat", r"cap|hat|beanie|bucket"),
    ("belt", r"belts?"),
    ("socks", r"socks?"),
    ("scarf", r"scarf|scarves|balaclava|gloves?"),
    ("glasses", r"glasses|sunglasses"),
    ("jewellery", r"necklace|bracelet|ring|earrings?|chain|pendant"),
    ("watch", r"watch"),
]
KIND_RE = [(k, re.compile(r"\b(?:%s)\b" % rx, re.I)) for k, rx in KINDS]


def kind_of(p):
    """The kind of item from the title (after the brand), or "" when none matches."""
    t = norm(p)[1]
    for k, rx in KIND_RE:
        if rx.search(t): return k
    return ""


def group_key(p):
    b, t = norm(p)
    return (b + "|" + t).lower()


def catalogue(root):
    html = open(os.path.join(root, "index.html"), encoding="utf-8").read()
    i = html.find(TAG)
    if i < 0: raise SystemExit("pc-catalog block not found in index.html")
    j = html.find("</script>", i)
    return json.loads(html[i + len(TAG):j])


def fetch_swaps(key):
    req = urllib.request.Request(SUPA + "/rest/v1/rpc/approved_swaps", data=b"{}", method="POST",
                                 headers={"apikey": key, "Authorization": "Bearer " + key, "Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=30))


def clean_swaps(rows):
    swaps = {}
    for r in rows:
        pid, pl, item = str(r.get("pid") or ""), str(r.get("platform") or ""), str(r.get("item_id") or "")
        if re.fullmatch(r"[0-9A-Za-z_-]{1,40}", pid) and pl in ("weidian", "taobao", "1688") and re.fullmatch(r"[0-9]{5,20}", item):
            swaps[pid] = [pl, item]
    return dict(sorted(swaps.items()))


def weidian_price(item_id):
    """The item's lowest price in yuan, or None (lookup failed, item gone, no price)."""
    url = WD_API + urllib.parse.quote(json.dumps({"itemId": str(item_id)}))
    for wait in (0, 4, 12):
        if wait: time.sleep(wait)
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA, "Referer": "https://weidian.com/"}), timeout=20) as r:
                d = json.load(r)
        except Exception:
            continue
        if (d.get("status") or {}).get("code") != 0: continue
        res = d.get("result") or {}
        if not (res.get("itemTitle") or res.get("itemMainPic")): return None      # the item is gone
        for k in ("itemDiscountLowPrice", "itemOriginalLowPrice"):                # fen (1/100 yuan)
            v = res.get(k)
            if isinstance(v, (int, float)) and v > 0:
                y = v / 100.0
                return int(y) if y == int(y) else round(y, 2)
        return None
    return None


def bake(swaps, items, old):
    """The new file's content (without the stamp) from the swaps, the catalogue and the previous file."""
    by_id = {str(p.get("id")): p for p in items}
    old_price = (old or {}).get("price") or {}
    price, looked = {}, 0
    for pid, (pl, item) in swaps.items():
        if pl != "weidian": continue                                         # Taobao and 1688: catalogue price stays
        cny = None
        if looked < MAX_LOOKUPS:
            if looked: time.sleep(PAUSE)
            looked += 1
            cny = weidian_price(item)
        if cny is None:                                                      # keep the last price read for the same item
            o = old_price.get(pid)
            if isinstance(o, list) and len(o) == 3 and str(o[0]) == item: cny = o[1]
        if cny is None: continue
        p = by_id.get(pid) or {}
        try: rate = float(p.get("usd")) / float(p.get("price")) if float(p.get("price") or 0) > 0 and float(p.get("usd") or 0) > 0 else USD_RATE
        except (TypeError, ValueError): rate = USD_RATE
        if not 0.05 < rate < 0.5: rate = USD_RATE
        price[pid] = [item, cny, round(cny * rate, 2)]
    # look-alikes (owner, 12 Nov 2026: "now that we have this arcteryx jacket swapped remove all of the other jackets, do the
    # same with all swapped items"): every other find of the same brand, category and kind of item (kind_of: jacket, hoodie,
    # pants, ...). A find whose kind can't be read falls back to the same name group. Never a swapped find itself.
    groups, kinds = {}, {}
    for p in items:
        cat = str(p.get("cat") or "")
        groups.setdefault((group_key(p), cat), []).append(str(p.get("id")))
        b, k = norm(p)[0].lower(), kind_of(p)
        if b and k: kinds.setdefault((b, cat, k), []).append(str(p.get("id")))
    hide_of = {}
    for pid in swaps:
        p = by_id.get(pid)
        if not p: continue
        cat, b, k = str(p.get("cat") or ""), norm(p)[0].lower(), kind_of(p)
        same = kinds.get((b, cat, k), []) if (b and k) else groups.get((group_key(p), cat), [])
        for oid in same:
            if oid != pid and oid not in swaps and oid not in hide_of: hide_of[oid] = pid
    hide_of = dict(sorted(hide_of.items()))
    return {"swaps": swaps, "price": dict(sorted(price.items())), "hide": sorted(hide_of), "hide_of": hide_of}, looked


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--from-json", help="take the swaps from this link_swaps.json instead of Supabase (local runs)")
    a = ap.parse_args(argv)
    out, js = os.path.join(a.root, OUT), os.path.join(a.root, JS)
    if a.from_json:
        swaps = clean_swaps([{"pid": k, "platform": v[0], "item_id": v[1]} for k, v in (json.load(open(a.from_json, encoding="utf-8")).get("swaps") or {}).items()])
    else:
        key = os.environ.get("SUPABASE_SERVICE_KEY")
        if not key:
            print("no SUPABASE_SERVICE_KEY: nothing to do"); return
        try:
            swaps = clean_swaps(fetch_swaps(key))
        except Exception as e:
            print("approved_swaps() not reachable (table not set up yet?):", e); return
    try:
        old = json.load(open(out, encoding="utf-8"))
    except (OSError, ValueError):
        old = None
    doc, looked = bake(swaps, catalogue(a.root), old)
    same = old is not None and all(old.get(k) == doc[k] for k in doc) and os.path.exists(js) and "SWAP_HIDE" in open(js, encoding="utf-8").read()
    print("%d swaps, %d Weidian prices looked up, %d with a partner price, %d look-alikes hidden" % (len(swaps), looked, len(doc["price"]), len(doc["hide"])))
    for pid, v in doc["price"].items(): print("  price %s -> %s %s: CNY %s (USD %s)" % (pid, swaps[pid][0], v[0], v[1], v[2]))
    for oid, pid in doc["hide_of"].items(): print("  hide %s (look-alike of %s)" % (oid, pid))
    if same:
        print("no change"); return
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    json.dump(dict({"updated": now}, **doc), open(out, "w", encoding="utf-8"), separators=(",", ":"))
    j = lambda o: json.dumps(o, separators=(",", ":"))
    open(js, "w", encoding="utf-8").write(
        "// GENERATED by scripts/bake_swaps.py (Swaps workflow) from the approved partner swaps on /partner. Do not edit by hand.\n"
        "// SWAPS: find id -> [platform, item id]: site.js sends that find's Buy buttons to this item and ranks the find first everywhere.\n"
        "// SWAP_PRICE: find id -> [item id, cny, usd]: the partner item's own price (Weidian), shown instead of the catalogue price.\n"
        "// SWAP_HIDE: look-alike find id -> swapped find id: the other finds of the same item, hidden like reported finds.\n"
        "export const SWAPS = " + j(swaps) + ";\n"
        "export const SWAP_PRICE = " + j(doc["price"]) + ";\n"
        "export const SWAP_HIDE = " + j(doc["hide_of"]) + ";\n")
    print("wrote %s and %s" % (OUT, JS))


if __name__ == "__main__":
    sys.exit(main())
