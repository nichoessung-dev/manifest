#!/usr/bin/env python3
"""Offline check of the "Most popular" order (index.html popScore / pcSmartPop, r9, 7 Nov 2026).

data/stats.json has, per find, views all time / last 30 days / last 7 days and saves. The last 7 days are held out: each
order is built from what was known before them (views of days 8-30 and older, saves scaled to that share) and scored on
the views each find really got in the held-out week. Nothing is fetched; only aggregate counts are read.

  NDCG@k        how well the first k finds match the finds people really opened next week (1 = perfect)
  outside AUC   the same idea where the grid's own order matters least: among finds outside the old top 300, the chance a
                find that got views next week ranks above one that got none (0.5 = guessing)
  brands48      different brands in the first 48;  top brand = most finds of one brand in the first 48
  run           longest run of one brand in a row;  dup48 = near-duplicates (same brand, garment type and colour) in 48
  new/week      finds without a single view that got a place in the first 200 on at least one day of a week

Caveat: the held-out views were caused partly by the old order itself (the top of the grid gets the clicks), so NDCG is
biased towards the old order. Variety and exploration always cost a little NDCG here; that is the price of showing more
than the same few listings, not a sign the order got worse.

Result on the 7 Nov 2026 file (9,202 finds, 7 day rotations averaged):
  OLD views (live popScore)    NDCG@24 0.872 @48 0.883 @200 0.899  outside AUC 0.768  brands48 26  top brand 10  run 2  dup48 7  new/week 0
  NEW variety, no explore      NDCG@24 0.854 @48 0.872 @200 0.893  outside AUC 0.768  brands48 28  top brand 8   run 1  dup48 5  new/week 0
  NEW full (variety+explore)   NDCG@24 0.843 @48 0.855 @200 0.880  outside AUC 0.767  brands48 29  top brand 7   run 2  dup48 4  new/week 53
  The score itself orders finds like the old one (same NDCG and AUC before the re-pick). Signals tested and left out
  because they made the prediction worse: brand and brand x type averages, QC photo count, save rate. Price and the AI
  photo and title labels added next to nothing. Older views (before the last 30 days) help only as a tie-break. For a find
  with no views at all, its brand's popularity is the best hint (AUC 0.60), which is how the exploration places are filled.

  python3 scripts/rank_eval.py [--root .]
"""
import argparse, collections, json, math, os, re

FY_TYPES = [("zip hoodie", r"zip.?up hood|zip hood|full zip|half.?zip|quarter.?zip|1/4 zip"), ("hoodie", r"hood"),
            ("tracksuit", r"tracksuit|track suit"), ("track jacket", r"track (jacket|top)"),
            ("puffer", r"puffer|down jacket|nuptse|down coat|maya|parka"), ("vest", r"vest|gilet|bodywarmer"),
            ("fleece", r"fleece|sherpa"), ("coat", r"\bcoat\b|trench|overcoat"),
            ("jacket", r"jacket|windbreaker|bomber|overshirt|shacket|anorak|blouson"),
            ("knit", r"knit|sweater|jumper|cardigan|cable"), ("crewneck", r"crewneck|crew neck|sweatshirt"),
            ("polo", r"polo(?! bear)|\bpolo shirt"), ("shirt", r"\bshirt\b|oxford|button.?down|flannel"),
            ("tee", r"\btee\b|t-shirt|tshirt|t shirt|long sleeve|longsleeve"),
            ("jeans", r"jeans|denim pant|\bdenim\b"), ("sweatpants", r"sweatpant|jogger|track pant"), ("shorts", r"shorts|swim"),
            ("pants", r"pant|trouser|chino|cargo"),
            ("sneakers", r"sneaker|trainer|jordan|dunk|air force|yeezy|runner|\bsb\b|9060|550|xt-6|samba|gazelle|shoe"),
            ("boots", r"boot"), ("slides", r"slide|sandal|slipper|clog|mule"), ("loafers", r"loafer|moccasin|derby|oxford shoe"),
            ("bag", r"bag|tote|backpack|duffle|crossbody|messenger|pouch|clutch|purse"), ("wallet", r"wallet|card ?holder|card case"),
            ("belt", r"belt"), ("cap", r"\bcap\b|hat\b|snapback|trucker|bucket"), ("beanie", r"beanie|balaclava"),
            ("watch", r"watch|rolex|submariner|datejust|daytona|omega|cartier"),
            ("jewelry", r"ring|necklace|bracelet|earring|chain|pendant|jewel"), ("glasses", r"sunglass|glasses|eyewear"),
            ("scarf", r"scarf|shawl"), ("socks", r"sock"), ("toy", r"toy|figure|labubu|plush|bearbrick")]
FY_TYPES = [(a, re.compile(b, re.I)) for a, b in FY_TYPES]
FY_SHOE = [("boots", re.compile("boot", re.I)), ("slides", re.compile("slide|sandal|slipper|clog|mule|flip", re.I)),
           ("loafers", re.compile("loafer|moccasin|derby|oxford|driver", re.I))]
COLS = ["black", "white", "grey", "gray", "navy", "blue", "red", "green", "olive", "brown", "beige", "cream", "tan", "pink",
        "purple", "yellow", "orange", "khaki", "camel", "burgundy"]


def fy_type(p):   # index.html fyType
    t = p.get("title") or ""
    if p.get("cat") == "Shoes":
        for a, r in FY_SHOE:
            if r.search(t): return a
        return "sneakers"
    for a, r in FY_TYPES:
        if r.search(t): return a
    return (p.get("cat") or "other").lower()


def fy_col(p):    # index.html fyCol
    t = (p.get("title") or "").lower()
    for c in COLS:
        if c in t: return "grey" if c == "gray" else c
    return ""


def h32(s):       # index.html rkH (FNV-1a), ids are ASCII
    h = 0x811c9dc5
    for ch in str(s).encode(): h = ((h ^ ch) * 0x01000193) & 0xffffffff
    return h / 4294967296.0


def pop(p): return p["views"] + p["views7"]


def smart_pop(items, day, sold=frozenset(), explore=True):
    """index.html pcSmartPop + rkPrep, line for line."""
    bs, bn, tot = collections.defaultdict(float), collections.Counter(), 0.0
    base = {}
    for p in items:
        h = p["views"] + 0.05 * max(0, p["viewsAll"] - p["views"]); b = p.get("brand") or "?"
        bs[b] += h; bn[b] += 1; tot += h
        s = (math.log1p(pop(p)) + 0.02 * math.log1p(p["favs"]) + 0.01 * math.log1p(p["viewsAll"]) + 0.001 * p.get("best", 0)
             + (h32(p["id"] + "|" + str(day)) - .5) * 0.02)
        if p["id"] in sold: s -= 2
        base[p["id"]] = s
    mu = tot / len(items); bp = {b: (bs[b] + 6 * mu) / (bn[b] + 6) for b in bs}
    lst = sorted(items, key=lambda p: -base[p["id"]])
    head, tail, out = lst[:200], lst[200:], []
    dk = lambda p: (p.get("brand") or "?") + "|" + fy_type(p) + "|" + fy_col(p)
    while head:
        rb, rt, rd = collections.Counter(), collections.Counter(), set()
        for j in range(max(0, len(out) - 24), len(out)):
            q = out[j]; rd.add(dk(q))
            if j >= len(out) - 6: rb[q.get("brand") or "?"] += 1
            if j >= len(out) - 3: rt[fy_type(q)] += 1
        bi, bv = 0, -1e9
        for i, p in enumerate(head[:40]):
            v = base[p["id"]] - 0.2 * rb[p.get("brand") or "?"] - 0.05 * rt[fy_type(p)] - (0.3 if dk(p) in rd else 0)
            if v > bv: bv, bi = v, i
        out.append(head.pop(bi))
    out += tail
    if explore and len(out) >= 120:
        cold = [p for p in out if not p["viewsAll"] > 0 and p.get("img") and p["id"] not in sold]
        if len(cold) >= 8:
            ps = sorted(bp.get(p.get("brand") or "?", 0) for p in cold); thr = ps[int(len(ps) * 0.6)]
            pick = sorted([p for p in cold if bp.get(p.get("brand") or "?", 0) >= thr], key=lambda p: h32(p["id"] + "#" + str(day)))[:8]
            ids = {p["id"] for p in pick}; out = [p for p in out if p["id"] not in ids]
            for k, p in enumerate(pick): out.insert(23 + k * 12, p)
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--root", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    a = ap.parse_args()
    html = open(os.path.join(a.root, "index.html"), encoding="utf-8").read()
    tag = '<script type="application/json" id="pc-catalog">'; i = html.find(tag)
    cat = json.loads(html[i + len(tag):html.find("</script>", i)])
    b0 = html.find("const PC_BEST"); best = set(re.findall(r'"(\d+)"', html[b0:html.find("]);", b0)]))
    S = json.load(open(os.path.join(a.root, "data/stats.json")))["p"]
    LH = json.load(open(os.path.join(a.root, "data/link_health.json")))
    dead = set(map(str, LH.get("dead", []))); sold = frozenset(map(str, LH.get("sold_out", [])))
    items, truth = [], {}
    for p in cat:
        if p["id"] in dead: continue   # the site drops them too
        va, v30, v7, f = (S.get(p["id"]) or [0, 0, 0, 0])[:4]
        recent, older = v30 - v7, va - v30            # days 8-30, and before
        q = dict(p, views=recent, views7=recent * 7 / 23, viewsAll=recent + older,
                 favs=round(f * (recent + older) / va) if va else 0, best=1 if p["id"] in best else 0)
        items.append(q); truth[p["id"]] = v7
    rel_sorted = sorted(truth.values(), reverse=True)

    def ndcg(order, k):
        disc = [1 / math.log2(r + 2) for r in range(k)]
        return sum(truth[p["id"]] * d for p, d in zip(order[:k], disc)) / sum(v * d for v, d in zip(rel_sorted[:k], disc))

    def auc(order, outside):
        r = [p for p in order if p["id"] in outside]
        n_pos = sum(1 for p in r if truth[p["id"]] > 0); n_neg = len(r) - n_pos; above, seen_neg = 0, 0
        for p in reversed(r):   # count negatives below each positive
            if truth[p["id"]] > 0: above += seen_neg
            else: seen_neg += 1
        return above / max(1, n_pos * n_neg)

    def side(order):
        b = [p.get("brand") or "?" for p in order[:48]]; run = mr = 1
        for x, y in zip(b, b[1:]): run = run + 1 if x == y else 1; mr = max(mr, run)
        ks = [(p.get("brand") or "?") + "|" + fy_type(p) + "|" + fy_col(p) for p in order[:48]]
        top = collections.Counter(b).most_common(1)[0]
        return "brands48 %d  top brand %d (%s)  run %d  dup48 %d" % (len(set(b)), top[1], top[0], mr, len(ks) - len(set(ks)))

    old = sorted(items, key=lambda p: (-pop(p), -p["favs"], -p["viewsAll"], -p["best"]))
    outside = {p["id"] for p in old[300:]}
    day0 = 20400
    rows = [("OLD views (live popScore)", [old] * 7)]
    rows.append(("NEW variety, no explore", [smart_pop(items, d, sold, explore=False) for d in range(day0, day0 + 7)]))
    rows.append(("NEW full (variety+explore)", [smart_pop(items, d, sold) for d in range(day0, day0 + 7)]))
    for name, orders in rows:
        nd = [sum(ndcg(o, k) for o in orders) / len(orders) for k in (24, 48, 200)]
        new = {p["id"] for o in orders for p in o[:200] if p["viewsAll"] == 0}
        print("%-28s NDCG@24 %.3f @48 %.3f @200 %.3f  outside AUC %.3f  %s  new/week %d"
              % (name, nd[0], nd[1], nd[2], auc(orders[0], outside), side(orders[0]), len(new)))


if __name__ == "__main__":
    main()
