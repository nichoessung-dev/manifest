# -*- coding: utf-8 -*-
"""Upload the reviewed transparent cut-outs (photo_white.py --alpha) to Supabase storage, as NEW objects only.

For every data/photo_cut record that is ok and not rejected in review, and not uploaded before
(data/photo_cut_uploaded.json): the file img/cut/<id>.webp is taken from the artifact of the GitHub run that made it
(record "run", artifact photo-cut-*), must have the sha1 recorded at review, must be a 1600 x 1600 RGBA WebP, and goes to
its record's "object": products/pc2/<id>-t1.webp for a main photo (the folder the site's photo proxy and mirror already
serve), products/store2/<stem>-t1.webp for an extra store angle (store-gallery.json "s2/" entries), with x-upsert false: an existing object is never replaced
and nothing is deleted. The site does not change: apply_catalog_ai.py --cut switches the photos after review.
Writes data/photo_cut_uploaded.json (kept as the run's artifact and committed by hand). Needs SUPABASE_SERVICE_KEY, and
GH_TOKEN with actions: read (gh run download). No image model runs here.

  python scripts/photo_cut_upload.py [--limit 0] [--ids 1,2] [--group main|gallery|all] [--dry-run]
"""
import argparse, glob, hashlib, io, json, os, re, subprocess, sys, tempfile, time, urllib.error, urllib.request
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from catalog_common import ROOT, load_json, save_json  # noqa: E402

SUPA = "https://uptpghuduqjqmrxwatbm.supabase.co"
OBJ = re.compile(r"^products/(pc2/[0-9]{1,15}|store2/[0-9]{1,15}-[a-z]{0,2}[0-9]{1,3})-t1\.webp$")
LOG = os.path.join(ROOT, "data", "photo_cut_uploaded.json")
ID = re.compile(r"^[0-9]{1,15}$")


def records():
    out = {}
    for f in sorted(glob.glob(os.path.join(ROOT, "data", "photo_cut", "*.json"))):
        for k, r in (load_json(f, {}).get("items") or {}).items():
            if r.get("ok") and r.get("review") != "rejected" and r.get("sha1") and r.get("run") and ID.match(str(r.get("id"))):
                r = dict(r); r.setdefault("object", f"products/pc2/{r['id']}-t1.webp")
                if OBJ.match(r["object"]) and re.fullmatch(r"img/cut/(g/)?[0-9A-Za-z_-]{1,40}\.webp", r.get("file", "")): out[k] = r
    return out


def download(run, dest):
    repo = os.environ.get("GITHUB_REPOSITORY", "nichoessung-dev/manifest")
    if not re.fullmatch(r"[0-9]{1,15}", str(run)): raise ValueError("bad run id")
    subprocess.run(["gh", "run", "download", str(run), "-R", repo, "-p", "photo-cut-*", "-D", dest], check=True,
                   stdout=subprocess.DEVNULL)


def find(dest, rel):
    for f in glob.glob(os.path.join(dest, "*", rel)) + glob.glob(os.path.join(dest, rel)):
        return f
    return None


def check(data):
    from PIL import Image
    im = Image.open(io.BytesIO(data)); im.load()
    if data[:4] != b"RIFF" or im.format != "WEBP": return "not a WebP"
    if im.mode != "RGBA": return f"mode {im.mode}"
    if im.size != (1600, 1600): return f"size {im.size}"
    if im.getchannel("A").getextrema()[0] != 0: return "nothing transparent"
    return ""


def upload(path, data):
    key = os.environ["SUPABASE_SERVICE_KEY"]
    req = urllib.request.Request(SUPA + "/storage/v1/object/" + path, data=data, method="POST", headers={
        "Authorization": "Bearer " + key, "apikey": key, "Content-Type": "image/webp",
        "x-upsert": "false", "Cache-Control": "max-age=31536000"})
    try:
        urllib.request.urlopen(req, timeout=60).read(); return "uploaded"
    except urllib.error.HTTPError as e:
        body = e.read()[:200].decode("utf-8", "replace")
        if e.code in (400, 409) and ("Duplicate" in body or "already exists" in body or "409" in body): return "exists"
        raise RuntimeError(f"{e.code} {body}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--ids", default="")
    ap.add_argument("--group", default="all", choices=["main", "gallery", "all"])
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    only = set(a.ids.replace(" ", "").split(",")) - {""}
    log = load_json(LOG, {"items": {}}); log.setdefault("items", {})
    todo = {k: r for k, r in records().items() if k not in log["items"] and (not only or r["id"] in only)
            and (a.group == "all" or (a.group == "gallery") == (r.get("group") == "g"))}
    ids = sorted(todo)[:a.limit] if a.limit else sorted(todo)
    print(f"photo_cut_upload: {len(ids)} to upload ({len(log['items'])} before){' (dry run)' if a.dry_run else ''}", flush=True)
    by_run = {}
    for i in ids: by_run.setdefault(todo[i]["run"], []).append(i)
    stats = {"uploaded": 0, "exists": 0, "failed": 0}
    with tempfile.TemporaryDirectory() as tmp:
        for run, rids in sorted(by_run.items()):
            dest = os.path.join(tmp, str(run))
            try:
                download(run, dest)
            except Exception as e:
                print(f"run {run}: artifact not readable ({str(e)[:100]}); {len(rids)} skipped", flush=True)
                stats["failed"] += len(rids); continue
            for i in rids:
                r = todo[i]; f = find(dest, r["file"])
                if not f: print(f"{i}: not in run {run}'s artifact", flush=True); stats["failed"] += 1; continue
                data = open(f, "rb").read()
                if hashlib.sha1(data).hexdigest() != r["sha1"]:
                    print(f"{i}: sha1 differs from the reviewed file", flush=True); stats["failed"] += 1; continue
                bad = check(data)
                if bad: print(f"{i}: {bad}", flush=True); stats["failed"] += 1; continue
                path = r["object"]
                if a.dry_run:
                    print(f"{i}: would upload {path} ({len(data) // 1024} KB)", flush=True); continue
                try:
                    res = upload(path, data)
                except Exception as e:
                    print(f"{i}: upload failed: {str(e)[:120]}", flush=True); stats["failed"] += 1; continue
                stats[res] += 1
                if res == "uploaded":
                    log["items"][i] = {"object": path, "sha1": r["sha1"], "kb": len(data) // 1024,
                                       "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "from_run": run}
                else:
                    print(f"{i}: {path} exists already (left as it is)", flush=True)
                time.sleep(0.15)
    if not a.dry_run:
        save_json(LOG, log)
    print("summary:", json.dumps(stats), flush=True)
    return 1 if stats["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
