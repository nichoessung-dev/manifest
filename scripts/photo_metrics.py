# -*- coding: utf-8 -*-
"""Pillow-only photo checks (no numpy): cut-out quality, framing, size, background, collage / text hints.

Most catalogue photos (Nov 2026) are ALREADY cut-outs: 1200x1200 RGBA WebP with a transparent background, which the
site puts on a light card. So the useful checks are about the mask (alpha):
  parts      separate pieces of the item mask (2+ big pieces = a set, a pair, front+back views or a collage)
  specks     tiny loose fragments (hanger hooks, rack poles, dust the cut-out kept)
  fill       longest side of the item / canvas side (RepLibrary-style shots sit around 0.80-0.88, all alike)
  off_x/y    item box centre minus canvas centre, as a share of the side
  touches    item box touches the canvas edge (cropped item)
  soft       share of half-transparent pixels in the item (hazy or fringed mask)
Photos without transparency fall back to border checks (is the frame white / plain?).

measure(im) -> dict of numbers + flags. Thresholds were set by eye on a 160-photo random sample of the live site.
"""
from PIL import Image, ImageChops, ImageFilter, ImageOps

N = 192          # analysis size for masks (long side)


def _rgb_on_white(im):
    if "A" in im.getbands():
        bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
        bg.alpha_composite(im.convert("RGBA"))
        return bg.convert("RGB")
    return im.convert("RGB")


def components(mask):
    """Connected pieces (4-neighbour) of a binary 'L' mask (255 = on). Returns sorted list of (area, bbox)."""
    w, h = mask.size
    px = list(mask.getdata())
    seen = bytearray(w * h)
    out = []
    for start in range(w * h):
        if px[start] < 128 or seen[start]:
            continue
        stack = [start]; seen[start] = 1; area = 0
        x0, y0, x1, y1 = w, h, 0, 0
        while stack:
            k = stack.pop(); area += 1
            x, y = k % w, k // w
            if x < x0: x0 = x
            if x > x1: x1 = x
            if y < y0: y0 = y
            if y > y1: y1 = y
            for n in (k - 1 if x > 0 else -1, k + 1 if x < w - 1 else -1, k - w if y > 0 else -1, k + w if y < h - 1 else -1):
                if n >= 0 and not seen[n] and px[n] >= 128:
                    seen[n] = 1; stack.append(n)
        out.append((area, (x0, y0, x1 + 1, y1 + 1)))
    out.sort(reverse=True)
    return out


def mask_stats(alpha):
    """Numbers about an 'L' alpha mask (any size)."""
    a = alpha.resize((N, round(N * alpha.height / alpha.width)) if alpha.width >= alpha.height else
                     (round(N * alpha.width / alpha.height), N), Image.BILINEAR)
    w, h = a.size
    hist = a.histogram()
    on = sum(hist[128:]); some = sum(hist[17:]); soft = sum(hist[17:240])
    m = a.point(lambda v: 255 if v >= 128 else 0)
    comps = components(m)
    total = sum(c[0] for c in comps) or 1
    big = [c for c in comps if c[0] >= 0.06 * comps[0][0]] if comps else []
    specks = [c for c in comps if 0.0004 * w * h <= c[0] < 0.06 * (comps[0][0] if comps else 1) and c[0] < 0.02 * total]
    box = m.getbbox()
    if box:
        bw, bh = box[2] - box[0], box[3] - box[1]
        fill = max(bw / w, bh / h)
        offx = (box[0] + box[2]) / 2 / w - 0.5
        offy = (box[1] + box[3]) / 2 / h - 0.5
        touches = sum([box[0] <= 0, box[1] <= 0, box[2] >= w, box[3] >= h])
        solidity = on / max(1, bw * bh)
    else:
        fill = offx = offy = 0.0; touches = 0; solidity = 0.0
    return {
        "cover": round(on / (w * h), 3), "fill": round(fill, 3), "off_x": round(offx, 3), "off_y": round(offy, 3),
        "touches": touches, "parts": len(big), "specks": len(specks), "soft": round(soft / max(1, some), 3),
        "solidity": round(solidity, 3), "largest_share": round((comps[0][0] / total) if comps else 0, 3),
    }


def border_light(rgb):
    """Share of the outer 4% frame that is white / very light, and the frame's luminance spread."""
    sm = rgb.copy(); sm.thumbnail((N, N))
    w, h = sm.size; b = max(2, round(min(w, h) * 0.04)); px = sm.load()
    pts = [px[x, y] for y in range(h) for x in (list(range(b)) + list(range(w - b, w)))]
    pts += [px[x, y] for x in range(b, w - b) for y in (list(range(b)) + list(range(h - b, h)))]
    light = sum(1 for (r, g, bl) in pts if min(r, g, bl) >= 232 and max(r, g, bl) - min(r, g, bl) <= 14)
    lum = [0.299 * r + 0.587 * g + 0.114 * bl for (r, g, bl) in pts]
    mu = sum(lum) / len(lum)
    return light / len(pts), (sum((v - mu) ** 2 for v in lum) / len(lum)) ** 0.5


def gutters(rgb):
    """Collage hint for photos WITHOUT transparency: interior rows/columns that are one flat colour across the whole
    photo with content on both sides, or a hard seam running nearly the full length."""
    g = rgb.convert("L"); g.thumbnail((N, N)); w, h = g.size; px = g.load()

    def flat(v):
        mu = sum(v) / len(v); return (sum((x - mu) ** 2 for x in v) / len(v)) ** 0.5 < 3.0

    rows = [[px[x, y] for x in range(w)] for y in range(h)]
    cols = [[px[x, y] for y in range(h)] for x in range(w)]
    hits = set()
    for lines, n, ax in ((rows, h, "h"), (cols, w, "v")):
        for k in range(int(n * 0.18), int(n * 0.82)):
            if flat(lines[k]) and not flat(lines[k - 3]) and not flat(lines[k + 3]):
                hits.add((ax, k // 6))
            d = [abs(a - b) for a, b in zip(lines[k], lines[k + 1])]
            if sum(1 for x in d if x > 28) / len(d) > 0.8:
                hits.add((ax, k // 6))
    return len(hits)


def text_hint(rgb, alpha=None):
    """Very rough overlay-text hint: saturated pure red / yellow stroke pixels (typical seller stickers and price
    text). Printed graphics on the garment trigger it too, so treat it as 'look at this one', not a verdict."""
    sm = rgb.copy(); sm.thumbnail((N, N)); hsv = sm.convert("HSV").load(); w, h = sm.size
    n = 0
    for y in range(h):
        for x in range(w):
            hh, s, v = hsv[x, y]
            if s > 190 and v > 190 and (hh < 10 or hh > 245 or 28 < hh < 42):
                n += 1
    return n / (w * h)


def measure(im):
    im = ImageOps.exif_transpose(im)
    w0, h0 = im.size
    rgb = _rgb_on_white(im)
    out = {"w": w0, "h": h0, "mode": im.mode}
    alpha = im.getchannel("A") if "A" in im.getbands() else None
    if alpha is not None and alpha.getextrema()[0] < 250:
        out["cutout"] = True
        out.update(mask_stats(alpha))
        out["bg_white"] = True                       # transparent: the site decides the backdrop
        out["no_bg_removed"] = out["solidity"] > 0.97 and out["fill"] > 0.97
        out["gutters"] = 0
    else:
        out["cutout"] = False
        light, sd = border_light(rgb)
        out["border_light"] = round(light, 3); out["border_sd"] = round(sd, 1)
        out["bg_white"] = light >= 0.85
        # foreground = differs from the frame colour
        sm = rgb.copy(); sm.thumbnail((N, N))
        d = ImageChops.difference(sm, Image.new("RGB", sm.size, (255, 255, 255) if light >= 0.85 else sm.getpixel((1, 1))))
        out.update(mask_stats(d.convert("L").point(lambda v: 255 if v > 38 else 0).filter(ImageFilter.MinFilter(3)).resize((w0, h0))))
        out["no_bg_removed"] = not out["bg_white"]
        out["gutters"] = gutters(rgb)
    out["text_hint"] = round(text_hint(rgb), 4)
    # flags
    out["small"] = min(w0, h0) < 600
    out["not_square"] = abs(w0 / h0 - 1) > 0.05
    out["multi_part"] = out["parts"] >= 2
    out["loose_bits"] = out["specks"] >= 1
    out["off_centre"] = abs(out["off_x"]) > 0.05 or abs(out["off_y"]) > 0.05
    out["too_small_in_frame"] = out["fill"] < 0.70
    out["too_big_or_cropped"] = out["fill"] >= 0.985 or out["touches"] >= 1
    out["hazy_mask"] = out.get("soft", 0) > 0.12
    out["collage"] = out["gutters"] >= 3
    out["text_overlay_hint"] = out["text_hint"] > 0.01
    return out


FLAGS = ["no_bg_removed", "small", "not_square", "multi_part", "loose_bits", "off_centre", "too_small_in_frame",
         "too_big_or_cropped", "hazy_mask", "collage", "text_overlay_hint"]
