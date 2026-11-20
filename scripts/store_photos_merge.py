# -*- coding: utf-8 -*-
"""Merge every shard's store photos (data/store_photos/<k>-of-<n>/store_photos.json, see store_photos_shards.py) into
data/store_photos.json, for the later apply step and the review sheets. Run any time; the shards keep their own files.

data/store_photos.json keeps its own "spent_usd" (what the runs that wrote it spent), so the global budget, which sums
the top-level file and every shard file, never counts a shard twice; "spent_usd_all" is the merged total, for reading.

  python scripts/store_photos_merge.py
"""
import json, os, sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import store_photos_shards as shards  # noqa: E402


def main():
    top_path = shards.path("log", (0, 1))
    try:
        top = json.load(open(top_path, encoding="utf-8"))
    except Exception:
        top = {"items": {}, "spent_usd": 0.0}
    files = shards.files("log")[1:]
    for p in files:
        d = json.load(open(p, encoding="utf-8"))
        top.setdefault("items", {}).update(d.get("items") or {})
    top["spent_usd_all"] = round(shards.spent_all(), 4)
    top["merged_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    tmp = top_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(top, f, ensure_ascii=False, indent=1, sort_keys=True); f.write("\n")
    os.replace(tmp, top_path)
    items = top["items"]
    with_main = sum(1 for r in items.values() if r.get("main"))
    print(f"merged {len(files)} shard files: {len(items)} finds ({with_main} with a main photo), "
          f"AI spend all runs {top['spent_usd_all']:.2f} USD")


if __name__ == "__main__":
    main()
