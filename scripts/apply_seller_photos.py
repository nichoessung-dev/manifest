# -*- coding: utf-8 -*-
"""Show the new seller photos on the site: point "img" of every find whose seller photo is ready
(data/seller_photos.json, status ok, made by scripts/seller_photos.py) at its site file, "/img/p2/<id>.webp"
(or "/img/p2/<id>.v<n>.webp" after a redo). Same surgical edit of the pc-catalog JSON in index.html as
apply_catalog_ai.py (same format, same order, nothing else touched); report only unless --write.

Why a site path works everywhere: "img" values starting with "/" are already used by ~170 finds (/img/p/<id>.webp).
functions/_lib/site.js imgSrc() makes them absolute (https://www.puroclassico.com/img/p2/...), thumbSrc() and the
app's thumbOf()/cdnOf() put them through Cloudflare resizing (/cdn-cgi/image/width=400,.../img/p2/...),
sync_catalog.py writes them absolute into products.json (emails, Discord, Telegram), /api/qc-check and qc_ai.py read
/img/ paths from the site's own files, and mirror_photos.py leaves them alone (it only copies Supabase photos).

Every write appends the old and new values to data/seller_photos_applied.json; --revert puts the old photos back
(only where a find still shows the photo this tool set).

  python scripts/apply_seller_photos.py [--ids 1,2] [--min-confidence 0.8] [--max-changes 0] [--write]
                                        [--report out/seller_photos_apply.md] [--revert data/seller_photos_applied.json]
"""
import argparse, collections, json, os, re, sys
from datetime import datetime, timezone

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from catalog_common import ROOT, load_catalog, load_json, save_json  # noqa: E402
from apply_catalog_ai import object_span, set_field  # noqa: E402

FILE_RX = re.compile(r"^img/p2/([A-Za-z0-9_-]{1,80})(?:\.v\d{1,4})?\.webp$")


def file_ok(path):
    """The cut-out is there and looks like one: a 1200x1200 WebP with transparency."""
    try:
        with Image.open(path) as im:
            return im.format == "WEBP" and im.size == (1200, 1200) and "A" in im.getbands()
    except Exception:  # noqa: BLE001
        return False


def planned(items, store, a, only):
    """(changes, why-not counter): (id, "img", old, new, note) for every ready photo the find does not show yet."""
    idx = {p["id"]: p for p in items}
    out, why = [], collections.Counter()
    for i, r in sorted((store.get("items") or {}).items()):
        if only and i not in only:
            continue
        if r.get("status") != "ok":
            continue
        p = idx.get(i)
        if not p:
            why["not in the catalogue"] += 1; continue
        if r.get("model") in ("mock", None):
            why["mock result"] += 1; continue
        f = r.get("file") or ""
        m = FILE_RX.match(f)
        if not m or m.group(1) != i:
            why["unexpected file name"] += 1; continue
        if float(r.get("confidence") or 0) < a.min_confidence:
            why["confidence under %.2f" % a.min_confidence] += 1; continue
        if not file_ok(os.path.join(a.root, f)):
            why["file missing or not a 1200x1200 cut-out"] += 1; continue
        new = "/" + f
        if p.get("img") == new:
            why["already shown"] += 1; continue
        out.append((i, "img", p.get("img"), new, "seller photo %.2f %s" % (float(r.get("confidence") or 0), (r.get("src") or "")[-48:])))
        if a.max_changes and len(out) >= a.max_changes:
            break
    return out, why


def reverts(items, log, only):
    """Put back the old "img" of finds this tool switched, newest batch first, only where the find still shows the
    photo the batch set (a later change by hand or by another tool is left alone)."""
    idx = {p["id"]: p for p in items}
    out, seen = [], set()
    for b in reversed(log.get("batches", [])):
        if b.get("kind") != "apply":
            continue
        for c in b.get("changes", []):
            i = c["id"]
            if c.get("field") != "img" or i in seen or (only and i not in only):
                continue
            p = idx.get(i)
            if p and p.get("img") == c["new"]:
                out.append((i, "img", c["new"], c["old"], "revert")); seen.add(i)
    return out


def edit(raw, items, changes):
    """Apply the changes to the raw catalogue JSON text. Returns (new raw, applied, failed). Verifies that only the
    intended fields changed and the order and count of finds are the same."""
    applied, failed = [], []
    by_id = collections.defaultdict(list)
    for c in changes:
        by_id[c[0]].append(c)
    out = raw
    for i, cs in by_id.items():
        sp = object_span(out, i)
        if not sp:
            failed.append((i, "object not found")); continue
        obj = out[sp[0]:sp[1]]
        ok = True
        for (_, f, old, new, note) in cs:
            o2 = set_field(obj, f, old, new)
            if o2 is None:
                failed.append((i, "field %s not found exactly once" % f)); ok = False; break
            obj = o2
        if ok:
            out = out[:sp[0]] + obj + out[sp[1]:]
            applied += cs
    after = json.loads(out)
    assert len(after) == len(items) and all(x["id"] == y["id"] for x, y in zip(items, after)), "order or count changed"
    want = {(c[0], c[1]): c[3] for c in applied}
    for x, y in zip(items, after):
        for k in set(x) | set(y):
            if x.get(k) != y.get(k):
                assert (x["id"], k) in want and y.get(k) == want[(x["id"], k)], "unexpected change %s %s" % (x["id"], k)
    return out, applied, failed


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=ROOT, help="repo root the img/p2 files are relative to")
    ap.add_argument("--index", default=None)
    ap.add_argument("--store", default=None, help="default data/seller_photos.json")
    ap.add_argument("--log", default=None, help="default data/seller_photos_applied.json")
    ap.add_argument("--ids", default="")
    ap.add_argument("--min-confidence", type=float, default=0.8)
    ap.add_argument("--max-changes", type=int, default=0)
    ap.add_argument("--report", default="")
    ap.add_argument("--revert", default="", help="put back the old photos recorded in this applied log")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args(argv)
    a.index = a.index or os.path.join(a.root, "index.html")
    a.store = a.store or os.path.join(a.root, "data", "seller_photos.json")
    a.log = a.log or os.path.join(a.root, "data", "seller_photos_applied.json")

    html, items, s, e = load_catalog(a.index)
    raw = html[s:e]
    only = set(a.ids.replace(" ", "").split(",")) - {""}
    if a.revert:
        changes, why = reverts(items, load_json(a.revert, {"batches": []}), only), collections.Counter()
    else:
        changes, why = planned(items, load_json(a.store, {}), a, only)
    out, applied, failed = edit(raw, items, changes)

    kind = "revert" if a.revert else "apply"
    print("%s: %d changes, %d failed; not switched: %s" % (kind, len(applied), len(failed), dict(why) or "none"))
    L = ["# Seller photos %s (%s)" % (kind, "written" if a.write else "report only, not written"), "",
         "Changes: %d. Failed: %d. Not switched: %s." % (len(applied), len(failed),
                                                        ", ".join("%s %d" % kv for kv in why.most_common()) or "none"), "",
         "| id | old | new | note |", "|---|---|---|---|"]
    L += ["| %s | %s | %s | %s |" % (c[0], c[2], c[3], c[4].replace("|", "/")) for c in applied]
    if failed:
        L += ["", "## Not applied", ""] + ["- %s: %s" % f for f in failed]
    if a.report:
        os.makedirs(os.path.dirname(a.report) or ".", exist_ok=True)
        open(a.report, "w", encoding="utf-8").write("\n".join(L) + "\n")
    else:
        print("\n".join(L[:40]))

    if a.write and applied and out != raw:
        open(a.index, "w", encoding="utf-8").write(html[:s] + out + html[e:])
        log = load_json(a.log, {"batches": []})
        log["batches"].append({"date": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "kind": kind,
                               "changes": [{"id": c[0], "field": c[1], "old": c[2], "new": c[3]} for c in applied]})
        save_json(a.log, log)
        print("index.html written; old values logged in", a.log)
    return 0


if __name__ == "__main__":
    sys.exit(main())
