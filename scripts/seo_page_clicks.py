#!/usr/bin/env python3
"""Which pages search visitors buy from, for SEO decisions (22 Nov 2026). Writes data/seo_page_clicks.json.

Buy clicks (table buy_clicks) of the last DAYS days, grouped by the page the click was made on (the "/app" prefix the
catalogue app adds is dropped, so an app hub and its server page count together) and by the visit source bucket
(ref "~google" and so on, the first page of the visit). Plus product page views from Google per find (table
product_page_views, source "google"), and (23 Nov 2026) the countries of the Google buy clicks on the pages with the most
of them, to know which Google markets each page is found in, and the site searches of the last 30 days that were made
5+ times in 3+ different hours (the same floor as the dashboard's top searches in scripts/bake_stats.py), to pick model
pages from real demand. Aggregate counts only: no ids of people, no addresses, nothing personal.

Runs in GitHub Actions (.github/workflows/seo-page-clicks.yml) with the SUPABASE_SERVICE_KEY secret.
"""
import collections, datetime, json, os, re, urllib.request

SUPA = "https://uptpghuduqjqmrxwatbm.supabase.co"
KEY = os.environ["SUPABASE_SERVICE_KEY"]
DAYS = 60
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "seo_page_clicks.json")
SEARCH = {"google", "bing", "yahoo", "duckduckgo", "ecosia", "yandex", "brave"}
AI = {"chatgpt", "gemini", "perplexity", "copilot", "claude"}


def fetch_all(path):
    rows, start = [], 0
    while True:
        req = urllib.request.Request(f"{SUPA}/rest/v1/{path}", headers={
            "apikey": KEY, "Authorization": "Bearer " + KEY, "Range-Unit": "items", "Range": f"{start}-{start + 999}"})
        chunk = json.load(urllib.request.urlopen(req, timeout=90))
        rows += chunk
        if len(chunk) < 1000:
            return rows
        start += 1000


def bucket(ref):
    s = ref[1:].split(".")[0].lower() if ref.startswith("~") else ("member" if ref else "none")
    return "google" if s == "google" else "search_other" if s in SEARCH else "ai" if s in AI else "direct" if s in ("direct", "pwa") else "other"


def norm(path):
    p = (path or "").split("?")[0].split("#")[0]
    if p.startswith("/app"):
        p = p[4:] or "/"
    p = re.sub(r"/+$", "", p) or "/"
    return p.lower()


SEARCH_MIN, SEARCH_MIN_HOURS = 5, 3   # as scripts/bake_stats.py


def site_searches(since):
    """[query, times, times a find was opened, distinct days] for the searches made SEARCH_MIN+ times in SEARCH_MIN_HOURS+
    different hours since `since` (table search_log, kept 30 days), most made first. Lower-cased and trimmed."""
    try:
        rows = fetch_all("search_log?select=created_at,q,clicked&created_at=gte." + since + "&order=created_at.asc")
    except Exception as e:
        print("search log not read:", str(e)[:80]); return []
    per = {}
    for r in rows:
        q = re.sub(r"\s+", " ", str(r.get("q") or "")).strip().lower()
        if not q or len(q) > 60: continue
        x = per.setdefault(q, [0, 0, set(), set()])
        t = str(r.get("created_at") or "")
        x[0] += 1; x[1] += 1 if r.get("clicked") else 0; x[2].add(t[:13]); x[3].add(t[:10])
    keep = [[q, x[0], x[1], len(x[3])] for q, x in per.items() if x[0] >= SEARCH_MIN and len(x[2]) >= SEARCH_MIN_HOURS]
    return sorted(keep, key=lambda e: (-e[1], e[0]))[:400]


def main():
    now = datetime.datetime.now(datetime.timezone.utc)
    since = (now - datetime.timedelta(days=DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = fetch_all("buy_clicks?select=page,ref,country,created_at&created_at=gte." + since + "&order=created_at.asc")
    per = collections.defaultdict(collections.Counter)
    gc = collections.defaultdict(collections.Counter)   # Google buy clicks per page and country
    for r in rows:
        pg, b = norm(r.get("page")), bucket(r.get("ref") or "")
        per[pg][b] += 1
        if b == "google":
            gc[pg][(r.get("country") or "??").upper()[:2]] += 1
    pages = sorted(([p, dict(c), sum(c.values())] for p, c in per.items() if sum(c.values()) >= 3 and not p.startswith("/product/")),
                   key=lambda x: -x[2])
    prod_clicks = collections.Counter()
    for p, c in per.items():
        if p.startswith("/product/"):
            prod_clicks[p[9:]] += c.get("google", 0)
    day0 = (now - datetime.timedelta(days=DAYS)).date().isoformat()
    try:
        pv = fetch_all("product_page_views?select=product_id,source,views&source=eq.google&day=gte." + day0)
    except Exception as e:
        print("product page views not read:", str(e)[:80]); pv = []
    g = collections.Counter()
    for r in pv:
        g[str(r.get("product_id") or "")] += int(r.get("views") or 0)
    out = {"generated": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "days": DAYS, "clicks": len(rows),
           "about": "Buy clicks per page (min 3) by visit source; product page views from Google per find. Aggregates only.",
           "pages": pages[:1500],
           "product_google_views": sorted(([k, v] for k, v in g.items() if k and v), key=lambda x: -x[1])[:3000],
           "product_google_buy_clicks": sorted(([k, v] for k, v in prod_clicks.items() if v), key=lambda x: -x[1])[:3000],
           # Google buy clicks by country: all pages together, then the 80 pages with the most (top 12 countries each)
           "google_countries": sorted(([k, v] for k, v in sum(gc.values(), collections.Counter()).items()), key=lambda x: -x[1])[:40],
           "google_countries_by_page": [[p, sum(c.values()), c.most_common(12)]
                                        for p, c in sorted(gc.items(), key=lambda x: -sum(x[1].values()))[:80] if not p.startswith("/product/")],
           "site_searches_30d": site_searches((now - datetime.timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ"))}
    json.dump(out, open(OUT, "w"), separators=(",", ":"))
    print("written", OUT, len(rows), "clicks,", len(pages), "pages,", len(out["product_google_views"]), "finds with Google views")


if __name__ == "__main__":
    main()
