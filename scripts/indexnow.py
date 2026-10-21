# -*- coding: utf-8 -*-
"""
Tell IndexNow which pages changed (21 Oct 2026). IndexNow is read by Bing, Yandex, Seznam and Naver; Bing's index also
feeds ChatGPT search, Copilot and DuckDuckGo. The key file /4709775d5b756bba3e9c31d8ee85aef1.txt was live but nothing
ever pinged it, so new finds reached those engines only when their crawler happened to come by.

  python scripts/indexnow.py changed [--since-hours 26 | --since-file OLD_products.json] [--dry]
      product pages added or changed since then (indexable ones only: those in the live product sitemap), pages that
      became indexable or were found gone (functions/_lib/signals.js), their brand hubs, and the main hubs whose server
      cards follow the view counts (homepage, agent and style spreadsheets).
  python scripts/indexnow.py all [--dry]
      every URL in the live sitemaps, for a site-wide change (run by hand, not on a schedule).

Only real changes are sent: the engines stop trusting a site that pings unchanged pages.
"""
import json, re, subprocess, sys, urllib.request, urllib.error

KEY = "4709775d5b756bba3e9c31d8ee85aef1"
HOST = "www.puroclassico.com"
SITE = "https://" + HOST
UA = {"User-Agent": "Mozilla/5.0 PuroClassicoIndexNow/1.0"}
# Pages whose content moves every day without a catalogue change: their first 60 cards follow the view counts.
DAILY = ["/", "/mycnbox-spreadsheet", "/kakobuy-spreadsheet", "/oopbuy-spreadsheet", "/lovegobuy-spreadsheet",
         "/sugargoo-spreadsheet", "/stockholm-spreadsheet", "/grisch-spreadsheet", "/old-money", "/cnfans-spreadsheet"] + \
        ["/%s-spreadsheet/%s" % (k, x) for k in ("mycnbox", "kakobuy", "oopbuy", "sugargoo") for x in ("grisch", "old-money", "shoes")]

def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read().decode("utf-8")

def sitemap(name):
    return re.findall(r"<loc>([^<]+)</loc>", get(SITE + "/" + name))

def slug(s):   # same as slug() in functions/_lib/site.js
    s = str(s).lower().replace("&", " and ")
    s = re.sub(r"['’]", "", s)
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")

def old_rev(args):
    hours = int(args[args.index("--since-hours") + 1]) if "--since-hours" in args else 26
    return subprocess.run(["git", "rev-list", "-1", "--before=%d hours ago" % hours, "HEAD"], capture_output=True, text=True).stdout.strip()

def old_file(rev, path):
    r = subprocess.run(["git", "show", rev + ":" + path], capture_output=True, text=True) if rev else None
    return r.stdout if r and r.returncode == 0 else None

def old_products(args):
    if "--since-file" in args:
        return json.load(open(args[args.index("--since-file") + 1], encoding="utf-8"))
    src = old_file(old_rev(args), "products.json")
    if src is None:
        print("no older products.json in the history: nothing to compare"); return None
    return json.loads(src)

def signal_ids(src):
    """Every id in DEMAND, DEAD and SOLD_OUT, tagged with its list, from the text of a signals.js."""
    out = set()
    for name in ("DEMAND", "DEAD", "SOLD_OUT"):
        m = re.search(r"export const %s = (\[[^\n]*\]);" % name, src or "")
        if m: out |= {(name, i) for i in json.loads(m.group(1))}
    return out

def signal_changes(args):
    """Product ids whose signal changed since then: newly indexable for demand, or newly found dead or sold out."""
    now = signal_ids(open("functions/_lib/signals.js", encoding="utf-8").read())
    before = set() if "--since-file" in args else signal_ids(old_file(old_rev(args), "functions/_lib/signals.js"))
    return sorted({i for _, i in now - before})

def changed_urls(args):
    old = old_products(args)
    new = json.load(open("products.json", encoding="utf-8"))
    if old is None: return []
    ids = [i for i, p in new.items() if old.get(i) != p]
    flips = [i for i in signal_changes(args) if i in new]
    products = set(sitemap("sitemap-products.xml"))
    pages = set(sitemap("sitemap-pages.xml"))
    urls = [u for u in (SITE + "/product/" + i for i in ids) if u in products]
    print("finds added or changed: %d (%d indexable), pages whose indexing changed: %d" % (len(ids), len(urls), len(flips)))
    urls += [SITE + "/product/" + i for i in flips]           # now indexable, or now noindex: either way worth a recrawl
    brands = {SITE + "/brand/" + slug(new[i].get("brand") or "") for i in ids if new[i].get("brand")}
    urls += sorted(u for u in brands if u in pages)
    urls += [SITE + p for p in DAILY if SITE + p in pages or p == "/"]
    return urls

def submit(urls, dry):
    urls = list(dict.fromkeys(urls))
    print("URLs to submit: %d" % len(urls))
    for u in urls[:12]: print("  " + u)
    if dry or not urls: return True
    ok = True
    for i in range(0, len(urls), 10000):
        body = json.dumps({"host": HOST, "key": KEY, "keyLocation": "%s/%s.txt" % (SITE, KEY), "urlList": urls[i:i + 10000]}).encode()
        req = urllib.request.Request("https://api.indexnow.org/indexnow", data=body, method="POST",
                                     headers={"Content-Type": "application/json; charset=utf-8", **UA})
        try:
            r = urllib.request.urlopen(req, timeout=60); print("IndexNow answered %d" % r.status)
        except urllib.error.HTTPError as e:
            # 200/202 = received. 403 = key not valid, 422 = URLs not on this host, 429 = too many requests.
            print("IndexNow answered %d: %s" % (e.code, e.read().decode()[:200])); ok = False
    return ok

def main():
    args = sys.argv[1:]
    mode = args[0] if args else "changed"
    urls = sitemap("sitemap-pages.xml") + sitemap("sitemap-products.xml") if mode == "all" else changed_urls(args)
    sys.exit(0 if submit(urls, "--dry" in args) else 1)

if __name__ == "__main__":
    main()
