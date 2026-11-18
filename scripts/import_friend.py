# -*- coding: utf-8 -*-
"""Add the friend's listings that are not on the site yet as new finds (data/friend_finds.json, 18 Nov 2026).

Owner: "im going to list all of his products". scripts/match_friend.py first looks for an existing find of each listing (a match
becomes a partner swap on that find); the listings it found none for ("nomatch") are added here as new finds, and
scripts/friend_swaps.py gives each new find a swap to itself, so it gets the Recommended badge and the top priority group.

Per find, one at a time with a pause (resumable: data/friend_import.json keeps every find's state and staged row):
  1. Weidian getItemSkuInfo: Chinese title, main photo, price (fen), colour options. Gone or sold-out listings are skipped.
  2. One vision call (claude-haiku-5-5) on the main photo + the Chinese title: English title in the site's style
     ("Brand Item Colour", e.g. "Argentina 2026 Home Jersey"), brand ("" when there is none), category (the site's nine),
     item type, colour, gender, and English names for the colour options.
  3. The photo is cut out (rembg isnet-general-use) onto a transparent canvas, at most 1600 px, WebP, and saved as
     img/fr/<id>.webp (a site file, like img/rl). A cut-out that looks wrong (almost nothing kept, or almost everything)
     keeps the original photo instead, noted in the state file.
  4. Finds whose photo is in place are appended to the pc-catalog block of index.html (surgical append, existing rows
     untouched, never a find already in the catalogue).
The Import friend's finds workflow runs it, then gen_catalog.py and sync_catalog.py, and commits. Run until "left 0".

  python scripts/import_friend.py [--max-minutes 50] [--limit N] [--max-usd 20] [--dry-run]
"""
import argparse, base64, io, json, os, re, sys, time, urllib.parse, urllib.request
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TAG = '<script type="application/json" id="pc-catalog">'
LIST = os.path.join(ROOT, "data", "friend_finds.json")
STATE = os.path.join(ROOT, "data", "friend_import.json")
IMG_DIR = os.path.join(ROOT, "img", "fr")
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
H = {"User-Agent": UA, "Referer": "https://weidian.com/"}
CATS = ["Tops", "Outerwear", "Shoes", "Pants", "Shorts", "Bags", "Accessories", "Headwear", "Toys"]
RATE = 7.142857   # CNY per USD, the catalogue's own rate
MAX_FILES = 19500
MODEL = os.environ.get("FRIEND_MODEL", "claude-haiku-5-5")
spent = 0.0


def wd(item_id):
    url = "https://thor.weidian.com/detail/getItemSkuInfo/1.0?param=" + urllib.parse.quote(json.dumps({"itemId": str(item_id)}))
    for wait in (0, 5, 15, 40):
        if wait: time.sleep(wait)
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=25) as r: d = json.load(r)
            if (d.get("status") or {}).get("code") == 0: return d.get("result") or {}
        except Exception: pass
    return None


def get_img(u):
    with urllib.request.urlopen(urllib.request.Request(u, headers=H), timeout=40) as r:
        im = Image.open(io.BytesIO(r.read())); im.load(); return im


def jpg64(im, side=512):
    im = im.convert("RGB"); im.thumbnail((side, side)); b = io.BytesIO(); im.save(b, "JPEG", quality=85)
    return base64.b64encode(b.getvalue()).decode()


def classify(im, zh, opts):
    global spent
    prompt = ("This is a product listing from a Chinese Weidian store. Chinese title: " + json.dumps(zh, ensure_ascii=False) +
              ". Colour options: " + json.dumps(opts, ensure_ascii=False) + ".\n"
              "Write the catalogue entry in English. Rules: title in the form 'Brand Item Colour' (short, 2-6 words, Title Case, "
              "no codes like DX1-7 or CY, no words like replica, fake, rep, 1:1, custom). Football kits: team, season and kit, e.g. "
              "'Argentina 2026 Home Jersey', 'Germany 2024/25 Training Hoodie'; brand = the kit maker if its logo is visible, else the "
              "team name. Brand '' when the item has no clear brand. cat is exactly one of " + json.dumps(CATS) + ". item is the "
              "item type (T-Shirt, Hoodie, Jersey, Belt, Shorts ...). colour is the main colour of the item in the photo. g is 'm', "
              "'w' or 'u' (unisex). colours: English names for the colour options, same order. "
              'Answer only JSON, no code fence: {"title":"","brand":"","cat":"","item":"","colour":"","g":"m","colours":[]}')
    body = json.dumps({"model": MODEL, "max_tokens": 2000, "messages": [{"role": "user", "content": [
        {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": jpg64(im)}},
        {"type": "text", "text": prompt}]}]}).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, headers={
        "x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01", "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r: d = json.load(r)
    u = d.get("usage") or {}; spent += (u.get("input_tokens", 0) * 1.0 + u.get("output_tokens", 0) * 5.0) / 1e6
    m = re.search(r"\{.*\}", "".join(c.get("text", "") for c in d.get("content", [])), re.S)
    return json.loads(m.group(0)) if m else {}


_sess = None
def cutout(im):
    """Transparent cut-out at most 1600 px; None when the mask looks wrong."""
    global _sess
    from rembg import remove, new_session
    if _sess is None: _sess = new_session("isnet-general-use")
    src = im.convert("RGB")
    if max(src.size) > 1600: src.thumbnail((1600, 1600), Image.LANCZOS)
    out = remove(src, session=_sess).convert("RGBA")
    a = out.getchannel("A"); h = a.histogram(); cover = sum(h[128:]) / max(1, sum(h))
    if not 0.04 <= cover <= 0.9: return None
    box = a.point(lambda v: 255 if v >= 24 else 0).getbbox()
    if not box: return None
    item = out.crop(box); side = int(max(item.size) / 0.86)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.alpha_composite(item, ((side - item.width) // 2, (side - item.height) // 2))
    if side > 1600: canvas = canvas.resize((1600, 1600), Image.LANCZOS)
    return canvas


def save_webp(im, dest):
    b = io.BytesIO(); im.save(b, "WEBP", quality=82, method=5)
    open(dest + ".part", "wb").write(b.getvalue()); os.replace(dest + ".part", dest)


def price_of(res):
    for k in ("itemDiscountLowPrice", "itemLowPrice", "itemOriginalLowPrice"):
        v = res.get(k)
        if isinstance(v, (int, float)) and v > 0: return round(v / 100)
    return 0


def repo_files():
    n = 0
    for dp, dn, fn in os.walk(ROOT):
        dn[:] = [d for d in dn if d not in (".git", ".github")]; n += len(fn)
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-minutes", type=float, default=50); ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--max-usd", type=float, default=20); ap.add_argument("--pause", type=float, default=0.6)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    ids = json.load(open(LIST, encoding="utf-8"))["ids"]
    st = json.load(open(STATE, encoding="utf-8")) if os.path.exists(STATE) else {"items": {}}
    items = st.setdefault("items", {})
    path = os.path.join(ROOT, "index.html"); html = open(path, encoding="utf-8").read()
    i = html.find(TAG); s = i + len(TAG); e = html.find("</script>", s); raw = html[s:e]
    have = {str(p["id"]) for p in json.loads(raw)}
    # only the listings scripts/match_friend.py found NO existing find for: a matched one takes over that find instead
    # (a partner swap), and a listing it has not looked at yet waits for it
    mt = (json.load(open(os.path.join(ROOT, "data", "friend_match.json"), encoding="utf-8")) if os.path.exists(os.path.join(ROOT, "data", "friend_match.json")) else {}).get("items") or {}
    todo = [x for x in ids if x not in have and (mt.get(x) or {}).get("status") == "nomatch" and (items.get(x) or {}).get("status") not in ("ok", "gone")]
    files = repo_files()
    print(f"friend list {len(ids)}, in catalogue {sum(1 for x in ids if x in have)}, to process {len(todo)}, site files {files}")
    if files + len(todo) > MAX_FILES: sys.exit("stopping: the photos would pass the Cloudflare Pages file limit")
    if a.dry_run: return
    os.makedirs(IMG_DIR, exist_ok=True)
    t0, done = time.time(), 0
    for x in todo:
        if time.time() - t0 > a.max_minutes * 60 or (a.limit and done >= a.limit) or spent >= a.max_usd:
            print("time, count or budget limit reached; the next run goes on"); break
        rec = {"date": time.strftime("%Y-%m-%d")}
        try:
            res = wd(x); time.sleep(a.pause)
            if res is None: rec.update(status="error", note="weidian did not answer")
            elif not (res.get("itemTitle") or res.get("itemMainPic")): rec.update(status="gone", note="listing gone")
            else:
                stock = res.get("itemStock")
                if isinstance(stock, (int, float)) and stock <= 0: rec.update(status="gone", note="sold out")
                else:
                    zh = res.get("itemTitle") or ""
                    opts = [str(v.get("attrValue") or "") for at in (res.get("attrList") or []) for v in (at.get("attrValues") or []) if v.get("img")][:12]
                    im = get_img(res["itemMainPic"])
                    c = classify(im, zh, opts)
                    if c.get("cat") not in CATS or not c.get("title"):
                        c = dict((mt.get(x) or {}).get("cls") or {}, g="m", colours=[])   # the matcher's naming of the same listing
                    if c.get("cat") not in CATS or not c.get("title"): raise RuntimeError("classification failed: " + json.dumps(c)[:120])
                    cut = cutout(im)
                    save_webp(cut if cut is not None else im.convert("RGB"), os.path.join(IMG_DIR, x + ".webp"))
                    price = price_of(res)
                    names = [n for n in (c.get("colours") or []) if n][:12] or [c.get("colour") or "Standard"]
                    title = re.sub(r"\s+", " ", str(c["title"]).replace("—", " ").replace("–", " ")).strip()
                    row = {"id": x, "platform": "weidian", "itemId": x, "cat": c["cat"], "brand": (c.get("brand") or "").strip(),
                           "title": title, "price": price, "usd": round(price / RATE, 2), "qc": 0, "seller": "Weidian",
                           "rating": 0, "views": 0, "variants": [[n, price] for n in names], "img": f"/img/fr/{x}.webp",
                           "g": c.get("g") if c.get("g") in ("m", "w") else "m"}
                    rec.update(status="ok", row=row, zh=zh, item=c.get("item"), cutout=cut is not None)
                    done += 1
        except Exception as ex:   # noqa: BLE001 (kept as error, retried next run)
            rec.update(status="error", note=str(ex)[:160])
        items[x] = rec
        if done and done % 25 == 0:
            print(f"  {done} done, ${spent:.2f}, {time.time() - t0:.0f} s")
            json.dump(st, open(STATE, "w", encoding="utf-8"), ensure_ascii=False)
    json.dump(st, open(STATE, "w", encoding="utf-8"), ensure_ascii=False)
    add = [r["row"] for k, r in items.items() if r.get("status") == "ok" and k not in have and os.path.exists(os.path.join(IMG_DIR, k + ".webp"))]
    if add:
        body = raw.rstrip()
        extra = json.dumps(add, ensure_ascii=False, separators=(",", ":"))[1:-1].replace("</", "<\\/")
        new_raw = body[:-1] + ("," if body[:-1].strip() != "[" else "") + extra + "]"
        json.loads(new_raw)
        open(path, "w", encoding="utf-8").write(html[:s] + new_raw + html[e:])
    from collections import Counter
    cnt = Counter(r.get("status") for r in items.values())
    left = sum(1 for x in ids if x not in have and (items.get(x) or {}).get("status") not in ("ok", "gone"))
    print(f"done: {done} processed this run, {len(add)} finds added to index.html; states {dict(cnt)}; left {left} "
          f"(${spent:.2f}, {time.time() - t0:.0f} s)")


if __name__ == "__main__":
    main()
