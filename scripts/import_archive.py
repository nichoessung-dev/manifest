# -*- coding: utf-8 -*-
"""The Archive import (owner, 26 Nov 2026): the finds of a public Google Sheet whose items are all marked-up relistings
of one reseller store, put on the site with the ORIGINAL seller's listing instead ("we dont show the reseller links at
all find a way to find the original links", "put it with the already established archive catogory", "i want the real
links we get to rank high").

Each sheet item was matched to its original 1688 or Taobao listing by image search (a session outside this repository
searched the reseller's main photo on the agents' image search and scored every candidate photo against it). Only items
with a confirmed original go on the site: match "same photo" or "likely" with a similarity of 0.80 or more. The reseller's
ids and links never enter this repository: the staging file below holds the original listings only, and the private map
(reseller id -> original) is written next to the input CSV, outside the repository.

The flow, one stage at a time (each is safe to run again; nothing already done is done twice):
  stage    the scored CSV + the sheet's names (names.json) + the raw image-search answers (*.jsonl, for the original
           listing's main photo) -> data/archive_import.json: one entry per original listing, a catalogue row without
           its photo (platform "1688" or "taobao" and the ORIGINAL item id, the title from the sheet's name in the house
           style with its brand (scripts/archive_names.py), the sheet's category and women's tab, the original's price)
           and "src", the original listing's main photo. Left out: ids the catalogue has, the same brand + model words +
           colour as a find the site has, a price that is not a real price, an earlier duplicate check's matches (--dupes).
           Run locally (the inputs are not in the repository). New entries are added, existing ones kept.
  photos   scripts/archive_photos.py on GitHub (.github/workflows/import-archive.yml, sharded): the cut-out, the quality
           gate, Supabase products/pc2/<id>-t1.webp. -> data/archive_photos/<k>-of-<n>.json
  apply    every staged find whose cut-out is in storage is appended to the pc-catalog block of index.html (surgical
           append, existing rows untouched, never an id already there) with "ar": 1, the Archive mark: the app counts the
           find as the Archive style whatever its brand (pcStyleMatch) and ranks it right after the partner finds
           (swapFirst; the server's score() in functions/_lib/site.js, through gen_catalog.py's 16th row field).
  report   counts per stage.

  python scripts/import_archive.py stage <scored.csv> [--names names.json] [--jsonl 'dir/*.jsonl'] [--map map.json]
                                          [--dupes dupes.json] [--min-sim 0.80] [--dry-run]
  python scripts/import_archive.py apply [--set archive] [--dry-run] [--test-src-photos --out preview.html]
  python scripts/import_archive.py report [--set archive]
These are not partner finds: no swap, no partner mark.

Sets (27 Nov 2026): photos, apply, report and drop also run other imports through the same code, each with its own
stage and photo records (SETS below). "murphy" is the Da Murphy finds sheet (scripts/import_sheet.py stages it, one file
per shard in data/sheet_import/): normal finds, so apply adds them WITHOUT "ar", and checks the same brand + model words
+ colour again against the catalogue and the finds it adds (shards stage in parallel and cannot see each other).
"""
import argparse, collections, csv, glob, json, os, re, sys, time, urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from catalog_common import ROOT, CATS, load_catalog, load_json, save_json  # noqa: E402

STAGE = os.path.join(ROOT, "data", "archive_import.json")
PHOTOS_DIR = os.path.join(ROOT, "data", "archive_photos")
TAG = '<script type="application/json" id="pc-catalog">'
RATE = 7.142857          # CNY per USD, the catalogue's own rate (import_friend.py)
MIN_SIM = 0.80           # the scorer's "likely" line; "same photo" is 0.88 and up
OK_MATCH = ("same photo", "likely")
SELLER = {"1688": "1688 Marketplace", "taobao": "Taobao Marketplace"}
LINK = {"1688": re.compile(r"^https?://detail\.1688\.com/offer/(\d{6,15})\.html"),
        "taobao": re.compile(r"^https?://(?:item\.taobao\.com/item\.htm|detail\.tmall\.com/item\.htm)\?(?:[^#]*&)?id=(\d{6,15})")}
PUB = "https://uptpghuduqjqmrxwatbm.supabase.co/storage/v1/object/public/"
# the cut-out: on Supabase (the workflow's own), or a site file /img/p2/<id>.webp (made from another photo of the same
# listing and checked by hand, 27 Nov 2026)
IMG = re.compile(r"^(?:" + re.escape(PUB) + r"products/pc2/([0-9]{6,15})-t1(?:\.v[0-9a-f]{6})?\.webp|/img/p2/([0-9]{6,15})\.webp)$")
BANNED = re.compile(r"(?i)\b(replicas?|reps?|fake|batch)\b|1\s*:\s*1|[\u2014\u2013]")
PHOTO_OK = ("cut",)
# a sheet name for a group of items ("Multiple Electronics", "All Jeans Brand", "Moncler Jackets, Hoodie, Pants, etc.")
GROUP = re.compile(r"(?i)\b(multiple|various|assorted|mixed brands?|no ?name|etc)\b|^all\b.*\bbrands?\b")      # photo records that go on the site (scripts/archive_photos.py)
# the imports that run through photos and apply: the stage (one file, or a folder of shard files), the photo records,
# the mark apply gives each find, the platforms its rows may have, and whether apply checks the same model again
SETS = {"archive": {"label": "Archive", "mark": {"ar": 1}, "platforms": ("1688", "taobao"), "recheck": False},
        "murphy": {"label": "Da Murphy sheet", "stage": os.path.join(ROOT, "data", "sheet_import"),
                   "photos": os.path.join(ROOT, "data", "sheet_photos"), "mark": {}, "platforms": ("weidian", "taobao", "1688"),
                   "recheck": True, "rule": 2}}   # rule: import_sheet.py RULE; an older staged entry waits to be staged again


def now(): return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def set_of(name):
    """A set's settings; the Archive's paths are read when called (the tests point STAGE and PHOTOS_DIR elsewhere)."""
    s = dict(SETS[name]); s.setdefault("stage", STAGE); s.setdefault("photos", PHOTOS_DIR)
    return s


def staged(name="archive", every=False):
    """{id: entry} of a set's stage: its one file, or every shard file of its folder (a staged record wins, an error loses).
    Only the staged entries (a row and "src") unless every; the Archive's entries have no status: all staged."""
    path, out = set_of(name)["stage"], {}
    for f in [path] if path.endswith(".json") else sorted(glob.glob(os.path.join(path, "*.json"))):
        for k, v in ((load_json(f, {}) or {}).get("items") or {}).items():
            cur = out.get(k)
            if cur is None or v.get("status", "staged") == "staged" or cur.get("status") == "error": out[k] = v
    rule = int(SETS[name].get("rule") or 0)
    return out if every else {k: v for k, v in out.items() if v.get("row") and v.get("status", "staged") == "staged"
                              and int(v.get("rule") or 1) >= rule}


def original(link):
    """(platform, item id) of an original listing link, or (None, None)."""
    for plat, rx in LINK.items():
        m = rx.match((link or "").strip())
        if m: return plat, m.group(1)
    return None, None


def https(u):
    u = (u or "").strip()
    if u.startswith("//"): u = "https:" + u
    return u.replace("http://", "https://", 1) if u.startswith("http://") else u


def search_answers(patterns):
    """{(sheet item id, platform, item id): candidate} from the raw image-search answers. The sheet item id of a second
    pass search ("<id>#d0", "<id>#c") is the item's own."""
    out, files = {}, []
    for pat in patterns:
        files += sorted(glob.glob(pat))
    for f in dict.fromkeys(files):
        for line in open(f, encoding="utf-8"):
            line = line.strip()
            if not line: continue
            try: r = json.loads(line)
            except ValueError: continue
            sid = str(r.get("id") or "").split("#")[0]
            for key, plat in (("c1688", "1688"), ("taobao", "taobao")):
                for c in r.get(key) or []:
                    if c.get("spu") and c.get("img"):
                        out.setdefault((sid, plat, str(c["spu"])), c)
                        out.setdefault(("", plat, str(c["spu"])), c)
    return out, len(files)


def num(v):
    try: return float(str(v).replace(",", "."))
    except (TypeError, ValueError): return None


def price_of(cny):
    """Whole yuan from 10 up, one decimal below (the catalogue's 1688 prices are whole yuan; a 6.5 stays 6.5)."""
    return int(round(cny)) if cny >= 10 else round(cny, 1)


def row_problems(row, platforms=tuple(SELLER)):
    bad = []
    if not row.get("title") or len(row["title"]) > 80: bad.append("title")
    if BANNED.search(row.get("title") or "") or BANNED.search(row.get("brand") or ""): bad.append("banned word or dash")
    if row.get("cat") not in CATS: bad.append("category %r" % row.get("cat"))
    if not isinstance(row.get("price"), (int, float)) or not 5 <= row["price"] < 99999: bad.append("price %r" % row.get("price"))
    if row.get("platform") not in platforms: bad.append("platform %r" % row.get("platform"))
    if not re.fullmatch(r"[0-9]{6,15}", str(row.get("id") or "")): bad.append("id")
    return bad


def model_key(p, N):
    """(brand, model words, colour) of a find whose model words name a model, else None (the same-model check)."""
    b = N.fold(p.get("brand") or "")
    mw = N.model_words(p.get("title") or "", p.get("brand") or "") if b else ()
    if not mw or not N.distinctive(mw): return None
    return (b, mw, N.colour_in(p.get("title") or "", p.get("brand") or ""))


def visible_keys(items, N):
    """{model key: id} of every catalogue find whose model words name a model."""
    keys = {}
    for p in items:
        k = model_key(p, N)
        if k: keys.setdefault(k, p["id"])
    return keys


def stage(a):
    import archive_names as N
    if not os.path.isfile(a.csv): sys.exit("no such CSV: " + a.csv)
    here = os.path.dirname(os.path.abspath(a.csv))
    names_path = a.names or os.path.join(here, "names.json")
    names = load_json(names_path, None)
    if not isinstance(names, dict):
        print("no sheet names (%s): names and the women's tab come from the CSV, categories from the names" % names_path)
        names = {}
    pats = a.jsonl or [os.path.join(here, "*.jsonl")]
    cands, nfiles = search_answers(pats)
    map_path = os.path.abspath(a.map or os.path.join(here, "archive_map.json"))
    if map_path.startswith(os.path.abspath(ROOT) + os.sep):
        sys.exit("the private map must stay outside the repository: " + map_path)
    dupes = ((load_json(a.dupes, {}) or {}).get("items") or {}) if a.dupes else {}
    html, items, _, _ = load_catalog()
    have = {str(p["id"]) for p in items} | {str(p.get("itemId")) for p in items if p.get("itemId")}
    same_model = visible_keys(items, N)

    rows = list(csv.DictReader(open(a.csv, encoding="utf-8", newline="")))
    reseller_ids = {str(k) for k in names} | {str(r.get("id") or "").split("#")[0] for r in rows}
    reseller_ids.discard("")
    # the best confirmed original of each sheet item (a second pass may add rows for the same item)
    best = collections.OrderedDict()
    why = collections.Counter()
    for r in rows:
        sid = str(r.get("id") or "").split("#")[0]
        sim = num(r.get("similarity")) or 0.0
        if (r.get("match") or "").strip() not in OK_MATCH or sim < a.min_sim or not (r.get("original_link") or "").strip():
            if sid not in best: best.setdefault(sid, None)
            continue
        cur = best.get(sid)
        if cur is None or sim > (num(cur.get("similarity")) or 0):
            best[sid] = r
    st = load_json(STAGE, {}) or {}
    staged = st.setdefault("items", {})
    pmap = load_json(map_path, {}) or {}
    new, by_orig = 0, {}
    for sid, r in best.items():
        if r is None: why["no confirmed original"] += 1; continue
        plat, oid = original(r["original_link"])
        rec_map = {"original": (r.get("original_link") or "").strip(), "similarity": num(r.get("similarity")),
                   "match": r.get("match"), "at": now()}
        def skip(reason):
            why[reason] += 1; rec_map["status"] = "skipped: " + reason; pmap[sid] = rec_map
        if not plat: skip("original link not understood"); continue
        if oid in reseller_ids: skip("original id is a sheet id"); continue
        rec_map.update(platform=plat, id=oid)
        if oid in by_orig and by_orig[oid] != sid:
            # two sheet items, one original listing: one find, for women only when every item is on the women's tab
            skip("same original as another sheet item")
            if (names.get(sid) or {}).get("g", "w" if (r.get("tab") or "").strip() == "women" else "m") != "w" and oid in staged and oid not in have: staged[oid]["row"]["g"] = "m"
            continue
        if oid in staged:
            why["staged before"] += 1; rec_map["status"] = "staged"; pmap[sid] = rec_map; by_orig[oid] = sid; continue
        if oid in have: skip("on the site (same id)"); continue
        d = (dupes.get(sid) or {}).get("why") or ""
        if d in ("same id", "same model and colour", "photo match"): skip("on the site (%s)" % d); continue
        meta = names.get(sid) or {}
        name = (meta.get("name") or r.get("name") or "").strip()
        tabs = [t.strip() for t in (r.get("tab") or "").split(",") if t.strip()]
        women = meta.get("g") == "w" if meta.get("g") in ("w", "m") else tabs == ["women"]
        if not name: skip("no name in the sheet"); continue
        if GROUP.search(name) or (len({b for b, _, _ in N.brands_in(name)}) >= 2 and re.search(r",|/|&|\band\b", name)):
            skip("the sheet's name is a group of items, not one find"); continue
        c = cands.get((sid, plat, oid)) or cands.get(("", plat, oid))
        if not c or not c.get("img"): skip("no photo of the original"); continue
        if re.search(r"(?i)weidian|geilicdn", c["img"]): skip("photo on the reseller's host"); continue
        otitle = c.get("t") or r.get("original_title") or ""   # the original listing's own title (English)
        cny = num(r.get("original_cny"))
        if cny is None: cny = num(c.get("cny"))
        if cny is None or not 5 <= cny < 99999: skip("no real price"); continue
        rcny = num(r.get("reseller_cny"))
        if rcny and cny > 2.0 * rcny: skip("original price above twice the sheet's"); continue
        if rcny and cny < 0.06 * rcny: skip("original price looks like a part or a deposit"); continue
        cat = meta.get("cat") if meta.get("cat") in CATS else (N.guess_cat(name) or N.guess_cat(otitle))
        if cat not in CATS: skip("no category"); continue
        # a name without an item word ("Havaianas") takes the original listing's own, when it fits the category
        item = "" if N.ITEM_WORDS.search(name) else N.item_in(otitle)
        if item and N.guess_cat(item) != cat: item = ""
        title = N.house_title(name, item=item, cat=cat)
        brand = N.find_brand(" ".join(N.clean_words(name)))[0]
        if not brand and item: brand = N.find_brand(title)[0]
        price = price_of(cny)
        row = {"id": oid, "platform": plat, "cat": cat, "brand": brand, "title": title, "price": price,
               "usd": round(price / RATE, 2), "qc": 0, "seller": SELLER[plat], "rating": 0, "views": 0,
               "variants": [["Standard", price]], "g": "w" if women else "m"}
        bad = row_problems(row)
        if bad: skip("; ".join(bad)); continue
        key = model_key(row, N)
        if key and key in same_model: skip("on the site (same model and colour)"); continue
        staged[oid] = {"row": row, "src": https(c["img"]), "match": r.get("match"),
                       "similarity": num(r.get("similarity")), "staged": now()}
        by_orig[oid] = sid
        rec_map["status"] = "staged"; pmap[sid] = rec_map
        new += 1; why["staged now"] += 1
    st["about"] = ("The Archive import (scripts/import_archive.py): original 1688 / Taobao listings of the sheet's items, "
                   "each a catalogue row without its photo plus 'src', the original listing's main photo. Original "
                   "listings only.")
    st["at"] = now()
    text = json.dumps(st, ensure_ascii=False, indent=1, sort_keys=True)
    # never a reseller id or link in the repository (owner, 26 Nov 2026)
    leak = sorted(set(re.findall(r"\d{6,}", text)) & reseller_ids)
    if leak or re.search(r"(?i)weidian|geilicdn|shop\d{6,}", text):
        sys.exit("stopping: the staging file would hold a reseller id or link (%s)" % ", ".join(sorted(leak)[:5]))
    print("archive stage: CSV rows %d (%d sheet items), search answers from %d files; staged now %d, staged in all %d; %s"
          % (len(rows), len(best), nfiles, new, len(staged), dict(why.most_common())), flush=True)
    print("  by category: %s; women's tab %d; by platform: %s" % (
        dict(collections.Counter(v["row"]["cat"] for v in staged.values()).most_common()),
        sum(1 for v in staged.values() if v["row"]["g"] == "w"),
        dict(collections.Counter(v["row"]["platform"] for v in staged.values()))), flush=True)
    if a.dry_run: return
    save_json(STAGE, st)
    save_json(map_path, pmap)
    print("written %s and the private map %s" % (os.path.relpath(STAGE, ROOT), map_path), flush=True)


def photo_records(name="archive"):
    out = {}
    for f in sorted(glob.glob(os.path.join(set_of(name)["photos"], "*.json"))):
        for k, v in ((load_json(f, {}) or {}).get("items") or {}).items():
            if (out.get(k) or {}).get("status") not in PHOTO_OK: out[k] = v
    return out


def in_set(p, S, st):
    """A catalogue find of this import: it has the set's mark, or (a set without one) its id is staged by it."""
    return all(p.get(k) == v for k, v in S["mark"].items()) if S["mark"] else str(p.get("id")) in st


def apply(a):
    S = set_of(a.set)
    st = staged(a.set)
    recs = photo_records(a.set)
    path = os.path.join(ROOT, "index.html")
    html = open(path, encoding="utf-8").read()
    i = html.find(TAG)
    if i < 0: sys.exit("pc-catalog block not found in index.html")
    s = i + len(TAG); e = html.find("</script>", s); raw = html[s:e]
    have, items = set(), json.loads(raw)
    for p in items:
        have.add(str(p["id"]))
        if p.get("itemId"): have.add(str(p["itemId"]))
    keys = None
    if S["recheck"]:
        import archive_names as N
        keys = visible_keys(items, N)
    add, why = [], collections.Counter()
    for oid, v in st.items():
        if oid in have: why["in the catalogue"] += 1; continue
        rec = recs.get(oid) or {}
        if a.test_src_photos:
            url = "/api/img?u=" + urllib.parse.quote(v.get("src") or "", safe="")   # the live photo proxy (preview only)
        elif rec.get("status") in PHOTO_OK and rec.get("url"):
            url = rec["url"]
        else:
            why["photo " + (rec.get("status") or "not made yet")] += 1; continue
        row = dict(v["row"]); row["img"] = url; row.update(S["mark"])
        bad = row_problems(row, S["platforms"])
        m = IMG.match(url or "")
        if not a.test_src_photos and (not m or (m.group(1) or m.group(2)) != oid): bad.append("photo address")
        if bad: why["; ".join(bad)] += 1; print("  not added", oid, bad, row.get("title")); continue
        if keys is not None:
            k = model_key(row, N)
            if k in keys: why["same model and colour as another find"] += 1; continue
            if k: keys[k] = oid
        add.append(row); have.add(oid)
    print("%s apply: %d finds to add (%d from the women's tab); left out: %s%s" % (
        a.set, len(add), sum(1 for r in add if r["g"] == "w"), dict(why.most_common()),
        " [TEST: original photos, do not commit]" if a.test_src_photos else ""), flush=True)
    if not add or a.dry_run: return
    body = raw.rstrip()
    if not body.endswith("]"): sys.exit("unexpected end of the pc-catalog block")
    extra = json.dumps(add, ensure_ascii=False, separators=(",", ":"))[1:-1].replace("</", "<\\/")
    new_raw = body[:-1] + ("," if body[:-1].strip() != "[" else "") + extra + "]"
    json.loads(new_raw)
    out = a.out or path
    if a.test_src_photos and os.path.abspath(out) == os.path.abspath(path):
        sys.exit("--test-src-photos writes a preview copy only: give --out <file outside index.html>")
    open(out, "w", encoding="utf-8").write(html[:s] + new_raw + html[e:])
    print("%s written" % os.path.relpath(out, ROOT), flush=True)


def report(a):
    S = set_of(a.set)
    st = staged(a.set)
    recs = photo_records(a.set)
    _, items, _, _ = load_catalog()
    have = {str(p["id"]) for p in items if in_set(p, S, st)}
    c = collections.Counter()
    for oid in st:
        c["on the site" if oid in have else "photo " + ((recs.get(oid) or {}).get("status") or "not made yet")] += 1
    print("%s: staged %d; %s; %s finds in the catalogue %d" % (a.set, len(st), dict(c.most_common()), S["label"], len(have)))


def drop(a):
    """Take Archive finds off the site (a broken cut-out seen after it went live): out of the pc-catalog block, and their
    photo record marked "kept" with the reason, so apply never adds them back. Only finds marked "ar" can be dropped
    (with --set, only finds of that import)."""
    S = set_of(a.set); st = staged(a.set)
    ids = {x.strip() for x in a.csv.split(",") if x.strip()}
    path = os.path.join(ROOT, "index.html"); html = open(path, encoding="utf-8").read()
    i = html.find(TAG); s = i + len(TAG); e = html.find("</script>", s)
    rows = json.loads(html[s:e]); keep, gone = [], []
    for p in rows:
        if str(p.get("id")) in ids:
            if not in_set(p, S, st): sys.exit("%s is not a find of the %s import: not dropped" % (p.get("id"), S["label"]))
            gone.append(str(p["id"])); continue
        keep.append(p)
    raw = html[s:e]
    # every object's span, parsed in order (key order and nesting differ between importers), then the dropped ones cut out
    dec, k, spans = json.JSONDecoder(), raw.index("[") + 1, []
    while True:
        while raw[k] in " \n\r\t,": k += 1
        if raw[k] == "]": break
        obj, j = dec.raw_decode(raw, k); spans.append((k, j, str(obj.get("id")))); k = j
    for k, j, pid in reversed(spans):
        if pid not in gone: continue
        if raw[j:j + 1] == ",": j += 1
        elif raw[k - 1:k] == ",": k -= 1
        raw = raw[:k] + raw[j:]
    json.loads(raw)
    open(path, "w", encoding="utf-8").write(html[:s] + raw + html[e:])
    for f in glob.glob(os.path.join(S["photos"], "*.json")):
        orig = open(f).read(); d = json.loads(orig); ch = False
        for pid in gone:
            r = d.get("items", {}).get(pid)
            if r: r["status"] = "kept"; r["why"] = [a.why or "dropped after review"]; ch = True
        if ch:
            lines = orig.splitlines(); ind = len(lines[1]) - len(lines[1].lstrip()) if len(lines) > 1 else None
            open(f, "w").write(json.dumps(d, ensure_ascii=False, indent=ind) + ("\n" if orig.endswith("\n") else ""))
    print("%s drop: %d finds taken off (%s)" % (a.set, len(gone), ", ".join(gone)))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["stage", "apply", "report", "drop"])
    ap.add_argument("csv", nargs="?", default="")
    ap.add_argument("--names", default=""); ap.add_argument("--jsonl", action="append", default=[])
    ap.add_argument("--map", default=""); ap.add_argument("--dupes", default="")
    ap.add_argument("--min-sim", type=float, default=MIN_SIM)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--test-src-photos", action="store_true",
                    help="apply: use the original listing photos instead of the cut-outs (local preview only, with --out)")
    ap.add_argument("--out", default="", help="apply: write the result here instead of index.html")
    ap.add_argument("--why", default="", help="drop: the reason, kept in the photo record")
    ap.add_argument("--set", default="archive", choices=sorted(SETS), help="apply, report, drop: which import")
    a = ap.parse_args(argv)
    if a.stage == "stage":
        if a.set != "archive": ap.error("stage here is the Archive's; the %s set is staged by scripts/import_sheet.py" % a.set)
        if not a.csv: ap.error("stage needs the scored CSV")
        return stage(a)
    if a.stage == "apply": return apply(a)
    if a.stage == "drop": return drop(a)
    return report(a)


if __name__ == "__main__":
    sys.exit(main())
