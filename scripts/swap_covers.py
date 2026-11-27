# -*- coding: utf-8 -*-
"""Give the booked Qualityfinds slideshows the new boxes covers (owner, 27 Nov 2026), then mark them so
`month_queue.py --redo` books them again in the same slot with the new cover.

  python scripts/swap_covers.py [--account second]
"""
import argparse, io, json, os, random, subprocess, sys, zipfile
from datetime import datetime, timezone
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_rug as M

ROOT = M.ROOT; STATE = os.path.join(ROOT, "month_queue.json")
ap = argparse.ArgumentParser(); ap.add_argument("--account", default="second"); a = ap.parse_args()
st = json.load(open(STATE, encoding="utf-8")); q = st["queued"]; now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M")
rows = sorted((v["at"], vid) for vid, v in q.items() if v["account"] == a.account and v["at"] > now and not v.get("manual") and v.get("rev") != "slides1-cover2")
print("booked slideshows to give the new cover:", len(rows))
out = os.path.join(ROOT, "out", "covers"); os.makedirs(out, exist_ok=True); done = 0; last = None
for i, (at, vid) in enumerate(rows):
    z = os.path.join(out, vid + ".zip")
    if subprocess.run(["gh", "release", "download", "month-content", "-p", vid + ".zip", "-D", out, "--clobber"], cwd=ROOT).returncode:
        print("::warning::could not download", vid); continue
    with zipfile.ZipFile(z) as f: files = {n: f.read(n) for n in f.namelist()}
    pk = json.loads(files["slides.json"]); name = pk.get("cover", "00.jpg")
    im, last, kg = M.cover(random.Random(vid), last, M.COVERS[i % len(M.COVERS)])
    b = io.BytesIO(); im.save(b, "JPEG", quality=94); files[name] = b.getvalue()
    with zipfile.ZipFile(z, "w", zipfile.ZIP_STORED) as f:
        for n, data in files.items(): f.writestr(n, data)
    if subprocess.run(["gh", "release", "upload", "month-content", z, "--clobber"], cwd=ROOT).returncode:
        print("::warning::could not upload", vid); continue
    q[vid]["rev"] = "slides1-cover2"; done += 1; os.remove(z)
    json.dump(st, open(STATE, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print("new cover:", vid, at, flush=True)
print("covers swapped:", done)
