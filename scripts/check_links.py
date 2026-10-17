# -*- coding: utf-8 -*-
"""Weekly dead-link check for the Weidian finds (about 90% of the catalogue).

Weidian's public item API answers every id: a live listing comes back with its title, main picture and stock, a deleted or
hidden one comes back without them. Taobao and 1688 block this kind of lookup, so their listings are not checked here; the
"Report broken link" button covers them.

A listing is only called dead when two lookups, a few seconds apart, both come back without a title, so one bad answer
never hides a find. Network errors and unexpected answers are counted, never treated as dead.

Writes data/link_health.json:
  {"checked": "...", "weidian_checked": n, "dead": [ids], "sold_out": [ids], "errors": n}
The site hides dead finds from the catalogue and the /stats page lists them.

  python scripts/check_links.py              # every Weidian find
  python scripts/check_links.py --limit 50   # a quick sample
"""
import argparse, json, os, re, sys, time, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "link_health.json")
API = "https://thor.weidian.com/detail/getItemSkuInfo/1.0?param="
PAUSE = 0.35      # seconds between lookups per worker; Weidian starts refusing above a few per second
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"


def catalogue():
    html = open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()
    m = re.search(r'<script type="application/json" id="pc-catalog">(.*?)</script>', html, re.S)
    if not m: sys.exit("catalogue not found in index.html")
    return json.loads(m.group(1))


def lookup(item_id):
    """'live', 'sold_out', 'gone' or 'error'."""
    url = API + urllib.parse.quote(json.dumps({"itemId": str(item_id)}))
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA, "Referer": "https://weidian.com/"}), timeout=20) as r:
            d = json.load(r)
    except Exception:
        return "error"
    if (d.get("status") or {}).get("code") != 0: return "error"
    res = d.get("result") or {}
    if res.get("itemTitle") or res.get("itemMainPic"):
        stock = res.get("itemStock")
        return "sold_out" if isinstance(stock, (int, float)) and stock <= 0 else "live"
    return "gone"


def patient(iid):
    """One lookup, retried with growing pauses while Weidian answers with errors (it rate-limits bursts)."""
    for wait in (0, 5, 15, 40):
        if wait: time.sleep(wait)
        st = lookup(iid)
        if st != "error": return st
    return "error"


def check(p):
    iid = str(p.get("itemId") or p["id"]).lstrip("0") or "0"
    time.sleep(PAUSE)
    first = patient(iid)
    if first == "gone":
        time.sleep(4)
        second = patient(iid)
        return p["id"], ("gone" if second == "gone" else second)
    return p["id"], first


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=2)
    a = ap.parse_args()
    items = [p for p in catalogue() if p.get("platform") == "weidian"]
    if a.limit: items = items[:a.limit]
    print("checking %d Weidian finds" % len(items), flush=True)
    res, t0 = {}, time.time()
    with ThreadPoolExecutor(a.workers) as ex:
        for k, (pid, st) in enumerate(ex.map(check, items), 1):
            res[pid] = st
            if k % 500 == 0: print("  %d done (%.0fs)" % (k, time.time() - t0), flush=True)
    dead = sorted(i for i, s in res.items() if s == "gone")
    sold = sorted(i for i, s in res.items() if s == "sold_out")
    errors = sum(1 for s in res.values() if s == "error")
    if items and errors > len(items) * 0.3:
        sys.exit("too many errors (%d of %d): Weidian may be blocking; the old result is kept" % (errors, len(items)))
    out = {"checked": datetime.now(timezone.utc).replace(microsecond=0).isoformat(), "weidian_checked": len(items),
           "dead": dead, "sold_out": sold, "errors": errors}
    if not a.limit:
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        json.dump(out, open(OUT, "w"), separators=(",", ":"))
    print("dead: %d, sold out: %d, errors: %d, live: %d" % (len(dead), len(sold), errors, len(items) - len(dead) - len(sold) - errors))
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as f:
            f.write("### Weidian link check\n\n%d checked: **%d dead**, %d sold out, %d errors.\n\n" % (len(items), len(dead), len(sold), errors))
            f.write("".join("- https://www.puroclassico.com/product/%s\n" % i for i in dead[:300]))


if __name__ == "__main__":
    main()
