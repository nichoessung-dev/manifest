# -*- coding: utf-8 -*-
"""
Tell IndexNow which pages changed (21 Oct 2026). IndexNow is read by Bing, Yandex, Seznam and Naver; Bing's index also
feeds ChatGPT search, Copilot and DuckDuckGo. The key file /4709775d5b756bba3e9c31d8ee85aef1.txt was live but nothing
ever pinged it, so new finds reached those engines only when their crawler happened to come by.

  python scripts/indexnow.py changed [--since-hours 26 | --since-file OLD_products.json] [--dry]
      product pages added or changed since then (indexable ones only: those in the live product sitemap), their brand
      hubs, and the main hubs whose server cards follow the view counts (homepage, agent and style spreadsheets).
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
         "/sugargoo-spreadsheet", "/stockholm-spreadsheet", "/grisch-spreadsheet", "/old-money"]

def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read().decode("utf-8")

def sitemap(name):
    return re.findall(r"<loc>([^<]+)</loc>", get(SITE + "/" + name))

def slug(s):   # same as slug() in functions/_lib/site.js
    s = str(s).lower().replace("&", " and ")
    s = re.sub(r"['’]", "", s)
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")

def old_products(args):
    if "--since-file" in args:
        return json.load(open(args[args.index("--since-file") + 1], encoding="utf-8"))
    hours = int(args[args.index("--since-hours") + 1]) if "--since-hours" in args else 26
    rev = subprocess.run(["git", "rev-list", "-1", "--before=%d hours ago" % hours, "HEAD", "--", "products.json"],
                         capture_output=True, text=True).stdout.strip()
    if not rev:
        print("no products.json older than %d hours in the history: nothing to compare" % hours); return None
    return json.loads(subprocess.run(["git", "show", rev + ":products.json"], capture_output=True, text=True, check=True).stdout)

def changed_urls(args):
    old = old_products(args)
    new = json.load(open("products.json", encoding="utf-8"))
    if old is None: return []
    ids = [i for i, p in new.items() if old.get(i) != p]
    products = set(sitemap("sitemap-products.xml"))
    pages = set(sitemap("sitemap-pages.xml"))
    urls = [u for u in (SITE + "/product/" + i for i in ids) if u in products]
    brands = {SITE + "/brand/" + slug(new[i].get("brand") or "") for i in ids if new[i].get("brand")}
    urls += sorted(u for u in brands if u in pages)
    urls += [SITE + p for p in DAILY if SITE + p in pages or p == "/"]
    print("finds added or changed: %d, indexable: %d" % (len(ids), sum(1 for u in urls if "/product/" in u)))
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
