# -*- coding: utf-8 -*-
"""Catalogue audit: categories, titles and (optionally) a random photo sample, measured from index.html.

  python scripts/catalog_audit.py [--index index.html] [--photos 150] [--seed 150] [--out data/catalog_audit.json]

No API calls. Photos are downloaded from our own site / storage (public URLs in the catalogue). Prints a Markdown
summary and writes the numbers + example ids to --out. The checks are heuristics: they find candidates for the
vision model and for review, they do not prove a find is wrong.
"""
import argparse, collections, io, json, os, random, re, statistics, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from catalog_common import ROOT, CATS, COLOURS, load_catalog, img_url, fetch, save_json  # noqa: E402

# words that, when they are the item word of a title, say which category it belongs in
KW = {
    "Shoes": r"sneakers?|shoes?|trainers?|boots?|loafers?|slides|sandals?|mules?|clogs?|slippers?|runners?|derby|oxfords?|"
             r"espadrilles?|dunks?|air force 1|af1|air max|jordan [1-9]\b|aj ?[1-9]\b|yeezy (?:boost )?(?:350|380|500|700)|foam runner|"
             r"gel[- ]\w+|kayano|samba|gazelle|campus 00s?|spezial|990v?\d?|9060|2002r|1906r|530\b|550\b|bapesta|b2[23]\b|b30\b|"
             r"triple s|speed trainer|xt-6|tasman|uggs?",
    "Bags": r"bags?|backpacks?|totes?|duffel|duffle|handbags?|crossbody|suitcase|luggage|pouch|clutch|messenger|fanny pack|"
            r"waist bag|keepall|speedy|neverfull|saddle|sling",
    "Headwear": r"beanies?|caps?|hats?|balaclava|bucket hat|snapback|trucker|visor|headband|durag",
    "Shorts": r"shorts|swim trunks",
    "Pants": r"pants|trousers|jeans|joggers|sweatpants|cargos|leggings|track pants|chinos",
    "Outerwear": r"jackets?|puffer|parka|coats?|windbreaker|gilet|anorak|bomber|vest|overshirt|shacket|fleece jacket|down jacket|varsity|blazer",
    "Tops": r"t-shirts?|tees?|hoodies?|sweatshirts?|sweaters?|jumpers?|crewnecks?|cardigans?|polos?|shirts?|tank tops?|jerseys?|"
            r"long[- ]sleeves?|longsleeve|quarter[- ]zip|half[- ]zip|knit|turtleneck|tracksuits?|(?<!high )(?<!high-)(?<!low )(?<!low-)(?<!mid )(?<!mid-)tops?",
    "Accessories": r"belts?|wallets?|watch(?:es)?|necklaces?|bracelets?|rings?|earrings?|sunglasses|glasses|socks|scarf|scarves|"
                   r"gloves|keychain|key ?ring|ties?|card ?holder|phone case|airpods case|perfume|fragrance|cologne|boxers|briefs|"
                   r"underwear|pendant|chain|cufflinks|umbrella|neck gaiter|lanyard|towel|blanket|pillow|mask",
    "Toys": r"lego|toys?|figures?|figurines?|bearbrick|be@rbrick|kaws|plush|labubu|model car|diecast|building blocks",
}
KWRX = {c: re.compile(r"\b(?:%s)\b" % rx, re.I) for c, rx in KW.items()}
# the first match wins when a title has words from several groups ("Shorts Set", "Hoodie And Pants")
SET_RX = re.compile(r"\b(set|tracksuit|two[- ]piece|2[- ]piece|co-ord)\b", re.I)
COLRX = re.compile(r"\b(?:%s)\b" % "|".join(sorted((re.escape(c) for c in COLOURS), key=len, reverse=True)), re.I)
GENERIC = set("""t-shirt t-shirts tee tees shirt hoodie zip-up zip sweatshirt sweater jacket jackets puffer coat pants
trousers jeans joggers sweatpants shorts bag bags backpack tote sneakers shoes trainers boots cap hat beanie belt wallet watch
logo graphic print cotton basic classic plain casual new long sleeve short polo crewneck knit vest tracksuit set down
leather denim suede nylon wool mesh light dark and with of the in for men mens women womens unisex""".split())
JUNK_RX = re.compile(r"[一-鿿]|\b(1:1|rep|reps|replica|batch|ljr|pk|og batch|top quality|high quality|hot sale|"
                     r"free shipping|2023|2024|2025|2026|xs|xxl|xl|size|eu \d\d|us \d+)\b", re.I)


def item_cats(title):
    """Categories whose item words appear in the title, in order of position."""
    hits = []
    for c, rx in KWRX.items():
        m = rx.search(title)
        if m:
            hits.append((m.start(), c, m.group(0)))
    hits.sort()
    return hits


def cat_suspect(p):
    """(suggested category, reason) when the title's item word clearly belongs to another category; None otherwise."""
    t, cat = p.get("title") or "", p.get("cat")
    hits = item_cats(t)
    if not hits:
        return None
    own = [h for h in hits if h[1] == cat]
    if own:
        return None
    if SET_RX.search(t) and cat in ("Tops", "Pants", "Shorts", "Outerwear"):
        return None
    # the item word is usually the LAST category word ("Nike Tech Fleece Jacket" -> Outerwear, "Bag Charm" aside)
    last = hits[-1]
    return last[1], "'%s' in %s" % (last[2], cat)


# moves where both categories are defensible (a zip hoodie in Outerwear, a wallet in Bags): counted apart
SOFT = {("Outerwear", "Tops"), ("Tops", "Outerwear"), ("Bags", "Accessories"), ("Accessories", "Bags"),
        ("Accessories", "Headwear"), ("Headwear", "Accessories")}


def title_tokens(p):
    b = (p.get("brand") or "").lower().split()
    out = []
    for w in re.findall(r"[A-Za-z0-9'&+.\-]+", p.get("title") or ""):
        lw = w.lower()
        if lw in b:
            continue
        out.append(lw)
    return out


def title_issues(p):
    t, b = p.get("title") or "", p.get("brand") or ""
    iss = []
    rest = COLRX.sub(" ", " ".join(title_tokens(p)))
    words = [w for w in rest.split() if w]
    if not words:
        iss.append("colour_only")
    elif all(w in GENERIC for w in words):
        iss.append("no_model_or_detail")
    if b and not t.lower().startswith(b.lower()) and b.lower() not in t.lower():
        iss.append("brand_missing")
    if JUNK_RX.search(re.sub(r"(?i)margiela( \w+)? replica", "", t)):     # "Replica" is a Margiela model name
        iss.append("junk_words")
    if "—" in t or "–" in t:
        iss.append("dash")
    dw = re.search(r"\b(\w+) \1\b", t, re.I)
    if dw and dw.group(0).lower() not in b.lower() and not re.search(r"(?i)off-white white", t):
        iss.append("doubled_word")
    if len(t.split()) > 7 or len(t) > 48:
        iss.append("long")
    if len(COLRX.findall(t)) >= 3:
        iss.append("many_colours")
    if t.isupper() and len(t) > 6:
        iss.append("all_caps")
    return iss


def audit_titles(items):
    out = {}
    lens_w = [len((p.get("title") or "").split()) for p in items]
    lens_c = [len(p.get("title") or "") for p in items]
    out["length_words"] = {"min": min(lens_w), "median": statistics.median(lens_w), "max": max(lens_w),
                           "p90": sorted(lens_w)[int(len(lens_w) * 0.9)]}
    out["length_chars"] = {"min": min(lens_c), "median": statistics.median(lens_c), "max": max(lens_c),
                           "p90": sorted(lens_c)[int(len(lens_c) * 0.9)]}
    by_t = collections.defaultdict(list)
    for p in items:
        by_t[(p.get("title") or "").strip().lower()].append(p["id"])
    dups = {k: v for k, v in by_t.items() if len(v) > 1}
    out["unique_titles"] = len(by_t)
    out["duplicate_groups"] = len(dups)
    out["finds_sharing_a_title"] = sum(len(v) for v in dups.values())
    out["top_duplicates"] = sorted(([k, len(v), v[:4]] for k, v in dups.items()), key=lambda x: -x[1])[:12]
    issues = collections.defaultdict(list)
    for p in items:
        for i in title_issues(p):
            issues[i].append(p["id"])
    out["issues"] = {k: len(v) for k, v in sorted(issues.items(), key=lambda x: -len(x[1]))}
    idx = {p["id"]: p for p in items}
    rnd = random.Random(7)
    out["issue_examples"] = {k: [[i, idx[i]["cat"], idx[i]["title"]] for i in rnd.sample(v, min(8, len(v)))] for k, v in issues.items()}
    # no-model titles per category (where model names matter most: Shoes, Bags)
    per = collections.Counter(idx[i]["cat"] for i in issues.get("no_model_or_detail", []))
    tot = collections.Counter(p["cat"] for p in items)
    out["no_model_by_cat"] = {c: [per[c], tot[c], round(per[c] / tot[c], 3) if tot[c] else 0] for c in CATS}
    # colour position: first word after the brand vs last word
    first = last = 0
    for p in items:
        toks = title_tokens(p)
        if toks and COLRX.fullmatch(toks[0]): first += 1
        if toks and COLRX.fullmatch(toks[-1]): last += 1
    out["colour_first"] = first; out["colour_last"] = last
    return out


def audit_cats(items):
    out = {"counts": dict(collections.Counter(p["cat"] for p in items).most_common())}
    sus = []
    for p in items:
        r = cat_suspect(p)
        if r:
            sus.append([p["id"], p["cat"], r[0], p["title"], r[1]])
    out["suspect_total"] = len(sus)
    out["suspect_strong"] = sum(1 for x in sus if (x[1], x[2]) not in SOFT)
    out["suspect_by_move"] = dict(collections.Counter("%s -> %s" % (s[1], s[2]) for s in sus).most_common(25))
    out["no_item_word"] = sum(1 for p in items if not item_cats(p.get("title") or ""))
    rnd = random.Random(11)
    out["suspects_sample"] = rnd.sample(sus, min(40, len(sus)))
    out["suspects_all"] = sus
    return out


def audit_photos(items, n, seed, cache_dir=None):
    from PIL import Image
    from photo_metrics import measure, FLAGS
    rnd = random.Random(seed)
    smp = rnd.sample(items, min(n, len(items)))
    res, fails = {}, []
    for p in smp:
        try:
            fn = cache_dir and os.path.join(cache_dir, p["id"] + ".img")
            if fn and os.path.exists(fn):
                data = open(fn, "rb").read()
            else:
                data = fetch(img_url(p))
                if fn:
                    os.makedirs(cache_dir, exist_ok=True); open(fn, "wb").write(data)
            res[p["id"]] = measure(Image.open(io.BytesIO(data)))
        except Exception as e:
            fails.append([p["id"], str(e)[:80]])
    flags = {f: [i for i, m in res.items() if m.get(f)] for f in FLAGS}
    fills = [m["fill"] for m in res.values()]
    return {
        "sample": len(smp), "measured": len(res), "failed": fails,
        "cutouts": sum(1 for m in res.values() if m["cutout"]),
        "sizes": dict(collections.Counter("%dx%d" % (m["w"], m["h"]) for m in res.values()).most_common(6)),
        "fill_median": statistics.median(fills) if fills else 0,
        "fill_p10_p90": [sorted(fills)[len(fills) // 10], sorted(fills)[len(fills) * 9 // 10]] if fills else [],
        "flags": {f: [len(v), v[:10]] for f, v in flags.items()},
        "per_id": res,
    }


def md(rep):
    c, t = rep["categories"], rep["titles"]
    L = ["## Categories", "", "| Category | Finds |", "|---|---:|"]
    L += ["| %s | %d |" % (k, v) for k, v in c["counts"].items()]
    L += ["", "Title says another category: **%d** finds (%d clear, the rest Tops/Outerwear or Bags/Accessories judgement calls); title has no item word at all: %d." % (c["suspect_total"], c["suspect_strong"], c["no_item_word"]), ""]
    L += ["| Move | Finds |", "|---|---:|"] + ["| %s | %d |" % kv for kv in list(c["suspect_by_move"].items())[:15]]
    L += ["", "## Titles", "", "Words: %s. Characters: %s." % (t["length_words"], t["length_chars"]),
          "Unique titles %d of %d; %d titles are shared by %d finds." % (t["unique_titles"], rep["finds"], t["duplicate_groups"], t["finds_sharing_a_title"]), ""]
    L += ["| Issue | Finds |", "|---|---:|"] + ["| %s | %d |" % kv for kv in t["issues"].items()]
    if "photos" in rep:
        ph = rep["photos"]
        L += ["", "## Photos (random sample of %d)" % ph["measured"], "", "Cut-outs with transparency: %d. Sizes: %s. Median fill %.3f." % (ph["cutouts"], ph["sizes"], ph["fill_median"]), ""]
        L += ["| Flag | Photos |", "|---|---:|"] + ["| %s | %d |" % (k, v[0]) for k, v in ph["flags"].items()]
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", default=os.path.join(ROOT, "index.html"))
    ap.add_argument("--photos", type=int, default=0)
    ap.add_argument("--seed", type=int, default=150)
    ap.add_argument("--cache", default=None, help="folder to keep downloaded sample photos")
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "catalog_audit.json"))
    a = ap.parse_args()
    _, items, _, _ = load_catalog(a.index)
    rep = {"finds": len(items), "categories": audit_cats(items), "titles": audit_titles(items)}
    if a.photos:
        rep["photos"] = audit_photos(items, a.photos, a.seed, a.cache)
    save_json(a.out, rep)
    print(md(rep))
    print("\nwrote", a.out)


if __name__ == "__main__":
    main()
