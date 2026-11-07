# -*- coding: utf-8 -*-
"""Apply the vision labels (data/catalog_ai.json) to the catalogue in index.html: only confident changes that pass the
category and title rules, as surgical string edits inside the pc-catalog JSON (same format, same order, nothing else touched).

  python scripts/apply_catalog_ai.py [--cats] [--titles] [--reorder-colour] [--photos] [--write]
                                     [--min-cat 0.8] [--min-title 0.85] [--min-new-words 0.9] [--allow-design] [--ids 1,2]
                                     [--review data/catalog_ai_review.json] [--report data/catalog_ai_apply.md]
                                     [--csv out/changes.csv] [--revert data/catalog_ai_applied.json]

  --cats            apply category changes        --titles   apply title changes
  --reorder-colour  titles only: move a colour that sits right after the brand to the end ("Moncler Black Down Jacket"
                    -> "Moncler Down Jacket Black"); no AI involved, same words, owner format Brand + model/item + colour
  --photos          point "img" of every find whose cleaned photo is ready (data/catalog_ai.json "photos", status ok) at
                    products/pc2/<id>.webp?v=<n>. The old URL is logged, so --revert puts the original photo back.
                    Every renderer (grid, product page, feed, search, chat cards, OG image) reads "img", so nothing else
                    changes; the Supabase URL goes through /api/img and Cloudflare resizing like today.
  --verify          with --photos: check that each cleaned file answers 200 before switching to it
  --write           really write index.html (without it: report only)
  --revert F        put back the old values recorded in F (the applied log of an earlier run)
  --review F        human review decisions (data/catalog_ai_review.json): {"cat": {id: cat}, "cat_hold": {id: why},
                    "title": {id: title}, "title_hold": {id: why}}; they win over the labels

Every write appends the old and new values to data/catalog_ai_applied.json, so any batch can be reverted.
"""
import argparse, collections, csv, json, os, re, sys, unicodedata, urllib.request
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from catalog_common import ROOT, CATS, COLOURS, UA, load_catalog, load_json, save_json, no_dash  # noqa: E402

SUPA_PUBLIC = "https://uptpghuduqjqmrxwatbm.supabase.co/storage/v1/object/public/products/pc2/"
BANNED = re.compile(r"[一-鿿—–]|\b(1:1|reps?|batch|top quality|high quality|hot|new|men'?s|women'?s|unisex|"
                    r"20[12]\d|size|xs|xl|xxl)\b", re.I)
ITEM_WORDS = set("""t-shirt tee long sleeve polo shirt hoodie zip sweatshirt sweater cardigan tank top jersey tracksuit set jacket
puffer down vest coat windbreaker fleece varsity bomber denim overshirt jeans pants cargo sweatpants track trousers shorts swim
sneakers boots loafers slides sandals shoes bag backpack tote crossbody shoulder belt duffle wallet card holder pouch cap beanie
bucket hat watch necklace bracelet ring earrings sunglasses glasses socks scarf gloves keychain phone case underwear perfume dress
skirt toy figure other and with of the""".split())
COLWORDS = set(w for c in COLOURS for w in c.lower().split()) | {"multicolour", "two-tone"}
STOP = {"x", "and", "the", "of", "de", "des", "la", "le", "du", "&"}

# ------------------------------------------------------------------ categories
T, O, P, S, SH, B, A, H = "Tops", "Outerwear", "Pants", "Shorts", "Shoes", "Bags", "Accessories", "Headwear"
# item words in a title -> the categories they allow. Sellers use "jacket" and "vest" loosely for any top, so those
# allow Tops and Outerwear; "bag" also covers small leather goods. A category only changes when one item word of the
# current title allows the new category, or the title names no item at all (reviewed by eye, 5 Nov 2026: every
# high-confidence move that broke this was a wrong photo or a model reading the outfit instead of the find).
TITLE_ITEMS = [
    (r"t-?shirts?|tees?|hoodies?|sweatshirts?|sweaters?|crewnecks?|polos?|jerseys?|tank tops?|tanks?|long[- ]sleeves?|"
     r"tracksuits?|sets?|blouses?|(?<!high )(?<!high-)(?<!low )tops?|quarter[- ]zip|half[- ]zip|zip[- ]up|pullovers?|"
     r"shirts?|knit vest", {T}),
    (r"cardigans?|fleece|overshirts?|jackets?|vests?|hooded", {T, O}),
    (r"gilets?|puffers?|down|coats?|windbreakers?|bombers?|varsity|blazers?|parkas?|anoraks?|shell", {O}),
    (r"jeans|pants|trousers|sweatpants|joggers|leggings|overalls", {P}),
    (r"cargos?", {P, S}),
    (r"shorts", {S}),
    (r"sneakers?|shoes?|boots?|loafers?|slides?|sandals?|heels|trainers?|runners?|mules|clogs|slippers|air max|"
     r"air force|dunks?|air jordan|samba|gel-\w+|high[- ]tops?|low[- ]tops?", {SH}),
    (r"bags?|pouch(?:es)?", {B, A}),
    (r"backpacks?|totes?|crossbody|duffle|handbags?|messenger|briefcase|luggage|suitcase", {B}),
    (r"caps?|beanies?|hats?|balaclava|visors?|trucker|headband", {H}),
    (r"watch(?:es)?|belts?|wallets?|scarf|scarves|socks|sunglasses|glasses|necklaces?|bracelets?|rings?|earrings|"
     r"card ?holder|ties?|perfume|boxers|briefs|gloves|keychain|phone case|dress(?:es)?|bodysuits?|swimsuit", {A}),
    (r"skirts?", {A, S}),
]
TITLE_RX = [(re.compile(r"(?i)(?<![\w-])(?:%s)(?![\w-])" % rx), cats) for rx, cats in TITLE_ITEMS]


def title_cats(title):
    """Union of the categories the title's item words allow; None when the title names no item."""
    out, hit = set(), False
    for rx, cats in TITLE_RX:
        if rx.search(title or ""):
            out |= cats; hit = True
    return out if hit else None


def usable(r):
    return bool(r) and not r.get("error") and r.get("model") != "mock"


def rank(model):
    m = model or ""
    return 3 if ("opus" in m or "fable" in m) else 2 if ("sonnet" in m or "pro" in m or m == "gpt-4o") else 1


def second_opinion(r):
    """The earlier label from another model that is at least as strong (catalog_ai.py keeps it under "prev" when a find
    is re-labelled). It can veto a change the current label proposes. A weaker earlier label (Haiku before a Sonnet
    recheck) does not: the stronger model's answer counts."""
    pv = r.get("prev") or {}
    if pv and pv.get("model") and pv.get("model") != r.get("model") and rank(pv["model"]) >= rank(r.get("model")):
        return pv
    return None


def cat_changes(items, labels, a, review):
    out, why = [], collections.Counter()
    for p in items:
        i, old = p["id"], p.get("cat")
        if i in review["cat"]:
            if review["cat"][i] in CATS and review["cat"][i] != old:
                out.append((i, old, review["cat"][i], "review"))
            continue
        r = labels.get(i)
        if not usable(r) or r.get("cat") not in CATS or r["cat"] == old:
            continue
        if i in review["cat_hold"]:
            why["held by review"] += 1; continue
        new, conf = r["cat"], r.get("cat_confidence", 0)
        tc = title_cats(p.get("title"))
        pv = second_opinion(r)
        if pv and pv.get("cat") != new and conf < 0.95:
            why["the two models disagree"] += 1; continue
        # the title names exactly one category, the find sits elsewhere and the label agrees with the title
        if tc and len(tc) == 1 and new in tc and old != "Toys" and conf >= 0.5:
            out.append((i, old, new, "title agrees %.2f" % conf)); continue
        if conf < a.min_cat:
            why["below %.2f" % a.min_cat] += 1; continue
        if "Toys" not in (old, new) and tc is not None and new not in tc:
            why["title names another category (photo/title mismatch, review)"] += 1; continue
        if tc is None and "worn_by_person" in (r.get("photo_issues") or []):
            why["worn by a person and the title names no item"] += 1; continue
        out.append((i, old, new, "%.2f" % conf))
    return out, why


# ------------------------------------------------------------------ titles
def words(s):
    return [w.lower() for w in re.findall(r"[A-Za-z0-9'&+.\-]+", s or "")]


COLRX = re.compile(r"\b(?:%s)\b" % "|".join(sorted((re.escape(c) for c in COLOURS), key=len, reverse=True)), re.I)
# plain item nouns: adding one of these is not new information ("Crewneck" -> "Crewneck Sweater"; "Foam Runner" ->
# "Foam Runner Slides" is even wrong)
PLAIN = set("""sweater jacket sneaker shoe shirt top pants trousers bag watch wallet belt cap hat tshirt slide sandal boot loafer
trainer runner set other item and with of the in a""".split())
SYN = {"tee": "tshirt", "tees": "tshirt", "t-shirt": "tshirt", "t-shirts": "tshirt", "tshirts": "tshirt",
       "cardholder": "card holder"}
SING = {"sneakers", "shoes", "boots", "loafers", "slides", "sandals", "trainers", "runners", "bags", "caps", "hats", "socks",
        "gloves", "earrings", "beanies", "hoodies", "jackets", "sweaters", "tops", "sets", "vests", "coats", "belts", "watches"}
FAMILY = {}
for fam, cols in {"blue": "blue navy light dark sky royal denim indigo teal turquoise",
                  "light": "white off-white cream ivory beige grey gray silver sand ecru charcoal",
                  "black": "black charcoal navy", "brown": "brown tan camel coffee khaki",
                  "green": "green olive army mint khaki teal", "red": "red burgundy maroon wine rose",
                  "pink": "pink rose", "purple": "purple lilac", "yellow": "yellow gold", "orange": "orange apricot",
                  "multi": "multicolour multicolor two-tone"}.items():
    for c in cols.split():
        FAMILY.setdefault(c, set()).add(fam)
# a colour right before one of these is part of a name or a detail, never moved ("Black Dial", "Purple Label", "Black Cat")
DETAIL_NEXT = set("""dial label cat toe tab wing fox panther thunder lightning widow mamba bred cement infrared oreo panda
heart hearts star stars tag tags flag line stripe stripes sole soles edition""".split())


def colour_words(t):
    return [m.group(0) for m in COLRX.finditer(re.sub(r"(?i)off-white", "offwhite", t or ""))]


def families(cols):
    out = set()
    for c in cols:
        for w in c.lower().split():
            out |= FAMILY.get(w, {w})
    return out


def canon(t):
    """canonical lower-case tokens: tee = t-shirt, plural item nouns singular, hyphenated words also split"""
    out = []
    for w in words(t):
        w = SYN.get(w, w)
        for x in (w.split("-") if "-" in w else w.split()):
            if not x: continue
            if x in SING: x = x[:-2] if x.endswith("ches") else x[:-1]
            out.append(x)
    return out


def unaccent(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s or "") if not unicodedata.combining(c))


def squash(s):
    return re.sub(r"[^a-z0-9]", "", unaccent(s).lower())


def lead(base, old, brand):
    """The start of the new title. Returns the base with the title's own start kept, or None when it would change it.
    "Jordan Air Jordan 1 Low Sneakers" -> "Air Jordan 1 Low Sneakers" (old "Air Jordan 1 Low Brown");
    "Hermes H Loafers" -> "Hermès H Loafers" (old "Hermès ..."); "North Face ..." -> "The North Face ..." is a fix."""
    if not brand:
        return base
    bl = brand.lower()
    if old.lower().startswith(bl + " ") or old.lower() == bl:
        return base if base.lower().startswith(bl + " ") or base.lower() == bl else None
    if not base.lower().startswith(bl + " "):
        return None
    rest = base[len(brand) + 1:]
    ow = old.split()
    for n in (1, 2, 3):
        if len(ow) < n: break
        pre = " ".join(ow[:n])
        if squash(pre) == squash(brand):
            # the old spelling has the accent or apostrophe ("Hermès", "Levi's"): keep it; else the brand fixes it
            # ("Arcteryx" -> "Arc'teryx")
            return pre + " " + rest if len(pre) >= len(brand) else base
        if bl.startswith("the ") and squash(pre) == squash(brand[4:]):
            return base                                               # "North Face" -> "The North Face"
    # the old title starts with a product line that contains the brand ("Air Jordan", "Polo Ralph Lauren")
    if ow and rest.lower().startswith(ow[0].lower() + " "):
        return rest
    return None


def compose_titles(items, labels, a, review):
    """New titles that pass the rules (owner, 5 Nov 2026, tightened after a by-eye review of 366 changes):
    format Brand + model/item + colour; never drop a word of the current title (tee = t-shirt and plurals count as the
    same word); never drop a colour; change a colour only when the model is 0.95+ sure, it is another colour family
    (navy and black count as one) and the seller's own variant names do not carry the old colour; add a second colour
    only at 0.9+ and never more than two colour words; a new word (model name) only when it is readable in the photo
    (visible_text) at --min-new-words, and when an at least as strong model labelled the find before, it must say the
    same; no repeated words ("Jordan Air Jordan", "Camo ... Camo"); keep the title's own start. A change must ADD
    information (a model name, a sub-type like Zip Hoodie, a second colour, a colour where there was none) or fix the
    brand. Anything else keeps its current title."""
    cand, why = {}, collections.Counter()
    for p in items:
        i = p["id"]
        old = p.get("title") or ""
        if i in review["title"]:
            if review["title"][i] != old: cand[i] = no_dash(review["title"][i])
            continue
        r = labels.get(i)
        if not usable(r):
            continue
        if i in review["title_hold"]:
            why["held by review"] += 1; continue
        base = re.sub(r"\s+", " ", no_dash(r.get("title_base") or "")).strip()
        brand = p.get("brand") or ""
        if not base:
            why["empty"] += 1; continue
        if r.get("title_confidence", 0) < a.min_title:
            why["low confidence"] += 1; continue
        if r.get("brand_check") == "different":
            why["brand differs in photo (review)"] += 1; continue
        base2 = lead(base, old, brand)
        if base2 is None:
            why["changes the start of the title"] += 1; continue
        base = base2
        if BANNED.search(re.sub(r"(?i)margiela replica", "", base)):
            why["banned words"] += 1; continue
        brand_part = base[:len(brand)] if base.lower().startswith(brand.lower()) else ""
        base_cols = colour_words(base[len(brand_part):])
        if base_cols and not all(re.search(r"(?i)\b%s \w+" % re.escape(c), old) for c in base_cols):
            why["colour inside base"] += 1; continue
        n = len(base.split())
        if n < 2 or n > 7 or len(base) > 44:
            why["length"] += 1; continue
        # no invented words
        known = set(words(brand)) | set(words(old)) | set(canon(old)) | ITEM_WORDS | COLWORDS
        for v in p.get("variants") or []:
            if isinstance(v, list) and v and isinstance(v[0], str): known |= set(words(v[0]))
        new_words = [w for w in words(base) if w not in known and not all(x in known for x in w.split("-"))]
        src = r.get("model_source")
        if new_words and not (src == "visible_text" or (src == "design" and a.allow_design)):
            why["new words without a source"] += 1; continue
        if new_words and r.get("title_confidence", 0) < a.min_new_words:
            why["new words below %.2f" % a.min_new_words] += 1; continue
        pv = second_opinion(r)
        if new_words and pv and not all(w in words(pv.get("title_base")) for w in new_words):
            why["second model does not see the new words"] += 1; continue
        # colour: keep the current one unless clearly wrong
        old_cols = colour_words(old[len(brand):] if old.lower().startswith(brand.lower()) else old)
        ai_col = (r.get("colour") or "").strip().title()
        ai_cols = colour_words(ai_col)
        if len(ai_col.split()) > 2 or len(ai_cols) > 2:
            ai_col, ai_cols = "", []                                    # three colours: a description, not a title
        col_conf = r.get("colour_confidence", min(r.get("title_confidence", 0), r.get("confidence", 0)))
        if pv and pv.get("colour") and families(colour_words(pv["colour"])) != families(ai_cols):
            col_conf = min(col_conf, 0.8)                               # the two models see different colours
        # the seller's own variant names carry the old colour: a photo that looks different is lighting, not an error
        vnames = " ".join(v[0] for v in (p.get("variants") or []) if isinstance(v, list) and v and isinstance(v[0], str))
        seller_says = bool(set(c.lower() for c in old_cols) & set(c.lower() for c in colour_words(vnames)))
        added_colour = False
        if old_cols:
            col = " ".join(c.title() for c in old_cols).replace("Offwhite", "Off-White")
            olds = set(c.lower() for c in old_cols)
            if ai_cols and olds < set(c.lower() for c in ai_cols) and col_conf >= a.min_second_colour and len(old_cols) == 1:
                col = ai_col; added_colour = True                       # a second colour: "Navy" -> "Navy White"
            elif ai_cols and col_conf >= 0.95 and not (families(old_cols) & families(ai_cols)) and not seller_says:
                col = ai_col; added_colour = True                       # a clear error fixed (0.95+, another colour family)
        else:
            col = ai_col if ai_cols and col_conf >= 0.85 and ai_col.lower() not in ("multicolour", "multicolor") else ""
            added_colour = bool(col)
        if base_cols:
            col = ""
        t = (base + " " + col).strip() if col else base
        # keep the casing of words the current title already has ("XT-6", "GG", "FF")
        oc = {w.lower(): w for w in re.findall(r"[A-Za-z0-9'&+.\-]+", old)}
        t = re.sub(r"[A-Za-z0-9'&+.\-]+", lambda m: oc.get(m.group(0).lower(), m.group(0)), t)
        tl, ol = canon(t), canon(old)
        if len(t.split()) > 8 or len(t) > 48:
            why["length"] += 1; continue
        reps = [w for w, c in collections.Counter(x for x in tl if x not in STOP and len(x) > 1).items() if c > 1]
        if reps and not all(ol.count(w) > 1 for w in reps):
            why["repeated word"] += 1; continue
        joined = squash(t)
        brand_t = set(canon(brand)) | set(canon(unaccent(brand)))
        lost = [w for w in ol if w not in tl and w not in COLWORDS and w != "offwhite" and w not in brand_t
                and not (len(w) >= 4 and squash(w) in joined)]
        if lost and brand.lower() not in old.lower():
            lost = [w for w in lost if squash(w) not in squash(brand)]
        if lost:
            why["would drop words"] += 1; continue
        gained = [w for w in tl if w not in ol and w not in PLAIN and w not in COLWORDS and w not in brand_t
                  and not (len(w) >= 4 and w in squash(old))]
        brand_fix = bool(brand) and squash(brand) not in squash(old)
        if not (gained or added_colour or brand_fix):
            why["adds nothing"] += 1; continue
        if t.lower() == old.lower():
            why["same as now"] += 1; continue
        cand[i] = t
    return cand, why


def reorder_colour(items, skip):
    """Brand + colour + rest -> Brand + rest + colour, for titles the label step leaves alone (pure word order)."""
    out = {}
    for p in items:
        if p["id"] in skip: continue
        t, b = p.get("title") or "", p.get("brand") or ""
        if not b or not t.lower().startswith(b.lower() + " ") or b.lower() in ("off-white",):
            continue
        rest = t[len(b) + 1:].split()
        k = 0
        while k < len(rest) and k < 2 and rest[k].lower() in COLWORDS and rest[k].lower() not in ("light", "dark"):
            k += 1
        if k and k < len(rest) and rest[k - 1].lower() in ("light", "dark"):
            continue
        if not k or k >= len(rest) or rest[k].lower() in DETAIL_NEXT:
            continue
        tail = rest[k:]
        if colour_words(" ".join(tail)) or len(tail) < 1:
            continue                                                    # a second colour later: leave it
        out[p["id"]] = " ".join([b] + tail + rest[:k])
    return out


def dedupe(cand, items, why):
    """Drop changes that would give a find the same title as another find when its current title is its own."""
    final = {p["id"]: cand.get(p["id"], p.get("title") or "") for p in items}
    count = collections.Counter(v.lower() for v in final.values())
    oldc = collections.Counter((p.get("title") or "").lower() for p in items)
    byid = {p["id"]: p for p in items}
    for i in list(cand):
        if count[cand[i].lower()] > 1 and oldc[(byid[i].get("title") or "").lower()] == 1:
            count[cand[i].lower()] -= 1; count[(byid[i].get("title") or "").lower()] += 1
            del cand[i]; why["would duplicate another find's title"] += 1
    return cand


# ------------------------------------------------------------------ text edits
def esc(v):
    s = json.dumps(v, ensure_ascii=False)
    return s.replace("</", "<\\/")


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


def mirrored(url):
    """True when scripts/mirror_photos.py already copied this photo into the site (no request to Supabase needed)."""
    try:
        from mirror_photos import mirror_path
    except ImportError:
        return False
    p = mirror_path(url)
    return bool(p) and os.path.isfile(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), p.lstrip("/")))


def head_ok(url):
    try:
        req = urllib.request.Request(url, method="HEAD", headers=UA)
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status == 200 and (r.headers.get("content-type") or "").startswith("image/")
    except Exception:
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", default=os.path.join(ROOT, "index.html"))
    ap.add_argument("--labels", default=os.path.join(ROOT, "data", "catalog_ai.json"))
    ap.add_argument("--review", default=os.path.join(ROOT, "data", "catalog_ai_review.json"))
    ap.add_argument("--cats", action="store_true")
    ap.add_argument("--titles", action="store_true")
    ap.add_argument("--reorder-colour", action="store_true")
    ap.add_argument("--photos", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--min-cat", type=float, default=0.80)
    ap.add_argument("--min-title", type=float, default=0.85)
    ap.add_argument("--min-new-words", type=float, default=0.90)
    ap.add_argument("--min-second-colour", type=float, default=0.90)
    ap.add_argument("--allow-design", action="store_true")
    ap.add_argument("--ids", default="")
    ap.add_argument("--max-changes", type=int, default=0, help="cap per field (0 = no cap)")
    ap.add_argument("--report", default=os.path.join(ROOT, "data", "catalog_ai_apply.md"))
    ap.add_argument("--csv", default="", help="also write every change as CSV (id, field, old, new, note)")
    ap.add_argument("--log", default=os.path.join(ROOT, "data", "catalog_ai_applied.json"))
    ap.add_argument("--revert", default="")
    a = ap.parse_args()

    html, items, s, e = load_catalog(a.index)
    raw = html[s:e]
    store = load_json(a.labels, {})
    labels = store.get("items", {})
    rv = load_json(a.review, {})
    review = {k: rv.get(k) or {} for k in ("cat", "cat_hold", "title", "title_hold")}
    only = set(a.ids.replace(" ", "").split(",")) - {""}
    sel = [p for p in items if not only or p["id"] in only]
    idx = {p["id"]: p for p in items}
    changes = []          # (id, field, old, new, note)
    whys = {}

    if a.revert:
        log = load_json(a.revert, {"batches": []})
        for b in reversed(log.get("batches", [])):
            for c in b.get("changes", []):
                i, f, old, new = c["id"], c["field"], c["old"], c["new"]
                if only and i not in only: continue
                p = idx.get(i)
                if not p: continue
                if f == "p2":
                    if "p2" in p: changes.append((i, "p2", p["p2"], None, "revert"))
                elif p.get(f) == new and not any(x[0] == i and x[1] == f for x in changes):
                    changes.append((i, f, new, old, "revert"))
    else:
        if a.cats:
            cc, whys["categories kept"] = cat_changes(sel, labels, a, review)
            for n, (i, old, new, note) in enumerate(cc):
                if a.max_changes and n >= a.max_changes: break
                changes.append((i, "cat", old, new, note))
        if a.titles:
            new, why = compose_titles(sel, labels, a, review)
            ai_ids = set(new)
            if a.reorder_colour:
                ro = reorder_colour(sel, set(new))
                why["moved the colour to the end (word order only)"] = len(ro)
                new.update(ro)
            new = dedupe(new, items, why)
            whys["titles kept"] = why
            for n, (i, t) in enumerate(new.items()):
                if a.max_changes and n >= a.max_changes: break
                r = labels.get(i) or {}
                if i in review["title"]: note = "review"
                elif i not in ai_ids: note = "word order"
                else: note = "%.2f %s" % (r.get("title_confidence", 0), r.get("model_source"))
                changes.append((i, "title", idx[i]["title"], t, note))
        if a.photos:
            bad = 0
            for i, ph in (store.get("photos") or {}).items():
                if only and i not in only: continue
                p = idx.get(i)
                if not p or ph.get("status") != "ok" or ph.get("store") != "supabase": continue
                url = SUPA_PUBLIC + i + ".webp?v=%d" % int(ph.get("v") or 1)
                if p.get("img") == url: continue
                if a.verify and not (mirrored(url) or head_ok(url)):
                    bad += 1; continue
                changes.append((i, "img", p.get("img"), url, "pc2 v%s" % ph.get("v")))
            whys["photos"] = {"cleaned file missing (not switched)": bad} if bad else {}

    for k, w in whys.items():
        print(k + ":", dict(w))

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
    for k, w in whys.items():
        if w: L += ["%s: %s" % (k.capitalize(), ", ".join("%s %d" % kv for kv in collections.Counter(w).most_common())), ""]
    if moves:
        L += ["## Category moves", "", "| Move | Finds |", "|---|---:|"] + ["| %s | %d |" % kv for kv in moves.most_common()] + [""]
    L += ["## Changes", "", "| id | field | old | new | note |", "|---|---|---|---|---|"]
    L += ["| %s | %s | %s | %s | %s |" % (c[0], c[1], str(c[2]).replace("|", "/"), str(c[3]).replace("|", "/"), c[4]) for c in applied]
    if failed:
        L += ["", "## Not applied", ""] + ["- %s: %s" % f for f in failed]
    os.makedirs(os.path.dirname(a.report) or ".", exist_ok=True)
    open(a.report, "w", encoding="utf-8").write("\n".join(L) + "\n")
    if a.csv:
        os.makedirs(os.path.dirname(a.csv) or ".", exist_ok=True)
        with open(a.csv, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f); w.writerow(["id", "field", "old", "new", "note"])
            for c in applied: w.writerow(c)
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
