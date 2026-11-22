# -*- coding: utf-8 -*-
"""Quick photo fixes from the AI ratings (owner, 22 Nov 2026: "you do this, not me").

Reads data/photo_ratings.json (scripts/rate_photos.py: photo 1 = the live main, photos 2..n = the angles in
store-gallery.json order) and writes data/store_photos_fixes.json, which scripts/apply_store_photos.py honours:

  {id: {"drop": [file names in products/store/], "main": "<file name>", "keep_old": true, "why": ..., "at": ...}}

  drop      angles the rating failed for what they show (wrong item or colour, duplicate, hanger, mannequin, tilted,
            flat-lay, tight model crop, lifestyle, label or detail shot ...). Angles that only failed on quality (soft,
            rough cut-out) stay: the polish step (scripts/store_photos_polish.py) re-cuts them, and the re-rating decides.
  main      an angle promoted to the main photo (a clean straight-on product shot; shoes: a single-shoe side profile),
            chosen by eye from contact sheets when the rated main failed. The old main is dropped unless keep_old
            (then it follows as the first angle: e.g. a pair shot behind a new single-shoe side profile).

Only finds whose rating saw exactly the live set are used (a photo that failed to load shifts the numbers). Entries are
merged: earlier drops and promotions stay unless --reset. Owner calls (data/store_photos_owner.json) win over these.

  python scripts/store_photos_fixes.py [--promote file.txt] [--reset] [--write] [--pass2]
  promote file: lines "<id> <file name> [keep]"
"""
import argparse, collections, json, os, re, sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from catalog_common import ROOT, load_json, save_json  # noqa: E402

FIXES = os.path.join(ROOT, "data", "store_photos_fixes.json")
# an angle whose issue names one of these is dropped; the rest failed on quality only (left to the polish step)
CONTENT = re.compile(
    r"differ|wrong|not the|not a |duplicate|same (shot|photo|view|angle)|near-identical|repeat|hanger|mannequin|tilt|skew|"
    r"diagonal|tight|crop|cut off|cut-off|head|flat-?lay|collage|lifestyle|on-foot|on foot|legs|hand|sole only|interior|"
    r"inside|label|tag|box|packag|close-up|closeup|detail|small in|off-cent|ai-generated|render|colou?r|version|shade|"
    r"female|women|kid|youth|another|other |mock|lying|awkward|odd|low angle|bottom|top-down|top view|floor|bed|"
    r"background|selfie|mirror|text|watermark|pile|folded|worn|dirty|stain|creas|wrinkl|deeper|darker|lighter|not white|"
    r"not blue|not black|long-sleeve|short-sleeve|main is|does not match|mismatch|rear view only|only one shoe|synthetic")


def now(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def base(n):
    """File name without the polished-copy prefix (s2/)."""
    return n[3:] if n.startswith("s2/") else n


WRONG_MAIN = re.compile(r"differ|wrong|not the|another|not a |title says|colou?r|version|shade|replica|fake|counterfeit")


def pass2(ratings, fx, owner):
    """Targets of the new search (data/store_photos_pass2.json), most viewed first: "fresh" = the rated main is another
    item than the title (searched from scratch with the title, the earlier photos never kept); "deep" = a weak set
    (few / lowq / angle / wrong / hide) whose main is still the old site photo."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from catalog_common import load_catalog
    from store_photos_collect import title_colour
    by = {p["id"]: p for p in load_catalog()[1]}
    hide = set(map(str, load_json(os.path.join(ROOT, "data", "report_overrides.json"), {}).get("hide") or []))
    order = open(os.path.join(ROOT, "data", "photo_rate_ids.txt"), encoding="utf-8").read().split()
    import store_photos_shards as shards
    log = shards.merged("log")["items"]
    out, c = {}, collections.Counter()
    for i in order:
        r, p = ratings.get(i), by.get(i)
        if not r or not p or i in hide or (fx.get(i) or {}).get("main"): continue
        t = set(r.get("tags") or [])
        m = next((x for x in r.get("photos") or [] if x.get("i") == 1), {})
        store_main = "/products/store" in (p.get("img") or "")
        col = title_colour(p.get("title"))
        if "wrong" in t and m.get("ok") is False and WRONG_MAIN.search((m.get("issue") or "").lower()):
            title = p.get("title") or ""
            brand = p.get("brand") or ""
            sa = title if brand.lower() in title.lower() else f"{brand} {title}".strip()
            words = [w for w in re.findall(r"[a-z0-9']+", sa.lower()) if w not in brand.lower().split() and w != col
                     and w not in ("t", "shirt", "tee", "hoodie", "jacket", "sweater", "pants", "shorts", "polo", "cap", "bag", "sneakers")]
            mn = (log.get(i) or {}).get("model_name") or ""
            if len(words) < 2 and mn and brand.lower() in mn.lower():   # a vague title: the name the store pick found
                sa = mn if not col or col in mn.lower() else f"{mn} {col}"
            out[i] = {"mode": "fresh", "search_as": sa,
                      "colour": col, "note": (m.get("issue") or "")[:200]}
        elif t & {"few", "lowq", "angle", "wrong", "hide"} and not store_main:
            out[i] = {"mode": "deep", "colour": col, "note": (r.get("why") or "")[:200]}
        else:
            continue
        c[out[i]["mode"]] += 1
    print("pass 2 targets:", dict(c))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--promote", default="")
    ap.add_argument("--reset", action="store_true")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--pass2", action="store_true", help="also write the new-search targets, data/store_photos_pass2.json")
    a = ap.parse_args(argv)
    ratings = load_json(os.path.join(ROOT, "data", "photo_ratings.json"), {})
    gal = load_json(os.path.join(ROOT, "store-gallery.json"), {})
    owner = {k for k in load_json(os.path.join(ROOT, "data", "store_photos_owner.json"), {}) if not k.startswith("_")}
    fx = {} if a.reset else {k: v for k, v in load_json(FIXES, {}).items() if not k.startswith("_")}
    c = collections.Counter()
    for i, r in ratings.items():
        g = [base(n) for n in gal.get(i, [])]
        if i in owner:
            c["owner call, skipped"] += 1; continue
        if r.get("n") != 1 + len(g):
            c["rating does not match the live set, skipped"] += 1; continue
        drop = []
        for p in r.get("photos") or []:
            k = p.get("i", 0)
            if k >= 2 and k - 2 < len(g) and p.get("ok") is False and CONTENT.search((p.get("issue") or "").lower()):
                drop.append(g[k - 2])
        if drop:
            e = fx.setdefault(i, {})
            new = [n for n in drop if n not in e.get("drop", [])]
            if new:
                e["drop"] = sorted(set(e.get("drop", [])) | set(new)); e["at"] = now()
                e["why"] = "; ".join(p.get("issue", "") for p in r["photos"] if p.get("i", 0) >= 2 and not p.get("ok"))[:300]
                c["finds with angles dropped"] += 1; c["angles dropped"] += len(new)
    if a.promote:
        for line in open(a.promote, encoding="utf-8"):
            w = line.split()
            if len(w) < 2: continue
            i, name = w[0], w[1]
            if i in owner: c["promote skipped (owner call)"] += 1; continue
            if name not in [base(n) for n in gal.get(i, [])] and (fx.get(i) or {}).get("main") != name:
                print("  promote: %s %s not in the live gallery" % (i, name)); continue
            e = fx.setdefault(i, {})
            e["main"] = name; e["keep_old"] = "keep" in w[2:]; e["at"] = now()
            e["drop"] = [n for n in e.get("drop", []) if n != name]
            if not e["drop"]: e.pop("drop")
            e["why_main"] = "rated main failed; angle %s is a clean straight-on product shot (reviewed on a contact sheet)" % name
            c["mains promoted"] += 1
    print(dict(c))
    print("%d finds with fixes" % len(fx))
    if a.write:
        out = {"_how": "Per-find photo fixes from the AI ratings (scripts/store_photos_fixes.py); "
                       "scripts/apply_store_photos.py honours them. drop: angle files taken off; main: angle promoted to main "
                       "(keep_old: the old main follows as first angle)."}
        out.update(dict(sorted(fx.items())))
        save_json(FIXES, out)
        print("written", os.path.relpath(FIXES, ROOT))
    if a.pass2:
        t = pass2(ratings, fx, owner)
        if a.write:
            save_json(os.path.join(ROOT, "data", "store_photos_pass2.json"), dict(
                {"_how": "Pass 2 search targets from the AI photo ratings (scripts/store_photos_fixes.py --pass2), most viewed "
                         "first. fresh: the live main is another item; search from scratch with search_as, never keep the "
                         "earlier photos. deep: a weak set with the old site photo as main. colour: the title's colour (strict)."},
                **t))
            print("written data/store_photos_pass2.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
