# -*- coding: utf-8 -*-
"""Hide finds whose main photo is bad (owner, 12 Nov 2026: "NO bad image from now on").

A find is hidden when the vision labels (data/catalog_ai.json "items", written by catalog_ai.py) say its photo shows
one of the problems below, which a cut-out can't fix:
  worn_by_person, hand_in_photo, packaging_or_box, collage_or_grid, text_or_watermark, blurry_or_low_res
(or the older flags has_text_or_watermark / is_collage).
A find comes back by itself as soon as it shows a different photo than the one that was labelled: a seller photo
(img/p2/, scripts/seller_photos.py + apply_seller_photos.py, switched in automatically), or any other new main photo.
The owner can always put a find back with "keep" in data/report_overrides.json.

Writes data/photo_hidden.json {"updated", "rule", "hidden": [ids], "why": {id: [issues]}}. bake_reports.py merges it
into data/reported.json "hidden" (by: "photo"), which the app, the server cards and the product pages already honour.

Also hides duplicates: the same item listed more than once (same brand, title and price) keeps only its best listing
(see dupes()).

  python scripts/photo_hide.py [--dry-run]
"""
import argparse, json, os, sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from catalog_common import ROOT, load_catalog  # noqa: E402

OUT = os.path.join(ROOT, "data", "photo_hidden.json")
AI = os.path.join(ROOT, "data", "catalog_ai.json")
BAD = ["worn_by_person", "hand_in_photo", "packaging_or_box", "collage_or_grid", "text_or_watermark", "blurry_or_low_res"]


def load(path, default):
    try:
        with open(path, encoding="utf-8") as f: return json.load(f)
    except Exception:
        return default


def decide(items, labels):
    """Pure: items = catalogue finds, labels = catalog_ai.json "items". Returns {id: [issues]} for the finds to hide."""
    why = {}
    for p in items:
        pid = str(p.get("id"))
        lab = labels.get(pid)
        if not isinstance(lab, dict): continue
        img = p.get("img") or ""
        if "/img/p2/" in img: continue                        # a seller photo replaced the labelled one
        issues = [i for i in (lab.get("photo_issues") or []) if i in BAD]
        if lab.get("has_text_or_watermark") and "text_or_watermark" not in issues: issues.append("text_or_watermark")
        if lab.get("is_collage") and "collage_or_grid" not in issues: issues.append("collage_or_grid")
        if issues: why[pid] = issues
    return why


def dupes(items, gone, swapped, pq, views):
    """Pure: the same item listed more than once (same brand, title and price) keeps only its best listing (owner,
    12 Nov 2026). Best = a partner swap first, then the cleaner photo (data/photo_quality.json, lower is better), then
    more views in 30 days, then the lowest id. Finds already gone (dead, hidden, bad photo) don't compete.
    Returns {id: ["duplicate"]} for the others."""
    groups = {}
    for p in items:
        pid = str(p.get("id"))
        if pid in gone: continue
        try: price = round(float(p.get("price") or 0))
        except Exception: price = 0
        key = ((p.get("brand") or "").strip().lower(), (p.get("title") or "").strip().lower(), price)
        if not key[1]: continue
        groups.setdefault(key, []).append(pid)
    out = {}
    for ids in groups.values():
        if len(ids) < 2: continue
        ids.sort(key=lambda i: (0 if i in swapped else 1, pq.get(i, 0), -views.get(i, 0), i))
        for i in ids[1:]:
            if i not in swapped: out[i] = ["duplicate"]
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--dry-run", action="store_true"); a = ap.parse_args()
    _, items, _, _ = load_catalog()
    labels = (load(AI, {}) or {}).get("items") or {}
    if not labels:
        print("no labels, nothing written"); return 0
    why = decide(items, labels)
    lh = load(os.path.join(ROOT, "data", "link_health.json"), {}) or {}
    ov = load(os.path.join(ROOT, "data", "report_overrides.json"), {}) or {}
    rp = load(os.path.join(ROOT, "data", "reported.json"), {}) or {}
    gone = set(map(str, lh.get("dead") or [])) | set(map(str, ov.get("hide") or [])) | set(why)
    gone |= {str(x.get("id")) for x in (rp.get("items") or []) if isinstance(x, dict) and x.get("by") == "reports"}
    swapped = set(map(str, ((load(os.path.join(ROOT, "data", "link_swaps.json"), {}) or {}).get("swaps") or {})))
    pq = {str(k): v for k, v in ((load(os.path.join(ROOT, "data", "photo_quality.json"), {}) or {}).get("bad") or {}).items()}
    views = {str(k): (v[1] if isinstance(v, list) and len(v) > 1 else 0) for k, v in ((load(os.path.join(ROOT, "data", "stats.json"), {}) or {}).get("p") or {}).items()}
    why.update(dupes(items, gone, swapped, pq, views))
    for pid in swapped: why.pop(pid, None)            # a partner-swapped find is never hidden (owner: the ones we want people to buy)
    counts = {}
    for v in why.values():
        for i in v: counts[i] = counts.get(i, 0) + 1
    print("hide %d of %d finds (%d labelled): %s" % (len(why), len(items), len(labels), json.dumps(counts, sort_keys=True)))
    if a.dry_run: return 0
    out = {"updated": datetime.now(timezone.utc).replace(microsecond=0).isoformat(), "rule": BAD,
           "hidden": sorted(why), "why": {k: why[k] for k in sorted(why)}}
    old = load(OUT, {})
    if isinstance(old, dict) and old.get("hidden") == out["hidden"] and old.get("why") == out["why"]:
        print("unchanged"); return 0
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f: json.dump(out, f, separators=(",", ":"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
