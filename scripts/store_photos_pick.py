# -*- coding: utf-8 -*-
"""Store photos for the partner's finds (owner, 20 Nov 2026). The owner's rules: data/store_photos_rules.md.

Runs in GitHub Actions (.github/workflows/store-photos.yml, ANTHROPIC_API_KEY + SUPABASE_SERVICE_KEY). Two steps:

--name  (step 1 of 3) one cheap vision call per find on its current photo + title: the exact model name, the details that
        identify that version (lining, hardware, pockets, logo placement) and search queries in English, Norwegian,
        German and French store wording -> data/store_photo_names.json. scripts/store_photos_collect.py (step 2, run
        where Brave Search works) searches with these names.
--pick  (step 3 of 3, default) per find in data/store_photo_candidates.json, most viewed first:
  1. download the candidates; drop broken, small (< 800 px) and soft ones (sharpness check, rule 4)
  2. one vision call: the candidates are shown grouped by store. It names the exact item, chooses ONE store (rule 5),
     says whether that store has a complete photoshoot of the exact item (use all of it, rule 13) or only some good
     photos (main + back + one model photo, rule 7), and labels every chosen photo: view and whether a person is in it
  3. product-only shots (person: false) are cut out (rembg): only background connected to the photo's border is removed,
     so gaps enclosed by the item keep their pixels (rule 1); a shot whose item touches the frame is dropped (rule 2).
     1200x1200 transparent canvas at 86%, WebP 88 -> Supabase products/store/<id>-<k>.webp. Photos with a person are
     never cut out (max 1600 px, WebP 85 -> products/store/<id>-m<k>.webp) and always come last (rule 3); the main is
     never one of them (rule 8). Every chosen photo must come from the chosen store.
  4. data/store_photos.json {"items": {id: {"main", "gallery", "model", "model_name", "store", "set", "src", ...}},
     "spent_usd": total}; out/store-photos/sheet.jpg (one row per find, each photo labelled with its store) and
     out/store-photos/review2-<n>.jpg (one image per find, its current site photo first).
The live site does not change: a later apply step can point the catalogue "img" at "main" and show the gallery.

  python scripts/store_photos_pick.py --name [--limit 20] [--ids ...] [--redo]
  python scripts/store_photos_pick.py [--limit 20] [--ids 1,2] [--max-usd 10] [--max-total-usd 150] [--redo] [--dry]
"""
import argparse, base64, io, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from catalog_common import COLOURS, ROOT, load_catalog, load_json  # noqa: E402

CAND = os.path.join(ROOT, "data", "store_photo_candidates.json")
NAMES = os.path.join(ROOT, "data", "store_photo_names.json")
LOG = os.path.join(ROOT, "data", "store_photos.json")
OUT = os.path.join(ROOT, "out", "store-photos")
SUPA = "https://uptpghuduqjqmrxwatbm.supabase.co"
PUB = SUPA + "/storage/v1/object/public/products/store/"
SITE = "https://www.puroclassico.com"
MODEL = os.environ.get("STORE_PHOTOS_MODEL", "claude-haiku-5-5")
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36"
MIN_SIDE = 800
SHARP_MIN = 28    # 99.5th percentile of |Laplacian| at 800 px: studio shots 50-130, a soft copy 10-18
THUMB = 360
spent = 0.0
_sess = None

NAME_PROMPT = """This is a photo of a fashion item listed as "{title}" (brand: {brand}, category: {cat}).
Identify the exact product so that store photos of this exact version can be found online.
Answer with JSON only:
{{"name": "the brand's exact product name, e.g. Burberry Bideford Hooded Puffer Jacket, Arc'teryx Beta AR Jacket,
Maison Margiela Replica Sneakers (if unsure, the most specific likely name)",
"details": "the visible details that identify this version: lining pattern and colour, hardware, pockets, logo type and
placement, sole, materials",
"colour": "the item's colour as stores name it",
"queries": {{"en": ["exact name + colour", "exact name + one identifying detail or the official colourway name"],
"no": "the same search the way a Norwegian store names it (e.g. dunjakke, genser, joggesko)",
"de": "the same in German store wording", "fr": "the same in French store wording"}}}}"""

PICK_PROMPT = """You choose official store photos for a fashion item in a shopping catalogue.
Item: "{title}" (brand: {brand}, category: {cat}). Exact model, if known: {name}. Identifying details: {details}.
Wanted colour: {colour}.
Image 0 is the item's current photo: it shows the exact DESIGN and VERSION (lining, hardware, pockets, logos, sole).
The candidates below are grouped by store; each store's photos are numbered.

Rules:
- EXACT VERSION only: every detail must match image 0 (a different lining colour, pocket layout or logo = another
  product). The wanted colour if any store has it, else the brand's best known colour of the same model.
- ONE STORE: choose the single store whose photos are the best consistent professional set of the exact item. Never mix
  stores. If one store has a COMPLETE consistent photoshoot of the exact item (front, back, side or close-ups of the item,
  model photos), set "set": "full" and use ALL of its good photos. Otherwise "set": "picked" and choose fewer, better:
  the main, the best product-only back if there is one, and ONE model photo matching the main's shoot. Never pad with
  weaker shots, never near-duplicates (several similar model poses: keep one).
- QUALITY: sharp, high-resolution, professional studio photos only. Brand/official studio photos are best, wherever they
  appear (resellers and marketplaces reuse them). Reject homemade photos (items on floors, beds, hangers, in rooms, in a
  hand, phone flash), collages, several products in one frame (a pair of shoes is fine), text/price overlays,
  watermarks, size charts, swatches, packaging, cropped photos where the item is cut off by the frame, and loose
  detail crops (a logo alone). Close-ups are fine only inside a full set from the same shoot.
- MAIN: the best product-only FRONT shot (no person, no hands). A 3/4 standing product shot (item shaped as if worn, on
  an invisible mannequin) beats a flat lay; for shoes a clean side profile is the front. The main is NEVER a photo with
  a person. For a set (tracksuit) the top alone may be the main.
- "person": true for any photo where a person (or part of one: legs, hands, face) is visible; product shots on grey or
  coloured studio backgrounds are person: false.
- Order "photos": main first, then the other product-only shots (back, side, close-ups, sole), then photos with a person
  (front first).

Answer with JSON only:
{{"model_name": "exact product name", "colour": "colourway of the chosen photos", "store": "the store letter or null",
"set": "full" | "picked" | "none", "photos": [{{"i": number, "view": "front|three_quarter|back|side|closeup|sole|top",
"person": true/false}}], "colour_match": true/false, "confidence": 0.0-1.0 (that the photos show the exact version),
"note": "a few words: why this store, what was rejected"}}"""


def now(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def host_of(u):
    h = urllib.parse.urlsplit(u).netloc.lower()
    return h[4:] if h.startswith("www.") else h


def fetch(url, timeout=25):
    h = {"User-Agent": UA, "Accept": "image/avif,image/webp,image/apng,image/*,*/*", "Referer": "https://" + urllib.parse.urlsplit(url).netloc + "/"}
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
    im = im.convert("RGBA"); bg = Image.new("RGBA", im.size, (255, 255, 255, 255)); bg.alpha_composite(im)
    im = bg.convert("RGB"); im.thumbnail((side, side)); b = io.BytesIO(); im.save(b, "JPEG", quality=82)
    return base64.b64encode(b.getvalue()).decode()


def sharpness(im):
    g = im.convert("L"); g.thumbnail((800, 800)); a = np.asarray(g, dtype=np.float32)
    lap = np.abs(a[1:-1, 1:-1] * 4 - a[:-2, 1:-1] - a[2:, 1:-1] - a[1:-1, :-2] - a[1:-1, 2:])
    return float(np.percentile(lap, 99.5))


def claude(content, max_tokens=4000):
    global spent
    body = json.dumps({"model": MODEL, "max_tokens": max_tokens, "messages": [{"role": "user", "content": content}]}).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, headers={
        "x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01", "content-type": "application/json"})
    for k in range(4):
        try:
            with urllib.request.urlopen(req, timeout=180) as r: d = json.load(r); break
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
    """(transparent 1200x1200 canvas, None) or (None, reason). Rule 1: only background connected to the border goes;
    rule 2: an item that touches the frame is a cropped photo."""
    global _sess
    from rembg import remove, new_session
    from scipy import ndimage
    if _sess is None: _sess = new_session("isnet-general-use")
    src = im.convert("RGB")
    if max(src.size) > 2000: src.thumbnail((2000, 2000), Image.LANCZOS)
    out = np.array(remove(src, session=_sess).convert("RGBA"))
    alpha = out[:, :, 3]
    clear = alpha < 128
    lab, _ = ndimage.label(clear)
    edge = np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))
    holes = clear & ~np.isin(lab, edge[edge > 0])
    if holes.any():  # enclosed gaps keep the original photo
        out[holes, :3] = np.asarray(src)[holes]
        out[holes, 3] = 255
        alpha = out[:, :, 3]
    solid = alpha >= 24
    cover = solid.mean()
    if not 0.03 <= cover <= 0.95: return None, "cut-out failed"
    m = 2
    if solid[:m].any() or solid[-m:].any() or solid[:, :m].any() or solid[:, -m:].any(): return None, "item touches the frame"
    ys, xs = np.where(solid)
    item = Image.fromarray(out).crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))
    s = 1200 * 0.86 / max(item.size)
    item = item.resize((max(1, round(item.width * s)), max(1, round(item.height * s))), Image.LANCZOS)
    canvas = Image.new("RGBA", (1200, 1200), (0, 0, 0, 0))
    canvas.alpha_composite(item, ((1200 - item.width) // 2, (1200 - item.height) // 2))
    return canvas, None


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
    t = " " + (title or "").lower() + " "
    hit = [c for c in sorted(COLOURS, key=len, reverse=True) if " " + c + " " in t]
    return " / ".join(hit[:2]) if hit else "the colour in image 0 (else the brand's best known colour)"


def load_cands(entry):
    """[(index in c, PIL image)] for candidates that download, are large enough and sharp."""
    c = entry["c"]

    def one(k):
        try:
            im = open_img(fetch(c[k][0]))
            if max(im.size) < MIN_SIDE or min(im.size) < 400: return None
            if sharpness(im) < SHARP_MIN: return None
            return k, im
        except Exception:
            return None
    with ThreadPoolExecutor(8) as ex:
        return [r for r in ex.map(one, range(len(c))) if r]


def process(p, entry, nm, a):
    c = entry["c"]
    got = load_cands(entry)
    before = current_photo(p)
    if not got: return {"error": "no usable candidates", "at": now(), "set": "none"}, [], before
    # groups as the collector made them: a page with its own gallery is one photoshoot, loose hits group by store
    gal_pages = {x[1] for x in c if x[4] == "s"}
    stores = {}
    for k, im in got:
        pg = entry["p"][c[k][1]]
        key = host_of(pg) + urllib.parse.urlsplit(pg).path if c[k][1] in gal_pages else host_of(pg)
        stores.setdefault(key, []).append((k, im))
    nm = nm or {}
    content = [{"type": "text", "text": PICK_PROMPT.format(title=p.get("title"), brand=p.get("brand"), cat=p.get("cat"),
                                                           name=nm.get("name") or entry.get("name") or "unknown",
                                                           details=nm.get("details") or "see image 0",
                                                           colour=nm.get("colour") or colour_of(p.get("title")))},
               {"type": "text", "text": "[0] current photo"},
               {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": jpg64(before)}}]
    num, letters = {}, {}
    n = 0
    for si, (host, ims) in enumerate(stores.items()):
        L = chr(65 + si); letters[L] = host
        content.append({"type": "text", "text": f"Store {L}: {host}" + (" (one product page)" if "/" in host else " (separate image hits)")})
        for k, im in ims:
            n += 1; num[n] = (k, im, host)
            content.append({"type": "text", "text": f"[{n}] store {L}, {im.width}x{im.height}"})
            content.append({"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": jpg64(im)}})
    ans, cost = claude(content)
    store = letters.get(str(ans.get("store") or "").strip().upper()[:1])
    rec = {"model_name": ans.get("model_name"), "colour": ans.get("colour"), "colour_match": bool(ans.get("colour_match")),
           "conf": ans.get("confidence"), "note": ans.get("note"), "set": ans.get("set") or "none", "store": store,
           "cost": round(cost, 5), "at": now(), "main": None, "gallery": [], "model": [], "src": [], "dropped": []}
    chosen, seen = [], set()
    for ph in ans.get("photos") or []:
        try: i = int(ph.get("i"))
        except Exception: continue
        if i not in num or i in seen: continue
        seen.add(i)
        k, im, host = num[i]
        if store and host != store: rec["dropped"].append(f"{i}: other store"); continue  # rule 5
        chosen.append((i, k, im, host, str(ph.get("view") or ""), bool(ph.get("person"))))
    if not store and chosen: store = rec["store"] = chosen[0][3]; chosen = [x for x in chosen if x[3] == store]
    prod = [x for x in chosen if not x[5]]
    pers = [x for x in chosen if x[5]]
    if rec["set"] != "full":  # rule 7: main + best back (+ an equally good side) + one model photo
        backs = [x for x in prod[1:] if x[4] == "back"][:1]
        prod = prod[:1] + backs + [x for x in prod[1:] if x[4] in ("side", "three_quarter") and x not in backs][:1]
        pers = pers[:1]
    else:
        prod, pers = prod[:8], pers[:3]
    shown = []  # (kind, image, host) for the sheets
    pid = p["id"]; k_out = 0
    for i, k, im, host, view, _ in prod:
        cut, why = cutout(im)
        if cut is None: rec["dropped"].append(f"{i} {view}: {why}"); continue
        name = f"{pid}-{k_out}.webp"; k_out += 1
        url = name if a.dry else upload(name, webp(cut, 88))
        if rec["main"] is None: rec["main"] = url; kind = "main"
        else: rec["gallery"].append(url); kind = view or "product"
        rec["src"].append(entry["p"][c[k][1]]); shown.append((kind, cut, host.split("/")[0]))
    for m, (i, k, im, host, view, _) in enumerate(pers):
        im = im.copy(); im.thumbnail((1600, 1600), Image.LANCZOS)
        name = f"{pid}-m{m}.webp"
        rec["model"].append(name if a.dry else upload(name, webp(im, 85)))
        rec["src"].append(entry["p"][c[k][1]]); shown.append(("model", im, host.split("/")[0]))
    rec["src"] = list(dict.fromkeys(rec["src"]))
    if not rec["main"]: rec["set"] = "none" if not rec["model"] else "model only"
    elif rec["set"] == "full" and not rec["gallery"]: rec["set"] = "picked"
    return rec, shown, before


def font(sz):
    try: return ImageFont.truetype(os.path.join(ROOT, "scripts", "fonts", "HankenGrotesk.ttf"), sz)
    except Exception: return ImageFont.load_default()


def tile(im, T, bg=(255, 255, 255)):
    im = im.convert("RGBA"); b = Image.new("RGBA", im.size, bg + (255,)); b.alpha_composite(im); b = b.convert("RGB")
    b.thumbnail((T, T)); t = Image.new("RGB", (T, T), bg); t.paste(b, ((T - b.width) // 2, (T - b.height) // 2)); return t


COL = {"main": (40, 150, 80), "model": (90, 110, 210)}


def row_text(p, rec):
    a = f"{p['id']}  {p.get('title')}  ->  {rec.get('model_name') or '?'} ({rec.get('colour') or '?'})"
    b = (f"set: {rec.get('set')}   store: {rec.get('store') or '-'}   conf {rec.get('conf')}   colour match "
         f"{rec.get('colour_match')}   {rec.get('error') or rec.get('note') or ''}")
    return a, b


def sheet(rows, path):
    """One row per find: current photo | main | other product shots | model photos, each labelled with its store."""
    T, t, pad, lab = 240, 180, 10, 46
    w = pad + T + 24 + T + 8 + 9 * (t + 6) + pad
    h = pad + 30 + len(rows) * (T + lab + pad)
    sh = Image.new("RGB", (w, h), (255, 255, 255)); d = ImageDraw.Draw(sh)
    f1, f2, f3 = font(16), font(13), font(11)
    d.text((pad, pad), "current site photo  |  main (green)  |  product angles  |  model photos (blue); store under each photo",
           fill=(30, 30, 30), font=f1)
    y = pad + 30
    for p, rec, before, shown in rows:
        if before is not None: sh.paste(tile(before, T, (236, 236, 236)), (pad, y))
        d.text((pad + 2, y + T - 14), "current", fill=(90, 90, 90), font=f3)
        x = pad + T + 24
        if not shown: d.rectangle((x, y, x + T, y + T), fill=(255, 236, 236))
        for n, (kind, im, host) in enumerate(shown[:10]):
            s = T if kind == "main" else t
            sh.paste(tile(im, s), (x, y))
            d.rectangle((x, y, x + s, y + s), outline=COL.get(kind, (200, 200, 210)), width=2 if kind in COL else 1)
            d.text((x + 3, y + s + 2), f"{kind}: {host}"[:34], fill=(70, 70, 70), font=f3)
            x += s + 8
        a, b = row_text(p, rec)
        d.text((pad, y + T + 16), a[:200], fill=(20, 20, 20), font=f2)
        d.text((pad, y + T + 32), b[:220], fill=(150, 30, 30) if not rec.get("main") else (90, 90, 90), font=f2)
        y += T + lab + pad
    os.makedirs(os.path.dirname(path), exist_ok=True)
    sh.save(path, quality=88)


def review(n, p, rec, before, shown, path):
    """One image per find for the owner: the current site photo first, then every chosen photo with its store."""
    T, pad = 420, 14
    tiles = [("current site photo", before, "")] + [(k, im, h) for k, im, h in shown]
    cols = min(4, len(tiles)); rws = (len(tiles) + cols - 1) // cols
    sh = Image.new("RGB", (pad + cols * (T + pad), 70 + rws * (T + 40)), (255, 255, 255)); d = ImageDraw.Draw(sh)
    a, b = row_text(p, rec)
    d.text((pad, 10), f"{n}. {a}"[:150], fill=(20, 20, 20), font=font(18))
    d.text((pad, 36), b[:190], fill=(90, 90, 90), font=font(13))
    for j, (kind, im, host) in enumerate(tiles):
        x, y = pad + (j % cols) * (T + pad), 70 + (j // cols) * (T + 40)
        if im is not None: sh.paste(tile(im, T, (236, 236, 236) if j == 0 else (255, 255, 255)), (x, y))
        d.rectangle((x, y, x + T, y + T), outline=COL.get(kind, (200, 200, 210)), width=2)
        d.text((x + 2, y + T + 6), f"{kind}" + (f"  ({host})" if host else ""), fill=(60, 60, 60), font=font(14))
    sh.save(path, quality=88)


def save_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1, sort_keys=True); f.write("\n")
    os.replace(tmp, path)


def partner_order(by):
    swaps = (load_json(os.path.join(ROOT, "data", "link_swaps.json"), {}) or {}).get("swaps") or {}
    stats = (load_json(os.path.join(ROOT, "data", "stats.json"), {}) or {}).get("p") or {}
    return sorted([i for i in swaps if i in by], key=lambda i: (-(stats.get(i) or [0])[0], i))


def run_name(a, by):
    names = load_json(NAMES, {"items": {}})
    ids = [i for i in a.ids.split(",") if i] if a.ids else partner_order(by)
    todo = [i for i in ids if i in by and (a.redo or i not in names["items"])][:a.limit or None]
    print(f"{len(todo)} finds to name", flush=True)
    for n, i in enumerate(todo, 1):
        if spent >= a.max_usd: print(f"run budget reached ({spent:.3f} USD), limit reached"); break
        p = by[i]
        try:
            before = current_photo(p)
            ans, cost = claude([{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": jpg64(before, 512)}},
                                {"type": "text", "text": NAME_PROMPT.format(title=p.get("title"), brand=p.get("brand"), cat=p.get("cat"))}], 2500)
        except Exception as e:
            print(f"  {i} failed: {e!r}", flush=True); continue
        if not ans.get("name"): print(f"  {i}: {ans.get('note')}", flush=True); continue
        ans["at"] = now(); names["items"][i] = ans
        print(f"[{n}/{len(todo)}] {i} {p.get('title')} -> {ans.get('name')} | {json.dumps(ans.get('queries'), ensure_ascii=False)[:160]} ${cost:.4f}", flush=True)
    names["spent_usd"] = round(names.get("spent_usd", 0) + spent, 4)
    save_json(NAMES, names)
    print(f"summary: named {len(todo)} finds, {spent:.4f} USD ({spent / max(1, len(todo)):.4f} per find)")


def main():
    global spent
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", action="store_true", help="step 1: name the exact models")
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--ids", default="")
    ap.add_argument("--max-usd", type=float, default=10.0)
    ap.add_argument("--max-total-usd", type=float, default=float(os.environ.get("STORE_PHOTOS_TOTAL_USD", "150")))
    ap.add_argument("--redo", action="store_true")
    ap.add_argument("--dry", action="store_true", help="no uploads (names only)")
    a = ap.parse_args()
    by = {p["id"]: p for p in load_catalog()[1]}
    if a.name: return run_name(a, by)
    cands = load_json(CAND, {"items": {}})["items"]
    names = load_json(NAMES, {"items": {}})["items"]
    log = load_json(LOG, {"items": {}, "spent_usd": 0.0})
    order = [i for i in a.ids.split(",") if i] if a.ids else [i for i in partner_order(by) if i in cands]
    todo = [i for i in order if i in cands and i in by and (a.redo or i not in log["items"])][:a.limit or None]
    print(f"{len(todo)} finds to do; spent so far {log.get('spent_usd', 0):.2f} USD (cap {a.max_total_usd})", flush=True)
    rows = []
    os.makedirs(OUT, exist_ok=True)
    for n, i in enumerate(todo, 1):
        if spent >= a.max_usd: print(f"run budget reached ({spent:.3f} USD), limit reached"); break
        if log.get("spent_usd", 0) + spent >= a.max_total_usd: print("global budget reached, limit reached"); break
        p = by[i]
        try:
            rec, shown, before = process(p, cands[i], names.get(i), a)
        except Exception as e:
            print(f"  {i} failed: {e!r}", flush=True)
            rec, shown, before = {"error": repr(e)[:200], "at": now(), "set": "none"}, [], None
        log["items"][i] = rec
        rows.append((p, rec, before, shown))
        if before is not None: review(n, p, rec, before, shown, os.path.join(OUT, f"review2-{n}.jpg"))
        print(f"[{n}/{len(todo)}] {i} {p.get('title')} -> {rec.get('model_name')} set={rec.get('set')} store={rec.get('store')} "
              f"main={'yes' if rec.get('main') else 'NO'} gallery={len(rec.get('gallery') or [])} model={len(rec.get('model') or [])} "
              f"conf={rec.get('conf')} ${rec.get('cost', 0):.4f} total ${spent:.3f} | {rec.get('error') or rec.get('note') or ''} "
              f"{'; '.join(rec.get('dropped') or [])}", flush=True)
    log["spent_usd"] = round(log.get("spent_usd", 0) + spent, 4)
    if not a.dry: save_json(LOG, log)
    if rows:
        sheet(rows, os.path.join(OUT, "sheet.jpg"))
        print("contact sheet:", os.path.join(OUT, "sheet.jpg"))
    done = [r for _, r, _, _ in rows]
    sets = {}
    for r in done: sets[r.get("set")] = sets.get(r.get("set"), 0) + 1
    print(f"summary: {len(done)} finds, sets {sets}, {spent:.4f} USD this run ({spent / max(1, len(done)):.4f} per find)")


if __name__ == "__main__":
    main()
