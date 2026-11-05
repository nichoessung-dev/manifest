# -*- coding: utf-8 -*-
"""Apply the vision labels (data/catalog_ai.json) to the catalogue in index.html: only confident changes that pass the
title rules, as surgical string edits inside the pc-catalog JSON (same format, same order, nothing else touched).

  python scripts/apply_catalog_ai.py [--cats] [--titles] [--photos] [--write]
                                     [--min-cat 0.9] [--min-title 0.85] [--allow-design] [--ids 1,2]
                                     [--report data/catalog_ai_apply.md] [--revert data/catalog_ai_applied.json]

  --cats      apply category changes          --titles   apply title changes
  --photos    mark finds whose cleaned photo is ready (data/catalog_ai.json "photos") with "p2":<version>,
              so the site shows img/p2/<id>.webp and falls back to "img" (the original, never changed)
  --write     really write index.html (without it: report only)
  --revert F  put back the old values recorded in F (the applied log of an earlier run) and drop "p2" keys it added

Every write appends the old and new values to data/catalog_ai_applied.json, so any batch can be reverted.
Afterwards run scripts/clean_catalog.py --dry-run (sanity) and let catalog-sync regenerate catalog.js/products.json.
"""
import argparse, collections, json, os, re, sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from catalog_common import ROOT, CATS, COLOURS, load_catalog, load_json, save_json, no_dash  # noqa: E402

BANNED = re.compile(r"[一-鿿—–]|\b(1:1|reps?|batch|top quality|high quality|hot|new|men'?s|women'?s|unisex|"
                    r"20[12]\d|size|xs|xl|xxl)\b", re.I)
ITEM_WORDS = set("""t-shirt tee long sleeve polo shirt hoodie zip sweatshirt sweater cardigan tank top jersey tracksuit set jacket
puffer down vest coat windbreaker fleece varsity bomber denim overshirt jeans pants cargo sweatpants track trousers shorts swim
sneakers boots loafers slides sandals shoes bag backpack tote crossbody shoulder belt duffle wallet card holder pouch cap beanie
bucket hat watch necklace bracelet ring earrings sunglasses glasses socks scarf gloves keychain phone case underwear perfume dress
skirt toy figure other and with of the""".split())
COLWORDS = set(w for c in COLOURS for w in c.lower().split()) | {"multicolour", "two-tone"}


def esc(v):
    s = json.dumps(v, ensure_ascii=False)
    return s.replace("</", "<\\/")


def words(s):
    return [w.lower() for w in re.findall(r"[A-Za-z0-9'&+.\-]+", s or "")]


COLRX = re.compile(r"\b(?:%s)\b" % "|".join(sorted((re.escape(c) for c in COLOURS), key=len, reverse=True)), re.I)


def strip_colours(t):
    return re.sub(r"\s+", " ", COLRX.sub(" ", re.sub(r"(?i)off-white", "offwhite", t or ""))).strip().lower().replace("offwhite", "off-white")


# plain item nouns: adding one of these is not new information ("Crewneck" -> "Crewneck Sweater")
PLAIN = set("""sweater jacket sneakers sneaker shoes shoe shirt top pants trousers bag watch wallet belt cap hat tee t-shirt
set other item and with of the in a""".split())
# colour families: a change inside one family (blue / navy, white / grey / cream) is a matter of shade, never applied
FAMILY = {}
for fam, cols in {"blue": "blue navy light dark sky royal denim indigo teal turquoise",
                  "light": "white off-white cream ivory beige grey gray silver sand ecru charcoal",
                  "black": "black charcoal", "brown": "brown tan camel coffee khaki",
                  "green": "green olive army mint khaki teal", "red": "red burgundy maroon wine rose",
                  "pink": "pink rose", "purple": "purple lilac", "yellow": "yellow gold", "orange": "orange apricot",
                  "multi": "multicolour multicolor two-tone"}.items():
    for c in cols.split():
        FAMILY.setdefault(c, set()).add(fam)


def colour_words(t):
    return [m.group(0) for m in COLRX.finditer(re.sub(r"(?i)off-white", "offwhite", t or ""))]


def families(cols):
    out = set()
    for c in cols:
        for w in c.lower().split():
            out |= FAMILY.get(w, {w})
    return out


def toks(t):
    """lower-case words, hyphenated words also split ("zip-up" -> zip, up)"""
    out = []
    for w in words(t):
        out += [x for x in w.split("-") if x] if "-" in w else [w]
    return out


def compose_titles(items, labels, allow_design, min_title, all_items=None):
    """New titles that pass the rules (owner, 5 Nov 2026):
    format Brand + model/item + colour; never drop a colour the current title has; change a colour only when the
    model is 0.95+ sure AND it is a clearly different colour (not navy vs blue, not white vs grey); keep every detail
    word of the current title ("Green Dial", "21 Inch", "Washed", "Check", "Polo"); accept a change only when it ADDS
    information (a model name, a sub-type like Zip Hoodie, a second colour, a colour where there was none) or fixes
    the brand spelling. Anything else keeps its current title."""
    cand = {}
    why = collections.Counter()
    for p in items:
        r = labels.get(p["id"])
        if not r or r.get("error") or r.get("model") == "mock":
            continue
        old = p.get("title") or ""
        base = re.sub(r"\s+", " ", no_dash(r.get("title_base") or "")).strip()
        brand = p.get("brand") or ""
        if not base:
            why["empty"] += 1; continue
        if r.get("title_confidence", 0) < min_title:
            why["low confidence"] += 1; continue
        if r.get("brand_check") == "different":
            why["brand differs in photo (review)"] += 1; continue
        if brand and not base.lower().startswith(brand.lower() + " ") and base.lower() != brand.lower():
            why["does not start with brand"] += 1; continue
        if BANNED.search(re.sub(r"(?i)margiela replica", "", base)):
            why["banned words"] += 1; continue
        # colour words inside the base are only allowed when they are a detail phrase of the current title ("Green Dial")
        base_cols = colour_words(base[len(brand):])
        if base_cols and not all(re.search(r"(?i)\b%s \w+" % re.escape(c), old) for c in base_cols):
            why["colour inside base"] += 1; continue
        n = len(base.split())
        if n < 2 or n > 7 or len(base) > 44:
            why["length"] += 1; continue
        # no invented words
        known = set(words(brand)) | set(words(old)) | set(toks(old)) | ITEM_WORDS | COLWORDS
        for v in p.get("variants") or []:
            if isinstance(v, list) and v and isinstance(v[0], str): known |= set(words(v[0]))
        new_words = [w for w in words(base) if w not in known and not all(x in known for x in w.split("-"))]
        src = r.get("model_source")
        if new_words and not (src == "visible_text" or (src == "design" and allow_design)):
            why["new words without a source"] += 1; continue
        if new_words and src == "design" and r.get("title_confidence", 0) < 0.92:
            why["design guess below 0.92"] += 1; continue
        # colour: keep the current one unless clearly wrong
        old_cols = colour_words(old[len(brand):] if old.lower().startswith(brand.lower()) else old)
        ai_col = (r.get("colour") or "").strip().title()
        ai_cols = colour_words(ai_col)
        col_conf = r.get("colour_confidence", min(r.get("title_confidence", 0), r.get("confidence", 0)))
        added_colour = False
        if old_cols:
            col = " ".join(c.title() for c in old_cols).replace("Offwhite", "Off-White")
            olds = set(c.lower() for c in old_cols)
            if ai_cols and olds < set(c.lower() for c in ai_cols):
                col = ai_col; added_colour = True                       # a second colour: "Navy" -> "Navy White"
            elif ai_cols and col_conf >= 0.95 and not (families(old_cols) & families(ai_cols)):
                col = ai_col; added_colour = True                       # a clear error fixed (0.95+, another colour family)
        else:
            col = ai_col if ai_cols and col_conf >= 0.85 and ai_col.lower() not in ("multicolour", "multicolor") else ""
            added_colour = bool(col)
        if base_cols:                                                    # the colour already sits in a detail phrase
            col = ""
        t = (base + " " + col).strip() if col else base
        # every detail word of the current title must survive
        tl = toks(t); joined = re.sub(r"[\s\-']", "", t.lower())
        lost = [w for w in toks(old) if w not in tl and w not in set(toks(brand)) and w not in PLAIN
                and w not in COLWORDS and w != "offwhite" and not (len(w) >= 5 and w.replace("'", "") in joined)]
        if brand.lower() not in old.lower():
            lost = [w for w in lost if w.replace("'", "") not in re.sub(r"[\s\-']", "", brand.lower())]
        if lost:
            why["would drop detail words"] += 1; continue
        # it must add information
        gained = [w for w in tl if w not in set(toks(old)) and w not in PLAIN and w not in COLWORDS
                  and w not in set(toks(brand)) and not (len(w) >= 5 and w in re.sub(r"[\s\-']", "", old.lower()))]
        brand_fix = bool(brand) and brand.lower() not in old.lower()
        if not (gained or added_colour or brand_fix):
            why["adds nothing"] += 1; continue
        if len(t) > 48:
            why["length"] += 1; continue
        if t.lower() == old.lower():
            why["same as now"] += 1; continue
        cand[p["id"]] = t
    return cand, why


def object_span(raw, pid):
    """(start, end) of the catalogue object with this id inside the raw JSON text (objects have no nested {})."""
    k = raw.find('{"id":%s,' % esc(pid))
    if k < 0:
        return None
    e = raw.find("}", k)
    return k, e + 1


def set_field(obj, key, old, new):
    """Replace "key":old with "key":new inside one object's text; None when the old text is not there exactly once."""
    a = '"%s":%s' % (key, esc(old)); b = '"%s":%s' % (key, esc(new))
    if obj.count(a) != 1 or obj.count('"%s":' % key) != 1:
        return None
    return obj.replace(a, b)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", default=os.path.join(ROOT, "index.html"))
    ap.add_argument("--labels", default=os.path.join(ROOT, "data", "catalog_ai.json"))
    ap.add_argument("--cats", action="store_true")
    ap.add_argument("--titles", action="store_true")
    ap.add_argument("--photos", action="store_true")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--min-cat", type=float, default=0.90)
    ap.add_argument("--min-title", type=float, default=0.85)
    ap.add_argument("--allow-design", action="store_true")
    ap.add_argument("--ids", default="")
    ap.add_argument("--max-changes", type=int, default=0, help="cap per field (0 = no cap)")
    ap.add_argument("--report", default=os.path.join(ROOT, "data", "catalog_ai_apply.md"))
    ap.add_argument("--log", default=os.path.join(ROOT, "data", "catalog_ai_applied.json"))
    ap.add_argument("--revert", default="")
    a = ap.parse_args()

    html, items, s, e = load_catalog(a.index)
    raw = html[s:e]
    store = load_json(a.labels, {})
    labels = store.get("items", {})
    only = set(a.ids.replace(" ", "").split(",")) - {""}
    idx = {p["id"]: p for p in items}
    changes = []          # (id, field, old, new, note)

    if a.revert:
        log = load_json(a.revert, {"batches": []})
        for b in log.get("batches", []):
            for c in b.get("changes", []):
                i, f, old, new = c["id"], c["field"], c["old"], c["new"]
                if only and i not in only: continue
                p = idx.get(i)
                if not p: continue
                if f == "p2":
                    if "p2" in p: changes.append((i, "p2", p["p2"], None, "revert"))
                elif p.get(f) == new:
                    changes.append((i, f, new, old, "revert"))
    else:
        if a.cats:
            n = 0
            for p in items:
                r = labels.get(p["id"])
                if only and p["id"] not in only: continue
                if not r or r.get("error") or r.get("model") == "mock": continue
                if r.get("cat") in CATS and r["cat"] != p.get("cat") and r.get("cat_confidence", 0) >= a.min_cat:
                    changes.append((p["id"], "cat", p.get("cat"), r["cat"], "%.2f" % r["cat_confidence"])); n += 1
                    if a.max_changes and n >= a.max_changes: break
        if a.titles:
            new, why = compose_titles([p for p in items if not only or p["id"] in only], labels, a.allow_design, a.min_title, items)
            print("titles kept as they are:", dict(why))
            for n, (i, t) in enumerate(new.items()):
                if a.max_changes and n >= a.max_changes: break
                changes.append((i, "title", idx[i]["title"], t, "%.2f %s" % (labels[i].get("title_confidence", 0), labels[i].get("model_source"))))
        if a.photos:
            for i, ph in (store.get("photos") or {}).items():
                if only and i not in only: continue
                if i in idx and ph.get("status") == "ok" and idx[i].get("p2") != ph.get("v"):
                    changes.append((i, "p2", idx[i].get("p2"), int(ph.get("v") or 1), ph.get("store", "")))

    # surgical edits, object by object
    applied, failed = [], []
    by_id = collections.defaultdict(list)
    for c in changes: by_id[c[0]].append(c)
    out = raw
    for i, cs in by_id.items():
        sp = object_span(out, i)
        if not sp:
            failed.append((i, "object not found")); continue
        obj = out[sp[0]:sp[1]]
        ok = True
        for (_, f, old, new, note) in cs:
            if f == "p2":
                if new is None:
                    o2 = re.sub(r',"p2":\d+', "", obj)
                elif '"p2":' in obj:
                    o2 = re.sub(r'"p2":\d+', '"p2":%d' % new, obj)
                else:
                    o2 = obj[:-1] + ',"p2":%d}' % new
            else:
                o2 = set_field(obj, f, old, new)
            if o2 is None:
                failed.append((i, "field %s not found exactly once" % f)); ok = False; break
            obj = o2
        if ok:
            out = out[:sp[0]] + obj + out[sp[1]:]
            applied += cs

    # verify: same finds, same order, only the intended fields differ
    after = json.loads(out)
    assert len(after) == len(items) and all(x["id"] == y["id"] for x, y in zip(items, after)), "order or count changed"
    want = {(c[0], c[1]): c[3] for c in applied}
    for x, y in zip(items, after):
        for k in set(x) | set(y):
            if x.get(k) != y.get(k):
                assert (x["id"], k) in want and y.get(k) == want[(x["id"], k)], "unexpected change %s %s" % (x["id"], k)

    cnt = collections.Counter(c[1] for c in applied)
    moves = collections.Counter("%s -> %s" % (c[2], c[3]) for c in applied if c[1] == "cat")
    L = ["# Catalogue AI changes (%s)" % ("written" if a.write else "report only, not written"), "",
         "Applied: %s. Failed: %d." % (dict(cnt) or "nothing", len(failed)), ""]
    if moves:
        L += ["## Category moves", "", "| Move | Finds |", "|---|---:|"] + ["| %s | %d |" % kv for kv in moves.most_common()] + [""]
    L += ["## Changes", "", "| id | field | old | new | note |", "|---|---|---|---|---|"]
    L += ["| %s | %s | %s | %s | %s |" % (c[0], c[1], str(c[2]).replace("|", "/"), str(c[3]).replace("|", "/"), c[4]) for c in applied]
    if failed:
        L += ["", "## Not applied", ""] + ["- %s: %s" % f for f in failed]
    os.makedirs(os.path.dirname(a.report), exist_ok=True)
    open(a.report, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("%d changes (%s), %d failed; report %s" % (len(applied), dict(cnt), len(failed), a.report))

    if a.write and applied and out != raw:
        open(a.index, "w", encoding="utf-8").write(html[:s] + out + html[e:])
        log = load_json(a.log, {"batches": []})
        log["batches"].append({"date": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                               "kind": "revert" if a.revert else "apply",
                               "changes": [{"id": c[0], "field": c[1], "old": c[2], "new": c[3]} for c in applied]})
        save_json(a.log, log)
        print("index.html written; old values logged in", a.log)


if __name__ == "__main__":
    main()
