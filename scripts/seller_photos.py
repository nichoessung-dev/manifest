# -*- coding: utf-8 -*-
"""Better main photos for Weidian finds, taken from the seller's OWN listing photos (owner, 10 Nov 2026).

Many finds show a bad photo: worn by a person, a collage, text on top, a hanger, a busy background. The seller's
listing usually has a better one (the main picture or a per-colour option picture). Per find:
  1. pick the finds whose photo the vision labels call not clean (data/catalog_ai.json "items"), worst issues and
     most viewed first (data/stats.json); finds the weekly link check calls dead are left out
  2. look the listing up on Weidian's public item API (the same endpoint, headers and pacing as check_links.py,
     one request at a time) and collect the main picture + the option / SKU pictures, deduped
  3. download them (same User-Agent and Referer), keep those whose short side is 900 px or more, at most 6;
     smaller photos are never enlarged (owner rule: no AI upscaling)
  4. a vision model (default claude-haiku-5-5) sees the current site photo + the candidates (512 px) + brand,
     title and colour, and picks the candidate that is a clean product photo of the SAME item in the SAME colour,
     or none. Accepted only at confidence 0.8+ with same item, same colour and clean all true. The model only
     chooses; it never draws, edits or upscales anything
  5. the chosen photo goes through clean_photos.py's deterministic pipeline (rembg mask, tidy, quality gate,
     compose a 1200x1200 transparent WebP with a soft shadow, fidelity check), WITHOUT its upscaler
  6. the result is written to img/p2/<id>.webp (a site file in git, never Supabase); a redo writes
     img/p2/<id>.v<n>.webp so browsers and the Cloudflare image cache never show a stale copy
Every find is recorded in data/seller_photos.json ("items": id -> status ok|skipped|error, reason, src, candidates,
choice, confidence, w, h, kb, date, model, file), saved after each find, so a run can stop at any time and the next
one carries on. Errors (network, Weidian busy) are retried on the next run; ok and skipped finds are not (--redo).
Nothing on the site changes here: scripts/apply_seller_photos.py points "img" at the new file (reversible).

  python scripts/seller_photos.py [--limit 50] [--ids 1,2] [--model claude-haiku-5-5] [--max-usd 5] [--max-minutes 80]
                                  [--sheets out/seller-sheets] [--redo] [--dry-run] [--mock]

  --dry-run  no network at all: prints the plan (which finds, why), a cost and time estimate and one example prompt
  --mock     no network and no API: a fake Weidian answer and fake candidate photos made locally (one clean, one
             collage with text, one too small, two duplicates), a fake picker; runs the whole write path into
             data/seller_photos.mock.json and out/mock-p2/ (unless --store / --outdir are given)
  --rembg-model threshold   (with --mock only) a plain background-distance mask instead of rembg, for tests

Env: ANTHROPIC_API_KEY (GitHub Actions secret; never printed or written). Out of credit: the run stops, keeps what
it has and exits with code 3, like catalog_ai.py.
"""
import argparse, base64, io, json, os, random, re, sys, time, urllib.error, urllib.parse, urllib.request, zlib
from datetime import datetime, timezone
from types import SimpleNamespace

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from catalog_common import ROOT, SITE, COLOURS, load_catalog, fetch, load_json, save_json, no_dash  # noqa: E402
from catalog_ai import price, OutOfCredit  # noqa: E402
import check_links  # noqa: E402  (API, UA, PAUSE: the Weidian endpoint and pacing the link check uses)
import clean_photos as CP  # noqa: E402

DEFAULT_MODEL = "claude-haiku-5-5"
MIN_SIDE = 900            # short side of a usable seller photo (px); smaller ones are skipped, never enlarged
MAX_CANDS = 6             # candidates shown to the picker
MAX_DOWNLOADS = 12        # photo downloads per find at most
THUMB_PX = 512            # what the picker sees
WORK_PX = 1600            # long side the cut-out works on (big photos are only scaled down)
REFERER = "https://weidian.com/"
# per find: 7 images of about 512x384..512 px (~260-350 tokens each, w*h/750) + ~750 prompt tokens; short answer
EST_TOKENS = (3200, 220)
FILE_CAP = 19800          # Cloudflare Pages allows 20,000 files; mirror_photos.py keeps img/m under its own 19,000 cap
# issues that make a photo worst first, in the owner's order; then the rest of the not-clean photos
FIRST = ["blurry_or_low_res", "worn_by_person", "collage_or_grid", "text_or_watermark", "multiple_items",
         "hanger_or_rack", "busy_background", "cut_out_damage", "item_cropped"]
WEIGHT = {"blurry_or_low_res": 2.0, "worn_by_person": 1.9, "collage_or_grid": 1.9, "text_or_watermark": 1.8,
          "multiple_items": 1.7, "hanger_or_rack": 1.6, "busy_background": 1.6, "cut_out_damage": 1.6,
          "item_cropped": 1.5, "hand_in_photo": 1.4, "packaging_or_box": 1.3, "multiple_views": 1.2}
SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{1,80}$")


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Skip(Exception):
    """This find gets no new photo (recorded as skipped, with the reason)."""


class StopRun(Exception):
    """Stop the whole run politely (Weidian refusing, file cap, money or time limit)."""


# ------------------------------------------------------------------ selection
def views_of(st, pid):
    v = st.get(pid)
    if not isinstance(v, list) or len(v) < 3:
        return 0, 0
    return (v[1] or 0) + (v[2] or 0), v[0] or 0


def priority(p, lab, st):
    """Sort key: finds with one of the FIRST issues before the rest; then recent views weighted by how bad the
    worst issue is; then all-time views; then id (stable)."""
    issues = set(lab.get("photo_issues") or [])
    first = bool(issues & set(FIRST))
    sev = max([WEIGHT.get(i, 1.0) for i in issues] or [1.0])
    recent, alltime = views_of(st, p["id"])
    return (0 if first else 1, -(recent * sev), -alltime, -sev, p["id"])


def select(items, labels, store, st, dead, a):
    """Weidian finds to do this run, in order. With --ids: those ids (Weidian only), labels or not."""
    done = store.get("items", {})
    if a.ids:
        want = set(a.ids.replace(" ", "").split(",")) - {""}
        pool = [p for p in items if p["id"] in want and p.get("platform") == "weidian"]
    else:
        pool = []
        for p in items:
            lab = labels.get(p["id"])
            if p.get("platform") != "weidian" or p["id"] in dead or not lab or lab.get("error"):
                continue
            if lab.get("is_clean_product_photo"):
                continue
            pool.append(p)
        pool.sort(key=lambda p: priority(p, labels.get(p["id"]) or {}, st))
    out = []
    for p in pool:
        if not SAFE_ID.match(p["id"]):
            continue
        old = done.get(p["id"])
        if old and old.get("status") == "rejected":
            continue                                        # turned down (by the owner or for damage): never again
        if old and old.get("status") in ("ok", "skipped") and not a.redo:
            continue
        out.append(p)
        if a.limit and len(out) >= a.limit:
            break
    return out


# ------------------------------------------------------------------ Weidian answer -> candidate photo URLs
SIZE_RX = re.compile(r"_(\d{2,5})_(\d{2,5})\.(?:jpe?g|png|webp)$", re.I)
IMG_PATH = re.compile(r"\.(?:jpe?g|png|webp)$", re.I)
SKIP_KEYS = re.compile(r"logo|avatar|head|icon|shop|seller|banner|qr|share|poster|video|cover", re.I)


def norm_url(u):
    """https, lower-case host, no query (geilicdn adds ?w=..&h=.. for resized copies: the bare URL is the original)."""
    if not isinstance(u, str):
        return ""
    u = u.strip()
    if u.startswith("//"):
        u = "https:" + u
    if u.startswith("http://"):
        u = "https://" + u[7:]
    try:
        t = urllib.parse.urlsplit(u)
    except ValueError:
        return ""
    if t.scheme != "https" or not t.netloc:
        return ""
    return urllib.parse.urlunsplit(("https", t.netloc.lower(), t.path, "", ""))


def ok_host(u):
    h = urllib.parse.urlsplit(u).hostname or ""
    return h == "geilicdn.com" or h.endswith(".geilicdn.com")


def size_hint(u):
    """(w, h) from a geilicdn file name ending in _W_H (e.g. ..._1279_1706.jpg), else None."""
    m = SIZE_RX.search(urllib.parse.urlsplit(u).path)
    return (int(m.group(1)), int(m.group(2))) if m else None


def _walk(o, path=()):
    if isinstance(o, dict):
        for k, v in o.items():
            yield from _walk(v, path + (str(k),))
    elif isinstance(o, list):
        for v in o:
            yield from _walk(v, path)
    elif isinstance(o, str):
        yield path, o


def parse_candidates(d):
    """Candidate photos from a getItemSkuInfo answer ({"status": {...}, "result": {...}}, or the result alone).
    Order: the listing's main picture, option pictures (attrList, with the option name), SKU pictures (with the SKU
    title), then any other listing picture in the answer. Only geilicdn photos; shop logos, avatars and the like are
    left out. Deduped by URL without its query. Each: {url, from, label, hint}."""
    res = d.get("result") if isinstance(d, dict) and isinstance(d.get("result"), dict) else (d if isinstance(d, dict) else {})
    out, seen = [], {}

    def add(u, src, label=""):
        n = norm_url(u)
        if not n or not ok_host(n) or not IMG_PATH.search(urllib.parse.urlsplit(n).path):
            return
        label = no_dash(str(label or ""))[:60]
        if n in seen:
            c = seen[n]
            if label and label not in c["label"].split(" / "):
                c["label"] = (c["label"] + " / " + label if c["label"] else label)[:80]
            return
        c = {"url": n, "from": src, "label": label, "hint": size_hint(n)}
        seen[n] = c
        out.append(c)

    add(res.get("itemMainPic"), "main")
    for k in ("itemMainPics", "itemPics", "imgs", "images", "pics"):
        for u in res.get(k) or [] if isinstance(res.get(k), list) else []:
            add(u if isinstance(u, str) else (u or {}).get("url") if isinstance(u, dict) else None, "main")
    for attr in res.get("attrList") or []:
        if not isinstance(attr, dict):
            continue
        for v in attr.get("attrValues") or []:
            if isinstance(v, dict):
                add(v.get("img") or v.get("image"), "option", v.get("attrValue") or "")
    for s in res.get("skuInfos") or []:
        si = s.get("skuInfo") if isinstance(s, dict) and isinstance(s.get("skuInfo"), dict) else s
        if isinstance(si, dict):
            add(si.get("img") or si.get("skuImg") or si.get("image"), "sku", si.get("title") or si.get("skuTitle") or "")
    for path, u in _walk(res):
        if any(SKIP_KEYS.search(k) for k in path):
            continue
        add(u, "other")
    return out


# ------------------------------------------------------------------ fetching (real and mock)
def tiny(im):
    """12x12 colour thumbnail: the same picture under two URLs gives (almost) the same pixels. Colour counts, so the
    same item photographed in two colours (two option photos) is never taken for a duplicate."""
    t = Image.new("RGBA", im.size, (255, 255, 255, 255)); t.alpha_composite(im.convert("RGBA"))
    return bytes(t.convert("RGB").resize((12, 12), Image.BILINEAR).tobytes())


def same_photo(t1, t2):
    return sum(abs(x - y) for x, y in zip(t1, t2)) / len(t1) < 4.0


class Weidian:
    """The real thing: one request at a time, check_links.PAUSE between requests, patient retries."""
    def __init__(self):
        self.requests = 0

    def _get(self, url, timeout, limit=None):
        time.sleep(check_links.PAUSE)
        self.requests += 1
        req = urllib.request.Request(url, headers={"User-Agent": check_links.UA, "Referer": REFERER})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read(limit) if limit else r.read()

    def lookup(self, item_id):
        """(result dict, "") or (None, why). Retried with growing pauses while Weidian answers with errors."""
        url = check_links.API + urllib.parse.quote(json.dumps({"itemId": str(item_id)}))
        why = ""
        for wait in (0, 5, 15, 40):
            if wait:
                time.sleep(wait)
            try:
                d = json.loads(self._get(url, 20))
            except Exception as e:  # noqa: BLE001 (network or bad JSON: retried, then an error record)
                why = "lookup failed: %s" % str(e)[:80]
                continue
            if (d.get("status") or {}).get("code") != 0:
                why = "lookup status %s" % (d.get("status") or {}).get("code")
                continue
            res = d.get("result") or {}
            if not (res.get("itemTitle") or res.get("itemMainPic")):
                return None, "listing has no title or photo (gone or hidden)"
            return d, ""
        return None, why

    def image(self, url):
        last = None
        for k in range(2):
            try:
                data = self._get(url, 30, limit=15 * 1024 * 1024 + 1)
                if len(data) > 15 * 1024 * 1024:
                    raise ValueError("photo over 15 MB")
                return data
            except urllib.error.HTTPError as e:
                last = e
                if e.code in (400, 403, 404, 410):
                    break
            except Exception as e:  # noqa: BLE001
                last = e
            time.sleep(3 * (k + 1))
        raise last


def _tee(d, cx, cy, s, colour):
    pts = [(-.45, -.9), (-.15, -.95), (0, -.8), (.15, -.95), (.45, -.9), (.95, -.5), (.7, -.2), (.5, -.35),
           (.5, .95), (-.5, .95), (-.5, -.35), (-.7, -.2), (-.95, -.5)]
    d.polygon([(cx + x * s, cy + y * s) for x, y in pts], fill=colour)


def mock_photo(size, colour, bg=(243, 243, 240), double=False, text=False, noise=0):
    w, h = size
    im = Image.new("RGB", size, bg)
    d = ImageDraw.Draw(im)
    s = min(w, h) * 0.44
    if double:
        _tee(d, w * 0.27, h / 2, s * 0.55, colour); _tee(d, w * 0.73, h / 2, s * 0.55, colour)
    else:
        _tee(d, w / 2, h / 2, s, colour)
        d.rectangle((w / 2 - s * 0.2, h / 2 - s * 0.3, w / 2 + s * 0.2, h / 2 - s * 0.1), fill=(250, 250, 250))  # a logo
    if text:
        d.rectangle((0, h - h // 9, w, h), fill=(200, 30, 30))
        d.text((20, h - h // 12), "SALE 1:1 TOP QUALITY", fill=(255, 255, 255))
    if noise:
        rnd = random.Random(noise)
        for _ in range(400):
            x, y = rnd.randrange(w), rnd.randrange(h)
            d.ellipse((x, y, x + 30, y + 30), fill=tuple(rnd.randrange(80, 200) for _ in range(3)))
    return im


def jpeg(im, q=90):
    b = io.BytesIO(); im.convert("RGB").save(b, "JPEG", quality=q); return b.getvalue()


class MockWeidian:
    """No network: a made-up getItemSkuInfo answer and made-up photos, so parsing, the size filter, the dedupe, the
    picker, the cut-out and the write path all run for real."""
    def __init__(self):
        self.requests = 0
        self.files = {}

    def lookup(self, item_id):
        self.requests += 1
        rnd = random.Random(str(item_id))
        col = rnd.choice([(20, 20, 24), (30, 50, 120), (150, 30, 40), (60, 90, 50)])
        base = "https://si.geilicdn.com/mock%s-" % item_id
        self.files[base + "main_1100_1400.jpg"] = jpeg(mock_photo((1100, 1400), col))
        self.files[base + "copy_1100_1400.jpg"] = self.files[base + "main_1100_1400.jpg"]       # same photo, other URL
        self.files[base + "collage_1100_1400.jpg"] = jpeg(mock_photo((1100, 1400), col, double=True, text=True))
        self.files[base + "small_600_800.jpg"] = jpeg(mock_photo((600, 800), col))
        self.files[base + "plain.jpg"] = jpeg(mock_photo((1000, 1200), (200, 200, 200)))         # no size in the name
        d = {"status": {"code": 0, "message": "OK"}, "result": {
            "itemId": str(item_id), "itemTitle": "mock listing", "itemStock": 10,
            "itemMainPic": base + "main_1100_1400.jpg?w=750&h=750",
            "shopLogo": "https://si.geilicdn.com/mock-logo_1200_1200.jpg",
            "attrList": [{"attrTitle": "colour", "attrValues": [
                {"attrValue": "collage", "img": base + "collage_1100_1400.jpg"},
                {"attrValue": "small", "img": base + "small_600_800.jpg"},
                {"attrValue": "grey", "img": base + "plain.jpg"}]}],
            "skuInfos": [{"skuInfo": {"id": 1, "title": "main;M", "img": base + "main_1100_1400.jpg", "stock": 5}},
                         {"skuInfo": {"id": 2, "title": "copy;L", "img": base + "copy_1100_1400.jpg", "stock": 5}}]}}
        if rnd.random() < 0.1:
            return None, "lookup status 2 (mock error)"
        return d, ""

    def image(self, url):
        self.requests += 1
        if url not in self.files:
            raise ValueError("mock: no such photo")
        return self.files[url]


def gather(cands, source, a):
    """Download candidates in order, keep at most a.max_cands whose short side is >= a.min_side. Returns
    (kept list of {url, from, label, w, h, data, im}, dropped reasons dict)."""
    kept, why, hashes, tries = [], {}, [], 0
    for c in cands:
        if len(kept) >= a.max_cands or tries >= a.max_downloads:
            break
        if c.get("hint") and min(c["hint"]) < a.min_side:
            why["under %d px (by name)" % a.min_side] = why.get("under %d px (by name)" % a.min_side, 0) + 1
            continue
        tries += 1
        try:
            data = source.image(c["url"])
            im = ImageOps.exif_transpose(Image.open(io.BytesIO(data)))
            im.load()
        except Exception as e:  # noqa: BLE001 (one bad photo never stops the find)
            why["download failed"] = why.get("download failed", 0) + 1
            if a.verbose:
                print("    photo failed %s: %s" % (c["url"][-40:], str(e)[:60]))
            continue
        w, h = im.size
        if min(w, h) < a.min_side:
            why["under %d px" % a.min_side] = why.get("under %d px" % a.min_side, 0) + 1
            continue
        hsh = tiny(im)
        if any(same_photo(hsh, x) for x in hashes):
            why["same photo twice"] = why.get("same photo twice", 0) + 1
            continue
        hashes.append(hsh)
        kept.append(dict(c, w=w, h=h, data=data, im=im))
    return kept, why


def site_photo(p):
    """The photo the find shows now: the site's own copy when there is one (img/p/..., img/m/... mirror), else
    through the site's /api/img proxy. Never straight from Supabase (its disk IO is limited)."""
    u = p.get("img") or ""
    if u.startswith("/"):
        local = os.path.join(ROOT, u.lstrip("/").split("?")[0])
        if os.path.isfile(local):
            return open(local, "rb").read()
        return fetch(SITE + u)
    try:
        from mirror_photos import mirror_path
        mp = mirror_path(u)
    except Exception:  # noqa: BLE001
        mp = ""
    if mp and os.path.isfile(os.path.join(ROOT, mp.lstrip("/"))):
        return open(os.path.join(ROOT, mp.lstrip("/")), "rb").read()
    if "supabase.co/storage/v1/object/public/" in u:
        return fetch(SITE + "/api/img?u=" + urllib.parse.quote(u, safe=""))
    return fetch(u)


# ------------------------------------------------------------------ picker (vision model)
PROMPT = """You help a fashion catalogue choose a better main photo for one find. You only choose; you never change a photo.

The find:
  brand: {brand}
  title: {title}
  category: {cat}
  colour of this find: {colour}

The first image is the photo the site shows now. It has problems ({issues}).
Then come {n} candidate photos from the seller's own listing, numbered 0 to {last}. The seller's option name is given
when there is one (often Chinese, often the colour).

Choose the ONE candidate that is a clean product photo of the SAME item in the SAME colour as this find ({colour}):
- the item alone: no person wearing or holding it (an invisible ghost mannequin is fine), no hand, no other products
- the whole item is visible, not cut off at the photo edges
- one view only: not a collage, a grid, an inset or front and back side by side
- no added text, price, shop name, logo stamp or watermark (print on the product itself is fine)
- no box, bag or packaging in front of the item; no hanger or rack if another candidate is free of them
- a plain, light or simple background, sharp, not blurry
- clearly better as a main photo than the current one
A pair of shoes counts as one item. A set sold together may show its pieces together.
When two candidates qualify, prefer the plainest background and the front view.
If no candidate meets ALL of these, the answer is -1.

Return JSON only:
- choice: the candidate number, or -1
- same_item, same_colour, clean: true/false for the chosen candidate (all false when choice is -1)
- confidence: 0 to 1, how sure you are that the chosen photo shows this exact item in this colour AND meets every rule above;
  0.9 or more only when there is no doubt
- reason: at most 20 words
"""

SCHEMA = {
    "type": "object",
    "properties": {
        "choice": {"type": "integer"},
        "same_item": {"type": "boolean"},
        "same_colour": {"type": "boolean"},
        "clean": {"type": "boolean"},
        "confidence": {"type": "number"},
        "reason": {"type": "string"},
    },
    "required": ["choice", "same_item", "same_colour", "clean", "confidence", "reason"],
    "additionalProperties": False,
}


def colour_of(p, lab):
    c = (lab.get("colour") or "").strip()
    if c:
        return c
    t = p.get("title") or ""
    for col in sorted(COLOURS, key=len, reverse=True):
        if re.search(r"(?i)\b%s\b" % re.escape(col), t):
            return col.title()
    return "(not stated: judge by the current photo)"


def prompt_for(p, lab, n):
    issues = ", ".join(i.replace("_", " ") for i in (lab.get("photo_issues") or [])) or "not a clean product photo"
    return PROMPT.format(brand=p.get("brand") or "(none)", title=p.get("title") or "", cat=p.get("cat") or "",
                         colour=colour_of(p, lab), issues=issues, n=n, last=n - 1)


def thumb_jpeg(im, px=THUMB_PX):
    """On white (cut-outs are transparent), long side px, JPEG. Only ever scaled down."""
    im = im.copy()
    if "A" in im.getbands():
        bg = Image.new("RGBA", im.size, (255, 255, 255, 255)); bg.alpha_composite(im.convert("RGBA")); im = bg
    im = im.convert("RGB"); im.thumbnail((px, px), Image.LANCZOS)
    b = io.BytesIO(); im.save(b, "JPEG", quality=85); return b.getvalue()


def request_content(p, lab, current_jpg, kept):
    """The message content: current photo, each candidate with its label, then the instructions."""
    content = [{"type": "text", "text": "Current site photo:"}]
    if current_jpg:
        content.append({"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                                    "data": base64.standard_b64encode(current_jpg).decode()}})
    else:
        content[0]["text"] = "Current site photo: (could not be loaded)"
    for k, c in enumerate(kept):
        where = {"main": "the listing's main photo", "option": "an option photo", "sku": "a SKU photo"}.get(c["from"], "a listing photo")
        lab_txt = (", seller option: %s" % c["label"]) if c.get("label") else ""
        content.append({"type": "text", "text": "Candidate %d (%s%s):" % (k, where, lab_txt)})
        content.append({"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                                    "data": base64.standard_b64encode(c["thumb"]).decode()}})
    content.append({"type": "text", "text": prompt_for(p, lab, len(kept))})
    return content


_claude = None


# Final check (owner, 10 Nov 2026, after the first 20: some new photos were no better, one had a hole in the cut-out):
# the finished cut-out next to the current photo; it is kept only when it is clearly better and undamaged.
VERDICT_SCHEMA = {"type": "object", "additionalProperties": False,
                  "required": ["clearly_better", "same_item_and_colour", "cutout_damage", "confidence", "reason"],
                  "properties": {"clearly_better": {"type": "boolean"}, "same_item_and_colour": {"type": "boolean"},
                                 "cutout_damage": {"type": "boolean"}, "confidence": {"type": "number"},
                                 "reason": {"type": "string"}}}
VERDICT_PROMPT = ("Image 1 is the photo a shopping site shows now for: {title} ({brand}). Image 2 is a new cut-out made from the "
    "seller's own listing photo, meant to replace it. Answer in JSON. clearly_better: true only if image 2 is clearly the better "
    "main product photo for a shopper (sharper or bigger item, whole item visible, cleaner: no hanger, person, hand, box, text, "
    "collage or busy background). If they are about the same, answer false. same_item_and_colour: image 2 shows the same product "
    "in the same colour as image 1 and the title. cutout_damage: true if image 2 has holes, missing or chopped parts, jagged edges "
    "or leftover background. confidence 0 to 1. reason: at most 12 words.")
VERDICT_TOKENS = (1700, 80)


def verdict_content(p, cur_jpg, new_jpg):
    return [{"type": "text", "text": "Image 1 (now):"},
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": base64.standard_b64encode(cur_jpg).decode()}},
            {"type": "text", "text": "Image 2 (new):"},
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": base64.standard_b64encode(new_jpg).decode()}},
            {"type": "text", "text": VERDICT_PROMPT.format(title=p.get("title") or "", brand=p.get("brand") or "")}]


def call_claude(model, content, schema=None):
    """Anthropic Messages API (official SDK), like catalog_ai.call_claude: images + prompt in, schema JSON out."""
    global _claude
    import anthropic
    if _claude is None:
        _claude = anthropic.Anthropic(max_retries=4, timeout=90.0)      # key from ANTHROPIC_API_KEY
    kw = {}
    if model.startswith("claude-haiku-5"):
        kw["thinking"] = {"type": "disabled"}          # allowed at effort high or below; a pick needs no thinking
    elif model.startswith("claude-sonnet-5-5"):
        kw["thinking"] = {"type": "between_tools"}     # Sonnet 5.5 rejects "disabled"; no tools here, so no thinking
    try:
        msg = _claude.messages.create(
            model=model, max_tokens=1024,
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": schema or SCHEMA}},
            messages=[{"role": "user", "content": content}], **kw)
    except anthropic.APIStatusError as e:
        if e.status_code == 402 or getattr(e, "type", "") == "billing_error" or "credit balance" in str(e).lower():
            raise OutOfCredit("Anthropic: %s" % str(e)[:200])
        raise
    if msg.stop_reason == "refusal":
        raise ValueError("refusal")
    if msg.stop_reason == "max_tokens":
        raise ValueError("answer cut off at max_tokens")
    txt = next(b.text for b in msg.content if b.type == "text")
    u = msg.usage
    return json.loads(txt), (u.input_tokens or 0), (u.output_tokens or 0)


def mock_pick(kept):
    """Deterministic fake answer: the first candidate that is not the collage; -1 when only the collage is left."""
    for k, c in enumerate(kept):
        if "collage" not in c["url"]:
            return {"choice": k, "same_item": True, "same_colour": True, "clean": True, "confidence": 0.9,
                    "reason": "mock: first candidate that is not a collage"}, 0, 0
    return {"choice": -1, "same_item": False, "same_colour": False, "clean": False, "confidence": 0.7,
            "reason": "mock: only a collage"}, 0, 0


def judge(r, n, min_conf):
    """(index or -1, confidence, reason, why not). The answer only counts when every check passes."""
    try:
        k = int(r.get("choice"))
    except (TypeError, ValueError):
        k = -1
    try:
        conf = max(0.0, min(1.0, float(r.get("confidence"))))
    except (TypeError, ValueError):
        conf = 0.0
    reason = no_dash(str(r.get("reason") or ""))[:160]
    if k < 0 or k >= n:
        return -1, conf, reason, "picker found no clean photo of this item"
    bad = [x for x in ("same_item", "same_colour", "clean") if r.get(x) is not True]
    if bad:
        return -1, conf, reason, "picker unsure: " + ", ".join(bad) + " not true"
    if conf < min_conf:
        return -1, conf, reason, "picker confidence %.2f under %.2f" % (conf, min_conf)
    return k, conf, reason, ""


# ------------------------------------------------------------------ cut-out (clean_photos.py, no upscaler)
def threshold_mask(im):
    """Test-only mask (--mock --rembg-model threshold): pixels far from the corner colour."""
    rgb = im.convert("RGB")
    w, h = rgb.size
    corners = [rgb.getpixel((x, y)) for x, y in ((2, 2), (w - 3, 2), (2, h - 3), (w - 3, h - 3))]
    bg = tuple(sorted(c[i] for c in corners)[1] for i in range(3))
    diff = ImageChops.difference(rgb, Image.new("RGB", rgb.size, bg)).convert("L")
    return diff.point(lambda v: 255 if v > 24 else 0).filter(ImageFilter.GaussianBlur(0.8))


def cut_out(im, p, a):
    """The chosen seller photo -> (1200x1200 RGBA cut-out, notes, mask stats, fidelity, how). Raises Skip."""
    im = ImageOps.exif_transpose(im)
    if max(im.size) > WORK_PX:
        im = im.copy(); im.thumbnail((WORK_PX, WORK_PX), Image.LANCZOS)           # down only, never up
    if a.rembg_model == "threshold":
        if not a.mock:
            raise SystemExit("--rembg-model threshold is for --mock tests only")
        alpha, how = threshold_mask(im), "threshold (mock)"
    else:
        alpha, how = CP.get_mask(im, a)
    set_title = re.search(r"(?i)\b(sets?|tracksuits?|pairs?)\b", p.get("title") or "")
    alpha, notes = CP.tidy(alpha, p.get("cat"), False, False)
    if "empty" in notes:
        raise Skip("cut-out: nothing found in the photo")
    bad, st = CP.gate(alpha, a, bool(set_title))
    bad += [n[9:] for n in notes if n.startswith("DAMAGED: ")]
    box = alpha.point(lambda v: 255 if v >= 24 else 0).getbbox()
    if box and max(box[2] - box[0], box[3] - box[1]) < a.min_item_px:
        bad.append("item only %d px in the photo (under %d; never upscaled)" % (max(box[2] - box[0], box[3] - box[1]), a.min_item_px))
    if bad:
        raise Skip("quality gate: " + "; ".join(bad))
    out, xy, item = CP.compose(im, alpha, a)
    fd = CP.fidelity(item, out, xy)
    if fd > 4.0:
        raise Skip("fidelity %.1f" % fd)
    return out, notes, st, fd, how


# ------------------------------------------------------------------ files, sheets
def count_site_files():
    """Files the site deploys (everything outside .git and .github), like mirror_photos.py counts them."""
    n = 0
    for dp, dn, fn in os.walk(ROOT):
        rel = os.path.relpath(dp, ROOT)
        dn[:] = [d for d in dn if not (rel == "." and d in (".git", ".github"))]
        n += len(fn)
    return n


def file_name(pid, v):
    return pid + (".v%d" % v if v > 1 else "") + ".webp"


def sheet3(rows, path):
    """rows: (id, current, chosen seller photo or None, result or None, label). Two rows of 3 tiles per line."""
    T = 240
    cols = 2
    cell_w = 3 * (T + 6) + 18
    n_rows = (len(rows) + cols - 1) // cols
    sh = Image.new("RGB", (cols * cell_w, max(1, n_rows) * (T + 36)), (255, 255, 255))
    d = ImageDraw.Draw(sh)
    for k, (pid, cur, src, res, label) in enumerate(rows):
        cx, cy = (k % cols) * cell_w, (k // cols) * (T + 36)
        for j, im in enumerate((cur, src, res)):
            x = cx + 4 + j * (T + 6)
            if im is None:
                d.rectangle((x, cy + 4, x + T, cy + T + 4), fill=(255, 236, 236) if j == 2 else (242, 242, 242))
                continue
            t = Image.new("RGBA", im.size, (255, 255, 255, 255)); t.alpha_composite(im.convert("RGBA"))
            t = t.convert("RGB"); t.thumbnail((T, T))
            sh.paste(t, (x + (T - t.width) // 2, cy + 4 + (T - t.height) // 2))
            d.rectangle((x, cy + 4, x + T, cy + T + 4), outline=(210, 214, 222))
        d.text((cx + 6, cy + T + 8), pid + "   now | seller photo | new", fill=(0, 0, 0))
        d.text((cx + 6, cy + T + 20), label[:110], fill=(60, 60, 60) if res is not None else (170, 20, 20))
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    sh.save(path, quality=86)


# ------------------------------------------------------------------ one find
def do_find(p, lab, store, source, a, ctx):
    """Process one find. Returns the record (always), raising only StopRun / OutOfCredit."""
    pid = p["id"]
    item_id = str(p.get("itemId") or pid).lstrip("0") or "0"
    old = store["items"].get(pid) or {}
    rec = {"date": now(), "model": a.model, "item": item_id}
    cur_im = None
    try:
        if a.mock:
            cur_im = mock_photo((1200, 1200), (90, 90, 90), text=True, noise=zlib.crc32(pid.encode()) % 1000 + 1)
        else:
            try:
                cur_im = Image.open(io.BytesIO(site_photo(p))); cur_im.load()
            except Exception as e:  # noqa: BLE001 (the picker can still work without it)
                print("  %s current photo not loaded: %s" % (pid, str(e)[:80]))
        d, why = source.lookup(item_id)
        if d is None and why.startswith("listing has no"):
            ctx["lookup_err"] = 0                           # Weidian answered: not a refusal (retried next run)
            raise ValueError(why)
        if d is None:
            ctx["lookup_err"] += 1
            if ctx["lookup_err"] >= a.max_lookup_errors:
                raise StopRun("%d Weidian lookups failed in a row: Weidian may be refusing; the rest waits for the next run" % ctx["lookup_err"])
            raise ValueError(why)
        ctx["lookup_err"] = 0
        cands = parse_candidates(d)
        rec["found"] = len(cands)
        if not cands:
            raise Skip("listing has no photos on Weidian's item API")
        kept, dropped = gather(cands, source, a)
        rec["candidates"] = [[c["url"], c["w"], c["h"], c["label"]] for c in kept]
        rec["dropped"] = dropped
        if not kept:
            raise Skip("no seller photo with a short side of %d px or more (%s)" % (a.min_side, ", ".join("%s %d" % kv for kv in dropped.items()) or "none found"))
        for c in kept:
            c["thumb"] = thumb_jpeg(c["im"])
        # money first: never start a call that could pass the limit
        pin, pout = price(a.model) if not a.mock else (0.0, 0.0)
        one = (EST_TOKENS[0] * pin + EST_TOKENS[1] * pout) / 1e6
        if a.max_usd and ctx["usd"] + one > a.max_usd:
            raise StopRun("money limit: $%.3f spent, the next pick could pass $%.2f" % (ctx["usd"], a.max_usd))
        if a.mock:
            r, ti, to = mock_pick(kept)
        else:
            r, ti, to = call_claude(a.model, request_content(p, lab, thumb_jpeg(cur_im) if cur_im else None, kept))
        ctx["tin"] += ti; ctx["tout"] += to; ctx["usd"] += (ti * pin + to * pout) / 1e6; ctx["calls"] += 1
        k, conf, reason, why_not = judge(r, len(kept), a.min_confidence)
        rec.update({"choice": k, "confidence": round(conf, 3), "picker": reason})
        if k < 0:
            raise Skip(why_not)
        c = kept[k]
        rec.update({"src": c["url"], "w": c["w"], "h": c["h"]})
        out, notes, st, fd, how = cut_out(c["im"], p, a)
        # final check: clearly better than now, same item and colour, no cut-out damage
        if cur_im is not None and not a.mock:
            one = (VERDICT_TOKENS[0] * pin + VERDICT_TOKENS[1] * pout) / 1e6
            if a.max_usd and ctx["usd"] + one > a.max_usd:
                raise StopRun("money limit: $%.3f spent, the final check could pass $%.2f" % (ctx["usd"], a.max_usd))
            vr, ti, to = call_claude(a.model, verdict_content(p, thumb_jpeg(cur_im), thumb_jpeg(out)), VERDICT_SCHEMA)
            ctx["tin"] += ti; ctx["tout"] += to; ctx["usd"] += (ti * pin + to * pout) / 1e6; ctx["calls"] += 1
            rec["verdict"] = {k2: vr.get(k2) for k2 in ("clearly_better", "same_item_and_colour", "cutout_damage", "confidence", "reason")}
            vc = float(vr.get("confidence") or 0)
            if not (vr.get("clearly_better") and vr.get("same_item_and_colour") and not vr.get("cutout_damage") and vc >= 0.75):
                ctx["rows"].append((pid, cur_im, c["im"], out, "REJECTED by final check: %s" % str(vr.get("reason") or "")[:60]))
                raise Skip("final check: not clearly better or damaged (%s)" % str(vr.get("reason") or "")[:120])
        buf = io.BytesIO(); out.save(buf, "WEBP", quality=a.quality, method=6); data = buf.getvalue()
        v = int(old.get("v") or 0) + 1 if old.get("status") == "ok" else max(1, int(old.get("v") or 0))
        name = file_name(pid, v)
        if ctx["files"] + 1 > FILE_CAP and not os.path.exists(os.path.join(a.outdir, name)):
            raise StopRun("the site is at %d files (Cloudflare Pages allows 20,000): no new photo files" % ctx["files"])
        os.makedirs(a.outdir, exist_ok=True)
        dest = os.path.join(a.outdir, name)
        new_file = not os.path.exists(dest)
        open(dest + ".part", "wb").write(data)
        os.replace(dest + ".part", dest)
        if new_file:
            ctx["files"] += 1
        rel = os.path.relpath(dest, ROOT).replace(os.sep, "/")
        rec.update({"status": "ok", "reason": "%s; %s" % (how, "; ".join(notes) or "clean mask"), "file": rel, "v": v,
                    "kb": len(data) // 1024, "fidelity": round(fd, 2), "mask": st})
        ctx["rows"].append((pid, cur_im, c["im"], out, "ok %.2f %s" % (conf, reason)))
    except Skip as e:
        rec.update({"status": "skipped", "reason": str(e)[:240]})
        if old.get("status") == "ok":                       # a redo that failed keeps the earlier good photo
            rec.update({k_: old[k_] for k_ in ("file", "v", "src", "w", "h", "kb", "choice", "confidence", "model") if k_ in old})
            rec["status"] = "ok"; rec["reason"] = "redo skipped (%s); earlier photo kept" % str(e)[:160]
        src_im = None
        if rec.get("choice", -1) >= 0 and "kept" in locals():
            src_im = kept[rec["choice"]]["im"]
        ctx["rows"].append((pid, cur_im, src_im, None, "skip: " + str(e)))
    except (StopRun, OutOfCredit):
        raise
    except Exception as e:  # noqa: BLE001 (recorded; retried on the next run)
        rec.update({"status": "error", "reason": str(e)[:240]})
        if old.get("status") == "ok":
            rec.update({k_: old[k_] for k_ in ("file", "v", "src", "w", "h", "kb", "choice", "confidence", "model") if k_ in old})
            rec["status"] = "ok"; rec["reason"] = "redo failed (%s); earlier photo kept" % str(e)[:160]
    for c in (locals().get("kept") or []):
        c.pop("im", None); c.pop("data", None); c.pop("thumb", None)
    return rec


# ------------------------------------------------------------------ main
def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", default=os.path.join(ROOT, "index.html"))
    ap.add_argument("--labels", default=os.path.join(ROOT, "data", "catalog_ai.json"))
    ap.add_argument("--stats", default=os.path.join(ROOT, "data", "stats.json"))
    ap.add_argument("--link-health", default=os.path.join(ROOT, "data", "link_health.json"))
    ap.add_argument("--store", default=None, help="results file (default data/seller_photos.json)")
    ap.add_argument("--outdir", default=None, help="where photos go (default img/p2)")
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--ids", default="")
    ap.add_argument("--model", default=None)
    ap.add_argument("--min-confidence", type=float, default=0.8)
    ap.add_argument("--max-usd", type=float, default=5.0, help="hard stop for this run's picker spend (0 = none)")
    ap.add_argument("--max-minutes", type=float, default=0)
    ap.add_argument("--max-lookup-errors", type=int, default=5, help="stop after this many failed lookups in a row")
    ap.add_argument("--min-side", type=int, default=MIN_SIDE)
    ap.add_argument("--max-cands", type=int, default=MAX_CANDS)
    ap.add_argument("--max-downloads", type=int, default=MAX_DOWNLOADS)
    ap.add_argument("--min-item-px", type=int, default=800, help="the item's long side in the photo; smaller is skipped")
    ap.add_argument("--rembg-model", default="isnet-general-use")
    ap.add_argument("--fill", type=float, default=0.86)
    ap.add_argument("--shadow", type=float, default=0.16)
    ap.add_argument("--max-parts", type=int, default=3)
    ap.add_argument("--quality", type=int, default=84)
    ap.add_argument("--sheets", default="", help="write before/after contact sheets here")
    ap.add_argument("--redo", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args(argv)
    a.model = "mock" if a.mock else (a.model or os.environ.get("SELLER_PHOTOS_MODEL") or DEFAULT_MODEL)
    a.store = a.store or os.path.join(ROOT, "data", "seller_photos.mock.json" if a.mock else "seller_photos.json")
    if not a.outdir:
        a.outdir = os.path.join(ROOT, "out", "mock-p2") if a.mock else os.path.join(ROOT, "img", "p2")
    # what clean_photos.py's functions read from their argparse namespace
    a.recut, a.bg = False, "none"

    _, items, _, _ = load_catalog(a.index)
    labels = load_json(a.labels, {}).get("items", {})
    st = load_json(a.stats, {}).get("p", {})
    dead = set(str(x) for x in load_json(a.link_health, {}).get("dead", []))
    store = load_json(a.store, {})
    store.setdefault("items", {}); store.setdefault("runs", [])
    todo = select(items, labels, store, st, dead, a)
    weid = sum(1 for p in items if p.get("platform") == "weidian")
    bad = sum(1 for p in items if p.get("platform") == "weidian" and p["id"] not in dead
              and (labels.get(p["id"]) or {}).get("is_clean_product_photo") is False and not labels[p["id"]].get("error"))
    done = {}
    for v in store["items"].values():
        done[v.get("status")] = done.get(v.get("status"), 0) + 1
    pin, pout = price(a.model) if not a.mock else (0.0, 0.0)
    per = (EST_TOKENS[0] * pin + EST_TOKENS[1] * pout) / 1e6
    print("Weidian finds %d, photo not clean %d (dead left out: %d); recorded so far %s; this run %d (%s)"
          % (weid, bad, len(dead), done or "none", len(todo), a.model))
    print("picker cost estimate: at most $%.4f per find, $%.2f per 100, this run at most $%.2f (only finds with a usable "
          "candidate are sent; %s in/out tokens per find, $%.2f/$%.2f per 1M)"
          % (per, per * 100, per * len(todo), EST_TOKENS, pin, pout))
    print("time estimate: about %.0f min (one Weidian request at a time, %.2f s apart, up to %d photos per find, rembg on CPU)"
          % (len(todo) * 25 / 60.0, check_links.PAUSE, a.max_downloads))
    if a.dry_run:
        for p in todo[:15]:
            lab = labels.get(p["id"]) or {}
            print("  %s  %-48s issues=%s views30+7=%d" % (p["id"], (p.get("title") or "")[:48],
                                                          ",".join(lab.get("photo_issues") or []) or "-", views_of(st, p["id"])[0]))
        if todo:
            p = todo[0]
            print("---- example prompt (after the current photo and %d candidate photos) ----" % a.max_cands)
            print(prompt_for(p, labels.get(p["id"]) or {}, a.max_cands) + "----")
            print("ids:", ",".join(x["id"] for x in todo[:40]) + (" ..." if len(todo) > 40 else ""))
        return 0
    if not a.mock and not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY is not set")

    source = MockWeidian() if a.mock else Weidian()
    ctx = {"lookup_err": 0, "tin": 0, "tout": 0, "usd": 0.0, "calls": 0, "rows": [], "files": count_site_files()}
    n = {"ok": 0, "skipped": 0, "error": 0}
    t0 = time.time()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    n_sheet, fatal, stop = 0, "", ""
    try:
        for k, p in enumerate(todo):
            if a.max_minutes and time.time() - t0 > a.max_minutes * 60:
                stop = "time limit reached"; break
            try:
                rec = do_find(p, labels.get(p["id"]) or {}, store, source, a, ctx)
            except StopRun as e:
                stop = str(e); break
            except OutOfCredit as e:
                fatal = str(e); break
            store["items"][p["id"]] = rec
            n[rec["status"]] = n.get(rec["status"], 0) + 1
            save_json(a.store, store)
            print("  %d/%d %s %s: %s" % (k + 1, len(todo), p["id"], rec["status"], rec.get("reason", "")[:110]), flush=True)
            if a.sheets and len(ctx["rows"]) >= 16:
                n_sheet += 1; sheet3(ctx["rows"], os.path.join(a.sheets, "seller-%s-%03d.jpg" % (stamp, n_sheet))); ctx["rows"] = []
    finally:
        if a.sheets and ctx["rows"]:
            n_sheet += 1; sheet3(ctx["rows"], os.path.join(a.sheets, "seller-%s-%03d.jpg" % (stamp, n_sheet)))
        store["runs"].append({"date": now(), "model": a.model, "asked": len(todo), "ok": n["ok"], "skipped": n["skipped"],
                              "errors": n["error"], "picks": ctx["calls"], "requests": source.requests,
                              "tokens_in": ctx["tin"], "tokens_out": ctx["tout"], "usd": round(ctx["usd"], 4),
                              "stopped": stop or fatal or ""})
        store["runs"] = store["runs"][-200:]
        store["updated"] = now()
        save_json(a.store, store)
    if stop:
        print("stopped early: " + stop)
    print("done: %d new photos, %d skipped, %d errors; %d picks, tokens in %d / out %d, $%.3f; %d requests in %.0f s -> %s"
          % (n["ok"], n["skipped"], n["error"], ctx["calls"], ctx["tin"], ctx["tout"], ctx["usd"], source.requests,
             time.time() - t0, a.store))
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as f:
            f.write("### Seller photos\n\n%d new photos, %d skipped, %d errors, %d picks, $%.3f (%s).%s\n\n"
                    % (n["ok"], n["skipped"], n["error"], ctx["calls"], ctx["usd"], a.model, (" Stopped early: " + stop) if stop else ""))
    if fatal:
        print("::error::STOPPED: the Anthropic account is out of credit (%s). Finished finds are saved; top up and run again." % fatal)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
