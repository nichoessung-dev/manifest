#!/usr/bin/env python3
"""Aggregate real product views + favourites from Supabase into data/stats.json.

Used by the site's "Most popular" sort (ranks by real recent views) and the /admin dashboard.
Runs in GitHub Actions (.github/workflows/stats.yml) with the SUPABASE_SERVICE_KEY secret.
Only aggregate counts are written -- no user ids or personal data.
"""
import datetime, json, os, urllib.request, collections

SUPA = "https://uptpghuduqjqmrxwatbm.supabase.co"
KEY = os.environ["SUPABASE_SERVICE_KEY"]
PAGE = 1000

def fetch_all(path):
    rows, start = [], 0
    while True:
        req = urllib.request.Request(f"{SUPA}/rest/v1/{path}", headers={
            "apikey": KEY, "Authorization": "Bearer " + KEY, "Range-Unit": "items", "Range": f"{start}-{start + PAGE - 1}"})
        chunk = json.load(urllib.request.urlopen(req, timeout=60))
        rows += chunk
        if len(chunk) < PAGE: return rows
        start += PAGE

def parse_ts(s):
    try: return datetime.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception: return None

def main():
    now = datetime.datetime.now(datetime.timezone.utc)
    d7, d30 = now - datetime.timedelta(days=7), now - datetime.timedelta(days=30)
    views = fetch_all("product_views?select=product_id,viewed_at,user_id&order=viewed_at.asc")
    favs = fetch_all("favorites?select=product_id")
    per = collections.defaultdict(lambda: [0, 0, 0, 0])       # [all, 30d, 7d, favourites]
    daily = collections.Counter(); users30 = set()
    for v in views:
        pid = str(v.get("product_id") or "")
        if not pid: continue
        t = parse_ts(v.get("viewed_at"))
        per[pid][0] += 1
        if t and t >= d30:
            per[pid][1] += 1; daily[t.date().isoformat()] += 1
            if v.get("user_id"): users30.add(v["user_id"])
        if t and t >= d7: per[pid][2] += 1
    for f in favs:
        pid = str(f.get("product_id") or "")
        if pid: per[pid][3] += 1
    days = [(now - datetime.timedelta(days=i)).date().isoformat() for i in range(29, -1, -1)]
    out = {
        "generated": now.replace(microsecond=0).isoformat(),
        "totals": {"views_all": len(views), "views_30d": sum(p[1] for p in per.values()), "views_7d": sum(p[2] for p in per.values()),
                   "favourites": len(favs), "products_viewed": sum(1 for p in per.values() if p[0]), "signed_in_viewers_30d": len(users30)},
        "daily": [[d, daily.get(d, 0)] for d in days],
        "p": {pid: v for pid, v in sorted(per.items())},
    }
    os.makedirs("data", exist_ok=True)
    new = json.dumps(out, separators=(",", ":"))
    old = open("data/stats.json").read() if os.path.exists("data/stats.json") else ""
    # don't churn commits when only the timestamp changed
    strip = lambda s: s.split(',"totals"', 1)[-1]
    if strip(old) == strip(new):
        print("stats unchanged"); return
    open("data/stats.json", "w").write(new)
    print("stats written:", out["totals"])

if __name__ == "__main__":
    main()
