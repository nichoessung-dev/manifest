# -*- coding: utf-8 -*-
"""Keep a queue of Pinterest product pins in Postiz: popular finds with a clean cut-out photo, each linking to its product
page, each on the board of its category.

  python scripts/pins.py            top the queue up (SLOTS a day, DAYS ahead)
  python scripts/pins.py --local D  only render the first pins into folder D (no Postiz)
  python scripts/pins.py --boards   look up the board ids of BOARD_NAMES on Pinterest and write data/pinterest_boards.json

Boards (27 Nov 2026): data/pinterest_boards.json {"Tops": "<board id>", ...}, made by --boards from Pinterest's public
board widget; PINTEREST_BOARD (one board id for every pin) is the fallback. Nothing is posted without a board.
Env: POSTIZ_API_KEY, PINTEREST_BOARD (optional)
"""
import io, json, os, random, re, sys, urllib.request, urllib.parse
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_finds import font

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://www.puroclassico.com"
SLOTS = ["08:41", "11:13", "13:37", "16:09", "19:23", "21:47"]   # Norwegian time, 6 pins a day
DAYS = 4
PROFILE = "puroclassicocom"                                  # the Pinterest account connected in Postiz
# board name on Pinterest -> the site's categories that go on it (the owner made the boards with these names)
BOARD_NAMES = {"Sneaker finds": ["Shoes"], "Hoodie and tee finds": ["Tops"], "Jacket and coat finds": ["Outerwear"],
               "Pants and shorts finds": ["Pants", "Shorts"], "Bag finds": ["Bags"],
               "Accessories and jewelry finds": ["Accessories", "Headwear", "Toys"]}
CATCH_ALL = "Fashion finds"                                  # one board for every find the boards above do not take
BOARDS_FILE = os.path.join(ROOT, "data", "pinterest_boards.json")
# a clean cut-out photo, as functions/_lib/photo_tiles.js CUT_RX (the path of the photo link)
CUT_RX = re.compile(r"^/(?:storage/v1/object/public/products|img/m)/pc2/[\w-]+-[et]1(?:\.v[\w-]+)?\.webp$|^/img/(?:rl|fr|cut)/[\w-]+-e1\.webp$"
                    r"|^/storage/v1/object/public/products/store2/[\w.-]+-t1\.webp$|^/storage/v1/object/public/products/pc/[\w-]+\.webp$"
                    r"|^/img/p2?/[\w-]+\.webp$")
TZ = ZoneInfo("Europe/Oslo")
UA = {"User-Agent": "Mozilla/5.0 (PuroClassicoPins)"}


def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40).read()


def clean_photo(img):
    """The find's photo is a clean cut-out (no seller backdrop, no text)."""
    return bool(CUT_RX.match(urllib.parse.urlparse(str(img or "")).path))


def candidates():
    """Finds with a clean cut-out photo, most viewed and saved first (QC photos count too)."""
    prod = json.loads(get(SITE + "/products.json")); stats = json.loads(get(SITE + "/data/stats.json")).get("p") or {}
    def score(i):
        v = list(stats.get(i) or []) + [0, 0, 0, 0]
        return 10 * v[3] + 2 * v[2] + v[1] + 0.05 * v[0] + (3 if (prod[i].get("qc") or 0) > 0 else 0)
    ids = [i for i, p in prod.items() if clean_photo(p.get("img")) and p.get("title") and sane(p)]
    return prod, sorted(ids, key=lambda i: -score(i))


def boards():
    """{category: board id} from data/pinterest_boards.json, else every category on PINTEREST_BOARD; {} when neither."""
    try: m = {k: str(v) for k, v in json.load(open(BOARDS_FILE)).get("boards", {}).items() if v}
    except Exception: m = {}
    one = os.environ.get("PINTEREST_BOARD", "").strip()
    if one: m.setdefault("*", one)
    return m


def board_of(p, m):
    return m.get(p.get("cat") or "") or m.get("*") or next(iter(v for k, v in m.items() if k != "*"), "")


def find_boards():
    """The ids of BOARD_NAMES on PROFILE, from Pinterest's public board widget (no login), into BOARDS_FILE."""
    out, missing = {}, []
    for name, cats in list(BOARD_NAMES.items()) + [(CATCH_ALL, ["*"])]:
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        try:
            d = json.loads(get("https://widgets.pinterest.com/v3/pidgets/boards/%s/%s/pins/" % (PROFILE, slug)))
            bid = str(((d.get("data") or {}).get("board") or {}).get("id") or "")
        except Exception:
            bid = ""
        if not bid: missing.append(name); continue
        for c in cats: out[c] = bid
        print("board %s: %s" % (name, bid))
    if out:
        json.dump({"profile": PROFILE, "boards": out, "names": BOARD_NAMES}, open(BOARDS_FILE, "w"), indent=1)
    print("boards found %d of %d%s" % (len(BOARD_NAMES) + 1 - len(missing), len(BOARD_NAMES) + 1, ("; missing: " + ", ".join(missing)) if missing else ""))


def sane(p):
    """A price a shopper believes (a $7 watch is a deposit or a placeholder line)."""
    usd, t = float(p.get("usd") or 0), (p.get("title") or "").lower()
    low = 20 if "watch" in t else 10 if p.get("cat") in ("Bags", "Shoes", "Outerwear") else 4
    return low <= usd <= 600


def pin_title(t):
    """The title for a pin: never the words replica, fake or 1:1 (Margiela's Replica line is the GAT)."""
    t = re.sub(r"(?i)\breplica\b", "GAT", t or "")
    return re.sub(r"\s+", " ", re.sub(r"(?i)\b(fake|1:1)\b", "", t)).strip()


def tag(s):
    return "".join(c for c in (s or "").lower() if c.isalnum())


def render(p, out):
    """A 2:3 pin: the product on the site's light studio card, brand, title and price under it."""
    W, H = 1000, 1500; im = Image.new("RGB", (W, H), (237, 234, 229)); d = ImageDraw.Draw(im)
    src = Image.open(io.BytesIO(get(p["img"] if p["img"].startswith("http") else SITE + p["img"]))).convert("RGBA")
    box = src.getbbox() or (0, 0, src.width, src.height); src = src.crop(box)
    k = min(820 / src.width, 900 / src.height); src = src.resize((max(1, int(src.width * k)), max(1, int(src.height * k))), Image.LANCZOS)
    im.paste(src, ((W - src.width) // 2, 120 + (900 - src.height) // 2), src)
    y = 1090
    if p.get("brand"): d.text((W / 2, y), p["brand"].upper(), font=font(34), fill=(120, 116, 108), anchor="ma"); y += 62
    title = pin_title(p.get("title")); size = 64
    while size > 38 and d.textlength(title, font=font(size)) > W - 120: size -= 4
    d.text((W / 2, y), title, font=font(size), fill=(16, 18, 26), anchor="ma"); y += size + 34
    try: d.text((W / 2, y), "$%d" % round(float(p.get("usd") or 0)), font=font(54), fill=(16, 18, 26), anchor="ma")
    except Exception: pass
    d.text((W / 2, H - 78), "puroclassico.com", font=font(32), fill=(120, 116, 108), anchor="ma")
    im.save(out, quality=92); return out


def main():
    if "--boards" in sys.argv: return find_boards()
    prod, order = candidates()
    if "--local" in sys.argv:
        out = sys.argv[sys.argv.index("--local") + 1]; os.makedirs(out, exist_ok=True)
        for i in order[:6]: print(render(prod[i], os.path.join(out, "pin-%s.jpg" % i)))
        return
    bmap = boards()
    if not bmap:
        find_boards(); bmap = boards()
    if not bmap: print("no Pinterest board yet (make the boards in BOARD_NAMES on Pinterest): nothing to do"); return
    import post_short as P
    ints = P.call("GET", "/integrations"); ints = ints if isinstance(ints, list) else ints.get("integrations", [])
    pin = next((i for i in ints if (i.get("identifier") or i.get("providerIdentifier")) == "pinterest" and not i.get("disabled")), None)
    if not pin: print("no Pinterest channel in Postiz"); return
    now = datetime.now(timezone.utc)
    q = "?startDate=%s&endDate=%s" % ((now - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S.000Z"), (now + timedelta(days=DAYS + 1)).strftime("%Y-%m-%dT%H:%M:%S.000Z"))
    have = []
    for p in P.call("GET", "/posts" + q).get("posts", []):
        if (p.get("integration") or {}).get("id") != pin["id"]: continue
        try: have.append(datetime.strptime((p.get("publishDate") or "")[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc))
        except Exception: pass
    path = os.path.join(ROOT, "pins_used.json")
    try: used = json.load(open(path))
    except Exception: used = []
    fresh = [i for i in order if i not in used] or order         # start over once every product has had a pin
    out = os.path.join(ROOT, "out", "pins"); os.makedirs(out, exist_ok=True); made = 0
    for d in range(DAYS + 1):
        day = (now.astimezone(TZ) + timedelta(days=d)).date()
        for s in SLOTS:
            t = datetime(day.year, day.month, day.day, int(s[:2]), int(s[3:]), tzinfo=TZ).astimezone(timezone.utc)
            if not (now + timedelta(minutes=20) <= t <= now + timedelta(days=DAYS)) or any(abs((t - h).total_seconds()) < 1800 for h in have) or not fresh: continue
            pid = fresh.pop(0); p = prod[pid]
            media = P.upload(render(p, os.path.join(out, "pin-%s.jpg" % pid)))
            # ref=pin stays (the site saves it as the sign-up channel); the utm tags give /admin the source and campaign
            link = "%s/product/%s?ref=pin&utm_source=pinterest&utm_medium=social&utm_campaign=pin" % (SITE, urllib.parse.quote(pid))
            title = pin_title(("%s %s" % (p.get("brand") or "", p.get("title") or "")).strip() if (p.get("brand") or "") not in (p.get("title") or "") else p.get("title"))
            shop = {"weidian": "Weidian", "taobao": "Taobao", "1688": "1688"}.get(p.get("platform") or "", "")
            price = ("about $%d" % round(float(p.get("usd") or 0))) if p.get("usd") else ""
            text = "%s, %s%s. Opens on MyCNBox, KakoBuy, Oopbuy and 14 more shopping agents, with size advice on Puro Classico. %s" % (
                title, price, (" on " + shop) if shop else "",
                " ".join("#" + t for t in dict.fromkeys([tag(p.get("brand")), tag(shop) + "finds" if shop else "", "fashionfinds", tag(p.get("cat"))]) if t))
            board = board_of(p, bmap)
            if not board: continue
            body = {"type": "schedule", "date": t.strftime("%Y-%m-%dT%H:%M:%S.000Z"), "shortLink": False, "tags": [],
                    "posts": [{"integration": {"id": pin["id"]}, "value": [{"content": text, "image": [media]}],
                               "settings": {"__type": "pinterest", "board": board, "title": title[:100], "link": link, "dominant_color": ""}}]}
            P.call("POST", "/posts", body); used.append(pid); made += 1
            print("queued a pin for", t.astimezone(TZ).strftime("%a %d %b %H:%M"), "-", title)
    json.dump(used[-2000:], open(path, "w"), indent=0); print("new pins queued:", made)


if __name__ == "__main__":
    main()
