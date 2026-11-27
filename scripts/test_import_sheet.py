# -*- coding: utf-8 -*-
"""Tests for the Da Murphy finds sheet import: python scripts/test_import_sheet.py

No network: Weidian's getItemSkuInfo, the photos and the vision call are answered by a fake urlopen.
  - scripts/import_sheet.py stage: a Weidian item staged (the price rule, the vision's title, brand spelling, the chosen
    photo, the sheet's hints in the prompt), rugs and room decor under Accessories, gone, sold out, placeholder prices,
    a deposit price, no clean photo, a banned word, the same id or the same model as a find on the site, Taobao and 1688
    left as "needs details" without a call, a run again calls nothing new, an item that keeps erroring is given up,
    shards write their own files
  - Taobao and 1688 from the details file (data/sheet_murphy_details.json): staged once their entry is there (the
    entry's photo, title and price, the Marketplace seller, no itemId), an entry with a photo off alicdn is not used
  - scripts/archive_photos.py --set murphy: reads the sheet's stage, writes the sheet's records; Weidian photos with the
    Weidian referrer
  - scripts/import_archive.py apply --set murphy: the finds with a cut-out are appended WITHOUT "ar", the same model only
    once, nothing else in index.html changes (written to a copy); the Archive set still gets "ar"
"""
import contextlib, glob, io, json, os, shutil, sys, tempfile, time, urllib.parse, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image  # noqa: E402
import archive_names as N  # noqa: E402
import archive_photos as AP  # noqa: E402
import import_archive as IA  # noqa: E402
import import_friend as IF  # noqa: E402
import import_sheet as IS  # noqa: E402
from catalog_common import ROOT, load_catalog  # noqa: E402

fails = []
CALLS, PROMPTS = [], []


def ok(c, m):
    if not c: fails.append(m); print("FAIL", m)


HTML, ITEMS, S0, E0 = load_catalog()
HAVE = {str(p["id"]) for p in ITEMS} | {str(p.get("itemId")) for p in ITEMS if p.get("itemId")}
KEYS = IA.visible_keys(ITEMS, N)
# a find on the site whose brand, title and row the stage keeps as they are: the vision names a new listing just like it
TWIN = next(p for p in ITEMS if IA.model_key(p, N) and KEYS.get(IA.model_key(p, N)) == p["id"] and p.get("brand")
            and IS.house_brand(p["brand"], N) == p["brand"] and not IA.row_problems(dict(p, platform="weidian"), ("weidian",))
            and not IS.ROOM.search(p["title"]))
ON_SITE = next(p for p in ITEMS if p.get("platform") == "weidian")["id"]


def sku(title, fen, stock=10): return {"skuInfo": {"title": title, "discountPrice": fen, "stock": stock}}


def listing(zh, skus, stock=50, opts=1):
    t = str(len(zh)) + "-" + "".join("%x" % ord(ch) for ch in zh)[:24]
    return {"itemTitle": zh, "itemMainPic": "https://si.geilicdn.com/main-%s.jpg" % t, "itemStock": stock,
            "attrList": [{"attrTitle": "颜色", "attrValues": [{"attrValue": "黑色", "img": "//si.geilicdn.com/opt-%d-%s.jpg" % (j, t)}
                                                             for j in range(opts)]}], "skuInfos": skus}


ids = ["79991%05d" % k for k in range(1, 14)]
assert not (set(ids) | {"7999300000001", "719154287380"}) & HAVE
HOODIE, RUG, DECOR, CARPET, SOLD, GONE, NOPRICE, DEPOSIT, BADPHOTO, BANNED, TWIN_ID, ERR, LOOKS = ids
LIST = [
    {"platform": "weidian", "id": HOODIE, "sheet_name": "stussy zip (heavy)", "section": "Hoodies", "sheet_gbp": 20.5, "note": ""},
    {"platform": "weidian", "id": RUG, "sheet_name": "kaws rug", "section": "Rugs", "sheet_gbp": 30, "note": ""},
    {"platform": "weidian", "id": DECOR, "sheet_name": "8 ball lamp", "section": "Room Decor", "sheet_gbp": 0, "note": ""},
    {"platform": "weidian", "id": CARPET, "sheet_name": "bape carpet", "section": "Most Popular Finds", "sheet_gbp": 0, "note": ""},
    {"platform": "weidian", "id": SOLD, "sheet_name": "sold tee", "section": "T-Shirts & Shirts", "sheet_gbp": 9, "note": ""},
    {"platform": "weidian", "id": GONE, "sheet_name": "gone tee", "section": "T-Shirts & Shirts", "sheet_gbp": 9, "note": ""},
    {"platform": "weidian", "id": NOPRICE, "sheet_name": "link only", "section": "Jeans", "sheet_gbp": 0, "note": ""},
    {"platform": "weidian", "id": DEPOSIT, "sheet_name": "BB coat", "section": "Jackets", "sheet_gbp": 100, "note": ""},
    {"platform": "weidian", "id": BADPHOTO, "sheet_name": "collage tee", "section": "T-Shirts & Shirts", "sheet_gbp": 0, "note": ""},
    {"platform": "weidian", "id": BANNED, "sheet_name": "rep hoodie", "section": "Hoodies", "sheet_gbp": 0, "note": ""},
    {"platform": "weidian", "id": TWIN_ID, "sheet_name": "twin", "section": "Hoodies", "sheet_gbp": 0, "note": ""},
    {"platform": "weidian", "id": ERR, "sheet_name": "flaky", "section": "Hoodies", "sheet_gbp": 0, "note": ""},
    {"platform": "weidian", "id": LOOKS, "sheet_name": "Accessorie add your name", "section": "Accessories", "sheet_gbp": 0, "note": ""},
    {"platform": "weidian", "id": ON_SITE, "sheet_name": "on the site", "section": "Hoodies", "sheet_gbp": 0, "note": ""},
    {"platform": "weidian", "id": "2055316446993086619623", "sheet_name": "vescartes jacket", "section": "Jackets", "sheet_gbp": 32, "note": ""},
    {"platform": "taobao", "id": "7999300000001", "sheet_name": "Ncta jacket", "section": "Jackets", "sheet_gbp": 40, "note": ""},
    {"platform": "1688", "id": "719154287380", "sheet_name": "8 ball pillows", "section": "Room Decor", "sheet_gbp": 1.92, "note": ""},
]
NET = {HOODIE, RUG, DECOR, CARPET, SOLD, GONE, NOPRICE, DEPOSIT, BADPHOTO, BANNED, TWIN_ID, ERR, LOOKS}
OK_SKUS = [sku("黑色;M", 18900), sku("补差价链接", 100, 99)]
THOR = {HOODIE: listing("斯图西 拉链卫衣 黑色", OK_SKUS, opts=2), RUG: listing("地毯 灰色", [sku("灰色", 25000)]),
        DECOR: listing("台灯", [sku("黑色", 9900)]), CARPET: listing("猿人头 地垫", [sku("迷彩", 15000)]),
        SOLD: listing("短袖 售罄", [sku("白色;L", 9000, 0)], stock=0), GONE: {},
        NOPRICE: listing("补差价", [sku("补差价链接", 100), sku("邮费专拍", 1000)]),
        DEPOSIT: listing("巴黎 大衣 定制", [sku("黑色", 2000)]), BADPHOTO: listing("拼图 短袖", [sku("白色", 8000)]),
        BANNED: listing("卫衣 复刻", [sku("灰色", 12000)]), TWIN_ID: listing("同款 双胞胎", [sku("黑色", 30000)]),
        LOOKS: listing("配饰 腰带", [sku("黑色", 6000)])}
EN = "Men's ncta jacket winter thick outdoor windproof cotton coat black"
VISION = {"斯图西 拉链卫衣 黑色": {"photo": 1, "title": "stussy Zip Hoodie Black", "brand": "stussy", "cat": "Tops", "item": "zip hoodie", "colour": "black", "g": "u"},
          "地毯 灰色": {"photo": 0, "title": "Kaws Companion Rug Grey", "brand": "Kaws", "cat": "Toys", "item": "rug", "colour": "grey", "g": "m"},
          "台灯": {"photo": 0, "title": "8 Ball Lamp Black", "brand": "", "cat": "Toys", "item": "lamp", "colour": "black", "g": "m"},
          "猿人头 地垫": {"photo": 0, "title": "Bape Camo Carpet", "brand": "A Bathing Ape", "cat": "Toys", "item": "carpet", "colour": "camo", "g": "m"},
          "拼图 短袖": {"photo": -1, "title": "Graphic T-Shirt", "brand": "", "cat": "Tops", "item": "t-shirt", "colour": "white", "g": "m"},
          "卫衣 复刻": {"photo": 0, "title": "Stussy Replica Hoodie Grey", "brand": "Stussy", "cat": "Tops", "item": "hoodie", "colour": "grey", "g": "m"},
          "同款 双胞胎": {"photo": 0, "title": TWIN["title"], "brand": TWIN["brand"], "cat": TWIN["cat"], "item": "x", "colour": "", "g": "m"},
          EN: {"photo": 0, "title": "Ncta Puffer Jacket Black", "brand": "", "cat": "Outerwear", "item": "puffer jacket", "colour": "black", "g": "m"},
          "配饰 腰带": {"photo": 0, "title": "Leather Belt Black", "brand": "", "cat": "Accessories", "item": "belt", "colour": "black", "g": "w"}}
PNG = io.BytesIO(); Image.new("RGB", (64, 64), (240, 240, 240)).save(PNG, "PNG"); PNG = PNG.getvalue()


class Resp(io.BytesIO):
    pass


def snap():
    """The real photo records as they are on disk (the tests must never change them)."""
    return {f: open(f, "rb").read() for f in sorted(glob.glob(os.path.join(ROOT, "data", "sheet_photos", "*")))}


REAL_PHOTOS = snap()


def fake_urlopen(req, timeout=None):
    url = req.full_url if isinstance(req, urllib.request.Request) else req
    CALLS.append(url)
    if "getDetailDesc" in url or url.startswith("https://weidian.com/item.html"):
        raise urllib.error.URLError("no gallery in the test")
    if url.startswith("https://thor.weidian.com/"):
        iid = json.loads(urllib.parse.unquote(url.split("param=", 1)[1]))["itemId"]
        if iid == ERR: return Resp(json.dumps({"status": {"code": 2, "message": "Login Error"}}).encode())
        return Resp(json.dumps({"status": {"code": 0}, "result": THOR[iid]}, ensure_ascii=False).encode())
    if "geilicdn.com/" in url or "alicdn.com/" in url: return Resp(PNG)
    if url == "https://api.anthropic.com/v1/messages":
        body = json.loads(req.data)
        text = " ".join(c.get("text", "") for c in body["messages"][0]["content"] if c["type"] == "text")
        PROMPTS.append(text)
        zh = next(k for k in VISION if json.dumps(k, ensure_ascii=False) in text)
        return Resp(json.dumps({"content": [{"type": "text", "text": json.dumps(VISION[zh])}], "usage": {"input_tokens": 900, "output_tokens": 60}}).encode())
    raise AssertionError("unexpected network call: " + url)


@contextlib.contextmanager
def sandbox():
    """The sheet's list, stage and photo records in a temp folder; the fake network; no sleeping."""
    tmp = tempfile.mkdtemp()
    old = (IS.LIST, dict(IA.SETS["murphy"]), urllib.request.urlopen, time.sleep, os.environ.get("ANTHROPIC_API_KEY"), IS.DETAILS)
    IS.LIST, IS.DETAILS = os.path.join(tmp, "list.json"), os.path.join(tmp, "details.json")
    json.dump({"source": "test", "items": LIST}, open(IS.LIST, "w"), ensure_ascii=False)
    IA.SETS["murphy"].update(stage=os.path.join(tmp, "stage"), photos=os.path.join(tmp, "photos"))
    urllib.request.urlopen = fake_urlopen; time.sleep = lambda s: None
    os.environ["ANTHROPIC_API_KEY"] = "test"
    try:
        yield tmp
    finally:
        IS.LIST, urllib.request.urlopen, time.sleep, IS.DETAILS = old[0], old[2], old[3], old[5]
        IA.SETS["murphy"].clear(); IA.SETS["murphy"].update(old[1])
        if old[4] is None: os.environ.pop("ANTHROPIC_API_KEY", None)
        else: os.environ["ANTHROPIC_API_KEY"] = old[4]
        shutil.rmtree(tmp)


def run_stage(*extra):
    del CALLS[:]; IF.spent = 0.0
    IS.main(["stage", "--pause", "0"] + list(extra))
    return IA.staged("murphy", every=True)


def test_stage():
    with sandbox() as tmp:
        st = run_stage()
        S = {k: v.get("status") for k, v in st.items()}
        ok(S[HOODIE] == "staged", "a Weidian item is staged: %s" % st.get(HOODIE))
        r = st[HOODIE]["row"]
        ok(r["platform"] == "weidian" and r["id"] == r["itemId"] == HOODIE and r["seller"] == "Weidian", "row ids: %s" % r)
        ok(r["price"] == 189 and r["usd"] == round(189 / IA.RATE, 2), "the cheapest real variant, not the 1 yuan link: %s" % r["price"])
        ok(r["brand"] == "Stussy" and r["title"] == "Stussy Zip Hoodie Black", "brand as the catalogue spells it: %s / %s" % (r["brand"], r["title"]))
        ok(r["cat"] == "Tops" and r["g"] == "m" and r["variants"] == [["Black", 189]], "category, gender, variants: %s" % r)
        ok("ar" not in r and "img" not in r, "no Archive mark, no photo yet")
        ok(st[HOODIE]["src"] == "https:" + THOR[HOODIE]["attrList"][0]["attrValues"][0]["img"], "src is the photo the vision chose, https: %s" % st[HOODIE]["src"])
        p = next(t for t in PROMPTS if "斯图西" in t)
        ok('"stussy zip (heavy)"' in p and '"Hoodies"' in p and "An earlier look" not in p, "the sheet's name and tab in the prompt")
        ok("add your name" not in next(t for t in PROMPTS if "配饰" in t), "the sheet's placeholder name is not a hint")
        for x in (RUG, DECOR, CARPET):
            ok(S[x] == "staged" and st[x]["row"]["cat"] == "Accessories", "rugs and room decor are Accessories: %s %s" % (x, st[x]))
        ok(st[CARPET]["row"]["brand"] == "Bape", "A Bathing Ape is Bape")
        ok(st[LOOKS]["row"]["g"] == "w", "women's find")
        ok(S[SOLD] == "sold out" and S[GONE] == "gone" and S[NOPRICE] == "no price", "sold out, gone, placeholder prices: %s" % ([S[SOLD], S[GONE], S[NOPRICE]],))
        ok(S[DEPOSIT] == "skipped" and "deposit" in st[DEPOSIT]["why"], "a deposit price against the sheet's: %s" % st[DEPOSIT])
        ok(S[BADPHOTO] == "badphoto", "no clean photo")
        ok(S[BANNED] == "skipped" and "banned" in st[BANNED]["why"], "a banned word in the title: %s" % st[BANNED])
        ok(S[TWIN_ID] == "skipped" and "same model" in st[TWIN_ID]["why"], "same brand, model and colour as a find on the site: %s" % st[TWIN_ID])
        ok(S[ON_SITE] == "skipped" and "same id" in st[ON_SITE]["why"], "an id the site has")
        ok(S["2055316446993086619623"] == "skipped", "an id that cannot be a Weidian item")
        ok(S["7999300000001"] == "needs details" and S["719154287380"] == "needs details", "Taobao and 1688 wait for details")
        ok(S[ERR] == "error" and st[ERR]["tries"] == 1, "an error is kept and tried again: %s" % st[ERR])
        asked = {json.loads(urllib.parse.unquote(u.split("param=", 1)[1]))["itemId"] for u in CALLS if "getItemSkuInfo" in u}
        ok(asked == NET, "Weidian asked only for the Weidian items that need it: %s" % sorted(asked ^ NET))
        ok(not any("taobao" in u or "1688" in u for u in CALLS), "no call for Taobao or 1688")
        ok(sorted(os.listdir(os.path.join(tmp, "stage"))) == ["0-of-1.json"], "one stage file for the shard")
        st = run_stage()
        ok({u.split("param=")[-1] for u in CALLS if "thor." in u} == {urllib.parse.quote(json.dumps({"itemId": ERR}))}, "a run again asks only for the error: %s" % CALLS[:3])
        st = run_stage()
        ok(st[ERR]["status"] == "failed" and st[ERR]["tries"] == 3, "given up after three tries: %s" % st[ERR])
        st = run_stage()
        ok(not CALLS, "nothing left to ask")
        out = io.StringIO()
        with contextlib.redirect_stdout(out): IS.main(["report"])
        ok(out.getvalue().strip().endswith("left %d" % sum(1 for v in st.values() if v["status"] == "staged")), "report: every staged find still needs its photo: " + out.getvalue()[-80:])
    with sandbox() as tmp:
        run_stage("--shard", "0/2"); a = set(IA.staged("murphy", every=True))
        run_stage("--shard", "1/2"); b = set(IA.staged("murphy", every=True)) - a
        ok(sorted(os.listdir(os.path.join(tmp, "stage"))) == ["0-of-2.json", "1-of-2.json"], "each shard its own file")
        ok(a | b == {it["id"] for it in LIST} and not a & b, "the shards share the list out")


def test_details():
    tb, cn = "7999300000001", "719154287380"
    with sandbox() as tmp:
        st = run_stage()
        ok(st[tb]["status"] == st[cn]["status"] == "needs details", "no entry yet: needs details")
        json.dump({"items": {tb: {"platform": "taobao", "src": "//img.alicdn.com/imgextra/i1/a.jpg", "title_en": EN, "cny": 239.6},
                             cn: {"platform": "1688", "src": "https://si.geilicdn.com/x.jpg", "title_en": "pillow", "cny": 15}}},
                  open(IS.DETAILS, "w"), ensure_ascii=False)
        del PROMPTS[:]
        st = run_stage()
        r = (st[tb].get("row") or {})
        ok(st[tb]["status"] == "staged", "a Taobao item staged from its details: %s" % st[tb])
        ok(r.get("platform") == "taobao" and r.get("seller") == "Taobao Marketplace" and "itemId" not in r, "Taobao row: %s" % r)
        ok(r.get("price") == 240 and r.get("title") == "Ncta Puffer Jacket Black" and r.get("cat") == "Outerwear", "price from cny, the vision's title: %s" % r)
        ok(st[tb].get("src") == "https://img.alicdn.com/imgextra/i1/a.jpg" and st[tb].get("en") == EN, "the entry's photo, https")
        ok(len(PROMPTS) == 1 and "Taobao listing" in PROMPTS[0] and json.dumps(EN) in PROMPTS[0] and '"Ncta jacket"' in PROMPTS[0],
           "one vision call with the entry's title and the sheet's name")
        asked = {json.loads(urllib.parse.unquote(u.split("param=", 1)[1]))["itemId"] for u in CALLS if "thor." in u}
        ok(asked == {ERR} and any("img.alicdn.com" in u for u in CALLS), "no Weidian call for it, the entry's photo: %s" % asked)
        ok(st[cn]["status"] == "needs details" and "alicdn" in st[cn]["why"], "an entry with a photo off alicdn is not used: %s" % st[cn])
        out = io.StringIO()
        with contextlib.redirect_stdout(out): IS.main(["report"])
        n = len(IA.staged("murphy")) + 1     # the staged finds' photos and the Weidian item that errored
        ok(out.getvalue().strip().endswith("left %d" % n), "report: the unusable entry is not work left: " + out.getvalue()[-60:])
        IA.save_json(os.path.join(tmp, "photos", "0-of-1.json"), {"items": {tb: {"status": "cut", "url": IA.PUB + "products/pc2/%s-t1.webp" % tb}}})
        IA.main(["apply", "--set", "murphy", "--out", os.path.join(tmp, "i.html")])
        h = open(os.path.join(tmp, "i.html"), encoding="utf-8").read(); s = h.find(IA.TAG) + len(IA.TAG)
        last = json.loads(h[s:h.find("</script>", s)])[-1]
        ok(last["id"] == tb and last["platform"] == "taobao" and "ar" not in last, "the Taobao find added without ar: %s" % last)


def test_photos_set():
    with sandbox() as tmp:
        run_stage()
        old_fetch, old_key = AP.fetch, os.environ.get("SUPABASE_SERVICE_KEY")
        AP.fetch = lambda url: None
        os.environ["SUPABASE_SERVICE_KEY"] = "test"
        try:
            AP.main(["--set", "murphy", "--no-vision", "--sheets", os.path.join(tmp, "sheets")])
        finally:
            AP.fetch = old_fetch
            if old_key is None: os.environ.pop("SUPABASE_SERVICE_KEY", None)
            else: os.environ["SUPABASE_SERVICE_KEY"] = old_key
        recs = json.load(open(os.path.join(tmp, "photos", "0-of-1.json")))["items"]
        ok(set(recs) == set(IA.staged("murphy")) and all(r["status"] == "gone" for r in recs.values()), "photo records of the sheet's staged finds: %s" % sorted(recs))
        ok(snap() == REAL_PHOTOS, "nothing written to the real records")
    seen = []

    def grab(req, timeout=None):
        seen.append(dict(req.header_items())); return Resp(PNG)
    old = urllib.request.urlopen; urllib.request.urlopen = grab
    try:
        AP.fetch("https://si.geilicdn.com/x.jpg"); AP.fetch("https://cbu01.alicdn.com/y.jpg")
    finally:
        urllib.request.urlopen = old
    ok(seen[0].get("Referer") == "https://weidian.com/" and "Referer" not in seen[1], "Weidian photos with the Weidian referrer: %s" % seen)


def test_apply():
    real = open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()
    with sandbox() as tmp:
        run_stage()
        staged = IA.staged("murphy")
        # two more staged finds of the same made-up model (two sellers of one design, staged by two shards)
        extra = {}
        for k, x in enumerate(("7999200001", "7999200002")):
            row = dict(staged[HOODIE]["row"], id=x, itemId=x, title="Stussy Zorblax Quantum Hoodie Black")
            extra[x] = {"status": "staged", "row": row, "src": "https://si.geilicdn.com/z%d.jpg" % k, "rule": IS.RULE}
        IA.save_json(os.path.join(tmp, "stage", "1-of-2.json"), {"items": extra})
        cut = [HOODIE, RUG, CARPET, "7999200001", "7999200002"]
        recs = {x: {"status": "cut", "url": IA.PUB + "products/pc2/%s-t1.webp" % x} for x in cut}
        recs[DECOR] = {"status": "kept", "why": ["vision: a hand"]}
        IA.save_json(os.path.join(tmp, "photos", "0-of-1.json"), {"items": recs})
        out = os.path.join(tmp, "index.html")
        IA.main(["apply", "--set", "murphy", "--out", out])
        new = open(out, encoding="utf-8").read()
        ok(open(os.path.join(ROOT, "index.html"), encoding="utf-8").read() == real, "index.html itself untouched (written to the copy)")
        s, e = S0, new.find("</script>", S0)
        ok(new[:s] == HTML[:S0] and new[e:] == HTML[E0:], "nothing outside the catalogue block changes")
        body = HTML[S0:E0].rstrip()
        ok(new[s:e].startswith(body[:-1]), "every existing row is byte for byte the same")
        rows = json.loads(new[s:e])
        ok(rows[:len(ITEMS)] == ITEMS, "existing rows first, unchanged")
        added = rows[len(ITEMS):]
        ok([r["id"] for r in added] == [HOODIE, RUG, CARPET, "7999200001"], "added the finds with a cut-out, the same model once: %s" % [r["id"] for r in added])
        ok(all("ar" not in r for r in added), "no Archive mark on the sheet's finds")
        ok(all(r["img"] == IA.PUB + "products/pc2/%s-t1.webp" % r["id"] for r in added), "the cut-out from storage")
        ok(next(r for r in added if r["id"] == RUG)["cat"] == "Accessories", "the rug under Accessories")
    # the Archive set still adds its mark
    tmp = tempfile.mkdtemp()
    old = (IA.STAGE, IA.PHOTOS_DIR)
    try:
        IA.STAGE, IA.PHOTOS_DIR = os.path.join(tmp, "a.json"), os.path.join(tmp, "ap")
        row = {"id": "897026768889", "platform": "1688", "cat": "Accessories", "brand": "Dior", "title": "Dior Comb", "price": 120,
               "usd": 16.8, "qc": 0, "seller": "1688 Marketplace", "rating": 0, "views": 0, "variants": [["Standard", 120]], "g": "m"}
        if row["id"] not in HAVE:
            IA.save_json(IA.STAGE, {"items": {row["id"]: {"row": row, "src": "https://cbu01.alicdn.com/a.jpg"}}})
            IA.save_json(os.path.join(IA.PHOTOS_DIR, "0-of-1.json"), {"items": {row["id"]: {"status": "cut", "url": IA.PUB + "products/pc2/897026768889-t1.webp"}}})
            IA.main(["apply", "--out", os.path.join(tmp, "i.html")])
            h = open(os.path.join(tmp, "i.html"), encoding="utf-8").read(); s = h.find(IA.TAG) + len(IA.TAG)
            last = json.loads(h[s:h.find("</script>", s)])[-1]
            ok(last["id"] == row["id"] and last.get("ar") == 1, "the Archive set keeps its mark")
    finally:
        IA.STAGE, IA.PHOTOS_DIR = old
        shutil.rmtree(tmp)
    ok(IA.row_problems(dict(row, platform="weidian"), IA.SETS["murphy"]["platforms"]) == [], "weidian rows for the sheet")
    ok(IA.row_problems(dict(row, platform="weidian")), "never weidian for the Archive")


def test_photo_rule():
    """Photo rule 2 (27 Nov 2026): the gallery and description photos, an older staged record staged again, a changed photo
    cut again under a new name."""
    page = ('<script>x={&#34;imgs&#34;:[&#34;https://si.geilicdn.com/open1-a_1284_1284.jpg&#34;,'
            '&#34;https://si.geilicdn.com/open1-b_1000_1000.jpg&#34;]}</script>')
    desc = {"status": {"code": 0}, "result": {"item_detail": {"desc_content": [
        {"type": 2, "url": "https://si.geilicdn.com/open1-b_1000_1000.jpg"},          # the same as the gallery's
        {"type": 2, "url": "https://si.geilicdn.com/img-c_750_4000.jpg"},             # a long strip: left out
        {"type": 2, "url": "https://si.geilicdn.com/open1-d_800_800.jpg"}, {"type": 1, "text": "x"}]}}}

    def net(req, timeout=None):
        u = req.full_url
        if u.startswith("https://weidian.com/item.html"): return Resp(page.encode())
        if "getDetailDesc" in u: return Resp(json.dumps(desc).encode())
        raise AssertionError(u)
    old = urllib.request.urlopen; urllib.request.urlopen = net
    try:
        got = IS.more_photos("7999100001", ["https://si.geilicdn.com/open1-a_1284_1284.jpg.webp?w=750&h=750"])
    finally:
        urllib.request.urlopen = old
    ok([u for _, u in got] == ["https://si.geilicdn.com/open1-b_1000_1000.jpg", "https://si.geilicdn.com/open1-d_800_800.jpg"],
       "gallery and description photos, new ones only, no strips: %s" % got)
    ok([l for l, _ in got] == ["gallery photo 1", "description photo 1"], "labelled for the vision call: %s" % got)
    ok(not IS.is_done({"status": "staged", "row": {}}, "1", {}), "a staged record of rule 1 is staged again")
    ok(IS.is_done({"status": "staged", "row": {}}, "1", {}, {"1"}), "never once the find is on the site")
    ok(IS.is_done({"status": "staged", "row": {}, "rule": IS.RULE}, "1", {}), "a record of the current rule is done")
    ok(not IS.is_done({"status": "badphoto"}, "1", {}) and IS.is_done({"status": "sold out"}, "1", {}), "badphoto again, sold out not")
    a, b = "https://si.geilicdn.com/a.jpg", "https://si.geilicdn.com/b.jpg"
    ok(AP.new_photo({"status": "cut", "src": a}, {"src": b}) and not AP.new_photo({"status": "cut", "src": a}, {"src": a}), "a changed photo is cut again")
    n = AP.object_name("7999100001", {"status": "cut", "src": a}, b)
    ok(n.startswith("products/pc2/7999100001-t1.v") and IA.IMG.match(IA.PUB + n) and AP.object_name("7999100001", None, b) == "products/pc2/7999100001-t1.webp",
       "a new object name for a changed photo, accepted by apply: %s" % n)


if __name__ == "__main__":
    test_photo_rule()
    test_stage()
    test_details()
    test_photos_set()
    test_apply()
    print("FAILED %d" % len(fails) if fails else "all passed")
    sys.exit(1 if fails else 0)
