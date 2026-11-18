# -*- coding: utf-8 -*-
"""A finished carousel as a 9:16 slideshow video with a whispered voice saying the item(s) on each slide, over quiet music
(owner, 18 Nov 2026: the whisper slideshows, for the second account Qualityfinds too).

Reads a rug carousel folder (scripts/make_rug.py: rug.json with the images, log.txt with each slide's item names), or any
list of slide images with --names. The cover shows first, then each slide for as long as its line takes.

  python scripts/slides_to_video.py --rug out/rug [--music-dir media/music-slideshow] [--out out/rug/rug.mp4]
  python scripts/slides_to_video.py --images a.jpg b.jpg ... --names '["", "moncler puffer", ...]' --out x.mp4
Env: ELEVENLABS_API_KEY (the whisper; without it the video is made with music only).
"""
import argparse, glob, json, os, random, subprocess, sys
from PIL import Image, ImageOps

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_finds as mf  # noqa: E402  (whisper_track, the ffmpeg binary)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H, FPS = 1080, 1920, 30


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rug"); ap.add_argument("--images", nargs="*"); ap.add_argument("--names", default="[]"); ap.add_argument("--prices", default="[]")
    ap.add_argument("--music-dir", default="media/music-slideshow"); ap.add_argument("--hold", type=float, default=2.2)
    ap.add_argument("--out"); ap.add_argument("--seed", type=int)
    a = ap.parse_args()
    if a.rug:
        meta = json.load(open(os.path.join(a.rug, "rug.json"), encoding="utf-8"))
        log = json.load(open(os.path.join(a.rug, "log.txt"), encoding="utf-8"))
        images = meta["images"]
        # owner, 18 Nov 2026: "make it also say the dollar amount": each item with its price
        def line(x):
            ns = x.get("label") or x.get("name") or []; us = x.get("usd") or []
            ns = ns if isinstance(ns, list) else [ns]; us = us if isinstance(us, list) else [us]
            return ", and ".join(n + (", %d dollars" % u if isinstance(u, (int, float)) and u else "") for n, u in zip(ns, us + [None] * len(ns)))
        spoken = [line(x) for x in log["slides"]]
        out = a.out or os.path.join(a.rug, "rug.mp4")
    else:
        images = a.images or []; names = json.loads(a.names); prices = json.loads(a.prices)
        names = names[1:] if len(names) == len(images) else names
        spoken = [(n + (", %d dollars" % p if isinstance(p, (int, float)) and p else "")) if n else "" for n, p in zip(names, prices + [None] * len(names))]
        out = a.out or "slideshow.mp4"
    if len(images) < 2: sys.exit("need a cover and at least one slide")
    frames = [(ImageOps.fit(Image.open(p).convert("RGB"), (W, H), Image.LANCZOS), min(1.4, a.hold * 1.4)) for p in images[:1]]
    frames += [(ImageOps.fit(Image.open(p).convert("RGB"), (W, H), Image.LANCZOS), a.hold) for p in images[1:]]
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    voice = mf.whisper_track([s.lower() for s in spoken], frames, a.hold, os.path.dirname(os.path.abspath(out)), 0)
    total = sum(d for _, d in frames)
    lib = sorted(glob.glob(os.path.join(ROOT, a.music_dir, "*.mp3")))
    music = random.Random(a.seed).choice(lib) if lib else None
    cmd = [mf.FF, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W, H), "-r", str(FPS), "-i", "-"]
    if voice and music:
        cmd += ["-i", voice, "-stream_loop", "-1", "-i", music, "-filter_complex",
                "[2:a]volume=0.22,afade=t=out:st=%.2f:d=0.6[m];[1:a][m]amix=inputs=2:duration=first:normalize=0[a]" % (total - 0.7), "-map", "0:v", "-map", "[a]"]
    elif voice: cmd += ["-i", voice]
    elif music: cmd += ["-stream_loop", "-1", "-i", music, "-af", "volume=0.6,afade=t=out:st=%.2f:d=0.6" % (total - 0.7)]
    else: cmd += ["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100"]
    cmd += ["-t", "%.3f" % total, "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", out]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for im, d in frames:
        raw = im.tobytes()
        for _ in range(int(round(d * FPS))): p.stdin.write(raw)
    p.stdin.close(); p.wait()
    print("wrote", out, "%.1fs" % total, len(frames) - 1, "slides,", "whisper" if voice else "no voice", "+", os.path.basename(music) if music else "no music")


if __name__ == "__main__":
    main()
