# -*- coding: utf-8 -*-
"""Background music for the product slideshow videos (owner, 18 Nov 2026: "the videos need some background music ... the
ones with only the products"). Generates instrumental tracks with ElevenLabs music into media/music-slideshow/ until the
library has --count tracks; scripts/make_finds.py --music-dir picks the least-used one per video, kept quiet under the
whispered voice. The talking format videos (make_short.py) are not affected.

  python scripts/make_music_lib.py [--count 20]
Env: ELEVENLABS_API_KEY.
"""
import argparse, glob, json, os, sys, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(ROOT, "media", "music-slideshow")
STYLES = [
    "Soft lo-fi hip hop instrumental, mellow Rhodes chords, dusty drums, relaxed and classy, 82 bpm",
    "Minimal deep house instrumental, warm sub bass, soft hi-hats, stylish late-night boutique feel, 120 bpm",
    "Chill R&B instrumental, smooth electric piano, gentle finger snaps, luxurious and calm, 90 bpm",
    "Ambient luxury fashion store music, airy pads, slow plucked guitar, elegant and quiet, 76 bpm",
    "Smooth jazz hop instrumental, upright bass, brushed drums, muted trumpet hints, cool and laid back, 88 bpm",
    "Soft afro house instrumental, light percussion, warm marimba, sunny and classy, 118 bpm",
    "Dreamy bedroom pop instrumental, chorus guitar, soft drum machine, nostalgic and calm, 95 bpm",
    "Old money piano lounge instrumental, light jazz piano trio, refined and relaxed, 84 bpm",
    "Downtempo electronic instrumental, glassy synth arps, deep soft kick, sleek and modern, 100 bpm",
    "Mellow boom bap instrumental, vinyl crackle, soft keys, nodding groove, 86 bpm",
]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--count", type=int, default=20); a = ap.parse_args()
    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not key: sys.exit("no ELEVENLABS_API_KEY")
    os.makedirs(DIR, exist_ok=True)
    have = sorted(glob.glob(os.path.join(DIR, "*.mp3")))
    k = len(have)
    while k < a.count:
        prompt = STYLES[k % len(STYLES)] + ", seamless steady loop, no vocals, no build-ups or drops, starts immediately"
        body = json.dumps({"prompt": prompt, "music_length_ms": 45000, "force_instrumental": True}).encode()
        req = urllib.request.Request("https://api.elevenlabs.io/v1/music?output_format=mp3_44100_128", data=body,
                                     headers={"xi-api-key": key, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=300) as r: b = r.read()
        except Exception as e:
            print("track", k + 1, "failed:", str(e)[:160]); break
        if len(b) < 20000: print("track", k + 1, "too small, stopping"); break
        path = os.path.join(DIR, "track-%02d.mp3" % (k + 1)); open(path, "wb").write(b)
        print("track", k + 1, len(b) // 1024, "KB:", STYLES[k % len(STYLES)][:60]); k += 1
    print("library:", k, "tracks")


if __name__ == "__main__":
    main()
