# -*- coding: utf-8 -*-
"""A "finds" post: a simple cover, then slides with two photos stacked (one on top, one below), over a sound.

  python scripts/make_finds.py --folder <Drive folder id of photos> [--audio <Drive file id>] [--cover <Drive file id>] [--slides 7] [--title "Old money finds"]
  python scripts/make_finds.py --local <directory of photos> ...        (for testing)

The Drive folder must be shared by link. Photos are picked least-used first, in random order among equally used ones (finds_used.json keeps the counts), so they repeat only once the pool is used up.
"""
import argparse, glob, hashlib, html, json, os, random, re, subprocess, sys, tempfile, urllib.request
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps
import imageio_ffmpeg

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H, FPS = 1080, 1920, 30
SW, SH = 1080, 1440                                          # carousel slides are 3:4: the TikTok app shows that shape whole, a 9:16 photo gets cut top and bottom
FF = imageio_ffmpeg.get_ffmpeg_exe()
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"}
CACHE = os.path.join(tempfile.gettempdir(), "pc_finds"); os.makedirs(CACHE, exist_ok=True)
FONT = os.path.join(ROOT, "scripts", "fonts", "Montserrat.ttf")


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


COVER_TEXT = "Grisch finds"                                  # the only words on the first image
HOOKS = ["%s", "%s, which one would you wear?", "%s you will want to save", "New %s", "%s, pick your favourite", "This week's %s", "%s worth a look", "%s, save for later"]
TAGS = ["#finds", "#haul", "#fashion", "#quietluxury", "#oldmoneystyle", "#oldmoneyaesthetic", "#mensfashion", "#outfitinspo", "#stockholmstyle", "#fashionfinds", "#autumnfashion"]


def cover_card(title, SW=SW, SH=SH, bg=None):
    """The start image: the title in heavy type with an arrow under it, on off-white or over a picture."""
    ink = (255, 255, 255) if bg is not None else (16, 18, 26)
    if bg is None: im = Image.new("RGB", (SW, SH), (244, 242, 238))
    else:
        im = ImageOps.fit(bg.convert("RGB"), (SW, SH), Image.LANCZOS)
        im = Image.blend(im, Image.new("RGB", (SW, SH), (0, 0, 0)), 0.22)          # a touch darker so white type reads on any picture
    d = ImageDraw.Draw(im); size = 170; lines = title.upper().split()
    while size > 70 and max(d.textlength(w, font=font(size)) for w in lines) > SW - 160: size -= 6
    f = font(size); lh = int(size * 1.06); aw, at = int(SW * 0.30), max(14, size // 8)
    y = SH // 2 - (lh * len(lines) + at * 6) // 2 - 40
    if bg is not None:                                           # a soft shadow under the type and the arrow
        sh = Image.new("L", (SW, SH), 0); sd = ImageDraw.Draw(sh); yy = y
        for ln in lines: sd.text((SW / 2, yy + 6), ln, font=f, fill=200, anchor="ma"); yy += lh
        draw_arrow(sd, SW // 2, yy + at * 4 + 6, aw, 200, at)
        im.paste((0, 0, 0), (0, 0), sh.filter(ImageFilter.GaussianBlur(14))); d = ImageDraw.Draw(im)
    for ln in lines: d.text((SW / 2, y), ln, font=f, fill=ink, anchor="ma"); y += lh
    draw_arrow(d, SW // 2, y + at * 4, aw, ink, at)
    return im


def draw_arrow(d, cx, y, w, col, t):
    """A bold arrow pointing right, centred on cx."""
    x0, x1, h = cx - w // 2, cx + w // 2, int(t * 2.3)
    d.line([(x0, y), (x1 - h, y)], fill=col, width=t)
    d.ellipse([x0 - t // 2, y - t // 2, x0 + t // 2, y + t // 2], fill=col)
    d.polygon([(x1, y), (x1 - int(h * 1.5), y - h), (x1 - int(h * 1.5), y + h)], fill=col)


def whole(im, w, h):
    """The whole photo, nothing cut off: scaled to fit, with a blurred copy of itself filling what is left at the sides."""
    im = im.convert("RGB"); bg = ImageOps.fit(im, (w, h), Image.BILINEAR).filter(ImageFilter.GaussianBlur(28))
    fg = ImageOps.contain(im, (w, h), Image.LANCZOS); bg.paste(fg, ((w - fg.width) // 2, (h - fg.height) // 2)); return bg


def slide(a, b, SW=SW, SH=SH):
    """Two photos stacked, each shown whole: one in the top half, one in the bottom half."""
    im = Image.new("RGB", (SW, SH), (255, 255, 255)); hh = (SH - 10) // 2
    im.paste(whole(a, SW, hh), (0, 0)); im.paste(whole(b, SW, hh), (0, hh + 10)); return im


def tall(im):
    """A 3:4 slide centred on a 9:16 frame, for the video version."""
    bg = ImageOps.fit(im, (W, H), Image.BILINEAR).filter(ImageFilter.GaussianBlur(40)); bg.paste(im, (0, (H - SH) // 2)); return bg


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--folder"); ap.add_argument("--local"); ap.add_argument("--audio"); ap.add_argument("--cover"); ap.add_argument("--covers", help="Drive folder of start pictures (one is picked per post, least used first)")
    ap.add_argument("--slides", type=int, default=7); ap.add_argument("--title", default=""); ap.add_argument("--part", type=int, default=0)
    ap.add_argument("--hold", type=float, default=2.2); ap.add_argument("--out", default=os.path.join(ROOT, "out")); ap.add_argument("--seed", type=int)
    ap.add_argument("--video", action="store_true", help="a full-screen 9:16 video of the slides instead of a photo carousel")
    ap.add_argument("--qc-cover", action="store_true", help="the start picture is one of the QC photos, so the post shows QC photos only")
    ap.add_argument("--commit-state", action="store_true"); a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)
    rnd = random.Random(a.seed)
    if a.local: pool = [(hashlib.md5(open(f, "rb").read()).hexdigest(), f) for f in sorted(glob.glob(os.path.join(a.local, "*"))) if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))]
    else: pool = drive_images(a.folder)
    pool = list(dict(pool).items()); state_path = os.path.join(ROOT, "finds_used.json")
    try: used = json.load(open(state_path))
    except Exception: used = {"count": {}, "part": 0}
    need = a.slides * 2 + (1 if a.qc_cover else 0)             # one more photo when the start picture is a QC photo too
    if len(pool) < need: raise SystemExit("only %d photos in the pool, need %d" % (len(pool), need))
    rnd.shuffle(pool); pool.sort(key=lambda p: used["count"].get(p[0], 0))          # least-used photos first, in random order among equally used ones
    bad = set(used.get("skip", [])); ims = []                   # photos that could not be used are remembered, not retried
    for pid, path in [p for p in pool if p[0] not in bad]:
        if len(ims) >= need: break
        path = path or drive_get(pid, "img")
        try:
            parts = split_stacked(Image.open(path).convert("RGB"))
            if parts is None: print("  skipping an oddly laid out photo"); bad.add(pid); continue      # the join is not in the middle
            for im in parts:
                mx = int(im.width * 0.012); ims.append((pid, im.crop((mx, mx, im.width - mx, im.height - mx))))        # only a hair off the edges
        except Exception as e: print("  skipping a photo:", e)
    used["skip"] = sorted(bad)
    if len(ims) < need:                                         # never publish a post with missing slides
        if a.commit_state: json.dump(used, open(state_path, "w"), indent=0)
        raise SystemExit("only %d usable photos, need %d" % (len(ims), need))
    ims = ims[:need]; rnd.shuffle(ims); picked = sorted({pid for pid, _ in ims})
    qc_bg = ims.pop()[1] if a.qc_cover else None
    for k in range(0, len(ims) - 1, 2):                         # two shots from the same file do not share a slide
        if ims[k][0] == ims[k + 1][0] and k + 2 < len(ims): ims[k + 1], ims[k + 2] = ims[k + 2], ims[k + 1]
    part = a.part or int(used.get("part", 0)) + 1
    title = a.title or COVER_TEXT                               # the cover always says the same; the caption hook and tags vary
    hook = rnd.choice(HOOKS) % title.lower()
    caption = "%s\n\n%s" % (hook[0].upper() + hook[1:], " ".join(["#grisch", "#oldmoney"] + rnd.sample(TAGS, 3)))
    FW, FH = (W, H) if a.video else (SW, SH)                     # video slides fill the 9:16 screen; carousel slides are 3:4
    bg, cover_id = None, None
    if qc_bg is not None: bg = qc_bg
    elif a.cover and drive_get(a.cover, "img"): bg = Image.open(drive_get(a.cover, "img"))
    elif a.covers:                                               # a start picture from the folder, least used first
        cu = used.setdefault("covers", {}); cl = [i for i, t in drive_list(a.covers) if t.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))]
        rnd.shuffle(cl); cl.sort(key=lambda i: cu.get(i, 0))
        for cid in cl[:6]:
            try: bg = Image.open(drive_get(cid, "img")); bg.load(); cover_id = cid; break
            except Exception as e: bg = None; print("  skipping a start picture:", e)
    frames = [(cover_card(title, FW, FH, bg), min(1.4, max(0.9, a.hold * 1.4)))]      # the start picture stays a little longer than a slide
    for k in range(0, len(ims) - 1, 2): frames.append((slide(ims[k][1], ims[k + 1][1], FW, FH), a.hold))
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
        ip = os.path.join(a.out, "finds-%d-%02d.jpg" % (part, k)); im.save(ip, quality=92); imgs.append(ip)
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
