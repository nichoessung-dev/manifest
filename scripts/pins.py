# -*- coding: utf-8 -*-
"""Keep a queue of Pinterest product pins in Postiz: popular products with a studio image, each linking to its product page.

  python scripts/pins.py            top the queue up (PIN_SLOTS a day, PIN_DAYS ahead)
  python scripts/pins.py --local D  only render one pin into folder D (no Postiz)

Env: POSTIZ_API_KEY, PINTEREST_BOARD (the board id; nothing is posted without it)
"""
import io, json, os, random, sys, urllib.request, urllib.parse
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_finds import font

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://www.puroclassico.com"
SLOTS = ["10:11", "18:41"]                                   # Norwegian time
DAYS = 4
TZ = ZoneInfo("Europe/Oslo")
UA = {"User-Agent": "Mozilla/5.0 (PuroClassicoPins)"}


def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40).read()


def candidates():
    """Most viewed and favourited products that have a clean studio image, best first."""
    prod = json.loads(get(SITE + "/products.json")); stats = json.loads(get(SITE + "/data/stats.json")).get("p") or {}
    def score(i): v = list(stats.get(i) or []) + [0, 0, 0, 0]; return 10 * v[3] + 2 * v[2] + v[1] + 0.05 * v[0]
    ids = [i for i, p in prod.items() if "/img/p/" in str(p.get("img") or "")]
    return prod, sorted(ids, key=lambda i: -score(i))


def render(p, out):
    """A 2:3 pin: the product on the site's light studio card, brand, title and price under it."""
    W, H = 1000, 1500; im = Image.new("RGB", (W, H), (237, 234, 229)); d = ImageDraw.Draw(im)
    src = Image.open(io.BytesIO(get(p["img"] if p["img"].startswith("http") else SITE + p["img"]))).convert("RGBA")
    box = src.getbbox() or (0, 0, src.width, src.height); src = src.crop(box)
    k = min(820 / src.width, 900 / src.height); src = src.resize((max(1, int(src.width * k)), max(1, int(src.height * k))), Image.LANCZOS)
    im.paste(src, ((W - src.width) // 2, 120 + (900 - src.height) // 2), src)
    y = 1090
    if p.get("brand"): d.text((W / 2, y), p["brand"].upper(), font=font(34), fill=(120, 116, 108), anchor="ma"); y += 62
    title = p.get("title") or ""; size = 64
    while size > 38 and d.textlength(title, font=font(size)) > W - 120: size -= 4
    d.text((W / 2, y), title, font=font(size), fill=(16, 18, 26), anchor="ma"); y += size + 34
    try: d.text((W / 2, y), "$%d" % round(float(p.get("usd") or 0)), font=font(54), fill=(16, 18, 26), anchor="ma")
    except Exception: pass
    d.text((W / 2, H - 78), "puroclassico.com", font=font(32), fill=(120, 116, 108), anchor="ma")
    im.save(out, quality=92); return out


def main():
    prod, order = candidates()
    if "--local" in sys.argv:
        out = sys.argv[sys.argv.index("--local") + 1]; os.makedirs(out, exist_ok=True)
        print(render(prod[order[0]], os.path.join(out, "pin-%s.jpg" % order[0]))); return
    board = os.environ.get("PINTEREST_BOARD", "").strip()
    if not board: print("PINTEREST_BOARD is not set - nothing to do"); return
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
            link = "%s/product/%s?ref=pin" % (SITE, urllib.parse.quote(pid))
            title = ("%s %s" % (p.get("brand") or "", p.get("title") or "")).strip() if (p.get("brand") or "") not in (p.get("title") or "") else p.get("title")
            text = "%s. Quality-checked find with QC photos, one tap from your agent. #oldmoney #fashionfinds #%s" % (title, "".join(c for c in (p.get("brand") or "style").lower() if c.isalnum()))
            body = {"type": "schedule", "date": t.strftime("%Y-%m-%dT%H:%M:%S.000Z"), "shortLink": False, "tags": [],
                    "posts": [{"integration": {"id": pin["id"]}, "value": [{"content": text, "image": [media]}],
                               "settings": {"__type": "pinterest", "board": board, "title": title[:100], "link": link, "dominant_color": ""}}]}
            P.call("POST", "/posts", body); used.append(pid); made += 1
            print("queued a pin for", t.astimezone(TZ).strftime("%a %d %b %H:%M"), "-", title)
    json.dump(used[-2000:], open(path, "w"), indent=0); print("new pins queued:", made)


if __name__ == "__main__":
    main()
