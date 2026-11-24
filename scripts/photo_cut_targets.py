# -*- coding: utf-8 -*-
"""Targets for transparent cut-outs (owner, 24 Nov 2026: in dark mode every tile on the category grey #262626, so every
visible find's main photo needs a transparent version): data/photo_cut_targets.json, read by photo_white.py --alpha.

Per visible find (not hidden: data/reported.json "hidden", data/report_overrides.json "hide"), by the main photo it shows:
  e  products/store2/<name>: a polished store photo on #FFFFFF                 -> cut out of the photo itself
  a  /img/white/store/<name>: photo_white group a                              -> the same cut, transparent
  c  /img/white/rl/<id>.webp: photo_white group c (from img/rl/<id>.webp)      -> the same cut, transparent
  d  /img/white/recut/<id>.webp: photo_white group d                           -> the same cut, transparent, with the
     white version's model, 2% limit, hand fix and forced cut (data/photo_white records)
Transparent already (not targets): products/pc, pc2, store, /img/rl, /img/fr, /img/p, /img/p2.

  python scripts/photo_cut_targets.py [--dry-run]
"""
import argparse, collections, glob, json, os, sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from catalog_common import ROOT, load_catalog, load_json, save_json  # noqa: E402

OUT = os.path.join(ROOT, "data", "photo_cut_targets.json")


def hidden_ids():
    h = set(map(str, (load_json(os.path.join(ROOT, "data", "reported.json"), {}) or {}).get("hidden") or []))
    ov = (load_json(os.path.join(ROOT, "data", "report_overrides.json"), {}) or {}).get("hide") or []
    return h | set(map(str, ov if isinstance(ov, list) else list(ov)))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--dry-run", action="store_true"); a = ap.parse_args()
    recs = {}
    for f in glob.glob(os.path.join(ROOT, "data", "photo_white", "*.json")):
        for k, r in (load_json(f, {}).get("items") or {}).items():
            if r.get("ok") and r.get("file"): recs["/" + r["file"]] = r
    hid = hidden_ids()
    out, other = [], collections.Counter()
    for p in load_catalog()[1]:
        i, u = p["id"], p.get("img") or ""
        if i in hid: continue
        path = u[u.index("/img/"):].split("?")[0] if "/img/" in u and "supabase" not in u else ""
        if "/storage/v1/object/public/products/store2/" in u:
            out.append({"id": i, "group": "e", "live": u})
        elif path.startswith(("/img/white/recut/", "/img/white/store/", "/img/white/rl/")):
            r = recs.get(path)
            if not r: other["white photo without its record"] += 1; continue
            t = {"id": i, "live": u, "model": r.get("model")}
            if path.startswith("/img/white/recut/"):
                t.update(group="d", old=r["old"])
                for k in ("lost_max", "forced", "hand_fix"):
                    if r.get(k): t[k] = r[k]
            elif path.startswith("/img/white/store/"):
                t.update(group="a", name=path.rsplit("/", 1)[1])
            else:
                t.update(group="c", path=f"img/rl/{i}.webp")
            out.append(t)
        else:
            other["transparent already: " + ("supabase " + u.split("/products/")[1].split("/")[0] if "/products/" in u else "/".join(path.split("/")[:3]))] += 1
    c = collections.Counter(t["group"] for t in out)
    print("targets", len(out), dict(sorted(c.items())), "| not targets", dict(other.most_common()))
    if not a.dry_run:
        save_json(OUT, {"made": datetime.now(timezone.utc).strftime("%Y-%m-%d"), "items": out,
                        "how": "photo_cut_targets.py: e store2 photo with background, a/c/d white composites of photo_white"})


if __name__ == "__main__":
    main()
