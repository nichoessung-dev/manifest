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
    """Which kind of page a buy click came from (buy_clicks.page holds the path). Since 22 Oct 2026 track.js sends
    "/app" + the page the catalogue app was loaded on; before that, app clicks show as product pages."""
    p = path or ""
    if p.startswith("/app"): return "app on " + page_kind(p[4:] or "/").replace("product page", "homepage")
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
    q = "&created_at=gte." + since + "&order=created_at.asc"
    try: rows = fetch_all("buy_clicks?select=created_at,agent,item_id,country,ref,page,campaign" + q)
    except Exception as e:                                         # no campaign column yet (OWNER_SQL.sql not run): as before
        print("buy clicks: no campaign column yet:", str(e)[:60])
        try: rows = fetch_all("buy_clicks?select=created_at,agent,item_id,country,ref,page" + q)
        except Exception as e: print("buy clicks not read:", str(e)[:80]); return {}
    ag, co, dy, it, pg, src = (collections.Counter() for _ in range(6))
    on_page = collections.Counter()                                  # item clicks made on /product/<id> itself, per id
    camp = collections.defaultdict(lambda: [0, 0])                   # (source, campaign) -> [item clicks, sign-up link clicks]
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
        s0 = ref[1:].split(".")[0] if ref.startswith("~") else ("member" if ref else "not recorded")
        src[s0] += 1
        m = re.match(r"^/product/([0-9A-Za-z_-]{1,40})$", r.get("page") or "")
        if is_item and m: on_page[m.group(1)] += 1
        # Campaign: the campaign column (since 29 Oct 2026), else what fitted in ref ("~email.news" -> news), else none.
        c = r.get("campaign") or (ref[1:].split(".", 1)[1] if ref.startswith("~") and "." in ref else "")
        if c: camp[(s0, c)][0 if is_item else 1] += 1
    days = [(now - datetime.timedelta(days=k)).date().isoformat() for k in range(29, -1, -1)]
    return {"total": len(rows), "agents": ag.most_common(), "countries": co.most_common(25), "days": days,
            "per_day": [dy.get(d, 0) for d in days], "items": it.most_common(20),
            "kinds": {a: {"item": v[0], "signup": v[1]} for a, v in kinds.items()},
            "per_day_item": [dy_item.get(d, 0) for d in days], "per_day_signup": [dy_signup.get(d, 0) for d in days],
            "pages": pg.most_common(), "sources": src.most_common(15),
            "campaigns": sorted([[s0, c, v[0], v[1]] for (s0, c), v in camp.items() if campaign_ok(c, v[0] + v[1])], key=lambda x: (-(x[2] + x[3]), x[1]))[:30],
            "_on_page": dict(on_page)}                                # used by product_views(), removed before writing


# Campaign names we put on our own links (scripts/*_drops.py, pins.py, post_short.py, newsletter.py). dashboard.json is
# public and anyone can type a utm_campaign, so another name is listed only once it has CAMPAIGN_MIN views or clicks.
CAMPAIGN_KNOWN = re.compile(r"^(drop|pin|short-[a-z0-9-]{1,20}|welcome|ordering|mycnbox|newsletter|saved|(welcome|ordering|mycnbox)-test)$")
CAMPAIGN_MIN = 5

def campaign_ok(c, n):
    return bool(c) and (bool(CAMPAIGN_KNOWN.match(c)) or n >= CAMPAIGN_MIN)

VIEWS_KEEP_DAYS = 760   # purge_product_page_views() keeps about 25 months
VIEW_RATE_MIN = 20      # a find gets a buy rate only with this many product page views in 30 days

def purge_page_views():
    """Retention for product_page_views via purge_product_page_views() (OWNER_SQL.sql). Always a dry run (count printed to
    the Actions log); deletes only when PAGE_VIEWS_PURGE=1. Never fails the bake (function missing = one printed line)."""
    def call(dry):
        req = urllib.request.Request(f"{SUPA}/rest/v1/rpc/purge_product_page_views", method="POST",
            data=json.dumps({"p_days": VIEWS_KEEP_DAYS, "p_dry": dry}).encode(),
            headers={"apikey": KEY, "Authorization": "Bearer " + KEY, "Content-Type": "application/json"})
        return json.load(urllib.request.urlopen(req, timeout=60))
    try:
        n = call(True); print(f"page view retention, dry run: {n} rows older than {VIEWS_KEEP_DAYS} days")
        if n and os.environ.get("PAGE_VIEWS_PURGE", "0") == "1":
            print("page view retention: deleted", call(False))
    except Exception as e: print("page view retention skipped:", str(e)[:80])

def product_views(clicks):
    """Server-counted /product/<id> page views (table product_page_views, functions/_lib/views.js): last 7 and 30 days,
    the 7 days before, per day, per source bucket, per campaign, and the buy rate per find (buy clicks made on that
    product page / its page views, finds with VIEW_RATE_MIN+ views only). Returns {} until the table exists and has rows."""
    now = datetime.datetime.now(datetime.timezone.utc); today = now.date()
    purge_page_views()
    since = (today - datetime.timedelta(days=60)).isoformat()
    try: rows = fetch_all("product_page_views?select=day,product_id,source,campaign,views&day=gte." + since + "&order=day.asc")
    except Exception as e: print("product page views not read:", str(e)[:80]); return {}
    if not rows: return {}
    d7, d14, d30 = (today - datetime.timedelta(days=k) for k in (6, 13, 29))   # 7 / 14 / 30 calendar days including today
    tot = {"d7": 0, "prev7": 0, "d30": 0}
    per_day, srcs, camps, per_pid = collections.Counter(), collections.defaultdict(lambda: [0, 0]), collections.Counter(), collections.Counter()
    for r in rows:
        try: d = datetime.date.fromisoformat(str(r.get("day"))[:10]); n = int(r.get("views") or 0)
        except Exception: continue
        if n <= 0 or d > today: continue
        s0, c, pid = r.get("source") or "other", r.get("campaign") or "", str(r.get("product_id") or "")
        if d >= d7: tot["d7"] += n; srcs[s0][0] += n
        elif d >= d14: tot["prev7"] += n
        if d >= d30:
            tot["d30"] += n; srcs[s0][1] += n; per_day[d.isoformat()] += n
            if pid: per_pid[pid] += n
            if c: camps[(s0, c)] += n
    days = [(today - datetime.timedelta(days=k)).isoformat() for k in range(29, -1, -1)]
    on_page = (clicks or {}).get("_on_page") or {}
    finds = []
    for pid, v in per_pid.items():
        if v >= VIEW_RATE_MIN:
            b = int(on_page.get(pid, 0)); finds.append([pid, v, b, round(b / v, 4)])
    buys = sum(int(on_page.get(pid, 0)) for pid in per_pid)
    return {"min_views": VIEW_RATE_MIN, "totals": tot, "days": days, "per_day": [per_day.get(d, 0) for d in days],
            "sources": sorted([[s0, v[0], v[1]] for s0, v in srcs.items()], key=lambda x: (-x[2], -x[1], x[0])),
            "campaigns": sorted([[s0, c, n] for (s0, c), n in camps.items() if campaign_ok(c, n)], key=lambda x: (-x[2], x[1]))[:30],
            "buys_on_page_30d": buys, "rate_30d": round(buys / tot["d30"], 4) if tot["d30"] else 0,
            "finds": sorted(finds, key=lambda x: (-x[1], x[0]))[:150]}


SEARCH_MIN = 5   # a query is listed only when seen this many times in the week: dashboard.json is public, rare queries are not
SEARCH_MIN_HOURS = 3   # ...and in at least this many different hours (created_at is rounded to the hour), so a burst from one script is not listed
SEARCH_KEEP_DAYS = 30  # privacy.html promises search rows are deleted after 30 days

def purge_searches():
    """Retention for search_log (privacy.html: deleted after 30 days), via purge_search_log() from OWNER_SQL.sql.
    Dry run first (counts only, printed to the Actions log), then the real delete. Set SEARCH_PURGE=0 to stop deleting.
    Never fails the bake: a missing function (SQL not run yet) just prints a line."""
    def call(dry):
        req = urllib.request.Request(f"{SUPA}/rest/v1/rpc/purge_search_log", method="POST",
            data=json.dumps({"p_days": SEARCH_KEEP_DAYS, "p_dry": dry}).encode(),
            headers={"apikey": KEY, "Authorization": "Bearer " + KEY, "Content-Type": "application/json"})
        return json.load(urllib.request.urlopen(req, timeout=60))
    try:
        n = call(True); print(f"search log retention, dry run: {n} rows older than {SEARCH_KEEP_DAYS} days")
        if n and os.environ.get("SEARCH_PURGE", "1") != "0":
            print("search log retention: deleted", call(False))
    except Exception as e: print("search log retention skipped:", str(e)[:80])

def searches():
    """Site searches (table search_log, written by functions/api/search.js): last 7 days against the 7 before.
    Totals, zero-result share, opened-a-find share, and the queries seen SEARCH_MIN+ times in SEARCH_MIN_HOURS+ hours (top and zero-result).
    Returns {} when the table does not exist yet (OWNER_SQL.sql not run) or cannot be read."""
    now = datetime.datetime.now(datetime.timezone.utc)
    d7, d14 = now - datetime.timedelta(days=7), now - datetime.timedelta(days=14)
    purge_searches()
    try: rows = fetch_all("search_log?select=created_at,q,results,clicked,page&created_at=gte." + d14.strftime("%Y-%m-%dT%H:%M:%SZ") + "&order=created_at.asc")
    except Exception as e: print("search log not read:", str(e)[:80]); return {}
    def totals(rs):
        n = len(rs); z = sum(1 for r in rs if not r.get("results")); o = sum(1 for r in rs if r.get("clicked"))
        return {"n": n, "zero": z, "opened": o}
    week, prev = [], []
    for r in rows:
        t = parse_ts(r.get("created_at"))
        if not t or not r.get("q"): continue
        (week if t >= d7 else prev if t >= d14 else []).append(r)
    per = {}
    for r in week:
        x = per.setdefault(r["q"], {"n": 0, "zero": 0, "opened": 0, "results": 0, "hours": set()})
        x["n"] += 1; x["hours"].add(str(r.get("created_at"))[:13]); x["opened"] += 1 if r.get("clicked") else 0
        if not r.get("results"): x["zero"] += 1
        x["results"] = int(r.get("results") or 0)                     # the latest result count for this query
    listed = [(q, x) for q, x in per.items() if x["n"] >= SEARCH_MIN and len(x["hours"]) >= SEARCH_MIN_HOURS]
    top = sorted(listed, key=lambda e: (-e[1]["n"], e[0]))[:10]
    zero = sorted([e for e in listed if e[1]["zero"] * 2 >= e[1]["n"]], key=lambda e: (-e[1]["zero"], e[0]))[:10]
    kinds = collections.Counter(r.get("page") or "other" for r in week)
    return {"min_seen": SEARCH_MIN, "min_hours": SEARCH_MIN_HOURS, "week": totals(week), "prev_week": totals(prev), "pages": kinds.most_common(),
            "top": [[q, x["n"], x["opened"], x["results"]] for q, x in top],
            "zero": [[q, x["n"], x["zero"]] for q, x in zero]}


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
        "search": searches(),
    }
    clicks = buy_clicks()
    try: out["page_views"] = product_views(clicks)
    except Exception as e: print("product page views not made:", str(e)[:80]); out["page_views"] = {}
    if isinstance(clicks, dict): clicks.pop("_on_page", None)
    out["buy_clicks"] = clicks
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
