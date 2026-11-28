# -*- coding: utf-8 -*-
"""
QC photo bank (25 Oct 2026). qualit.ly allows 1,000 QC lookups a month, and the site used to spend them per visitor and
per Cloudflare location (each location caches on its own), so the quota ran out mid-month and QC photos stopped loading.
This job looks each find up ONCE, stores its QC thumbnails in our own Supabase storage (products/qc/...) and lists it in
data/qc_bank.json. functions/api/qc.js answers from that list first, so a banked find shows QC photos to every visitor
for good, without touching the quota. Each month the quota goes to finds that are not banked yet, most viewed first.

  python scripts/qc_bank.py [--max 300] [--reserve 150] [--per-run 120] [--dry]
      --max      most lookups this run (the quota allows 30 a minute; one lookup every ~2.2 s)
      --reserve  lookups kept for visitors opening finds that are not banked yet, for a whole month: the share kept on a
                 given day is the part of it for the days left until the quota resets (25 Nov 2026), so the end of the
                 month does not leave 150 unused (November: visitors used almost none of them)
      --per-run  on the free plan, at most this many lookups a run (the daily run), so a month's quota is spent over
                 about a week of runs instead of in the first one (0: no cap; bulk mode has none)
      --dry      list what would be looked up, without calling qualit.ly

Order (25 Nov 2026, SEO pass): the swapped finds' old listings, then the finds whose product page is in the live product
sitemap (indexable) and is not hidden, most viewed first: their pages show the banked photos in their HTML. Then the rest.

Sources, in order: Oopbuy (scripts/oopbuy_qc.py, when its keys are set), repsapi.pl (scripts/repsapi_qc.py, REPSAPI_KEY,
2,000 a day free; owner 28 Nov 2026), then qualit.ly with what is left of its monthly quota.
Needs QUALITLY_KEY (qualit.ly API key) and SUPABASE_SERVICE_KEY (storage upload), both GitHub secrets.
data/qc_bank.json: {"updated": ..., "items": {"weidian/123456": [qc_count, stored_thumbs], ...}}. [n, 0] means qualit.ly
had no usable photos; such finds are not looked up again for 90 days ("checked" dates).
The photos are at SUPA/storage/v1/object/public/products/qc/<storefront>-<id>-<k>.webp, k = 0 .. stored_thumbs-1.
"""
import io, json, os, re, sys, time, urllib.parse, urllib.request, urllib.error
from datetime import datetime, timezone, timedelta
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BANK = os.path.join(ROOT, "data", "qc_bank.json")
UPSTREAM = "https://backend.qualit.ly/api/v1"
SUPA = "https://uptpghuduqjqmrxwatbm.supabase.co"
SITE = "https://www.puroclassico.com"
UA = {"User-Agent": "Mozilla/5.0 PuroClassicoQCBank/1.0"}
MAX_THUMBS = 5
RECHECK_DAYS = 90


def arg(name, default):
    a = sys.argv[1:]
    return type(default)(a[a.index(name) + 1]) if name in a else default


def get(url, headers=None, timeout=30):
    r = urllib.request.urlopen(urllib.request.Request(url, headers={**UA, **(headers or {})}), timeout=timeout)
    return r.read()


def upstream(path):
    """(status, data) from qualit.ly, like upstreamJSON() in functions/api/qc.js."""
    try:
        body = json.loads(get(UPSTREAM + path, {"Authorization": "Bearer " + os.environ["QUALITLY_KEY"], "Accept": "application/json"}))
        return 200, (body.get("data") if isinstance(body, dict) and body.get("data") is not None else body)
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception:
        return 0, None


def urls_from(lst):
    out = []
    for x in lst if isinstance(lst, list) else []:
        u = x if isinstance(x, str) else (x or {}).get("url") or (x or {}).get("src") or (x or {}).get("image") or (x or {}).get("thumbnail") or ""
        if u.startswith("https://"): out.append(u)
    return out


def catalogue(everything=False):
    src = open(os.path.join(ROOT, "functions", "_lib", "catalog.js"), encoding="utf-8").read()
    rows = json.loads(src[src.index("export const ROWS = ") + 20:].rstrip().rstrip(";"))
    out = []
    for r in rows:
        plat, qc, item = r[4], r[8] or 0, (r[13] if len(r) > 13 and r[13] else r[0])
        sid = str(item).lstrip("0")
        if plat in ("weidian", "taobao", "1688") and (qc >= 1 or everything) and re.fullmatch(r"[1-9][0-9]{5,19}", sid):
            out.append((r[0], plat + "/" + sid, qc))
    return out


def indexable_ids():
    """The finds whose product page is in the live product sitemap (indexable); empty if it cannot be read."""
    try:
        return {urllib.parse.unquote(x) for x in re.findall(r"/product/([^<]+)</loc>", get(SITE + "/sitemap-products.xml", timeout=60).decode("utf-8"))}
    except Exception as e:
        print("product sitemap not readable (%s): ordering by views only" % str(e)[:80]); return set()


def hidden_ids():
    """Finds the app hides (data/reported.json "hidden": reports, the photo check, the owner's list)."""
    try: return {str(i) for i in json.load(open(os.path.join(ROOT, "data", "reported.json"), encoding="utf-8")).get("hidden") or []}
    except Exception: return set()


def views():
    try:
        st = json.loads(get(SITE + "/data/stats.json"))["p"]
        return {k: (v[1] + v[2]) for k, v in st.items()}
    except Exception as e:
        print("view stats not readable (%s): ordering by QC count only" % e); return {}


def rebadge(im):
    """The qualit.ly corner badge swapped for ours (scripts/qc_badge.py, 26 Nov 2026); the photo as is when that fails."""
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from qc_badge import swap
        return swap(im)[0]
    except Exception as e:
        print("   badge not swapped: %s" % str(e)[:80]); return im


def upload(name, data):
    req = urllib.request.Request(SUPA + "/storage/v1/object/products/qc/" + name, data=data, method="POST",
                                 headers={**UA, "Authorization": "Bearer " + os.environ["SUPABASE_SERVICE_KEY"],
                                          "apikey": os.environ["SUPABASE_SERVICE_KEY"], "Content-Type": "image/webp",
                                          "x-upsert": "true", "Cache-Control": "max-age=31536000"})
    urllib.request.urlopen(req, timeout=60).read()


def store(key, thumbs, badge=True):
    """Download, shrink and upload up to MAX_THUMBS photos; returns how many were stored (in order, k = 0..n-1).
    badge: swap qualit.ly's corner badge for ours (only qualit.ly's own photos; another source's photos stay as sent)."""
    n = 0; name = key.replace("/", "-")
    for u in thumbs:
        if n >= MAX_THUMBS: break
        try:
            im = Image.open(io.BytesIO(get(u, timeout=20))).convert("RGB"); im.thumbnail((900, 900))
            if badge: im = rebadge(im)
            buf = io.BytesIO(); im.save(buf, "WEBP", quality=80)
            upload("%s-%d.webp" % (name, n), buf.getvalue()); n += 1
        except Exception as e:
            print("   skipped a photo: %s" % str(e)[:80])
    return n


def ingest_live(items, checked, now):
    """QC photos saved by visitors' live lookups (functions/api/qc.js saveLive, 19 Nov 2026) into the bank: no lookup spent."""
    key_ = os.environ["SUPABASE_SERVICE_KEY"]; H = {**UA, "Authorization": "Bearer " + key_, "apikey": key_, "Content-Type": "application/json"}
    names, off = [], 0
    while True:
        req = urllib.request.Request(SUPA + "/storage/v1/object/list/products", method="POST", headers=H,
                                     data=json.dumps({"prefix": "qc-live/", "limit": 1000, "offset": off}).encode())
        pg = json.loads(urllib.request.urlopen(req, timeout=60).read())
        names += [x["name"] for x in pg if x.get("name", "").endswith(".json")]
        if len(pg) < 1000: break
        off += 1000
    added = 0
    for nm in names:
        try:
            meta = json.loads(get(SUPA + "/storage/v1/object/public/products/qc-live/" + nm))
            key = "%s/%s" % (meta["storefront"], meta["id"])
            if key in items and items[key][1] > 0: continue
            n = 0; name = key.replace("/", "-")
            for f in meta.get("files") or []:
                if n >= MAX_THUMBS: break
                try:
                    im = Image.open(io.BytesIO(get(SUPA + "/storage/v1/object/public/products/qc-live/" + f, timeout=30))).convert("RGB"); im.thumbnail((900, 900))
                    im = rebadge(im)
                    buf = io.BytesIO(); im.save(buf, "WEBP", quality=80); upload("%s-%d.webp" % (name, n), buf.getvalue()); n += 1
                except Exception as e: print("   live photo skipped: %s" % str(e)[:80])
            if n:
                items[key] = [int(meta.get("qc_count") or n), n]; checked[key] = now.date().isoformat(); added += 1
        except Exception as e: print("   live entry skipped (%s): %s" % (nm, str(e)[:80]))
    print("saved from visitors' lookups: %d finds added to the bank (%d saved in all)" % (added, len(names)))


def main():
    mx, reserve, per_run, dry = arg("--max", 300), arg("--reserve", 150), arg("--per-run", 120), "--dry" in sys.argv
    try: bank = json.load(open(BANK, encoding="utf-8"))
    except Exception: bank = {}
    items, checked = bank.setdefault("items", {}), bank.setdefault("checked", {})
    now = datetime.now(timezone.utc); old = (now - timedelta(days=RECHECK_DAYS)).date().isoformat()
    if not dry:
        try: ingest_live(items, checked, now); save(bank, now)
        except Exception as e: print("visitors' saved lookups not read: %s" % str(e)[:120])
    v = views()
    # a paid plan (owner, 19 Nov 2026: "Save QC photos in bulk"): with 10,000+ lookups a month every find is looked up,
    # also those with no QC on record (the catalogue's QC counts are old), more photos are kept and the pace follows the
    # plan's per-minute limit
    st, use = (0, None) if dry else upstream("/usage")
    month, minute = (use or {}).get("month") or {}, (use or {}).get("minute") or {}
    big = (month.get("limit") or 0) >= 10000
    global MAX_THUMBS
    if big: MAX_THUMBS = 12; old = (now - timedelta(days=30)).date().isoformat()
    pause = max(0.25, 66.0 / (minute.get("limit") or 30))
    # the partner's store items first (owner, 19 Nov 2026: "i want to do qc photos on all my friends items"): their own
    # Weidian ids (data/friend_finds.json), which are the Buy links of the imported and the swapped finds
    try: friend = [str(i).lstrip("0") for i in json.load(open(os.path.join(ROOT, "data", "friend_finds.json"), encoding="utf-8"))["ids"]]
    except Exception: friend = []
    fkeys = {"weidian/" + i for i in friend if re.fullmatch(r"[1-9][0-9]{5,19}", i)}
    todo = [("fr:" + k, k, 1) for k in sorted(fkeys)] + [(pid, key, qc) for pid, key, qc in catalogue(big) if key not in fkeys]
    todo = [t for t in todo if t[1] not in items or (items[t[1]][1] == 0 and checked.get(t[1], "") < old)]
    todo = list({key: (pid, key, qc) for pid, key, qc in todo}.values())
    # 20 Nov 2026: the partner's own listings turned out to have no QC on qualit.ly (130 of 130 empty), so the old listings
    # of the swapped finds go first (the app shows those photos on the swapped finds), then the rest by views; the
    # partner's own ids last
    try: swapped = set((json.load(open(os.path.join(ROOT, "data", "link_swaps.json"), encoding="utf-8")).get("swaps") or {}).keys())
    except Exception: swapped = set()
    ix, hid = indexable_ids(), hidden_ids()
    todo.sort(key=lambda t: (t[0].startswith("fr:"), t[0] not in swapped, t[0] not in ix or t[0] in hid, -v.get(t[0], 0), -t[2]))
    print("finds with QC on record: %d, banked: %d, still to look up: %d" % (len(catalogue()), len(items), len(todo)))
    if dry:
        for t in todo[:15]: print("  ", t[1], "views", v.get(t[0], 0), "qc", t[2])
        return
    # Oopbuy first (26 Nov 2026): its QC API has no monthly quota, so every find not banked yet is asked there, also those
    # with no QC on record; what it does not have goes on to qualit.ly below
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import oopbuy_qc
        if oopbuy_qc.ready():
            omax = arg("--oopbuy-max", 3000); asked = found = 0
            seen = set(items)
            allf = [t for t in ([("fr:" + k, k, 1) for k in sorted(fkeys)] + catalogue(True)) if t[1] not in seen or (items[t[1]][1] == 0 and checked.get("oop:" + t[1], "") < old)]
            allf.sort(key=lambda t: (t[0].startswith("fr:"), t[0] not in swapped, t[0] not in ix or t[0] in hid, -v.get(t[0], 0)))
            for pid, key, qc in list({t[1]: t for t in allf}.values())[:omax]:
                st, ph = oopbuy_qc.photos(key.split("/")[1]); asked += 1
                if st not in (200, 404) and asked <= 3 and not found:
                    print("Oopbuy QC not answering (%s): skipped this run" % st); break
                checked["oop:" + key] = now.date().isoformat()
                if ph:
                    n = store(key, ph, badge=False)
                    if n: items[key] = [max(len(ph), n), n]; checked[key] = now.date().isoformat(); found += 1
                    print("%-28s oopbuy photos %d stored %d" % (key, len(ph), n))
                time.sleep(0.4)
                if asked % 50 == 0: save(bank, now)
            save(bank, now)
            print("Oopbuy: asked %d, finds with photos stored %d" % (asked, found))
            todo = [t for t in todo if not (t[1] in items and items[t[1]][1] > 0)]
    except Exception as e:
        print("Oopbuy QC pass failed: %s" % str(e)[:160])
    # repsapi.pl next (owner, 28 Nov 2026): 2,000 lookups a day on the free plan, every find not banked yet (also those
    # with no QC on record), most important first; what it does not have goes on to qualit.ly below
    try:
        import repsapi_qc
        if repsapi_qc.ready():
            rmax = arg("--repsapi-max", 1200); asked = found = 0
            seen = {k for k, x in items.items() if x[1] > 0}
            allf = [t for t in ([("fr:" + k, k, 1) for k in sorted(fkeys)] + catalogue(True))
                    if t[1] not in seen and checked.get("rep:" + t[1], "") < old]
            allf.sort(key=lambda t: (t[0].startswith("fr:"), t[0] not in swapped, t[0] not in ix or t[0] in hid, -v.get(t[0], 0), -t[2]))
            for pid, key, qc in list({t[1]: t for t in allf}.values())[:rmax]:
                sf, sid = key.split("/")
                rst, total, ph = repsapi_qc.photos(sf, sid); asked += 1
                if rst == 429:
                    print("repsapi.pl: rate limited, waiting a minute"); time.sleep(62)
                    rst, total, ph = repsapi_qc.photos(sf, sid)
                if rst in (401, 403): print("repsapi.pl refused the key (%s): check REPSAPI_KEY" % rst); break
                if rst == 429: print("repsapi.pl: daily allowance used up, the next run goes on"); break
                if rst not in (200, 404):
                    if asked <= 3 and not found: print("repsapi.pl not answering (%s): skipped this run" % rst); break
                    continue
                checked["rep:" + key] = now.date().isoformat()
                if ph:
                    n = store(key, ph, badge=False)
                    if n: items[key] = [max(total, n), n]; checked[key] = now.date().isoformat(); found += 1
                    print("%-28s repsapi photos %d stored %d" % (key, total, n))
                elif key not in items:
                    items[key] = [0, 0]; checked[key] = now.date().isoformat()
                time.sleep(repsapi_qc.PAUSE)
                if asked % 50 == 0: save(bank, now)
            save(bank, now)
            print("repsapi.pl: asked %d, finds with photos stored %d" % (asked, found))
            todo = [t for t in todo if not (t[1] in items and items[t[1]][1] > 0)]
        else:
            print("repsapi.pl: REPSAPI_KEY is not set, skipped")
    except Exception as e:
        print("repsapi.pl pass failed: %s" % str(e)[:160])
    left = month.get("remaining")
    if left is None:
        save(bank, now); print("could not read the qualit.ly quota (status %s): no qualit.ly lookups this run" % st); return
    # the visitors' share for the days left until the quota resets (reset_at, else the 1st of next month, UTC)
    try: rdt = datetime.fromisoformat(str(month.get("reset_at")).replace("Z", "+00:00"))
    except Exception: rdt = None
    if not rdt or rdt.tzinfo is None: rdt = (now.replace(day=28) + timedelta(days=4)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    days_left = max(1, (rdt - now).days + 1)
    keep = min(reserve, -(-reserve * days_left // 30))
    cap = mx if big or per_run <= 0 else min(mx, per_run)
    budget = max(0, min(cap, left - keep))
    print("plan: %s lookups a month%s" % (month.get("limit"), " (bulk mode: every find)" if big else ""))
    print("qualit.ly lookups left this month: %s, days to the reset: %d, kept for visitors: %d of %d, this run: %d (cap %d)" % (left, days_left, keep, reserve, budget, cap))
    print("first in line: %s" % ", ".join("%s (views %d)" % (t[1], v.get(t[0], 0)) for t in todo[:5]))
    done = stored = 0
    for pid, key, qc in todo:
        if done >= budget: break
        sf, sid = key.split("/")
        st, d = upstream("/products/%s/%s" % (sf, sid)); done += 1
        if st == 429: print("rate limited: waiting a minute"); time.sleep(62); st, d = upstream("/products/%s/%s" % (sf, sid)); done += 1
        if st == 429 or st >= 500 or st == 0: print("qualit.ly unavailable (%s): stopping" % st); break
        thumbs = urls_from((d or {}).get("qc_preview")) + urls_from((d or {}).get("thumbnails"))
        n = store(key, list(dict.fromkeys(thumbs))) if thumbs else 0
        items[key] = [int((d or {}).get("qc_count") or 0), n]; checked[key] = now.date().isoformat()
        stored += n > 0
        print("%-28s qc %-3s stored %d" % (key, items[key][0], n))
        time.sleep(pause)                                 # the plan's per-minute limit (30 on the free plan)
        if done % 25 == 0: save(bank, now)                # keep progress if the run is cut short
    save(bank, now)
    print("still to look up after this run: %d" % max(0, len(todo) - done))
    print("looked up %d, finds with photos stored: %d, bank now %d finds (%d with photos)" %
          (done, stored, len(items), sum(1 for x in items.values() if x[1])))


def save(bank, now):
    bank["updated"] = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    bank["items"] = dict(sorted(bank["items"].items())); bank["checked"] = dict(sorted(bank["checked"].items()))
    json.dump(bank, open(BANK, "w", encoding="utf-8"), separators=(",", ":"))


if __name__ == "__main__":
    main()
