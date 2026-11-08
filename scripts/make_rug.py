# -*- coding: utf-8 -*-
"""Rug slides (preview only): the item from a QC photo, re-shot by an image model as if it lies on the owner's
Maison Margiela rug. Small things are close-ups, shoes and jackets get a natural angle that changes per slide.
Only items that fit the look: accessories, shoes, jackets (and bottles once they are labelled).

  python scripts/make_rug.py --out rug-out [--n 6] [--seed 1] [--own 2]

A carousel: the boxes photo with a yellow hook (a different one each time), then n item slides, each with the item's
name and an estimated price in yellow. Prices are the median of matching finds on the site (functions/_lib/catalog.js).
Env: OPENAI_API_KEY. Writes rug-out/NN-*.jpg (1080x1920), the QC photo each came from, and log.json (with the cost).
"""
import argparse, base64, hashlib, unicodedata, json, os, random, re, html, statistics, sys, time, urllib.request, urllib.error, uuid, io
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUG = os.path.join(ROOT, "scripts", "rug", "rug.jpg")
BOXES = os.path.join(ROOT, "scripts", "rug", "boxes.jpg")
YELLOW = (252, 250, 190)                                   # TikTok's pale caption yellow (owner's reference, 22 Oct 2026)
TTS = os.path.join(ROOT, "scripts", "fonts", "TikTokSans.ttf")   # TikTok Sans (OFL), the app's own caption font
FOLDER = "10IZ-ip4UjlEy5UMyhXaznvjsfSYZeH6L"
# The site's own QC photos (owner, 4 Nov 2026: "use the photos from our sheet"): the thumbnails scripts/qc_bank.py stored in
# our Supabase storage, listed in data/qc_bank.json. They take turns with the Drive photos. Only the second account uses
# them (the main account's carousels read the Drive folder only), so the two accounts still never share a photo.
SITE_QC = "https://uptpghuduqjqmrxwatbm.supabase.co/storage/v1/object/public/products/qc/%s-%s-%d.webp"
SITE_ON = os.environ.get("RUG_SITE", "1") == "1"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"}
ENGINE = os.environ.get("RUG_ENGINE", "gemini" if os.environ.get("GEMINI_API_KEY") else "openai")     # "gemini" (Google, about $0.04 an image) or "openai"
MODELS = [m for m in os.environ.get("RUG_MODELS", "gemini-2.5-flash-image" if ENGINE == "gemini" else "gpt-image-2,gpt-image-1.5,gpt-image-1").split(",") if m]
SOURCE = os.environ.get("RUG_SOURCE", "pop")     # "pop": only the site's most popular finds (owner, 8 Nov 2026: "the most popular items from the spreadsheet"); "mix": owner's picks, QC photos and Drive
MULTI_ON = os.environ.get("RUG_MULTI", "1") == "1"     # several items on one slide (owner, 22 Oct 2026); "0" = one item per slide
GEMINI = "https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent"

SMALL = {"watch", "sunglasses", "wallet", "belt", "jewellery", "cap", "beanie", "bottle"}
SHOES = {"sneakers", "loafers", "boots", "dress shoes", "slides"}
BAGS = {"bag", "suitcase"}
JACKETS = {"puffer jacket", "down vest", "quilted jacket", "field jacket", "bomber jacket", "leather jacket", "coat", "track jacket"}
FITS = SMALL | SHOES | BAGS | JACKETS | {"other"}          # "other" may be a bottle: the check below decides

ANGLES = {                                                   # the owner's verdict (22 Oct 2026): only the standing view of image 1 looks real; close-ups and low angles look AI
    "small": ["the same standing viewpoint as image 1 but one small step closer, the item in the middle of the rug with several rug numbers around it"],
    "shoes": ["the same standing viewpoint as image 1, the pair side by side on the rug, one shoe turned a little"],
    "bags": ["the same standing viewpoint as image 1, the bag lying or standing in the middle of the rug"],
    "jackets": ["the same standing viewpoint as image 1, the jacket laid flat on the rug, sleeves loose and natural"],
    "several": ["the same standing viewpoint as image 1, the items spread over the middle of the rug"],
}


def group(t):
    return "small" if t in SMALL else "shoes" if t in SHOES else "bags" if t in BAGS else "jackets"


MULTI = {"small": 3, "shoes": 2, "bags": 2, "jackets": 1}       # items per slide (owner, 22 Oct 2026: several accessories or shoes together; one jacket fills the rug)


def prompt(items, angle, product=False):
    """items: the item words of one slide, in the order of their photos (images 2, 3, ...). product: shop photos, not QC photos."""
    src1 = "shop product photo on a plain background" if product else "quality-check photo on a green mat"
    srcn = "shop product photos on a plain background" if product else "quality-check photos on a green mat"
    n = len(items); shoes = sum(1 for t in items if re.search(r"sneaker|shoe|loafer|boot|slide", t))
    if n == 1:
        what = "Image 2 is a %s of one %s. Edit image 1: put that exact %s on the rug, %s. " % (src1, items[0], items[0], angle)
        count = "Exactly one item; for shoes exactly one pair, two shoes, never three. "
    else:
        what = ("Images 2 to %d are %s of %d different items: %s. Edit image 1: lay all %d items on the rug together like a haul I am showing off, "
                "side by side with a little space between them so each one is fully visible, %s. " % (n + 1, srcn, n, ", ".join("image %d: %s" % (k + 2, t) for k, t in enumerate(items)), n, angle))
        count = "Exactly these %d items, each exactly once%s, nothing else. " % (n, "; shoes come as pairs, so exactly %d shoes in total" % (2 * shoes) if shoes else "")
    return ("Image 1 is a photo of my cream Maison Margiela rug (black numbers 0 to 23, 'Maison Margiela PARIS') on the wooden floor of my room, taken standing up with my iPhone. "
            + what + "Keep everything else of image 1: the same camera position, height and angle, the same room, light and colours. "
            "It must look like a plain photo from my camera roll, not an ad, not a render and not a close-up: natural light, a real soft shadow under each item, "
            "natural creases in the fabric, real rug fibres, a little iPhone noise. "
            "Keep every item exactly as in its photo: the same shape, colours, materials, logos, text, stitching and hardware. Never add, move or invent a logo or text. "
            "Real sizes on the rug. " + count +
            "No feet, legs, hands or people. No green mat, no ruler, no round stamp, no other objects. Vertical 9:16 photo.")


JUDGE = ("Image 1 is the real photo of my room: a rug, a wooden floor, white drawers and a hanging plant. Images 2 to {last} are quality-check photos of {n} fashion item(s). "
         "Image {res} is a photo made from them for TikTok: the item(s) placed on the rug of image 1. Compare image {res} with the quality-check photos for the items and with image 1 for the room. Reply as JSON "
         "{{\"same_item\": true/false, \"logos_ok\": true/false, \"count_ok\": true/false, \"no_people\": true/false, \"no_extra\": true/false, "
         "\"standing_view\": true/false, \"real_photo\": 1-10, \"why\": \"...\"}}. same_item: every item from the quality-check photos is in image {res} and matches its photo (shape, colours, materials). "
         "logos_ok: logos and text match the photos and none are invented. count_ok: exactly {n} item(s), each once; shoes as pairs (two shoes per pair, never three). "
         "no_people: no feet, legs, hands or people. no_extra: nothing was added that is not in image 1 or the quality-check photos (the room's plant, drawers and floor are fine). "
         "standing_view: shot from standing height looking down at the rug like image 1, with every item fully in view, not a close-up and not a low or dramatic angle. "
         "real_photo: how much image {res} looks like a plain iPhone photo from someone's camera roll (10) versus AI, a render or an ad (1). Be strict.")


def judge(shots, png):
    """A strict second look at a made image (Gemini Flash): True when it may be posted. The owner's slop rules (22 Oct 2026)."""
    if ENGINE != "gemini": return True, "no judge"
    enc = lambda im: {"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(jpeg(im, 768)).decode()}}
    try:
        text = JUDGE.format(n=len(shots), last=len(shots) + 1, res=len(shots) + 2)
        j = gemini(os.environ.get("RUG_CHECK_MODEL") or newest_flash(), [{"text": text}, enc(Image.open(RUG))] + [enc(x) for x in shots] + [enc(Image.open(io.BytesIO(png)))],
                   {"responseMimeType": "application/json", "temperature": 0}, 90)
        v = json.loads(j["candidates"][0]["content"]["parts"][0]["text"])
    except Exception as e: return True, "judge failed: %s" % str(e)[:80]          # never block on a broken judge; the owner still reviews the draft
    ok = all(v.get(k) for k in ("same_item", "logos_ok", "count_ok", "no_people", "no_extra", "standing_view")) and int(v.get("real_photo") or 0) >= 6
    return ok, json.dumps(v)[:300]


def fetch(url, timeout=120):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout).read()


def drive_ids():
    out = []
    def walk(f, depth=0):
        h = fetch("https://drive.google.com/embeddedfolderview?id=%s#list" % f, 60).decode("utf-8", "ignore")
        for i, t in re.findall(r'id="entry-([A-Za-z0-9_-]{20,})".*?class="flip-entry-title">(.*?)</div>', h, re.S):
            t = html.unescape(t)
            if t.lower().endswith((".png", ".jpg", ".jpeg", ".webp")): out.append(i)
            elif "." not in t and depth < 2: walk(i, depth + 1)
    walk(FOLDER); return set(out)


def jpeg(im, side=1024):
    im = im.convert("RGB"); im.thumbnail((side, side)); b = io.BytesIO(); im.save(b, "JPEG", quality=92); return b.getvalue()


def edit(model, images, text, fidelity=True):
    """OpenAI image edit with several input images; returns PNG bytes."""
    bd = "----rug" + uuid.uuid4().hex; parts = []
    fields = {"model": model, "prompt": text, "size": "1024x1536", "quality": os.environ.get("RUG_OPENAI_QUALITY", "medium"), "n": "1"}   # medium: about a quarter of the high price
    if fidelity: fields["input_fidelity"] = "high"
    for k, v in fields.items(): parts.append(('--%s\r\nContent-Disposition: form-data; name="%s"\r\n\r\n%s\r\n' % (bd, k, v)).encode())
    for n, data in enumerate(images):
        parts.append(('--%s\r\nContent-Disposition: form-data; name="image[]"; filename="in%d.jpg"\r\nContent-Type: image/jpeg\r\n\r\n' % (bd, n)).encode() + data + b"\r\n")
    body = b"".join(parts) + ("--%s--\r\n" % bd).encode()
    req = urllib.request.Request("https://api.openai.com/v1/images/edits", data=body, method="POST",
                                 headers={"Authorization": "Bearer " + os.environ["OPENAI_API_KEY"], "Content-Type": "multipart/form-data; boundary=" + bd})
    with urllib.request.urlopen(req, timeout=300) as r: j = json.load(r)
    return base64.b64decode(j["data"][0]["b64_json"]), j.get("usage") or {}


class NoCredit(RuntimeError): pass


def to_openai(why):
    """Gemini has no credit left (HTTP 402): finish this run with OpenAI so the drafts keep coming (5 Nov 2026). The next
    run tries Gemini again, so topping up the Gemini account switches back by itself."""
    global ENGINE, MODELS
    if not os.environ.get("OPENAI_API_KEY"): return False
    if ENGINE == "gemini":                                   # several checks run at once: only the first one switches
        print("  GEMINI OUT OF CREDIT (%s): using OpenAI for this run" % re.sub(r"\s+", " ", why)[:300])
        ENGINE = "openai"; MODELS = [m for m in os.environ.get("RUG_FALLBACK_MODELS", "gpt-image-2,gpt-image-1.5,gpt-image-1").split(",") if m]
    return True


def gemini(model, parts, config, timeout=150):
    if "responseMimeType" in config and "thinkingConfig" not in config:       # the quick yes/no checks: little thinking, so they take seconds
        try: return gemini(model, parts, dict(config, thinkingConfig={"thinkingLevel": "low"}), timeout)
        except RuntimeError as e:
            if "HTTP 400" not in str(e): raise
    body = {"contents": [{"role": "user", "parts": parts}], "generationConfig": config}
    req = urllib.request.Request(GEMINI % model, data=json.dumps(body).encode(), method="POST",
                                 headers={"x-goog-api-key": os.environ["GEMINI_API_KEY"], "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r: return json.load(r)
    except urllib.error.HTTPError as e:
        msg = e.read().decode("utf-8", "replace")[:300]
        if e.code == 402 or "credits are depleted" in msg: raise NoCredit("HTTP %s %s" % (e.code, msg))
        raise RuntimeError("HTTP %s %s" % (e.code, msg))


_FLASH = None


def newest_flash():
    """The newest plain Gemini Flash text model this key can use (older ones are retired for new users)."""
    global _FLASH
    if _FLASH: return _FLASH
    try:
        r = urllib.request.Request("https://generativelanguage.googleapis.com/v1beta/models?pageSize=300", headers={"x-goog-api-key": os.environ["GEMINI_API_KEY"]})
        names = [m["name"].split("/")[-1] for m in json.load(urllib.request.urlopen(r, timeout=60))["models"]]
        flash = [n for n in names if re.fullmatch(r"gemini-\d+(\.\d+)?-flash", n)]
        _FLASH = max(flash, key=lambda n: float(re.findall(r"\d+(?:\.\d+)?", n)[0])) if flash else "gemini-flash-latest"
    except Exception as e: print("  could not list Gemini models:", str(e)[:100]); _FLASH = "gemini-flash-latest"
    print("  item check model:", _FLASH); return _FLASH


def gemini_image(model, images, text):
    parts = [{"text": text}] + [{"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(d).decode()}} for d in images]
    j = gemini(model, parts, {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": "9:16"}})
    for p in ((j.get("candidates") or [{}])[0].get("content") or {}).get("parts", []):
        d = p.get("inlineData") or p.get("inline_data")
        if d and d.get("data"): return base64.b64decode(d["data"]), j.get("usageMetadata") or {}
    raise RuntimeError("no image in the reply: %s" % json.dumps(j)[:200])


def generate(images, text, models=None):
    if ENGINE == "gemini":
        for m in models or MODELS:
            for attempt in range(3):
                try: png, use = gemini_image(m, images, text); return png, m, use
                except NoCredit as e:
                    if to_openai(str(e)): return generate(images, text)
                    return None, None, {}
                except Exception as e:
                    print("  %s: %s" % (m, str(e)[:200]))
                    if "429" in str(e) or "503" in str(e) or "timed out" in str(e): time.sleep(10 * (attempt + 1)); continue
                    break
        return None, None, {}
    for m in models or MODELS:
        for fid in (True, False):
            try: png, use = edit(m, images, text, fid); return png, m, use
            except urllib.error.HTTPError as e:
                msg = e.read().decode("utf-8", "replace")[:200]; print("  %s (fidelity %s): HTTP %s %s" % (m, fid, e.code, msg))
                if "insufficient_quota" in msg or "billing" in msg: return None, None, {}
                if e.code == 429: time.sleep(20)
            except Exception as e: print("  %s: %s" % (m, str(e)[:120]))
    return None, None, {}


CHECK = ("A quality-check photo of a fashion find on a green mat (it may show the item twice). Reply as JSON "
         "{\"fits\": true/false, \"clear\": true/false, \"group\": \"small|shoes|bags|jackets\", \"item\": ..., \"brand\": ..., \"name\": ...}. "
         "fits: true for shoes, jackets, vests, coats, bags, suitcases, normal wristwatches (any brand, metal or leather strap), sunglasses, belts, wallets, cardholders, jewellery, caps, perfume or cologne bottles; "
         "false for clothing that is not outerwear, electronics or tech of any brand (smartwatches, Apple Watch with a custom face, phones, cameras, glasses with screens), "
         "novelty or desk items, car parts, toys, sports gear, and anything with rude, joke or offensive words on it. "
         "clear: true when the item itself is clearly visible, including a top-down view of a pair of shoes or one shoe from the side; false only when the photo shows just the soles, "
         "the inside or a box is shown. group: small for watches, sunglasses, belts, wallets, jewellery, caps and bottles. item: the item in 1 or 2 plain words "
         "(sneakers, puffer vest, duffle bag, perfume). brand: the brand whose logo, monogram, patch or signature design you can see on the item (the YSL monogram, the Ralph Lauren pony or RL, the Golden Goose star, Margiela's tape or tabi toe, the Moncler patch, the Stone Island badge), else \"\"; never guess from colour or shape alone (the round 'puro classico' stamp is not a brand). "
         "name: 2 to 3 lowercase words: that brand plus the item ('golden goose sneakers', 'ysl duffle bag', 'stone island jacket', 'burberry puffer'); "
         "with no readable brand, the colour plus the item ('white leather sneakers', 'light blue puffer'). Never filler words like cool, nice, sick, fire.")


def check(qc):
    """Is this QC photo right for a rug slide, and what is it called. One small call (Gemini Flash, or gpt-4o-mini)."""
    t = qc.convert("RGB"); t.thumbnail((768, 768)); b = io.BytesIO(); t.save(b, "JPEG", quality=85)
    if ENGINE == "gemini":
        try:
            j = gemini(os.environ.get("RUG_CHECK_MODEL") or newest_flash(), [{"text": CHECK}, {"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(b.getvalue()).decode()}}],
                       {"responseMimeType": "application/json", "temperature": 0}, 60)
        except NoCredit as e:
            if not to_openai(str(e)): raise
            return check(qc)
        return json.loads(j["candidates"][0]["content"]["parts"][0]["text"])
    body = {"model": "gpt-4o-mini", "max_tokens": 120, "temperature": 0, "response_format": {"type": "json_object"}, "messages": [{"role": "user", "content": [
        {"type": "text", "text": CHECK}, {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode(), "detail": "low"}}]}]}
    req = urllib.request.Request("https://api.openai.com/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Authorization": "Bearer " + os.environ["OPENAI_API_KEY"], "Content-Type": "application/json"})
    try: return json.loads(json.load(urllib.request.urlopen(req, timeout=60))["choices"][0]["message"]["content"])
    except urllib.error.HTTPError as e: raise RuntimeError("HTTP %s %s" % (e.code, e.read().decode("utf-8", "replace")[:300]))


_ROWS = None
CATS = {"shoes": {"Shoes"}, "jackets": {"Outerwear"}, "bags": {"Bags"}, "small": {"Accessories", "Headwear"}}
WORDS = {"sneaker": "sneaker|trainer|shoe", "vest": "vest|gilet", "puffer": "puffer|down", "jacket": "jacket", "coat": "coat", "bag": "bag|tote|duffle|backpack",
         "backpack": "backpack", "duffle": "duffle|duffel|travel", "watch": "watch", "sunglasses": "sunglass|glasses", "glasses": "glasses|sunglass",
         "belt": "belt", "wallet": "wallet|card holder|cardholder", "cap": "cap", "perfume": "perfume|cologne|fragrance", "slides": "slide", "loafer": "loafer", "boots": "boot"}


def price(brand, item, grp):
    """Estimated USD price: the median of the site's finds of this brand and kind, then of this kind only. None when the site has nothing close."""
    global _ROWS
    if _ROWS is None:
        t = open(os.path.join(ROOT, "functions", "_lib", "catalog.js"), encoding="utf-8").read(); i = t.index("export const ROWS = ") + 20
        _ROWS = json.loads(t[i:t.index("];", i) + 1])
    if grp is None: return None
    words = "|".join(v for k, v in WORDS.items() if k in (item or "").lower())
    rows = [r for r in _ROWS if r[3] in CATS.get(grp, set()) and isinstance(r[6], (int, float)) and r[6] > 0]
    kw = [r for r in rows if words and re.search(words, r[1], re.I)]
    br = lambda rs: [r for r in rs if brand and brand.lower() in r[2].lower()]
    for pool, need in ((br(kw), 2), (br(rows), 3), (kw, 5)):
        if len(pool) >= need:                                   # the cheaper end of what the site has (owner: lower prices), never below the cheapest find
            p = sorted(r[6] for r in pool); return max(1, int(round(p[len(p) // 4])))
    return None


COVER_FONTS = [("Anton-Regular.ttf", None), ("BebasNeue-Regular.ttf", None), ("ArchivoBlack-Regular.ttf", None), ("Oswald.ttf", 700),
               ("BowlbyOneSC-Regular.ttf", None), ("RussoOne-Regular.ttf", None), ("PassionOne-Bold.ttf", None), ("Montserrat.ttf", 900)]
HOOKS = ["hardest grisch finds", "my last haul was crazy", "old money haul", "what i ordered this month", "rate this haul 1-10",
         "stockholm style haul", "the whole haul was ${total}", "{n} finds you need", "grisch haul, nothing over ${max}", "best finds i ordered"]


def font(k, size):
    name, w = COVER_FONTS[k % len(COVER_FONTS)]; f = ImageFont.truetype(os.path.join(ROOT, "scripts", "fonts", name), size)
    if w:
        try: f.set_variation_by_axes([w])
        except Exception: pass
    return f


def tt(size, weight=560):
    f = ImageFont.truetype(TTS, size)
    try: f.set_variation_by_axes([36, 100, weight, 0])
    except Exception: pass
    return f


def lines_of(text, f, maxw, d):
    out, cur = [], ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if cur and d.textlength(t, font=f) > maxw: out.append(cur); cur = w
        else: cur = t
    return out + ([cur] if cur else [])


def caption(im, text, cy=None, size=72, width=0.78):
    """TikTok-style text: pale yellow TikTok Sans, centred lines, a soft dark shadow, no outline. Its middle sits at cy (the screen middle by default)."""
    d = ImageDraw.Draw(im); W, H = im.size; f = tt(size); rows = []
    while size > 46 and max(d.textlength(p, font=f) for p in text.split("\n")) > W * width: size -= 2; f = tt(size)      # each item stays on one line
    for part in text.split("\n"): rows += lines_of(part, f, W * width, d)
    lh = int(size * 1.22); y = int((cy or H / 2) - lh * len(rows) / 2)
    sh = Image.new("RGBA", im.size, (0, 0, 0, 0)); ds = ImageDraw.Draw(sh)
    for k, r in enumerate(rows): ds.text((W / 2 + 2, y + k * lh + 3), r, font=f, fill=(0, 0, 0, 215), anchor="ma")
    im = Image.alpha_composite(im.convert("RGBA"), sh.filter(ImageFilter.GaussianBlur(2.2))).convert("RGB"); d = ImageDraw.Draw(im)
    for k, r in enumerate(rows): d.text((W / 2, y + k * lh), r, font=f, fill=YELLOW, anchor="ma")
    return im


EMOJI = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"          # apt: fonts-noto-color-emoji
MAINS = ["{kg}KG Unique {season} Haul unboxing", "Unboxing my {kg}KG {season} haul", "{kg}KG Old Money Haul unboxing",
         "My {kg}KG {season} haul finally came", "{kg}KG Grisch Haul unboxing", "{kg}KG {season} Haul, all grisch"]
SIDES = ["Old Money& Grisch Style", "Stockholm Style", "Quiet luxury only", "Grisch season", "Old money only", "Grisch & Old Money"]
EMOJIS = ["\U0001F342\U0001F3CC\U0001F37E", "⛳\U0001F942", "\U0001F342⛳\U0001F37E", "\U0001F40E\U0001F942", "\U0001F3BE\U0001F342", "\U0001F3CC\U0001F942"]
SIDE_EMOJI = ["\U0001F40E", "⛳", "\U0001F942", "\U0001F531"]      # no hearts or soft emojis (owner, 22 Oct 2026)


def season():
    return ["Winter", "Winter", "Spring", "Spring", "Spring", "Summer", "Summer", "Summer", "Fall/Autumn", "Fall/Autumn", "Fall/Autumn", "Winter"][time.localtime().tm_mon - 1]


def emoji_strip(chars, h):
    """Colour emojis side by side, h pixels tall (Noto Color Emoji only draws at 109 px, so scale)."""
    if not os.path.exists(EMOJI): return None
    f = ImageFont.truetype(EMOJI, 109); tiles = []
    for c in chars:
        t = Image.new("RGBA", (150, 150), (0, 0, 0, 0)); ImageDraw.Draw(t).text((10, 10), c, font=f, embedded_color=True)
        bb = t.getbbox()
        if bb: tiles.append(t.crop(bb))
    if not tiles: return None
    tiles = [x.resize((max(1, int(x.width * h / x.height)), h), Image.LANCZOS) for x in tiles]; gap = h // 6
    out = Image.new("RGBA", (sum(x.width for x in tiles) + gap * (len(tiles) - 1), h), (0, 0, 0, 0)); x = 0
    for t in tiles: out.paste(t, (x, 0), t); x += t.width + gap
    return out


def outlined(text, size, weight=700):
    """White TikTok Sans with a thin black outline and a soft shadow, as its own transparent layer."""
    f = tt(size, weight); d = ImageDraw.Draw(Image.new("RGBA", (1, 1))); w = int(d.textlength(text, font=f)) + size; h = int(size * 1.4)
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0)); sh = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(sh).text((size // 2 + 3, 5), text, font=f, fill=(0, 0, 0, 170), stroke_width=max(3, size // 16), stroke_fill=(0, 0, 0, 170))
    im = Image.alpha_composite(im, sh.filter(ImageFilter.GaussianBlur(4)))
    ImageDraw.Draw(im).text((size // 2, 2), text, font=f, fill=(255, 255, 255), stroke_width=max(3, size // 18), stroke_fill=(0, 0, 0))
    return im.crop(im.getbbox())


def cover(rnd, last=None):
    """The boxes photo with a haul line in white (a random weight, the season, emojis), >>> under it, and a tilted side text.
    The wording changes every post (owner's reference, 22 Oct 2026)."""
    im = ImageOps.fit(Image.open(BOXES).convert("RGB"), (1080, 1920), Image.LANCZOS).convert("RGBA")
    pick = [k for k in range(len(MAINS)) if k != last] or [0]; k = rnd.choice(pick)
    kg = rnd.randint(14, 34); main = MAINS[k].replace("{kg}", str(kg)).replace("{season}", season())
    d = ImageDraw.Draw(im); size = 94; f = tt(size, 700); words = main.split(); rows, cur = [], ""
    for w in words:                                            # two lines like the reference, the second one shorter
        t = (cur + " " + w).strip()
        if cur and d.textlength(t, font=f) > 1080 * 0.80: rows.append(cur); cur = w
        else: cur = t
    rows.append(cur); y = int(1920 * 0.44)
    em = emoji_strip(rnd.choice(EMOJIS), int(size * 0.95))
    for n, r in enumerate(rows):
        layer = outlined(r, size)
        if n == len(rows) - 1 and em is not None:              # the emojis follow the last line
            both = Image.new("RGBA", (layer.width + 2 + em.width, max(layer.height, em.height)), (0, 0, 0, 0))
            both.paste(layer, (0, both.height - layer.height), layer); both.paste(em, (layer.width + 2, both.height - em.height - 6), em); layer = both
        im.alpha_composite(layer, ((1080 - layer.width) // 2, y)); y += int(size * 1.22)
    arr = outlined(">>>", size)
    im.alpha_composite(arr, ((1080 - arr.width) // 2 + 60, y + 14))
    side = rnd.choice(SIDES); words = side.split(); half = (len(words) + 1) // 2
    lines = [" ".join(words[:half]), " ".join(words[half:])] if len(words) > 2 else [side]
    sz = 72; parts = [outlined(l, sz) for l in lines]
    se = emoji_strip(rnd.choice(SIDE_EMOJI), int(sz * 0.95))
    if se is not None:
        p = parts[-1]; both = Image.new("RGBA", (p.width + 6 + se.width, max(p.height, se.height)), (0, 0, 0, 0))
        both.paste(p, (0, both.height - p.height), p); both.paste(se, (p.width + 6, both.height - se.height), se); parts[-1] = both
    blk = Image.new("RGBA", (max(p.width for p in parts) + 40, sum(p.height + 8 for p in parts)), (0, 0, 0, 0)); yy = 0
    for n, p in enumerate(parts): blk.paste(p, (n * 30 if n else 50, yy), p); yy += p.height + 8
    blk = blk.rotate(-14, resample=Image.BICUBIC, expand=True)
    im.alpha_composite(blk, (90, int(1920 * 0.64)))
    return im.convert("RGB"), k, kg


def item_slide(im, name, usd, fk=0):
    """name/usd: one item (two lines: name, price) or lists for several (one line each: "name $price")."""
    if isinstance(name, list) and len(name) > 1:
        text = "\n".join(n + (" $%d" % u if u else "") for n, u in zip(name, usd)); return caption(im, text, cy=int(im.height * 0.70), size=64, width=0.9)
    else:
        n, u = (name[0], usd[0]) if isinstance(name, list) else (name, usd); text = n + ("\n$%d" % u if u else "")
    return caption(im, text, cy=int(im.height * 0.70))      # below the items, never on them (owner, 22 Oct 2026)


def top_shot(im):
    """The upper shot of a QC file that is two shots stacked (the lower one is often a different item or the box)."""
    im = im.convert("RGB"); r = im.height / float(im.width)
    if r <= 1.22: return im
    g = im.convert("L").resize((240, int(240 * r))); w, h = g.size; px = g.load(); cov, row = 0.0, h // 2
    for y in range(int(h * .40), int(h * .60)):
        c = sum(1 for x in range(w) if abs(px[x, y] - px[x, y + 1]) > 18) / float(w)
        if c > cov: cov, row = c, y + 1
    return im.crop((0, 0, im.width, int(row * im.height / float(h)))) if cov >= .5 else im


def site_cands(no):
    """The site's stored QC photos as candidates "site:<storefront>/<id>/<k>"."""
    try: items = json.load(open(os.path.join(ROOT, "data", "qc_bank.json")))["items"]
    except Exception: return []
    out = []
    for key, v in items.items():
        for k in range(int(v[1] if len(v) > 1 else 0)):
            sid = "site:%s/%d" % (key, k)
            if sid not in no: out.append((sid, "other"))
    return out


POP_N = int(os.environ.get("RUG_POP_N", "300"))


def pop_cands(no, n=None):
    """Product photos of the site's most popular finds (owner, 5 Nov 2026: "randomly of the most popular ones"), as
    candidates "pop:<id>". Popularity = views in the last 30 days + views in the last 7 + 3 x favourites (data/stats.json)."""
    try: st = json.load(open(os.path.join(ROOT, "data", "stats.json"))).get("p") or {}
    except Exception: return []
    price(None, None, None)                                    # loads _ROWS
    rows = [r for r in _ROWS if r[11] and r[3] in ("Shoes", "Outerwear", "Bags", "Accessories", "Headwear")]   # the kinds that fit the rug
    sc = lambda r: (lambda v: (v[1] or 0) + (v[2] or 0) + 3 * (v[3] or 0))(st.get(r[0]) or [0, 0, 0, 0])
    rows.sort(key=sc, reverse=True)
    return [("pop:" + r[0], "other") for r in rows[:n or POP_N] if sc(r) > 0 and ("pop:" + r[0]) not in no]


def pop_url(sid):
    r = site_row(sid[4:]); img = r[11] if r else ""
    if img.startswith("/"): return "https://www.puroclassico.com" + img
    if img[:1] == "B": return "https://uptpghuduqjqmrxwatbm.supabase.co/storage/v1/object/public/" + img[1:]
    return ""


def site_find(sid):
    """("taobao", "760438413422", 0) for "site:taobao/760438413422/0"."""
    sf, fid, k = sid[5:].split("/"); return sf, fid, int(k)


def site_row(fid):
    """The find's row in functions/_lib/catalog.js (title, brand, price ...), or None."""
    price(None, None, None)                                    # loads _ROWS
    for r in _ROWS:
        if r[0] == fid: return r
    return None


FLATLAY_ON = os.environ.get("RUG_FLATLAY", "0") == "1"   # the no-AI flat-lay: off (owner, 8 Nov 2026: it looks bad); no credit = no post that run
AI_OUT = [False]      # set when every image service is out of credit: the run then lays product cut-outs on the rug itself
CUT = {}              # pop:<id> -> the transparent product cut-out, for that fallback


def pop_check(pid):
    """What check() would say about a popular find, from the catalogue itself (no API call)."""
    r = site_row(pid[4:]) or [pid[4:], "", "", "", "", "", 0]
    cat = r[3]; g = "shoes" if cat == "Shoes" else "bags" if cat == "Bags" else "jackets" if cat == "Outerwear" else "small"
    name = re.sub(r"\b(black|white|grey|gray|navy|blue|light|dark|red|green|brown|beige|cream|tan|pink|purple|yellow|orange|khaki|silver|gold|olive|multicolou?r)\b", "", r[1], flags=re.I)
    name = re.sub(r"\s+", " ", name).strip().lower()
    while len(name) > 26 and " " in name: name = name.rsplit(" ", 1)[0]     # cut at a word, never "snea"
    item = (ai_label(pid[4:]).get("item") or "").lower()
    if re.search(r"suitcase|luggage|trolley|carry.?on", (ai_label(pid[4:]).get("title_base") or "") + " " + r[1], re.I): item = "suitcase"   # labelled "bag", but 60 cm
    if item in FLAT_CM: g = group_of(item)                    # the vision labels' kind: a watch is small, a vest is a jacket
    lab = flat_label(pid, r)
    if SOURCE == "pop" and lab:                               # "christian louboutin sneakers", not "christian louboutin" (a title cut short)
        name = lab.lower()
        while len(name) > 28 and " " in name: name = name.rsplit(" ", 1)[0]
    return {"fits": True, "clear": True, "group": g, "item": item or g, "brand": r[2], "name": name, "label": lab}


# ---- The no-AI fallback: a flat-lay of the items' own product photos on the rug photo (rebuilt 6 Nov 2026) ----
# The first version (5 Nov) pasted the cut-outs flat and too big over the rug ("looks insanely bad", owner). Now:
#  - only clean product photos: the vision labels in data/catalog_ai.json (is_clean_product_photo and no hand, person,
#    box, collage, extra views, cropped item or damaged cut-out) plus a check of the cut-out itself (one item, no haze,
#    not touching the photo edge, a front view for jackets), and only kinds that lie well on a rug, each with a real size;
#  - real sizes (a watch is about 21 cm, a jacket about 74 cm) at the rug's own scale, and the camera "a step closer"
#    for small things, so one slide shows one jacket, two pairs of shoes or bags, or three small things;
#  - no item overlaps another or leaves the rug; a small natural turn, the rug camera's slight tilt (the far edge a
#    little narrower and shorter), a contact shadow and a softer cast shadow, the room's colour and light, the photo's
#    softness and a little grain;
#  - captions like the cover: white TikTok Sans bold with a black outline, Title Case "Brand Item $price", in the clear
#    band under the items.
# The Gemini path above is unchanged: when the image credit is back, the real re-shot look returns by itself.
RUG_BOX = (28, 437, 930, 1222)        # the rug in rug.jpg (930x1692): left, top, right (it runs off the photo), bottom
RUG_PX_CM = 8.0                       # rug.jpg pixels per centimetre in the middle of the rug (the rug is about 1.1 m wide)
FLAT_BAD = {"hand_in_photo", "worn_by_person", "multiple_items", "packaging_or_box", "collage_or_grid", "item_cropped",
            "cut_out_damage", "multiple_views", "text_or_watermark", "blurry_or_low_res", "hanger_or_rack", "busy_background"}
FLAT_CM = {                           # the long side of the item as the product photo shows it, in cm (catalog_ai "item")
    "watch": 21, "bracelet": 9, "necklace": 16, "card holder": 10, "wallet": 11, "sunglasses": 15, "glasses": 15,
    "belt": 14, "beanie": 24, "cap": 27, "trucker cap": 27, "bucket hat": 30, "perfume": 13, "pouch": 24,
    "bag": 34, "crossbody bag": 26, "shoulder bag": 30, "belt bag": 30, "messenger bag": 32, "clutch": 26, "tote bag": 40,
    "backpack": 44, "duffle bag": 56, "briefcase": 40, "bucket bag": 28, "suitcase": 62,
    "sneakers": 31, "shoes": 30, "boots": 31, "loafers": 29, "slides": 28, "sandals": 28, "clogs": 29,
    "jacket": 74, "puffer jacket": 76, "down jacket": 76, "windbreaker": 74, "varsity jacket": 72, "bomber jacket": 70,
    "denim jacket": 70, "fleece": 70, "overshirt": 74, "zip hoodie": 72, "track jacket": 70, "coat": 96, "vest": 64,
}
FLAT_ZOOM = {"small": 2.1, "shoes": 1.6, "bags": 1.35, "jackets": 1.1}      # how much closer the camera is, per kind of slide
_AI = None
PAIRS = set()         # pop:<id> whose photo shows a pair (two shoes): a little wider on the rug


def ai_label(fid):
    """The find's vision labels (data/catalog_ai.json "items"), {} when it has none."""
    global _AI
    if _AI is None:
        try: _AI = json.load(open(os.path.join(ROOT, "data", "catalog_ai.json"))).get("items") or {}
        except Exception: _AI = {}
    return _AI.get(fid) or {}


def flat_ok(pid):
    """Can this popular find go on the rug without AI? (ok, why). Only the labels, no download."""
    a = ai_label(pid[4:])
    if not a: return False, "no photo labels"
    if not a.get("is_clean_product_photo"): return False, "not a clean product photo"
    bad = set(a.get("photo_issues") or []) & FLAT_BAD
    if bad: return False, ", ".join(sorted(bad))
    if (a.get("item") or "").lower() not in FLAT_CM: return False, "a %s does not lie on a rug" % (a.get("item") or "?")
    return True, ""


def flat_label(pid, row):
    """The caption name in Title Case, brand first ("Moncler Puffer Jacket"): the labels' clean title, else brand + item."""
    a = ai_label(pid[4:]); brand = (row[2] if row else "") or ""; item = a.get("item") or ""
    t = re.sub(r"\s+", " ", (a.get("title_base") or "").replace("\u2014", "-").replace("\u2013", "-")).strip() or (brand + " " + item).strip()     # never an em dash (owner)
    if len(t) > 26 and brand and item and len(brand + " " + item) <= 30: t = brand + " " + item          # "Christian Louboutin Sneakers"
    while len(t) > 30 and " " in t: t = t.rsplit(" ", 1)[0]
    return " ".join(w if (w[:1].isupper() or any(ch.isdigit() for ch in w) or not w[:1].isalpha()) else w[:1].upper() + w[1:] for w in t.split())


def cut_clean(im, pid):
    """The product cut-out made ready for the rug, or (None, why): one item, a clean edge, nothing cropped."""
    if "A" not in im.getbands(): return None, "no transparency"
    im = im.convert("RGBA"); al = im.getchannel("A")
    if al.getextrema()[0] > 250: return None, "no background removed"
    cat = (site_row(pid[4:]) or [None] * 4)[3]
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from clean_photos import tidy                          # the site photo clean-up: loose specks, hanger hooks, rack poles
        from photo_metrics import mask_stats
        al, notes = tidy(al, cat, False)
        if any(n.startswith("DAMAGED") for n in notes): return None, notes[-1]
        st = mask_stats(al)
    except Exception as e: return None, "mask check: %s" % str(e)[:60]
    item = (ai_label(pid[4:]).get("item") or "").lower()
    if st["touches"]: return None, "item cut off at the photo edge"
    if st["soft"] > 0.16: return None, "hazy edge (%.0f%% half-transparent)" % (100 * st["soft"])
    if st["cover"] < 0.03: return None, "almost empty"
    if st["parts"] > (2 if item in ("sneakers", "shoes", "boots", "loafers", "slides", "sandals", "clogs", "sunglasses", "glasses") else 1):
        return None, "%d separate pieces" % st["parts"]
    if st["largest_share"] < 0.4: return None, "pieces of equal size"
    im.putalpha(al); im = im.crop(al.point(lambda v: 255 if v >= 24 else 0).getbbox())
    import numpy as np
    a = np.asarray(im).astype(np.float32); A = a[..., 3] / 255.0
    if group_of(item) == "jackets":                          # a front view (symmetric), not a side or worn three-quarter view
        m = A > .5; sym = (m & m[:, ::-1]).sum() / max(1, (m | m[:, ::-1]).sum())
        if sym < 0.78: return None, "not a front view (%.2f)" % sym
    if item == "belt" and max(im.size) > 3.2 * min(im.size): return None, "a belt laid out straight"
    # the edge: pixels the cut-out left half-transparent carry the old (white) background, so they take the colour of the
    # solid item next to them (colour decontamination); then the edge is pulled in a little and softened by half a pixel
    solid = A > 0.97
    if solid.sum() < 50: return None, "no solid item"
    wimg = Image.fromarray((solid * 255).astype(np.uint8)); rgb = a[..., :3] * solid[..., None]
    out = a[..., :3].copy(); done = solid.copy()
    for r in (2, 5, 12):
        wsum = np.asarray(wimg.filter(ImageFilter.GaussianBlur(r))).astype(np.float32) / 255.0
        csum = np.stack([np.asarray(Image.fromarray(np.clip(rgb[..., c], 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(r))).astype(np.float32) for c in range(3)], -1)
        sel = (A > 0.02) & ~done & (wsum > 0.02)
        out[sel] = (csum / np.maximum(wsum[..., None], 1e-3))[sel]; done |= sel
    a[..., :3] = out
    a3 = Image.fromarray((A * 255).astype(np.uint8)).filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(0.6))
    a[..., 3] = np.asarray(a3).astype(np.float32)
    if st["parts"] == 2: PAIRS.add(pid)
    out = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGBA")
    return out, "ok"


def group_of(item):
    item = (item or "").lower()
    if item in ("sneakers", "shoes", "boots", "loafers", "slides", "sandals", "clogs"): return "shoes"
    if FLAT_CM.get(item, 0) >= 60: return "jackets"
    if item in ("bag", "crossbody bag", "shoulder bag", "belt bag", "messenger bag", "clutch", "tote bag", "backpack", "duffle bag", "briefcase", "bucket bag"): return "bags"
    return "small"


def _persp(dst, src):
    """Coefficients for Image.transform(PERSPECTIVE) that map the dst quad onto the src quad."""
    import numpy as np
    m = []
    for (x, y), (u, v) in zip(dst, src):
        m.append([x, y, 1, 0, 0, 0, -u * x, -u * y]); m.append([0, 0, 0, x, y, 1, -v * x, -v * y])
    return np.linalg.solve(np.array(m, float), np.array([c for p in src for c in p], float)).tolist()


def composite(sl, rnd):
    """No-AI slide: the items' clean product cut-outs laid on the rug photo like a flat-lay (see the notes above).
    Returns PNG bytes; puts the slide's item boxes in sl[0]["boxes"] so the caption goes in the clear band."""
    import numpy as np
    W, H = 1080, 1920
    src = Image.open(RUG).convert("RGB"); sw, sh = src.size
    z = min([FLAT_ZOOM.get(group_of(p.get("item")), 1.0) for p in sl] or [1.0])     # the biggest item decides
    cw = sw / z; ch = cw * H / W
    if ch > sh: ch = sh; cw = ch * W / H
    cx = sw * 0.5 + (sw * 0.03 if z > 1.05 else 0); cy = (RUG_BOX[1] + RUG_BOX[3]) / 2 - 40     # the middle of the rug, a little of the room above
    x0 = min(max(0, cx - cw / 2), sw - cw); y0 = min(max(0, cy - ch / 2), sh - ch)
    base = src.resize((W, H), Image.LANCZOS, box=(x0, y0, x0 + cw, y0 + ch)); u = W / cw          # output px per rug.jpg px
    B = np.asarray(base).astype(np.float32) / 255.0
    to_out = lambda x, y: ((x - x0) * u, (y - y0) * u)
    rl, rt = to_out(RUG_BOX[0], RUG_BOX[1]); rr, rb = to_out(RUG_BOX[2], RUG_BOX[3])
    rug_px = B[int(max(0, rt)) + 10:int(min(H, rb)) - 10, int(max(0, rl)) + 10:int(min(W, rr)) - 10].reshape(-1, 3)
    white = np.percentile(rug_px, 90, axis=0)                 # the rug's cream under the room light
    lum = B.mean(-1); light = np.asarray(Image.fromarray((lum * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(70))).astype(np.float32) / 255.0
    light = light / max(1e-3, float(np.median(light[int(max(0, rt)):int(min(H, rb)), :])))
    block = int(64 * 1.25 * (len(sl) - 1)) + 90; cap_y = int(H * 0.72 - block / 2)     # the caption sits at the same height on every slide
    reg = (max(rl, 0) + 34, max(rt + 30, H * 0.17), min(rr, W) - 34, min(rb - 24, cap_y - 44))   # where items may lie
    # 1. each item at its real size, turned a little, tilted like the rug, toned to the room
    prepared = []
    for p in sl:
        im = CUT.get(p["qc"])
        if im is None: continue
        cm = FLAT_CM.get((p.get("item") or "").lower(), 30)
        if p["qc"] in PAIRS: cm *= 1.12
        prepared.append([p, im, cm])
    prepared.sort(key=lambda q: -q[2])
    anchors = {1: [(.5, .5)], 2: [(.3, .3), (.7, .72)], 3: [(.27, .27), (.73, .34), (.45, .76)]}.get(len(prepared), [(.5, .5)] * len(prepared))
    if rnd.random() < .5: anchors = [(1 - ax, ay) for ax, ay in anchors]
    def shape(im, cm, ycen, k):
        ysrc = ycen / u + y0
        s = RUG_PX_CM * cm * u * (1 + 0.00013 * (ysrc - 830)) * k / max(im.size)
        it = im.resize((max(1, int(im.width * s / u)), max(1, int(im.height * s / u))), Image.LANCZOS)     # the rug photo's own detail
        it = it.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.BICUBIC)
        return it
    for shrink in (1.0, 0.92, 0.85, 0.78, 0.72):
        boxes, layers, ok = [], [], True
        for (p, im, cm), (ax, ay) in zip(prepared, anchors):
            g = group_of(p.get("item")); ang = rnd.uniform(-1, 1) * (4 if g == "jackets" else 9 if g == "shoes" else 7)
            it = shape(im, cm, (reg[1] + reg[3]) / 2, shrink)
            it = it.rotate(ang, expand=True, resample=Image.BICUBIC)
            w, h = it.size; k = 0.035; sq = 0.95                # the far edge a little narrower, the depth a little shorter
            h2 = max(1, int(h * sq))
            it = it.transform((w, h2), Image.PERSPECTIVE, _persp([(w * k / 2, 0), (w - w * k / 2, 0), (w, h2), (0, h2)], [(0, 0), (w, 0), (w, h), (0, h)]), Image.BICUBIC)
            bb = it.getchannel("A").point(lambda v: 255 if v > 20 else 0).getbbox()
            if bb: it = it.crop(bb)
            w, h = it.size
            if w > reg[2] - reg[0] or h > reg[3] - reg[1]: ok = False; break
            best = None
            for t in range(500):
                x = rnd.uniform(reg[0], reg[2] - w); y = rnd.uniform(reg[1], reg[3] - h)
                r = (x - 30, y - 30, x + w + 30, y + h + 30)
                if any(r[0] < b[2] and b[0] < r[2] and r[1] < b[3] and b[1] < r[3] for b in boxes): continue
                tx = reg[0] + ax * (reg[2] - reg[0]); ty = reg[1] + ay * (reg[3] - reg[1])
                d = (x + w / 2 - tx) ** 2 + (y + h / 2 - ty) ** 2
                if best is None or d < best[0]: best = (d, x, y)
            if best is None: ok = False; break
            x, y = int(best[1]), int(best[2]); boxes.append((x, y, x + w, y + h)); layers.append((p, it, x, y)); p["_box"] = (x, y, x + w, y + h)
        if ok and layers: break
    if not ok or not layers: return None
    # 2. shadows first (the rug darkens under and beside each item), then the items
    S = np.zeros((H, W), np.float32)
    for p, it, x, y in layers:
        a = it.getchannel("A"); pad = int(40 * u)
        big = Image.new("L", (it.width + 2 * pad, it.height + 2 * pad), 0); big.paste(a, (pad, pad))
        ao = np.asarray(big.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(3.5 * u))).astype(np.float32) / 255.0 * 0.62
        cast = np.asarray(big.filter(ImageFilter.GaussianBlur(15 * u))).astype(np.float32) / 255.0 * 0.32
        sets = [(ao, 1 * u, 2.5 * u), (cast, 6 * u, 11 * u)]
        if group_of(p.get("item")) in ("shoes", "bags"):       # standing things: a darker shadow where the sole or the base meets the rug
            foot = big.copy(); ImageDraw.Draw(foot).rectangle((0, 0, foot.width, pad + int(it.height * 0.78)), fill=0)
            sets.append((np.asarray(foot.filter(ImageFilter.GaussianBlur(5 * u))).astype(np.float32) / 255.0 * 0.7, 2 * u, 5 * u))
        for arr, dx, dy in sets:
            X, Y = int(x - pad + dx), int(y - pad + dy)
            xa, ya, xb, yb = max(0, X), max(0, Y), min(W, X + arr.shape[1]), min(H, Y + arr.shape[0])
            if xb > xa and yb > ya: S[ya:yb, xa:xb] = 1 - (1 - S[ya:yb, xa:xb]) * (1 - arr[ya - Y:yb - Y, xa - X:xb - X])
    tint = np.array([0.32, 0.27, 0.23], np.float32)            # a warm brown shadow, like the floor's
    B = B * (1 - S[..., None] * (1 - tint))
    for p, it, x, y in layers:
        a = np.asarray(it).astype(np.float32) / 255.0; A = a[..., 3:4]; c = a[..., :3]
        L = c.mean(-1, keepdims=True); c = L + (c - L) * 0.9            # a little less saturated than the studio shot
        m = float((c.mean(-1) * A[..., 0]).sum() / max(1e-3, A.sum())); c = m + (c - m) * 0.9      # and less contrast
        c = c * (0.55 + 0.45 * white / max(1e-3, white.max()))           # the room's warm light
        hi = np.percentile(c.mean(-1)[A[..., 0] > .5], 99) if (A > .5).any() else 1
        c = c * min(1.0, float(white.mean()) * 1.02 / max(1e-3, hi))       # no item brighter than the lit rug
        c = c * light[y:y + it.height, x:x + it.width, None]                # the same light falloff as the room
        reg_b = B[y:y + it.height, x:x + it.width]
        B[y:y + it.height, x:x + it.width] = reg_b * (1 - A) + np.clip(c, 0, 1) * A
    # 3. one camera: a little grain over everything
    g = np.random.default_rng(rnd.randrange(1 << 30))
    noise = g.normal(0, 1, (H, W)).astype(np.float32)
    noise = np.asarray(Image.fromarray(np.clip(noise * 40 + 128, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.7))).astype(np.float32) / 255.0 - 0.5
    B = B + noise[..., None] * 0.07 + g.normal(0, 0.006, (H, W, 3)).astype(np.float32)
    out = Image.fromarray(np.clip(B * 255, 0, 255).astype(np.uint8))
    sl[0]["boxes"] = boxes + [("cap_y", cap_y)]
    b = io.BytesIO(); out.save(b, "PNG"); return b.getvalue()


def flat_caption(im, names, usds, boxes):
    """The cover's text style for the item slides: white TikTok Sans bold, black outline, soft shadow; one line per item
    ("Moncler Puffer Jacket $35"), centred, in the clear band under the items (above them when there is no room)."""
    im = im.convert("RGBA"); W, H = im.size
    texts = [n + (" $%d" % u if u else "") for n, u in zip(names, usds)]
    size = 64
    while size > 44 and max(outlined(t, size).width for t in texts) > W * 0.88: size -= 2
    layers = [outlined(t, size) for t in texts]; lh = int(size * 1.25)
    block = lh * (len(layers) - 1) + max(l.height for l in layers)
    lo, hi = int(H * 0.13), int(H * 0.79) - block
    fixed = [b[1] for b in boxes if b[0] == "cap_y"]; boxes = [b for b in boxes if b[0] != "cap_y"]
    bottom = max(b[3] for b in boxes) if boxes else int(H * 0.6); top = min(b[1] for b in boxes) if boxes else int(H * 0.3)
    y = fixed[0] if fixed and fixed[0] >= bottom + 20 else bottom + 48 if bottom + 48 <= hi else top - 48 - block if top - 48 - block >= lo else hi
    for k, l in enumerate(layers): im.alpha_composite(l, ((W - l.width) // 2, y + k * lh))
    return im.convert("RGB")


def owner(pid):
    """Same rule as make_finds.owner: which TikTok account a photo belongs to, so the accounts never share one."""
    return 2 if int(hashlib.md5(pid.encode()).hexdigest(), 16) % 3 == 0 else 1


def never(paths):
    out = set()
    for p in [x.strip() for x in (paths or "").split(",") if x.strip()]:
        try: j = json.load(open(os.path.join(ROOT, p)))
        except Exception: continue
        out |= set(j) if isinstance(j, list) else {k for k, v in (j.get("count") or {}).items() if v} | set(j.get("covers") or {})
    return out


RUG_TAGS = "#fyp #grisch #oldmoney #stockholmstyle #haul"       # the rug posts' caption (owner, 22 Oct 2026): "27kg haul unboxing" + these


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default="rug-out"); ap.add_argument("--n", type=int, default=6); ap.add_argument("--seed", type=int)
    ap.add_argument("--own", type=int, default=2); ap.add_argument("--avoid", default="finds_used.json,scripts/slides_exclude.json")
    ap.add_argument("--state", default="", help="this account's usage record (slides_used.json); rug use is counted in its own key, least used first")
    ap.add_argument("--text", default="", help="json with this account's caption lines (scripts/slides_text.json)")
    ap.add_argument("--commit-state", action="store_true")
    a = ap.parse_args(); os.makedirs(a.out, exist_ok=True); rnd = random.Random(a.seed)
    state_path = os.path.join(ROOT, a.state) if a.state else ""
    try: used = json.load(open(state_path)) if state_path else {"count": {}}
    except Exception: used = {"count": {}}
    used.setdefault("count", {}); rejected = set(used.get("rug_skip", []))
    items = json.load(open(os.path.join(ROOT, "scripts", "qc_items.json")))
    live, no = drive_ids(), never(a.avoid) | rejected; cands = {}; rc = used.setdefault("rug_count", {})      # the account's own green-mat photos may come back on the rug (a new look)
    for sid, v in items.items():
        pid = sid.split(":")[0]
        if sid.endswith(":0") and v.get("i") in FITS and pid in live and pid not in no and (not a.own or owner(pid) == a.own): cands[pid] = v["i"]
    cands = list(cands.items()); rnd.shuffle(cands); cands.sort(key=lambda c: (rc.get(c[0], 0), c[1] == "other"))      # least used on the rug first; known kinds before maybe-bottles
    try: chosen = json.load(open(os.path.join(ROOT, "scripts", "rug_picks.json")))["ids"]      # the owner's own picks (picker page): these go first
    except Exception: chosen = []
    fresh = [pid for pid in chosen if pid in live and not rc.get(pid)]
    if fresh:                                                  # only picks until every pick has been on the rug once, then the normal pool again
        rnd.shuffle(fresh); cands = [(pid, (items.get(pid + ":0") or {}).get("i", "other")) for pid in fresh]
        print("using the owner's picks: %d not posted yet" % len(fresh))
    if SOURCE == "pop":                                        # only the most popular finds with a clean shop photo, kinds taking turns
        fresh = []; pool = [c for c in pop_cands(no) if flat_ok(c[0])[0]]
        rnd.shuffle(pool); pool.sort(key=lambda c: rc.get(c[0], 0))     # random, least used on the rug first
        kinds = {}
        for c in pool: kinds.setdefault(group_of(ai_label(c[0][4:]).get("item")), []).append(c)
        cands = []
        while any(kinds.values()):
            for g in ("small", "shoes", "jackets", "bags"):
                cands += kinds.get(g, [])[:MULTI[g]]; kinds[g] = kinds.get(g, [])[MULTI[g]:]
        print("popular finds with a clean photo:", len(cands))
    picked_ids = set(fresh)
    if SITE_ON and not fresh and SOURCE != "pop":                                  # the site's QC photos take turns with the Drive photos, least used first
        site = site_cands(no); rnd.shuffle(site); site.sort(key=lambda c: rc.get(c[0], 0))
        pop = pop_cands(no); rnd.shuffle(pop); pop.sort(key=lambda c: rc.get(c[0], 0))     # random among the popular ones, least used first
        mix = []
        for k in range(max(len(cands), len(site), len(pop))):
            if k < len(pop): mix.append(pop[k])
            if k < len(site): mix.append(site[k])
            if k < len(cands): mix.append(cands[k])
        print("site QC photos:", len(site), "popular product photos:", len(pop)); cands = mix
    print("candidates:", len(cands))
    picks, groups, fails = [], {}, 0                           # 1. pick the photos (a quick check each, six at a time), a mix of kinds
    from concurrent.futures import ThreadPoolExecutor
    def look(c):
        pid, t = c
        if AI_OUT[0] and not pid.startswith("pop:"): return c, None, "flat-lay: no image credit for this photo"
        if AI_OUT[0]:
            ok, why = flat_ok(pid)
            if not ok: return c, None, "flat-lay: skip %s (%s)" % (pid, why)
        url = SITE_QC % site_find(pid) if pid.startswith("site:") else pop_url(pid) if pid.startswith("pop:") else "https://drive.usercontent.google.com/download?id=%s&export=download&confirm=t" % pid
        try: qc = Image.open(io.BytesIO(fetch(url))); qc.load()
        except Exception as e: return c, None, "download: %s" % e
        if pid.startswith(("site:", "pop:")):                 # one photo, not two stacked like the Drive exports
            if qc.mode in ("RGBA", "LA", "P"):                 # the product photos are cut-outs: put them on white
                qc = qc.convert("RGBA"); CUT[pid] = qc.copy(); bg = Image.new("RGB", qc.size, (255, 255, 255)); bg.paste(qc, mask=qc.split()[-1]); qc = bg
            else: qc = qc.convert("RGB")
        if SOURCE == "pop" and pid.startswith("pop:") and not AI_OUT[0]: return c, qc, pop_check(pid)     # facts from the catalogue: no green-mat check
        if AI_OUT[0] and pid.startswith("pop:"):
            cut, why = cut_clean(CUT[pid], pid) if pid in CUT else (None, "not a cut-out")
            if cut is None: CUT.pop(pid, None); return c, None, "flat-lay: skip %s (%s)" % (pid, why)
            CUT[pid] = cut; return c, qc, pop_check(pid)
        try: return c, qc, check(qc if pid.startswith(("site:", "pop:")) else top_shot(qc))      # only the shot the image model gets: the lower one is often another item
        except Exception as e: return c, qc, "check: %s" % str(e)[:300]
    want, cap = (a.n * 2 + 2, a.n) if MULTI_ON else (a.n + 3, max(2, a.n // 3))
    t_pick = time.time()
    def pick_from(cl):
        nonlocal fails
        for b in range(0, len(cl), 6):
            if len(picks) >= want or time.time() - t_pick > 8 * 60: break      # spares for the judge; never more than 8 minutes of checking
            with ThreadPoolExecutor(6) as ex: seen = list(ex.map(look, cl[b:b + 6]))
            for (pid, t), qc, c in seen:
                if isinstance(c, str) and c.startswith("flat-lay"): print(" ", c); continue     # not a failure: a photo that does not suit the flat-lay
                if isinstance(c, str):
                    print(" ", c); fails += 1
                    if "insufficient_quota" in c or "billing" in c or "credit" in c.lower():
                        if AI_OUT[0]: continue
                        if not FLATLAY_ON: sys.exit("NO IMAGE CREDIT LEFT (Gemini and OpenAI): no post this run, the next run tries again (%s)" % c[:200])
                        AI_OUT[0] = True; print("  NO IMAGE CREDIT LEFT (Gemini and OpenAI): laying product photos on the rug without AI this run"); return
                    if fails >= 12: sys.exit("the item check keeps failing: stopping (the next run tries again)")
                    continue
                fails = 0
                if len(picks) >= want: break
                g = c.get("group") if c.get("group") in ANGLES else group(t)
                if pid not in picked_ids and not (c.get("fits") and c.get("clear")):      # the owner's picks are never skipped
                    print("  skip (%s): %s" % ("not a fit" if not c.get("fits") else "not clear", c.get("name"))); rejected.add(pid); continue
                if groups.get(g, 0) >= cap: continue                                # a mix: not all bags
                fid = site_find(pid)[1] if pid.startswith("site:") else pid[4:] if pid.startswith("pop:") else ""
                if fid and any(p.get("find") == fid for p in picks): continue      # one photo per find in a post
                groups[g] = groups.get(g, 0) + 1
                name = re.sub(r"[^a-z0-9 '&.-]", "", unicodedata.normalize("NFKD", str(c.get("name") or c.get("item") or t)).encode("ascii", "ignore").decode().lower()).strip()[:28]      # "pérignon" -> "perignon", not "prignon"
                print("  picked", name, "(%.0fs)" % (time.time() - t_pick))
                row = site_row(fid) if fid else None
                usd = int(round(row[6])) if row and isinstance(row[6], (int, float)) and row[6] > 0 else price(c.get("brand"), c.get("item") or t, g)   # a site photo: its find's own price
                picks.append({"qc": pid, "img": qc, "name": name, "usd": usd, "group": g, "brand": c.get("brand"), "find": fid, "single": bool(fid),
                              "item": c.get("item") or t, "angle": rnd.choice(ANGLES[g]), "label": c.get("label")})

    pick_from(cands)
    if AI_OUT[0]:                                              # only the popular finds' cut-outs can be laid on the rug without AI
        picks[:] = []; groups.clear()                         # picked before the credit ran out: not checked for the flat-lay, so pick again
        pool =[c for c in pop_cands(no, POP_N * 3) if flat_ok(c[0])[0]]      # only clean photos of kinds that lie well on a rug
        rnd.shuffle(pool); pool.sort(key=lambda c: rc.get(c[0], 0)); fails = 0
        kinds = {}                                             # kinds take turns in slide-sized groups (three small things, two pairs, one jacket, two bags),
        for c in pool: kinds.setdefault(group_of(ai_label(c[0][4:]).get("item")), []).append(c)     # so small things are never left alone on a slide
        pool = []
        while any(kinds.values()):
            for g in ("small", "shoes", "jackets", "bags"):
                pool += kinds.get(g, [])[:MULTI[g]]; kinds[g] = kinds.get(g, [])[MULTI[g]:]
        print("flat-lay candidates (clean product photos):", len(pool))
        pick_from(pool)
    rug = jpeg(Image.open(RUG), 1536)
    t0 = time.time(); budget = float(os.environ.get("RUG_BUDGET_MIN", "15")) * 60

    by = {}                                                    # 2. slides: several of a kind together (MULTI), kinds taking turns
    for p in picks: by.setdefault(p["group"], []).append(p)
    chunks = {g: [ps[k:k + (MULTI.get(g, 1) if MULTI_ON else 1)] for k in range(0, len(ps), MULTI.get(g, 1) if MULTI_ON else 1)] for g, ps in by.items()}
    if AI_OUT[0]: chunks["small"] = [c for c in chunks.get("small", []) if len(c) > 1]     # one bracelet alone on the rug looks empty
    slides = []
    while any(chunks.values()) and len(slides) < a.n + 1:
        for g in ["small", "shoes", "jackets", "bags"]:
            if chunks.get(g) and len(slides) < a.n + 1: slides.append(chunks[g].pop(0))

    def make(sl):                                              # 3. the images, three at a time; each one judged, one retry, then the slide is dropped
        shots = [p["img"] if p.get("single") else top_shot(p["img"]) for p in sl]; label = " + ".join(p["name"] for p in sl)
        angle = rnd.choice(ANGLES["several"]) if len(sl) > 1 else sl[0]["angle"]
        if AI_OUT[0]: return sl, composite(sl, random.Random("%s %s" % (a.seed, label))), "rug flat-lay (no AI credit)", {}     # its own dice: the slides are made side by side
        for attempt in range(2):
            if time.time() - t0 > budget: print("  out of time, skipping", label); break
            print("  making", label, "try", attempt + 1, "%.0fs in" % (time.time() - t0))
            png, model, use = generate([rug] + [jpeg(x) for x in shots], prompt([p["item"] for p in sl], angle, all(p["qc"].startswith("pop:") for p in sl)))
            if not png: break
            ok, why = judge(shots, png); print("  %s, try %d: %s %s" % (label, attempt + 1, "OK" if ok else "REJECTED", why))
            if ok: return sl, png, model, use
        return sl, None, None, {}
    with ThreadPoolExecutor(3) as ex: done = list(ex.map(make, slides))
    log = []
    for sl, png, model, use in done:
        if not png or len(log) >= a.n: print("no image for", " + ".join(p["name"] for p in sl)) if not png else None; continue
        fn = "%02d-%s" % (len(log) + 1, re.sub(r"[^a-z0-9]+", "-", sl[0]["name"]) + ("-and-%d-more" % (len(sl) - 1) if len(sl) > 1 else ""))
        for k, p in enumerate(sl): p["img"].convert("RGB").save(os.path.join(a.out, fn + "-qc%s.jpg" % (k or "")), quality=85)
        ImageOps.fit(Image.open(io.BytesIO(png)).convert("RGB"), (1080, 1920), Image.LANCZOS).save(os.path.join(a.out, fn + "-raw.jpg"), quality=94)
        log.append({"file": fn + ".jpg", "qc": [p["qc"] for p in sl], "name": [p["name"] for p in sl], "usd": [p["usd"] for p in sl],
                    "group": sl[0]["group"], "model": model, "usage": use})
        if sl[0].get("boxes") is not None:                     # a flat-lay slide: caption lines in the items' order from top to bottom
            order = sorted(range(len(sl)), key=lambda k: (sl[k].get("_box") or (0, 1e9))[1])
            log[-1].update(label=[sl[k].get("label") or sl[k]["name"].title() for k in order], usd=[sl[k]["usd"] for k in order], boxes=sl[0]["boxes"])
        print("made", fn, "with", model)
    if state_path and a.commit_state: used["rug_skip"] = sorted(rejected)
    if len(log) < min(a.n, 5):                                 # never post a thin carousel
        if state_path and a.commit_state: json.dump(used, open(state_path, "w"), indent=0)
        sys.exit("only %d slides made" % len(log))
    cv, k, kg = cover(rnd, used.get("rug_cover")); cover_path = os.path.join(a.out, "00-cover.jpg"); cv.save(cover_path, quality=94)
    images = [cover_path]
    for x in log:
        p = os.path.join(a.out, x["file"]); raw = Image.open(p[:-4] + "-raw.jpg")
        (flat_caption(raw, x["label"], x["usd"], x["boxes"]) if x.get("boxes") is not None else item_slide(raw, x["name"], x["usd"])).save(p, quality=94); images.append(p)
    caption = "%dkg haul unboxing\n\n%s" % (kg, RUG_TAGS)       # the title line is the same weight as on the cover
    meta = {"format": "finds", "images": images, "ids": [], "caption": caption, "seconds": 0, "voiceover": False,
            "file": os.path.join(a.out, "none.mp4"), "product_url": "https://www.puroclassico.com/"}
    json.dump(meta, open(os.path.join(a.out, "rug.json"), "w"), indent=1, ensure_ascii=False)
    json.dump({"cover": k, "slides": log}, open(os.path.join(a.out, "log.txt"), "w"), indent=1)      # not .json: finds_plan posts the first .json it finds
    print("wrote", len(images), "images;", caption.replace("\n", " | "))
    if state_path and a.commit_state:
        for x in log:
            for q in x["qc"]: rc[q] = rc.get(q, 0) + 1
        used["rug_cover"] = k; used["part"] = int(used.get("part", 0)) + 1; json.dump(used, open(state_path, "w"), indent=0)


if __name__ == "__main__":
    main()
