# -*- coding: utf-8 -*-
"""Store photos for the partner's finds, step 2 of 2 (step 1: scripts/store_photos_collect.py, owner 20 Nov 2026).

Runs in GitHub Actions (.github/workflows/store-photos.yml: ANTHROPIC_API_KEY, SUPABASE_SERVICE_KEY). Per find in
data/store_photo_candidates.json, most viewed first:
  1. download the candidates (drop broken ones and any under 800 px on the longest side) and the find's current photo
  2. one vision call (claude-haiku-5-5): the current photo shows the design; the candidates are numbered. It names the
     exact model and picks: main = the best clean product-only FRONT shot of the same design (the find's colour
     preferred, else the brand's iconic colour), gallery = other product-only angles (back, side, detail, sole), model =
     on-model shots of the same design (front, back, side). Collages, text overlays, size charts, hands, secondhand
     listings, other designs and low resolution are rejected.
  3. main + gallery: rembg cut-out (isnet-general-use) on a transparent 1200x1200 canvas at 86%, WebP 88, uploaded to
     Supabase products/store/<id>-<k>.webp. On-model shots stay full photos (max 1600 px, WebP 85) as
     products/store/<id>-m<k>.webp. Nothing goes in the repo (Cloudflare Pages file limit).
  4. data/store_photos.json {"items": {id: {"main", "gallery", "model", "model_name", "src", "conf", "colour_match"}},
     "spent_usd": total}; out/store-photos/sheet.jpg (before = current photo, after = main, gallery, on-model).
The live site does not change: a later apply step can point the catalogue "img" at "main" and show the gallery.

  python scripts/store_photos_pick.py [--limit 20] [--ids 1,2] [--max-usd 10] [--max-total-usd 150] [--redo] [--dry]
"""
import argparse, base64, io, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from catalog_common import ROOT, load_catalog, load_json  # noqa: E402

CAND = os.path.join(ROOT, "data", "store_photo_candidates.json")
LOG = os.path.join(ROOT, "data", "store_photos.json")
OUT = os.path.join(ROOT, "out", "store-photos")
SUPA = "https://uptpghuduqjqmrxwatbm.supabase.co"
PUB = SUPA + "/storage/v1/object/public/products/store/"
SITE = "https://www.puroclassico.com"
MODEL = os.environ.get("STORE_PHOTOS_MODEL", "claude-haiku-5-5")
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36"
MIN_SIDE = 800
THUMB = 384
spent = 0.0
_sess = None

PROMPT = """You pick official store product photos for a clothing item in a shopping catalogue.
Find: "{title}" (brand: {brand}, category: {cat}). Wanted colour: {colour}.
Image 0 is the item's current photo: it shows the DESIGN (shape, logo placement, pattern, details).
Images 1..{n} are candidate photos from online stores (host and size in brackets before each).

Choose, using only candidates that show the SAME DESIGN as image 0 (same model; a different colourway of the same model is
fine only when no candidate has the wanted colour, and then prefer the brand's best known colour; all chosen photos must
be ONE colourway):
- main: the single best clean PRODUCT-ONLY FRONT shot (no person, no hands, no mannequin, plain or studio background,
  whole item visible, sharp). For shoes the side profile of one shoe is the front shot. null if none qualifies.
- gallery: other PRODUCT-ONLY shots of that same item and colourway (back, side, detail close-ups, sole, inside), ordered
  front/back/side/detail/sole, no near duplicates of main or of each other, at most 6.
- model: ON-MODEL photos of that same item and colourway (a person wearing it, studio or clean editorial), ordered
  front/back/side, at most 3.
Reject everywhere: collages or several items in one frame (a pair of shoes is fine), text or price overlays, watermarks,
size charts, swatches, packaging only, blurry or tiny images, secondhand listing photos (items on floors, beds, hangers,
in a hand), lifestyle shots where the item is small, and any other design.

Answer with JSON only:
{{"model_name": "exact product name, e.g. Arc'teryx Beta AR Jacket", "colour": "colourway of the chosen photos",
"main": index or null, "gallery": [indexes], "model": [indexes], "colour_match": true/false (chosen colour = wanted
colour), "confidence": 0.0-1.0 (that main is the same design), "note": "a few words"}}"""


def now(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def fetch(url, timeout=25):
    h = {"User-Agent": UA, "Accept": "image/avif,image/webp,image/apng,image/*,*/*"}
    host = urllib.parse.urlsplit(url).netloc
    h["Referer"] = "https://" + host + "/"
    with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=timeout) as r:
        return r.read()


def open_img(data):
    im = Image.open(io.BytesIO(data)); im.load()
    if im.mode in ("P", "LA", "RGBA") or "transparency" in im.info:
        im = im.convert("RGBA"); bg = Image.new("RGBA", im.size, (255, 255, 255, 255)); bg.alpha_composite(im); im = bg
    return im.convert("RGB")


def current_photo(p):
    u = p.get("img") or ""
    if u.startswith("/"):
        path = os.path.join(ROOT, u.split("?")[0].lstrip("/"))
        if os.path.exists(path): return Image.open(path).convert("RGBA")
        u = SITE + u
    return Image.open(io.BytesIO(fetch(u))).convert("RGBA")


def jpg64(im, side=THUMB):
    im = im.copy(); im.thumbnail((side, side)); b = io.BytesIO(); im.convert("RGB").save(b, "JPEG", quality=82)
    return base64.b64encode(b.getvalue()).decode()


def claude(content, max_tokens=4000):
    global spent
    body = json.dumps({"model": MODEL, "max_tokens": max_tokens, "messages": [{"role": "user", "content": content}]}).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, headers={
        "x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01", "content-type": "application/json"})
    for k in range(4):
        try:
            with urllib.request.urlopen(req, timeout=120) as r: d = json.load(r); break
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503, 529) or k == 3: raise
            time.sleep(10 * (k + 1))
    u = d.get("usage") or {}
    cost = (u.get("input_tokens", 0) * 1.0 + u.get("output_tokens", 0) * 5.0) / 1e6
    spent += cost
    txt = "".join(c.get("text", "") for c in d.get("content", []))
    m = re.search(r"\{.*\}", txt, re.S)
    try:
        ans = json.loads(m.group(0)) if m else {}
    except ValueError:
        ans = {}
    if not ans: ans = {"note": f"no answer ({d.get('stop_reason')}): {txt[:160]}"}
    return ans, cost


def cutout(im):
    """Transparent cut-out on a 1200x1200 canvas, item at 86%; None when the mask looks wrong."""
    global _sess
    from rembg import remove, new_session
    if _sess is None: _sess = new_session("isnet-general-use")
    src = im.convert("RGB")
    if max(src.size) > 2000: src.thumbnail((2000, 2000), Image.LANCZOS)
    out = remove(src, session=_sess).convert("RGBA")
    a = out.getchannel("A"); h = a.histogram(); cover = sum(h[128:]) / max(1, sum(h))
    if not 0.03 <= cover <= 0.95: return None
    box = a.point(lambda v: 255 if v >= 24 else 0).getbbox()
    if not box: return None
    item = out.crop(box)
    s = 1200 * 0.86 / max(item.size)
    item = item.resize((max(1, round(item.width * s)), max(1, round(item.height * s))), Image.LANCZOS)
    canvas = Image.new("RGBA", (1200, 1200), (0, 0, 0, 0))
    canvas.alpha_composite(item, ((1200 - item.width) // 2, (1200 - item.height) // 2))
    return canvas


def webp(im, q):
    b = io.BytesIO(); im.save(b, "WEBP", quality=q, method=5); return b.getvalue()


def upload(name, data):
    key = os.environ["SUPABASE_SERVICE_KEY"]
    req = urllib.request.Request(SUPA + "/storage/v1/object/products/store/" + name, data=data, method="POST", headers={
        "User-Agent": UA, "Authorization": "Bearer " + key, "apikey": key, "Content-Type": "image/webp",
        "x-upsert": "true", "Cache-Control": "max-age=31536000"})
    urllib.request.urlopen(req, timeout=60).read()
    return PUB + name


def colour_of(title):
    from catalog_common import COLOURS
    t = " " + (title or "").lower() + " "
    hit = [c for c in sorted(COLOURS, key=len, reverse=True) if " " + c + " " in t]
    return " / ".join(hit[:2]) if hit else "the find's colour in image 0 (else the brand's best known colour)"


def load_cands(c):
    """[(index in c, PIL image, (w, h))] for candidates that download and are large enough."""
    def one(k):
        try:
            im = open_img(fetch(c[k][0]))
            if max(im.size) < MIN_SIDE or min(im.size) < 400: return None
            return k, im
        except Exception:
            return None
    with ThreadPoolExecutor(8) as ex:
        return [r for r in ex.map(one, range(len(c))) if r]


def process(p, entry, a):
    c = entry["c"]
    got = load_cands(c)
    if not got: return {"error": "no usable candidates", "at": now()}, [], None
    before = current_photo(p)
    content = [{"type": "text", "text": PROMPT.format(title=p.get("title"), brand=p.get("brand"), cat=p.get("cat"),
                                                      colour=colour_of(p.get("title")), n=len(got))},
               {"type": "text", "text": "[0] current photo"},
               {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": jpg64(before)}}]
    for n, (k, im) in enumerate(got, 1):
        host = urllib.parse.urlsplit(entry["p"][c[k][1]]).netloc.replace("www.", "")
        content.append({"type": "text", "text": f"[{n}] {host} {im.width}x{im.height}"})
        content.append({"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": jpg64(im)}})
    ans, cost = claude(content)

    def pick(v):
        try: v = int(v)
        except Exception: return None
        return got[v - 1] if 1 <= v <= len(got) else None
    main = pick(ans.get("main"))
    gal = [g for g in (pick(v) for v in (ans.get("gallery") or [])[:6]) if g and (not main or g[0] != main[0])]
    mod = [g for g in (pick(v) for v in (ans.get("model") or [])[:3]) if g]
    rec = {"model_name": ans.get("model_name"), "colour": ans.get("colour"), "colour_match": bool(ans.get("colour_match")),
           "conf": ans.get("confidence"), "note": ans.get("note"), "cost": round(cost, 5), "at": now(),
           "main": None, "gallery": [], "model": [], "src": []}
    shown = []  # (kind, image) for the contact sheet
    pid = p["id"]; k_out = 0
    for kind, (k, im) in ([("main", main)] if main else []) + [("gallery", g) for g in gal]:
        cut = cutout(im)
        if cut is None:
            if kind == "main": rec["note"] = (rec.get("note") or "") + "; main cut-out failed"
            continue
        name = f"{pid}-{k_out}.webp"; k_out += 1
        url = name if a.dry else upload(name, webp(cut, 88))
        if kind == "main" and rec["main"] is None: rec["main"] = url
        else: rec["gallery"].append(url)
        rec["src"].append(entry["p"][c[k][1]]); shown.append((kind, cut))
    if rec["main"] is None and rec["gallery"]:  # main cut-out failed: the first product-only shot moves up
        rec["main"] = rec["gallery"].pop(0); shown[0] = ("main", shown[0][1])
    for m, (k, im) in enumerate(mod):
        im = im.copy(); im.thumbnail((1600, 1600), Image.LANCZOS)
        name = f"{pid}-m{m}.webp"
        rec["model"].append(name if a.dry else upload(name, webp(im, 85)))
        rec["src"].append(entry["p"][c[k][1]]); shown.append(("model", im))
    rec["src"] = list(dict.fromkeys(rec["src"]))
    return rec, shown, before


def font(sz):
    try: return ImageFont.truetype(os.path.join(ROOT, "scripts", "fonts", "HankenGrotesk.ttf"), sz)
    except Exception: return ImageFont.load_default()


def tile(im, T, bg=(255, 255, 255)):
    im = im.convert("RGBA"); b = Image.new("RGBA", im.size, bg + (255,)); b.alpha_composite(im); b = b.convert("RGB")
    b.thumbnail((T, T)); t = Image.new("RGB", (T, T), bg); t.paste(b, ((T - b.width) // 2, (T - b.height) // 2)); return t


def sheet(rows, path):
    """rows: (find, rec, before, shown). One row per find: before | main | gallery | on-model."""
    T, t, pad, lab = 240, 170, 10, 46
    w = pad + T + 24 + T + 8 + 9 * (t + 6) + pad
    h = pad + len(rows) * (T + lab + pad) + 40
    sh = Image.new("RGB", (w, h), (255, 255, 255)); d = ImageDraw.Draw(sh)
    f1, f2 = font(16), font(13)
    d.text((pad, pad), "before (site photo)  |  after: main (front), gallery (product-only), on-model", fill=(30, 30, 30), font=f1)
    y = pad + 30
    for p, rec, before, shown in rows:
        if before is not None: sh.paste(tile(before, T, (236, 236, 236)), (pad, y))
        x = pad + T + 24
        if not shown:
            d.rectangle((x, y, x + T, y + T), fill=(255, 236, 236))
        for n, (kind, im) in enumerate(shown[:10]):
            s = T if n == 0 and kind == "main" else t
            sh.paste(tile(im, s, (255, 255, 255) if kind != "model" else (250, 250, 250)), (x, y))
            d.rectangle((x, y, x + s, y + s), outline=(60, 160, 90) if kind == "main" else (205, 205, 215) if kind == "gallery" else (120, 140, 220))
            x += s + (8 if n == 0 else 6)
        info = f"{p['id']}  {p.get('title')}  ->  {rec.get('model_name') or '?'} ({rec.get('colour') or '?'})"
        info2 = (f"conf {rec.get('conf')}  colour match {rec.get('colour_match')}  gallery {len(rec.get('gallery') or [])}  "
                 f"on-model {len(rec.get('model') or [])}  {rec.get('error') or rec.get('note') or ''}")
        d.text((pad, y + T + 4), info[:190], fill=(20, 20, 20), font=f2)
        d.text((pad, y + T + 22), info2[:190], fill=(150, 30, 30) if not rec.get("main") else (90, 90, 90), font=f2)
        y += T + lab + pad
    os.makedirs(os.path.dirname(path), exist_ok=True)
    sh.save(path, quality=88)


def save_log(log):
    tmp = LOG + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=1, sort_keys=True); f.write("\n")
    os.replace(tmp, LOG)


def main():
    global spent
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--ids", default="")
    ap.add_argument("--max-usd", type=float, default=10.0)
    ap.add_argument("--max-total-usd", type=float, default=float(os.environ.get("STORE_PHOTOS_TOTAL_USD", "150")))
    ap.add_argument("--redo", action="store_true")
    ap.add_argument("--dry", action="store_true", help="no uploads (names only)")
    a = ap.parse_args()
    cands = load_json(CAND, {"items": {}})["items"]
    by = {p["id"]: p for p in load_catalog()[1]}
    stats = (load_json(os.path.join(ROOT, "data", "stats.json"), {}) or {}).get("p") or {}
    log = load_json(LOG, {"items": {}, "spent_usd": 0.0})
    order = [i for i in a.ids.split(",") if i] if a.ids else sorted(cands, key=lambda i: (-(stats.get(i) or [0])[0], i))
    todo = [i for i in order if i in cands and i in by and (a.redo or i not in log["items"])][:a.limit or None]
    print(f"{len(todo)} finds to do; spent so far {log.get('spent_usd', 0):.2f} USD (cap {a.max_total_usd})", flush=True)
    rows = []
    for n, i in enumerate(todo, 1):
        if spent >= a.max_usd: print(f"run budget reached ({spent:.3f} USD), limit reached"); break
        if log.get("spent_usd", 0) + spent >= a.max_total_usd: print("global budget reached, limit reached"); break
        p = by[i]
        try:
            rec, shown, before = process(p, cands[i], a)
        except Exception as e:
            print(f"  {i} failed: {e!r}", flush=True)
            rec, shown, before = {"error": repr(e)[:200], "at": now()}, [], None
        log["items"][i] = rec
        rows.append((p, rec, before, shown))
        print(f"[{n}/{len(todo)}] {i} {p.get('title')} -> {rec.get('model_name')} main={'yes' if rec.get('main') else 'NO'} "
              f"gallery={len(rec.get('gallery') or [])} model={len(rec.get('model') or [])} conf={rec.get('conf')} "
              f"${rec.get('cost', 0):.4f} total ${spent:.3f} {rec.get('error') or rec.get('note') or ''}", flush=True)
    log["spent_usd"] = round(log.get("spent_usd", 0) + spent, 4)
    if not a.dry: save_log(log)
    if rows:
        sheet(rows, os.path.join(OUT, "sheet.jpg"))
        print("contact sheet:", os.path.join(OUT, "sheet.jpg"))
    done = [r for _, r, _, _ in rows]
    good = sum(1 for r in done if r.get("main"))
    print(f"summary: {len(done)} finds, {good} with a main photo, {spent:.4f} USD this run "
          f"({spent / max(1, len(done)):.4f} per find)")


if __name__ == "__main__":
    main()
