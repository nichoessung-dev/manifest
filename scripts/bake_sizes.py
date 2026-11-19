# -*- coding: utf-8 -*-
"""The size helper's data (owner, 19 Nov 2026: "make a size recomendation based on users weigth and heigth").

Merges data/listing_details.json (scripts/listing_details.py, one Listing details run) into data/sizes.json, the small file
size.js reads on product pages:
  {"v": 1, "updated": ..., "items": {id: {"s": [sizes the listing sells], "m": "flat|round|body", "c": [[size, {measure: cm}], ...]}}}
A find that was looked at but has no chart keeps only "s"; one that failed is left out so the next run tries again.
Measurements kept: height and weight ranges, chest, waist, hip, length, shoulder, inseam, foot length.

  python scripts/bake_sizes.py [--from data/listing_details.json]
"""
import argparse, json, os, re
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "sizes.json")
KEEP = {"height_min": "h0", "height_max": "h1", "weight_min": "w0", "weight_max": "w1", "chest": "ch", "waist": "wa", "hip": "hi",
        "length": "le", "shoulder": "sh", "inseam": "in", "foot_length": "ft"}
SIZE = re.compile(r"^(?:[2-6]?X{0,4}[SML]|X{1,4}[SL]|[2-6]XL|One size|Regular|\d{2}(?:\.5)?(?:[/-]\d{2}(?:\.5)?)*|\d{2,3}(?:cm)?|[A-Z]{1,3}\d{2,3})$", re.I)
ZH = {"均码": "One size", "通码": "One size", "常规": "Regular"}


def clean_size(s):
    s = str(s or "").strip()
    s = re.sub(r"[（(][^)）]*[)）]", "", s).strip()           # "XL（建议130-150斤）" -> "XL"
    s = re.sub(r"码$", "", s).strip()                           # "S码" -> "S"
    s = ZH.get(s, s)
    return s[:16] if SIZE.match(s) else ""


def compact(rec):
    sizes = []
    for x in rec.get("sizes") or []:
        c = clean_size(x)
        if c and c not in sizes: sizes.append(c)
    out = {"s": sizes[:20]}
    ch = rec.get("chart") or {}
    rows = []
    for r in ch.get("rows") or []:
        if not isinstance(r, dict) or not r.get("size"): continue
        m = {}
        for k, short in KEEP.items():
            v = r.get(k)
            try: v = float(v)
            except (TypeError, ValueError): continue
            if 0 < v < 400: m[short] = round(v, 1)
        z = clean_size(r["size"])
        if m and z and z not in [x[0] for x in rows]: rows.append([z, m])
    if len(rows) >= 2 and (ch.get("confidence") or 0.7) >= 0.5:
        out["c"] = rows[:16]
        if ch.get("measured") in ("flat", "round", "body"): out["m"] = ch["measured"]
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--from", dest="src", default=os.path.join(ROOT, "data", "listing_details.json"))
    a = ap.parse_args()
    cur = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {"v": 1, "items": {}}
    src = json.load(open(a.src, encoding="utf-8")).get("items") or {} if os.path.exists(a.src) else {}
    n = 0
    for i, rec in src.items():
        if rec.get("status") != "ok": continue
        cur["items"][str(i)] = compact(rec); n += 1
    cur["updated"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with open(OUT, "w", encoding="utf-8") as f: json.dump(cur, f, ensure_ascii=False, separators=(",", ":"))
    # what the browser reads: one small file per last two digits of the id (data/sizes/07.json), so a product page
    # downloads ~1% of the data, only when the visitor opens the size helper
    shard = os.path.join(ROOT, "data", "sizes"); os.makedirs(shard, exist_ok=True)
    parts = {}
    for i, v in cur["items"].items():
        if v.get("s") or v.get("c"): parts.setdefault(i[-2:].rjust(2, "0"), {})[i] = v
    for k in ["%02d" % n for n in range(100)]:
        with open(os.path.join(shard, k + ".json"), "w", encoding="utf-8") as f: json.dump(parts.get(k, {}), f, ensure_ascii=False, separators=(",", ":"))
    charts = sum(1 for v in cur["items"].values() if v.get("c"))
    print(f"sizes.json: {len(cur['items'])} finds ({charts} with a seller chart), {n} from this run")


if __name__ == "__main__":
    main()
