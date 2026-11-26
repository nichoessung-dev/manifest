# -*- coding: utf-8 -*-
"""
One-off (26 Nov 2026, owner: swap the qualit.ly corner badge for a QR code to puroclassico.com, agreed with qualit.ly):
goes through every photo in the QC bank (data/qc_bank.json, products/qc/<storefront>-<id>-<k>.webp), swaps the badge
with scripts/qc_badge.py and uploads the photo again under the same name. Photos without the badge are left alone.
New photos get the swap in scripts/qc_bank.py, so this runs once.

  python scripts/qc_rebadge.py [--limit N] [--dry]

Needs SUPABASE_SERVICE_KEY. Writes data/qc_rebadged.json (names done), so a second run skips them.
"""
import io, json, os, sys, urllib.request
from concurrent.futures import ThreadPoolExecutor
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from qc_badge import swap
from qc_bank import SUPA, UA, upload, BANK

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DONE = os.path.join(ROOT, "data", "qc_rebadged.json")


def one(name, dry):
    import time
    for t in range(4):
        r = _one(name, dry)
        if not r[1].startswith("error"): return r
        time.sleep(2 + 3 * t)
    return r


def _one(name, dry):
    try:
        raw = urllib.request.urlopen(urllib.request.Request(SUPA + "/storage/v1/object/public/products/qc/" + name, headers=UA), timeout=30).read()
        out, ok = swap(Image.open(io.BytesIO(raw)))
        if ok and not dry:
            buf = io.BytesIO(); out.save(buf, "WEBP", quality=80); upload(name, buf.getvalue())
        return name, "swapped" if ok else "clean"
    except Exception as e:
        return name, "error: " + str(e)[:80]


def main():
    dry = "--dry" in sys.argv
    lim = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else 0
    items = json.load(open(BANK, encoding="utf-8")).get("items", {})
    try: done = set(json.load(open(DONE)))
    except Exception: done = set()
    names = [k.replace("/", "-") + "-%d.webp" % i for k, v in items.items() for i in range(int(v[1] or 0))]
    todo = [n for n in names if n not in done]
    if lim: todo = todo[:lim]
    print("%d photos in the bank, %d to check" % (len(names), len(todo)))
    tally = {}
    with ThreadPoolExecutor(3) as ex:
        for i, (n, r) in enumerate(ex.map(lambda n: one(n, dry), todo)):
            k = r.split(":")[0]; tally[k] = tally.get(k, 0) + 1
            if k != "error": done.add(n)
            else: print("  %s %s" % (n, r))
            if i % 100 == 0: print("  %d/%d %s" % (i, len(todo), tally))
    print("done:", tally)
    if not dry:
        json.dump(sorted(done), open(DONE, "w"))


if __name__ == "__main__":
    main()
