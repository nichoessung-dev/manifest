# -*- coding: utf-8 -*-
"""
QC photo corner badge (26 Nov 2026, owner: "swap this in the corner with a QR code to our site", agreed with qualit.ly).
Many QC photos carry a dark badge in the top-right corner: a QR code over the word "Qualit.ly". swap(im) finds it and
paints our own badge in the same place: a QR code to puroclassico.com over "puroclassico.com". Photos without the badge
come back unchanged.

  swap(im) -> (image, True when the badge was swapped)
  python scripts/qc_badge.py in.webp out.png      try one photo

Detection: a multi-scale template match of the badge (scripts/qc_badge_tpl.png) in the top-right corner, so a dark
corner or a QR code printed on a product is left alone.
"""
import os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont

URL = "https://puroclassico.com"
LABEL = "puroclassico.com"
_FONTS = ["/usr/share/fonts/opentype/inter/Inter-SemiBold.otf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]


def _font(size):
    for f in _FONTS:
        if os.path.exists(f):
            return ImageFont.truetype(f, size)
    try:
        return ImageFont.load_default(size)
    except TypeError:
        return ImageFont.load_default()


TPL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "qc_badge_tpl.png")   # the qualit.ly badge, 108 x 139
THRESH = 0.47   # 45 banked photos: badges scored 0.52 to 1.0, photos without one 0.39 at most
_tpl = None


def find_badge(gray):
    """(x0, y0, x1, y1, score) of the qualit.ly badge in the top-right corner, or None. Multi-scale template match."""
    import cv2
    global _tpl
    if _tpl is None:
        _tpl = cv2.imread(TPL, 0)
    h, w = gray.shape
    ox = int(w * 0.6)
    reg = gray[: int(h * 0.45), ox:]
    best = (0, 1.0, (0, 0))
    def at(sc):
        t = cv2.resize(_tpl, None, fx=sc, fy=sc, interpolation=cv2.INTER_AREA if sc < 1 else cv2.INTER_CUBIC)
        if t.shape[0] > reg.shape[0] or t.shape[1] > reg.shape[1]:
            return None
        _, mv, _, ml = cv2.minMaxLoc(cv2.matchTemplate(reg, t, cv2.TM_CCOEFF_NORMED))
        return mv, sc, ml
    k = w / 900.0
    for sc in np.arange(0.4, 2.0, 0.05) * k:
        r = at(sc)
        if r and r[0] > best[0]: best = r
    for sc in np.arange(best[1] - 0.05, best[1] + 0.051, 0.01):
        r = at(sc)
        if r and r[0] > best[0]: best = r
    mv, sc, (x, y) = best
    if mv < THRESH:
        return None
    tw, th = int(round(_tpl.shape[1] * sc)), int(round(_tpl.shape[0] * sc))
    x0, y0 = ox + x, y
    if x0 + tw < w * 0.85:   # a badge sits in the corner
        return None
    box = gray[y0:y0 + th, x0:x0 + tw]
    if box.size == 0 or (box < 60).mean() < 0.3 or (box > 200).mean() < 0.15:   # dark box with a white code panel in it
        return None
    return x0, y0, x0 + tw - 1, y0 + th - 1, mv


WORDMARK = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logo-wordmark.png")


def _qr_matrix():
    import qrcode
    q = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, border=0, box_size=1)
    q.add_data(URL); q.make(fit=True)
    return q.get_matrix()


def make_badge(bw, bh):
    """Our badge at bw x bh, in the site's look: a near-black card with a hairline rim (the logo's circle line), a white
    rounded panel with the QR code (rounded finder eyes), and the script "puro classico" wordmark under it."""
    ss = 5
    W, H = bw * ss, bh * ss
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    r = int(min(W, H) * 0.13)
    d.rounded_rectangle([0, 0, W - 1, H - 1], radius=r, fill=(12, 12, 12, 255))
    rim = max(2, int(W * 0.012))
    d.rounded_rectangle([rim * 2, rim * 2, W - 1 - rim * 2, H - 1 - rim * 2], radius=r - rim * 2, outline=(255, 255, 255, 70), width=rim)
    pad = int(W * 0.1)
    side = W - 2 * pad
    d.rounded_rectangle([pad, pad, pad + side, pad + side], radius=int(side * 0.12), fill=(255, 255, 255, 255))
    m = _qr_matrix(); n = len(m)
    quiet = side * 0.08
    cell = (side - 2 * quiet) / n
    ox = oy = pad + quiet
    ink = (12, 12, 12, 255)
    eyes = [(0, 0), (n - 7, 0), (0, n - 7)]
    def in_eye(x, y):
        return any(ex <= x < ex + 7 and ey <= y < ey + 7 for ex, ey in eyes)
    for y, row in enumerate(m):
        for x, v in enumerate(row):
            if v and not in_eye(x, y):
                d.rectangle([ox + x * cell, oy + y * cell, ox + (x + 1) * cell - 0.5, oy + (y + 1) * cell - 0.5], fill=ink)
    for ex, ey in eyes:
        x0, y0 = ox + ex * cell, oy + ey * cell
        d.rounded_rectangle([x0, y0, x0 + 7 * cell - 1, y0 + 7 * cell - 1], radius=cell * 2.2, fill=ink)
        d.rounded_rectangle([x0 + cell, y0 + cell, x0 + 6 * cell - 1, y0 + 6 * cell - 1], radius=cell * 1.5, fill=(255, 255, 255, 255))
        d.rounded_rectangle([x0 + 2 * cell, y0 + 2 * cell, x0 + 5 * cell - 1, y0 + 5 * cell - 1], radius=cell * 0.9, fill=ink)
    # the script wordmark, white, centred in the space under the panel
    ly0, ly1 = pad + side, H - rim * 3
    wm = Image.open(WORDMARK).convert("RGBA")
    a = wm.getchannel("A")
    from PIL import ImageFilter
    a = a.filter(ImageFilter.MaxFilter(9))   # a heavier stroke, so the thin script stays readable at badge size
    white = Image.new("RGBA", wm.size, (255, 255, 255, 255)); white.putalpha(a)
    bb = white.getbbox(); white = white.crop(bb)
    tw = int(W * 0.86); th = int(white.height * tw / white.width)
    if th > (ly1 - ly0) * 0.85:
        th = int((ly1 - ly0) * 0.85); tw = int(white.width * th / white.height)
    white = white.resize((tw, th), Image.LANCZOS)
    im.alpha_composite(white, ((W - tw) // 2, int((ly0 + ly1 - th) / 2)))
    return im.resize((bw, bh), Image.LANCZOS)


def swap(im):
    rgb_im = im.convert("RGB")
    b = find_badge(np.asarray(rgb_im.convert("L")))
    if not b:
        return im, False
    bx0, by0, bx1, by1, _ = b
    w, h = rgb_im.size
    m = 2  # cover the old badge's soft edge
    bx0, by0, bx1, by1 = max(0, bx0 - m), max(0, by0 - m), min(w - 1, bx1 + m), min(h - 1, by1 + m)
    out = rgb_im.copy()
    badge = make_badge(bx1 - bx0 + 1, by1 - by0 + 1)
    out.paste(badge, (bx0, by0), badge)
    return out, True


if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2]
    out, ok = swap(Image.open(src))
    out.save(dst)
    print("swapped" if ok else "no badge")
