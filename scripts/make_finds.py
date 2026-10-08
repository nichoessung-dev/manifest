# -*- coding: utf-8 -*-
"""A "finds" post: a simple cover, then slides with two photos stacked (one on top, one below), over a sound.

  python scripts/make_finds.py --folder <Drive folder id of photos> [--audio <Drive file id>] [--cover <Drive file id>] [--slides 7] [--title "Old money finds"]
  python scripts/make_finds.py --local <directory of photos> ...        (for testing)

The Drive folder must be shared by link. Photos already used are remembered in finds_used.json so posts do not repeat pairs.
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


def drive_get(fid, ext):
    path = os.path.join(CACHE, "%s.%s" % (fid, ext))
    if not os.path.exists(path):
        for u in ("https://drive.google.com/uc?export=download&id=%s" % fid, "https://drive.usercontent.google.com/download?id=%s&export=download&confirm=t" % fid):
            try:
                d = fetch(u)
                if len(d) > 5000 and not d[:15].lstrip().lower().startswith(b"<!doctype"): open(path, "wb").write(d); break
            except Exception: pass
    return path if os.path.exists(path) else None


def cover_card(title, part, SW=SW, SH=SH):
    """A plain start image: the title in heavy type on off-white."""
    im = Image.new("RGB", (SW, SH), (244, 242, 238)); d = ImageDraw.Draw(im); size = 150
    while size > 70 and max(d.textlength(w, font=font(size)) for w in title.upper().split()) > SW - 160: size -= 6
    f = font(size); lines = [w for w in title.upper().split() if w != "/"]; y = SH // 2 - int(size * 1.08 * len(lines)) // 2 - 60
    for ln in lines: d.text((SW / 2, y), ln, font=f, fill=(16, 18, 26), anchor="ma"); y += int(size * 1.08)
    return im


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
    ap = argparse.ArgumentParser(); ap.add_argument("--folder"); ap.add_argument("--local"); ap.add_argument("--audio"); ap.add_argument("--cover")
    ap.add_argument("--slides", type=int, default=7); ap.add_argument("--title", default="Grisch / old money finds"); ap.add_argument("--part", type=int, default=0)
    ap.add_argument("--hold", type=float, default=2.2); ap.add_argument("--out", default=os.path.join(ROOT, "out")); ap.add_argument("--seed", type=int)
    ap.add_argument("--video", action="store_true", help="a full-screen 9:16 video of the slides instead of a photo carousel")
    ap.add_argument("--commit-state", action="store_true"); a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)
    rnd = random.Random(a.seed)
    if a.local: pool = [(hashlib.md5(open(f, "rb").read()).hexdigest(), f) for f in sorted(glob.glob(os.path.join(a.local, "*"))) if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))]
    else: pool = [(i, None) for i, t in drive_list(a.folder) if t.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))]
    pool = list(dict(pool).items()); state_path = os.path.join(ROOT, "finds_used.json")
    try: used = json.load(open(state_path))
    except Exception: used = {"count": {}, "part": 0}
    need = a.slides * 2
    if len(pool) < need: raise SystemExit("only %d photos in the pool, need %d" % (len(pool), need))
    rnd.shuffle(pool); pool.sort(key=lambda p: used["count"].get(p[0], 0))          # least-used photos first, random among equals
    bad = set(used.get("skip", [])); ims = []                   # photos that could not be used are remembered, not retried
    for pid, path in [p for p in pool if p[0] not in bad]:
        if len(ims) >= need: break
        path = path or drive_get(pid, "img")
        try:
            im = Image.open(path).convert("RGB")
            if im.height > im.width * 1.5:                       # a source that is already two stacked shots: keep the main (top) one
                g = im.convert("L").resize((48, 240)); px = g.load(); rows = [sum(px[x, y] for x in range(48)) / 48.0 for y in range(240)]
                seam = max(range(48, 192), key=lambda y: abs(rows[y] - rows[y - 1]) + abs(rows[y + 1] - rows[y]))
                if not 108 <= seam <= 132: print("  skipping an oddly laid out photo"); bad.add(pid); continue      # the join is not in the middle
                im = im.crop((0, 0, im.width, im.height // 2))
            mx = int(im.width * 0.012); im = im.crop((mx, mx, im.width - mx, im.height - mx))        # only a hair off the edges
            ims.append((pid, im))
        except Exception as e: print("  skipping a photo:", e)
    used["skip"] = sorted(bad)
    if len(ims) < need:                                         # never publish a post with missing slides
        if a.commit_state: json.dump(used, open(state_path, "w"), indent=0)
        raise SystemExit("only %d usable photos, need %d" % (len(ims), need))
    rnd.shuffle(ims)
    part = a.part or int(used.get("part", 0)) + 1
    FW, FH = (W, H) if a.video else (SW, SH)                     # video slides fill the 9:16 screen; carousel slides are 3:4
    frames = [(Image.open(drive_get(a.cover, "img")).convert("RGB") if a.cover and drive_get(a.cover, "img") else cover_card(a.title, part, FW, FH), 1.4)]
    if frames[0][0].size != (FW, FH): frames[0] = (ImageOps.fit(frames[0][0], (FW, FH), Image.LANCZOS), 1.4)
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
    meta = {"format": "finds", "images": imgs, "ids": [], "caption": "%s\n\n#grisch #oldmoney #finds #haul #fashion" % a.title,
            "seconds": round(total, 1), "voiceover": False, "file": out, "product_url": "https://www.puroclassico.com/"}
    json.dump(meta, open(out[:-4] + ".json", "w"), indent=1, ensure_ascii=False)
    print("wrote", out, "%.1fs" % total, len(frames) - 1, "slides", "with sound" if audio else "silent")
    if a.commit_state:
        for pid, _ in ims: used["count"][pid] = used["count"].get(pid, 0) + 1
        used["part"] = part; json.dump(used, open(state_path, "w"), indent=0)


if __name__ == "__main__":
    main()
