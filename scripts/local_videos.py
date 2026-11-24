# -*- coding: utf-8 -*-
"""Turns the slideshow packs on the release "month-content" (scripts/month_build.py) into finished videos with the owner's own
voice, made on the owner's PC with Chatterbox (owner, 25 Nov 2026), and puts each video on the release "month-videos".

Every video: the account's usual cover with "here is what I bought from China", each slide with its item and price, then
"check out puroclassico.com for finds like this" over the last slide. One of the owner's 8 tracks underneath, about 20 dB under
the voice (quiet, but there). Runs the voice on the CPU so the GPU stays free for Blender.

  C:/Users/nicho/chatterbox/.venv/Scripts/python.exe scripts/local_videos.py [--limit 5] [--device cpu] [--no-upload]

Keeps everything in C:/Users/nicho/Downloads/month-content (packs, voice lines, videos) for good.
"""
import argparse, glob, json, os, random, re, subprocess, sys, time, zipfile
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.environ.get("MONTH_WORK", "C:/Users/nicho/Downloads/month-content")
VOICE = os.environ.get("OWNER_VOICE", "C:/Users/nicho/voice-clean/out/narrator/owner_slides.wav")
FF = os.environ.get("FFMPEG") or __import__("imageio_ffmpeg").get_ffmpeg_exe()
PACKS_TAG, VIDEOS_TAG = "month-content", "month-videos"
INTRO = "here is what I bought from China."
OUTRO = "check out puroclassico.com for finds like this."
OUTRO_SAY = "check out puro classico dot com, for finds like this."     # how the voice should say it
EXAG, CFG = 0.65, 0.5                                                      # owner picked strength 0.65 (25 Nov 2026)
W, H, FPS = 1080, 1920, 30
SR = 24000
_M = [None]


def sh(cmd, **kw): return subprocess.run(cmd, **kw)


def model(device):
    if _M[0] is None:
        import torch
        from chatterbox.tts import ChatterboxTTS
        m = ChatterboxTTS.from_pretrained(device=device); m.prepare_conditionals(VOICE, exaggeration=EXAG); _M[0] = m
    return _M[0]


def trim(w, thr=0.012, pad=0.06):
    a = np.abs(w); idx = np.where(a > thr * max(1e-6, a.max()) * 4)[0]
    if not len(idx): return w
    s, e = max(0, idx[0] - int(pad * SR)), min(len(w), idx[-1] + int(pad * SR * 2)); return w[s:e]


def expected(text):
    """About how long the line takes to say: a digit is said as a word ("25" = "twenty five")."""
    t = text.lower(); n = len(re.sub(r"[^a-z]", "", t)) + 5 * len(re.findall(r"\d", t))
    return max(0.9, n / 13.0)


def say(text, device, seed=0, tries=4):
    """One clean take of a line: trimmed, and its length must fit the words (a garbled or run-on take is made again)."""
    import torch
    m = model(device); best = None
    for t in range(tries):
        torch.manual_seed(7000 + seed * 10 + t)
        w = m.generate(text, exaggeration=EXAG, cfg_weight=CFG).squeeze(0).cpu().numpy().astype(np.float32)
        w = trim(w); d = len(w) / SR; e = expected(text); r = d / e
        if 0.55 <= r <= 1.7: return w
        if best is None or abs(np.log(r)) < abs(np.log(best[1])): best = (w, r)
        print("    retake (%.1fs for ~%.1fs): %s" % (d, e, text[:50]), flush=True)
    return best[0]


def fixed_line(name, text, device):
    """The intro and the ending are the same in every video: made once (the take closest to a normal length) and reused."""
    p = os.path.join(WORK, "voice", name + ".npy")
    if os.path.exists(p): return np.load(p)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    takes = [say(text, device, seed=900 + k, tries=2) for k in range(4)]
    e = expected(text); w = min(takes, key=lambda x: abs(len(x) / SR - e * 1.05))
    np.save(p, w); write_wav(p[:-4] + ".wav", w); return w


def write_wav(path, w):
    import wave
    x = np.clip(w, -1, 1); x = (x * 32767).astype(np.int16)
    with wave.open(path, "wb") as f: f.setnchannels(1); f.setsampwidth(2); f.setframerate(SR); f.writeframes(x.tobytes())


def music_pick(state):
    lib = sorted(glob.glob(os.path.join(ROOT, "media", "music-slideshow", "*.mp3")))
    mu = state.setdefault("music", {}); random.shuffle(lib); lib.sort(key=lambda f: mu.get(os.path.basename(f), 0))
    mu[os.path.basename(lib[0])] = mu.get(os.path.basename(lib[0]), 0) + 1; return lib[0]


def render(pk_dir, pk, device, state):
    from PIL import Image, ImageOps
    intro, outro = fixed_line("intro", INTRO, device), fixed_line("outro", OUTRO_SAY, device)
    lines = []
    for j, s in enumerate(pk["slides"]):
        t = re.sub(r"\s+", " ", (s.get("say") or "").replace("&", " and ")).strip()
        lines.append(say(t + ".", device, seed=j) if t else None)
    gap = 0.35
    frames, voice = [], []                                   # (image path, seconds); (clip, start)
    d0 = max(1.6, len(intro) / SR + 0.5); frames.append((os.path.join(pk_dir, pk["cover"]), d0)); voice.append((intro, 0.2)); t = d0
    for j, s in enumerate(pk["slides"]):
        c = lines[j]; d = max(1.3, (len(c) / SR + gap) if c is not None else 1.3)
        if c is not None: voice.append((c, t + 0.12))
        if j == len(pk["slides"]) - 1:
            voice.append((outro, t + d + 0.1)); d += len(outro) / SR + 0.9
        frames.append((os.path.join(pk_dir, s["img"]), d)); t += d
    total = t
    track = np.zeros(int((total + 0.5) * SR), np.float32)
    for c, st in voice:
        i = int(st * SR); track[i:i + len(c)] += c[:max(0, len(track) - i)]
    vw = os.path.join(pk_dir, "voice.wav"); write_wav(vw, track)
    music = music_pick(state); out = os.path.join(WORK, "videos", pk["id"] + ".mp4"); os.makedirs(os.path.dirname(out), exist_ok=True)
    # the voice clearly on top, the music about 20 dB under it but still there (owner, 25 Nov 2026)
    fc = ("[1:a]aresample=44100,loudnorm=I=-15:TP=-1.5:LRA=11[v];"
          "[2:a]aresample=44100,loudnorm=I=-35:TP=-8,afade=t=in:d=0.4,afade=t=out:st=%.2f:d=0.8[m];"
          "[v][m]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.89[a]") % max(0, total - 0.8)
    cmd = [FF, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W, H), "-r", str(FPS), "-i", "-",
           "-i", vw, "-stream_loop", "-1", "-i", music, "-filter_complex", fc, "-map", "0:v", "-map", "[a]", "-t", "%.3f" % total,
           "-c:v", "libx264", "-preset", "medium", "-crf", "21", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", out]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE); n = 0
    for path, d in frames:
        raw = ImageOps.fit(Image.open(path).convert("RGB"), (W, H), Image.LANCZOS).tobytes(); k = int(round(d * FPS))
        for _ in range(k): p.stdin.write(raw)
        n += k
    p.stdin.close(); p.wait()
    if p.returncode or not os.path.exists(out): raise RuntimeError("ffmpeg failed for " + pk["id"])
    meta = {"format": "month-video", "account": pk["account"], "images": [], "ids": [], "caption": pk.get("caption") or "",
            "seconds": round(total, 1), "voiceover": True, "file": pk["id"] + ".mp4", "product_url": "https://www.puroclassico.com/spreadsheet",
            "music": os.path.basename(music), "says": [INTRO] + [s.get("say") for s in pk["slides"]] + [OUTRO]}
    json.dump(meta, open(out[:-4] + ".json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return out, total


def assets(tag):
    r = sh(["gh", "release", "view", tag, "--json", "assets", "-q", ".assets[].name"], capture_output=True, text=True, cwd=ROOT)
    return set(r.stdout.split()) if r.returncode == 0 else None


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--limit", type=int, default=0); ap.add_argument("--device", default="cpu")
    ap.add_argument("--no-upload", action="store_true"); ap.add_argument("--only", default=""); ap.add_argument("--loop", action="store_true", help="keep checking for new packs")
    a = ap.parse_args()
    if a.device == "cpu": os.environ["CUDA_VISIBLE_DEVICES"] = ""
    for d in ("packs", "videos", "voice"): os.makedirs(os.path.join(WORK, d), exist_ok=True)
    sp = os.path.join(WORK, "state.json")
    try: state = json.load(open(sp))
    except Exception: state = {}
    if not a.no_upload and assets(VIDEOS_TAG) is None:
        sh(["gh", "release", "create", VIDEOS_TAG, "--prerelease", "--title", "Month videos: finished", "--notes", "Finished month videos (scripts/local_videos.py). Not a software release."], cwd=ROOT)
    made = 0
    while True:
        sh(["gh", "release", "download", PACKS_TAG, "-p", "*.zip", "-D", os.path.join(WORK, "packs"), "--skip-existing"], cwd=ROOT, capture_output=True)
        done = (assets(VIDEOS_TAG) or set()) if not a.no_upload else set()
        todo = [z for z in sorted(glob.glob(os.path.join(WORK, "packs", "*.zip"))) if (not a.only or a.only in z)]
        todo = [z for z in todo if os.path.basename(z)[:-4] + ".mp4" not in done and not (a.no_upload and os.path.exists(os.path.join(WORK, "videos", os.path.basename(z)[:-4] + ".mp4")))]
        if not todo:
            if not a.loop: break
            print("waiting for new packs...", flush=True); time.sleep(300); continue
        for z in todo:
            if a.limit and made >= a.limit: break
            pid = os.path.basename(z)[:-4]; pk_dir = os.path.join(WORK, "packs", pid)
            with zipfile.ZipFile(z) as f: f.extractall(pk_dir)
            pk = json.load(open(os.path.join(pk_dir, "slides.json"), encoding="utf-8")); t0 = time.time()
            print("video", pid, len(pk["slides"]), "slides", flush=True)
            try: out, total = render(pk_dir, pk, a.device, state)
            except Exception as e: print("  FAILED:", str(e)[:200], flush=True); continue
            json.dump(state, open(sp, "w"), indent=0)
            print("  made %s (%.1fs long) in %.0fs" % (os.path.basename(out), total, time.time() - t0), flush=True)
            if not a.no_upload:
                r = sh(["gh", "release", "upload", VIDEOS_TAG, out, out[:-4] + ".json", "--clobber"], cwd=ROOT)
                if r.returncode: print("  upload failed, will try again next time", flush=True); continue
            made += 1
        if (a.limit and made >= a.limit) or not a.loop: break
    print("videos made:", made)


if __name__ == "__main__":
    main()
