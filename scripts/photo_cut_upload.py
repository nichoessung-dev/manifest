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

--set edge (owner, 25 Nov 2026): the existing cut-outs with their light outline cleaned (photo_edge.py, data/photo_edge,
img/edge/<id>.webp at the source's own size, artifact photo-edge-*) to products/pc2/<id>-e1.webp, the same way; their log
is data/photo_edge_uploaded.json.

  python scripts/photo_cut_upload.py [--set cut|edge] [--limit 0] [--ids 1,2] [--group main|gallery|all] [--dry-run]
"""
import argparse, glob, hashlib, io, json, os, re, subprocess, sys, tempfile, time, urllib.error, urllib.request
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from catalog_common import ROOT, load_json, save_json  # noqa: E402

SUPA = "https://uptpghuduqjqmrxwatbm.supabase.co"
SETS = {"cut": {"state": "photo_cut", "log": "photo_cut_uploaded.json", "artifact": "photo-cut-*",
               "obj": re.compile(r"^products/(pc2/[0-9]{1,15}|store2/[0-9]{1,15}-[a-z]{0,2}[0-9]{1,3})-t1\.webp$"),
               "file": re.compile(r"img/cut/(g/)?[0-9A-Za-z_-]{1,40}\.webp"), "size": (1600, 1600)},
        "edge": {"state": "photo_edge", "log": "photo_edge_uploaded.json", "artifact": "photo-edge-*",
                 "obj": re.compile(r"^products/pc2/[0-9]{1,15}-e1\.webp$"),
                 "file": re.compile(r"img/edge/[0-9]{1,15}\.webp"), "size": None}}
SET = SETS["cut"]
LOG = os.path.join(ROOT, "data", SET["log"])
ID = re.compile(r"^[0-9]{1,15}$")


def records():
    out = {}
    for f in sorted(glob.glob(os.path.join(ROOT, "data", SET["state"], "*.json"))):
        for k, r in (load_json(f, {}).get("items") or {}).items():
            if r.get("site"): continue   # edge set: an /img/rl or /img/fr find gets a site file next to the old one, not an object
            if r.get("ok") and r.get("review") != "rejected" and r.get("sha1") and r.get("run") and ID.match(str(r.get("id"))):
                r = dict(r); r.setdefault("object", f"products/pc2/{r['id']}-t1.webp")
                if SET["obj"].match(r["object"]) and SET["file"].fullmatch(r.get("file", "")): out[k] = r
    return out


def download(run, dest):
    repo = os.environ.get("GITHUB_REPOSITORY", "nichoessung-dev/manifest")
    if not re.fullmatch(r"[0-9]{1,15}", str(run)): raise ValueError("bad run id")
    subprocess.run(["gh", "run", "download", str(run), "-R", repo, "-p", SET["artifact"], "-D", dest], check=True,
                   stdout=subprocess.DEVNULL)


def find(dest, rel):
    for f in glob.glob(os.path.join(dest, "*", rel)) + glob.glob(os.path.join(dest, rel)):
        return f
    return None


def check(data, size=None):
    from PIL import Image
    im = Image.open(io.BytesIO(data)); im.load()
    if data[:4] != b"RIFF" or im.format != "WEBP": return "not a WebP"
    if im.mode != "RGBA": return f"mode {im.mode}"
    if SET["size"] and im.size != SET["size"]: return f"size {im.size}"
    if size and list(im.size) != list(size): return f"size {im.size}, recorded {size}"
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


def same_remote(path, sha1):
    """An object that exists already: True when the public copy is this very file (a re-run after an interrupted upload)."""
    try:
        data = urllib.request.urlopen(SUPA + "/storage/v1/object/public/" + path, timeout=60).read()
        return hashlib.sha1(data).hexdigest() == sha1
    except Exception:
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--ids", default="")
    ap.add_argument("--group", default="all", choices=["main", "gallery", "all"])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--set", default="cut", choices=sorted(SETS))
    ap.add_argument("--src", default="", help="edge set: only these sources (pc, rl, fr; comma separated)")
    a = ap.parse_args()
    global SET, LOG
    SET = SETS[a.set]; LOG = os.path.join(ROOT, "data", SET["log"])
    only = set(a.ids.replace(" ", "").split(",")) - {""}
    log = load_json(LOG, {"items": {}}); log.setdefault("items", {})
    srcs = {x for x in a.src.replace(" ", "").split(",") if x}
    todo = {k: r for k, r in records().items() if k not in log["items"] and (not only or r["id"] in only)
            and (not srcs or r.get("src") in srcs)
            and (a.group == "all" or (a.group == "gallery") == (r.get("group") == "g"))}
    ids = sorted(todo)[:a.limit] if a.limit else sorted(todo)
    print(f"photo_cut_upload ({a.set}): {len(ids)} to upload ({len(log['items'])} before){' (dry run)' if a.dry_run else ''}", flush=True)
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
                bad = check(data, r.get("size"))
                if bad: print(f"{i}: {bad}", flush=True); stats["failed"] += 1; continue
                path = r["object"]
                if a.dry_run:
                    print(f"{i}: would upload {path} ({len(data) // 1024} KB)", flush=True); continue
                try:
                    res = upload(path, data)
                except Exception as e:
                    print(f"{i}: upload failed: {str(e)[:120]}", flush=True); stats["failed"] += 1; continue
                if res == "exists" and same_remote(path, r["sha1"]): res = "uploaded"; stats["exists"] += 1
                else: stats[res] += 1
                if res == "uploaded":
                    log["items"][i] = {"object": path, "sha1": r["sha1"], "kb": len(data) // 1024,
                                       "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "from_run": run}
                else:
                    print(f"{i}: {path} exists already with other bytes (left as it is)", flush=True)
                if not a.dry_run and sum(stats.values()) % 250 == 0: save_json(LOG, log)   # an interrupted run keeps its log
                time.sleep(0.15)
    if not a.dry_run:
        save_json(LOG, log)
    print("summary:", json.dumps(stats), flush=True)
    return 1 if stats["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
