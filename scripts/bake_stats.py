#!/usr/bin/env python3
"""Aggregate real product views + favourites from Supabase into data/stats.json.

Used by the site's "Most popular" sort (ranks by real recent views) and the /admin dashboard.
Runs in GitHub Actions (.github/workflows/stats.yml) with the SUPABASE_SERVICE_KEY secret.
Only aggregate counts are written -- no user ids or personal data.
"""
import datetime, json, os, re, urllib.request, collections

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

def link_reports():
    """Visitors' "Report broken link" clicks (table link_reports, insert-only for visitors): finds with reports, most first.
    Empty when the table does not exist yet (scripts/link_reports.sql has not been run)."""
    try: rows = fetch_all("link_reports?select=product_id,created_at&order=created_at.desc")
    except Exception as e: print("link reports not read:", str(e)[:80]); return []
    agg = {}
    for r in rows:
        pid = str(r.get("product_id") or "")
        if not pid: continue
        n, last = agg.get(pid, (0, r.get("created_at")))
        agg[pid] = (n + 1, last)
    return sorted([[pid, n, (last or "")[:10]] for pid, (n, last) in agg.items()], key=lambda x: (-x[1], x[2]))[:200]


def page_kind(path):
    """Which kind of page a buy click came from (buy_clicks.page holds the path)."""
    p = path or ""
    if p.startswith("/product/"): return "product page"
    if p in ("", "/"): return "homepage"
    if re.match(r"^/[a-z]+-spreadsheet(/|$)", p): return "agent and style hubs"
    if re.match(r"^/(brand|category|best|old-money|brands)(/|$)", p): return "brand and category hubs"
    if p.startswith("/links"): return "links page"
    if p.startswith(("/guides", "/tools", "/how-to-order")): return "guides and tools"
    return "other"

def buy_clicks():
    """"Buy" clicks on agent links (table buy_clicks, written by functions/api/click.js): last 30 days by agent, country,
    day, item, page kind and visit source. Counts only; the table holds no ids or addresses. Member referral codes are
    counted as "member", never published (this file is public). Sign-up links (no item) are kept apart from item clicks."""
    now = datetime.datetime.now(datetime.timezone.utc); since = (now - datetime.timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    try: rows = fetch_all("buy_clicks?select=created_at,agent,item_id,country,ref,page&created_at=gte." + since + "&order=created_at.asc")
    except Exception as e: print("buy clicks not read:", str(e)[:80]); return {}
    ag, co, dy, it, pg, src = (collections.Counter() for _ in range(6))
    kinds = collections.defaultdict(lambda: [0, 0])                  # agent -> [item clicks, sign-up link clicks]
    dy_item, dy_signup = collections.Counter(), collections.Counter()
    for r in rows:
        t = parse_ts(r.get("created_at"))
        if not t: continue
        a = r.get("agent") or "?"; d = t.date().isoformat(); is_item = bool(r.get("item_id"))
        ag[a] += 1; co[r.get("country") or "??"] += 1; dy[d] += 1
        kinds[a][0 if is_item else 1] += 1; (dy_item if is_item else dy_signup)[d] += 1
        if is_item: it[r["item_id"]] += 1
        pg[page_kind(r.get("page"))] += 1
        ref = r.get("ref") or ""
        src[ref[1:].split(".")[0] if ref.startswith("~") else ("member" if ref else "not recorded")] += 1
    days = [(now - datetime.timedelta(days=k)).date().isoformat() for k in range(29, -1, -1)]
    return {"total": len(rows), "agents": ag.most_common(), "countries": co.most_common(25), "days": days,
            "per_day": [dy.get(d, 0) for d in days], "items": it.most_common(20),
            "kinds": {a: {"item": v[0], "signup": v[1]} for a, v in kinds.items()},
            "per_day_item": [dy_item.get(d, 0) for d in days], "per_day_signup": [dy_signup.get(d, 0) for d in days],
            "pages": pg.most_common(), "sources": src.most_common(15)}


def dashboard():
    """data/dashboard.json for the private /stats page: daily and monthly aggregates only (no user ids, no addresses).
    Active users = distinct signed-in members who opened a find that day / month; guests carry no id, so they show only in views."""
    now = datetime.datetime.now(datetime.timezone.utc)
    views = fetch_all("product_views?select=viewed_at,user_id,brand&order=viewed_at.asc")
    try: profiles = fetch_all("profiles?select=created_at&order=created_at.asc")
    except Exception as e: print("profiles not read:", e); profiles = []
    vday, uday, umonth, vmonth = collections.Counter(), collections.defaultdict(set), collections.defaultdict(set), collections.Counter()
    brands7, d7, d30, d60 = collections.Counter(), now - datetime.timedelta(days=7), now - datetime.timedelta(days=30), now - datetime.timedelta(days=60)
    u7, u30, u1, v30, vprev30 = set(), set(), set(), 0, 0
    for v in views:
        t = parse_ts(v.get("viewed_at"))
        if not t: continue
        d, m, u = t.date().isoformat(), t.strftime("%Y-%m"), v.get("user_id")
        vday[d] += 1; vmonth[m] += 1
        if t >= d30: v30 += 1
        elif t >= d60: vprev30 += 1
        if u:
            uday[d].add(u); umonth[m].add(u)
            if t >= d30: u30.add(u)
            if t >= d7: u7.add(u)
            if t >= now - datetime.timedelta(days=1): u1.add(u)
        if t >= d7 and v.get("brand"): brands7[v["brand"]] += 1
    sday, smonth = collections.Counter(), collections.Counter()
    for p in profiles:
        t = parse_ts(p.get("created_at"))
        if t: sday[t.date().isoformat()] += 1; smonth[t.strftime("%Y-%m")] += 1
    first = min([d for d in list(vday) + list(sday)] or [now.date().isoformat()])
    days, d = [], datetime.date.fromisoformat(first)
    while d <= now.date(): days.append(d.isoformat()); d += datetime.timedelta(days=1)
    total, cum = 0, []
    for d in days: total += sday.get(d, 0); cum.append(total)
    months = sorted(set(vmonth) | set(smonth))
    out = {
        "generated": now.replace(microsecond=0).isoformat(),
        "days": days, "views": [vday.get(d, 0) for d in days], "active": [len(uday.get(d, ())) for d in days],
        "signups": [sday.get(d, 0) for d in days], "members": cum,
        "months": [{"m": m, "views": vmonth.get(m, 0), "active": len(umonth.get(m, ())), "signups": smonth.get(m, 0)} for m in months],
        "dau": len(u1), "wau": len(u7), "mau": len(u30), "views_30d": v30, "views_prev_30d": vprev30,
        "top_brands_7d": brands7.most_common(8),
        "reports": link_reports(),
        "buy_clicks": buy_clicks(),
    }
    new = json.dumps(out, separators=(",", ":"))
    old = open("data/dashboard.json").read() if os.path.exists("data/dashboard.json") else ""
    strip = lambda s: s.split(',"days"', 1)[-1]
    if strip(old) == strip(new): print("dashboard unchanged"); return
    open("data/dashboard.json", "w").write(new)
    print("dashboard written: %d days, mau %d, wau %d" % (len(days), out["mau"], out["wau"]))

if __name__ == "__main__":
    main()
    try: dashboard()
    except Exception as e: print("dashboard not made:", e)
