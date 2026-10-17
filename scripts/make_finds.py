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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H, FPS = 1080, 1920, 30
SW, SH = 1080, 1440                                          # carousel slides are 3:4: the TikTok app shows that shape whole, a 9:16 photo gets cut top and bottom
FF = imageio_ffmpeg.get_ffmpeg_exe()
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"}
CACHE = os.path.join(tempfile.gettempdir(), "pc_finds"); os.makedirs(CACHE, exist_ok=True)
FONT = os.path.join(ROOT, "scripts", "fonts", "Montserrat.ttf")
ANTON = os.path.join(ROOT, "scripts", "fonts", "Anton-Regular.ttf")          # tall condensed type for the start picture
SCRIPT = os.path.join(ROOT, "scripts", "fonts", "Parisienne-Regular.ttf")    # the "puro classico" script in the corner badge
CATS_FILE = os.path.join(ROOT, "scripts", "qc_categories.json")              # item type of every QC shot, so a slide pairs two of a kind


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


def cover_card(title, SW=SW, SH=SH, bg=None):
    """The start image: the title in tall white capitals with a black outline, and three arrow keys under it, over a picture."""
    if bg is None: im = Image.new("RGB", (SW, SH), (24, 26, 32))
    else: im = crisp(ImageOps.fit(bg.convert("RGB"), (SW, SH), Image.LANCZOS))
    d = ImageDraw.Draw(im); words = title.upper().split()
    lines = [" ".join(words)]
    size = 150
    f = lambda z: ImageFont.truetype(ANTON, z)
    while size > 60 and d.textlength(lines[0], font=f(size)) > SW - 90: size -= 4
    if size < 96 and len(words) > 1:                              # too long for one line: two lines, bigger
        k = (len(words) + 1) // 2; lines = [" ".join(words[:k]), " ".join(words[k:])]; size = 170
        while size > 60 and max(d.textlength(l, font=f(size)) for l in lines) > SW - 90: size -= 4
    ft, lh, sw = f(size), int(size * 1.12), max(6, size // 14)
    key = int(size * 0.92); gap = int(key * 0.14)
    block = lh * len(lines) + gap * 3 + key
    y = int(SH * 0.56) - block // 2
    for ln in lines:
        d.text((SW / 2, y), ln, font=ft, fill=(255, 255, 255), anchor="ma", stroke_width=sw, stroke_fill=(0, 0, 0)); y += lh
    y += gap * 2; x0 = SW // 2 - (key * 3 + gap * 2) // 2
    for k in range(3): arrow_key(im, x0 + k * (key + gap), y, key)
    return im


def arrow_key(im, x, y, s):
    """One arrow key like the emoji: a rounded blue-grey square with a white arrow pointing right."""
    k = Image.new("RGBA", (s, s), (0, 0, 0, 0)); d = ImageDraw.Draw(k); r = int(s * 0.2)
    d.rounded_rectangle([0, 0, s - 1, s - 1], r, fill=(92, 112, 138, 255))
    d.rounded_rectangle([int(s * .04), int(s * .04), s - 1 - int(s * .04), s - 1 - int(s * .06)], r, fill=(150, 172, 200, 255))
    t = int(s * 0.13); cy = s // 2; xa, xb = int(s * 0.2), int(s * 0.8)
    d.rectangle([xa, cy - t // 2, xb - int(s * 0.18), cy + t // 2], fill=(255, 255, 255, 255))
    d.polygon([(xb, cy), (xb - int(s * 0.26), cy - int(s * 0.24)), (xb - int(s * 0.26), cy + int(s * 0.24))], fill=(255, 255, 255, 255))
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
    """The photo filling the whole area edge to edge (cropped to fit, centred), no blurred bars."""
    return crisp(ImageOps.fit(im.convert("RGB"), (w, h), Image.LANCZOS, centering=(0.5, 0.5)))


def slide(a, b, SW=SW, SH=SH, badge=None):
    """Two photos stacked, each filling its half: one on top, one below, a thin dark line between them.
    With a badge, it covers the bottom-right corner of each half (where the old watermark of exported photos sits)."""
    im = Image.new("RGB", (SW, SH), (12, 12, 14)); gap = 6; hh = (SH - gap) // 2
    im.paste(fill(a, SW, hh), (0, 0)); im.paste(fill(b, SW, SH - hh - gap), (0, hh + gap))
    if badge is not None:
        im.paste(badge, (SW - badge.width, hh - badge.height)); im.paste(badge, (SW - badge.width, SH - badge.height))
    return im


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


TYPES = ["shoes", "bag", "wallet", "belt", "watch", "jewellery", "glasses", "hat", "top", "jacket", "pants", "shorts", "scarf", "other"]


def classify(shots):
    """Item type of each shot, from scripts/qc_categories.json; unknown shots are asked once of OpenAI (a small thumbnail,
    gpt-4o-mini) and the answer is stored. Without OPENAI_API_KEY, or when the call fails, the shot is "other" this time."""
    try: known = json.load(open(CATS_FILE))
    except Exception: known = {}
    key = os.environ.get("OPENAI_API_KEY", "").strip(); out, new = {}, 0
    for sid, im in shots:
        if sid in known: out[sid] = known[sid]; continue
        if not key: out[sid] = "other"; continue
        try:
            import base64, io
            t = im.copy(); t.thumbnail((384, 384)); buf = io.BytesIO(); t.convert("RGB").save(buf, "JPEG", quality=80)
            body = {"model": "gpt-4o-mini", "max_tokens": 5, "temperature": 0, "messages": [{"role": "user", "content": [
                {"type": "text", "text": "This is a quality-check photo of one fashion item. Answer with exactly one word from this list: " + ", ".join(TYPES)},
                {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode(), "detail": "low"}}]}]}
            req = urllib.request.Request("https://api.openai.com/v1/chat/completions", data=json.dumps(body).encode(),
                                         headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
            ans = json.load(urllib.request.urlopen(req, timeout=60))["choices"][0]["message"]["content"].strip().lower().strip(".")
            out[sid] = known[sid] = ans if ans in TYPES else "other"; new += 1
        except Exception as e:
            print("  could not classify a photo:", str(e)[:80]); out[sid] = "other"
    if new:
        json.dump(known, open(CATS_FILE, "w"), indent=0, sort_keys=True); print("  classified %d new photos" % new)
    return out


def pair_by_type(ims, rnd):
    """Reorder the shots so each slide (two in a row) shows two items of the same type; leftovers are paired together."""
    sid = lambda pid, im: im.info.get("sid") or pid
    labels = classify([(sid(pid, im), im) for pid, im in ims])
    lab = lambda k: labels.get(sid(*ims[k]), "other")
    groups = {}
    for k in range(len(ims)): groups.setdefault(lab(k), []).append(ims[k])
    pairs, rest = [], []
    for g in groups.values():
        rnd.shuffle(g)
        while len(g) >= 2: pairs.append((g.pop(), g.pop()))
        rest += g
    rnd.shuffle(rest)
    while len(rest) >= 2: pairs.append((rest.pop(), rest.pop()))
    rnd.shuffle(pairs)
    return [x for p in pairs for x in p] + rest


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
        if len(ims) >= need: break
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
    ims = ims[:need]; rnd.shuffle(ims); picked = sorted({pid for pid, _ in ims})
    qc_bg = ims.pop()[1] if a.qc_cover else None
    if not a.single: ims = pair_by_type(ims, rnd)
    for k in ([] if a.single else range(0, len(ims) - 1, 2)):   # two shots from the same file do not share a slide
        if ims[k][0] == ims[k + 1][0] and k + 2 < len(ims): ims[k + 1], ims[k + 2] = ims[k + 2], ims[k + 1]
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
    frames = [(cover_card(title, FW, FH, bg), min(1.4, max(0.9, a.hold * 1.4)))]      # the start picture stays a little longer than a slide
    if a.single:
        for _, im in ims: frames.append((whole(im, FW, FH), a.hold))
    else:
        badge = make_badge(int(FW * 0.15)) if a.badge else None
        for k in range(0, len(ims) - 1, 2): frames.append((slide(ims[k][1], ims[k + 1][1], FW, FH, badge), a.hold))
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
