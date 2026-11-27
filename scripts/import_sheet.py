# -*- coding: utf-8 -*-
"""The Da Murphy finds sheet import (owner, 27 Nov 2026): about 2,600 direct seller listings of a public Google Sheet
(data/sheet_murphy_list.json: platform, item id, the sheet's name and tab, its price in GBP as a hint) put on the site as
NORMAL finds, ranked like every other find: no Archive mark, no partner swap. Rugs and room decor go under Accessories.

It runs through the Archive import's own photos and apply steps (scripts/import_archive.py SETS, set "murphy"):
  stage    this script, on GitHub (.github/workflows/import-sheet.yml; sharded like scripts/archive_photos.py, int(sha1(id))
           % n == k, so parallel runs never write the same file). Per item of the shard with no final state yet:
             1. the listing. Weidian: getItemSkuInfo (import_friend.py wd): Chinese title, main photo, colour option
                photos; the price is the cheapest real variant (scripts/price_rule.py); gone, sold-out and
                placeholder-only listings are left out. Taobao and 1688 (getItemSkuInfo is Weidian only, and never a
                shopping agent's own API): the entry of data/sheet_murphy_details.json, made by image search outside this
                script ({"items": {id: {"platform", "src": the main photo on alicdn, "title_en", "cny"}}}); the price is
                the cny, whole yuan from 10 up (import_archive.py price_of), price_rule's placeholder lines apply. An item
                without an entry waits as "needs details" and is staged once its entry is there
             2. one vision call (import_friend.py classify, claude-haiku-5-5) on the photos and the listing's title, with
                the sheet's name and tab as hints (its names are slang: "BB coat", "deputy ID zip"): the clean
                single-product photo, an English title in the house style, brand ("" when none), category (the site's
                nine; a rug or room decor is Accessories), gender, colour. The brand is spelled as the catalogue spells it
             3. the Archive stage's checks: an id the catalogue has (or another import staged), the same brand + model
                words + colour as a find on the site, a price that is not a real price (or under 6% of the sheet's)
           -> data/sheet_import/<k>-of-<n>.json, one record per item: its state, and for a staged one the catalogue row
           without its photo plus "src", the chosen photo. An item that errors 3 times is given up ("failed").
  photos   scripts/archive_photos.py --set murphy: the vision look, the cut-out, Supabase products/pc2/<id>-t1.webp
  apply    scripts/import_archive.py apply --set murphy: every staged find whose cut-out is in storage, WITHOUT "ar"; the
           same model check again (shards stage in parallel), then gen_catalog.py and sync_catalog.py --no-thumbs
  report   counts per state and step; the last line, "left N" (to stage + to photograph), is what the workflow goes on by

  python scripts/import_sheet.py stage [--shard 0/1] [--limit 0] [--max-minutes 0] [--max-usd 3] [--ids 1,2] [--dry-run]
  python scripts/import_sheet.py report
"""
import argparse, collections, json, os, re, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from catalog_common import ROOT, CATS, load_catalog, load_json, no_dash, save_json  # noqa: E402
import archive_photos as AP  # noqa: E402
import import_archive as IA  # noqa: E402
import import_friend as IF  # noqa: E402
import price_rule  # noqa: E402
import store_photos_shards as shards  # noqa: E402

SET = "murphy"
LIST = os.path.join(ROOT, "data", "sheet_murphy_list.json")
DETAILS = os.path.join(ROOT, "data", "sheet_murphy_details.json")
FINAL = ("staged", "needs details", "gone", "sold out", "no price", "badphoto", "skipped", "failed")
TRIES = 3                # an item that errors this many times is given up
OPTIONS = 5              # colour option photos the vision call sees next to the main photo
EXTRA = 8                # Weidian: the listing's gallery and description photos it also sees (a clean one may be there)
# The photo rule. 2 (owner, 27 Nov 2026): a photo with a blurred-out logo never qualifies (about 40% of the first 537
# cut-outs had one); the listing's gallery and description photos are looked at too. A "staged" or "badphoto" record of
# an older rule is staged again (never once the find is on the site).
RULE = 2
REDO = ("staged", "badphoto")
MOBILE_UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148"
GBP_CNY = 9.1            # yuan per pound, only for the sheet price check
SHOP = {"weidian": "Weidian", "taobao": "Taobao", "1688": "1688"}
ROOM_TABS = ("Rugs", "Room Decor")
ROOM = re.compile(r"(?i)\b(rugs?|carpets?|pillows?|cushions?|(room|home) decor)\b")
ALICDN = re.compile(r"^https://[\w.-]*\balicdn\.com/")


def load_list():
    return [dict(it, id=str(it["id"])) for it in (load_json(LIST, {}) or {}).get("items") or []]


def load_details():
    return {str(k): v for k, v in ((load_json(DETAILS, {}) or {}).get("items") or {}).items() if isinstance(v, dict)}


def detail_problem(it, d):
    """Why a details entry cannot be staged ('' when it can): a later file can fix it."""
    if (d.get("platform") or it["platform"]) != it["platform"]: return "details for another platform"
    if not ALICDN.match(IA.https(d.get("src"))): return "details photo not on alicdn"
    if not str(d.get("title_en") or "").strip(): return "details without a title"
    return ""


def about(it, zh="", en=""):
    """The listing's title and the sheet's hints for the vision call, in words."""
    s = ("Chinese title: " + json.dumps(zh, ensure_ascii=False) + ". ") if zh or not en else (
        "Its listing title (machine translated, may be long or wrong): " + json.dumps(en, ensure_ascii=False) + ". ")
    name = re.sub(r"(?i)\badd your name\b", " ", no_dash(it.get("sheet_name") or "")).strip(" -,.")
    s += "A finds sheet lists it under the tab " + json.dumps(it.get("section") or "")
    if name:
        s += (" and calls it " + json.dumps(name, ensure_ascii=False) + " (slang, nicknames and short brand names: use "
              "it for the brand and model only when the photos and the listing's title agree)")
    return s + ". A rug, a carpet, a pillow or other room decor is Accessories."


def house_brand(b, N):
    """The brand as the catalogue spells it (import_friend.py BRAND_FIX, then the catalogue's own list), else as named."""
    b = re.sub(r"\s+", " ", no_dash(str(b or ""))).strip()
    return (IF.BRAND_FIX.get(b.lower()) or N.find_brand(b)[0] or b) if b else ""


def weidian(it, rec):
    """The listing from getItemSkuInfo: {"price", "photos", "srcs", "words" (its title for the vision call)}, or the record
    of an item left out (it has a "status")."""
    res = IF.wd(it["id"])
    if res is None: return dict(rec, status="error", why="weidian did not answer")
    pr = price_rule.shown_price(res)
    if pr["status"] == "gone": return dict(rec, status="gone", why="listing gone")
    if pr["status"] == "sold_out": return dict(rec, status="sold out")
    if pr["status"] != "ok" or not pr["price"]: return dict(rec, status="no price", why="only placeholder prices")
    zh = res.get("itemTitle") or ""
    opts = [v for at in (res.get("attrList") or []) for v in (at.get("attrValues") or []) if v.get("img")][:OPTIONS]
    urls = [("main photo", IA.https(res.get("itemMainPic")))] + [
        ("colour option " + str(v.get("attrValue") or ""), IA.https(v["img"])) for v in opts]
    urls += more_photos(it["id"], [u for _, u in urls])
    photos, srcs = [], []
    for lab, u in urls:
        try: photos.append((lab, IF.get_img(u))); srcs.append(u)
        except Exception:   # noqa: BLE001 (an option photo that does not load is left out; the main photo must load)
            if not photos: raise
    return {"price": pr["price"], "photos": photos, "srcs": srcs, "words": {"zh": zh}}


def photo_key(u):
    """One key per photo whatever its size or format suffix (geilicdn serves x.jpg, x.jpg.webp?w=750...)."""
    return re.sub(r"(\.(?:jpe?g|png))(?:\.webp)?(?:\?.*)?$", r"\1", re.sub(r"^https?://", "", u or ""), flags=re.I)


def usable(u):
    """A product photo, not a banner, a size-chart strip or an icon: by the size geilicdn puts in the name (_W_H.ext)."""
    m = re.search(r"_(\d{2,5})_(\d{2,5})\.(?:jpe?g|png|webp)", u or "", re.I)
    if not m: return True
    w, h = int(m.group(1)), int(m.group(2))
    return min(w, h) >= 400 and 0.5 <= h / w <= 2.0


def more_photos(x, seen):
    """The listing's other photos, new ones only, at most EXTRA: the item page's gallery ("imgs") and its description's
    photos (getDetailDesc). Both answer without a login; [] when either fails (the main and option photos still go)."""
    import html as H
    import urllib.parse, urllib.request
    keys, out = {photo_key(u) for u in seen}, []

    def get(u):
        req = urllib.request.Request(u, headers={"User-Agent": MOBILE_UA, "Referer": "https://weidian.com/"})
        with urllib.request.urlopen(req, timeout=25) as r: return r.read().decode("utf-8", "ignore")

    found = []
    try:
        m = re.search(r'"imgs":\[(.*?)\]', H.unescape(get("https://weidian.com/item.html?itemID=" + x)))
        found += [("gallery photo", u) for u in re.findall(r'"(https?://[^"]+)"', m.group(1))] if m else []
    except Exception:  # noqa: BLE001
        pass
    try:
        d = json.loads(get("https://thor.weidian.com/detail/getDetailDesc/1.0?param=" + urllib.parse.quote(json.dumps({"vItemId": x}))))
        found += [("description photo", c["url"]) for c in (((d.get("result") or {}).get("item_detail") or {}).get("desc_content") or [])
                  if c.get("type") == 2 and c.get("url")]
    except Exception:  # noqa: BLE001
        pass
    for lab, u in found:
        u = IA.https(u)
        if photo_key(u) in keys or not usable(u): continue
        keys.add(photo_key(u)); out.append(("%s %d" % (lab, sum(1 for l, _ in out if l.startswith(lab)) + 1), u))
        if len(out) >= EXTRA: break
    return out


def from_file(it, d, rec):
    """The same from a details entry (Taobao, 1688): its photo, its title, its price."""
    cny = IA.num(d.get("cny"))
    if cny is None or not price_rule.MIN_REAL <= cny < price_rule.MAX_REAL:
        return dict(rec, status="no price", why="details price %r" % d.get("cny"))
    src = IA.https(d["src"])
    im = AP.fetch(src)
    if im is None: return dict(rec, status="gone", why="the details photo no longer loads")
    return {"price": IA.price_of(cny), "photos": [("main photo", im)], "srcs": [src], "words": {"en": str(d.get("title_en") or "").strip()}}


def stage_one(it, N, keys, d=None):
    """The record of one item (network: the listing or its details photo, one vision call)."""
    x, plat, rec = it["id"], it["platform"], {"at": IA.now()}
    L = weidian(it, rec) if plat == "weidian" else from_file(it, d, rec)
    if "status" in L: return L
    price, photos, srcs, words = L["price"], L["photos"], L["srcs"], L["words"]
    gbp = IA.num(it.get("sheet_gbp"))
    if gbp and price < 0.06 * gbp * GBP_CNY:
        return dict(rec, status="skipped", why="price %s looks like a part or a deposit (sheet %s GBP)" % (price, gbp))
    c = IF.classify(photos, words.get("zh", ""), None, about=about(it, **words), shop=SHOP[plat])
    if c.get("cat") not in CATS or not c.get("title"): raise RuntimeError("classification failed: " + json.dumps(c)[:120])
    k = c.get("photo")
    if not isinstance(k, int) or not 0 <= k < len(photos):
        return dict(rec, status="badphoto", why="no clean single-product photo in the listing", **words)
    raw_b = re.sub(r"\s+", " ", no_dash(str(c.get("brand") or ""))).strip()
    brand = house_brand(raw_b, N)
    title = re.sub(r"\s+", " ", no_dash(str(c["title"]))).strip()
    if raw_b and brand != raw_b and title.lower().startswith(raw_b.lower() + " "): title = brand + title[len(raw_b):]
    room = it.get("section") in ROOM_TABS or ROOM.search("%s %s" % (c.get("item") or "", title))
    colour = re.sub(r"\s+", " ", no_dash(str(c.get("colour") or ""))).strip().title()
    row = {"id": x, "platform": plat, "cat": "Accessories" if room else c["cat"], "brand": brand, "title": title,
           "price": price, "usd": round(price / IA.RATE, 2), "qc": 0, "seller": "Weidian" if plat == "weidian" else IA.SELLER[plat],
           "rating": 0, "views": 0, "variants": [[colour or "Standard", price]], "g": c.get("g") if c.get("g") in ("m", "w") else "m"}
    if plat == "weidian": row["itemId"] = x                      # as import_friend.py; the Archive's rows have none
    bad = IA.row_problems(row, IA.SETS[SET]["platforms"])
    if bad: return dict(rec, status="skipped", why="; ".join(bad), title=title)
    key = IA.model_key(row, N)
    if key and key in keys: return dict(rec, status="skipped", why="on the site (same model and colour as %s)" % keys[key], title=title)
    return dict(rec, status="staged", row=row, src=srcs[k], item=str(c.get("item") or ""), **words)


def is_done(r, x, details, on=()):
    """A final state, except "needs details" once the details file has the item, and a "staged" or "badphoto" record of an
    older photo RULE while the find is not on the site (on: the catalogue's ids)."""
    s = (r or {}).get("status")
    if s == "needs details" and x in details: return False
    if s in REDO and int((r or {}).get("rule") or 1) < RULE and x not in on: return False
    return s in FINAL


def ready(it, details):
    """The item can be staged: a Weidian listing, or a usable details entry."""
    d = details.get(it["id"])
    return it["platform"] == "weidian" or bool(d) and not detail_problem(it, d)


def stage(a):
    import archive_names as N
    shard = shards.parse(a.shard); k, n = shard
    log_path = os.path.join(IA.set_of(SET)["stage"], "%d-of-%d.json" % (k, n))
    log = load_json(log_path, {}) or {}
    recs = log.setdefault("items", {})
    details = load_details()
    _, items, _, _ = load_catalog()
    have = {str(p["id"]) for p in items} | {str(p.get("itemId")) for p in items if p.get("itemId")}
    done = {x for x, r in IA.staged(SET, every=True).items() if is_done(r, x, details, have)}   # every shard's file
    other = {x for name in IA.SETS if name != SET for x in IA.staged(name)}
    want = {x for x in a.ids.replace(" ", "").split(",") if x}
    mine = [it for it in load_list() if shards.mine(it["id"], shard) and (not want or it["id"] in want)]
    todo = [it for it in mine if it["id"] not in done]
    print("murphy stage, shard %d/%d: this shard %d (weidian %d, with details %d), to do now %d"
          % (k, n, len(mine), sum(1 for it in mine if it["platform"] == "weidian"),
             sum(1 for it in mine if it["id"] in details), len(todo)), flush=True)
    if a.dry_run: return
    # no network first: items without details, ids that cannot be a listing, finds the site has
    net = []
    for it in todo:
        x, why = it["id"], ""
        if it["platform"] != "weidian" and (x not in details or detail_problem(it, details[x])):
            recs[x] = {"at": IA.now(), "status": "needs details", "platform": it["platform"],
                       "why": detail_problem(it, details[x]) if x in details else "no detail source for %s listings yet" % it["platform"]}
            continue
        if not re.fullmatch(r"[0-9]{6,15}", x): why = "not a listing id"
        elif x in have: why = "on the site (same id)"
        elif x in other: why = "staged by another import"
        if why: recs[x] = {"at": IA.now(), "status": "skipped", "why": why}
        else: net.append(it)
    if net and not os.environ.get("ANTHROPIC_API_KEY"): sys.exit("ANTHROPIC_API_KEY is not set: the vision call names each find")
    keys = IA.visible_keys(items, N)
    t0, count, n_done = time.time(), collections.Counter(), 0
    for it in net:
        if (a.max_minutes and time.time() - t0 > a.max_minutes * 60) or (a.limit and n_done >= a.limit) or IF.spent >= a.max_usd:
            print("time, count or budget limit reached; the next run goes on", flush=True); break
        x = it["id"]
        try:
            rec = stage_one(it, N, keys, details.get(x))
        except Exception as e:  # noqa: BLE001 (recorded, tried again next run)
            rec = {"at": IA.now(), "status": "error", "why": str(e)[:160]}
        rec["rule"] = RULE
        if rec["status"] == "error":
            rec["tries"] = int((recs.get(x) or {}).get("tries") or 0) + 1
            if rec["tries"] >= TRIES: rec["status"] = "failed"
        recs[x] = rec; n_done += 1; count[rec["status"]] += 1
        if rec["status"] != "staged": print("  %s %s: %s" % (x, rec["status"], rec.get("why") or ""), flush=True)
        if n_done % 10 == 0:
            save_json(log_path, log); print("  %d done, $%.2f, %.0f s" % (n_done, IF.spent, time.time() - t0), flush=True)
        time.sleep(a.pause)
    log["about"] = ("The Da Murphy finds sheet import (scripts/import_sheet.py), shard %d of %d: one record per item, a "
                    "staged one with its catalogue row without the photo plus 'src', the chosen photo." % (k, n))
    log["spent_usd"] = round(float(log.get("spent_usd") or 0) + IF.spent, 4); log["at"] = IA.now()
    save_json(log_path, log)
    left = sum(1 for it in mine if it["id"] not in done and ready(it, details) and not is_done(recs.get(it["id"]), it["id"], details, have))
    print("done: %s in %.0f s, vision $%.2f; this shard's states %s" % (
        ", ".join("%s %d" % kv for kv in sorted(count.items())) or "nothing", time.time() - t0, IF.spent,
        dict(collections.Counter(r.get("status") for r in recs.values()).most_common())), flush=True)
    print("left %d" % left, flush=True)


def report(a):
    lst, details = load_list(), load_details()
    every, st, recs = IA.staged(SET, every=True), IA.staged(SET), IA.photo_records(SET)
    on = {str(p["id"]) for p in load_catalog()[1]}
    c = collections.Counter((every.get(it["id"]) or {}).get("status") or "not looked at" for it in lst)
    old_rule = sum(1 for it in lst if (every.get(it["id"]) or {}).get("status") in REDO and it["id"] not in on
                   and int((every.get(it["id"]) or {}).get("rule") or 1) < RULE)
    ph = collections.Counter("on the site" if x in on else "photo " + ((recs.get(x) or {}).get("status") or "not made yet") for x in st)
    to_stage = sum(1 for it in lst if ready(it, details) and not is_done(every.get(it["id"]), it["id"], details, on))
    to_photo = sum(1 for x in st if x not in on and (recs.get(x) or {}).get("status") not in AP.FINAL)
    print("murphy sheet: list %d %s, details for %d; states %s" % (
        len(lst), dict(collections.Counter(it["platform"] for it in lst)), len(details), dict(c.most_common())))
    print("  staged %d: %s; to look at again under photo rule %d: %d" % (len(st), dict(ph.most_common()), RULE, old_rule))
    print("left %d" % (to_stage + to_photo))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["stage", "report"])
    ap.add_argument("--shard", default="0/1"); ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--max-minutes", type=float, default=0); ap.add_argument("--max-usd", type=float, default=3)
    ap.add_argument("--pause", type=float, default=0.6); ap.add_argument("--ids", default="")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    return stage(a) if a.step == "stage" else report(a)


if __name__ == "__main__":
    sys.exit(main())
