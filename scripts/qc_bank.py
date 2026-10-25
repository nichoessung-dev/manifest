# -*- coding: utf-8 -*-
"""
QC photo bank (25 Oct 2026). qualit.ly allows 1,000 QC lookups a month, and the site used to spend them per visitor and
per Cloudflare location (each location caches on its own), so the quota ran out mid-month and QC photos stopped loading.
This job looks each find up ONCE, stores its QC thumbnails in our own Supabase storage (products/qc/...) and lists it in
data/qc_bank.json. functions/api/qc.js answers from that list first, so a banked find shows QC photos to every visitor
for good, without touching the quota. Each month the quota goes to finds that are not banked yet, most viewed first.

  python scripts/qc_bank.py [--max 300] [--reserve 150] [--dry]
      --max      most lookups this run (the quota allows 30 a minute; one lookup every ~2.2 s)
      --reserve  lookups left untouched each month for visitors opening finds that are not banked yet
      --dry      list what would be looked up, without calling qualit.ly

Needs QUALITLY_KEY (qualit.ly API key) and SUPABASE_SERVICE_KEY (storage upload), both GitHub secrets.
data/qc_bank.json: {"updated": ..., "items": {"weidian/123456": [qc_count, stored_thumbs], ...}}. [n, 0] means qualit.ly
had no usable photos; such finds are not looked up again for 90 days ("checked" dates).
The photos are at SUPA/storage/v1/object/public/products/qc/<storefront>-<id>-<k>.webp, k = 0 .. stored_thumbs-1.
"""
import io, json, os, re, sys, time, urllib.request, urllib.error
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


def catalogue():
    src = open(os.path.join(ROOT, "functions", "_lib", "catalog.js"), encoding="utf-8").read()
    rows = json.loads(src[src.index("export const ROWS = ") + 20:].rstrip().rstrip(";"))
    out = []
    for r in rows:
        plat, qc, item = r[4], r[8] or 0, (r[13] if len(r) > 13 and r[13] else r[0])
        sid = str(item).lstrip("0")
        if plat in ("weidian", "taobao", "1688") and qc >= 1 and re.fullmatch(r"[1-9][0-9]{5,19}", sid):
            out.append((r[0], plat + "/" + sid, qc))
    return out


def views():
    try:
        st = json.loads(get(SITE + "/data/stats.json"))["p"]
        return {k: (v[1] + v[2]) for k, v in st.items()}
    except Exception as e:
        print("view stats not readable (%s): ordering by QC count only" % e); return {}


def upload(name, data):
    req = urllib.request.Request(SUPA + "/storage/v1/object/products/qc/" + name, data=data, method="POST",
                                 headers={**UA, "Authorization": "Bearer " + os.environ["SUPABASE_SERVICE_KEY"],
                                          "apikey": os.environ["SUPABASE_SERVICE_KEY"], "Content-Type": "image/webp",
                                          "x-upsert": "true", "Cache-Control": "max-age=31536000"})
    urllib.request.urlopen(req, timeout=60).read()


def store(key, thumbs):
    """Download, shrink and upload up to MAX_THUMBS photos; returns how many were stored (in order, k = 0..n-1)."""
    n = 0; name = key.replace("/", "-")
    for u in thumbs:
        if n >= MAX_THUMBS: break
        try:
            im = Image.open(io.BytesIO(get(u, timeout=20))).convert("RGB"); im.thumbnail((900, 900))
            buf = io.BytesIO(); im.save(buf, "WEBP", quality=80)
            upload("%s-%d.webp" % (name, n), buf.getvalue()); n += 1
        except Exception as e:
            print("   skipped a photo: %s" % str(e)[:80])
    return n


def main():
    mx, reserve, dry = arg("--max", 300), arg("--reserve", 150), "--dry" in sys.argv
    try: bank = json.load(open(BANK, encoding="utf-8"))
    except Exception: bank = {}
    items, checked = bank.setdefault("items", {}), bank.setdefault("checked", {})
    now = datetime.now(timezone.utc); old = (now - timedelta(days=RECHECK_DAYS)).date().isoformat()
    v = views()
    todo = [(pid, key, qc) for pid, key, qc in catalogue()
            if key not in items or (items[key][1] == 0 and checked.get(key, "") < old)]
    todo = list({key: (pid, key, qc) for pid, key, qc in todo}.values())
    todo.sort(key=lambda t: (-v.get(t[0], 0), -t[2]))
    print("finds with QC on record: %d, banked: %d, still to look up: %d" % (len(catalogue()), len(items), len(todo)))
    if dry:
        for t in todo[:15]: print("  ", t[1], "views", v.get(t[0], 0), "qc", t[2])
        return
    st, use = upstream("/usage")
    left = ((use or {}).get("month") or {}).get("remaining")
    if left is None: raise SystemExit("could not read the qualit.ly quota (status %s): nothing looked up" % st)
    budget = max(0, min(mx, left - reserve))
    print("qualit.ly lookups left this month: %s, reserve for visitors: %d, this run: %d" % (left, reserve, budget))
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
        time.sleep(2.2)                                   # the quota allows 30 lookups a minute
        if done % 25 == 0: save(bank, now)                # keep progress if the run is cut short
    save(bank, now)
    print("looked up %d, finds with photos stored: %d, bank now %d finds (%d with photos)" %
          (done, stored, len(items), sum(1 for x in items.values() if x[1])))


def save(bank, now):
    bank["updated"] = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    bank["items"] = dict(sorted(bank["items"].items())); bank["checked"] = dict(sorted(bank["checked"].items()))
    json.dump(bank, open(BANK, "w", encoding="utf-8"), separators=(",", ":"))


if __name__ == "__main__":
    main()
