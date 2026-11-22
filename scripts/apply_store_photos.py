# -*- coding: utf-8 -*-
"""Put the store photos live (owner, 21 Nov 2026: "swap over the images to the real site").

Reads data/store_photos_audit.json (the second AI check, scripts/store_photos_audit.py) and the owner's own calls in
data/store_photos_owner.json, then:
  1. points "img" of every find with a new main photo at it (same surgical pc-catalog edit as apply_seller_photos.py:
     same format, same order, nothing else touched; old values logged in data/store_photos_applied.json, --revert
     puts them back where a find still shows the photo this tool set)
  2. writes functions/_lib/store_gallery.js: the extra store angles and model shots per find, shown on the product page
     (pages.js), and the set of finds whose main is now a store photo (site.js leaves their old photo-quality penalty out)

Rating fixes (data/store_photos_fixes.json, scripts/store_photos_fixes.py): angles to drop and an angle promoted to main,
from the AI photo ratings; ignored on finds with an owner call.
Owner calls: main "site" keeps the site photo as main, main "gallery0" makes angle 1 the main, drop_site never keeps
the site photo (angle 1 becomes main when the AI kept the site photo). Hidden finds (data/report_overrides.json) are
left alone. Report only unless --write.

Polished copies (scripts/store_photos_polish.py, products/store2/, pure white 1600 px) replace a store photo wherever the
polish step made and verified one; gallery entries "s2/<name>" (pages.js, index.html storeGal). --no-polish goes back.

  python scripts/apply_store_photos.py [--ids 1,2] [--write] [--no-polish] [--revert data/store_photos_applied.json]
"""
import argparse, collections, glob, json, os, re, sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from catalog_common import ROOT, load_catalog, load_json, save_json  # noqa: E402
from apply_seller_photos import edit  # noqa: E402

STORE = "https://uptpghuduqjqmrxwatbm.supabase.co/storage/v1/object/public/products/store/"
GAL_JS = os.path.join(ROOT, "functions", "_lib", "store_gallery.js")
GAL_JSON = os.path.join(ROOT, "store-gallery.json")
MAX_GAL = 8


STORE2 = STORE.replace("/products/store/", "/products/store2/")
POLISH_V = 3      # scripts/store_photos_polish.py VERSION whose results are used (3: interior same-photo check)


MODEL_SHOT = re.compile(r"-[a-z]?m\d+\.webp$")


def ok(u):
    return isinstance(u, str) and u.startswith(STORE)


def base(u):
    """The products/store/ URL of a photo, also when the site shows its polished products/store2/ copy."""
    return STORE + u[len(STORE2):] if isinstance(u, str) and u.startswith(STORE2) else u


def polished():
    """{file name: products/store2/ URL} of the store photos the polish step made AND verified: uploaded, no error,
    a store-copy source passed both same-photo checks (outline and interior), and the regression check passed
    (data/store_photos_polish_check.json: no part lost on white or ghosted items). Model shots only where a larger store
    copy was found. Finds whose rating fixes or audit changed later keep their other files."""
    out = {}
    # the regression check (scripts/store_photos_polish_check.py): white and ghosted items whose polished copy lost parts
    chk = load_json(os.path.join(ROOT, "data", "store_photos_polish_check.json"), {})
    for f in [os.path.join(ROOT, "data", "store_photos_polish.json")] + sorted(glob.glob(os.path.join(ROOT, "data", "store_photos_polish", "*.json"))):
        for r in (load_json(f, {}).get("items") or {}).values():
            if r.get("v") != POLISH_V: continue
            for name, x in (r.get("photos") or {}).items():
                if not x.get("url") or x.get("error") or x.get("upload_error") or x.get("skip"): continue
                if re.search(r"-[a-z]?m\d+\.webp$", name):   # a model shot: the same photo at a larger size, never re-cut
                    if x.get("source") != "store" or x.get("match", 0) < 0.99: continue
                elif x.get("source") == "store" and (x.get("same", 0) < 0.96 or "inside" not in x): continue
                elif not (chk.get(name) or {}).get("ok"): continue
                if x["url"] == STORE2 + name: out[name] = x["url"]
    return out


def plan(items, audit, owner, hidden, only, fixes=None, pol=None):
    """(img changes, gallery map, main set, why-not counter)."""
    fixes = fixes or {}
    pol = pol or {}
    two = lambda u: pol.get(u[len(STORE):], u) if ok(u) else u   # the polished copy where there is one
    idx = {p["id"]: p for p in items}
    changes, gal, mains, why = [], {}, set(), collections.Counter()
    for i, r in sorted(audit.items()):
        if only and i not in only:
            continue
        p = idx.get(i)
        if not p:
            why["not in the catalogue"] += 1; continue
        if i in hidden:
            why["hidden"] += 1; continue
        o = owner.get(i) or {}
        if not o and (fixes.get(i) or {}).get("audit"):
            r = fixes[i]["audit"]; why["rating fixes: earlier audit set restored"] += 1   # a pass-2 set that was worse
        main = r.get("main")
        main = main if ok(main) else None
        extra = [u for u in (r.get("gallery") or []) if ok(u)]
        model = [u for u in (r.get("model") or []) if ok(u)]
        if o.get("main") == "site" and main:
            extra.insert(0, main); main = None
        if o.get("main") == "gallery0" and extra:
            if main: extra.insert(1, main)
            main = extra.pop(0)
        if o.get("drop_site") and not main and extra:
            main = extra.pop(0)
        fx = fixes.get(i) if not o else None    # the owner's own call on a find wins over the rating fixes
        if fx:
            drops = {STORE + n for n in fx.get("drop") or []}
            if drops & set(extra + model):
                why["rating fixes: angles dropped"] += len(drops & set(extra + model))
            extra = [u for u in extra if u not in drops]
            model = [u for u in model if u not in drops]
            nm = STORE + fx["main"] if fx.get("main") else None
            if nm and nm not in drops:
                old = main or (base(p.get("img")) if ok(base(p.get("img"))) else None)
                extra = [u for u in extra if u != nm]; model = [u for u in model if u != nm]
                if fx.get("keep_old") and old and old != nm:
                    extra.insert(0, old)
                if old != nm:
                    why["rating fixes: angle promoted to main"] += 1
                main = nm
        if main and MODEL_SHOT.search(main):   # rule 8: the main is never a model photo; it goes with the model shots
            model.insert(0, main); main = None; why["model shot kept off the main"] += 1
        if not main and ok(base(p.get("img"))):
            # the site photo the audit kept is already a store photo (applied earlier): still a store main
            main = base(p.get("img")); why["kept the earlier store main"] += 1
        if main:
            mains.add(i)
            if p.get("img") != two(main):
                changes.append((i, "img", p.get("img"), two(main), "store main"))
                if two(main) != main: why["main: polished copy"] += 1
        else:
            why["kept the site photo as main"] += 1
        g = [two(u) for u in extra + model if u != main][:MAX_GAL]
        why["angles: polished copy"] += sum(1 for u in g if u.startswith(STORE2))
        if g:
            gal[i] = g
    return changes, gal, mains, why


def rel(u):
    """A gallery entry: the file name in products/store/, or "s2/<name>" for the polished copy in products/store2/."""
    return "s2/" + u[len(STORE2):] if u.startswith(STORE2) else u[len(STORE):]


def write_gallery(gal, mains):
    js = ("// GENERATED by scripts/apply_store_photos.py from data/store_photos_audit.json. Do not edit by hand.\n"
          "// SG: extra store photos per find for the product page. SG_MAIN: finds whose main photo is a store photo.\n"
          "export const SG = %s;\nexport const SG_MAIN = new Set(%s);\n"
          % (json.dumps({k: [rel(u) for u in v] for k, v in sorted(gal.items())}, separators=(",", ":")),
             json.dumps(sorted(mains), separators=(",", ":"))))
    open(GAL_JS, "w", encoding="utf-8").write(js)
    # the same angles for the app's product view (index.html storeGal()), fetched once when a find is opened
    json.dump({k: [rel(u) for u in v] for k, v in sorted(gal.items())},
              open(GAL_JSON, "w", encoding="utf-8"), separators=(",", ":"))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", default="")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--revert", default="")
    ap.add_argument("--no-polish", action="store_true", help="the products/store/ files even where a polished copy exists")
    a = ap.parse_args(argv)
    index = os.path.join(ROOT, "index.html")
    logf = os.path.join(ROOT, "data", "store_photos_applied.json")
    html, items, s, e = load_catalog(index)
    raw = html[s:e]
    only = set(a.ids.replace(" ", "").split(",")) - {""}
    audit = load_json(os.path.join(ROOT, "data", "store_photos_audit.json"), {}).get("items") or {}
    owner = {k: v for k, v in load_json(os.path.join(ROOT, "data", "store_photos_owner.json"), {}).items() if not k.startswith("_")}
    hidden = set(map(str, load_json(os.path.join(ROOT, "data", "report_overrides.json"), {}).get("hide") or []))
    fixes = {k: v for k, v in load_json(os.path.join(ROOT, "data", "store_photos_fixes.json"), {}).items() if not k.startswith("_")}

    if a.revert:
        idx = {p["id"]: p for p in items}
        changes, seen = [], set()
        for b in reversed(load_json(a.revert, {"batches": []}).get("batches", [])):
            for c in b.get("changes", []):
                i = c["id"]
                if i not in seen and (not only or i in only) and idx.get(i, {}).get("img") == c["new"]:
                    changes.append((i, "img", c["new"], c["old"], "revert")); seen.add(i)
        gal, mains, why = {}, set(), collections.Counter()
    else:
        pol = {} if a.no_polish else polished()
        changes, gal, mains, why = plan(items, audit, owner, hidden, only, fixes, pol)
    out, applied, failed = edit(raw, items, changes)
    print("%s: %d main photos switched, %d failed, %d finds with extra angles (%d photos); not switched: %s"
          % ("revert" if a.revert else "apply", len(applied), len(failed), len(gal), sum(map(len, gal.values())), dict(why)))
    for f in failed[:20]:
        print("  failed:", f)
    if not a.write:
        return 0
    if applied and out != raw:
        open(index, "w", encoding="utf-8").write(html[:s] + out + html[e:])
        log = load_json(logf, {"batches": []})
        log["batches"].append({"date": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                               "kind": "revert" if a.revert else "apply",
                               "changes": [{"id": c[0], "field": c[1], "old": c[2], "new": c[3]} for c in applied]})
        save_json(logf, log)
    write_gallery(gal, mains)
    print("written: index.html, %s, store-gallery.json, %s" % (os.path.relpath(GAL_JS, ROOT), os.path.relpath(logf, ROOT)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
