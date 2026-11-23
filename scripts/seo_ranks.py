#!/usr/bin/env python3
"""Where puroclassico.com ranks on Google for the searches in data/seo_keywords.json, US and UK, via Serper.

Writes data/seo_ranks.json: per search and market the position of our first result (top 100 where the budget allows),
the ranking URL, every one of our URLs on the page, and the top 3 results (the competitors). Also an index check:
site: searches and a random sample of sitemap URLs looked up one by one, to estimate how many pages Google has indexed.

Runs in GitHub Actions (.github/workflows/seo-ranks.yml) with the SERPER_API_KEY secret. Stops before --budget
credits (counted from the credits Serper reports per request).

  python scripts/seo_ranks.py [--budget 600] [--sample 60]

A focused check (23 Nov 2026): other searches, other markets, its own output file, no index check. The top results are
kept with their snippets (--top), to see what ranks and why. Example, the spreadsheet searches in the ten countries
with the most buy clicks, looked up to the top 30:

  python scripts/seo_ranks.py --keywords data/seo_keywords_head.json --markets us,gb,de,se,pl,ca,no,nl,dk,au \
      --depth 3 --top 5 --no-index --out data/seo_ranks_markets.json
"""
import argparse, json, os, random, re, sys, time, urllib.request, urllib.error
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "seo_ranks.json")
KW = os.path.join(ROOT, "data", "seo_keywords.json")
SITE = "https://www.puroclassico.com"
MARKETS = [("us", "en"), ("gb", "en")]
# Google's interface language per market for --markets (the language most searchers there use Google in).
HL = {"us": "en", "gb": "en", "ca": "en", "au": "en", "ie": "en", "nz": "en", "za": "en", "de": "de", "at": "de", "ch": "de",
      "se": "sv", "no": "no", "dk": "da", "fi": "fi", "nl": "nl", "be": "nl", "pl": "pl", "cz": "cs", "fr": "fr", "it": "it",
      "es": "es", "pt": "pt", "ro": "ro"}
DEEP_GROUPS = ("brand", "head", "agent", "guide")       # searched past page 1 when we are not on it (paged mode)
UA = {"User-Agent": "Mozilla/5.0 (compatible; PuroClassicoSEO/1.0)"}


class Budget(Exception):
    pass


class Serper:
    def __init__(self, key, budget):
        self.key, self.budget, self.used, self.calls = key, budget, 0, 0

    def search(self, q, gl, hl, num=10, page=1, cost_guess=1):
        if self.used + cost_guess > self.budget:
            raise Budget()
        body = {"q": q, "gl": gl, "hl": hl, "num": num}
        if page > 1:
            body["page"] = page
        req = urllib.request.Request("https://google.serper.dev/search", data=json.dumps(body).encode(),
                                     headers={"X-API-KEY": self.key, "Content-Type": "application/json"})
        last = None
        for k in range(4):
            try:
                d = json.load(urllib.request.urlopen(req, timeout=40))
                self.calls += 1
                self.used += int(d.get("credits") or cost_guess)
                return d
            except urllib.error.HTTPError as e:
                last = e
                if e.code in (400, 401, 403):
                    raise
                time.sleep(2 + 3 * k)
            except Exception as e:
                last = e
                time.sleep(2 + 3 * k)
        raise last


def ours(link):
    try:
        host = link.split("/")[2].lower()
    except IndexError:
        return False
    return host == "puroclassico.com" or host.endswith(".puroclassico.com")


def host_of(link):
    try:
        return link.split("/")[2].lower().removeprefix("www.")
    except IndexError:
        return ""


def read_results(d, offset):
    """[(absolute position, link, title)] of the organic results of one response (offset: results on earlier pages)."""
    return [(offset + i + 1, r.get("link") or "", r.get("title") or "") for i, r in enumerate(d.get("organic") or [])]


def features(d):
    f = []
    for k, name in (("answerBox", "answer box"), ("knowledgeGraph", "knowledge panel"), ("peopleAlsoAsk", "people also ask"),
                    ("topStories", "top stories"), ("images", "images"), ("videos", "videos"), ("shopping", "shopping")):
        if d.get(k):
            f.append(name)
    return f


TOP = 3   # results kept per search with title (and, from 4 up, snippet and date): --top


def rank(s, q, gl, hl, mode, depth, prev=None):
    """One search in one market: our position (None = not in the results we read), how deep we looked, results.
    prev: an earlier result for the same search, continued from the next page (paged mode)."""
    res = [tuple(x) for x in (prev or {}).get("_res", [])]
    snip = dict((prev or {}).get("_snip", {}))
    seen_depth, feats = (prev or {}).get("checked_top", 0), (prev or {}).get("features", [])
    if mode["num100"]:
        d = s.search(q, gl, hl, num=100, cost_guess=mode["c100"])
        res = read_results(d, 0); seen_depth = max(len(res), 10); feats = features(d)
    else:
        for page in range(seen_depth // 10 + 1, depth + 1):
            d = s.search(q, gl, hl, num=10, page=page)
            if page == 1:
                feats = features(d)
            got = read_results(d, (page - 1) * 10)
            for i, r in enumerate(d.get("organic") or []):
                snip[str((page - 1) * 10 + i + 1)] = [(r.get("snippet") or "")[:220], r.get("date") or ""]
            res += got; seen_depth = page * 10
            if any(ours(l) for _, l, _ in got) or len(got) < 8:
                break
    mine = [(p, l, t) for p, l, t in res if ours(l)]
    top = [{"pos": p, "domain": host_of(l), "url": l, "title": t} for p, l, t in res[:3]]
    out = {"pos": mine[0][0] if mine else None, "url": mine[0][1] if mine else None, "title": mine[0][2] if mine else None,
           "all_ours": [[p, l] for p, l, _ in mine][:10], "checked_top": seen_depth, "top3": top, "features": feats,
           "domains_top10": [host_of(l) for _, l, _ in res[:10]], "_res": [list(x) for x in res], "_snip": snip}
    if TOP > 3:
        out["top"] = [{"pos": p, "domain": host_of(l), "url": l, "title": t, "snippet": (snip.get(str(p)) or ["", ""])[0],
                       "date": (snip.get(str(p)) or ["", ""])[1]} for p, l, t in res[:TOP]]
    return out


def sitemap_urls():
    urls = []
    for name in ("sitemap-pages.xml", "sitemap-products.xml"):
        try:
            t = urllib.request.urlopen(urllib.request.Request(SITE + "/" + name, headers=UA), timeout=60).read().decode()
            urls += re.findall(r"<loc>([^<]+)</loc>", t)
        except Exception as e:
            print("sitemap", name, "not read:", e)
    return urls


def kind(u):
    p = u.split("puroclassico.com", 1)[-1]
    if p.startswith("/product/"): return "product"
    if p.startswith("/brand/"): return "brand"
    if p.startswith("/best/"): return "best"
    if p.startswith("/category/"): return "category"
    if p.startswith(("/guides", "/tools", "/how-to-order")): return "guide"
    if re.match(r"^/[a-z0-9]+-spreadsheet", p): return "hub"
    return "other"


def same_url(a, b):
    n = lambda u: re.sub(r"^https?://(www\.)?", "", (u or "").split("#")[0].split("?")[0]).rstrip("/").lower()
    return n(a) == n(b)


def page_name(u):
    """The words a page is known by in Google: its <title> up to the colon or ' Rep' (product pages)."""
    try:
        t = urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=40).read().decode("utf-8", "replace")
    except Exception:
        return None
    m = re.search(r"<title>(.*?)</title>", t, re.S)
    if not m:
        return None
    import html as H
    t = H.unescape(m.group(1)).strip()
    t = t.split(" | ")[0]
    if "/product/" in u:
        t = re.split(r" \(| Rep[:| ]", t)[0]
    else:
        t = t.split(":")[0]
    return t.strip()[:80] or None


def index_by_name(s, out, n_product, n_other):
    """Second index check: search site:puroclassico.com "<page name>" and look for the exact URL. The site:<full URL>
    lookups above miss pages that clearly rank, so this one is used for the estimate. Control pages that rank for a
    tracked search are checked the same way, to show the method finds pages that are indexed."""
    old = out["index"].get("sample") or []
    prod = [x for x in old if x["kind"] == "product"][:n_product]
    other = [x for x in old if x["kind"] != "product"]
    rnd = random.Random(7); rnd.shuffle(other); other = other[:n_other]
    ranked = []
    for q, v in out.get("ranks", {}).items():
        for m in ("us", "gb"):
            u = (v.get(m) or {}).get("url")
            if u and u not in ranked: ranked.append(u)
    controls = [{"kind": "control", "url": u} for u in ranked[:5]]
    res = []
    for x in controls + [{"kind": y["kind"], "url": y["url"]} for y in prod + other]:
        name = page_name(x["url"])
        if not name:
            res.append({**x, "name": None, "indexed": None}); continue
        d = s.search('site:puroclassico.com "%s"' % name.replace('"', ""), "us", "en", num=10)
        links = [l for _, l, _ in read_results(d, 0)]
        res.append({**x, "name": name, "indexed": any(same_url(l, x["url"]) for l in links), "returned": links[:10]})
    out["index"]["sample_by_name"] = res


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=int, default=600)
    ap.add_argument("--sample", type=int, default=60, help="sitemap URLs checked one by one for the index estimate")
    ap.add_argument("--index-by-name", default="", help="P,O: only the second index check on P product and O other pages "
                    "of the earlier sample, added to data/seo_ranks.json")
    ap.add_argument("--keywords", default=KW, help="searches to check (same shape as data/seo_keywords.json)")
    ap.add_argument("--markets", default="", help="comma list of Google markets (us,gb,de,...); default us,gb")
    ap.add_argument("--out", default=OUT, help="output file (default data/seo_ranks.json)")
    ap.add_argument("--depth", type=int, default=5, help="pages of 10 looked through when we are not on page 1 (deep groups)")
    ap.add_argument("--deep-groups", default=",".join(DEEP_GROUPS), help="groups searched past page 1; 'all' for every group")
    ap.add_argument("--top", type=int, default=3, help="results kept per search with title, snippet and date")
    ap.add_argument("--no-index", action="store_true", help="skip the index check")
    a = ap.parse_args(argv)
    global TOP
    TOP = max(3, a.top)
    markets = [(m.strip(), HL.get(m.strip(), "en")) for m in a.markets.split(",") if m.strip()] or MARKETS
    out_path = os.path.join(ROOT, a.out) if not os.path.isabs(a.out) else a.out
    key = os.environ.get("SERPER_API_KEY") or sys.exit("no SERPER_API_KEY")
    s = Serper(key, a.budget - 5)
    if a.index_by_name:
        out = json.load(open(OUT))
        p, o = (int(x) for x in a.index_by_name.split(","))
        try:
            index_by_name(s, out, p, o)
        except Budget:
            out["notes"].append("budget reached during the second index check")
        out["credits_used"] = out.get("credits_used", 0) + s.used
        out["requests"] = out.get("requests", 0) + s.calls
        out["index_by_name_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        json.dump(out, open(OUT, "w"), indent=1, ensure_ascii=False)
        r = out["index"]["sample_by_name"]
        print("index by name: %d checked, %d found, %d credits this run" % (len(r), sum(1 for x in r if x.get("indexed")), s.used))
        return
    kw_path = os.path.join(ROOT, a.keywords) if not os.path.isabs(a.keywords) else a.keywords
    kw = {g: v for g, v in json.load(open(kw_path)).items() if not g.startswith("_")}
    queries = [(g, q) for g, qs in kw.items() for q in qs]
    deep = set(kw) if a.deep_groups == "all" else set(x.strip() for x in a.deep_groups.split(",") if x.strip())
    out = {"generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "markets": [m for m, _ in markets],
           "keywords": os.path.relpath(kw_path, ROOT), "ranks": {}, "index": {}, "notes": []}

    # 1. Does num=100 still return 100 results, and what does it cost?
    probe = s.search("weidian spreadsheet", "us", "en", num=100, cost_guess=2)
    n100, c100 = len(probe.get("organic") or []), int(probe.get("credits") or 2)
    reserve = 0 if a.no_index else a.sample + 12
    mode = {"num100": n100 >= 40, "c100": c100, "probe_results": n100}
    if mode["num100"] and len(queries) * len(markets) * c100 + reserve > s.budget:
        mode["num100_markets"] = ["us"]
    out["mode"] = mode
    print("probe: num=100 gave %d results for %d credits -> %s" % (n100, c100, "top 100 per search" if mode["num100"] else "pages of 10"))

    # 2. Rankings. Page 1 everywhere first, then deeper where we are missing (paged mode), most important groups first.
    try:
        for g, q in queries:
            for gl, hl in markets:
                m = dict(mode)
                if mode["num100"] and gl not in mode.get("num100_markets", [gl]):
                    m["num100"] = False
                r = rank(s, q, gl, hl, m, depth=1)
                r["group"] = g
                out["ranks"].setdefault(q, {"group": g})[gl] = r
        if not mode["num100"]:
            for depth in sorted(set(d for d in (3, 5) if d <= a.depth) | ({a.depth} if a.depth > 1 else set())):
                for g, q in queries:
                    if g not in deep: continue
                    for gl, hl in markets:
                        r0 = out["ranks"][q][gl]
                        if r0["pos"] or r0["checked_top"] >= depth * 10 or len(r0["_res"]) < r0["checked_top"] - 2: continue
                        if s.used + (depth - r0["checked_top"] // 10) + reserve > s.budget: continue
                        r = rank(s, q, gl, hl, mode, depth=depth, prev=r0); r["group"] = g
                        out["ranks"][q][gl] = r
    except Budget:
        out["notes"].append("budget reached during rankings")
    for v in out["ranks"].values():
        for m, r in v.items():
            if m != "group": r.pop("_res", None); r.pop("_snip", None)

    # 3. Index: site: searches, then a fixed random sample of sitemap URLs looked up one by one.
    try:
        if a.no_index:
            raise StopIteration
        for q in ("site:puroclassico.com", "site:fb.puroclassico.com", "site:puroclassico.com -inurl:www",
                  "site:puroclassico.com/product", "site:puroclassico.com/brand", "site:puroclassico.com/best"):
            d = s.search(q, "us", "en", num=100 if mode["num100"] else 10, cost_guess=c100 if mode["num100"] else 1)
            res = read_results(d, 0)
            out["index"].setdefault("site", {})[q] = {"results": len(res), "urls": [l for _, l, _ in res][:100]}
        urls = sitemap_urls()
        out["index"]["sitemap_urls"] = len(urls)
        by = {}
        for u in urls: by.setdefault(kind(u), []).append(u)
        out["index"]["sitemap_by_kind"] = {k: len(v) for k, v in by.items()}
        rnd = random.Random(20261122)
        want = {"product": 30, "brand": 8, "best": 6, "category": 4, "hub": 6, "guide": 6}
        tot = sum(want.values()); sample = []
        for k, n in want.items():
            n = max(1, round(n * a.sample / tot)); pool = by.get(k, [])
            sample += [(k, u) for u in rnd.sample(pool, min(n, len(pool)))]
        checked = []
        for k, u in sample:
            d = s.search("site:" + u.split("://", 1)[1], "us", "en", num=10)
            hit = any((l.rstrip("/") == u.rstrip("/")) or l.split("?")[0].rstrip("/") == u.rstrip("/") for _, l, _ in read_results(d, 0))
            checked.append({"kind": k, "url": u, "indexed": hit})
        out["index"]["sample"] = checked
    except Budget:
        out["notes"].append("budget reached during the index check")
    except StopIteration:
        out.pop("index", None)

    out["credits_used"], out["requests"] = s.used, s.calls
    json.dump(out, open(out_path, "w"), indent=1, ensure_ascii=False)
    found = sum(1 for v in out["ranks"].values() for m, r in v.items() if m != "group" and r.get("pos"))
    print("written %s: %d searches, %d positions found, %d credits, %d requests" % (out_path, len(out["ranks"]), found, s.used, s.calls))


if __name__ == "__main__":
    main()
