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
  python scripts/store_photos_pick.py [--limit 20] [--ids 1,2] [--max-usd 8] [--max-total-usd 60] [--redo] [--dry]
"""
import argparse, base64, io, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from catalog_common import COLOURS, ROOT, load_catalog, load_json  # noqa: E402
import store_photos_shards as shards  # noqa: E402

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
- DESIGN ON THE BACK: when the item's main graphic/logo is on the back (image 0 shows the back, or the front is plain),
  the BACK product shot is the main and the plain front follows it.
- BACK: always include a product-only BACK shot when the chosen store has one (the owner asks for it every time); a back
  view on a model is the fallback.
- NO CAMPAIGN SHOTS: skip ad/lifestyle photos (a person posing on a sofa, a scene, editorial styling where the item is
  small). Model photos are plain studio or catalogue shots of the item being worn or held (owner, Goyard wallet).
- SEVERAL COLOURS: when image 0 shows the item in several colours (the listing sells them all), choose ONE colour, the
  most popular one (usually black, else the brand's best-known colour), and take every photo, main and model shots,
  in that same colour (owner, Acne Stockholm 1996 long sleeve).
- MODEL PHOTOS show the whole item on the person (the full jacket, top or trousers, shoes on feet): skip tight model crops
  where the item is cut off or only a chest/collar area shows (owner: Ralph Lauren glossy puffer, the chest crop).
- CLOSE-UPS: keep close-ups of a real part (handle, name tag, clasp/strap clip, zip, inside, collar, sole); skip pure
  pattern/texture shots and wear or damage details (pre-owned listings have many).
- NO LABELS: never pick shots of size tags, care labels, neck-print/inside-print scans or the inside print alone (owner,
  Chrome Hearts hoodie).
- NO LOGO CLOSE-UPS: never pick a close-up of only a print/logo/text (it reads as a bad shot); close-ups must show a
  recognisable part of the item (a collar, a zip, a buckle).
- MAIN = the item's FRONT as it is worn or first seen: a watch's dial facing the camera (never the caseback), a jacket's
  or hoodie's front, a shoe's outer side. Casebacks, soles and insides are fine as EXTRA photos after the main.
- EXACT VERSION only: every detail must match image 0 (a different lining colour, pocket layout or logo = another
  product). The wanted colour if any store has it, else the brand's best known colour of the same model.
- VERY SIMILAR IS FINE (owner, 21 Nov 2026, rule 36): MUCH better photos of a very similar item (same brand, same kind
  of item, same main colour, near-identical look and silhouette) beat bad photos of the exact one. Use them and set
  "similar": true (confidence stays about the exact version). Never another colour (black vs navy, grey vs beige),
  another pattern or print, a big logo where image 0 has none, or a clearly different shape or garment type (owner:
  Gucci GG knit zip cardigan, Stussy puffer).
- SECOND STORE (owner, 20 Nov 2026: "id like way more photos"): when the chosen store has FEWER THAN 4 good photos, also
  name a second store ("store2") with more photos of the SAME exact item in a matching style (similar background and
  lighting) and add its good photos after the first store's. Never a second store for the main.
- ONE STORE: choose the single store whose photos are the best consistent professional set of the exact item. Never mix
  stores. If one store has a COMPLETE consistent photoshoot of the exact item (front, back, side or close-ups of the item,
  model photos), set "set": "full" and use ALL of its good photos. Otherwise "set": "picked": still choose EVERY good
  photo of that one store (the owner prefers more photos when they are good), one per angle. Never pad with weaker
  shots, never near-duplicates (the same angle twice, several similar model poses: keep the best one).
- QUALITY: sharp, high-resolution, professional studio photos only. Brand/official studio photos are best, wherever they
  appear (resellers and marketplaces reuse them). Reject homemade photos (items on floors, beds, hangers, in rooms, in a
  hand, phone flash), collages, several products in one frame (a pair of shoes is fine), packaging/boxes/bags/tags or props next to the item, text/price overlays,
  watermarks, size charts, swatches, packaging, cropped photos where the item is cut off by the frame, and loose
  detail crops (a logo alone). Close-ups are fine only inside a full set from the same shoot.
- MAIN: the best product-only FRONT shot (no person, no hands). A clean straight-on studio front beats a 3/4 or side
  view (rule 37); a 3/4 standing product shot (item shaped as if worn, on an invisible mannequin) beats a flat lay. The
  main is NEVER a photo with a person.
- SNEAKERS AND SHOES (rule 39): the main is ONE shoe in clean side profile (toe pointing left or right), before any pair,
  3/4, top, sole or back shot.
- SETS (rule 40): for a set (tracksuit, two-piece) a clean studio front of the main piece (the top) is a fine main.
- KEEP THE CURRENT MAIN (rule 37): image 0 is the find's photo on the site now. When image 0 is ALREADY a clean,
  sharp, straight-on studio product-only front on a white or plain background (official-looking, item alone) at least
  as good as the chosen store's front, set "keep_current_main": true; the store's photos then follow it (owner on the
  Arc'teryx Beta LT: the current official front shot stays the main).
- BAD CURRENT MAIN (rule 38): a seller photo on a hanger or mannequin, a flat-lay or pile, a washed-out or messy cut-out
  (smeared edges, glare, ghosting), a tag or hanger hook in view, a busy room or floor: set "current_bad": true and never
  keep it as the main when any clean front exists (an exact or very similar item).
- THE OWNER wants every listing to look perfect: at the very least a very good main, and many angles (front, back, both
  sides, 3/4, details, model photos).{owner}
- "person": true for any photo where a person (or part of one: legs, hands, face) is visible; product shots on grey or
  coloured studio backgrounds are person: false.
- MANY PHOTOS: list EVERY good product-only shot of the item in the chosen store(s), not a sample: front, 3/4, back, both
  sides, top, sole, inside, real-part close-ups (the owner wants way more photos; 6-10 product shots is normal when a
  store has them). Only skip the ones the rules above reject.
- Order "photos": main first, then the other product-only shots (back, side, close-ups, sole), then photos with a person
  (front first).

Answer with JSON only:
{{"model_name": "exact product name", "colour": "colourway of the chosen photos", "store": "the store letter or null", "store2": "a second store letter or null (only when store has fewer than 4 good photos)",
"set": "full" | "picked" | "none", "photos": [{{"i": number, "view": "front|three_quarter|back|side|closeup|sole|top",
"person": true/false}}], "colour_match": true/false, "confidence": 0.0-1.0 (that the photos show the exact version),
"similar": true/false (the photos show a very similar item, not the exact version), "current_bad": true/false,
"keep_current_main": true/false, "note": "a few words: why this store, what was rejected"}}"""

OWNER = os.path.join(ROOT, "data", "store_photos_owner.json")
DEEP_SHOW = 48     # deep pass: at most this many candidates shown to the picker (cost), up to 12 per store, 8 stores
DEEP_LOAD = 90     # and at most this many downloaded


def owner_text(call):
    """The owner's own call on this find (data/store_photos_owner.json), as prompt lines."""
    if not call: return ""
    out = []
    if call.get("drop_site"): out.append("Image 0 is NOT this exact item (the owner): use it only for the brand, kind and colour; "
                                         "the main must be a store photo, never keep_current_main.")
    if call.get("needs_main"): out.append("The owner says the current photo is a bad main: find a clean product-only front.")
    if call.get("needs_more"): out.append("The owner asks for many more angles: front, back, sides, details, model photos.")
    if call.get("search_as"): out.append(f"The owner says the item is: {call['search_as']}.")
    if call.get("main") == "site": out.append("The owner keeps the current photo as the main: keep_current_main true.")
    if call.get("note"): out.append(f"Owner's note: {call['note']}.")
    return ("\n- THIS FIND (owner's call, follow it): " + " ".join(out)) if out else ""


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
    # rate limits and overload (several shards run at once): exponential back-off, about 2 minutes in all
    waits = [4, 8, 16, 32, 60]
    for k in range(len(waits) + 1):
        try:
            with urllib.request.urlopen(req, timeout=180) as r: d = json.load(r); break
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503, 529) or k == len(waits): raise
            ra = e.headers.get("retry-after") if e.headers else None
            time.sleep(min(60, float(ra)) if ra and ra.replace(".", "", 1).isdigit() else waits[k])
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            if k == len(waits): raise
            time.sleep(waits[k])
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
    # cropped = the item is CUT by the frame: more than 25% of one border is item (tight store crops where a toe or heel touches the edge are fine, Jordan 4: 7 good shots dropped at 6%) (20 Nov 2026: a sole, strap tip or
    # shadow just touching the edge dropped 11 good product shots in one run)
    m = 2
    if max(solid[:m].mean(), solid[-m:].mean(), solid[:, :m].mean(), solid[:, -m:].mean()) > 0.25: return None, "item cut off by the frame"
    ys, xs = np.where(solid)
    # a broken cut-out (rule 33, Trapstar close-ups): the tool removed most of a light or white item and only scattered
    # lines are left, so the item fills little of its own box
    box = solid[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    if box.mean() < 0.35: return None, "cut-out broke (item mostly removed)"
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
    # Supabase throttles when six runners upload at once (21 Nov 2026: 429 and 544 for 689 finds whose AI call was
    # already paid): back off and retry, about 70 seconds per photo
    waits = [3, 8, 20, 40]
    for k in range(len(waits) + 1):
        try:
            urllib.request.urlopen(req, timeout=60).read(); break
        except urllib.error.HTTPError as e:
            if e.code not in (408, 429, 500, 502, 503, 504, 520, 522, 524, 544) or k == len(waits): raise
            time.sleep(waits[k])
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if k == len(waits): raise
            time.sleep(waits[k])
    return PUB + name


def colour_of(title):
    t = " " + (title or "").lower() + " "
    hit = [c for c in sorted(COLOURS, key=len, reverse=True) if " " + c + " " in t]
    return " / ".join(hit[:2]) if hit else "the colour in image 0 (else the brand's best known colour)"


def load_cands(entry, n_max=None):
    """[(index in c, PIL image)] for candidates that download, are large enough and sharp. Kept at most 1600 px (the
    cut-out and model photos never need more), so a find with 90 candidates holds well under a gigabyte."""
    c = entry["c"]

    def one(k):
        try:
            im = open_img(fetch(c[k][0]))
            if max(im.size) < MIN_SIDE or min(im.size) < 400: return None
            if sharpness(im) < SHARP_MIN: return None
            if max(im.size) > 1600: im.thumbnail((1600, 1600), Image.LANCZOS)
            return k, im
        except Exception:
            return None
    with ThreadPoolExecutor(8) as ex:
        return [r for r in ex.map(one, range(min(len(c), n_max or len(c)))) if r]


def dhash(im, n=12):
    """A small difference hash: near-identical photos (the same store photo, resized or recompressed) get close hashes."""
    g = im.convert("L").resize((n + 1, n), Image.LANCZOS); px = list(g.getdata())
    return [px[r * (n + 1) + c] > px[r * (n + 1) + c + 1] for r in range(n) for c in range(n)]


def same_photo(a_im, b_im):
    try:
        ha, hb = dhash(a_im), dhash(b_im)
        return sum(x != y for x, y in zip(ha, hb)) <= 14          # of 144 bits
    except Exception: return False


def process(p, entry, nm, a, call=None, prev=None):
    """call: the owner's per-find call (data/store_photos_owner.json); prev: the first pass's record (deep pass)."""
    c = entry["c"]
    deep = bool(getattr(a, "deep", False))
    call = call or {}
    got = load_cands(entry, DEEP_LOAD if deep else None)
    before = current_photo(p)
    if not got: return {"v": 2, "error": "no usable candidates", "at": now(), "set": "none"}, [], before
    # groups as the collector made them: a page with its own gallery is one photoshoot, loose hits group by store
    gal_pages = {x[1] for x in c if x[4] == "s"}
    stores = {}
    for k, im in got:
        pg = entry["p"][c[k][1]]
        key = host_of(pg) + urllib.parse.urlsplit(pg).path if c[k][1] in gal_pages else host_of(pg)
        stores.setdefault(key, []).append((k, im))
    if deep:  # the new deep-search groups first, then the store the first pass chose, then the rest; capped for cost
        n_new = (entry.get("deep") or {}).get("n", 0)
        prev_store = (prev or {}).get("store")
        rank = lambda kv: (0 if kv[1][0][0] < n_new else (1 if kv[0] == prev_store else 2), kv[1][0][0])
        kept, total = {}, 0
        for key, ims in sorted(stores.items(), key=rank)[:8]:
            ims = ims[:min(12, DEEP_SHOW - total)]
            if not ims: break
            kept[key] = ims; total += len(ims)
        stores = kept
    nm = dict(nm or {})
    if call.get("search_as"): nm["name"] = call["search_as"]
    content = [{"type": "text", "text": PICK_PROMPT.format(title=p.get("title"), brand=p.get("brand"), cat=p.get("cat"),
                                                           name=nm.get("name") or entry.get("name") or "unknown",
                                                           details=nm.get("details") or "see image 0",
                                                           colour=nm.get("colour") or colour_of(p.get("title")),
                                                           owner=owner_text(call))},
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
    cached = (prev or {}).get("deep_pending") if deep else None
    if cached and all(str(i) in cached.get("num", {}) and num.get(i) and num[i][0] == cached["num"][str(i)]
                      for i in [int(ph.get("i")) for ph in cached["ans"].get("photos") or [] if str(ph.get("i")).isdigit()]):
        ans, cost = cached["ans"], 0.0   # the answer paid for before an upload was refused: no second AI call
    else:
        ans, cost = claude(content)
    pending = {"ans": json.loads(json.dumps(ans)), "num": {str(n_): v[0] for n_, v in num.items()}}
    store = letters.get(str(ans.get("store") or "").strip().upper()[:1])
    store2 = letters.get(str(ans.get("store2") or "").strip().upper()[:1])
    rec = {"model_name": ans.get("model_name"), "colour": ans.get("colour"), "colour_match": bool(ans.get("colour_match")),
           "conf": ans.get("confidence"), "note": ans.get("note"), "set": ans.get("set") or "none", "store": store,
           "v": 2, "cost": round(cost, 5), "at": now(), "main": None, "gallery": [], "model": [], "src": [], "dropped": [],
           "similar": bool(ans.get("similar")), "current_bad": bool(ans.get("current_bad"))}
    chosen, seen = [], set()
    for ph in ans.get("photos") or []:
        try: i = int(ph.get("i"))
        except Exception: continue
        if i not in num or i in seen: continue
        seen.add(i)
        k, im, host = num[i]
        if store and host != store and not (store2 and host == store2): rec["dropped"].append(f"{i}: other store"); continue  # rule 5 (+ rule 31)
        chosen.append((i, k, im, host, str(ph.get("view") or ""), bool(ph.get("person"))))
    if not store and chosen: store = rec["store"] = chosen[0][3]; chosen = [x for x in chosen if x[3] == store]
    if store2 and store2 != store:   # rule 31: the second store's photos come after the first store's, never the main
        rec["store2"] = store2; chosen = [x for x in chosen if x[3] == store] + [x for x in chosen if x[3] == store2]
    prod = [x for x in chosen if not x[5]]
    pers = [x for x in chosen if x[5]]
    # rule 18 (owner, 20 Nov 2026: "id prefer more if there are any"): every good photo of the chosen store, one per
    # angle (rule 17: no repeated angle), product shots first; at most 8 product and 3 model photos
    seen_v, keep = set(), []
    for x in prod:
        v = x[4] or "other"
        if v in seen_v and v not in ("detail", "other", "closeup"): continue
        seen_v.add(v); keep.append(x)
    prod, pers = keep[:12], pers[:3]
    # rule 24 (owner, 20 Nov 2026, Ralph jeans from poshmark at 45%): an unsure match never replaces the main; the photos
    # are added after the current one, and "photo_score" marks the find lower for the ranking
    try: conf = float(ans.get("confidence") or 0)
    except Exception: conf = 0.0
    # rule 26: a chosen store photo that IS the site's current photo proves it is the exact item (Parajumpers: the AI said
    # 40% while the store's photo was the very photo on the site)
    if any(same_photo(before, im) for _, _, im, _, _, _ in chosen):
        conf = max(conf, 0.9); rec["conf"] = conf; rec["same_as_current"] = True
    weak = conf < 0.7
    rec["photo_score"] = 0 if not chosen else (1 if weak else (3 if rec["set"] == "full" else 2))
    # the current photo as main: rule 37 (a clean straight-on studio site photo stays), rule 38 (a hanger, mannequin,
    # flat-lay or washed-out seller photo is replaced), rule 36 (a very similar item with much better photos may replace
    # a bad one), rule 24 (an unsure match that is not even very similar never replaces it); the owner's call wins
    bad_now = bool(ans.get("current_bad")) or bool(call.get("needs_main")) or bool(call.get("drop_site"))
    if call.get("main") == "site": keep_now = True
    elif call.get("drop_site"): keep_now = False
    elif bad_now: keep_now = not (not weak or ans.get("similar") or conf >= 0.4)
    else: keep_now = ans.get("keep_current_main") is True or (weak and not ans.get("similar"))
    if weak and chosen and not deep: keep_now = keep_now or not bad_now
    ans["keep_current_main"] = bool(keep_now and chosen)
    if ans.get("keep_current_main") is True:   # rule 21: the site's own clean front shot stays the main
        rec["main"] = "current"; rec["keep_current_main"] = True
        prod = [x for x in prod if x[4] not in ("front", "three_quarter")]   # rule 17: no second front
    shown = []  # (kind, image, host) for the sheets
    pid = p["id"]; k_out = 0
    for i, k, im, host, view, _ in prod:
        cut, why = cutout(im)
        if cut is None: rec["dropped"].append(f"{i} {view}: {why}"); continue
        name = f"{pid}-{'d' if deep else ''}{k_out}.webp"; k_out += 1   # deep pass: new names, the first pass's photos stay
        try: url = name if a.dry else upload(name, webp(cut, 88))
        except Exception as e:  # one refused upload drops that photo, not the whole find (the answer is kept)
            k_out -= 1; rec["dropped"].append(f"{i} {view}: upload failed {e!r}"[:120]); rec["deep_pending"] = pending; continue
        if rec["main"] is None: rec["main"] = url; kind = "main"
        else: rec["gallery"].append(url); kind = view or "product"
        rec["src"].append(entry["p"][c[k][1]]); shown.append((kind, small(cut), host.split("/")[0]))
    for m, (i, k, im, host, view, _) in enumerate(pers):
        im = im.copy(); im.thumbnail((1600, 1600), Image.LANCZOS)
        name = f"{pid}-{'d' if deep else ''}m{m}.webp"
        try: rec["model"].append(name if a.dry else upload(name, webp(im, 85)))
        except Exception as e:
            rec["dropped"].append(f"{i} model: upload failed {e!r}"[:120]); rec["deep_pending"] = pending; continue
        rec["src"].append(entry["p"][c[k][1]]); shown.append(("model", small(im), host.split("/")[0]))
    rec["src"] = list(dict.fromkeys(rec["src"]))
    if not rec["main"]: rec["set"] = "none" if not rec["model"] else "model only"
    elif rec["set"] == "full" and not rec["gallery"]: rec["set"] = "picked"
    return rec, shown, before


def small(im):
    """A sheet-sized copy (the sheets show 420 px at most): the run keeps these for every find until the end."""
    im = im.copy(); im.thumbnail((420, 420)); return im


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


def partner_order(by, shard=(0, 1)):
    """The partner's finds in this shard, most viewed first."""
    swaps = (load_json(os.path.join(ROOT, "data", "link_swaps.json"), {}) or {}).get("swaps") or {}
    stats = (load_json(os.path.join(ROOT, "data", "stats.json"), {}) or {}).get("p") or {}
    return sorted([i for i in swaps if i in by and shards.mine(i, shard)], key=lambda i: (-(stats.get(i) or [0])[0], i))


def total_spent():
    """Everything spent so far on this project (naming + picking, every shard), for the global cap."""
    return shards.spent_all()


def over_budget(a, base, base_shard):
    """The reason to stop, or None: the run's cap, the global cap (all shards), or this shard's share of it."""
    if spent >= a.max_usd: return f"run budget reached ({spent:.3f} USD), limit reached"
    if base + spent >= a.max_total_usd: return "global budget reached"
    if getattr(a, "deep", False):  # the deep pass has its own share per shard (deep_usd), on top of the first pass's spend
        if a.deep_spent0 + spent >= a.deep_usd: return f"global budget reached (this shard's deep share, {a.deep_usd:.2f} USD)"
        return None
    n = a.shard_t[1]
    if n > 1 and base_shard + spent >= a.max_total_usd / n: return f"global budget reached (this shard's share, {a.max_total_usd / n:.2f} USD)"
    return None


def run_name(a, by):
    own_path = shards.path("names", a.shard_t)
    names = load_json(own_path, {"items": {}})  # this shard's own file: the only one it writes
    named = shards.merged("names")["items"]
    base, base_shard = total_spent(), shards.spent_shard(a.shard_t)
    ids = [i for i in a.ids.split(",") if i] if a.ids else partner_order(by, a.shard_t)
    todo = [i for i in ids if i in by and (a.redo or i not in named)][:a.limit or None]
    print(f"{len(todo)} finds to name", flush=True)
    for n, i in enumerate(todo, 1):
        stop = over_budget(a, base, base_shard)
        if stop: print(stop); break
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
    os.makedirs(os.path.dirname(own_path), exist_ok=True)
    save_json(own_path, names)
    print(f"summary: named {len(todo)} finds, {spent:.4f} USD ({spent / max(1, len(todo)):.4f} per find)")


def main():
    global spent
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", action="store_true", help="step 1: name the exact models")
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--ids", default="")
    ap.add_argument("--max-usd", type=float, default=8.0)
    ap.add_argument("--max-total-usd", type=float, default=float(os.environ.get("STORE_PHOTOS_TOTAL_USD", "60")))
    ap.add_argument("--redo", action="store_true")
    ap.add_argument("--dry", action="store_true", help="no uploads (names only)")
    ap.add_argument("--shard", default="0/1", help="k/n: only the finds of shard k of n (see store_photos_shards.py)")
    ap.add_argument("--deep", action="store_true", help="the second, deeper pass: re-pick the --ids-file finds from old + new candidates")
    ap.add_argument("--ids-file", default="")
    ap.add_argument("--deep-usd", type=float, default=4.6, help="deep pass: this shard's AI budget, all its deep runs together")
    a = ap.parse_args()
    a.shard_t = shards.parse(a.shard)
    by = {p["id"]: p for p in load_catalog()[1]}
    if a.name: return run_name(a, by)
    cands = shards.merged("cands")["items"]
    names = shards.merged("names")["items"]
    log = shards.merged("log")  # every shard's results: what is done already
    own_path = shards.path("log", a.shard_t)
    own = load_json(own_path, {"items": {}, "spent_usd": 0.0})  # this shard's own file: the only one it writes
    order = [i for i in a.ids.split(",") if i] if a.ids else [i for i in partner_order(by, a.shard_t) if i in cands]
    base, base_shard = total_spent(), shards.spent_shard(a.shard_t)
    own_spent0 = own.get("spent_usd", 0)
    a.deep_spent0 = own.get("deep_spent_usd", 0.0)
    owner = load_json(OWNER, {}) or {}
    if a.deep:
        hide = set((load_json(os.path.join(ROOT, "data", "report_overrides.json"), {}) or {}).get("hide") or [])
        want = []
        with open(a.ids_file if os.path.isabs(a.ids_file) else os.path.join(ROOT, a.ids_file), encoding="utf-8") as f:
            want = [i for i in re.split(r"[\s,]+", f.read()) if i]
        stats = (load_json(os.path.join(ROOT, "data", "stats.json"), {}) or {}).get("p") or {}
        order = sorted({i for i in want if i in by and i not in hide and shards.mine(i, a.shard_t)},
                       key=lambda i: (-(stats.get(i) or [0])[0], i))

    def save_own():
        if a.dry: return
        own["spent_usd"] = round(own_spent0 + spent, 4)
        if a.deep: own["deep_spent_usd"] = round(a.deep_spent0 + spent, 4)
        os.makedirs(os.path.dirname(own_path), exist_ok=True)
        save_json(own_path, own)
    # a find whose search came back empty (Brave out of searches, 20 Nov 2026) is not done: it is picked again
    done = lambda i: (log["items"].get(i) or {}).get("v") == 2 and (log["items"].get(i) or {}).get("error") != "no usable candidates"
    # only finds searched with their exact model name (collector v2), unless asked by id
    todo = [i for i in order if i in cands and i in by and (a.ids or cands[i].get("v") == 2) and (a.redo or not done(i))][:a.limit or None]
    if a.deep:  # searched by the deep pass and not re-picked yet (or --redo)
        # a find whose deep pick failed (deep_error: an upload refused) is picked again
        # deep_pending (some uploads refused, the rest kept) counts as done: a redo would upload every photo again and
        # meet the same refusals; the saved answer lets a later --redo run skip the AI call
        ddone = lambda i: (log["items"].get(i) or {}).get("deep") == 1 and not (log["items"].get(i) or {}).get("deep_error")
        todo = [i for i in order if (cands.get(i) or {}).get("deep") and (a.redo or not ddone(i))][:a.limit or None]
    print(f"{len(todo)} finds to do; spent so far {base:.2f} USD (cap {a.max_total_usd})", flush=True)
    rows = []
    os.makedirs(OUT, exist_ok=True)
    for n, i in enumerate(todo, 1):
        stop = over_budget(a, base, base_shard)
        if stop: print(stop); break
        p = by[i]
        try:
            call = owner.get(i) if isinstance(owner.get(i), dict) else None
            prev = log["items"].get(i) or {}
            rec, shown, before = process(p, cands[i], names.get(i), a, call, prev)
            if a.deep:
                rec["deep"] = 1
                prev = prev.get("prev") or {k: prev.get(k) for k in ("main", "gallery", "model", "store", "set", "conf", "model_name") if k in prev}
                rec["prev"] = prev   # the first pass's set, kept for the audit and for going back
        except Exception as e:
            print(f"  {i} failed: {e!r}", flush=True)
            rec, shown, before = {"v": 2, "error": repr(e)[:200], "at": now(), "set": "none"}, [], None
            if a.deep:  # the first pass's set stays; marked done so a chained batch does not retry it forever
                old = log["items"].get(i) or {}
                rec = dict(old, deep=1, deep_error=repr(e)[:200], prev=old.get("prev") or {k: old.get(k) for k in ("main", "gallery", "model", "store", "set", "conf", "model_name") if k in old})
        log["items"][i] = rec; own["items"][i] = rec
        if n % 10 == 0: save_own()  # a run that is stopped keeps what it has done
        rows.append((p, rec, before, shown))
        if before is not None: review(n, p, rec, before, shown, os.path.join(OUT, f"review2-{n}.jpg"))
        print(f"[{n}/{len(todo)}] {i} {p.get('title')} -> {rec.get('model_name')} set={rec.get('set')} store={rec.get('store')} "
              f"main={'yes' if rec.get('main') else 'NO'} gallery={len(rec.get('gallery') or [])} model={len(rec.get('model') or [])} "
              f"conf={rec.get('conf')} ${rec.get('cost', 0):.4f} total ${spent:.3f} | {rec.get('error') or rec.get('note') or ''} "
              f"{'; '.join(rec.get('dropped') or [])}", flush=True)
    save_own()
    if rows:
        sheet(rows, os.path.join(OUT, "sheet.jpg"))
        print("contact sheet:", os.path.join(OUT, "sheet.jpg"))
    finished = [r for _, r, _, _ in rows]
    sets = {}
    for r in finished: sets[r.get("set")] = sets.get(r.get("set"), 0) + 1
    if a.deep:
        left = [i for i in order if not ddone(i)]
        print(f"deep remaining {len(left)} target finds not re-picked (shard {a.shard}); deep spend this shard "
              f"{a.deep_spent0 + spent:.4f} USD (share {a.deep_usd})")
    else:
        left = [i for i in partner_order(by, a.shard_t) if not done(i)]
        print(f"remaining {len(left)} partner finds without v2 store photos (shard {a.shard})")
    print(f"summary: {len(finished)} finds, sets {sets}, {spent:.4f} USD this run ({spent / max(1, len(finished)):.4f} per find), "
          f"{base + spent:.2f} USD in total (cap {a.max_total_usd})")


if __name__ == "__main__":
    main()
