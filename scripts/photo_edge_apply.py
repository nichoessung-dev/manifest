# -*- coding: utf-8 -*-
"""Switch the finds to their cleaned cut-outs (photo_edge.py, owner 25 Nov 2026: dark tiles on #262626), in one commit.

For every reviewed record in data/photo_edge (ok and not rejected in review), with the reviewed file from the photo-edge
run's artifacts (FILES/<id>.webp, sha1 checked against the record):
  1. /img/rl and /img/fr finds: the cleaned cut-out becomes the site file img/<rl|fr>/<id>-e1.webp next to the old one
  2. apply_catalog_ai.py --edge --write switches "img": products/pc -> products/pc2/<id>-e1.webp (uploaded, sha1 in
     data/photo_edge_uploaded.json), rl/fr -> the site file. The old values go to data/catalog_ai_applied.json
  3. the derived files are made again (gen_catalog.py, sync_catalog.py --no-thumbs), as the catalogue sync does
  4. the old /img/rl and /img/fr files of the switched finds are deleted once no text file of the site or the pipeline
     names them (index.html, functions/, products.json, sitemap.xml, lab/, the root pages, scripts/, data/; history logs
     that only record old values aside). A find posted to Discord keeps its old file (the embed loads it)
  5. the photo mirror (img/m, mirror_photos.py) gets the same bytes the new pc2 objects hold, and drops the copies of the
     old pc photos that nothing wants any more, exactly as its next run would (same wanted list, same room under the file
     cap, counted after step 4), so no switched photo is served by the proxy meanwhile and the site stays under its limit
  6. data/photo_edge_applied.json records what was switched, added and deleted
Without --write it reports only and changes nothing.

  python scripts/photo_edge_apply.py FILES [--write]
  python scripts/photo_edge_apply.py --revert [--write]    put the old photos back (old values from
      data/catalog_ai_applied.json, deleted files from the commit before the one that wrote data/photo_edge_applied.json)
"""
import argparse, glob, hashlib, json, os, re, subprocess, sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from catalog_common import ROOT, load_json, save_json  # noqa: E402

LOG = os.path.join(ROOT, "data", "photo_edge_applied.json")
PC2 = "https://uptpghuduqjqmrxwatbm.supabase.co/storage/v1/object/public/products/pc2/"
HISTORY = re.compile(r"^data/(photo_white/|photo_edge/|photo_cut/|photo_white_targets\.json|photo_cut_targets\.json|"
                     r"catalog_ai_applied\.json|store_photos_applied\.json|store_photos_fixes\.json|photo_background\.json|"
                     r"friend_import\.json|photo_edge_applied\.json|photo_edge_uploaded\.json)|^scripts/rl_import\.json$")
TEXT = (".html", ".js", ".json", ".xml", ".txt", ".md", ".py", ".yml", ".css", ".sql", ".webmanifest", "_headers")
OLD = re.compile(r"img/(rl|fr)/([0-9]{1,15})\.webp")


def sha1(path):
    return hashlib.sha1(open(path, "rb").read()).hexdigest()


def run(cmd):
    o = subprocess.run([sys.executable] + cmd, cwd=ROOT, capture_output=True, text=True)
    if o.returncode: sys.exit("%s failed: %s" % (" ".join(cmd), (o.stderr or o.stdout)[-600:]))
    return o.stdout


def records():
    recs = {}
    for f in sorted(glob.glob(os.path.join(ROOT, "data", "photo_edge", "*.json"))):
        recs.update((load_json(f, {}) or {}).get("items") or {})
    return recs


def references():
    """{"img/rl/<id>.webp": {files that name it}} over every tracked text file outside img/ and the history logs."""
    files = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True).stdout.split("\n")
    refs, n = {}, 0
    for f in files:
        if not f or f.startswith(("img/", ".git/")) or HISTORY.search(f) or not f.endswith(TEXT): continue
        try: t = open(os.path.join(ROOT, f), encoding="utf-8", errors="ignore").read()
        except OSError: continue
        n += 1
        for m in OLD.finditer(t): refs.setdefault("img/%s/%s.webp" % m.groups(), set()).add(f)
    return refs, n


def seed_mirror(switched, recs, files, write):
    """img/m after the switch, as mirror_photos.py would leave it: copies of the new pc2 objects from the reviewed bytes,
    the unused copies of the old pc photos gone. Returns (added, dropped)."""
    import mirror_photos as mp
    base = os.path.join(ROOT, "img", "m")
    have = set()
    for dp, _, fn in os.walk(base):
        for f in fn: have.add("/" + os.path.relpath(os.path.join(dp, f), ROOT).replace(os.sep, "/"))
    room = mp.MAX_FILES - mp.other_files()
    want = mp.wanted_urls()[:max(room, 0)]
    keep = {p for _, p in want}
    new_urls = {PC2 + i + "-e1.webp": i for i, (o, n) in switched.items() if n.startswith(PC2)}
    old_paths = {mp.mirror_path(o) for i, (o, n) in switched.items() if n.startswith(PC2)} - {""}
    added, dropped = [], []
    for u, p in want:
        i = new_urls.get(u)
        if not i or p in have: continue
        src = os.path.join(files, i + ".webp")
        data = open(src, "rb").read()
        if hashlib.sha1(data).hexdigest() != recs[i]["sha1"]: sys.exit("sha1 differs for " + i)
        if len(data) > mp.KEEP_MAX: continue                    # the mirror makes its own copy of a big file
        if write:
            os.makedirs(os.path.dirname(os.path.join(ROOT, p.lstrip("/"))), exist_ok=True)
            open(os.path.join(ROOT, p.lstrip("/")), "wb").write(data)
        added.append(p)
    for p in sorted((have - keep) & old_paths):
        if write: os.remove(os.path.join(ROOT, p.lstrip("/")))
        dropped.append(p)
    return added, dropped


def apply(a):
    recs = records()
    sw = {i: r for i, r in recs.items() if r.get("ok") and r.get("review") != "rejected"}
    site = {i: r for i, r in sw.items() if r.get("src") in ("rl", "fr")}
    print("records %d, reviewed and ok %d (site files %d, storage %d)" % (len(recs), len(sw), len(site), len(sw) - len(site)))
    added = []
    for i, r in sorted(site.items()):
        dst = os.path.join(ROOT, "img", r["src"], i + "-e1.webp")
        src = os.path.join(a.files, i + ".webp")
        if not os.path.isfile(src): sys.exit("reviewed file missing: " + src)
        data = open(src, "rb").read()
        if hashlib.sha1(data).hexdigest() != r["sha1"]: sys.exit("sha1 differs for " + i)
        if os.path.exists(dst) and open(dst, "rb").read() != data: sys.exit("another file is already at " + dst)
        if a.write and not os.path.exists(dst): open(dst, "wb").write(data)
        added.append(os.path.relpath(dst, ROOT))
    print("site files %d%s" % (len(added), "" if a.write else " (not written)"))
    out = run(["scripts/apply_catalog_ai.py", "--edge"] + (["--write"] if a.write else []))
    print("\n".join(l for l in out.splitlines() if "cleaned edges" in l or "changes" in l))
    if not a.write:
        rep = os.path.join(ROOT, "data", "catalog_ai_apply.md")
        if os.path.exists(rep): os.remove(rep)
        return
    batch = (load_json(os.path.join(ROOT, "data", "catalog_ai_applied.json"), {}) or {}).get("batches", [])[-1]
    switched = {c["id"]: (c["old"], c["new"]) for c in batch["changes"] if c["field"] == "img" and "-e1.webp" in str(c["new"])}
    for f in added[:]:                                  # a site file whose find did not switch is not kept
        if os.path.basename(f)[:-8] not in switched:
            os.remove(os.path.join(ROOT, f)); added.remove(f)
    print("switched %d" % len(switched))
    run(["scripts/gen_catalog.py"]); run(["scripts/sync_catalog.py", "--no-thumbs"])
    refs, scanned = references()
    discord = set(map(str, load_json(os.path.join(ROOT, "discord_posted.json"), []) or []))
    deleted, kept = [], {}
    for i, (o, n) in sorted(switched.items()):
        m = re.match(r"^/img/(rl|fr)/([0-9]+)\.webp", str(o))
        if not m: continue
        p = "img/%s/%s.webp" % m.groups()
        if not os.path.exists(os.path.join(ROOT, p)): continue
        if i in discord: kept[p] = "posted to Discord (the embed loads this file)"; continue
        if p in refs: kept[p] = "still named in " + ", ".join(sorted(refs[p]))[:200]; continue
        os.remove(os.path.join(ROOT, p)); deleted.append(p)
    print("old site files: %d deleted, %d kept (%d text files scanned)" % (len(deleted), len(kept), scanned))
    seeded, dropped = seed_mirror(switched, recs, a.files, True)
    print("mirror: %d copies of the new photos added, %d unused old copies dropped" % (len(seeded), len(dropped)))
    save_json(LOG, {"at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(), "batch": batch.get("date"),
                    "switched": {i: {"old": o, "new": n} for i, (o, n) in sorted(switched.items())},
                    "site_files_added": sorted(added), "mirror_added": sorted(seeded), "mirror_dropped": sorted(dropped),
                    "old_files_deleted": sorted(deleted), "old_files_kept": kept,
                    "revert": "python scripts/photo_edge_apply.py --revert --write"})


def revert(a):
    log = load_json(LOG, {}) or {}
    ids = sorted(log.get("switched") or {})
    if not ids: sys.exit("nothing to revert")
    commit = subprocess.run(["git", "log", "-1", "--format=%H", "--diff-filter=A", "--", "data/photo_edge_applied.json"],
                            cwd=ROOT, capture_output=True, text=True).stdout.strip()
    print("%d finds back to their old photo; %d deleted files back from %s^" % (len(ids), len(log.get("old_files_deleted") or []), commit[:10]))
    if not a.write: return
    run(["scripts/apply_catalog_ai.py", "--revert", os.path.join(ROOT, "data", "catalog_ai_applied.json"), "--ids", ",".join(ids), "--write"])
    gone = [f for f in log.get("old_files_deleted") or [] if not os.path.exists(os.path.join(ROOT, f))]
    for k in range(0, len(gone), 500):
        subprocess.run(["git", "checkout", commit + "^", "--"] + gone[k:k + 500], cwd=ROOT, check=True)
    run(["scripts/gen_catalog.py"]); run(["scripts/sync_catalog.py", "--no-thumbs"])
    print("reverted; the mirror fetches the old pc photos again on its next run")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="?", default="")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--revert", action="store_true")
    a = ap.parse_args()
    if a.revert: revert(a)
    elif not a.files or not os.path.isdir(a.files): sys.exit("FILES: the folder with the reviewed <id>.webp files")
    else: apply(a)


if __name__ == "__main__":
    main()
