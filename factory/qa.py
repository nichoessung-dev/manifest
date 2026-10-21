# -*- coding: utf-8 -*-
"""QA for one rendered video: an 8-frame contact sheet to look at, plus the numbers a person should not have to guess.

  python factory/qa.py out/vf-puffer-1200            # the folder make_short.py wrote (or the .mp4 itself)

Prints JSON: seconds, voiceover flag from the render's own .json, audio loudness (mean / max dB, share of silence), black frames,
frozen stretches (product shots on paper and call-outs hold still on purpose: judge those on the sheet), and the sheet's path.
Writes <video>.sheet.jpg next to the video.
"""
import glob, json, os, re, subprocess, sys

from PIL import Image, ImageDraw
import imageio_ffmpeg

FF = imageio_ffmpeg.get_ffmpeg_exe()


def run(args):
    return subprocess.run([FF, "-hide_banner"] + args, capture_output=True, text=True).stderr


def video_of(p):
    if os.path.isdir(p):
        v = sorted(glob.glob(os.path.join(p, "*.mp4")))
        if not v: raise SystemExit("no mp4 in %s" % p)
        return v[0]
    return p


def qa(path):
    path = video_of(path); info = run(["-i", path])
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", info); secs = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 0.0
    has_audio = "Audio:" in info
    vol = run(["-i", path, "-vn", "-af", "volumedetect", "-f", "null", "-"]) if has_audio else ""
    mean = re.search(r"mean_volume: (-?[\d.]+) dB", vol); peak = re.search(r"max_volume: (-?[\d.]+) dB", vol)
    sil = run(["-i", path, "-vn", "-af", "silencedetect=noise=-45dB:d=0.6", "-f", "null", "-"]) if has_audio else ""
    silent = sum(float(x) for x in re.findall(r"silence_duration: ([\d.]+)", sil))
    blk = run(["-i", path, "-an", "-vf", "blackdetect=d=0.15:pix_th=0.06", "-f", "null", "-"])
    black = [(float(a), float(b)) for a, b in re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", blk)]
    frz = run(["-i", path, "-an", "-vf", "freezedetect=n=0.002:d=2.5", "-f", "null", "-"])
    starts = [float(x) for x in re.findall(r"freeze_start: ([\d.]+)", frz)]; durs = [float(x) for x in re.findall(r"freeze_duration: ([\d.]+)", frz)]
    frozen = list(zip(starts, durs))
    # contact sheet: 8 frames, evenly spread, with their times
    times = [secs * (k + 0.5) / 8 for k in range(8)]; tiles = []
    for t in times:
        raw = subprocess.run([FF, "-loglevel", "error", "-ss", "%.2f" % t, "-i", path, "-frames:v", "1", "-vf", "scale=270:480", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
        tiles.append(Image.frombuffer("RGB", (270, 480), raw[:270 * 480 * 3]) if len(raw) >= 270 * 480 * 3 else Image.new("RGB", (270, 480), (255, 0, 255)))
    sheet = Image.new("RGB", (4 * 270 + 30, 2 * (480 + 26) + 10), (24, 24, 24)); d = ImageDraw.Draw(sheet)
    for k, (im, t) in enumerate(zip(tiles, times)):
        x, y = 6 + (k % 4) * 276, 6 + (k // 4) * 512; sheet.paste(im, (x, y + 22)); d.text((x + 4, y + 4), "%.1fs" % t, fill=(255, 220, 0))
    out = os.path.splitext(path)[0] + ".sheet.jpg"; sheet.save(out, quality=88)
    meta = {}
    j = os.path.splitext(path)[0] + ".json"
    if os.path.exists(j): meta = json.load(open(j, encoding="utf-8"))
    rep = {"video": path, "seconds": round(secs, 2), "audio": has_audio, "voiceover": meta.get("voiceover"),
           "mean_db": float(mean.group(1)) if mean else None, "max_db": float(peak.group(1)) if peak else None, "silent_s": round(silent, 2),
           "black": black, "frozen": frozen, "missing_assets": meta.get("missing_assets", []), "sheet": out}
    problems = []
    if not 20 <= secs <= 41: problems.append("length %.1fs" % secs)
    if not has_audio or rep["mean_db"] is None or rep["mean_db"] < -35: problems.append("audio missing or too quiet")
    if meta and not meta.get("voiceover"): problems.append("no voiceover")
    if silent > 0.25 * secs: problems.append("%.1fs of silence" % silent)
    if black: problems.append("black frames at %s" % ", ".join("%.1f" % a for a, _ in black))
    if any(dur > 4.0 for _, dur in frozen): problems.append("a still stretch over 4s (check the sheet)")
    if rep["missing_assets"]: problems.append("missing library files")
    rep["problems"] = problems
    return rep


def layout_sheet(path, step=2.0, out=None):
    """Silent layout renders give every line 2 s: one frame from the middle of each line, to check hooks, product shots and tags."""
    path = video_of(path); info = run(["-i", path]); m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", info)
    secs = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)); n = max(1, int(round(secs / step))); tiles = []
    for k in range(n):
        t = k * step + step * 0.6
        raw = subprocess.run([FF, "-loglevel", "error", "-ss", "%.2f" % t, "-i", path, "-frames:v", "1", "-vf", "scale=270:480", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
        tiles.append((t, Image.frombuffer("RGB", (270, 480), raw[:270 * 480 * 3]) if len(raw) >= 270 * 480 * 3 else Image.new("RGB", (270, 480), (255, 0, 255))))
    cols = min(5, n); rows = (n + cols - 1) // cols
    sheet = Image.new("RGB", (cols * 276 + 6, rows * 512 + 6), (24, 24, 24)); d = ImageDraw.Draw(sheet)
    for k, (t, im) in enumerate(tiles):
        x, y = 6 + (k % cols) * 276, 6 + (k // cols) * 512; sheet.paste(im, (x, y + 22)); d.text((x + 4, y + 4), "line %d" % (k + 1), fill=(255, 220, 0))
    out = out or os.path.splitext(path)[0] + ".lines.jpg"; sheet.save(out, quality=88); return out


if __name__ == "__main__":
    if sys.argv[1:2] == ["--lines"]:
        for p in sys.argv[2:]: print(layout_sheet(p))
    else:
        for p in sys.argv[1:]: print(json.dumps(qa(p), ensure_ascii=False))
