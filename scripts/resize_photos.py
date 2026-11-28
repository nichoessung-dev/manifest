# -*- coding: utf-8 -*-
"""Our own small copies of every find's photo (owner, 28 Nov 2026). Cloudflare's image resizing billed $59.50 in November:
it counts every photo in every size once per calendar month (15,000+ finds in up to 7 sizes, about 120,000 a month).
The site now asks for these files instead, so Cloudflare resizes nothing.

  img/r/<w>/<key>.webp   w = 400 or 720 px wide (never enlarged; transparency kept); larger views use the original
  key                    /img/<rest>.webp                                    -> <rest>
                         a Supabase product photo .../public/products/<sub>.webp[?v=n] -> s/<sub>[.v<n>]
Same rule as rsKey() in index.html and functions/_lib/site.js, and rsOrigin() in functions/_middleware.js (which sends a
copy not made yet to the original photo). The source is read from the repository (img/..., the img/m mirror of Supabase),
else downloaded. data/resized/<k>-of-<n>.json {key: sha1 of the source, first 12}: an unchanged source is not made again.
Sharded by key (store_photos_shards.py), so parallel jobs (.github/workflows/resize-photos.yml) never write the same file.

  python scripts/resize_photos.py [--shard 0/1] [--limit N] [--check]      --check: only count what is missing
"""
import hashlib, io, json, os, re, sys, time, urllib.request
from concurrent.futures import ProcessPoolExecutor

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from catalog_common import ROOT, load_catalog  # noqa: E402
import store_photos_shards as shards  # noqa: E402

TIERS = (400, 720)
QUALITY = {400: 76, 720: 78}
SB = "https://uptpghuduqjqmrxwatbm.supabase.co/storage/v1/object/public/products/"
OUT = os.path.join(ROOT, "img", "r")
LOGS = os.path.join(ROOT, "data", "resized")
UA = {"User-Agent": "Mozilla/5.0 PuroClassicoResize/1.0"}


def key_of(img):
    """The copy's key for a catalogue photo address, '' when it has none (the original is used)."""
    img = img or ""
    m = re.fullmatch(r"/img/((?:rl|fr|p|p2|cut|white)/[\w./-]+?)\.webp", img)
    if m: return m.group(1)
    if img.startswith(SB):
        m = re.fullmatch(r"((?:pc|pc2|store|store2)/[\w./-]+?)\.webp(?:\?v=([\w-]{1,20}))?", img[len(SB):])
        if m: return "s/" + m.group(1) + (".v" + m.group(2) if m.group(2) else "")
    return ""


def source_bytes(img):
    """The original photo: the repository file, the img/m mirror of a Supabase photo, else a download."""
    if img.startswith("/img/"):
        return open(os.path.join(ROOT, img[1:]), "rb").read()
    m = re.fullmatch(re.escape(SB) + r"(pc|pc2|qc)/([\w-]{1,80})\.webp(?:\?v=([\w-]{1,20}))?", img)
    if m:
        p = os.path.join(ROOT, "img", "m", m.group(1), m.group(2) + (".v" + m.group(3) if m.group(3) else "") + ".webp")
        if os.path.exists(p): return open(p, "rb").read()
    for t in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(img, headers=UA), timeout=40) as r: return r.read()
        except Exception:
            time.sleep(2 + 3 * t)
    raise RuntimeError("source not readable")


def make(job):
    """(key, sha or None, error) for one photo: writes its copies."""
    key, img, old = job
    try:
        data = source_bytes(img)
        sha = hashlib.sha1(data).hexdigest()[:12]
        if sha == old and all(os.path.exists(os.path.join(OUT, str(w), key + ".webp")) for w in TIERS): return key, sha, ""
        im = Image.open(io.BytesIO(data)); im.load()
        im = im.convert("RGBA") if im.mode in ("RGBA", "LA", "P") or "transparency" in im.info else im.convert("RGB")
        for w in TIERS:
            c = im.copy()
            if c.width > w: c = c.resize((w, max(1, round(c.height * w / c.width))), Image.LANCZOS)
            dest = os.path.join(OUT, str(w), key + ".webp"); os.makedirs(os.path.dirname(dest), exist_ok=True)
            b = io.BytesIO(); c.save(b, "WEBP", quality=QUALITY[w], method=4)
            open(dest + ".part", "wb").write(b.getvalue()); os.replace(dest + ".part", dest)
        return key, sha, ""
    except Exception as e:  # noqa: BLE001 (left out; the site shows the original)
        return key, None, str(e)[:120]


def main():
    a = sys.argv[1:]
    limit = int(a[a.index("--limit") + 1]) if "--limit" in a else 0
    shard = shards.parse(a[a.index("--shard") + 1] if "--shard" in a else "0/1")
    LOG = os.path.join(LOGS, "%d-of-%d.json" % shard)
    _, items, _, _ = load_catalog()
    try: log = json.load(open(LOG))
    except Exception: log = {}
    done = log.setdefault("items", {})
    jobs, seen = [], set()
    for p in items:
        img = p.get("img") or ""; key = key_of(img)
        if not key or key in seen or not shards.mine(key, shard): continue
        seen.add(key)
        if key in done and all(os.path.exists(os.path.join(OUT, str(w), key + ".webp")) for w in TIERS) and "--deep" not in a: continue
        jobs.append((key, img, done.get(key)))
    print("photos with a copy key %d, to make now %d" % (len(seen), len(jobs)), flush=True)
    if "--check" in a: return
    if limit: jobs = jobs[:limit]
    t0, ok, bad = time.time(), 0, 0
    with ProcessPoolExecutor(max(1, (os.cpu_count() or 2))) as ex:
        for n, (key, sha, err) in enumerate(ex.map(make, jobs, chunksize=8), 1):
            if sha: done[key] = sha; ok += 1
            else: bad += 1; print("  %s: %s" % (key, err), flush=True)
            if n % 500 == 0: print("  %d done in %.0f s" % (n, time.time() - t0), flush=True)
    # copies of photos no find uses any more are removed, so the site's file count does not grow
    gone = [k for k in done if k not in seen]
    for k in gone:
        for w in TIERS:
            try: os.remove(os.path.join(OUT, str(w), k + ".webp"))
            except FileNotFoundError: pass
        done.pop(k, None)
    log["about"] = "Our own small copies of the finds' photos (scripts/resize_photos.py): key -> sha1 of the source, first 12."
    log["items"] = dict(sorted(done.items()))
    os.makedirs(LOGS, exist_ok=True); json.dump(log, open(LOG, "w"), indent=0)
    print("made %d, failed %d, removed %d, in %.0f s; copies on record %d" % (ok, bad, len(gone), time.time() - t0, len(done)), flush=True)


if __name__ == "__main__":
    main()
