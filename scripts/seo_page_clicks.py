#!/usr/bin/env python3
"""Which pages search visitors buy from, for SEO decisions (22 Nov 2026). Writes data/seo_page_clicks.json.

Buy clicks (table buy_clicks) of the last DAYS days, grouped by the page the click was made on (the "/app" prefix the
catalogue app adds is dropped, so an app hub and its server page count together) and by the visit source bucket
(ref "~google" and so on, the first page of the visit). Plus product page views from Google per find (table
product_page_views, source "google"). Aggregate counts only: no ids of people, no addresses, nothing personal.

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


def main():
    now = datetime.datetime.now(datetime.timezone.utc)
    since = (now - datetime.timedelta(days=DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = fetch_all("buy_clicks?select=page,ref,created_at&created_at=gte." + since + "&order=created_at.asc")
    per = collections.defaultdict(collections.Counter)
    for r in rows:
        per[norm(r.get("page"))][bucket(r.get("ref") or "")] += 1
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
           "product_google_buy_clicks": sorted(([k, v] for k, v in prod_clicks.items() if v), key=lambda x: -x[1])[:3000]}
    json.dump(out, open(OUT, "w"), separators=(",", ":"))
    print("written", OUT, len(rows), "clicks,", len(pages), "pages,", len(out["product_google_views"]), "finds with Google views")


if __name__ == "__main__":
    main()
