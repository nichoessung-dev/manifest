# -*- coding: utf-8 -*-
"""A "finds" post: a simple cover, then slides with two photos stacked (one on top, one below), over a sound.

  python scripts/make_finds.py --folder <Drive folder id of photos> [--audio <Drive file id>] [--cover <Drive file id>] [--slides 7] [--title "Old money finds"]
  python scripts/make_finds.py --local <directory of photos> ...        (for testing)

The Drive folder must be shared by link. Photos are picked least-used first, in random order among equally used ones (finds_used.json keeps the counts), so they repeat only once the pool is used up.
"""
import argparse, glob, hashlib, html, json, os, random, re, subprocess, sys, tempfile, urllib.request
from datetime import datetime
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps
import imageio_ffmpeg
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from restore import restore

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H, FPS = 1080, 1920, 30
SW, SH = 1080, 1440                                          # carousel slides are 3:4: the TikTok app shows that shape whole, a 9:16 photo gets cut top and bottom
FF = imageio_ffmpeg.get_ffmpeg_exe()
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"}
CACHE = os.path.join(tempfile.gettempdir(), "pc_finds"); os.makedirs(CACHE, exist_ok=True)
FONT = os.path.join(ROOT, "scripts", "fonts", "Montserrat.ttf")
SCRIPT = os.path.join(ROOT, "scripts", "fonts", "Parisienne-Regular.ttf")    # the "puro classico" script in the corner badge
ITEMS_FILE = os.path.join(ROOT, "scripts", "qc_items.json")                 # what each QC shot shows (type, item, brand, colour), so a slide pairs two alike
LABELS = os.environ.get("FINDS_LABELS", "") == "1"                           # the name in the middle of each slide: off since 18 Oct 2026 (owner: a boosted post with brand names was rejected)
LABELS_FILE = os.path.join(ROOT, "scripts", "qc_labels.json")               # the short casual name on each slide ("Stoney Half-Zips"), per pair of shots


def font(size, weight=900):
    f = ImageFont.truetype(FONT, size)
    try: f.set_variation_by_axes([weight])
    except Exception: pass
    return f


def fetch(url, timeout=180):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout).read()


def drive_list(folder):
    h = fetch("https://drive.google.com/embeddedfolderview?id=%s#list" % folder, 60).decode("utf-8", "ignore")
    return [(i, html.unescape(t)) for i, t in re.findall(r'id="entry-([A-Za-z0-9_-]{20,})".*?class="flip-entry-title">(.*?)</div>', h, re.S)]


IMG_EXT = (".png", ".jpg", ".jpeg", ".webp")


def drive_images(folder, depth=0):
    """Every picture in a Drive folder, including pictures in its subfolders (the owner uploads batches as folders)."""
    out = []
    for i, t in drive_list(folder):
        if t.lower().endswith(IMG_EXT): out.append((i, None))
        elif "." not in t and depth < 2:
            try: out += drive_images(i, depth + 1)
            except Exception as e: print("  could not read the subfolder %s: %s" % (t, e))
    return out


def split_stacked(im):
    """A source that is already two shots stacked. Tall ones (the first uploads) give their main, top shot; the slide exports give both shots.
    Returns the usable shots, or None when a tall picture has no join near the middle."""
    r = im.height / float(im.width)
    if r <= 1.22: return [im]
    g = im.convert("L").resize((240, max(4, int(240 * r)))); w, h = g.size; px = g.load(); cov, row = 0.0, h // 2
    for y in range(int(h * 0.40), int(h * 0.60)):               # the join: a row where nearly every column changes at once
        c = sum(1 for x in range(w) if abs(px[x, y] - px[x, y + 1]) > 18) / float(w)
        if c > cov: cov, row = c, y + 1
    cut = int(round(row * im.height / float(h)))
    if r > 1.5: return [im.crop((0, 0, im.width, cut))] if cov >= 0.5 else None
    return [im.crop((0, 0, im.width, cut)), im.crop((0, cut, im.width, im.height))] if cov >= 0.5 else [im]


def drive_get(fid, ext):
    path = os.path.join(CACHE, "%s.%s" % (fid, ext))
    if not os.path.exists(path):
        for u in ("https://drive.google.com/uc?export=download&id=%s" % fid, "https://drive.usercontent.google.com/download?id=%s&export=download&confirm=t" % fid):
            try:
                d = fetch(u)
                if len(d) > 5000 and not d[:15].lstrip().lower().startswith(b"<!doctype"): open(path, "wb").write(d); break
            except Exception: pass
    return path if os.path.exists(path) else None


COVER_TEXT = "Hardest grisch finds"                          # the only words on the first image (owner's choice, 17 Oct 2026)
HOOKS = ["%s", "New %s", "%s, part {part}", "Best %s", "%s this week"]          # short on purpose (owner, 17 Oct 2026)
TAGS = ["#finds", "#haul", "#fashion", "#quietluxury", "#oldmoneystyle", "#oldmoneyaesthetic", "#mensfashion", "#outfitinspo", "#stockholmstyle", "#fashionfinds", "#autumnfashion"]


COVER_FONTS = [("Anton-Regular.ttf", None), ("BebasNeue-Regular.ttf", None), ("ArchivoBlack-Regular.ttf", None), ("Oswald.ttf", 700),
               ("BowlbyOneSC-Regular.ttf", None), ("Bangers-Regular.ttf", None), ("RussoOne-Regular.ttf", None),
               ("PassionOne-Bold.ttf", None), ("Montserrat.ttf", 900)]          # the start picture's type changes every post (owner, 18 Oct 2026)
ARROWS = ["keys", "keys_white", "keys_yellow", "chevrons", "long", "circles", "triangles"]


def cover_font(k, size):
    name, w = COVER_FONTS[k % len(COVER_FONTS)]; f = ImageFont.truetype(os.path.join(ROOT, "scripts", "fonts", name), size)
    if w:
        try: f.set_variation_by_axes([w])
        except Exception: pass
    return f


def cover_card(title, SW=SW, SH=SH, bg=None, look=(0, 0)):
    """The start image: the title in tall white capitals with a black outline and arrows under it, over a picture.
    look = (font, arrow style): both change from post to post."""
    if bg is None: im = Image.new("RGB", (SW, SH), (24, 26, 32))
    else: im = crisp(ImageOps.fit(bg.convert("RGB"), (SW, SH), Image.LANCZOS))
    d = ImageDraw.Draw(im); words = title.upper().split()
    lines = [" ".join(words)]
    size = 150
    f = lambda z: cover_font(look[0], z)
    while size > 60 and d.textlength(lines[0], font=f(size)) > SW - 90: size -= 4
    if size < 96 and len(words) > 1:                              # too long for one line: two lines, bigger
        k = (len(words) + 1) // 2; lines = [" ".join(words[:k]), " ".join(words[k:])]; size = 170
        while size > 60 and max(d.textlength(l, font=f(size)) for l in lines) > SW - 90: size -= 4
    ft, lh, sw = f(size), int(size * 1.12), max(6, size // 14)
    key = int(SW * 0.12); gap = int(key * 0.16)                    # the arrows keep one size whatever the font
    block = lh * len(lines) + gap * 3 + key
    y = int(SH * 0.56) - block // 2
    for ln in lines:
        d.text((SW / 2, y), ln, font=ft, fill=(255, 255, 255), anchor="ma", stroke_width=sw, stroke_fill=(0, 0, 0)); y += lh
    arrows(im, SW // 2, y + gap * 2, key, gap, ARROWS[look[1] % len(ARROWS)])
    return im


def arrows(im, cx, y, s, gap, style):
    """Arrows pointing right under the title, in one of several looks."""
    x0 = cx - (s * 3 + gap * 2) // 2
    if style.startswith("keys"):
        face, edge, ink = {"keys": ((150, 172, 200), (92, 112, 138), (255, 255, 255)), "keys_white": ((250, 250, 250), (170, 170, 176), (20, 20, 22)),
                           "keys_yellow": ((255, 206, 40), (196, 150, 10), (20, 20, 22))}[style]
        for k in range(3): arrow_key(im, x0 + k * (s + gap), y, s, face, edge, ink)
        return
    d = ImageDraw.Draw(im); white, black = (255, 255, 255), (0, 0, 0); o = max(5, s // 14)
    if style == "chevrons":
        for k in range(3):
            x = x0 + k * (s + gap) + s // 4; pts = [(x, y + s * 0.12), (x + s * 0.5, y + s * 0.5), (x, y + s * 0.88)]
            d.line(pts, fill=black, width=int(s * 0.26) + 2 * o, joint="curve"); d.line(pts, fill=white, width=int(s * 0.26), joint="curve")
    elif style == "long":
        w, t, cy = s * 3, int(s * 0.16), y + s // 2
        for col, e in ((black, o), (white, 0)):
            d.line([(cx - w // 2 - e, cy), (cx + w // 2 - s * 0.5, cy)], fill=col, width=t + 2 * e)
            d.polygon([(cx + w // 2 + e * 1.6, cy), (cx + w // 2 - s * 0.6 - e, cy - s * 0.42 - e), (cx + w // 2 - s * 0.6 - e, cy + s * 0.42 + e)], fill=col)
    elif style == "circles":
        for k in range(3):
            x = x0 + k * (s + gap); d.ellipse([x - o, y - o, x + s + o, y + s + o], fill=black); d.ellipse([x, y, x + s, y + s], fill=white)
            t, cy = int(s * 0.12), y + s // 2
            d.line([(x + s * 0.25, cy), (x + s * 0.62, cy)], fill=black, width=t)
            d.polygon([(x + s * 0.78, cy), (x + s * 0.52, cy - s * 0.22), (x + s * 0.52, cy + s * 0.22)], fill=black)
    else:                                                          # triangles
        for k in range(3):
            x = x0 + k * (s + gap) + s * 0.12; tri = [(x, y + s * 0.1), (x + s * 0.8, y + s * 0.5), (x, y + s * 0.9)]
            d.polygon(tri, fill=black, outline=black, width=2 * o); d.polygon([(x + o, y + s * 0.1 + o * 1.8), (x + s * 0.8 - o * 2, y + s * 0.5), (x + o, y + s * 0.9 - o * 1.8)], fill=white)


def arrow_key(im, x, y, s, face=(150, 172, 200), edge=(92, 112, 138), ink=(255, 255, 255)):
    """One arrow key like the emoji: a rounded square with an arrow pointing right."""
    k = Image.new("RGBA", (s, s), (0, 0, 0, 0)); d = ImageDraw.Draw(k); r = int(s * 0.2)
    d.rounded_rectangle([0, 0, s - 1, s - 1], r, fill=edge + (255,))
    d.rounded_rectangle([int(s * .04), int(s * .04), s - 1 - int(s * .04), s - 1 - int(s * .06)], r, fill=face + (255,))
    t = int(s * 0.13); cy = s // 2; xa, xb = int(s * 0.2), int(s * 0.8)
    d.rectangle([xa, cy - t // 2, xb - int(s * 0.18), cy + t // 2], fill=ink + (255,))
    d.polygon([(xb, cy), (xb - int(s * 0.26), cy - int(s * 0.24)), (xb - int(s * 0.26), cy + int(s * 0.24))], fill=ink + (255,))
    sh = Image.new("RGBA", (s + 20, s + 20), (0, 0, 0, 0)); ImageDraw.Draw(sh).rounded_rectangle([10, 14, s + 9, s + 13], r, fill=(0, 0, 0, 120))
    sh = sh.filter(ImageFilter.GaussianBlur(6)); im.paste(sh, (x - 10, y - 10), sh); im.paste(k, (x, y), k)


def draw_arrow(d, cx, y, w, col, t):
    """A bold arrow pointing right, centred on cx."""
    x0, x1, h = cx - w // 2, cx + w // 2, int(t * 2.3)
    d.line([(x0, y), (x1 - h, y)], fill=col, width=t)
    d.ellipse([x0 - t // 2, y - t // 2, x0 + t // 2, y + t // 2], fill=col)
    d.polygon([(x1, y), (x1 - int(h * 1.5), y - h), (x1 - int(h * 1.5), y + h)], fill=col)


def whole(im, w, h):
    """The whole photo, nothing cut off: scaled to fit, with a blurred copy of itself filling what is left at the sides."""
    im = im.convert("RGB"); bg = ImageOps.fit(im, (w, h), Image.BILINEAR).filter(ImageFilter.GaussianBlur(28))
    fg = crisp(ImageOps.contain(im, (w, h), Image.LANCZOS)); bg.paste(fg, ((w - fg.width) // 2, (h - fg.height) // 2)); return bg


def crisp(im):
    """Sharpen after resizing: the QC photos are soft video stills, and TikTok compresses them again on top."""
    im = im.filter(ImageFilter.UnsharpMask(radius=2.2, percent=90, threshold=2)).filter(ImageFilter.UnsharpMask(radius=0.8, percent=60, threshold=1))
    return ImageEnhance.Color(ImageEnhance.Contrast(im).enhance(1.05)).enhance(1.06)


def fill(im, w, h):
    """The photo filling the whole area edge to edge (cropped to fit, centred), no blurred bars. Cleaned up by the
    restoration model when it is available (a little of the original is kept so knit and fabric texture stays real)."""
    im = im.convert("RGB"); base = ImageOps.fit(im, (w, h), Image.LANCZOS, centering=(0.5, 0.5)); r = restore(im, w, h)
    if r is im: return crisp(base)
    out = Image.blend(ImageOps.fit(r, (w, h), Image.LANCZOS, centering=(0.5, 0.5)), base, 0.15)
    out = out.filter(ImageFilter.UnsharpMask(radius=1.2, percent=45, threshold=2))
    return ImageEnhance.Color(ImageEnhance.Contrast(out).enhance(1.04)).enhance(1.05)


def slide(a, b, SW=SW, SH=SH, badge=None, label=""):
    """Two photos stacked, each filling its half, a thin white line between them and, when given, a short white label
    ("Stoney Half-Zips") centred on the line. With a badge, it covers the bottom-right corner of each half (where the old
    watermark of exported photos sits)."""
    im = Image.new("RGB", (SW, SH), (255, 255, 255)); gap = 4; hh = (SH - gap) // 2
    im.paste(fill(a, SW, hh), (0, 0)); im.paste(fill(b, SW, SH - hh - gap), (0, hh + gap))
    if badge is not None:
        im.paste(badge, (SW - badge.width, hh - badge.height)); im.paste(badge, (SW - badge.width, SH - badge.height))
    if label: pill(im, label, hh + gap // 2)
    return im


def pill(im, text, cy):
    """A white rounded label with bold black text, centred on the line at height cy."""
    d = ImageDraw.Draw(im); size = int(im.width * 0.046)
    while size > 20 and d.textlength(text, font=font(size, 700)) > im.width * 0.62: size -= 2
    f = font(size, 700); tw = d.textlength(text, font=f); px, ph = int(size * 0.62), int(size * 1.72)
    box = [int(im.width / 2 - tw / 2 - px), int(cy - ph / 2), int(im.width / 2 + tw / 2 + px), int(cy + ph / 2)]
    sh = Image.new("RGBA", im.size, (0, 0, 0, 0)); ImageDraw.Draw(sh).rounded_rectangle([box[0], box[1] + 4, box[2], box[3] + 4], ph // 2, fill=(0, 0, 0, 70))
    im.paste(sh.filter(ImageFilter.GaussianBlur(6)), (0, 0), sh.filter(ImageFilter.GaussianBlur(6)))
    d = ImageDraw.Draw(im); d.rounded_rectangle(box, ph // 2, fill=(255, 255, 255))
    d.text((im.width / 2, cy), text, font=f, fill=(12, 12, 14), anchor="mm")


def make_badge(w=200):
    """The corner badge of the second account: "puro classico" in navy script over "HARDEST FINDS", on white."""
    b = Image.new("RGB", (w, w), (255, 255, 255)); d = ImageDraw.Draw(b)
    size = int(w * 0.30)
    while size > 10 and d.textlength("puro classico", font=ImageFont.truetype(SCRIPT, size)) > w * 0.86: size -= 1
    d.text((w / 2, w * 0.47), "puro classico", font=ImageFont.truetype(SCRIPT, size), fill=(18, 30, 72), anchor="ms")
    cap = ImageFont.truetype(FONT, max(8, int(w * 0.068))); txt = "HARDEST FINDS"
    try: cap.set_variation_by_axes([500])
    except Exception: pass
    sp = w * 0.022; tw = sum(d.textlength(c, font=cap) for c in txt) + sp * (len(txt) - 1); x = (w - tw) / 2
    for c in txt: d.text((x, w * 0.60), c, font=cap, fill=(20, 20, 22), anchor="ls"); x += d.textlength(c, font=cap) + sp
    return b


def tall(im):
    """A 3:4 slide centred on a 9:16 frame, for the video version."""
    bg = ImageOps.fit(im, (W, H), Image.BILINEAR).filter(ImageFilter.GaussianBlur(40)); bg.paste(im, (0, (H - SH) // 2)); return bg




NICK = {"stone island": "Stoney", "ralph lauren": "Ralph", "polo ralph lauren": "Ralph", "moncler": "Moncler", "louis vuitton": "LV",
        "golden goose": "GGDB", "canada goose": "Canada Goose", "the north face": "TNF", "loro piana": "Loro"}


def brand(x):
    """The brand of a described shot, ignoring our own "puro classico" stamp that is baked into many exported photos."""
    b = (x.get("b") or "").strip()
    return "" if "puro" in b or "classico" in b or b in ("unknown", "none", "n/a") else b


def plain_label(a, b):
    """A label from the stored descriptions when the model's answer is unusable: "Stoney Half-Zip Knits", "Puffer Jackets"."""
    try: d = json.load(open(ITEMS_FILE))
    except Exception: return ""
    p, q = d.get(a.info.get("sid", ""), {}), d.get(b.info.get("sid", ""), {})
    if not p.get("i") or p.get("i") != q.get("i") or p["i"] == "other": return ""
    item = p["i"].title().replace("T-Shirt", "Tee"); item = item + ("" if item.endswith("s") else "es" if item.endswith(("sh", "ch")) else "s")
    br = brand(p) if brand(p) and brand(p) == brand(q) else ""
    t = ((NICK.get(br) or br.title()) + " " + item).strip() if br else item
    return t if len(t) <= 26 else item


def usable(t):
    return bool(t) and 2 <= len(t) <= 26 and not any(c in t for c in ",/\n") and not any(w in t.lower() for w in (" and ", " & ", "puro"))


def pair_label(a, b):
    """A short casual name for the two items on a slide, like "Stoney Half-Zips" or "Moncler Puffers", asked once of OpenAI
    and stored in scripts/qc_labels.json. It only names a brand it can read on the item; otherwise it names the item.
    Empty (no label) without OPENAI_API_KEY or when the call fails."""
    ka, kb = a.info.get("sid", ""), b.info.get("sid", ""); k = "|".join(sorted([ka, kb]))
    try: known = json.load(open(LABELS_FILE))
    except Exception: known = {}
    if ka and kb and k in known: return known[k] if usable(known[k]) else plain_label(a, b)
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key: return ""
    try:
        import base64, io
        def enc(im):
            t = im.copy(); t.thumbnail((512, 512)); buf = io.BytesIO(); t.convert("RGB").save(buf, "JPEG", quality=85)
            return {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode(), "detail": "low"}}
        body = {"model": "gpt-4o-mini", "max_tokens": 12, "temperature": 0.3, "messages": [{"role": "user", "content": [
            {"type": "text", "text": "Two quality-check photos of fashion items for a TikTok slide. Write a short casual label for both together, 2 to 4 words, "
             "the way young guys say it, plural when it fits: e.g. 'Stoney Half-Zips', 'Moncler Puffers', 'Ralph Knits', 'Burberry Scarves', 'Rimowa Cases'. "
             "Use common nicknames (Stone Island = Stoney, Ralph Lauren = Ralph). Ignore the round 'puro classico' stamp in the corner, it is not a brand. Only name a brand you can clearly see on a logo, patch or tag; "
             "if the two items are different brands or you are not sure, name the item instead ('Grey Puffers', 'Zip Knits'). Never invent a collab. "
             "One label for both, never two names, no commas. Answer with the label only, no quotes."}, enc(a), enc(b)]}]}
        req = urllib.request.Request("https://api.openai.com/v1/chat/completions", data=json.dumps(body).encode(),
                                     headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
        t = json.load(urllib.request.urlopen(req, timeout=60))["choices"][0]["message"]["content"].strip().strip("'\".").replace("\u2014", "-")
        t = t if usable(t) else ""
    except Exception as e:
        print("  could not label a slide:", str(e)[:80]); return ""
    if t and ka and kb:
        known[k] = t; json.dump(known, open(LABELS_FILE, "w"), indent=0, sort_keys=True, ensure_ascii=False)
    return t or plain_label(a, b)


ITEMS = ["puffer jacket", "down vest", "quilted jacket", "field jacket", "bomber jacket", "leather jacket", "track jacket", "overshirt",
         "coat", "blazer", "half-zip knit", "crewneck knit", "cable knit", "cardigan", "knit polo", "hoodie", "zip hoodie", "sweatshirt",
         "fleece", "polo shirt", "rugby shirt", "button shirt", "t-shirt", "chinos", "jeans", "sweatpants", "shorts", "swim shorts",
         "loafers", "sneakers", "boots", "dress shoes", "slides", "cap", "beanie", "scarf", "belt", "wallet", "bag", "watch",
         "sunglasses", "jewellery", "suitcase", "other"]


def describe(shots):
    """What each shot shows, {"i": item from ITEMS, "b": brand, "c": main colour}, from scripts/qc_items.json; unknown shots are
    asked once of OpenAI (a small thumbnail, gpt-4o-mini) and the answer is stored. Unknown or failed: item "other"."""
    try: known = json.load(open(ITEMS_FILE))
    except Exception: known = {}
    key = os.environ.get("OPENAI_API_KEY", "").strip(); out, new = {}, 0
    for sid, im in shots:
        if sid in known: out[sid] = known[sid]; continue
        if not key: out[sid] = {"i": "other", "b": "", "c": ""}; continue
        try:
            import base64, io
            t = im.copy(); t.thumbnail((512, 512)); buf = io.BytesIO(); t.convert("RGB").save(buf, "JPEG", quality=85)
            body = {"model": "gpt-4o-mini", "max_tokens": 40, "temperature": 0, "response_format": {"type": "json_object"}, "messages": [{"role": "user", "content": [
                {"type": "text", "text": "A quality-check photo of one fashion item. Reply as JSON {\"item\": ..., \"brand\": ..., \"colour\": ...}. "
                 "item: exactly one of " + ", ".join(ITEMS) + ". brand: the brand only if you can read it on a logo, patch or tag of the item, lowercase, else \"\" (the round 'puro classico' stamp in the corner is not a brand). "
                 "colour: the main colour in one word."},
                {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode(), "detail": "low"}}]}]}
            req = urllib.request.Request("https://api.openai.com/v1/chat/completions", data=json.dumps(body).encode(),
                                         headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
            j = json.loads(json.load(urllib.request.urlopen(req, timeout=60))["choices"][0]["message"]["content"])
            it = str(j.get("item", "")).strip().lower()
            out[sid] = known[sid] = {"i": it if it in ITEMS else "other", "b": str(j.get("brand", "")).strip().lower()[:30],
                                     "c": str(j.get("colour", "")).strip().lower()[:15]}; new += 1
        except Exception as e:
            print("  could not describe a photo:", str(e)[:80]); out[sid] = {"i": "other", "b": "", "c": ""}
    if new:
        json.dump(known, open(ITEMS_FILE, "w"), indent=0, sort_keys=True, ensure_ascii=False); print("  described %d new photos" % new)
    return out


def kind(item):
    """The broad kind of an item, for a fallback pair when no two of the same item are at hand."""
    for k, words in (("outer", ("jacket", "vest", "coat", "blazer", "overshirt", "fleece")), ("knit", ("knit", "cardigan")),
                     ("top", ("hoodie", "sweatshirt", "shirt", "polo")), ("bottom", ("chinos", "jeans", "pants", "shorts")),
                     ("shoes", ("loafers", "sneakers", "boots", "shoes", "slides"))):
        if any(w in item for w in words): return k
    return item


def pick_pairs(ims, n, rnd):
    """n slides of two alike shots: the same item first (two half-zip knits, two puffers), ideally the same brand in
    different colours; only when that runs out, the same kind of thing. ims is in least-used order and the least-used
    shots are placed first. The two halves of one source photo (already a pair) are next best. Returns (pairs, unused shots)."""
    sid = lambda x: x[1].info.get("sid") or x[0]
    d = describe([(sid(x), x[1]) for x in ims])
    def score(x, y):
        if x[0] == y[0]: return 9                             # the two halves of one photo: already a matching pair, used when no fresh one is left
        p, q = d.get(sid(x), {}), d.get(sid(y), {}); s = 0
        if p.get("i") == q.get("i") and p.get("i") not in (None, "other"): s += 10
        elif kind(p.get("i") or "other") == kind(q.get("i") or "other") and p.get("i") != "other": s += 3
        if brand(p) and brand(p) == brand(q): s += 4
        if p.get("c") and q.get("c") and p.get("c") != q.get("c"): s += 1
        return s
    left, pairs = list(ims), []
    for need in (14, 10, 3, 0):                                 # same item and brand, same item, same kind, anything
        k = 0
        while k < len(left) and len(pairs) < n:
            x = left[k]; best = max(left[k + 1:], key=lambda y: score(x, y), default=None)
            if best is not None and score(x, best) >= need:
                pairs.append((x, best)); left.remove(best); left.pop(k)
            else: k += 1
    rnd.shuffle(pairs)
    return [x for p in pairs for x in p], left


def owner(pid):
    """Which TikTok account a photo belongs to (1 or 2). A fixed rule on its id: the two accounts never show the same photo,
    and photos added later are split the same way with no list to keep. One third goes to the second account."""
    return 2 if int(hashlib.md5(pid.encode()).hexdigest(), 16) % 3 == 0 else 1


def never(paths):
    """Ids that must not be used, from the given files: a plain list of ids, or the other account's usage record."""
    out = set()
    for p in [x.strip() for x in (paths or "").split(",") if x.strip()]:
        try: j = json.load(open(os.path.join(ROOT, p)))
        except Exception: continue
        if isinstance(j, list): out |= set(j)
        else: out |= {k for k, v in (j.get("count") or {}).items() if v} | set(j.get("covers") or {})
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--folder"); ap.add_argument("--local"); ap.add_argument("--audio"); ap.add_argument("--cover"); ap.add_argument("--covers", help="Drive folder of start pictures (one is picked per post, least used first)")
    ap.add_argument("--slides", type=int, default=7); ap.add_argument("--title", default=""); ap.add_argument("--part", type=int, default=0)
    ap.add_argument("--hold", type=float, default=2.2); ap.add_argument("--out", default=os.path.join(ROOT, "out")); ap.add_argument("--seed", type=int)
    ap.add_argument("--video", action="store_true", help="a full-screen 9:16 video of the slides instead of a photo carousel")
    ap.add_argument("--qc-cover", action="store_true", help="the start picture is one of the QC photos, so the post shows QC photos only")
    ap.add_argument("--own", type=int, default=0, help="only photos that belong to this TikTok account (1 or 2); 0 = all")
    ap.add_argument("--state", default="finds_used.json", help="this account's usage record")
    ap.add_argument("--avoid", default="", help="files with ids never to use (the other account's record, a list)")
    ap.add_argument("--single", action="store_true", help="one photo on each slide instead of two stacked")
    ap.add_argument("--text", default="", help="json with the caption lines and hashtag groups for this account")
    ap.add_argument("--badge", action="store_true", help="the second account's 'puro classico / HARDEST FINDS' badge in the corners of every photo")
    ap.add_argument("--commit-state", action="store_true"); a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)
    rnd = random.Random(a.seed)
    if a.local: pool = [(hashlib.md5(open(f, "rb").read()).hexdigest(), f) for f in sorted(glob.glob(os.path.join(a.local, "*"))) if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))]
    else: pool = drive_images(a.folder)
    pool = list(dict(pool).items()); state_path = os.path.join(ROOT, a.state); no_go = never(a.avoid)
    if a.own: pool = [p for p in pool if owner(p[0]) == a.own]
    pool = [p for p in pool if p[0] not in no_go]
    try: used = json.load(open(state_path))
    except Exception: used = {"count": {}, "part": 0}
    need = (a.slides if a.single else a.slides * 2) + (1 if a.qc_cover else 0)             # one more photo when the start picture is a QC photo too
    if len(pool) < need: raise SystemExit("only %d photos in the pool, need %d" % (len(pool), need))
    rnd.shuffle(pool); pool.sort(key=lambda p: used["count"].get(p[0], 0))          # least-used photos first, in random order among equally used ones
    bad = set(used.get("skip", [])); ims = []                   # photos that could not be used are remembered, not retried
    for pid, path in [p for p in pool if p[0] not in bad]:
        if len(ims) >= (need if a.single else need * 4): break       # pairs need a choice: look at four times as many shots
        path = path or drive_get(pid, "img")
        try:
            parts = split_stacked(Image.open(path).convert("RGB"))
            if parts is None: print("  skipping an oddly laid out photo"); bad.add(pid); continue      # the join is not in the middle
            for n, im in enumerate(parts):
                mx = int(im.width * 0.012); c = im.crop((mx, mx, im.width - mx, im.height - mx))        # only a hair off the edges
                c.info["sid"] = "%s:%d" % (pid, n); ims.append((pid, c))                                  # a stable id per shot, for its item type
        except Exception as e: print("  skipping a photo:", e)
    used["skip"] = sorted(bad)
    if len(ims) < need:                                         # never publish a post with missing slides
        if a.commit_state: json.dump(used, open(state_path, "w"), indent=0)
        raise SystemExit("only %d usable photos, need %d" % (len(ims), need))
    if a.single:
        ims = ims[:need]; rnd.shuffle(ims); cover = [ims.pop()] if a.qc_cover else []
    else:
        ims, rest = pick_pairs(ims, a.slides, rnd); cover = rest[:1] if a.qc_cover else []
        if len(ims) < a.slides * 2: raise SystemExit("could not make %d slides" % a.slides)
    picked = sorted({pid for pid, _ in ims + cover}); qc_bg = cover[0][1] if cover else None
    part = a.part or int(used.get("part", 0)) + 1
    title = a.title or COVER_TEXT                               # the cover always says the same; the caption hook and tags vary
    hook = (rnd.choice(HOOKS) % title.lower()).replace("{part}", str(part))
    caption = "%s\n\n%s" % (hook[0].upper() + hook[1:], " ".join(["#grisch", "#oldmoney"] + rnd.sample(TAGS, 1)))
    if a.text:                                                   # this account's own lines: none repeats within ten posts; five tags (TikTok's limit)
        T = json.load(open(os.path.join(ROOT, a.text), encoding="utf-8")); recent = used.get("texts", [])[-10:]
        line = rnd.choice([t for t in T["lines"] if t not in recent] or T["lines"])
        season = ["winter", "winter", "spring", "spring", "spring", "summer", "summer", "summer", "autumn", "autumn", "autumn", "winter"][datetime.now().month - 1]
        head = line.replace("{n}", str(len(ims))).replace("{part}", str(part)).replace("{season}", season)
        caption = "%s\n\n%s" % (head[0].upper() + head[1:], " ".join(T["core"]))            # three tags, nothing else
        used["texts"] = (used.get("texts", []) + [line])[-20:]
    FW, FH = (W, H) if a.video else (SW, SH)                     # video slides fill the 9:16 screen; carousel slides are 3:4
    bg, cover_id = None, None
    if qc_bg is not None: bg = qc_bg
    elif a.cover and drive_get(a.cover, "img"): bg = Image.open(drive_get(a.cover, "img"))
    elif a.covers:                                               # a start picture from the folder, least used first
        cu = used.setdefault("covers", {}); cl = [i for i, t in drive_list(a.covers) if t.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))]
        try: no = set(json.load(open(os.path.join(ROOT, "scripts", "finds_covers_skip.json"))))      # pictures screened out as start pictures (watermarks, words on them, too small...)
        except Exception: no = set()
        cl = [i for i in cl if i not in no and i not in no_go and (not a.own or owner(i) == a.own)]
        rnd.shuffle(cl); cl.sort(key=lambda i: cu.get(i, 0))
        for cid in cl[:6]:
            try: bg = Image.open(drive_get(cid, "img")); bg.load(); cover_id = cid; break
            except Exception as e: bg = None; print("  skipping a start picture:", e)
    last = used.get("look") or [-1, -1]                          # a different font and arrow style than the post before
    look = [rnd.choice([k for k in range(len(COVER_FONTS)) if k != last[0]]), rnd.choice([k for k in range(len(ARROWS)) if k != last[1]])]
    used["look"] = look
    frames = [(cover_card(title, FW, FH, bg, look), min(1.4, max(0.9, a.hold * 1.4)))]      # the start picture stays a little longer than a slide
    if a.single:
        for _, im in ims: frames.append((whole(im, FW, FH), a.hold))
    else:
        badge = make_badge(int(FW * 0.15)) if a.badge else None
        for k in range(0, len(ims) - 1, 2): frames.append((slide(ims[k][1], ims[k + 1][1], FW, FH, badge, pair_label(ims[k][1], ims[k + 1][1]) if LABELS else ""), a.hold))
    total = sum(d for _, d in frames); out = os.path.join(a.out, "finds-%d.mp4" % part); audio = drive_get(a.audio, "mp3") if a.audio else None
    cmd = [FF, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W, H), "-r", str(FPS), "-i", "-"]
    cmd += ["-stream_loop", "-1", "-i", audio, "-af", "afade=t=out:st=%.2f:d=0.6" % (total - 0.7)] if audio else ["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100"]
    cmd += ["-t", "%.3f" % total, "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", out]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for im, d in frames:
        raw = (im if a.video else tall(im)).tobytes()
        for _ in range(int(round(d * FPS))): p.stdin.write(raw)
    p.stdin.close(); p.wait()
    imgs = []                                                    # the same slides as JPEGs, for a swipeable photo carousel
    for k, (im, _) in enumerate([] if a.video else frames):
        ip = os.path.join(a.out, "finds-%d-%02d.jpg" % (part, k)); im.save(ip, quality=96, subsampling=0, optimize=True); imgs.append(ip)
    meta = {"format": "finds", "images": imgs, "ids": [], "caption": caption,
            "seconds": round(total, 1), "voiceover": False, "file": out, "product_url": "https://www.puroclassico.com/"}
    json.dump(meta, open(out[:-4] + ".json", "w"), indent=1, ensure_ascii=False)
    print("wrote", out, "%.1fs" % total, len(frames) - 1, "slides", "with sound" if audio else "silent")
    if a.commit_state:
        for pid in picked: used["count"][pid] = used["count"].get(pid, 0) + 1
        if cover_id: used["covers"][cover_id] = used["covers"].get(cover_id, 0) + 1
        used["part"] = part; json.dump(used, open(state_path, "w"), indent=0)


if __name__ == "__main__":
    main()
