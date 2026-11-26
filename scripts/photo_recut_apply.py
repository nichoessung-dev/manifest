# -*- coding: utf-8 -*-
"""Switch the last light-tile finds to their new transparent cut-outs (owner, 26 Nov 2026: in dark mode every find on the
category grey #262626; the photos still on a light tile were the store photos on white, the white composites, a few
plain photos and the img/fr cut-outs the review of 25 Nov 2026 found half see-through or not cut out).

data/photo_recut.json holds one record per target, reviewed by eye on before / after sheets (the photo on white, the
cut-out on #262626, the cut-out on the light well #F5F5F5):
  {"old": the "img" the find showed when it was cut out, "file": "img/cut/<id>-e1.webp" (img/fr finds:
   "img/fr/<id>-e1.webp"), "sha1": of that file, "source": the photo it was cut from, "model": the matte,
   "review": "ok" | "rejected", "why": the reason a rejected one keeps its light tile}
Cut-outs: BiRefNet (rembg birefnet-general) on the full-size photo, matte tidied (store_photos_polish.clean_alpha), a
hanger hook above a garment trimmed (photo_white.trim_hook), an opaque item that the matte left partly see-through
made solid well inside its outline, the backdrop taken out of the soft edge (photo_white.edge_colours) and the light
rim cleaned (photo_edge.edge_fix), RGBA WebP q92. img/fr finds are framed like import_friend.py (86% of a square).

For every record with review "ok" whose file is in the repo with that sha1 and whose find still shows "old", "img"
becomes "/<file>" (a surgical edit of the pc-catalog block, the old value logged in data/catalog_ai_applied.json, so
apply_catalog_ai.py --revert puts it back), then the derived files are made again (gen_catalog.py,
sync_catalog.py --no-thumbs). The grey rule knows the addresses: CUT_RX in functions/_lib/photo_tiles.js and pcCut() in
index.html match /img/(rl|fr|cut)/<id>-e1.webp. Old files are kept (a Discord embed or a cached page may load them).
Without --write it reports only.

  python scripts/photo_recut_apply.py [--write]
"""
import argparse, collections, hashlib, json, os, re, subprocess, sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from catalog_common import ROOT, load_catalog, load_json, save_json  # noqa: E402
from apply_catalog_ai import object_span, set_field  # noqa: E402

RECS = os.path.join(ROOT, "data", "photo_recut.json")
LOG = os.path.join(ROOT, "data", "catalog_ai_applied.json")
FILE = re.compile(r"^img/(?:cut|fr)/[0-9]{1,15}-e1\.webp$")


def run(cmd):
    o = subprocess.run([sys.executable] + cmd, cwd=ROOT, capture_output=True, text=True)
    if o.returncode: sys.exit("%s failed: %s" % (" ".join(cmd), (o.stderr or o.stdout)[-600:]))
    return o.stdout


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--write", action="store_true"); a = ap.parse_args()
    html, items, s, e = load_catalog()
    raw, idx = html[s:e], {p["id"]: p for p in items}
    why, changes = collections.Counter(), []
    for i, r in sorted(((load_json(RECS, {}) or {}).get("items") or {}).items()):
        if r.get("review") != "ok": why["keeps a light tile (rejected in review)"] += 1; continue
        f = r.get("file") or ""
        if not FILE.match(f) or not f.endswith("/%s-e1.webp" % i): why["bad file name"] += 1; continue
        fp = os.path.join(ROOT, f)
        if not os.path.isfile(fp): why["file not in the repo"] += 1; continue
        if hashlib.sha1(open(fp, "rb").read()).hexdigest() != r.get("sha1"): why["file differs from the reviewed one"] += 1; continue
        p = idx.get(i)
        if not p: why["not in the catalogue"] += 1; continue
        if p.get("img") == "/" + f: why["already shown"] += 1; continue
        if p.get("img") != r.get("old"): why["the find shows another photo now"] += 1; continue
        changes.append((i, p.get("img"), "/" + f))
    out, failed = raw, []
    for i, old, new in changes:
        sp = object_span(out, i)
        obj = set_field(out[sp[0]:sp[1]], "img", old, new) if sp else None
        if obj is None: failed.append(i); continue
        out = out[:sp[0]] + obj + out[sp[1]:]
    after = json.loads(out)                     # same finds, same order, only "img" of the switched finds differs
    want = {i: new for i, _, new in changes if i not in failed}
    assert len(after) == len(items) and all(x["id"] == y["id"] for x, y in zip(items, after))
    for x, y in zip(items, after):
        for k in set(x) | set(y):
            if x.get(k) != y.get(k): assert k == "img" and want.get(x["id"]) == y.get(k), (x["id"], k)
    print("kept:", dict(why), "| switch %d, failed %d%s" % (len(want), len(failed), "" if a.write else " (report only)"))
    if failed: print("failed:", " ".join(failed))
    if not a.write or not want: return
    open(os.path.join(ROOT, "index.html"), "w", encoding="utf-8").write(html[:s] + out + html[e:])
    log = load_json(LOG, {"batches": []})
    log["batches"].append({"date": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "kind": "apply",
                           "changes": [{"id": i, "field": "img", "old": o, "new": n} for i, o, n in changes if i in want]})
    save_json(LOG, log)
    run(["scripts/gen_catalog.py"]); run(["scripts/sync_catalog.py", "--no-thumbs"])
    print("index.html written, derived files made again; revert: python scripts/apply_catalog_ai.py --revert "
          "data/catalog_ai_applied.json --ids <ids> --write")


if __name__ == "__main__":
    main()
