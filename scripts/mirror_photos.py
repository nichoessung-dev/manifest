#!/usr/bin/env python3
"""Copy the catalogue's Supabase photos into the site (img/m/...), so visitors never wait on Supabase.

functions/api/img.js serves img/m/<dir>/<name>[.v<n>].webp for
  https://uptpghuduqjqmrxwatbm.supabase.co/storage/v1/object/public/products/<dir>/<name>.webp[?v=<n>]
whenever that file exists, and only asks Supabase for photos without a copy. index.html keeps the Supabase URLs, so the
catalogue tools (clean_photos.py, apply_catalog_ai.py and its --revert) work exactly as before.

What gets copied, in this order, while the site stays under Cloudflare Pages' 20,000 file limit:
  1. the photo every find shows now ("img" in index.html, products/pc or pc2)
  2. the QC photo bank (data/qc_bank.json, products/qc)
  3. with --ready-cleaned: cleaned photos that are ready but not switched on yet (data/catalog_ai.json photos, status
     ok). Run that just before apply_catalog_ai.py --photos, so switching does not send a wave of requests to Supabase.
Copies that nothing uses any more are deleted.

Sharper photos (owner, 9 Nov 2026): copies keep the stored photo's own size up to 1600 px (the stored cut-outs are
1200 px) and its own bytes when it is already a WebP, so nothing is re-compressed. Older copies were cut to 900 px;
--upgrade N fetches N of those again, straight from Supabase (the proxy would hand back the 900 px copy), a few at a
time (one request at a time with a pause, backing off when Supabase answers 429), in catalogue order. Never enlarged and never touched by an image model: the pixels are the stored photo's.

Photos are fetched through the site's own /api/img proxy (Cloudflare edge cache first, Supabase only on a miss), a
few at a time, and the run stops early if Supabase keeps failing, so it never adds much load. Run it again until
"missing 0"; the Mirror photos workflow does that on a schedule.

  python scripts/mirror_photos.py [--limit 1500] [--upgrade 300] [--max-minutes 40] [--workers 4] [--ready-cleaned] [--dry-run]
"""
import argparse, io, json, os, re, sys, time, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TAG = '<script type="application/json" id="pc-catalog">'
SITE = "https://www.puroclassico.com"
HOST = "uptpghuduqjqmrxwatbm.supabase.co"
PUB = "https://" + HOST + "/storage/v1/object/public/products/"
UA = {"User-Agent": "Mozilla/5.0 (compatible; PuroClassicoPhotoMirror/1.0; +https://www.puroclassico.com)"}
MAX_FILES = 19000          # Cloudflare Pages allows 20,000 files per deployment; keep room for the rest of the site
MAX_SIDE, QUALITY = 1600, 82    # the stored size (1200 px cut-outs); grid thumbs and the product view are resized by Cloudflare
OLD_SIDE = 900                  # copies made before 9 Nov 2026 were cut to this; --upgrade replaces them
KEEP_MAX = 600 * 1024           # a stored WebP up to this size is copied byte for byte
PATH_RE = re.compile(r"^/storage/v1/object/public/products/(pc|pc2|qc)/([A-Za-z0-9_-]{1,80})\.webp$")


def mirror_path(url):
    """Site path for a Supabase photo URL, '' when it is not one we mirror. Same rule as mirrorPath() in img.js."""
    try:
        t = urllib.parse.urlsplit(url)
    except ValueError:
        return ""
    if t.scheme != "https" or t.hostname != HOST:
        return ""
    m = PATH_RE.match(t.path)
    if not m:
        return ""
    q = urllib.parse.parse_qs(t.query, keep_blank_values=True)
    if any(k != "v" for k in q):
        return ""
    v = (q.get("v") or [""])[0]
    if v and not re.fullmatch(r"[A-Za-z0-9_-]{1,20}", v):
        return ""
    return "/img/m/%s/%s%s.webp" % (m.group(1), m.group(2), ".v" + v if v else "")


def load_json(path, default):
    try:
        return json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError):
        return default


def wanted_urls(ready_cleaned=False):
    """Photo URLs to keep a copy of, most important first (see the module docstring)."""
    html = open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()
    i = html.find(TAG)
    if i < 0:
        sys.exit("pc-catalog block not found in index.html")
    s = i + len(TAG)
    items = json.loads(html[s:html.find("</script>", s)])
    out = [p.get("img") or "" for p in items]
    bank = (load_json(os.path.join(ROOT, "data", "qc_bank.json"), {}).get("items") or {})
    for key, v in bank.items():
        try:
            plat, fid = key.split("/", 1); n = int(v[1])
        except (ValueError, TypeError, IndexError):
            continue
        out += [PUB + "qc/%s-%s-%d.webp" % (plat, fid, k) for k in range(n)]
    if ready_cleaned:
        ids = {str(p.get("id")) for p in items}
        photos = (load_json(os.path.join(ROOT, "data", "catalog_ai.json"), {}).get("photos") or {})
        out += [PUB + "pc2/%s.webp?v=%d" % (k, int(ph.get("v") or 1)) for k, ph in photos.items()
                if k in ids and ph.get("status") == "ok" and ph.get("store") == "supabase"]
    seen, res = set(), []
    for u in out:
        p = mirror_path(u)
        if p and p not in seen:
            seen.add(p); res.append((u, p))
    return res


def other_files():
    """Files the site deploys besides the photo copies (everything outside .git, .github and img/m)."""
    n = 0
    skip = {".git", ".github", os.path.join("img", "m")}
    for dp, dn, fn in os.walk(ROOT):
        rel = os.path.relpath(dp, ROOT)
        dn[:] = [d for d in dn if os.path.normpath(os.path.join(rel, d)) not in skip]
        n += len(fn)
    return n


def shrink(data):
    """WebP at most MAX_SIDE px, keeping transparency. A WebP that already fits is kept byte for byte (no second
    compression); anything else is resized down (never up) and saved as WebP, or kept when that comes out bigger."""
    im = Image.open(io.BytesIO(data))
    if data[:4] == b"RIFF" and max(im.size) <= MAX_SIDE and len(data) <= KEEP_MAX:
        return data
    im.load()
    if im.mode not in ("RGB", "RGBA"):
        im = im.convert("RGBA" if "A" in im.getbands() or im.mode == "P" else "RGB")
    if max(im.size) > MAX_SIDE:
        im.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)
    o = io.BytesIO()
    im.save(o, "WEBP", quality=QUALITY, method=5)
    small = o.getvalue()
    if len(small) < len(data) or data[:4] != b"RIFF":
        return small
    return data


def fetch(url, direct=False):
    """Through the site's /api/img proxy (edge cache first), or straight from storage with direct=True."""
    u = url if direct else SITE + "/api/img?u=" + urllib.parse.quote(url, safe="")
    with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30) as r:
        ct = r.headers.get("content-type") or ""
        body = r.read()
    if not ct.startswith("image/") or len(body) < 200:
        raise ValueError("not an image (%s)" % ct)
    return body


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=1500, help="new copies this run at most")
    ap.add_argument("--upgrade", type=int, default=0, help="old 900 px copies to fetch again at full size this run")
    ap.add_argument("--max-minutes", type=float, default=40)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--max-fails", type=int, default=60, help="stop after this many failures in a row (Supabase struggling)")
    ap.add_argument("--ready-cleaned", action="store_true", help="also copy cleaned photos that are not switched on yet")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    base = os.path.join(ROOT, "img", "m")
    have = set()
    for dp, _, fn in os.walk(base):
        for f in fn:
            have.add("/" + os.path.relpath(os.path.join(dp, f), ROOT).replace(os.sep, "/"))

    room = MAX_FILES - other_files()
    want = wanted_urls(a.ready_cleaned)[:max(room, 0)]
    keep = {p for _, p in want}
    drop = sorted(have - keep)
    todo = [(u, p) for u, p in want if p not in have]
    old = []                                  # copies still cut to the old 900 px, catalogue order
    if a.upgrade > 0:
        for u, p in want:
            if p in have:
                try:
                    with Image.open(os.path.join(ROOT, p.lstrip("/"))) as im:
                        if max(im.size) == OLD_SIDE:
                            old.append((u, p))
                except Exception:  # noqa: BLE001 (unreadable copy: fetch it again)
                    old.append((u, p))
    print("site files outside img/m: %d, room for %d copies; wanted %d, have %d, missing %d, unused %d, old 900 px %s"
          % (MAX_FILES - room, room, len(want), len(have & keep), len(todo), len(drop), len(old) if a.upgrade > 0 else "not checked"))
    if a.dry_run:
        return

    for p in drop:
        try:
            os.remove(os.path.join(ROOT, p.lstrip("/")))
        except OSError:
            pass

    t0, done, fails, streak, kb_in, kb_out = time.time(), 0, 0, 0, 0, 0
    todo = [(u, p, False) for u, p in todo[:a.limit]]
    old = old[:a.upgrade]

    def one(job):
        u, p, direct = job
        try:
            data = fetch(u, direct)
            out = shrink(data)
            dest = os.path.join(ROOT, p.lstrip("/"))
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            tmp = dest + ".part"
            open(tmp, "wb").write(out)
            os.replace(tmp, dest)
            return len(data), len(out), ""
        except Exception as e:  # noqa: BLE001 (logged, retried next run)
            return 0, 0, "%s: %s" % (p, str(e)[:120])

    with ThreadPoolExecutor(a.workers) as ex:
        for k in range(0, len(todo), a.workers * 4):
            if time.time() - t0 > a.max_minutes * 60:
                print("time limit reached"); break
            if streak >= a.max_fails:
                print("stopping: %d failures in a row, Supabase is probably struggling; next run retries" % streak); break
            for n_in, n_out, err in ex.map(one, todo[k:k + a.workers * 4]):
                if err:
                    fails += 1; streak += 1
                    if fails <= 20: print("  failed", err)
                else:
                    done += 1; streak = 0; kb_in += n_in // 1024; kb_out += n_out // 1024
            if done and done % 200 < a.workers * 4:
                print("  %d copied (%.0f KB avg, from %.0f KB), %d failed, %.0f s" % (done, kb_out / done, kb_in / done, fails, time.time() - t0))
    # Upgrades come straight from Supabase storage, which answered 429 (too many requests) to 4 parallel workers on
    # 9 Nov 2026: one at a time, a short pause, a long pause after a 429, and stop after a few 429s (next run goes on).
    up, up_fail, n429 = 0, 0, 0
    for u, p in old:
        if time.time() - t0 > a.max_minutes * 60 or n429 >= 5:
            print("upgrade stopped early (%s)" % ("time limit" if n429 < 5 else "Supabase busy, 429")); break
        time.sleep(0.6)
        n_in, n_out, err = one((u, p, True))
        if err and "429" in err:
            n429 += 1; up_fail += 1; time.sleep(20); continue
        if err:
            up_fail += 1
            if up_fail <= 10: print("  upgrade failed", err)
            continue
        up += 1; kb_in += n_in // 1024; kb_out += n_out // 1024
    print("done: %d copied, %d failed, %d unused removed, missing %d; upgraded %d to full size (%d failed, %d old left); avg %.0f KB in %.0f s"
          % (done, fails, len(drop), max(len(todo) - done, 0), up, up_fail, max(len(old) - up, 0), kb_out / max(done + up, 1), time.time() - t0))


if __name__ == "__main__":
    main()
