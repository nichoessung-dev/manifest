#!/usr/bin/env python3
"""One-time import of the RepLibrary finds (shared with written permission) into the catalogue.

scripts/rl_import.json lists the new finds: catalogue rows exactly as index.html stores them, plus "src", the public
RepLibrary photo they come with. For each find this script
  1. copies the photo into the site as img/rl/<id>.webp (same conversion as mirror_photos.py: WebP, at most 1600 px,
     quality 82, transparency kept), one request at a time with a pause, one retry, then skipped until the next run;
  2. adds the row (without "src") to the pc-catalog block in index.html, but only once its photo is in img/rl and
     only when the id is not in the catalogue yet. Existing rows are never touched (a surgical append, no reformat).
Safe to run again: finds already in the catalogue and photos already copied are skipped. Run until "left 0".

  python scripts/import_rl.py [--max-minutes 40] [--pause 0.3] [--limit N] [--dry-run]
The Import RepLibrary finds workflow runs it, then gen_catalog.py and sync_catalog.py, and commits.
"""
import argparse, io, json, os, sys, time, urllib.request

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TAG = '<script type="application/json" id="pc-catalog">'
LIST = os.path.join(ROOT, "scripts", "rl_import.json")
IMG_DIR = os.path.join(ROOT, "img", "rl")
UA = {"User-Agent": "Mozilla/5.0 (compatible; PuroClassicoImport/1.0; +https://www.puroclassico.com)"}
MAX_SIDE, QUALITY = 1600, 82      # same as scripts/mirror_photos.py
MAX_FILES = 19500                 # Cloudflare Pages allows 20,000 files per deployment


def shrink(data):
    im = Image.open(io.BytesIO(data))
    im.load()
    if im.mode not in ("RGB", "RGBA"):
        im = im.convert("RGBA" if "A" in im.getbands() or im.mode == "P" or "transparency" in im.info else "RGB")
    if im.mode == "RGBA" and im.getchannel("A").getextrema() == (255, 255):
        im = im.convert("RGB")
    if max(im.size) > MAX_SIDE:
        im.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)
    o = io.BytesIO()
    im.save(o, "WEBP", quality=QUALITY, method=5)
    return o.getvalue()


def fetch(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as r:
        ct = r.headers.get("content-type") or ""
        body = r.read()
    if not ct.startswith("image/") or len(body) < 200:
        raise ValueError("not an image (%s)" % ct)
    return body


def repo_files():
    n = 0
    for dp, dn, fn in os.walk(ROOT):
        dn[:] = [d for d in dn if d not in (".git", ".github")]
        n += len(fn)
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-minutes", type=float, default=40)
    ap.add_argument("--pause", type=float, default=0.3)
    ap.add_argument("--limit", type=int, default=0, help="new photos this run at most (0 = no limit)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    rows = json.load(open(LIST, encoding="utf-8"))
    path = os.path.join(ROOT, "index.html")
    html = open(path, encoding="utf-8").read()
    i = html.find(TAG)
    if i < 0:
        sys.exit("pc-catalog block not found in index.html")
    s = i + len(TAG)
    e = html.find("</script>", s)
    raw = html[s:e]
    have = {str(p["id"]) for p in json.loads(raw)}
    todo = [r for r in rows if str(r["id"]) not in have]
    need = [r for r in todo if not os.path.exists(os.path.join(IMG_DIR, r["id"] + ".webp"))]
    files = repo_files()
    print("import list %d, already in catalogue %d, to add %d, photos to copy %d, site files now %d"
          % (len(rows), len(rows) - len(todo), len(todo), len(need), files))
    if files + len(need) > MAX_FILES:
        sys.exit("stopping: %d more photos would pass the Cloudflare Pages file limit" % len(need))
    if a.dry_run:
        return

    os.makedirs(IMG_DIR, exist_ok=True)
    t0, done, failed = time.time(), 0, []
    for r in need:
        if time.time() - t0 > a.max_minutes * 60 or (a.limit and done >= a.limit):
            print("time or count limit reached; the next run goes on")
            break
        dest = os.path.join(IMG_DIR, r["id"] + ".webp")
        err = ""
        for attempt in (1, 2):
            try:
                out = shrink(fetch(r["src"]))
                open(dest + ".part", "wb").write(out)
                os.replace(dest + ".part", dest)
                done += 1
                err = ""
                break
            except Exception as ex:  # noqa: BLE001 (logged, retried next run)
                err = str(ex)[:120]
                time.sleep(3)
        if err:
            failed.append(r["id"])
            if len(failed) <= 30:
                print("  photo failed", r["id"], err)
        time.sleep(a.pause)
        if done and done % 200 == 0:
            print("  %d photos copied, %d failed, %.0f s" % (done, len(failed), time.time() - t0))

    add = [{k: v for k, v in r.items() if k != "src"} for r in todo
           if os.path.exists(os.path.join(IMG_DIR, r["id"] + ".webp"))]
    if add:
        body = raw.rstrip()
        if not body.endswith("]"):
            sys.exit("unexpected end of the pc-catalog block")
        extra = json.dumps(add, ensure_ascii=False, separators=(",", ":"))[1:-1].replace("</", "<\\/")
        new_raw = body[:-1] + ("," if body[:-1].strip() != "[" else "") + extra + "]"
        json.loads(new_raw)    # still valid JSON
        open(path, "w", encoding="utf-8").write(html[:s] + new_raw + html[e:])
    left = len(todo) - len(add)
    print("done: %d photos copied, %d failed; %d finds added to index.html; left %d (%.0f s)"
          % (done, len(failed), len(add), left, time.time() - t0))


if __name__ == "__main__":
    main()
