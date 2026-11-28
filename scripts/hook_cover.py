# -*- coding: utf-8 -*-
"""Bold "hook" covers for some slideshows (owner, 28 Nov 2026: "lets get creative and switch it up on some videos").

Big condensed white words with a thick black outline, one or two words a line, stacked in the middle of a boxes
photo, like "BEST CARDIGANS TO BUY INSTEAD OF ZARA". The hooks fit a mixed haul (jackets, shoes, bags in one slideshow).

  from hook_cover import hook_cover, wants_hook
"""
import os, random
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTS = os.path.join(ROOT, "scripts", "fonts")
COVERS = sorted(os.path.join(ROOT, "scripts", "rug", "covers", f) for f in os.listdir(os.path.join(ROOT, "scripts", "rug", "covers")) if f.endswith(".jpg"))
SHARE = float(os.environ.get("HOOK_SHARE", "0.4"))        # about 2 in 5 slideshows get a hook cover

HOOKS = [
    "Best Finds To Buy Instead Of Zara",
    "Old Money Pieces To Buy Instead Of Zara",
    "Clothes That Look 10x More Expensive",
    "Stop Buying Your Clothes At Zara",
    "Finds That Look Like Designer",
    "Pieces Every Old Money Guy Needs",
    "Rich Guy Wardrobe For Less",
    "Things I Would Buy Again",
    "Best Winter Finds Instead Of Moncler",
    "Pov: You Stopped Shopping At Zara",
    "Grisch Pieces You Need This Winter",
    "Designer Looks Without Designer Prices",
]


def wants_hook(seed):
    return random.Random("hook-" + str(seed)).random() < SHARE


def _lines(words, rnd):
    """One word a line mostly; sometimes two short words share a line, for a different rhythm."""
    out, i = [], 0
    pair = rnd.random() < 0.4
    while i < len(words):
        if pair and i + 1 < len(words) and len(words[i]) + len(words[i + 1]) <= 7: out.append(words[i] + " " + words[i + 1]); i += 2
        else: out.append(words[i]); i += 1
    return out


def hook_cover(seed, img=None, text=None):
    rnd = random.Random("hookc-" + str(seed))
    text = text or rnd.choice(HOOKS)
    img = img or COVERS[rnd.randrange(len(COVERS))]
    im = ImageOps.fit(Image.open(img).convert("RGB"), (1080, 1920), Image.LANCZOS)
    d = ImageDraw.Draw(im)
    rows = _lines(text.upper().split(), rnd)
    big = 150
    while big > 90:                                            # the longest line fits 86% of the width
        f1, f2 = ImageFont.truetype(os.path.join(FONTS, "Anton-Regular.ttf"), big), ImageFont.truetype(os.path.join(FONTS, "Anton-Regular.ttf"), int(big * 0.76))
        wid = lambda r: sum(d.textlength(w[0], font=f1) + d.textlength(w[1:], font=f2) for w in r.split(" ")) + d.textlength(" ", font=f2) * r.count(" ")
        if max(wid(r) for r in rows) <= 1080 * 0.86 and len(rows) * big * 1.08 <= 1920 * 0.72: break
        big -= 6
    lh = int(big * 1.08); y = int(1920 * rnd.uniform(0.47, 0.53) - lh * len(rows) / 2); sw = max(6, big // 16)
    for r in rows:
        x = (1080 - wid(r)) / 2
        for n, w in enumerate(r.split(" ")):
            if n: x += d.textlength(" ", font=f2)
            for part, f in ((w[0], f1), (w[1:], f2)):          # a bigger first letter, like the reference
                if not part: continue
                d.text((x, y + (0 if f is f1 else big - int(big * 0.76))), part, font=f, fill="white", stroke_width=sw, stroke_fill="black")
                x += d.textlength(part, font=f)
        y += lh
    return im


if __name__ == "__main__":
    import sys
    out = sys.argv[1] if len(sys.argv) > 1 else "."
    for k, h in enumerate(HOOKS):
        hook_cover(k, COVERS[k % len(COVERS)], h).save(os.path.join(out, "hook%02d.jpg" % k), quality=90)
