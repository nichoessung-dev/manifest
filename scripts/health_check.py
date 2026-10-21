# -*- coding: utf-8 -*-
"""
Daily health check of the parts of the site that make money or members (21 Oct 2026). Run by .github/workflows/health.yml.
Every check prints OK, WARN or FAIL with one line of detail; the run fails (red) when any check FAILs, and GitHub then
emails the owner. WARN is shown in the run summary only. Nothing is changed anywhere: this only reads.

Each check is here because it broke once without anyone noticing: the Discord invite on every page expired, the QC
photo quota ran out mid-month, the Postiz API went down (no TikTok drafts), unsubscribe links answered with a redirect,
pages grew past Google's 2 MB limit, and the welcome emails ran three times a day instead of every 15 minutes.

  python scripts/health_check.py            (GITHUB_TOKEN optional: used for the welcome-email check)
"""
import datetime, json, os, re, sys, urllib.request, urllib.error

SITE = "https://www.puroclassico.com"
REPO = "nichoessung-dev/manifest"
UA = {"User-Agent": "Mozilla/5.0 PuroClassicoHealth/1.0"}
LIMIT = 2 * 1024 * 1024                     # Googlebot reads the first 2 MB of each file
NOW = datetime.datetime.now(datetime.timezone.utc)
results = []

def req(url, method="GET", data=None, headers=None, timeout=40):
    """(status, headers, body) without following redirects, so a 301 shows as a 301."""
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k): return None
    opener = urllib.request.build_opener(NoRedirect)
    r = urllib.request.Request(url, data=data, method=method, headers={**UA, **(headers or {})})
    try:
        resp = opener.open(r, timeout=timeout); return resp.status, resp.headers, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers, e.read()

def check(name, fn):
    try: level, detail = fn()
    except Exception as e: level, detail = "FAIL", "check crashed: %s" % str(e)[:160]
    results.append((level, name, detail)); print("%-4s %-28s %s" % (level, name, detail))

def age_hours(iso):
    return (NOW - datetime.datetime.fromisoformat(iso.replace("Z", "+00:00"))).total_seconds() / 3600

def discord():
    src = open("functions/_lib/site.js", encoding="utf-8").read()
    code = re.search(r'DISCORD_INVITE = "https://discord\.gg/([A-Za-z0-9-]+)"', src).group(1)
    st, _, body = req("https://discord.com/api/v10/invites/%s?with_expiration=true" % code)
    d = json.loads(body or b"{}")
    if st != 200: return "FAIL", "invite %s: %s (make a new never-expiring invite, put it in DISCORD_INVITE in functions/_lib/site.js)" % (code, d.get("message", st))
    exp = d.get("expires_at")
    if exp and age_hours(exp) > -72: return "WARN", "invite %s expires %s" % (code, exp[:16])
    return "OK", "invite %s works%s" % (code, "" if not exp else ", expires " + exp[:10])

def pages():
    bad = []
    for path in ["/", "/kakobuy-spreadsheet", "/mycnbox-spreadsheet", "/brand/ralph-lauren", "/stockholm-spreadsheet", "/cnfans-spreadsheet", "/kakobuy-spreadsheet/grisch", "/product/6716583439", "/how-to-order"]:
        st, _, body = req(SITE + path)
        if st != 200: bad.append("%s answered %d" % (path, st)); continue
        if len(body) > LIMIT: bad.append("%s is %.1f MB (over Google's 2 MB)" % (path, len(body) / 1048576))
        if path != "/product/6716583439" and path != "/how-to-order" and b"data-ssr=" not in body: bad.append("%s has no server cards" % path)
    m = re.search(rb'catalog\.js\?v=([A-Za-z0-9]+)', req(SITE + "/")[2])
    if not m: bad.append("homepage loads no /catalog.js")
    else:
        for i in range(3):
            st, _, body = req("%s/catalog.js?v=%s&p=%d" % (SITE, m.group(1).decode(), i))
            if st != 200 or len(body) > LIMIT: bad.append("catalog part %d: %d, %.1f MB" % (i, st, len(body) / 1048576))
    return ("FAIL", "; ".join(bad)) if bad else ("OK", "key pages 200, under 2 MB, cards in the HTML, catalogue parts fine")

def sitemaps():
    n = {name: len(re.findall(rb"<loc>", req("%s/%s" % (SITE, name))[2])) for name in ("sitemap-pages.xml", "sitemap-products.xml")}
    if n["sitemap-pages.xml"] < 300 or n["sitemap-products.xml"] < 1500: return "FAIL", "only %(sitemap-pages.xml)d page URLs and %(sitemap-products.xml)d product URLs" % n
    return "OK", "%(sitemap-pages.xml)d page URLs, %(sitemap-products.xml)d product URLs" % n

def unsubscribe():
    st, _, _ = req(SITE + "/unsubscribe?u=health-check&t=0", method="POST", data=b"List-Unsubscribe=One-Click",
                   headers={"Content-Type": "application/x-www-form-urlencoded"})
    if 300 <= st < 400: return "FAIL", "one-click unsubscribe answers %d: a redirect breaks Gmail's unsubscribe button" % st
    if st >= 500: return "FAIL", "unsubscribe endpoint answers %d" % st
    return "OK", "one-click unsubscribe answers %d without a redirect" % st

def qc_quota():
    st, _, body = req(SITE + "/api/qc?usage=1")
    if st != 200: return "WARN", "quota not readable (%d)" % st
    m = json.loads(body).get("month") or {}
    left, limit = m.get("remaining"), m.get("limit")
    if left is None or not limit: return "WARN", "quota answer without numbers"
    # a warning, not a failure: only a bigger plan fixes it, and a red run every day until the reset would be noise
    if left <= 0: return "WARN", "QC photo lookups used up (%s of %s) until %s: new QC photos can't load" % (m.get("used"), limit, (m.get("reset_at") or "")[:10])
    if left < 0.1 * limit: return "WARN", "%s of %s QC lookups left this month" % (left, limit)
    return "OK", "%s of %s QC lookups left this month" % (left, limit)

def postiz():
    st, _, body = req("https://api.postiz.com/public/v1/integrations")
    if st == 404 and b"Application not found" in body or st >= 500 or st == 0:
        return "FAIL", "Postiz API is down (%d): no TikTok drafts or posts until it is back" % st
    return "OK", "Postiz API answers (%d without a key, as expected)" % st

def cnfans():
    """/cnfans-spreadsheet says CNFans shows a maintenance page (CNFANS in functions/_lib/pages.js): warn when that changes."""
    try:
        st, _, body = req("https://cnfans.com/", headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"}, timeout=20)
    except Exception: return "WARN", "could not reach cnfans.com"
    m = re.search(rb"<title>(.*?)</title>", body or b"", re.S | re.I)
    title = m.group(1).decode("utf-8", "replace").strip() if m else "(no title, status %d)" % st
    if "aintenance" in title: return "OK", "CNFans still shows its maintenance page"
    return "WARN", 'CNFans title is now "%s": update CNFANS in functions/_lib/pages.js and the /cnfans-spreadsheet copy' % title[:60]

def data_age():
    bad = []
    st = json.loads(req(SITE + "/data/stats.json")[2]); lh = json.loads(req(SITE + "/data/link_health.json")[2])
    h = age_hours(st["generated"])
    if h > 24: bad.append("view stats are %.0f h old (Stats job every 6 h)" % h)
    d = age_hours(lh["checked"]) / 24
    if d > 9: bad.append("link check is %.0f days old (Link check job weekly)" % d)
    return ("FAIL", "; ".join(bad)) if bad else ("OK", "stats %.0f h old, link check %.0f days old" % (h, d))

def welcome():
    tok = os.environ.get("GITHUB_TOKEN")
    hdr = {"Authorization": "Bearer " + tok} if tok else {}
    st, _, body = req("https://api.github.com/repos/%s/actions/workflows/welcome.yml/runs?status=success&per_page=1" % REPO, headers=hdr)
    runs = json.loads(body).get("workflow_runs") or []
    if not runs: return "FAIL", "no successful welcome-email run found"
    h = age_hours(runs[0]["updated_at"])
    if h > 6: return "FAIL", "last successful welcome-email run was %.0f h ago: new members wait for their coupon email" % h
    return "OK", "last welcome-email run %.0f min ago" % (h * 60)

check("Discord invite", discord)
check("Key pages", pages)
check("Sitemaps", sitemaps)
check("One-click unsubscribe", unsubscribe)
check("QC photo quota", qc_quota)
check("Postiz API", postiz)
check("CNFans status", cnfans)
check("Data freshness", data_age)
check("Welcome emails", welcome)

summary = os.environ.get("GITHUB_STEP_SUMMARY")
if summary:
    with open(summary, "a", encoding="utf-8") as f:
        f.write("## Site health %s\n\n| | Check | Detail |\n|---|---|---|\n" % NOW.strftime("%Y-%m-%d %H:%M UTC"))
        for level, name, detail in results:
            f.write("| %s | %s | %s |\n" % ({"OK": "✅", "WARN": "⚠️", "FAIL": "❌"}[level], name, detail.replace("|", "/")))
fails = [r for r in results if r[0] == "FAIL"]
print("\n%d checks, %d failing" % (len(results), len(fails)))
sys.exit(1 if fails else 0)
