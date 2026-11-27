# -*- coding: utf-8 -*-
"""Make closer and angled versions of the main account's rug photo (owner, 27 Nov 2026), to try as backgrounds.

  python scripts/make_bg_angles.py --out bg-angles
Env: GEMINI_API_KEY, RUG_MODELS. Writes one jpg per view.
"""
import argparse, os, sys
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("RUG_BG", os.path.join(os.path.dirname(os.path.abspath(__file__)), "rug", "main_bg.png"))
import make_rug as M

BASE = ("Image 1 is a real iPhone photo of my cream Maison Margiela rug (black numbers 0 to 23, the 3 circled, 'Maison Margiela PARIS') "
        "on a cream woven carpet in my walk-in closet, under a wooden shelf with shoes. Make a new photo of the SAME rug in the SAME room, "
        "same light and colours, nothing added or removed, the rug empty, taken with the same iPhone, a plain camera-roll photo, not a render. "
        "Keep the rug's text and numbers exactly right. Vertical 9:16. ")
VIEWS = {
    "close-top": "Standing right over the rug, phone pointing straight down from about 1 metre: the whole rug fills most of the photo, a little carpet around it, the shelf edge just visible at the top.",
    "close-angle": "Standing at the front edge of the rug, phone tilted down about 45 degrees: the rug fills the lower two thirds, the shoe shelf visible behind it.",
    "detail": "Crouching close, phone pointing down from about 50 cm: only part of the rug, the numbers 10 to 23 and 'Maison Margiela' filling the photo, for small items like a wallet or glasses.",
    "side": "Standing at the left side of the rug, phone tilted down about 50 degrees, the rug seen at an angle with the shelf on the right side of the photo.",
}
ap = argparse.ArgumentParser(); ap.add_argument("--out", default="bg-angles"); a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)
src = M.jpeg(Image.open(M.RUG), 1536)
for name, view in VIEWS.items():
    for m in M.MODELS:
        try:
            png, use = M.gemini_image(m, [src], BASE + view)
            open(os.path.join(a.out, name + ".jpg"), "wb").write(png); print("made", name, "with", m, flush=True); break
        except Exception as e: print(name, m, str(e)[:200])
