# -*- coding: utf-8 -*-
"""Render vertical shorts (1080x1920) about the most-viewed finds, in rotating formats.

Formats (--format):
  spotlight  the #1 unposted most-viewed item: hook -> price -> real QC photos
  top5       countdown of the five most-viewed items this week
  guess      "guess the price": item -> 3-2-1 -> reveal
  qc         "how to QC it": three things to check on that model, over real QC photos
  term       rep term of the day (GL/RL, W2C, batch ...)
  order      how to order in 4 steps, using a top item as the example
  story      "did you know" story over real footage/photos, narrated by the mascot (scripts/stories.json)
  relatable  the mascot says a relatable line, punchline lands on a top find
  auto       (default) rotates through the list above, by --slot

  python scripts/make_short.py                       # auto format, next unposted item -> out/short-*.mp4 + .json
  python scripts/make_short.py --format top5
  python scripts/make_short.py --format qc --id 6716583439

Needs: pillow, imageio-ffmpeg. Voiceover is added when ELEVENLABS_API_KEY is set (otherwise the video is silent).
QC photos come from the site's own /api/qc (edge-cached for 7 days).
"""
import argparse, io, json, os, re, subprocess, sys, tempfile, urllib.parse, urllib.request, wave

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps
import imageio_ffmpeg

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://www.puroclassico.com"
W, H, FPS = 1080, 1920, 30
BG, CARD, INK, MUTED, ACCENT, RED, GREEN = (12, 18, 32), (244, 242, 238), (242, 245, 251), (148, 160, 189), (123, 154, 224), (225, 48, 31), (74, 190, 130)
FONT = os.path.join(ROOT, "scripts", "fonts", "HankenGrotesk.ttf")
FONT2 = os.path.join(ROOT, "scripts", "fonts", "Montserrat.ttf")   # caption face of the "style" videos
UA = {"User-Agent": "Mozilla/5.0 (PuroClassicoShorts/1.0; +https://www.puroclassico.com)"}
PLAT = {"weidian": "Weidian", "taobao": "Taobao", "1688": "1688"}
FORMATS = ["style", "story", "relatable", "story", "guess", "story", "top5", "story", "qc", "story", "term", "story", "order"]
FF = imageio_ffmpeg.get_ffmpeg_exe()
VOICES = [v for v in (os.environ.get("SHORTS_VOICE", "").strip(), "fYdm7SWZ5yjWg5gCjVsS", "pNInz6obpgDQGcFmaJgB", "nPczCjzI2devNBz1zQrb", "bIHbv24MWmeRgasZH58o", "TX3LPaxmHKxFdv7VOQHJ") if v]   # Adam first, then   # Brian (owner's pick), Will, Liam
VOICE_MODEL = "eleven_multilingual_v2"; _VOICE = {}

TERMS = [  # (term, what it stands for, plain-English meaning, example line)
    ("GL / RL", "Green light / Red light", "GL means the item looks right, ship it. RL means there's a flaw, so exchange it before it ships.", "You decide from the QC photos."),
    ("QC", "Quality check", "Photos your agent takes of your exact item at the warehouse, before it leaves China.", "No QC photos? Don't ship yet."),
    ("W2C", "Where to cop", "Someone asking for the link to an item.", "The answer is usually a spreadsheet."),
    ("Batch", "One factory's production run", "The same shoe can come from several batches, and the quality can differ a lot.", "Always compare batches."),
    ("Haul", "Several items in one parcel", "Shipping many items together costs less per item than shipping them one by one.", "Bigger haul, cheaper shipping."),
    ("Agent", "Your buyer in China", "A service that buys from Weidian, Taobao and 1688 for you, checks the item and ships it to you.", "MyCNBox and KakoBuy are agents."),
    ("Volumetric weight", "Size counts, not just weight", "Couriers charge for how much space the parcel takes. That's why people remove shoe boxes.", "No box means cheaper shipping."),
    ("Rehearsal", "Rehearsal packaging", "Your agent packs the parcel first and shows you the real weight before you pay for shipping.", "No surprises on the bill."),
]
# relatable lines: (setup the character says, punchline shown with the find, on-screen setup, on-screen punchline)
RELATABLE = [
    ("POV: your friend paid full retail.", "And you paid {usd}.", "POV: your friend paid retail", "You paid {price}"),
    ("Me, refreshing the tracking page for the fortieth time today.", "It still says: departed from sorting centre.", "Me checking tracking again", "\"Departed from sorting centre\""),
    ("That feeling when the QC photos come back...", "and it's a green light.", "When the QC photos come back", "And it's a GL"),
    ("When someone asks: where did you get that?", "And you just say... a spreadsheet.", "\"Where did you get that?\"", "\"A spreadsheet.\""),
    ("Retail price? No thanks.", "The spreadsheet says {usd}.", "Retail price? No thanks", "Spreadsheet price: {price}"),
    ("Me explaining to my mum why a parcel from China takes two weeks.", "It's worth the wait, mum.", "Explaining my haul to my mum", "\"It's worth the wait\""),
    ("When shipping costs more than the hoodie.", "That's why we ship a whole haul at once.", "Shipping costs more than the hoodie", "So we ship a whole haul"),
    ("My wallet, before I found the China side.", "My wallet now. Much better.", "My wallet before the China side", "My wallet now"),
    ("When you remove the shoe box to save on shipping.", "Big brain move.", "Removing the shoe box", "Cheaper shipping. Big brain"),
    ("Me saying I'll only order one thing.", "The cart: eleven items.", "\"I'll only order one thing\"", "The cart: 11 items"),
    ("When your haul finally lands after two weeks.", "Best day of the month.", "The haul finally landed", "Best day of the month"),
    ("Everyone asking for the link.", "It's in the spreadsheet. It's always in the spreadsheet.", "\"W2C?? Link??\"", "It's in the spreadsheet"),
]
STEPS = [("Find it", "Search the spreadsheet and open the find."), ("Open it in your agent", "Tap Buy and it opens in MyCNBox, ready to order."),
         ("Check the QC photos", "Your agent photographs your item at the warehouse."), ("Ship it home", "Pick a shipping line and track it to your door.")]


import functools
@functools.lru_cache(maxsize=256)
def font(size, weight=700):
    f = ImageFont.truetype(FONT, size)
    try: f.set_variation_by_axes([weight])
    except Exception: pass
    return f


@functools.lru_cache(maxsize=64)
def mfont(size, weight=800):
    try: f = ImageFont.truetype(FONT2, size); f.set_variation_by_axes([weight]); return f
    except Exception: return font(size, 900)


def fetch(url, timeout=30, data=None, headers=None):
    h = dict(UA); h.update(headers or {})
    return urllib.request.urlopen(urllib.request.Request(url, data=data, headers=h), timeout=timeout).read()


def load_img(url):
    try:
        im = ImageOps.exif_transpose(Image.open(io.BytesIO(fetch(url))))
        if im.mode in ("RGBA", "LA", "P"):                # cut-out product shots: put them on the card colour, not black
            im = im.convert("RGBA"); flat = Image.new("RGBA", im.size, CARD + (255,)); flat.alpha_composite(im); im = flat
        return im.convert("RGB")
    except Exception as e:
        print("  image failed:", url[:80], e); return None


def img_url(p):
    u = p.get("img") or ""
    if "supabase.co/storage/v1/object/public/" in u:      # same proxy the site uses (edge cached)
        return SITE + "/api/img?u=" + urllib.parse.quote(u, safe="")
    return u if u.startswith("http") else SITE + u


def qc_photos(pid, p, limit=4):
    try:
        d = json.loads(fetch("%s/api/qc?storefront=%s&id=%s" % (SITE, p.get("platform"), p.get("itemId") or pid)))
    except Exception as e:
        print("  no QC:", e); return []
    out = []
    for u in (d.get("thumbnails") or [])[:6]:
        im = load_img(u)
        if im and min(im.size) >= 200: out.append(im)
    def interest(im):                                     # label/tag close-ups are flat grey text: low contrast spread
        g = im.convert("L").resize((64, 64)); px = list(g.getdata()); m = sum(px) / len(px)
        dark = sum(1 for v in px if v < 90) / len(px)
        return (sum((v - m) ** 2 for v in px) / len(px)) ** 0.5 + 120 * dark
    if len(out) > 1:
        keep = sorted(sorted(range(len(out)), key=lambda k: -interest(out[k]))[:limit])
        ranked = sorted(keep, key=lambda k: (interest(out[k]) < 0.6 * max(interest(o) for o in out), k))   # weakest ones last
        out = [out[k] for k in ranked]
    return out[:limit]


MEDIA_DIR = os.path.join(tempfile.gettempdir(), "pc_media"); _USED = set()

def _clean(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html or "")).strip()

def pexels(q, kind):
    key = os.environ.get("PEXELS_API_KEY", "").strip()
    if not key: return None
    try:
        if kind == "video":
            d = json.loads(fetch("https://api.pexels.com/videos/search?" + urllib.parse.urlencode({"query": q, "orientation": "portrait", "per_page": 8}), 30, None, {"Authorization": key}))
            for v in d.get("videos", []):
                if v["id"] in _USED or v.get("duration", 0) < 4: continue
                files = sorted([f for f in v.get("video_files", []) if f.get("file_type") == "video/mp4" and 700 <= (f.get("width") or 0) <= 1440], key=lambda f: abs((f.get("height") or 0) - 1920))
                if not files: continue
                os.makedirs(MEDIA_DIR, exist_ok=True); path = os.path.join(MEDIA_DIR, "px%d.mp4" % v["id"])
                if not os.path.exists(path): open(path, "wb").write(fetch(files[0]["link"], 120))
                _USED.add(v["id"]); return ("video", path, "Video: %s / Pexels" % (v.get("user") or {}).get("name", ""))
        else:
            d = json.loads(fetch("https://api.pexels.com/v1/search?" + urllib.parse.urlencode({"query": q, "orientation": "portrait", "per_page": 8}), 30, None, {"Authorization": key}))
            for ph in d.get("photos", []):
                if ph["id"] in _USED: continue
                im = load_img(ph["src"]["large2x"])
                if im: _USED.add(ph["id"]); return ("image", im, "Photo: %s / Pexels" % ph.get("photographer", ""))
    except Exception as e:
        print("  pexels failed:", q, e)
    return None

def _on_topic(q, tags):
    words = [w for w in re.findall(r"[a-z]+", q.lower()) if len(w) > 3]; t = (tags or "").lower()
    hits = sum(1 for w in words if w[:5] in t)
    return hits >= min(len(words), 2) if words else True

def pixabay(q, kind):
    key = os.environ.get("PIXABAY_API_KEY", "").strip()
    if not key: return None
    try:
        if kind == "video":
            d = json.loads(fetch("https://pixabay.com/api/videos/?" + urllib.parse.urlencode({"key": key, "q": q, "per_page": 15, "safesearch": "true", "video_type": "film"})))
            for v in d.get("hits", []):
                if ("pb", v["id"]) in _USED or v.get("duration", 0) < 4 or not _on_topic(q, v.get("tags")): continue
                f = next((v["videos"][k] for k in ("medium", "large", "small") if (v["videos"].get(k) or {}).get("url") and (v["videos"][k].get("height") or 0) >= 700), None)
                if not f: continue
                os.makedirs(MEDIA_DIR, exist_ok=True); path = os.path.join(MEDIA_DIR, "pb%d.mp4" % v["id"])
                if not os.path.exists(path): open(path, "wb").write(fetch(f["url"], 180))
                _USED.add(("pb", v["id"])); return ("video", path, "Video: %s / Pixabay" % v.get("user", ""))
        else:
            d = json.loads(fetch("https://pixabay.com/api/?" + urllib.parse.urlencode({"key": key, "q": q, "per_page": 10, "image_type": "photo", "orientation": "vertical", "safesearch": "true"})))
            for ph in d.get("hits", []):
                if ("pbi", ph["id"]) in _USED or not _on_topic(q, ph.get("tags")): continue
                im = load_img(ph.get("largeImageURL") or ph.get("webformatURL"))
                if im: _USED.add(("pbi", ph["id"])); return ("image", im, "Photo: %s / Pixabay" % ph.get("user", ""))
    except Exception as e:
        print("  pixabay failed:", q, e)
    return None

def stock(q):                                                # real video first, then photos, then Wikimedia Commons
    return pexels(q, "video") or pixabay(q, "video") or pexels(q, "photo") or pixabay(q, "photo") or commons(q)

def commons(q):
    try:
        u = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode({"action": "query", "format": "json", "generator": "search", "gsrnamespace": 6, "gsrlimit": 12,
            "gsrsearch": q + " filetype:bitmap", "prop": "imageinfo", "iiprop": "url|extmetadata|size|mime", "iiurlwidth": 1600})
        pages = sorted((json.loads(fetch(u)).get("query", {}).get("pages", {}) or {}).values(), key=lambda x: x.get("index", 0))
    except Exception as e:
        print("  commons failed:", q, e); return None
    words = [w for w in re.findall(r"[a-z]+", q.lower()) if len(w) > 3]
    for strict in (True, False):
        for p in pages:
            ii = p["imageinfo"][0]; m = ii.get("extmetadata", {}); title = p["title"].lower()
            if p["title"] in _USED or ii.get("mime") not in ("image/jpeg", "image/png") or ii.get("width", 0) < 1000: continue
            if strict and not any(w in title for w in words): continue
            lic = (m.get("LicenseShortName", {}) or {}).get("value", "")
            if not re.match(r"(CC0|CC BY|Public domain|PD)", lic or "", re.I): continue
            im = load_img(ii.get("thumburl") or ii["url"])
            if im is None: continue
            _USED.add(p["title"]); artist = _clean((m.get("Artist", {}) or {}).get("value", ""))[:40]
            return ("image", im, "Photo: %s, %s, Wikimedia Commons" % (artist or "unknown", lic))
    return None

def media(q):
    """Real footage for a search phrase: (kind, video-path-or-image, credit) or None."""
    for q2 in (q, " ".join(q.split()[:2])):
        r = stock(q2)
        if r: print("  media:", q2, "->", r[0], r[2]); return r
    print("  media: nothing for", q); return None

BROWSER_UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"}
def pexels_clip(vid):
    """A specific, hand-picked Pexels video by id (720p). Returns (kind, path, credit) or None."""
    os.makedirs(MEDIA_DIR, exist_ok=True); path = os.path.join(MEDIA_DIR, "pexels%d.mp4" % vid)
    if not os.path.exists(path):
        for q in ("?h=1280&w=720", "?h=720&w=1280", ""):
            try:
                data = fetch("https://www.pexels.com/download/video/%d/%s" % (vid, q), 180, None, BROWSER_UA)
                if len(data) > 50000: open(path, "wb").write(data); break
            except Exception as e: err = e
        else:
            print("  hand-picked clip %d unavailable:" % vid, err); return None
    return ("video", path, "Video: Pexels")

def drive_file(fid, ext="bin"):
    """Any file from the owner's link-shared Drive folder, cached locally. Returns its path or None."""
    os.makedirs(MEDIA_DIR, exist_ok=True); path = os.path.join(MEDIA_DIR, "drive_%s.%s" % (fid, ext))
    if not os.path.exists(path):
        for u in ("https://drive.google.com/uc?export=download&id=%s" % fid, "https://drive.usercontent.google.com/download?id=%s&export=download&confirm=t" % fid):
            try:
                d = fetch(u, 180, None, BROWSER_UA)
                if len(d) > 20000 and not d[:15].lstrip().lower().startswith(b"<!doctype"): open(path, "wb").write(d); break
            except Exception as e: err = e
    return path if os.path.exists(path) else None

def drive_clip(fid, start=0.0, opts=None):
    """One of the owner's own clips or photos from Google Drive (the folder is shared by link). Returns a shot or None."""
    os.makedirs(MEDIA_DIR, exist_ok=True); path = os.path.join(MEDIA_DIR, "drive_%s.bin" % fid)
    if not os.path.exists(path):
        data = None
        for u in ("https://drive.google.com/uc?export=download&id=%s" % fid, "https://drive.usercontent.google.com/download?id=%s&export=download&confirm=t" % fid):
            try:
                d = fetch(u, 180, None, BROWSER_UA)
                if len(d) > 20000 and not d[:15].lstrip().lower().startswith(b"<!doctype"): data = d; break
            except Exception as e: err = e
        if data is None: print("  drive file %s unavailable" % fid); return None
        open(path, "wb").write(data)
    head = open(path, "rb").read(12)
    if head[:8] == b"\x89PNG\r\n\x1a\n" or head[:3] == b"\xff\xd8\xff":
        try: return ("photo", Image.open(path).convert("RGB"), "")
        except Exception: return None
    meta = {"ss": float(start)}
    if opts and opts.get("arrow"):
        x0, y0, x1, y1 = opts["arrow"]; meta.update(fx="orbit", ding=True, bell=bool(opts.get("bell")), freeze=bool(opts.get("freeze", opts.get("bell"))), box=(x0 * W, y0 * H, x1 * W, y1 * H))
    return ("video", path, "", meta)

def picked(ids):
    out = [c for c in (pexels_clip(i) for i in ids or []) if c]
    if ids: print("  hand-picked:", ids, "->", len(out), "ok")
    return out

def media_many(q, n=3, themes=()):
    """Up to n different real shots for one phrase; falls back to the story's on-topic themes, never to a lone generic word."""
    out = []
    for q2 in (list(q) if isinstance(q, (list, tuple)) else [q]) + list(themes):
        while len(out) < n:
            r = stock(q2)
            if not r: break
            out.append(r)
        if len(out) >= n: break
    print("  media:", q, "->", [(m[0], m[2][:40]) for m in out]); return out

class Clip:                                                  # reads a video as 1080x1920 frames, looping; key=True removes a green screen
    def __init__(self, path, key=False, ss=0.0): self.path = path; self.p = None; self.key = key; self.ss = ss
    def frame(self):
        n = 4 if self.key else 3
        if self.p is None:
            vf = "scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d,fps=%d" % (W, H, W, H, FPS)
            if self.key: vf += ",chromakey=0x00FF00:0.20:0.08,despill=type=green,format=rgba"
            self.p = subprocess.Popen([FF, "-loglevel", "error"] + (["-ss", "%.2f" % self.ss] if self.ss else ["-stream_loop", "-1"]) + ["-i", self.path, "-an", "-vf", vf,
                "-f", "rawvideo", "-pix_fmt", "rgba" if self.key else "rgb24", "-"], stdout=subprocess.PIPE)
        b = self.p.stdout.read(W * H * n)
        if len(b) != W * H * n: return None
        return Image.frombuffer("RGBA", (W, H), b) if self.key else Image.frombuffer("RGB", (W, H), b).convert("RGBA")
    def close(self):
        if self.p: self.p.kill(); self.p = None


def models():
    out = []
    for f in ("content2.js", "content3.js"):
        s = open(os.path.join(ROOT, "functions", "_lib", f), encoding="utf-8").read()
        for slug, name, rx, qc in re.findall(r'\{ slug: "([^"]+)", name: "([^"]+)", rx: "((?:[^"\\]|\\.)*)", intro: "(?:[^"\\]|\\.)*", qc: \[([^\]]*)\]', s):
            out.append((slug, name, re.compile(rx.replace("\\\\", "\\"), re.I), re.findall(r'"((?:[^"\\]|\\.)*)"', qc)))
    return out


class Data:
    def __init__(self):
        self.products = json.load(open(os.path.join(ROOT, "products.json"), encoding="utf-8"))
        self.stats = json.load(open(os.path.join(ROOT, "data", "stats.json"), encoding="utf-8"))["p"]
        try: self.state = json.load(open(os.path.join(ROOT, "shorts_posted.json")))
        except Exception: self.state = {}
        if isinstance(self.state, list): self.state = {"ids": self.state}
        self.done = set(self.state.get("ids", []))
        r = sorted(self.stats.items(), key=lambda kv: (-kv[1][2], -kv[1][1], -kv[1][0]))      # 7d, 30d, all-time views
        self.ranked = [(i, v) for i, v in r if i in self.products and self.products[i].get("img")]

    def top(self, n=1, skip_done=True, where=None):
        out = []
        for i, v in self.ranked:
            if skip_done and i in self.done: continue
            if where and not where(i, self.products[i]): continue
            out.append((i, self.products[i], v))
            if len(out) == n: break
        return out


# ---------------------------------------------------------------- drawing helpers
import base64, math, random

def ease(t): t = max(0.0, min(1.0, t)); return 1 - (1 - t) ** 3
def pop(t, d=0.38):                                          # 0 -> overshoot -> 1 (for things that "pop" in)
    t = max(0.0, min(1.0, t / d)); return 1 + 2.2 * (t - 1) ** 3 + 1.2 * (t - 1) ** 2

def rounded(im, r):
    m = Image.new("L", im.size, 0); ImageDraw.Draw(m).rounded_rectangle([0, 0, im.size[0] - 1, im.size[1] - 1], r, fill=255)
    out = Image.new("RGBA", im.size); out.paste(im, (0, 0), m); return out

def cover(im, w, h, zoom=1.0):
    s = max(w / im.size[0], h / im.size[1]) * zoom
    im2 = im.resize((max(w, int(im.size[0] * s)), max(h, int(im.size[1] * s))), Image.LANCZOS)
    x, y = (im2.size[0] - w) // 2, (im2.size[1] - h) // 2
    return im2.crop((x, y, x + w, y + h))

def contain_on_card(im, w, h, pad):
    c = Image.new("RGB", (w, h), CARD); s = min((w - 2 * pad) / im.size[0], (h - 2 * pad) / im.size[1])
    im2 = im.resize((int(im.size[0] * s), int(im.size[1] * s)), Image.LANCZOS)
    c.paste(im2, ((w - im2.size[0]) // 2, (h - im2.size[1]) // 2)); return c

def paste(fr, im, cx, cy, scale=1.0, alpha=1.0, angle=0):
    if alpha <= 0 or scale <= 0.02: return
    if abs(scale - 1) > 0.004: im = im.resize((max(2, int(im.size[0] * scale)), max(2, int(im.size[1] * scale))), Image.BILINEAR)
    if angle: im = im.rotate(angle, resample=Image.BICUBIC, expand=True)
    if alpha < 1: im = im.copy(); im.putalpha(im.getchannel("A").point(lambda v: int(v * alpha)))
    x, y = int(cx - im.size[0] / 2), int(cy - im.size[1] / 2)
    fr.alpha_composite(im, (x, y)) if (x >= 0 and y >= 0 and x + im.size[0] <= W and y + im.size[1] <= H) else fr.paste(im, (x, y), im)

def wrap(d, s, f, maxw):
    lines, cur = [], ""
    for word in s.split():
        t = (cur + " " + word).strip()
        if d.textlength(t, font=f) <= maxw or not cur: cur = t
        else: lines.append(cur); cur = word
    if cur: lines.append(cur)
    return lines

_M = ImageDraw.Draw(Image.new("RGB", (8, 8)))
def fit(s, maxw, max_lines, size, weight=800, lo=40):       # largest font that fits the box
    while size > lo:
        f = font(size, weight)
        if len(wrap(_M, s, f, maxw)) <= max_lines: return f
        size -= 4
    return font(lo, weight)

def text(fr, s, f, y, fill=INK, maxw=W - 140, alpha=1.0, dy=0, gap=1.14, cx=W // 2):
    if alpha <= 0 or not s: return y
    layer = Image.new("RGBA", fr.size, (0, 0, 0, 0)); d = ImageDraw.Draw(layer); lh = int(f.size * gap)
    lines = wrap(d, s, f, maxw)
    for k, ln in enumerate(lines): d.text((cx, y + dy + k * lh), ln, font=f, fill=fill + (int(255 * alpha),), anchor="ma")
    fr.alpha_composite(layer); return y + len(lines) * lh

def tag(s, f, bg, fg, padx=34, pady=16, r=None):             # a pill / sticker as its own image
    w, h = int(_M.textlength(s, font=f) + 2 * padx), int(f.size + 2 * pady)
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, w - 1, h - 1], h // 2 if r is None else r, fill=bg + (255,)); d.text((w / 2, h / 2), s, font=f, fill=fg + (255,), anchor="mm")
    return im

def background():
    bg = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(bg, "RGBA")
    for r, a in ((900, 26), (620, 30), (380, 34)): d.ellipse([W // 2 - r, -r - 120, W // 2 + r, r - 120], fill=ACCENT + (a // 3,))
    return bg.filter(ImageFilter.GaussianBlur(90)).convert("RGBA")

def confetti(fr, lt, cx, cy, seed=1):
    if lt < 0 or lt > 2.2: return
    rnd = random.Random(seed); d = ImageDraw.Draw(fr)
    for _ in range(70):
        ang, sp, col = rnd.uniform(-math.pi, 0), rnd.uniform(500, 1500), rnd.choice([ACCENT, GREEN, RED, (255, 205, 80), INK]); sz = rnd.randint(10, 22); rot = rnd.random()
        x = cx + math.cos(ang) * sp * lt * (1 - 0.25 * lt); y = cy + math.sin(ang) * sp * lt + 900 * lt * lt
        a = max(0, 1 - lt / 2.2); w2 = sz * abs(math.cos(lt * 9 + rot * 6)) + 3
        d.rectangle([x - w2 / 2, y - sz / 2, x + w2 / 2, y + sz / 2], fill=col + (int(255 * a),))


# ---------------------------------------------------------------- the mascot: "Boxy", a little parcel
_SPR = {}
def boxy(mouth=0, blink=False, look=0, mood="talk"):
    key = (mouth, blink, look, mood)
    if key in _SPR: return _SPR[key]
    S = 2; w, h = 360 * S, 380 * S; im = Image.new("RGBA", (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    TAN, DARK, TAPE, WHITE, PUPIL, PINK = (222, 178, 118), (120, 84, 44), (244, 226, 184), (255, 255, 255), (28, 28, 40), (240, 140, 130)
    def R(b): return [v * S for v in b]
    wow = mood == "wow"; up = 1 if mood in ("wow", "point") else 0
    # legs + arms behind the body
    for x in (130, 230): d.rounded_rectangle(R([x - 13, 300, x + 13, 356]), 12 * S, fill=DARK); d.ellipse(R([x - 24, 340, x + 24, 372]), fill=DARK)
    def arm(x0, x1, y1): d.line(R([x0, 215, x1, y1]), fill=DARK, width=16 * S); d.ellipse(R([x1 - 20, y1 - 20, x1 + 20, y1 + 20]), fill=TAN, outline=DARK, width=5 * S)
    arm(70, 22, 150 if wow else 262); arm(290, 338, 120 if up else 262)
    # body
    d.rounded_rectangle(R([50, 96, 310, 316]), 34 * S, fill=TAN, outline=DARK, width=7 * S)
    d.rectangle(R([158, 100, 202, 150]), fill=TAPE)                                          # tape
    d.polygon(R([50, 128, 96, 70, 180, 100, 180, 128]), fill=(206, 160, 100), outline=DARK); d.polygon(R([310, 128, 264, 70, 180, 100, 180, 128]), fill=(206, 160, 100), outline=DARK)   # open flaps
    d.line(R([50, 128, 310, 128]), fill=DARK, width=5 * S)
    # face
    for ex in (128, 232):
        if blink: d.arc(R([ex - 26, 190, ex + 26, 226]), 200, 340, fill=PUPIL, width=7 * S)
        else:
            rr = 33 if wow else 28
            d.ellipse(R([ex - rr, 208 - rr, ex + rr, 208 + rr]), fill=WHITE, outline=DARK, width=4 * S)
            px = ex + 9 * look; pr = 15 if wow else 13
            d.ellipse(R([px - pr, 210 - pr, px + pr, 210 + pr]), fill=PUPIL); d.ellipse(R([px + 2, 198, px + 10, 206]), fill=WHITE)
    for cx in (96, 264): d.ellipse(R([cx - 16, 240, cx + 16, 258]), fill=PINK + (150,))
    if wow: d.ellipse(R([160, 248, 200, 292]), fill=PUPIL)
    elif mouth == 0: d.arc(R([150, 236, 210, 276]), 20, 160, fill=PUPIL, width=7 * S)
    else:
        mh = 10 + 12 * mouth; d.rounded_rectangle(R([154, 254, 206, 254 + mh]), 14 * S, fill=PUPIL); d.ellipse(R([166, 254 + mh - 12, 194, 254 + mh + 2]), fill=(230, 90, 90))
    out = im.resize((w // S, h // S), Image.LANCZOS); _SPR[key] = out; return out


# ---------------------------------------------------------------- one generic, animated scene
# fields: dur, say, kicker, head, img, fill, grid=[imgs], big, para, sticker=(text, colour), number, count, sub, fx, mood, look, small_card
_SHADE = None
def shade():                                                 # darken top and bottom so text and the mascot stay readable
    global _SHADE
    if _SHADE is None:
        g = Image.new("L", (1, H)); px = g.load()
        for y in range(H): px[0, y] = int(205 * max(0, 1 - y / 620) ** 1.4) if y < 620 else (int(225 * ((y - 1180) / 520) ** 1.2) if 1180 < y < 1700 else (225 if y >= 1700 else 0))
        _SHADE = Image.new("RGBA", (W, H), BG + (255,)); _SHADE.putalpha(g.resize((W, H)))
    return _SHADE

YEL = (255, 214, 64)
def outlined(d, xy, txt, f, fill=INK, alpha=1.0, anchor="la", stroke=None):
    sw = stroke if stroke is not None else max(4, f.size // 11)
    d.text(xy, txt, font=f, fill=fill + (int(255 * alpha),), anchor=anchor, stroke_width=sw, stroke_fill=(8, 10, 18, int(255 * alpha)))

def rich_lines(txt, f, maxw):
    """Wrap 'plain *highlighted* plain' into lines of (word, highlighted) pairs."""
    words = []; hl = False
    for part in re.split(r"(\*)", txt):
        if part == "*": hl = not hl; continue
        words += [(w, hl) for w in part.split()]
    lines, cur = [], []
    for w in words:
        if cur and _M.textlength(" ".join(x for x, _ in cur + [w]), font=f) > maxw: lines.append(cur); cur = []
        cur.append(w)
    if cur: lines.append(cur)
    return lines

HOT = (225, 29, 72)
def draw_title(fr, txt, lt, cy):
    """Hook headline: black type on white rounded boxes (one per line), key words in red. Visible from the very first frame."""
    size = 92
    while size > 58 and len(rich_lines(txt, font(size, 900), W - 220)) > 3: size -= 4
    f = font(size, 900); lines = rich_lines(txt, f, W - 220); lh = int(size * 1.42); y0 = cy - lh * len(lines) // 2; S = 2; f2 = font(size * S, 900)
    for k, ln in enumerate(lines):
        t = lt - 0.07 * k; a = 1.0                              # all there on frame one (it is the cover frame)
        if a <= 0: continue
        key = ("ttl", txt, k, size)
        if key not in _SPR:
            tw = _M.textlength(" ".join(w for w, _ in ln), font=f); bw, bh = int(tw + 76), int(size * 1.36)
            layer = Image.new("RGBA", (bw * S, bh * S), (0, 0, 0, 0)); d = ImageDraw.Draw(layer)
            d.rounded_rectangle([0, 0, bw * S - 1, bh * S - 1], 26 * S, fill=(255, 255, 255, 255)); x = 38 * S
            for w, hl in ln:
                d.text((x, bh * S / 2), w, font=f2, fill=(HOT if hl else (12, 14, 22)) + (255,), anchor="lm"); x += _M.textlength(w + " ", font=f2)
            _SPR[key] = layer.resize((bw, bh), Image.LANCZOS)
        paste(fr, _SPR[key], W / 2, y0 + k * lh + lh / 2, 0.94 + 0.06 * pop(max(t, 0) + 0.12, 0.3), a, -1.5)

def draw_gfx(fr, g, lt, dur):
    """Animated explainer card in the top half: stat / ring / compare / chain (a list of rows)."""
    if not g: return
    a = ease((lt - 0.2) / 0.3) * (1 - ease((lt - (dur - 0.25)) / 0.25))
    if a <= 0: return
    S = 2; CW, CH = W - 120, 650
    L = Image.new("RGBA", (CW * S, CH * S), (0, 0, 0, 0)); d = ImageDraw.Draw(L)
    def R(x0, y0, x1, y1): return [x0 * S, y0 * S, x1 * S, y1 * S]
    def F(size, wt=800): return font(int(size) * S, wt)
    def T(x, y, txt, f, fill, anchor="mm", al=1.0): d.text((x * S, y * S), txt, font=f, fill=fill + (int(255 * al),), anchor=anchor)
    def fitw(txt, maxw, size, wt=900, lo=30):
        while size > lo and _M.textlength(txt, font=font(int(size), wt)) > maxw: size -= 4
        return size
    d.rounded_rectangle(R(0, 0, CW, CH), 60 * S, fill=(10, 13, 26, 238), outline=(255, 255, 255, 46), width=2 * S)
    t = g.get("t"); cx = CW / 2; SOFT = (198, 206, 226)
    def label(y, al=1.0):
        if not g.get("l"): return
        sz = fitw(g["l"], CW - 110, 50, 650, 30); T(cx, y, g["l"], F(sz, 650), SOFT, "mm", al)
    if t == "stat":
        sz = fitw(g["v"], CW - 130, 230, 900, 90); T(cx, 268, g["v"], F(sz, 900), YEL)
        w = (CW - 360) * ease((lt - 0.45) / 0.5) / 2
        if w > 4: d.rounded_rectangle(R(cx - w, 420, cx + w, 432), 6 * S, fill=YEL + (255,))
        label(505)
    elif t == "ring":
        p = g["pct"] * ease((lt - 0.35) / 0.9); r = 205; cy = 275; wd = 58
        box = R(cx - r, cy - r, cx + r, cy + r)
        d.arc(box, 0, 360, fill=(255, 255, 255, 34), width=wd * S)
        if p > 0.5:
            d.arc(box, -90, -90 + 3.6 * p, fill=YEL + (255,), width=wd * S)
            for ang in (-90, -90 + 3.6 * p):                   # round ends
                ex = cx + (r - wd / 2) * math.cos(math.radians(ang)); ey = cy + (r - wd / 2) * math.sin(math.radians(ang))
                d.ellipse(R(ex - wd / 2, ey - wd / 2, ex + wd / 2, ey + wd / 2), fill=YEL + (255,))
        T(cx, cy, "%d%%" % round(p), F(128, 900), INK); label(565)
    elif t == "compare":
        rows = (g["a"], g["b"]); mx = max(r[2] for r in rows); grow = ease((lt - 0.35) / 0.9)
        for i, (v, l, n) in enumerate(rows):
            y = 70 + i * 290; col = YEL if n == mx else (150, 170, 255)
            T(70, y + 28, l.upper(), F(38, 750), SOFT, "lm"); T(70, y + 118, v, F(128, 900), col, "lm")
            d.rounded_rectangle(R(70, y + 196, CW - 70, y + 236), 20 * S, fill=(255, 255, 255, 30))
            bw = max(40, (CW - 140) * n / mx * grow)
            d.rounded_rectangle(R(70, y + 196, 70 + bw, y + 236), 20 * S, fill=col + (255,))
    elif t == "chain":
        items = g["items"]; n = len(items); hi = g.get("hi", n - 1); top = 56; lab = 96 if g.get("l") else 0
        rh = (CH - top - 46 - lab) / n; sz = min(fitw(max(items, key=len), CW - 330, 96, 900, 40), int(rh * 0.56))
        for i, it in enumerate(items):
            ai = ease((lt - 0.3 - 0.4 * i) / 0.28)
            if ai <= 0: continue
            y0 = top + i * rh; on = i == hi; dx = 40 * (1 - ai)
            d.rounded_rectangle(R(56 + dx, y0, CW - 56 + dx, y0 + rh - 20), 32 * S, fill=(YEL + (int(255 * ai),)) if on else (255, 255, 255, int(30 * ai)))
            ink = (12, 14, 22) if on else INK; my = y0 + (rh - 20) / 2
            d.ellipse(R(84 + dx, my - 38, 160 + dx, my + 38), fill=((12, 14, 22) if on else (255, 255, 255)) + (int((255 if on else 40) * ai),))
            T(122 + dx, my, str(i + 1), F(46, 900), YEL if on else INK, "mm", ai)
            T(196 + dx, my, re.sub(r"^\d+\.\s*", "", it), F(sz, 900), ink, "lm", ai)
        label(CH - 74)
    L = L.resize((CW, CH), Image.LANCZOS)
    paste(fr, L, W / 2, 160 + CH / 2 + int(30 * (1 - a)), 0.94 + 0.06 * pop(lt - 0.2, 0.35), a)

def draw_sticker(fr, meta, tl):
    """Stickers on a shot: a red arrow that slides in pointing at the item, or a tick that draws itself on."""
    if meta["fx"] == "orbit":                                 # the red arrow travels round the item, always pointing at it
        a = ease((tl - 0.06) / 0.18)
        if a <= 0: return
        x0, y0, x1, y1 = meta["box"]; cx, cy = (x0 + x1) / 2, (y0 + y1) / 2; rx, ry = (x1 - x0) / 2 + 30, (y1 - y0) / 2 + 30
        ang = math.radians(-50 + 95 * (tl - 0.06))                          # starts top-right, moves clockwise
        tx, ty = cx + rx * math.cos(ang), cy + ry * math.sin(ang)            # tip, just outside the item
        dx, dy = cx - tx, (cy - ty) * 0.6; n = math.hypot(dx, dy) or 1.0; dx, dy = dx / n, dy / n   # points inward
        Ln = 230 + 60 * (1 - a); S = 2; pad = 320; L = Image.new("RGBA", (pad * 2 * S, pad * 2 * S), (0, 0, 0, 0)); d = ImageDraw.Draw(L)
        o = lambda px, py: ((px - tx + pad) * S, (py - ty + pad) * S)
        bx, by = tx - dx * Ln, ty - dy * Ln; hx, hy = tx - dx * 92, ty - dy * 92; nx, ny = -dy, dx
        for off, col in (((5, 9), (0, 0, 0, 70)), ((0, 0), (226, 28, 36, 255))):
            q = lambda px, py: (o(px, py)[0] + off[0] * S, o(px, py)[1] + off[1] * S)
            d.line([q(bx, by), q(hx, hy)], fill=col, width=38 * S)
            d.polygon([q(tx, ty), q(hx + nx * 62, hy + ny * 62), q(hx - nx * 62, hy - ny * 62)], fill=col)
        paste(fr, L.resize((pad * 2, pad * 2), Image.LANCZOS), tx, ty, 1.0, a)
    elif meta["fx"] == "arrow":
        if "arrow" not in _SPR:
            S = 2; L = Image.new("RGBA", (340 * S, 340 * S), (0, 0, 0, 0)); d = ImageDraw.Draw(L)   # points down-left, tip at (30, 310)
            d.line([(310 * S, 30 * S), (110 * S, 230 * S)], fill=(226, 28, 36, 255), width=40 * S)
            d.polygon([(30 * S, 310 * S), (190 * S, 262 * S), (78 * S, 150 * S)], fill=(226, 28, 36, 255))
            sh = Image.new("RGBA", L.size, (0, 0, 0, 0)); sh.paste((0, 0, 0, 110), (5 * S, 9 * S), L.getchannel("A")); sh = sh.filter(ImageFilter.GaussianBlur(7 * S)); sh.alpha_composite(L)
            _SPR["arrow"] = sh.resize((340, 340), Image.LANCZOS)
        a = ease((tl - 0.08) / 0.16)
        if a <= 0: return
        tx, ty = meta.get("target", (W * 0.62, H * 0.42)); off = 70 * (1 - a)
        paste(fr, _SPR["arrow"], tx + 140 + off, ty - 140 - off, 1.0, a)
    elif meta["fx"] == "tick":
        S = 2; cx, cy = 230, 240; L = Image.new("RGBA", (460 * S, 460 * S), (0, 0, 0, 0)); d = ImageDraw.Draw(L)
        r = max(2.0, 150 * pop(max(tl, 0.0), 0.22)); d.ellipse([(cx - r) * S, (cy - r) * S, (cx + r) * S, (cy + r) * S], fill=(150, 197, 224, 255))
        pts = [(cx - 95, cy - 5), (cx - 30, cy + 70), (cx + 135, cy - 175)]; pr = ease((tl - 0.12) / 0.3)
        if pr > 0:
            l1 = math.dist(pts[0], pts[1]); l2 = math.dist(pts[1], pts[2]); go = pr * (l1 + l2); line = [pts[0]]
            if go <= l1: t = go / l1; line.append((pts[0][0] + (pts[1][0] - pts[0][0]) * t, pts[0][1] + (pts[1][1] - pts[0][1]) * t))
            else: t = (go - l1) / l2; line += [pts[1], (pts[1][0] + (pts[2][0] - pts[1][0]) * t, pts[1][1] + (pts[2][1] - pts[1][1]) * t)]
            d.line([(x * S, y * S) for x, y in line], fill=(36, 48, 78, 255), width=46 * S, joint="curve")
            for x, y in (line[0], line[-1]): d.ellipse([(x - 23) * S, (y - 23) * S, (x + 23) * S, (y + 23) * S], fill=(36, 48, 78, 255))
        paste(fr, L.resize((460, 460), Image.LANCZOS), W / 2, 975, 1.0, 1.0)

PRESENTER_FIT = {"presenter.png": (0.84, "left"), "presenter2.png": (0.78, "center")}   # scale, anchor
_PM = {}
def place_presenter(f):
    sc, anc = PRESENTER_FIT.get(os.path.basename(PRESENTER), (0.8, "center")); w, h = int(W * sc), int(H * sc)
    im = f.resize((w, h), Image.BILINEAR)
    if (w, h, anc) not in _PM:                                # fade the sides that no longer touch the edge of the frame
        m = Image.new("L", (w, 1), 255); px = m.load(); r = 90
        for x in range(r):
            v = int(255 * ease(x / r))
            if anc != "left": px[x, 0] = v
            px[w - 1 - x, 0] = v
        _PM[(w, h, anc)] = m.resize((w, h))
    im.putalpha(ImageChops.multiply(im.getchannel("A"), _PM[(w, h, anc)]))
    return im, (0 if anc == "left" else (W - w) // 2, H - h)
_FLOOR = None
def floor_shade():                                            # darken the bottom so captions read over the presenter's chest
    global _FLOOR
    if _FLOOR is None:
        g = Image.new("L", (1, H)); px = g.load()
        for y in range(H): px[0, y] = int(215 * ease((y - 1240) / 560)) if y > 1240 else 0
        _FLOOR = Image.new("RGBA", (W, H), (6, 8, 16, 255)); _FLOOR.putalpha(g.resize((W, H)))
    return _FLOOR

CUT = 2.6                                                    # seconds per shot
LASTF = {}                                                    # last frame of the previous line, for dissolves
XF = 0.28
def draw_bg(fr, s, lt, dur):
    shots = s["bg"]; nseg = max(1, min(len(shots), int(round(dur / s.get("cut", CUT))))); seg = dur / nseg      # never more cuts than different clips
    hard = s.get("word")                                      # "style" videos: plain hard cuts, clean footage
    k = min(nseg - 1, int(lt / seg)); st = (lt - k * seg) / seg; sh = shots[k % len(shots)]; kind, m, credit = sh[:3]; meta = sh[3] if len(sh) > 3 else {}
    s["_quiet"] = bool(meta.get("overlay") and not meta.get("blur"))          # product on paper: no caption over it
    zoom = 1.0 if hard else (1.0 + 0.07 * st if k % 2 == 0 else 1.07 - 0.07 * st)   # style videos: footage plays as shot, no zooming
    if kind == "video":
        clips = s.setdefault("_clips", {})
        if (id(m), k) not in clips: clips[(id(m), k)] = Clip(m, ss=meta.get("ss", 0.0))
        f = None if (meta.get("freeze") and s.get("_frozen") == k) else clips[(id(m), k)].frame()      # a frozen shot holds its first frame
        if f is not None:
            s["_last"] = f
            if meta.get("freeze"): s["_frozen"] = k
        base = s.get("_last")
    elif meta.get("site"): draw_site(fr, lt - k * seg); base = None
    elif meta.get("overlay"):                                 # a held product shot: the paper moves, the item does not
        if not meta.get("blur"): fr.paste(paper(int(lt * 7)), (0, 0))
        a = ease((lt - k * seg) / 0.34)                      # the item glides up into place
        if a >= 1: fr.alpha_composite(m)
        else: paste(fr, m, W / 2, H / 2 + int(46 * (1 - a)), 1.0, a)
        base = None
    elif meta.get("paper"): fr.paste(paper(int(lt * 7)), (0, 0)); base = None
    else:
        key = ("bg", id(m))
        if key not in _SPR: _SPR[key] = cover(m, W, H).convert("RGBA")
        base = _SPR[key]
    if base is not None:
        cw, ch = int(W / zoom), int(H / zoom); ox = [0.5, 0.2, 0.8, 0.5][k % 4]; oy = [0.35, 0.5, 0.45, 0.6][k % 4]
        x, y = int((W - cw) * ox), int((H - ch) * oy)
        if k > 0 and st < 0.12 and not hard: x += int(18 * math.sin(lt * 140) * (1 - st / 0.12))    # tiny shake on the cut
        x = max(0, min(W - cw, x))
        fr.paste(base.crop((x, y, x + cw, y + ch)).resize((W, H), Image.BILINEAR), (0, 0))
    if not hard: fr.alpha_composite(shade())
    if hard and k == 0 and lt < XF and LASTF.get("im") is not None and (meta.get("overlay") or meta.get("site") or LASTF.get("soft")):
        fr.paste(Image.blend(LASTF["im"], fr, ease(lt / XF)), (0, 0))                     # dissolve instead of a hard cut
    if meta.get("fx"): draw_sticker(fr, meta, lt - k * seg)
    if s.get("fg"):                                            # the presenter, cut out, in front of the footage
        if "_fg" not in s: s["_fg"] = Clip(s["fg"], key=True)
        f = s["_fg"].frame()
        if f is not None: s["_fgl"] = f
        if s.get("_fgl") is not None:
            im, pos = place_presenter(s["_fgl"]); fr.alpha_composite(im, pos); fr.alpha_composite(floor_shade())
    if k > 0 and st < 0.09 and not hard:                      # white flash on the cut
        fr.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(150 * (1 - st / 0.09)))))
    if credit and not hard: ImageDraw.Draw(fr).text((W - 30, 1712), credit[:70], font=font(22, 500), fill=(200, 208, 225, 200), anchor="ra")

def draw_scene(fr, s, lt, dur, FT):
    a = ease(lt / 0.35)
    if s.get("bg"):
        draw_bg(fr, s, lt, dur)
        if s.get("label"): draw_title(fr, s["label"], lt, 330)
        draw_gfx(fr, s.get("gfx"), lt, dur)
        return
    if s.get("kicker"): paste(fr, tag(s["kicker"].upper(), FT["kick"], s.get("kcol", ACCENT), BG), W / 2, 300, pop(lt), a)
    hy = 350
    if s.get("head"):
        f = fit(s["head"], W - 120, 2, 92); n = len(wrap(_M, s["head"], f, W - 120))
        hy = text(fr, s["head"], f, 356 + (0 if n > 1 else 34), fill=s.get("hcol", INK), alpha=a, dy=int(-26 * (1 - a)), maxw=W - 120)
    cy = 960; size = s.get("small_card") or 700
    sc = pop(lt - 0.08, 0.42) * (1 + 0.035 * lt / dur)
    if s.get("img") is not None:
        key = ("card", id(s["img"]), size, bool(s.get("fill")))
        if key not in _SPR: _SPR[key] = rounded(cover(s["img"], size, size) if s.get("fill") else contain_on_card(s["img"], size, size, int(size * 0.07)), 54)
        paste(fr, _SPR[key], W / 2, cy, sc, ease((lt - 0.05) / 0.25))
    if s.get("grid"):
        g = s["grid"][:4]; cols = 2 if len(g) > 1 else 1; tw = 340 if cols == 2 else 700; th = 340 if len(g) > 2 else (700 if len(g) < 2 else 700)
        if len(g) == 2: tw, th = 340, 700
        for k, q in enumerate(g):
            key = ("tile", id(q), tw, th)
            if key not in _SPR: _SPR[key] = rounded(cover(q, tw, th), 40)
            x = W / 2 + ((k % cols) - (cols - 1) / 2) * (tw + 20); y = cy + ((k // cols) - ((len(g) > 2) * 0.5)) * (th + 20)
            paste(fr, _SPR[key], x, y, pop(lt - 0.12 - 0.14 * k, 0.4), ease((lt - 0.1 - 0.14 * k) / 0.2), [-3, 2.5, 2, -2.5][k] if len(g) > 1 else 0)
    if s.get("big"):
        f = fit(s["big"], W - 160, 2, 230, 900, 90); n = len(wrap(_M, s["big"], f, W - 160))
        text(fr, s["big"], f, cy - int(f.size * 1.14 * n / 2) - 10, fill=s.get("bcol", ACCENT), alpha=a, maxw=W - 160, dy=int(40 * (1 - pop(lt))))
    if s.get("para"):
        f = fit(s["para"], W - 180, 6, 70, 600, 44); n = len(wrap(_M, s["para"], f, W - 180))
        text(fr, s["para"], f, cy - int(f.size * 1.3 * n / 2), alpha=ease((lt - 0.25) / 0.4), maxw=W - 180, gap=1.3)
    if s.get("count"):                                        # 3-2-1 over the product
        n = 3 - int(lt / (dur / 3)); f2 = (lt % (dur / 3)) / (dur / 3)
        d = ImageDraw.Draw(fr); d.ellipse([W / 2 - 190, cy - 190, W / 2 + 190, cy + 190], fill=BG + (215,))
        ff = font(int(300 * (1.3 - 0.3 * ease(f2 / 0.3))), 900); d.text((W / 2, cy), str(max(1, n)), font=ff, fill=ACCENT + (255,), anchor="mm")
    if s.get("number"):
        paste(fr, tag("#%d" % s["number"], font(120, 900), GREEN if s["number"] == 1 else ACCENT, BG, 40, 14, 44), W / 2 - size / 2 + 60, cy - size / 2 + 30, pop(lt - 0.15), ease((lt - 0.15) / 0.2), 8)
    if s.get("sticker"):
        st, col = s["sticker"]; t0 = lt - 0.45
        paste(fr, tag(st, font(150, 900), col, BG if col != RED else (255, 255, 255), 44, 14, 50), W / 2 + size / 2 - 120, cy + size / 2 - 40, pop(t0, 0.45), ease(t0 / 0.15), -8 + 30 * (1 - ease(t0 / 0.45)))
    if s.get("sub"):                                          # one line: under the headline when the host is centre stage, else under the card
        f = fit(s["sub"], W - 140, 1, 56, 650, 34)
        text(fr, s["sub"], f, (hy + 26) if s.get("host_big") else 1340, fill=s.get("scol", MUTED), alpha=ease((lt - 0.3) / 0.4))
    if s.get("fx") == "confetti": confetti(fr, lt - 0.45, W / 2, cy - 60, seed=len(s.get("head") or "x"))


def captions(s):                                             # [(word, start, end)] for the speech bubble
    if s.get("words"): return s["words"]
    ws = (s.get("say") or "").split()
    if not ws: return []
    span = s["dur"] * 0.82; tot = sum(len(w) + 2 for w in ws); t = 0.12; out = []
    for w in ws:
        d = span * (len(w) + 2) / tot; out.append((w, t, t + d)); t += d
    return out


def draw_news_caption(fr, s, lt):
    ws = captions(s); cur = next((k for k, (w, a, b) in enumerate(ws) if a <= lt < b), None)
    if not ws or lt < ws[0][1] - 0.05: return
    k0 = cur if cur is not None else max((k for k, (w, a, b) in enumerate(ws) if b <= lt), default=0); g0 = (k0 // 3) * 3; grp = ws[g0:g0 + 3]
    line = " ".join(w for w, _, _ in grp); size = 100
    while size > 60 and _M.textlength(line, font=font(size, 900)) > W - 120: size -= 6
    f = font(size, 900); tw = _M.textlength(line, font=f); y = 1420 if s.get("fg") else 1060   # over the presenter's chest, or just below the centre
    t0 = grp[0][1]; sc = 0.9 + 0.1 * pop(lt - t0, 0.22)                                  # each new group pops in
    layer = Image.new("RGBA", (W, int(size * 1.6)), (0, 0, 0, 0)); d = ImageDraw.Draw(layer); x = W / 2 - tw / 2; idx = g0
    for w in line.split():
        outlined(d, (x, int(size * 0.2)), w, f, YEL if idx == cur else INK); x += _M.textlength(w + " ", font=f); idx += 1
    paste(fr, layer, W / 2, y, sc, 1.0)

def word_groups(ws):                                          # one word at a time; tiny words ride along with the next one
    out, k = [], 0
    while k < len(ws):
        w, a, b = ws[k]
        if k + 1 < len(ws) and len(w.strip(".,!?")) <= 3 and not w.rstrip().endswith((".", ",", "!", "?")) and len(w) + len(ws[k + 1][0]) <= 14:
            out.append((w + " " + ws[k + 1][0], a, ws[k + 1][2])); k += 2
        else: out.append((w, a, b)); k += 1
    return out

CAP_YEL = (243, 199, 18)
def draw_word_caption(fr, s, lt):
    """One or two words, caps, yellow Montserrat with a soft shadow, dead centre."""
    if "_wg" not in s: s["_wg"] = word_groups(captions(s))
    g = next(((w, a, b) for w, a, b in s["_wg"] if a <= lt < b), None)
    if not g: return
    txt = g[0].upper().strip(",")
    key = ("wc", txt)
    if key not in _SPR:
        size = 88
        while size > 52 and _M.textlength(txt, font=mfont(size)) > W - 180: size -= 4
        f = mfont(size); tw = int(_M.textlength(txt, font=f)); pad = 50
        sh = Image.new("RGBA", (tw + 2 * pad, int(size * 1.5) + 2 * pad), (0, 0, 0, 0)); ImageDraw.Draw(sh).text((pad + 2, pad + 5), txt, font=f, fill=(0, 0, 0, 215))
        sh = sh.filter(ImageFilter.GaussianBlur(7)); sh.alpha_composite(sh)                                  # denser soft shadow
        ImageDraw.Draw(sh).text((pad, pad), txt, font=f, fill=CAP_YEL + (255,))
        _SPR[key] = sh
    paste(fr, _SPR[key], W / 2, 975, 1.0, 1.0)

def draw_host(fr, s, lt, t_abs, FT):
    if s.get("nocap") or s.get("_quiet"): return
    if s.get("word"): return draw_word_caption(fr, s, lt)
    if s.get("news"): return draw_news_caption(fr, s, lt)
    ws = captions(s); cur = next((k for k, (w, a, b) in enumerate(ws) if a <= lt < b), None)
    speaking = cur is not None
    mouth = (1 + int(2 * abs(math.sin(lt * 17)))) if speaking else 0
    blink = (t_abs % 3.1) > 2.96
    mood = s.get("mood", "talk"); jump = 0
    if mood == "wow": jump = -int(46 * abs(math.sin(min(lt, 1.2) * 7)) * max(0, 1 - lt / 1.2))
    bob = int(7 * math.sin(t_abs * 3.2))
    spr = boxy(mouth, blink, s.get("look", 0), mood)
    big = s.get("host_big")
    if big: paste(fr, spr, W / 2, 1000 + 2 * bob + 2 * jump, 2.0 * pop(lt, 0.45), 1.0, 3 * math.sin(t_abs * 2.1))
    else: paste(fr, spr, 200, 1560 + bob + jump, 1.0, 1.0, 2.5 * math.sin(t_abs * 2.1))
    if not ws: return
    # speech bubble with 3-4 words at a time, current word highlighted
    k0 = (cur if cur is not None else max((k for k, (w, a, b) in enumerate(ws) if b <= lt), default=0)); g0 = (k0 // 4) * 4; grp = ws[g0:g0 + 4]
    if lt < ws[0][1] - 0.05: return
    d = ImageDraw.Draw(fr)
    if big:
        bx0, by0, bx1, by1 = 110, 1440, 970, 1680
        d.rounded_rectangle([bx0, by0, bx1, by1], 46, fill=INK + (255,)); d.polygon([(W / 2 - 40, by0 + 6), (W / 2, by0 - 46), (W / 2 + 40, by0 + 6)], fill=INK + (255,))
    else:
        bx0, by0, bx1, by1 = 400, 1440, 1030, 1680
        d.rounded_rectangle([bx0, by0, bx1, by1], 46, fill=INK + (255,)); d.polygon([(bx0 + 6, 1560), (bx0 - 44, 1590), (bx0 + 6, 1620)], fill=INK + (255,))
    f = fit(" ".join(w for w, _, _ in grp), bx1 - bx0 - 70, 2, 74, 800, 44); lines = wrap(d, " ".join(w for w, _, _ in grp), f, bx1 - bx0 - 70)
    lh = int(f.size * 1.12); y = (by0 + by1) / 2 - lh * len(lines) / 2; idx = g0
    for ln in lines:
        x = (bx0 + bx1) / 2 - d.textlength(ln, font=f) / 2
        for w in ln.split():
            d.text((x, y), w, font=f, fill=(RED if idx == cur else BG) + (255,)); x += d.textlength(w + " ", font=f); idx += 1
        y += lh


def fonts():
    logo = Image.open(os.path.join(ROOT, "logo-wordmark.png")).convert("RGBA")
    return dict(kick=font(40, 800), logo=logo.resize((240, int(240 * logo.size[1] / logo.size[0])), Image.LANCZOS),
                bug=logo.resize((170, int(170 * logo.size[1] / logo.size[0])), Image.LANCZOS))
def usd(p): return "$%d" % round(float(p.get("usd") or 0))
def dollars(p): return "%d dollars" % round(float(p.get("usd") or 0))
def plat(p): return PLAT.get(p.get("platform"), "")
def short_title(p, n=40):
    t = p.get("title") or "Top find"
    return t if len(t) <= n else t[:n - 1].rsplit(" ", 1)[0] + "…"

SIGNOFF = "Join the China side. Link in bio!"
def cta(hero, sub="puroclassico.com  ·  9,000+ finds", say=None, kicker="Link in bio"):
    say = (say + " " if say else "") + SIGNOFF
    return dict(dur=3.4, say=say, kicker=kicker, kcol=RED, head="Join the China side", hcol=ACCENT, sub=sub, scol=INK, mood="wow", host_big=True, last=True)


# ---------------------------------------------------------------- formats (each returns scenes, ids, caption, product[, state])
def one(D, a):
    return (D.top(1, False, lambda i, _: i == a.id) if a.id else D.top(1))[0]

def fmt_spotlight(D, a):
    pid, p, v = one(D, a); hero = load_img(img_url(p)); qcs = qc_photos(pid, p); v7 = int(v[2] or 0)
    sc = [dict(dur=3.0, say="Everyone is looking at this one right now.", kicker=("%d views this week" % v7) if v7 >= 5 else "Trending", head="The most viewed find this week", img=hero, mood="wow"),
          dict(dur=3.6, say="%s. Only %s!" % (short_title(p, 60), dollars(p)), head=short_title(p), img=hero, sticker=(usd(p), GREEN), sub=("Listed on " + plat(p)) if plat(p) else "", fx="confetti", look=1)]
    if qcs: sc.append(dict(dur=3.6, say="And these are real QC photos from the warehouse.", kicker="Real QC photos", head="Check it before it ships", grid=qcs, look=1))
    sc.append(cta(hero))
    return sc, [pid], "%s — %s%s. Find it on puroclassico.com (link in bio) 🔗" % (p.get("title"), usd(p), " with real QC photos" if qcs else ""), p

def fmt_top5(D, a):
    items = D.top(5, skip_done=False); imgs = [load_img(img_url(p)) for _, p, _ in items]
    items = [it for it, im in zip(items, imgs) if im is not None]; imgs = [im for im in imgs if im is not None]
    sc = [dict(dur=3.0, say="The five most viewed finds this week. Wait for number one!", kicker="This week", head="Most viewed finds", big="TOP 5", mood="wow")]
    for k in range(len(items) - 1, -1, -1):
        p = items[k][1]
        sc.append(dict(dur=2.6 if k else 3.4, say=("Number %d! " % (k + 1)) + "%s, %s." % (short_title(p, 46), dollars(p)), head=short_title(p, 34), img=imgs[k], number=k + 1,
                       sticker=(usd(p), GREEN if k == 0 else ACCENT), fx="confetti" if k == 0 else None, mood="wow" if k == 0 else "talk", look=1))
    sc.append(cta(imgs[0], say="Which one would you pick? They're all on puro classico dot com."))
    return sc, [], "Top 5 most viewed finds this week 👀 Which one would you pick? All on puroclassico.com (link in bio)", items[0][1]

def fmt_guess(D, a):
    pid, p, v = one(D, a); hero = load_img(img_url(p)); qcs = qc_photos(pid, p, 4); b = p.get("brand") or "find"
    sc = [dict(dur=3.0, say="Okay, guess the price of this %s." % b, kicker="Game time", head="Guess the price", img=hero, sub=short_title(p), scol=INK, look=1),
          dict(dur=3.0, say="Three... two... one...", head="Guess the price", img=hero, count=True, look=1),
          dict(dur=3.4, say="%s! Were you close?" % dollars(p).capitalize(), kicker="It's only", kcol=GREEN, head=short_title(p), img=hero, sticker=(usd(p), GREEN), fx="confetti", mood="wow")]
    if len(qcs) >= 2: sc.append(dict(dur=3.2, say="And yes, it has real QC photos.", kicker="Real QC photos", head="Looks like this in hand", grid=qcs, look=1))
    sc.append(cta(hero, say="Comment your guess! The link is in the bio.", kicker="Comment your guess"))
    return sc, [pid], "Guess the price before the reveal 👀 %s — were you close? More on puroclassico.com (link in bio)" % p.get("title"), p

def fmt_qc(D, a):
    ms = models(); pick = None
    for pid, p, v in D.top(40, skip_done=not a.id, where=(lambda i, _: i == a.id) if a.id else None):
        t = (p.get("brand") or "") + " " + (p.get("title") or ""); m = next((m for m in ms if m[2].search(t) and len(m[3]) >= 3), None)
        if not m: continue
        qcs = qc_photos(pid, p, 4)
        if len(qcs) >= 3: pick = (pid, p, m, qcs); break
    if not pick: return None
    pid, p, m, qcs = pick; hero = load_img(img_url(p)); name = m[1]
    sc = [dict(dur=3.2, say="Buying %s? Check these three things first." % name, kicker="QC guide", head="How to QC " + name, img=hero, sub="3 checks before you ship", mood="point", look=1)]
    for k, tip in enumerate(m[3][:3]):
        tip = tip[0].upper() + tip[1:]
        sc.append(dict(dur=3.4, say="%s. %s." % (["One", "Two", "Three"][k], tip), kicker="Check %d of 3" % (k + 1), head=tip, img=qcs[k % len(qcs)], fill=True, look=1))
    sc.append(cta(hero, say="Save this for later. The full guide is on puro classico dot com.", kicker="Save this"))
    return sc, [pid], "How to QC %s before you ship: 3 things to check ✅ Save this. Full guide on puroclassico.com (link in bio)" % name, p

def fmt_term(D, a):
    n = int(D.state.get("term", 0)) % len(TERMS); term, stands, meaning, ex = TERMS[n]
    pid, p, v = D.top(1, skip_done=False)[0]; hero = load_img(img_url(p)); spoken = term.replace(" / ", " and ")
    sc = [dict(dur=3.0, say="What does %s actually mean?" % spoken, kicker="Rep terms in 10 seconds", head="What does this mean?", big=term, mood="wow"),
          dict(dur=5.6, say="%s. %s" % (stands, meaning), kicker=stands, head=term, hcol=ACCENT, para=meaning),
          dict(dur=3.0, say=ex, kicker="Remember", kcol=GREEN, head=ex, img=hero, mood="point", look=1),
          cta(hero, say="More terms explained on puro classico dot com.", kicker="Save this")]
    return sc, [], "What does %s mean? Rep terms in 10 seconds 📚 Save this for later. Full glossary on puroclassico.com (link in bio)" % term, p, {"term": n + 1}

def fmt_order(D, a):
    pid, p, v = D.top(1, skip_done=False)[0]; hero = load_img(img_url(p)); qcs = qc_photos(pid, p, 1)
    sc = [dict(dur=3.0, say="Never ordered from China? It's four steps.", kicker="Beginner guide", head="How to order in 4 steps", img=hero, sub="using this %s find" % usd(p), mood="wow")]
    for k, (h1, sub) in enumerate(STEPS):
        sc.append(dict(dur=3.2, say="%s. %s. %s" % (["One", "Two", "Three", "Four"][k], h1, sub), kicker="Step %d of 4" % (k + 1), head=h1, img=(qcs[0] if k == 2 and qcs else hero), fill=(k == 2 and bool(qcs)), sub=sub, look=1,
                       mood="point" if k == 1 else "talk"))
    sc.append(cta(hero, say="The full video guide is on puro classico dot com. Link in bio!", kicker="Save this"))
    return sc, [], "How to order from China in 4 steps 📦 Save this for your first haul. Full video guide on puroclassico.com (link in bio)", p

def fmt_relatable(D, a):
    n = int(D.state.get("rel", 0)) % len(RELATABLE); setup, punch, t1, t2 = RELATABLE[n]
    pid, p, v = one(D, a); hero = load_img(img_url(p))
    f = lambda x: x.format(usd=dollars(p), price=usd(p))
    uses_price = "{" in punch or "{" in t2
    sc = [dict(dur=3.4, say=f(setup), head=f(t1), host_big=True, mood="talk"),
          dict(dur=3.4, say=f(punch), head=f(t2), hcol=GREEN, img=hero, sticker=(usd(p), GREEN) if uses_price else None, sub=short_title(p), scol=INK, fx="confetti", mood="wow", look=1),
          cta(hero)]
    return sc, [pid], "%s 😅 %s — %s on puroclassico.com. Join the China side (link in bio)" % (f(t1).strip('"'), p.get("title"), usd(p)), p, {"rel": n + 1}

def fmt_story(D, a):
    try: stories = json.load(open(os.path.join(ROOT, "scripts", "stories.json"), encoding="utf-8"))
    except Exception as e: print("no stories.json:", e); return None
    pool = [x for x in stories if x.get("approved")] or stories      # only stories the owner approved go out
    n = int(D.state.get("story", 0)) % len(pool); st = next((x for x in stories if x["id"] == a.id), pool[n]) if a.id else pool[n]
    pid, p, v = D.top(1, skip_done=False)[0]; hero = load_img(img_url(p))
    beats = st["beats"][:4]; th = st.get("themes") or []
    rot = lambda k: th[k % len(th):] + th[:k % len(th)] if th else ()
    hp = st.get("clips") or {}                                                        # hand-picked clips first, search only as a fallback
    shots = [picked(b.get("clips")) or media_many(b["show"], 3, rot(k)) for k, b in enumerate(beats)]
    intro = picked(hp.get("intro")) or media_many(th[:2] or beats[0]["show"], 2, th); outro = picked(hp.get("outro")) or media_many(th[-2:] or beats[-1]["show"], 2, th)
    if not any(shots): return None
    spare = [m for ms in shots for m in ms[2:]]
    use_presenter(a.presenter - 1 if a.presenter else (pool.index(st) if st in pool else n))
    sc = [dict(dur=3.4, say=st["hook"], label=st.get("label") or st["hook"], bg=intro or spare or shots[0], news=True, presenter=True)]
    for k, b in enumerate(beats):
        if shots[k]: sc.append(dict(dur=3.6, say=b["say"], bg=shots[k][:2] if len(shots[k]) > 2 and spare else shots[k], news=True, gfx=b.get("gfx")))
    sc.append(dict(dur=3.6, say="Want to see what's on the China side? The spreadsheet is in the bio. Join the China side!", bg=outro or spare or shots[-1], news=True, last=True, presenter=True))
    cap = "%s 👀 Follow for more. The spreadsheet is in the bio — join the China side." % st["hook"].strip()
    return sc, [], cap, p, {"story": n + 1}

def cutout(im):
    """Remove a plain light background (flood fill from the edges). Returns RGBA, or None if the photo has no plain background."""
    im = im.convert("RGB"); w, h = im.size
    pts = [(1, 1), (w - 2, 1), (1, h - 2), (w - 2, h - 2), (w // 2, 1), (w // 2, h - 2), (1, h // 2), (w - 2, h // 2)]
    if sum(1 for x, y in pts[:4] if min(im.getpixel((x, y))) > 205) < 3: return None
    work = im.copy(); key = (255, 0, 254)
    for x, y in pts:
        if min(work.getpixel((x, y))) > 205 and work.getpixel((x, y)) != key: ImageDraw.floodfill(work, (x, y), key, thresh=26)
    r, g, b = work.split()
    bgm = ImageChops.multiply(ImageChops.multiply(r.point(lambda v: 255 if v == 255 else 0), g.point(lambda v: 255 if v == 0 else 0)), b.point(lambda v: 255 if v == 254 else 0))
    a = ImageOps.invert(bgm).filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(1.2))
    if a.histogram()[255] < w * h * 0.04: return None
    out = im.convert("RGBA"); out.putalpha(a); return out.crop(a.getbbox())

_BACK = {}
def paper(v):
    """Crumpled-paper backdrop, variant v (0-2); cycling the variants gives a stop-motion paper feel."""
    key = ("paper", v % 3)
    if key not in _BACK:
        rnd = random.Random(7 + 11 * (v % 3)); acc = Image.new("L", (W, H), 128)
        for sc, amt in ((14, 0.55), (36, 0.3), (90, 0.15)):
            small = Image.new("L", (W // sc + 2, H // sc + 2)); small.putdata([rnd.randint(0, 255) for _ in range(small.size[0] * small.size[1])])
            acc = Image.blend(acc, small.resize((W, H), Image.BICUBIC), amt)
        relief = acc.filter(ImageFilter.EMBOSS).filter(ImageFilter.GaussianBlur(1.5)).point(lambda x: int(232 + (x - 128) * 0.7))
        _BACK[key] = Image.merge("RGB", (relief, relief, relief.point(lambda x: min(255, x + 3)))).convert("RGBA")
    return _BACK[key]

def backdrop(kind):
    """Studio backdrops for product shots: 'paper' (crumpled white paper) or 'soft' (light grey gradient)."""
    if kind not in _BACK:
        if kind == "paper":
            rnd = random.Random(7); acc = Image.new("L", (W, H), 128)
            for sc, amt in ((14, 0.55), (36, 0.3), (90, 0.15)):
                small = Image.new("L", (W // sc + 2, H // sc + 2)); small.putdata([rnd.randint(0, 255) for _ in range(small.size[0] * small.size[1])])
                acc = Image.blend(acc, small.resize((W, H), Image.BICUBIC), amt)
            relief = acc.filter(ImageFilter.EMBOSS).filter(ImageFilter.GaussianBlur(1.5)).point(lambda v: int(232 + (v - 128) * 0.55))
            _BACK[kind] = Image.merge("RGB", (relief, relief, relief.point(lambda v: min(255, v + 3))))
        else:
            g = Image.new("L", (1, H)); px = g.load()
            for y in range(H): px[0, y] = int(246 - 22 * abs(y / H - 0.42) ** 1.3 * 2)
            g = g.resize((W, H)); _BACK[kind] = Image.merge("RGB", (g, g, g))
    return _BACK[kind]

def clip_frame(shot, t=1.0):
    """One still from a shot (video or photo), cover-fitted to the frame."""
    kind, m = shot[0], shot[1]
    if kind != "video": return cover(m.convert("RGB"), W, H)
    try:
        raw = subprocess.run([FF, "-loglevel", "error", "-ss", str(t), "-i", m, "-frames:v", "1", "-vf", "scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d" % (W, H, W, H), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE).stdout
        return Image.frombuffer("RGB", (W, H), raw[:W * H * 3]) if len(raw) >= W * H * 3 else None
    except Exception: return None

_PSHOT = [0]
def product_shot(p, over=None, brand=False, arrow=False):
    """A spreadsheet product photo as a studio shot: the item cut out, with a soft shadow, held still on moving paper
    (or over a blurred outfit clip), the brand name above it and a red arrow that travels round it."""
    im = load_img(img_url(p))
    if im is None: return None
    co = cutout(im); base = clip_frame(over) if over else None
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    if base is not None and co is not None:
        lay = ImageEnhance.Brightness(base.resize((W // 6, H // 6)).filter(ImageFilter.GaussianBlur(5)).resize((W, H), Image.BICUBIC)).enhance(0.92).convert("RGBA")
    if co is None:                                            # busy photo: show it as a rounded card instead
        card = rounded(cover(im.convert("RGB"), 900, 900), 46); lay.alpha_composite(card, ((W - 900) // 2, (H - 900) // 2 - 40))
        return ("photo", lay, "", {"ding": True, "overlay": True})
    co = ImageOps.contain(co, (W - 400, 640), Image.LANCZOS); x, y = (W - co.width) // 2, (H - co.height) // 2 - 30
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0)); sh.paste((20, 22, 30, 120), (x + 6, y + 26), co.getchannel("A")); lay.alpha_composite(sh.filter(ImageFilter.GaussianBlur(24)))
    lay.alpha_composite(co, (x, y))
    if (brand or base is not None) and p.get("brand"):         # the brand name in plain type above the item
        txt = p["brand"].upper(); size = 82
        while size > 44 and _M.textlength(txt, font=mfont(size, 900)) > W - 200: size -= 4
        f = mfont(size, 900); by = max(190, y - 250)             # clear of the arrow's path
        if base is not None:
            t2 = Image.new("RGBA", (W, H), (0, 0, 0, 0)); ImageDraw.Draw(t2).text((W / 2 + 2, by + 4), txt, font=f, fill=(0, 0, 0, 170), anchor="ms"); lay.alpha_composite(t2.filter(ImageFilter.GaussianBlur(6)))
            ImageDraw.Draw(lay).text((W / 2, by), txt, font=f, fill=(255, 255, 255, 255), anchor="ms")
        else: ImageDraw.Draw(lay).text((W / 2, by), txt, font=f, fill=(18, 20, 28, 255), anchor="ms")
    meta = {"ding": True, "overlay": True, "blur": base is not None}
    if arrow: meta.update(fx="orbit", box=(x, y, x + co.width, y + co.height))
    return ("photo", lay, "", meta)

def best_item(D, brand, cat=None, look=8):
    """The best single photo of a brand's items: among its most-viewed, the cleanest, largest cut-out (side-on for shoes)."""
    best = None; seen = 0
    for i, v in D.ranked:
        p = D.products[i]
        if (p.get("brand") or "").lower() != brand.lower() or (cat and (p.get("cat") or "").lower() != cat.lower()): continue
        seen += 1; im = load_img(img_url(p)); co = cutout(im) if im is not None else None
        if co is not None:
            ar = co.width / co.height; fill = co.getchannel("A").histogram()[255] / float(co.width * co.height)
            score = min(co.width, 900) / 900.0 + 0.6 * fill + (0.5 if (cat or "").lower() == "shoes" and 1.5 < ar < 3.2 else 0) - 0.04 * seen
            if best is None or score > best[0]: best = (score, i, p)
        if seen >= look: break
    return best

def board_shot(D, brand, cat=None):
    """A brand board: the brand name on top and one good photo of its item, big, with the red ring and arrow."""
    b = best_item(D, brand, cat)
    if not b: return None, []
    return product_shot(b[2], None, True, True), [b[1]]

_SITE = {}
def site_shot():
    path = os.path.join(ROOT, "scripts", "site.png")
    return ("photo", Image.new("RGB", (8, 8)), "", {"site": True, "ding": True}) if os.path.exists(path) else None

def draw_site(fr, tl):
    """End screen: deep navy with a soft glow, the spreadsheet on a phone sliding up, and the address above it."""
    if "bg" not in _SITE:
        g = Image.new("L", (1, H)); px = g.load()
        for y in range(H): px[0, y] = int(255 * (y / H) ** 1.2)
        bg = Image.composite(Image.new("RGB", (W, H), (6, 9, 20)), Image.new("RGB", (W, H), (20, 30, 62)), g.resize((W, H))).convert("RGBA")
        glow = Image.new("RGBA", (W, H), (0, 0, 0, 0)); ImageDraw.Draw(glow).ellipse([W // 2 - 520, 620, W // 2 + 520, 1660], fill=(92, 124, 220, 90)); bg.alpha_composite(glow.filter(ImageFilter.GaussianBlur(170)))
        shot = Image.open(os.path.join(ROOT, "scripts", "site.png")).convert("RGB"); w = 610; shot = shot.resize((w, int(shot.height * w / shot.width)), Image.LANCZOS).crop((0, 0, w, 1240))
        ph = Image.new("RGBA", (w + 36, 1240 + 36), (0, 0, 0, 0)); d = ImageDraw.Draw(ph)
        d.rounded_rectangle([0, 0, w + 35, 1240 + 35], 76, fill=(10, 12, 20, 255), outline=(70, 80, 110, 255), width=3); ph.alpha_composite(rounded(shot, 60), (18, 18))
        d.rounded_rectangle([(w + 36) // 2 - 70, 30, (w + 36) // 2 + 70, 64], 17, fill=(10, 12, 20, 255))                                 # the phone's pill
        sh = Image.new("RGBA", (ph.width + 240, ph.height + 240), (0, 0, 0, 0)); ImageDraw.Draw(sh).rounded_rectangle([120, 150, 120 + ph.width, 150 + ph.height], 80, fill=(0, 0, 0, 150)); sh = sh.filter(ImageFilter.GaussianBlur(46)); sh.alpha_composite(ph, (120, 120))
        _SITE.update(bg=bg, phone=sh)
    fr.paste(_SITE["bg"], (0, 0)); a = ease(tl / 0.5)
    paste(fr, _SITE["phone"], W / 2, 1210 + int(220 * (1 - a)), 0.96 + 0.04 * a, a, -2.5 * (1 - a))
    for k, (txt, size, col, y, wt) in enumerate((("EVERY FIND IN ONE PLACE", 44, (255, 255, 255), 250, 700), ("PUROCLASSICO.COM", 98, (255, 255, 255), 372, 900))):
        b = ease((tl - 0.15 - 0.12 * k) / 0.3)
        if b <= 0: continue
        while size > 40 and _M.textlength(txt, font=mfont(size, wt)) > W - 150: size -= 2
        f = mfont(size, wt); L = Image.new("RGBA", (W, int(size * 1.6)), (0, 0, 0, 0)); ImageDraw.Draw(L).text((W / 2, int(size * 0.8)), txt, font=f, fill=col + (255,), anchor="mm")
        paste(fr, L, W / 2, y + int(24 * (1 - b)), 1.0, b)

def fmt_style(D, a):
    """Fast outfit-advice video: no presenter, footage with a cut on every beat, one-word captions, voice + music."""
    try: vids = json.load(open(os.path.join(ROOT, "scripts", "styles.json"), encoding="utf-8"))
    except Exception as e: print("no styles.json:", e); return None
    n = int(D.state.get("style", 0)) % len(vids); st = next((x for x in vids if x["id"] == a.id), vids[n]) if a.id else vids[n]
    sc, ids, hero = [], [], None
    for k, ln in enumerate(st["lines"]):
        shots = [c for c in (drive_clip(*(d if isinstance(d, list) else [d])) for d in ln.get("drive") or []) if c] + picked(ln.get("clips")); first = shots[0] if shots else None
        if ln.get("paper"): shots.insert(0, ("photo", backdrop("paper"), "", dict({"paper": True}, **({"fx": "tick", "ding": True} if ln.get("tick") else {}))))      # a text-only beat on paper
        for pid in ln.get("products") or []:
            p = D.products.get(str(pid))
            ps = product_shot(p, first if ln.get("blur") else None, bool(ln.get("brand", True)), bool(ln.get("arrow", True))) if p else None
            if ps: shots.append(ps); ids.append(str(pid)); hero = hero or p
        nb = 0
        for b in ln.get("boards") or []:                         # brand boards, one per brand, swapping in place
            bs, bids = board_shot(D, b["brand"], b.get("cat"))
            if bs: shots.insert(nb, bs); nb += 1; ids += bids; hero = hero or D.products[bids[0]]      # the board leads its line
        if ln.get("site"):
            ss = site_shot()
            if ss: shots.append(ss)
        if ln.get("loop") and sc: shots += sc[0]["bg"][:3]        # end on the opening shots so the video loops
        if not shots: continue
        sc.append(dict(dur=2.0, say=ln["say"], bg=shots, music=st.get("music"), nocap=bool(ln.get("site") or ln.get("nocap")), word=True, cut=ln.get("cut", 0.9), pad=ln.get("pad", 0.14), boom=bool(ln.get("boom")), last=(k == len(st["lines"]) - 1)))
    if len(sc) < 3: return None
    if not hero: hero = D.top(1, skip_done=False)[0][1]
    cap = "%s 👕 Everything is on the spreadsheet in the bio." % st["title"] + (("\n\n" + st["credits"]) if st.get("credits") else "")
    return sc, ids[:1] and [], cap, hero, {"style": n + 1}

BUILD = dict(style=fmt_style, story=fmt_story, relatable=fmt_relatable, spotlight=fmt_spotlight, top5=fmt_top5, guess=fmt_guess, qc=fmt_qc, term=fmt_term, order=fmt_order)


# ---------------------------------------------------------------- voiceover (optional): ElevenLabs with word timings
def tts(line, path):
    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not key or not line: return 0.0, None
    body = json.dumps({"text": line, "model_id": VOICE_MODEL, "voice_settings": {"stability": 0.42, "similarity_boost": 0.8, "style": 0.18, "use_speaker_boost": True, "speed": _VOICE.get("speed", 1.0)}}).encode()
    r = None
    if "named" not in _VOICE and not os.environ.get("SHORTS_VOICE", "").strip() and os.environ.get("SHORTS_VOICE_NAME", "").strip():   # a voice looked up by name, only when asked for
        _VOICE["named"] = True; want = os.environ["SHORTS_VOICE_NAME"].strip().lower()
        try:
            vs = json.loads(fetch("https://api.elevenlabs.io/v1/voices", 60, None, {"xi-api-key": key})).get("voices", [])
            hit = next((v for v in vs if (v.get("name") or "").strip().lower() == want), None) or next((v for v in vs if want in (v.get("name") or "").lower()), None)
            if hit: VOICES.insert(0, hit["voice_id"]); print("  voice: using '%s'" % hit.get("name"))
            else: print("  voice '%s' not found among" % want, [v.get("name") for v in vs][:12])
        except Exception as e: print("  voice lookup failed:", e)
    for v in ([_VOICE["id"]] if _VOICE.get("id") else VOICES):               # first voice that works is kept for the whole video
        try:
            r = json.loads(fetch("https://api.elevenlabs.io/v1/text-to-speech/%s/with-timestamps?output_format=mp3_44100_128" % v, 90, body, {"xi-api-key": key, "Content-Type": "application/json"}))
            if not _VOICE.get("id"): print("  voice:", v)
            _VOICE["id"] = v; break
        except Exception as e:
            print("  voice %s failed:" % v, e)
    if r is None: return 0.0, None
    open(path + ".mp3", "wb").write(base64.b64decode(r["audio_base64"]))
    subprocess.run([FF, "-y", "-loglevel", "error", "-i", path + ".mp3", "-af", "areverse,silenceremove=start_periods=1:start_threshold=-55dB:start_silence=0.22,areverse",
                    "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le", path], check=True)
    with wave.open(path) as w: dur = w.getnframes() / w.getframerate()
    al = r.get("alignment") or {}; ch, st, en = al.get("characters") or [], al.get("character_start_times_seconds") or [], al.get("character_end_times_seconds") or []
    words, cur, t0 = [], "", None
    for c, a, b in zip(ch, st, en):
        if c.strip():
            if not cur: t0 = a
            cur += c; t1 = b
        elif cur: words.append((cur, t0, t1)); cur = ""
    if cur: words.append((cur, t0, t1))
    words = [(w, a, (words[k + 1][1] if k + 1 < len(words) else b + 0.15)) for k, (w, a, b) in enumerate(words)]   # hold each word until the next starts
    return dur, words or None


import glob
PRESENTERS = sorted(glob.glob(os.path.join(ROOT, "scripts", "presenter*.png"))); PRESENTER = PRESENTERS[0] if PRESENTERS else os.path.join(ROOT, "scripts", "presenter.png")
def use_presenter(n):                                         # rotate presenters between videos
    global PRESENTER
    if PRESENTERS: PRESENTER = PRESENTERS[n % len(PRESENTERS)]; print("  presenter:", os.path.basename(PRESENTER))
    v = PRESENTER_VOICE.get(os.path.basename(PRESENTER))          # each presenter keeps their own voice
    if v and not os.environ.get("SHORTS_VOICE", "").strip(): VOICES[:] = [v] + [x for x in VOICES if x != v]
PRESENTER_VOICE = {"presenter.png": "nPczCjzI2devNBz1zQrb", "presenter2.png": "iP95p4xoKVk53GoZ742B"}   # Brian, Chris
HEDRA = "https://api.hedra.com/v3"                           # v3 API: upload files -> submit job -> poll -> outputs[].url

def _multipart(path, mime):
    b = "----pc" + os.urandom(8).hex()
    body = ("--%s\r\nContent-Disposition: form-data; name=\"file\"; filename=\"%s\"\r\nContent-Type: %s\r\n\r\n" % (b, os.path.basename(path), mime)).encode() + open(path, "rb").read() + ("\r\n--%s--\r\n" % b).encode()
    return body, "multipart/form-data; boundary=" + b

_HEDRA = {}
def hedra_clip(audio_mp3, out_path):
    """Talking-presenter video for one line of audio (9:16, 720p). Returns the mp4 path, or None (falls back to footage)."""
    import time as _t
    key = os.environ.get("HEDRA_API_KEY", "").strip()
    if not key or not os.path.exists(PRESENTER) or not os.path.exists(audio_mp3) or _HEDRA.get("off"): return None
    H = {"Authorization": "Key " + key}
    def api(path, body=None, headers=None, timeout=120):
        return json.loads(fetch(HEDRA + path, timeout, body, headers or H) or b"{}")
    def upload(path, mime):
        body, ct = _multipart(path, mime); return api("/files", body, dict(H, **{"Content-Type": ct}), 180)["url"]
    try:
        if "bal" not in _HEDRA:
            _HEDRA["bal"] = api("/balance"); print("  hedra API wallet:", _HEDRA["bal"].get("balance"), _HEDRA["bal"].get("currency"))
        img = upload(PRESENTER, "image/png"); aud = upload(audio_mp3, "audio/mpeg")
        job = api("/models/hedra-character-3", json.dumps({"input": {
            "prompt": "A young man presenting the news to the camera in front of a plain solid green screen, natural head movement and blinking, friendly and confident, the background stays a flat green",
            "aspect_ratio": "9:16", "resolution": "720p",
            "start_image": {"source": "url", "url": img}, "audio": {"source": "url", "url": aud}}}).encode(), dict(H, **{"Content-Type": "application/json"}))
        jid = job["job_id"]
        for _ in range(150):
            _t.sleep(6); st = api("/jobs/%s/status" % jid).get("status")
            if st == "COMPLETED":
                outs = api("/jobs/%s" % jid).get("outputs") or []; url = next((o.get("url") for o in outs if o.get("url")), None)
                if not url: print("  hedra: no output url", outs); return None
                open(out_path, "wb").write(fetch(url, 300)); print("  presenter clip ready:", os.path.getsize(out_path) // 1024, "KB"); return out_path
            if st == "FAILED": print("  hedra job failed:", json.dumps(api("/jobs/%s" % jid))[:400]); return None
        print("  hedra timed out")
    except Exception as e:
        detail = ""
        try: detail = e.read().decode()[:400]
        except Exception: pass
        print("  hedra failed (using footage instead):", e, detail)
        if "402" in str(e) or "INSUFFICIENT" in detail: _HEDRA["off"] = True       # empty wallet: don't keep trying
    return None


def build_audio(scenes, tmp):
    if any(s.get("word") for s in scenes): _VOICE["speed"] = 1.03                         # an easy, conversational pace
    track = os.path.join(tmp, "voice.wav"); out = wave.open(track, "wb"); out.setnchannels(2); out.setsampwidth(2); out.setframerate(44100); voiced = False
    for k, s in enumerate(scenes):
        wav = os.path.join(tmp, "s%d.wav" % k); d, words = tts(s.get("say"), wav); written = 0
        if d:
            voiced = True; s["words"] = words
            s["dur"] = d + (1.5 if s.get("last") else s["pad"]) if s.get("word") else max(d + (1.0 if s.get("last") else 0.4), 2.0)
            if s.get("presenter"):                            # the AI presenter says this line on camera
                os.makedirs(MEDIA_DIR, exist_ok=True); clip = hedra_clip(wav + ".mp3", os.path.join(MEDIA_DIR, "presenter%d.mp4" % k))
                if clip: s["fg"] = clip
            with wave.open(wav) as w: out.writeframes(w.readframes(w.getnframes()))
            written = int(d * 44100)
        out.writeframes(b"\0\0\0\0" * max(0, int(round(s["dur"] * FPS)) * 44100 // FPS - written))
    out.close(); return track if voiced else None


# ---------------------------------------------------------------- background music
MUSIC_PROMPT = "Upbeat modern instrumental beat for a fast, punchy explainer video: tight drums, driving bass, bright synth plucks, confident and energetic, 118 bpm, no vocals"
STYLE_MUSIC = "Minimal stylish instrumental beat for a fast fashion video, exactly 128 bpm, starts immediately on the first kick, punchy kick and clap, deep bass, sparse plucks, confident, no vocals"
SFX_PROMPTS = {"ding": ("One soft, satisfying interface tap: a gentle rounded click with a warm low pop, like a premium phone keyboard tap. Subtle, dry, clean, no bell, no reverb", 0.5),
               "boom": ("One soft low whoosh into a gentle muffled thump, like a smooth film transition. Warm, subtle, clean, no distortion", 0.9),
               "swish": ("One very soft airy swoosh, a light quick swipe of air. Subtle, smooth, clean", 0.5),
               "bell": ("A warm, positive two-note chime, like the sound a quiz app plays for a correct answer. Soft mallet tone, pleasant, short, clean", 0.9),
               "bell-b": ("One single ring of a small hotel reception desk bell. Clear, bright, natural, short", 0.9),
               "bell-c": ("A soft, modern notification sound: one rounded marimba note with a gentle shimmer. Pleasant, clean, short", 0.8),
               "reveal": ("A very soft, airy whoosh, like a gentle breath of air, fading out smoothly. Quiet, warm, no chime, no bell, no high notes", 1.2)}
SFX = {}
def load_sfx(out_dir):
    """Sound effects from scripts/sfx/<name>.mp3 if present, else generated (saved next to the video so they can be kept)."""
    import array
    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    for name, (prompt, dur) in SFX_PROMPTS.items():
        src = os.path.join(ROOT, "scripts", "sfx", name + ".mp3")
        if not os.path.exists(src) and key:
            try:
                b = fetch("https://api.elevenlabs.io/v1/sound-generation", 120, json.dumps({"text": prompt, "duration_seconds": dur, "prompt_influence": 0.7}).encode(), {"xi-api-key": key, "Content-Type": "application/json"})
                if len(b) > 2000: src = os.path.join(out_dir, "sfx-%s.mp3" % name); open(src, "wb").write(b); print("  sfx: generated", name, len(b) // 1024, "KB")
            except Exception as e:
                d = ""
                try: d = e.read().decode()[:160]
                except Exception: pass
                print("  sfx %s failed:" % name, e, d)
        if os.path.exists(src):
            raw = subprocess.run([FF, "-loglevel", "error", "-i", src, "-ac", "2", "-ar", "44100", "-af", "silenceremove=start_periods=1:start_threshold=-45dB,loudnorm=I=-14:TP=-2", "-f", "s16le", "-"], stdout=subprocess.PIPE).stdout
            if len(raw) > 4000: a = array.array("h"); a.frombytes(raw[:len(raw) // 4 * 4]); SFX[name] = a

def sfx_track(scenes, path):
    """Sound effects for a style video (thump on emphasis, pop on reveals, swish on the marker ring) as a stereo wav."""
    import array
    total = sum(int(round(s["dur"] * FPS)) for s in scenes) / FPS; n = int(total * 44100); buf = array.array("h", [0]) * (n * 2); t0 = 0.0; any_hit = False
    def mix(a, i0, gain=1.0):
        m = min(len(a), (n - i0) * 2)
        for j in range(max(0, m)):
            v = buf[2 * i0 + j] + int(a[j] * gain); buf[2 * i0 + j] = 32000 if v > 32000 else -32000 if v < -32000 else v
    for s in scenes:
        if s.get("boom") and SFX.get("boom"): any_hit = True; mix(SFX["boom"], int(t0 * 44100), 0.6)
        elif s.get("boom"):
            any_hit = True; i0 = int(t0 * 44100); ph = 0.0
            for i in range(int(0.35 * 44100)):
                if i0 + i >= n: break
                t = i / 44100; f = 36 + 50 * math.exp(-t * 30); ph += 2 * math.pi * f / 44100
                v = int(17000 * math.sin(ph) * math.exp(-t * 13) * min(1.0, i / 90)); buf[2 * (i0 + i)] = v; buf[2 * (i0 + i) + 1] = v
        dur = int(round(s["dur"] * FPS)) / FPS; shots = s.get("bg") or []
        if shots and s.get("word"):
            nseg = max(1, min(len(shots), int(round(dur / s.get("cut", CUT))))); seg = dur / nseg
            for k in range(nseg):
                meta = shots[k % len(shots)][3] if len(shots[k % len(shots)]) > 3 else {}
                if not meta.get("ding"): continue
                any_hit = True; i0 = int((t0 + k * seg + (0.1 if meta.get("fx") else 0.02)) * 44100)
                if meta.get("bell") and SFX.get("bell"): mix(SFX["bell"], int((t0 + k * seg + 0.02) * 44100), 0.6); continue      # the answer: a clear ding
                if meta.get("site") and SFX.get("reveal"): mix(SFX["reveal"], int((t0 + k * seg) * 44100), 0.2); continue    # the end screen has its own sound
                if meta.get("fx") == "orbit" and SFX.get("swish"): mix(SFX["swish"], i0, 0.4)
                if SFX.get("ding"): mix(SFX["ding"], i0, 0.5); continue
                for i in range(int(0.6 * 44100)):
                    if i0 + i >= n: break
                    t = i / 44100; env = math.exp(-t / 0.17) * min(1.0, i / 130)
                    v = int(5200 * env * (math.sin(2 * math.pi * 2350 * t) + 0.38 * math.sin(2 * math.pi * 5170 * t) * math.exp(-t / 0.08) + 0.16 * math.sin(2 * math.pi * 7990 * t) * math.exp(-t / 0.05)))
                    for c in (0, 1): buf[2 * (i0 + i) + c] = max(-32000, min(32000, buf[2 * (i0 + i) + c] + v))
        t0 += dur
    if not any_hit: return None
    with wave.open(path, "wb") as w: w.setnchannels(2); w.setsampwidth(2); w.setframerate(44100); w.writeframes(buf.tobytes())
    return path

MUSIC_OPTIONS = ["Laid-back melodic house instrumental, 122 bpm, warm piano chords, soft four-on-the-floor kick, tasteful and stylish, starts immediately, no vocals",
                 "Smooth classy lounge hip-hop instrumental, 90 bpm, jazzy electric piano, soft boom-bap drums, relaxed and confident, starts immediately, no vocals",
                 "Bright Scandinavian pop-house instrumental, 126 bpm, plucked synth melody, clean and uplifting, starts immediately, no vocals"]
def music_options(out_dir):
    """Generate the candidate tracks (music-1.mp3 ...) and return the first that worked."""
    key = os.environ.get("ELEVENLABS_API_KEY", "").strip(); first = None
    if not key: return None
    for k, prompt in enumerate(MUSIC_OPTIONS, 1):
        for body in ({"prompt": prompt, "music_length_ms": 40000, "force_instrumental": True}, {"prompt": prompt, "music_length_ms": 40000}):
            try:
                b = fetch("https://api.elevenlabs.io/v1/music?output_format=mp3_44100_128", 240, json.dumps(body).encode(), {"xi-api-key": key, "Content-Type": "application/json"})
                if len(b) > 20000: path = os.path.join(out_dir, "music-%d.mp3" % k); open(path, "wb").write(b); print("  music option", k, len(b) // 1024, "KB"); first = first or path; break
            except Exception as e: print("  music option", k, "failed:", e)
    return first

def music_track(out_dir, prompt=None):
    """A track from scripts/music/ if there is one, else a new one from ElevenLabs (saved next to the video so it can be kept)."""
    lib = sorted(glob.glob(os.path.join(ROOT, "scripts", "music", "*.mp3")))
    if lib: m = random.choice(lib); print("  music:", os.path.basename(m)); return m
    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not key: return None
    H = {"xi-api-key": key, "Content-Type": "application/json"}; path = os.path.join(out_dir, "music.mp3"); MUSIC_PROMPT = prompt or globals()["MUSIC_PROMPT"]
    tries = [("music", "https://api.elevenlabs.io/v1/music?output_format=mp3_44100_128", {"prompt": MUSIC_PROMPT, "music_length_ms": 40000, "force_instrumental": True}),
             ("music", "https://api.elevenlabs.io/v1/music?output_format=mp3_44100_128", {"prompt": MUSIC_PROMPT, "music_length_ms": 40000}),
             ("sound loop", "https://api.elevenlabs.io/v1/sound-generation", {"text": MUSIC_PROMPT + ", seamless loop", "duration_seconds": 22, "prompt_influence": 0.5})]
    for name, url, body in tries:
        try:
            b = fetch(url, 240, json.dumps(body).encode(), H)
            if len(b) > 20000: open(path, "wb").write(b); print("  music: generated (%s), %d KB" % (name, len(b) // 1024)); return path
        except Exception as e:
            d = ""
            try: d = e.read().decode()[:200]
            except Exception: pass
            print("  music (%s) failed:" % name, e, d)
    return None


# ---------------------------------------------------------------- render
def render(scenes, out_path):
    FT = fonts(); bg = background(); logo = FT["logo"]
    with tempfile.TemporaryDirectory() as tmp:
        audio = build_audio(scenes, tmp)
        frames = [int(round(s["dur"] * FPS)) for s in scenes]; total = sum(frames)
        fake = os.environ.get("SHORTS_FAKE_FG")                 # layout testing without the presenter API
        if fake:
            for s in scenes:
                if s.get("presenter") and not s.get("fg"): s["fg"] = fake
        style = any(s.get("word") for s in scenes)
        lib = glob.glob(os.path.join(ROOT, "scripts", "music", "*.mp3"))
        own = next((s.get("music") for s in scenes if s.get("music")), None); own = drive_file(own, "mp3") if own else None
        music = (own or (random.choice(lib) if lib else None)) if style else (music_track(os.path.dirname(out_path), None) if any(s.get("news") for s in scenes) else None)
        if style: print("  music:", os.path.basename(music) if music else "none yet (waiting for the owner's tracks in scripts/music/)")
        if style: load_sfx(os.path.dirname(out_path))
        sfx = sfx_track(scenes, os.path.join(tmp, "sfx.wav")) if style else None
        cmd = [FF, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W, H), "-r", str(FPS), "-i", "-"]
        cmd += ["-i", audio] if audio else ["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100"]
        if music or sfx or style:
            fc, mix, k = ["[1:a]acompressor=threshold=0.09:ratio=4:attack=5:release=90:makeup=3.2,alimiter=limit=0.97[v]"], "[v]", 2
            if music:
                cmd += ["-stream_loop", "-1", "-i", music]
                fc.append("[%d:a]volume=%s,afade=t=out:st=%.2f:d=1.5[m]" % (k, "1,loudnorm=I=-16:TP=-1.5,volume=0.30" if style else "0.16,afade=t=in:d=0.3", max(0, total / FPS - 1.6))); mix += "[m]"; k += 1
            if sfx: cmd += ["-i", sfx]; fc.append("[%d:a]volume=0.9[x]" % k); mix += "[x]"; k += 1
            fc.append("%samix=inputs=%d:duration=first:dropout_transition=0:normalize=0[a]" % (mix, k - 1))
            cmd += ["-filter_complex", ";".join(fc), "-map", "0:v", "-map", "[a]", "-t", "%.3f" % (total / FPS)]
        cmd += ["-shortest", "-c:v", "libx264", "-preset", "medium", "-crf", "23", "-maxrate", "6M", "-bufsize", "12M", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", out_path]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE); done = 0
        for s, nf in zip(scenes, frames):
            dur = nf / FPS
            for i in range(nf):
                lt = i / FPS; t_abs = (done + i) / FPS; fr = bg.copy(); fr.alpha_composite(logo, ((W - logo.size[0]) // 2, 150))
                draw_scene(fr, s, lt, dur, FT)
                draw_host(fr, s, lt, t_abs, FT)
                if i == nf - 1: LASTF.update(im=fr.copy(), soft=bool(s.get("_quiet")))
                proc.stdin.write(fr.convert("RGB").tobytes())
            done += nf
            for c in list((s.get("_clips") or {}).values()) + ([s["_fg"]] if s.get("_fg") else []): c.close()
        proc.stdin.close(); proc.wait()
        if proc.returncode: raise SystemExit("ffmpeg failed")
    return total / FPS, bool(audio)


SAMPLE_VOICES = [("Will", "bIHbv24MWmeRgasZH58o"), ("Liam", "TX3LPaxmHKxFdv7VOQHJ"), ("Chris", "iP95p4xoKVk53GoZ742B"), ("Charlie", "IKne3meq5aSn9XLyUdCD"),
                 ("Daniel", "onwK4e9ZLuTAKqWW03F9"), ("George", "JBFqnCBsd6RMkjVDRZzb"), ("Adam", "pNInz6obpgDQGcFmaJgB"), ("Brian", "nPczCjzI2devNBz1zQrb")]

def voice_samples(out_dir):
    """One mp3 where each candidate voice says its name and the same line, so the owner can pick."""
    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not key: print("no ELEVENLABS_API_KEY"); return
    parts = []
    for n, (name, vid) in enumerate(SAMPLE_VOICES, 1):
        text = "Voice %d. %s. Did you know more than half of the world's shoes come from one country?" % (n, name)
        try:
            mp3 = fetch("https://api.elevenlabs.io/v1/text-to-speech/%s?output_format=mp3_44100_128" % vid, 90,
                        json.dumps({"text": text, "model_id": VOICE_MODEL}).encode(), {"xi-api-key": key, "Content-Type": "application/json", "Accept": "audio/mpeg"})
            path = os.path.join(out_dir, "v%d.mp3" % n); open(path, "wb").write(mp3); parts.append(path); print("  sample:", n, name)
        except Exception as e: print("  sample failed:", name, e)
    if not parts: return
    lst = os.path.join(out_dir, "v.txt"); open(lst, "w").write("".join("file '%s'\n" % p for p in parts))
    subprocess.run([FF, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c:a", "libmp3lame", "-b:a", "128k", os.path.join(out_dir, "voices.mp3")], check=True)
    for p in parts + [lst]: os.remove(p)


CANDIDATES = [
    "a woman in her late twenties with dark brown hair in a low bun, wearing a cream blazer over a white top",
    "a man in his early thirties with short dark curly hair and light stubble, wearing an olive green overshirt over a white t-shirt",
    "a woman in her mid twenties with shoulder-length auburn hair, wearing a navy knit sweater",
    "a man in his late twenties with short black hair, wearing a charcoal crewneck sweater",
]
def make_presenters(out_dir):
    """Generate candidate AI presenter portraits (on a green screen) for the owner to choose from."""
    import time as _t
    key = os.environ.get("HEDRA_API_KEY", "").strip()
    if not key: print("no HEDRA_API_KEY"); return
    H = {"Authorization": "Key " + key, "Content-Type": "application/json"}
    jobs = []
    for n, who in enumerate(CANDIDATES, 1):
        prompt = ("Ultra-realistic professional studio portrait photograph of %s. Head and shoulders, centred, facing the camera, looking straight into the lens, "
                  "relaxed friendly expression with a slight smile, mouth closed. Soft even studio lighting, sharp focus, natural skin texture, 85mm lens. "
                  "The background is a perfectly flat, evenly lit, pure chroma-key green screen (#00FF00) with no shadows, no gradient and no other objects. No text, no logos.") % who
        try:
            j = json.loads(fetch(HEDRA + "/models/nano-banana-pro", 120, json.dumps({"input": {"prompt": prompt, "aspect_ratio": "9:16", "resolution": "2K"}}).encode(), H))
            jobs.append((n, j["job_id"]))
        except Exception as e:
            d = ""
            try: d = e.read().decode()[:300]
            except Exception: pass
            print("  candidate %d failed to start:" % n, e, d)
    for n, jid in jobs:
        for _ in range(60):
            _t.sleep(5); st = json.loads(fetch(HEDRA + "/jobs/%s/status" % jid, 60, None, H)).get("status")
            if st == "COMPLETED":
                outs = json.loads(fetch(HEDRA + "/jobs/%s" % jid, 60, None, H)).get("outputs") or []; url = next((o.get("url") for o in outs if o.get("url")), None)
                if url:
                    im = Image.open(io.BytesIO(fetch(url, 180))).convert("RGB"); im.save(os.path.join(out_dir, "candidate-%d.jpg" % n), quality=92); print("  candidate", n, "saved", im.size)
                break
            if st == "FAILED": print("  candidate", n, "failed"); break


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--voice-samples", action="store_true"); ap.add_argument("--make-presenters", action="store_true"); ap.add_argument("--presenter", type=int, default=0)
    ap.add_argument("--format", default="auto", choices=["auto"] + FORMATS); ap.add_argument("--id"); ap.add_argument("--slot", type=int)
    ap.add_argument("--out", default=os.path.join(ROOT, "out")); ap.add_argument("--commit-state", action="store_true")
    a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)
    if a.voice_samples: return voice_samples(a.out)
    if a.make_presenters: return make_presenters(a.out)
    D = Data(); n = a.slot if a.slot is not None else int(D.state.get("n", 0))
    order = FORMATS[n % len(FORMATS):] + FORMATS[:n % len(FORMATS)] if a.format == "auto" else [a.format]
    built = None
    for f in order + ["spotlight"]:
        built = BUILD[f](D, a)
        if built: fmt = f; break
        print("format", f, "not possible right now, trying the next one")
    scenes, ids, caption, p = built[:4]; extra = built[4] if len(built) > 4 else {}
    tagb = "".join(ch for ch in (p.get("brand") or "") if ch.isalnum()).lower()
    caption += "\n\n#fashion #finds #outfitinspo #haul #mycnbox" + ((" #" + tagb) if tagb and fmt in ("spotlight", "guess", "qc") else "")
    name = "short-%s-%s" % (fmt, ids[0] if ids else "n%d" % n); out = os.path.join(a.out, name + ".mp4")
    print("rendering", fmt, ids or "", "->", out)
    secs, voiced = render(scenes, out)
    meta = {"format": fmt, "ids": ids, "caption": caption, "seconds": round(secs, 1), "voiceover": voiced, "file": out,
            "product_url": ("%s/product/%s" % (SITE, ids[0])) if ids else SITE + "/"}
    json.dump(meta, open(out[:-4] + ".json", "w"), indent=1, ensure_ascii=False)
    print("wrote", out, "%.1fs" % secs, "%.1f MB" % (os.path.getsize(out) / 1e6), "voiceover" if voiced else "silent")
    if a.commit_state:
        st = D.state; st["ids"] = sorted(D.done | set(ids)); st["n"] = n + 1; st.update(extra)
        json.dump(st, open(os.path.join(ROOT, "shorts_posted.json"), "w"), indent=0)
    return meta


if __name__ == "__main__":
    main()
