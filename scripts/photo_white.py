# -*- coding: utf-8 -*-
"""Pure white cut-outs for the product photos that still show a background (owner, 23 Nov 2026: "remove the background
on the products with a background"; every product photo like a premium store's: the item cut out on #FFFFFF, like
SSENSE or Mr Porter).

Targets (data/photo_white_targets.json):
  a  a find's MAIN photo is a store photo (products/store/) the polish step skipped, mostly white or see-through items
     whose new cut-out lost parts: the site still shows the old transparent cut-out on its grey photo well
  b  extra store angles (not model shots) with the same problem
  c  finds whose main photo (img/rl/<id>.webp) still shows its background (data/photo_background.json); photo_hide.py
     hides them until the photo file changes
  d  every visible find whose main photo is a transparent cut-out (products/pc, img/rl, img/fr, img/p, img/p2): the
     photo it was cut from is found again (RepLibrary's own image, the seller photo, or the Weidian listing's photos)
     and lined up (MATCH); a quick matte of it (birefnet-general-lite) shows what the item really covers (a hanger
     above the item that the old cut-out took out does not count, and stays out). When the old cut-out misses more
     than 4% of that (owner, 23 Nov 2026: "remove backgrounds without making the item / product cropped"), the item is
     cut out again from the original with the checks of group c against the original photo (the whole item, the lost
     parts included, as the reference), plus: nothing the old cut-out showed may go. Writes img/white/recut/<id>.webp.
Model shots (people, -m0 / -dm0) and QC photos are never touched.

Why the old store cut-outs look grey: their RGB is premultiplied by alpha (the cut-out was composited on black), but WebP
alpha is straight, so every half-transparent pixel shows darker than it is: white parts look grey and see-through. This
script reads them un-premultiplied (their true colours), as the source and as the reference for every check.

Per photo:
  1. source   a, b: the store image the live file was cut from, found again among the find's candidates
              (store_photos_polish.find_source, on the un-premultiplied live file), then the live file itself.
              c: the site file. Live store files are read through the site's edge cache (/api/img), never from Supabase.
  2. cut-out  BiRefNet first (birefnet-general, rembg), then BiRefNet_HR and BiRefNet_HR-matting (2048 px, PyTorch,
              HuggingFace at pinned revisions) for what it cannot do (white on white, glossy, see-through), and
              isnet-general-use only as the fallback. Each matte is tidied like the polish step (specks out, enclosed gaps
              decided, fringe choked, a hanger hook above a garment trimmed), the background colour is taken out of the
              edge, and the item is framed by store_photos_polish.place (1600 x 1600 #FFFFFF, fill by type, guarded
              Real-ESRGAN, light sharpening), WebP q90.
  3. checks   the first candidate that passes EVERY check is kept; otherwise the photo keeps its old file and goes on
              the "could not fix" list with the reason:
                frame       the photo itself crops the item (more than 25% of a border is item: polish rule)
                gate        clean_photos.gate on the matte (empty, hazy, too many loose pieces)
                outline     store_photos_polish.same_item >= 0.96 against the live photo (un-premultiplied, on white)
                interior    store_photos_polish.same_inside >= 0.78 / 0.74
                regression  store_photos_polish_check: aspect change <= 0.08, correlation >= 0.6; and nothing of the
                            item lost, its white and half-transparent parts included: at most 2% (a, b) / 1% (c) of the
                            live item turns much lighter (white) in the new photo
                fidelity    the item's own pixels unchanged: mean difference <= 4 (clean_photos.py bar)
Writes img/white/store/<name>.webp (a, b), img/white/rl/<id>.webp (c), results in data/photo_white/<k>-of-<n>.json and
before / after sheets in out/photo-white/. Nothing is uploaded, the catalogue and the gallery are not touched: the
apply step (apply_store_photos.py, apply_catalog_ai.py --white) switches them.

  python scripts/photo_white.py [--group a,b,c] [--ids 1,2] [--shard 0/1] [--limit 0] [--models m1,m2] [--redo]
"""
import argparse, io, json, os, re, sys, time, urllib.parse
from types import SimpleNamespace
from datetime import datetime, timezone

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from catalog_common import ROOT, load_catalog, load_json, save_json  # noqa: E402
import store_photos_polish as sp  # noqa: E402
import store_photos_shards as shards  # noqa: E402

EDGE = "https://www.puroclassico.com/api/img?u="
TARGETS = os.path.join(ROOT, "data", "photo_white_targets.json")
STATE_DIR = os.path.join(ROOT, "data", "photo_white")
OUT = {"store": os.path.join(ROOT, "img", "white", "store"), "rl": os.path.join(ROOT, "img", "white", "rl"),
       "recut": os.path.join(ROOT, "img", "white", "recut")}
SHEETS = os.path.join(ROOT, "out", "photo-white")
VERSION = 2            # 2: band frame check, anchored framing where the photo's frame cuts the item
SIZE = sp.SIZE
MODEL_SHOT = re.compile(r"-[a-z]?m\d+\.webp$")
MODELS = ["birefnet-general", "birefnet-hr", "birefnet-hr-matting", "isnet-general-use"]
HF = {"birefnet-hr": ("ZhengPeng7/BiRefNet_HR", "a7a562f6fd16021180f2f4348f4de003a2d3d1e1"),               # MIT
      "birefnet-hr-matting": ("ZhengPeng7/BiRefNet_HR-matting", "5d6b6f8adcb5b417c871b1d84ceaae9871355b7f")}
FRAME_MAX = 0.25        # polish rule: more than 25% of a border is item -> the photo crops the item
LOST_MAX = {"a": 0.02, "b": 0.02, "c": 0.01, "d": float(os.environ.get("PHOTO_WHITE_LOST_MAX_D", "0.01"))}
# PHOTO_WHITE_LOST_MAX_D: a second, by-eye reviewed pass on visibly broken finds that every free model fails by a hair
# (a white shirt on a light background: the model-free reference counts a little shadow as item); the record keeps it
OLD_KEPT_MIN = 0.97     # d: the new cut-out keeps at least this share of what the old one showed solidly
LOST_FLAG = 0.04        # d: the old cut-out misses more than this share of the item (the original's matte): re-cut
DETECT = os.environ.get("PHOTO_WHITE_DETECT", "birefnet-general-lite")   # d: the matte that shows what the item covers
FID_MAX = 4.0           # clean_photos.py: the item's own pixels may differ by at most 4 of 255 on average
RESTORED_MAX = 0.08     # a, b: parts the old cut-out lost (not white, not background) the new one may have back
AR_MAX, CORR_MIN = 0.08, 0.6    # store_photos_polish_check.py
NEEDS_NEW_PHOTO = {"worn_by_person", "collage_or_grid", "packaging_or_box", "hand_in_photo"}   # rl_cutout / clean_photos
GARMENT = {"Tops", "Outerwear"}


def now(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


# ---------------------------------------------------------------- images
def unpremul(im):
    """RGBA with straight colours from a file whose RGB was premultiplied by alpha (the old store cut-outs)."""
    a = np.asarray(im.convert("RGBA"), dtype=np.float32)
    al = a[..., 3:4] / 255.0
    rgb = np.where(al > 0, a[..., :3] / np.maximum(al, 1 / 255.0), 0)
    return Image.fromarray(np.concatenate([np.clip(rgb, 0, 255), a[..., 3:4]], axis=2).round().astype(np.uint8), "RGBA")


def flat_bg(rgb, tol=16):
    """(photo with its plain background turned white, background mask, background colour): flood fill from the border
    over pixels within tol of the border colour. Model-free: the independent reference for the checks of group c."""
    from scipy import ndimage
    a = np.asarray(rgb.convert("RGB"), dtype=np.int16)
    bg = sp.border_bg(a.astype(np.float32))
    near = np.abs(a - bg[None, None, :]).max(axis=2) <= tol
    lab, n = ndimage.label(near)
    edge = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
    m = np.isin(lab, list(edge)) if edge else np.zeros(near.shape, bool)
    out = np.where(m[..., None], 255, a).astype(np.uint8)
    return Image.fromarray(out), m, bg


def fetch_edge(url):
    """A Supabase photo through the site's edge cache (direct storage reads fail on cache misses)."""
    data = sp.fetch(EDGE + urllib.parse.quote(url, safe=""), timeout=60, tries=3)
    return sp.open_any(data, cap=4000) if data else None


# ---------------------------------------------------------------- mattes
_hr = {}
MEAN, STD = np.array([0.485, 0.456, 0.406], np.float32), np.array([0.229, 0.224, 0.225], np.float32)


HR_SIZE = int(os.environ.get("PHOTO_WHITE_HR_SIZE", "2048"))


def matte_hr(rgb, model, size=None):
    """BiRefNet_HR / BiRefNet_HR-matting (trained at 2048 x 2048) on the CPU. One of them in memory at a time: a 2048 px
    pass needs about 9 GB (a runner was shut down with both loaded, 23 Nov 2026); PHOTO_WHITE_HR_SIZE runs it smaller."""
    size = size or HR_SIZE
    import gc, torch
    from transformers import AutoModelForImageSegmentation
    if model not in _hr:
        _hr.clear(); gc.collect()
        repo, rev = HF[model]
        _hr[model] = AutoModelForImageSegmentation.from_pretrained(repo, revision=rev, trust_remote_code=True).eval().float()
    x = (np.asarray(rgb.convert("RGB").resize((size, size), Image.BILINEAR), np.float32) / 255.0 - MEAN) / STD
    with torch.inference_mode():
        p = _hr[model](torch.from_numpy(np.ascontiguousarray(x.transpose(2, 0, 1))).unsqueeze(0))[-1].sigmoid()[0, 0].numpy()
    del x; gc.collect()
    return Image.fromarray((p * 255).round().astype(np.uint8)).resize(rgb.size, Image.LANCZOS)


def matte(rgb, model):
    return matte_hr(rgb, model) if model in HF else sp.matte(rgb, model)


def trim_hook(alpha):
    """A hanger hook above a garment (clean_photos._hook_rows on a 300 px copy): rows above it cleared."""
    import clean_photos as cp
    w, h = alpha.size
    sc = 300 / max(w, h)
    sm = alpha.resize((max(1, round(w * sc)), max(1, round(h * sc))), Image.BILINEAR).point(lambda v: 255 if v >= 128 else 0)
    cut = cp._hook_rows(sm)
    if not cut: return alpha, False
    a = np.asarray(alpha).copy(); a[:int(cut / sc)] = 0
    return Image.fromarray(a), True


def touches(alpha):
    """{side: share of that side that is item}, read on a band along the photo's edge (0.6% of its size, at least 2 px;
    the polish step reads the outer 2 px, which a thin white line along the edge can hide)."""
    m = np.asarray(alpha) >= 128
    h, w = m.shape; b = max(2, round(0.006 * max(h, w)))
    return {"top": float(m[:b].mean(axis=1).max()), "bottom": float(m[-b:].mean(axis=1).max()),
            "left": float(m[:, :b].mean(axis=0).max()), "right": float(m[:, -b:].mean(axis=0).max())}


def frame_share(alpha):
    return max(touches(alpha).values())


TOUCH_MIN = 0.004       # more of a side than this is item: the photo's own frame cuts the item there


def layout(w, h, kind, touch):
    """(tw, th, x0, y0, anchored sides) of an item w x h in the 1600 px photo: the polish step's framing (fill by type),
    except that where the photo's own frame cuts the item (a watch bracelet, a cable, trouser legs running out of the
    picture) that side stays on the edge of the new photo, as in the original, instead of ending in a flat cut in mid-air.
    Top and bottom are kept on the edge alone or together; left and right only together (a sleeve tip touching one
    side leaves the item centred)."""
    fw, fh, cy = sp.FILL[kind]
    t = {k: v > TOUCH_MIN for k, v in (touch or {}).items()}
    top, bot, lr = t.get("top"), t.get("bottom"), t.get("left") and t.get("right")
    s = min(fw * SIZE / w, fh * SIZE / h)
    if top and bot: s = SIZE / h
    if lr: s = min(SIZE / w, SIZE / h) if (top and bot) else SIZE / w
    s = min(s, SIZE / w, SIZE / h)
    tw, th = max(1, round(w * s)), max(1, round(h * s))
    x0 = (SIZE - tw) // 2
    if top and not bot: y0 = 0
    elif bot and not top: y0 = SIZE - th
    elif top and bot: y0 = (SIZE - th) // 2
    else: y0 = max(0, min(SIZE - th, round(SIZE * cy - th / 2)))
    anchored = [k for k in ("top", "bottom") if t.get(k)] + (["left", "right"] if lr else [])
    return tw, th, x0, y0, anchored


def place(rgb, alpha, kind, notes, touch):
    """store_photos_polish.place (enlarging with the guarded Real-ESRGAN below 1100 px real size, light sharpening,
    #FFFFFF canvas) with layout() for the position. Returns (photo, (x0, y0, tw, th))."""
    from PIL import ImageFilter
    w, h = rgb.size
    tw, th, x0, y0, anchored = layout(w, h, kind, touch)
    if anchored: notes["anchored"] = anchored
    es = sp.eff_scale(rgb, alpha)
    real = max(w, h) * es
    notes["real_px"] = round(real); notes["shown_px"] = max(tw, th)
    if real < sp.ESRGAN_BELOW and max(tw, th) > real * 1.08:
        inp = rgb if es >= 0.97 else rgb.resize((max(8, round(w * es)), max(8, round(h * es))), Image.LANCZOS)
        big, notes["up"] = sp.esrgan(inp, tw, th)
    else:
        big = rgb.resize((tw, th), Image.LANCZOS)
        notes["up"] = "lanczos" if max(tw, th) > max(w, h) else "downscale"
    big = big.filter(ImageFilter.UnsharpMask(radius=0.9, percent=40, threshold=2))
    canvas = Image.new("RGB", (SIZE, SIZE), (255, 255, 255))
    canvas.paste(big, (x0, y0), alpha.resize((tw, th), Image.LANCZOS))
    return canvas, (x0, y0, tw, th)


def gate(alpha, several):
    """clean_photos.gate on the matte cropped to the item (+10%); the frame is checked separately. Its haze test reads
    a 192 px copy, where a thin chain or strap is all half-transparent; here haze is counted at full size and only away
    from the solid item (a ghosted white body is, a chain's soft edge is not)."""
    import clean_photos as cp
    from scipy import ndimage
    b = sp.alpha_box(alpha, 24)
    if not b: return ["empty cut-out"]
    w, h = alpha.size; pw, ph = round(0.1 * (b[2] - b[0])), round(0.1 * (b[3] - b[1]))
    crop = alpha.crop((max(0, b[0] - pw), max(0, b[1] - ph), min(w, b[2] + pw), min(h, b[3] + ph)))
    bad, _ = cp.gate(crop, SimpleNamespace(max_parts=4 if several else 3), several)
    bad = [x for x in bad if not x.startswith("item cut off") and not x.startswith("no background removed")
           and not x.startswith("hazy mask")]
    a = np.asarray(crop)
    some, solid = a >= 17, a >= 240
    haze = float((some & ~solid & ~ndimage.binary_dilation(solid, iterations=2)).sum() / max(1, some.sum()))
    if haze > 0.10: bad.append(f"hazy mask ({100 * haze:.0f}% half-transparent away from the item)")
    if (np.asarray(alpha) >= 128).mean() > 0.95: bad.append("no background removed")
    return bad


# ---------------------------------------------------------------- one cut-out
def compose(src_rgb, al, bg, kind, garment):
    """(1600 photo, notes, placement) from a source image and its raw matte. placement: crop box in the source and
    (x0, y0, tw, th) in the photo."""
    notes = {}
    al, cn = sp.clean_alpha(al, src_rgb, bg)
    if cn: notes["clean"] = cn
    if garment:
        al, cut = trim_hook(al)
        if cut: notes["hook"] = "trimmed"
    b = sp.alpha_box(al, 8)
    if not b: return None, {"error": "empty cut-out", **notes}, None
    touch = touches(al)
    rgb = sp.decontaminate(src_rgb, al, bg)
    pad = 2
    b = (max(0, b[0] - pad), max(0, b[1] - pad), min(rgb.width, b[2] + pad), min(rgb.height, b[3] + pad))
    rgb, al = rgb.crop(b), al.crop(b)
    flat = Image.composite(rgb, Image.new("RGB", rgb.size, (255, 255, 255)), al)
    out, xy = place(flat, al, kind, notes, touch)
    return out, notes, {"box": b, "xy": xy, "flat": flat, "alpha": al}


def back_to_source(out, pl, size):
    """The new photo mapped back into the source frame (white outside the item box)."""
    x0, y0, tw, th = pl["xy"]; b = pl["box"]
    canvas = Image.new("RGB", size, (255, 255, 255))
    canvas.paste(out.crop((x0, y0, x0 + tw, y0 + th)).resize((b[2] - b[0], b[3] - b[1]), Image.LANCZOS), (b[0], b[1]))
    return canvas


def fidelity(out, pl):
    """Mean difference (0..255) between the item's solid pixels and the same pixels in the new photo, compared at the
    smaller of the two sizes (an enlarged item is shrunk back, a reduced one is compared reduced)."""
    from scipy import ndimage
    x0, y0, tw, th = pl["xy"]; flat, al = pl["flat"], pl["alpha"]
    region = out.crop((x0, y0, x0 + tw, y0 + th))
    if tw * th < flat.width * flat.height:
        a, b, m = region, flat.resize((tw, th), Image.LANCZOS), al.resize((tw, th), Image.LANCZOS)
    else:
        a, b, m = region.resize(flat.size, Image.LANCZOS), flat, al
    solid = ndimage.binary_erosion(np.asarray(m) >= 250, iterations=2)
    if solid.sum() < 200: return 0.0
    d = np.abs(np.asarray(a, np.float32) - np.asarray(b, np.float32)).mean(axis=2)
    return float(d[solid].mean())


def item_support(ref_rgba=None, ref_rgb=None, bgmask=None, bg=None):
    """The reference item (bool mask): the live cut-out's support, its half-transparent parts included (a, b), or the
    clearly visible item of a site photo, independent of any model (c)."""
    from scipy import ndimage
    if ref_rgba is not None:
        # solid parts, and half-transparent parts that are white (a white body the old cut-out ghosted); darker
        # half-transparent haze (a floor shadow) may go
        a = np.asarray(ref_rgba, dtype=np.int16)
        m = (a[..., 3] >= 128) | ((a[..., 3] >= 26) & (a[..., :3].min(axis=2) >= 215))
    else:
        a = np.asarray(ref_rgb, dtype=np.int16)
        m = (np.abs(a - bg[None, None, :]).max(axis=2) > 40) & ~bgmask
    lab, n = ndimage.label(m)
    if n > 1:
        areas = ndimage.sum(m, lab, range(1, n + 1))
        m = np.isin(lab, [k + 1 for k, ar in enumerate(areas) if ar >= 0.01 * areas.max()])
    return ndimage.binary_fill_holes(m)


def lost_share(ref, new, supp):
    """Share of the reference item that turned much lighter in the new photo (both in the same frame, slightly blurred so
    a one-pixel edge shift does not count): a part the cut-out dropped shows white where the item was."""
    from scipy import ndimage
    from PIL import ImageFilter
    r = np.asarray(ref.convert("L").filter(ImageFilter.GaussianBlur(1.5)), np.float32)
    n = np.asarray(new.convert("L").filter(ImageFilter.GaussianBlur(1.5)), np.float32)
    core = ndimage.binary_erosion(supp, iterations=max(2, round(0.004 * max(supp.shape))))
    if core.sum() < 500: return 0.0, None
    lost = core & (n - r > 12)
    return float(lost.sum() / core.sum()), lost


def _ncc(x, y):
    x = x - x.mean(); y = y - y.mean()
    return float(np.dot(x, y) / (np.linalg.norm(x) * np.linalg.norm(y) + 1e-6))


def register(ref, core, supp, src, sb):
    """Where the live photo sits in a store image: (a, bx, by, ncc, colour) with source = a * live + (bx, by) (scale and
    shift, no rotation), found by the grey correlation of the live cut-out's solid pixels (core) with the store image,
    coarse to fine. colour: mean RGB difference on those pixels. sb: a rough item box in the store image."""
    from scipy import ndimage
    W, H = ref.size
    rb = bbox(supp)
    if not rb or core.sum() < 300: return None
    am = np.sqrt(((sb[2] - sb[0]) / (rb[2] - rb[0])) * ((sb[3] - sb[1]) / (rb[3] - rb[1])))
    refl, srcl = ref.convert("L"), src.convert("L")
    cache = {}

    def level(n):
        if n not in cache:
            k = n / max(W, H)
            r = np.asarray(refl.resize((max(8, round(W * k)), max(8, round(H * k))), Image.BILINEAR), np.float32)
            c = np.asarray(Image.fromarray(core.astype(np.uint8) * 255).resize((r.shape[1], r.shape[0]), Image.BILINEAR)) >= 192
            c = ndimage.binary_erosion(c, iterations=1) if n >= 200 else c
            q = min(1.0, k / am)
            s = srcl.resize((max(8, round(src.width * q)), max(8, round(src.height * q))), Image.LANCZOS) if q < 1 else srcl
            cache[n] = (r, c, s, q)
        return cache[n]

    def score(n, a, bx, by):
        r, c, s, q = level(n)
        if c.sum() < 50: return -1.0
        box = (bx * q, by * q, (bx + a * W) * q, (by + a * H) * q)
        t = np.asarray(s.transform((r.shape[1], r.shape[0]), Image.EXTENT, box, Image.BILINEAR, fillcolor=255), np.float32)
        return _ncc(r[c], t[c])
    cands = []
    for a in am * np.exp(np.linspace(-0.25, 0.25, 13)):
        x0, x1 = sb[0] - a * rb[0] - 0.15 * (sb[2] - sb[0]), sb[2] - a * rb[2] + 0.15 * (sb[2] - sb[0])
        y0, y1 = sb[1] - a * rb[1] - 0.15 * (sb[3] - sb[1]), sb[3] - a * rb[3] + 0.15 * (sb[3] - sb[1])
        for bx in np.linspace(min(x0, x1), max(x0, x1), 15):
            for by in np.linspace(min(y0, y1), max(y0, y1), 15):
                cands.append((score(96, a, bx, by), a, bx, by))
    cands.sort(key=lambda t: -t[0])
    best = cands[:4]
    for n, da, dt, steps in ((256, 0.05, 0.025, 5), (640, 0.012, 0.006, 5)):
        nxt = []
        for _, a, bx, by in best:
            for a2 in a * np.exp(np.linspace(-da, da, steps)):
                for bx2 in bx + np.linspace(-dt, dt, steps) * a2 * (rb[2] - rb[0]):
                    for by2 in by + np.linspace(-dt, dt, steps) * a2 * (rb[3] - rb[1]):
                        nxt.append((score(n, a2, bx2, by2), a2, bx2, by2))
        nxt.sort(key=lambda t: -t[0]); best = nxt[:2]
    sc, a, bx, by = best[0]
    # colour on the solid pixels, at 640 px
    r, c, s, q = level(640)
    k = r.shape[1] / W
    rc = np.asarray(ref.convert("RGB").resize((r.shape[1], r.shape[0]), Image.BILINEAR), np.float32)
    box = (bx, by, bx + a * W, by + a * H)
    tc = np.asarray(src.convert("RGB").transform((r.shape[1], r.shape[0]), Image.EXTENT, box, Image.BILINEAR, fillcolor=(255, 255, 255)), np.float32)
    col = float(np.abs(rc[c] - tc[c]).mean()) if c.sum() else 99.0
    return float(a), float(bx), float(by), round(sc, 4), round(col, 2)


def to_ref(img, reg, size):
    """An image of the store frame shown in the live photo's frame."""
    a, bx, by = reg[:3]
    W, H = size
    return img.transform((W, H), Image.EXTENT, (bx, by, bx + a * W, by + a * H), Image.BILINEAR,
                         fillcolor=(255, 255, 255) if img.mode == "RGB" else 0)


def bbox(m):
    ys, xs = np.where(m)
    if not len(ys): return None
    return (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)


def regression(ref, out):
    """store_photos_polish_check metrics between the reference and the new photo: aspect change and grey correlation of
    the visible items (pixels darker than 250)."""
    import store_photos_polish_check as pc
    ea, eb = pc.visible(ref), pc.visible(out)
    if not ea or not eb: return None, None
    ar = float(np.log(((eb[2] - eb[0]) / max(1, eb[3] - eb[1])) / ((ea[2] - ea[0]) / max(1, ea[3] - ea[1]))))
    x = np.asarray(ref.crop(ea).convert("L").resize((96, 96)), dtype=np.float32).ravel()
    y = np.asarray(out.crop(eb).convert("L").resize((96, 96)), dtype=np.float32).ravel()
    x, y = x - x.mean(), y - y.mean()
    return ar, float(np.dot(x, y) / (np.linalg.norm(x) * np.linalg.norm(y) + 1e-6))


def _grey_box(im, thr=243):
    g = np.asarray(sp.on_white(im).convert("L"), dtype=np.float32)
    return g, bbox(g < thr)


def same_item_shared(a, b, N=96):
    """store_photos_polish.same_item on two photos that are already lined up in one frame, with one crop box for both
    (the union of the two items' boxes): a removed shadow or a lost end shows as a difference where it is, instead of
    shifting the whole crop."""
    (ga, ba), (gb, bb) = _grey_box(a), _grey_box(b)
    if not ba or not bb: return -1.0
    box = (min(ba[0], bb[0]), min(ba[1], bb[1]), max(ba[2], bb[2]), max(ba[3], bb[3]))
    x, y = [np.asarray(Image.fromarray(g.astype(np.uint8)).crop(box).resize((N, N), Image.BILINEAR), np.float32).ravel() for g in (ga, gb)]
    return _ncc(x, y)


def same_inside_shared(a, b, N=160):
    """store_photos_polish.same_inside (grey and detail correlation inside the outline, eroded 7 px at N px) with the
    shared crop box of same_item_shared."""
    from scipy import ndimage
    (ga, ba), (gb, bb) = _grey_box(a), _grey_box(b)
    if not ba or not bb: return None
    box = (min(ba[0], bb[0]), min(ba[1], bb[1]), max(ba[2], bb[2]), max(ba[3], bb[3]))
    x, y = [np.asarray(Image.fromarray(g.astype(np.uint8)).crop(box).resize((N, N), Image.BILINEAR), np.float32) for g in (ga, gb)]
    m = ndimage.binary_erosion((x < 243) & (y < 243), iterations=7)
    if m.sum() < 300: return None
    return _ncc(x[m], y[m]), _ncc((x - ndimage.gaussian_filter(x, 3))[m], (y - ndimage.gaussian_filter(y, 3))[m])


def judge(g, ref, supp, out, pl, src_size, reg, clip, live_alpha=None, bgmask=None, bgcol=None, old_core=None):
    """Every check against the reference (the live photo on white), both photos lined up in the reference's frame.
    reg: where the live photo sits in a store source (None when the source is the reference itself). clip: compare the
    outline only where the live cut-out shows the item, so white parts the old cut-out lost and the new one has back do
    not count against it ('added' counts anything that is not white). A soft floor shadow or reflection the old cut-out
    kept (bottom 15% of the item, light grey, half-transparent in the old cut-out) may go: it is taken out of the reference
    where the new photo dropped it, and counted as 'shadow'. Returns (ok, reason, numbers)."""
    from scipy import ndimage
    from PIL import ImageFilter
    ck = {}
    view = back_to_source(out, pl, src_size)
    alpha = full_alpha(pl, src_size)
    if reg is not None:
        view, alpha = to_ref(view, reg, ref.size), to_ref(alpha, reg, ref.size)
    # the old cut-out's floor shadow / reflection, where the new photo dropped it
    rb = bbox(supp)
    ra = np.asarray(ref.convert("RGB"), dtype=np.int16)
    rl = np.asarray(ref.convert("L").filter(ImageFilter.GaussianBlur(1.5)), np.float32)
    vl = np.asarray(view.convert("L").filter(ImageFilter.GaussianBlur(1.5)), np.float32)
    shadow = np.zeros(supp.shape, bool)
    if rb:
        band = np.zeros(supp.shape, bool); band[int(rb[3] - 0.15 * (rb[3] - rb[1])):rb[3]] = True
        soft = np.ones(supp.shape, bool) if live_alpha is None else (live_alpha < 230)
        shadow = band & soft & ((ra.max(axis=2) - ra.min(axis=2)) <= 20) & (rl >= 150) & (vl - rl > 12)
        shadow = ndimage.binary_dilation(shadow, iterations=2) & band
    ck["shadow"] = round(float(shadow.sum() / max(1, supp.sum())), 4)
    refn = Image.fromarray(np.where(shadow[..., None], 255, ra).astype(np.uint8)) if shadow.any() else ref
    r = max(3, round(0.006 * max(ref.size)))
    near = ndimage.binary_dilation(supp, iterations=r)
    shown = Image.fromarray(np.where(near[..., None], np.asarray(view), 255).astype(np.uint8)) if clip else view
    same = same_item_shared(refn, shown); ck["same"] = round(same, 3)
    ins = same_inside_shared(refn, view)
    if ins: ck["inside"] = [round(ins[0], 3), round(ins[1], 3)]
    ar, corr = regression(refn, shown)
    if ar is not None: ck["ar"], ck["corr"] = round(ar, 3), round(corr, 3)
    lost, _ = lost_share(refn, view, supp & ~shadow); ck["lost"] = round(lost, 4)
    item = np.asarray(alpha) >= 128
    if bgmask is not None:     # c: the plain background the flood fill found (model-free) must not be kept where it
        # shows. A white background kept on white is invisible, and on a white item the fill runs into the item itself
        # (a white sleeve's shading), so only a background that is not white counts.
        mask, colour = bgmask
        src = np.asarray(back_to_source(out, pl, src_size).convert("RGB"), dtype=np.int16)
        added = 0.0 if min(colour) >= 240 else \
            float((item & ndimage.binary_erosion(mask, iterations=r) & (src.min(axis=2) < 243)).sum() / max(1, item.sum()))
    else:                      # a, b: what the new cut-out has far from the live cut-out, when it is not white: in the
        # store photo's background colour it is background kept; in another colour it is a part the old cut-out lost
        # and the new one has back ("restored", allowed up to RESTORED_MAX; anything more is not the same cut-out)
        far = ~ndimage.binary_dilation(supp, iterations=2 * r)
        va = np.asarray(view.convert("RGB"), dtype=np.int16)
        extra = item & far & (va.min(axis=2) < 200)
        bgc = np.asarray(bgcol if bgcol is not None else [255, 255, 255], dtype=np.int16)
        near_bg = np.abs(va - bgc[None, None, :]).max(axis=2) <= 15
        added = float((extra & near_bg).sum() / max(1, item.sum()))
        ck["restored"] = round(float((extra & ~near_bg).sum() / max(1, item.sum())), 4)
    ck["added"] = round(added, 4)
    if old_core is not None and old_core.any():     # d: everything the old cut-out showed solidly is still there
        ck["old_kept"] = round(float(item[old_core].mean()), 4)
    ck["fid"] = round(fidelity(out, pl), 2)
    if same < sp.SAME_MIN: return False, f"another photo or a changed outline (outline {same:.2f} < {sp.SAME_MIN})", ck
    if ins and (ins[0] < sp.INNER_MIN[0] or ins[1] < sp.INNER_MIN[1]):
        return False, f"changed inside the outline (interior {ins[0]:.2f} / {ins[1]:.2f})", ck
    if ar is None: return False, "no visible item", ck
    if abs(ar) > AR_MAX: return False, f"shape changed (aspect {ar:+.2f}): a part was lost or added", ck
    if corr < CORR_MIN: return False, f"looks different from the live photo (correlation {corr:.2f})", ck
    if lost > LOST_MAX[g]: return False, f"part of the item lost ({100 * lost:.1f}% of it turned white)", ck
    if added > 0.01: return False, f"something kept around the item ({100 * added:.1f}% of the new cut-out)", ck
    if ck.get("restored", 0) > RESTORED_MAX:
        return False, f"much more than the live photo shows ({100 * ck['restored']:.1f}% of the new cut-out)", ck
    if ck.get("old_kept", 1) < OLD_KEPT_MIN:
        return False, f"drops part of what the old cut-out showed ({100 * (1 - ck['old_kept']):.1f}%)", ck
    if ck["fid"] > FID_MAX: return False, f"item pixels changed (fidelity {ck['fid']:.1f} > {FID_MAX})", ck
    return True, "", ck


def full_alpha(pl, size):
    """The cleaned matte back in the full source frame."""
    a = Image.new("L", size, 0); b = pl["box"]; a.paste(pl["alpha"], (b[0], b[1])); return a


# ---------------------------------------------------------------- one photo
def try_source(g, src_rgb, bg, ref, supp, reg, clip, kind, garment, several, models, mcache, tag, log, live_alpha=None, bgmask=None,
               keep=None, old_core=None, drop=None):
    """Cut-outs of one source, best first, until one passes every check. Returns (photo, record) or (None, record).
    keep (d): only the pieces of the matte that touch this region stay (the item, not the other products of a collage).
    old_core (d): what the old cut-out showed solidly; the new one must keep it.
    drop (d): never part of the new cut-out (a hanger above the item the old cut-out had taken out)."""
    rec = {"tried": []}
    # matting region: the item with a margin (faster, finer), from a quick isnet pass and the border difference
    crop = (0, 0, src_rgb.width, src_rgb.height)
    try:
        key = (tag, "isnet-full")
        if key not in mcache: mcache[key] = matte(src_rgb, "isnet-general-use")
        ib = bbox(np.asarray(mcache[key]) >= 13); fb = sp.fg_box(src_rgb)
        if ib:
            x0, y0, x1, y1 = min(fb[0], ib[0]), min(fb[1], ib[1]), max(fb[2], ib[2]), max(fb[3], ib[3])
            pad = round(0.06 * max(x1 - x0, y1 - y0))
            crop = (max(0, x0 - pad), max(0, y0 - pad), min(src_rgb.width, x1 + pad), min(src_rgb.height, y1 + pad))
    except Exception as e:
        rec["crop_err"] = str(e)[:80]
    sub = src_rgb.crop(crop)
    fails, cands = [], {}

    def attempt(m):
        """Matte, frame and gate checks, framing, every check. Returns (photo or None, record entry)."""
        t = time.time()
        try:
            raw = matte(sub, m)
        except Exception as e:
            return None, {"model": m, "why": f"{m}: {str(e)[:60]}"}, None
        r = {"model": m, "s": round(time.time() - t, 1)}
        full = Image.new("L", src_rgb.size, 0); full.paste(raw, crop[:2])
        if keep is not None:
            full = keep_pieces(full, keep)
        if drop is not None and drop.any():
            full = Image.fromarray(np.where(drop, 0, np.asarray(full)).astype(np.uint8))
        fr = frame_share(full)
        if fr > FRAME_MAX:
            r["why"] = f"item cut off by the photo's frame ({100 * fr:.0f}% of a border)"
        else:
            bad = gate(full, several)
            if bad: r["why"] = "gate: " + "; ".join(bad)
        if "why" in r:
            log(f"      {tag} {m}: {r['why']}"); return None, r, None
        out, notes, pl = compose(src_rgb, full, bg, kind, garment)
        if out is None:
            r["why"] = notes.get("error"); return None, r, None
        ok, why, ck = judge(g, ref, supp, out, pl, src_rgb.size, reg, clip, live_alpha, bgmask, bg, old_core)
        if not ok and why.startswith("item pixels changed") and str(notes.get("up", "")).startswith("Real-ESRGAN"):
            # the enlarged copy is what changed the pixels: the same cut-out enlarged plainly (Lanczos) instead
            below, sp.ESRGAN_BELOW = sp.ESRGAN_BELOW, 0
            try:
                out2, notes2, pl2 = compose(src_rgb, full, bg, kind, garment)
            finally:
                sp.ESRGAN_BELOW = below
            if out2 is not None:
                ok2, why2, ck2 = judge(g, ref, supp, out2, pl2, src_rgb.size, reg, clip, live_alpha, bgmask, bg, old_core)
                r["esrgan_fid"] = ck.get("fid")
                out, notes, pl, ok, why, ck = out2, notes2, pl2, ok2, why2, ck2
        r.update(ck); r.update({k: v for k, v in notes.items() if k in ("clean", "hook", "up", "real_px", "shown_px", "anchored")})
        if not ok: r["why"] = why
        log(f"      {tag} {m}: {'OK' if ok else why}  {json.dumps(ck)}")
        return (out if ok else None), r, notes

    def done(m, out, r, notes):
        rec["tried"].append(r)
        if out is not None:
            rec.update(model=m, checks={k: v for k, v in r.items() if k not in ("model", "s", "clean", "hook", "up", "real_px", "shown_px", "anchored", "fallback", "esrgan_fid")},
                       notes={k: v for k, v in (notes or {}).items() if k != "edge"})
            return True
        fails.append(r.get("why")); return False
    # BiRefNet first (birefnet-general), then the HR / matting BiRefNets for what it cannot do (white on white, glossy,
    # see-through), isnet-general-use only as the fallback. isnet is tried right after birefnet-general as a probe (it
    # is fast): when both fail the same way the photo or its reference is the problem and the slow HR mattes are skipped,
    # but its result is only used when no BiRefNet passes.
    fast = [m for m in models if m == "birefnet-general"]
    probe = [m for m in models if m == "isnet-general-use"]
    slow = [m for m in models if m in HF]
    for m in fast:
        out, r, notes = attempt(m)
        if done(m, out, r, notes): return out, rec
    fallback = None
    for m in probe:
        out, r, notes = attempt(m)
        r["fallback"] = True
        if out is not None: fallback = (m, out, r, notes)
        else: rec["tried"].append(r); fails.append(r.get("why"))
    if slow and not hr_worth(rec["tried"] + ([fallback[2]] if fallback else [])):
        rec["hr"] = "skipped: the fast cut-outs failed for a reason a finer matte does not change"; slow = []
    for m in slow:
        out, r, notes = attempt(m)
        if done(m, out, r, notes): return out, rec
    if fallback:
        m, out, r, notes = fallback
        done(m, out, r, notes); return out, rec
    rec["why"] = fails[-1] if fails else "no cut-out"
    return None, rec


def hr_worth(tried):
    """The slow HR mattes only help when a fast matte failed on the matte itself (lost or hazy parts, a changed outline).
    Not when the photo crops the item, or when two different mattes fail the same way with the same numbers (the
    photo or its reference is the problem, not the matte)."""
    if not tried: return True
    if all(str(t.get("why", "")).startswith("item cut off") for t in tried if t.get("why")): return False
    first = str(tried[0].get("why", ""))
    if first.startswith("item pixels changed") or first.startswith("item cut off"): return False   # not the matte
    if len(tried) >= 2:
        a, b = tried[0], tried[1]
        if a.get("why") and b.get("why") and a["why"].split("(")[0] == b["why"].split("(")[0] and \
                abs(a.get("same", 0) - b.get("same", 1)) < 0.01 and abs(a.get("ar", 0) - b.get("ar", 1)) < 0.01:
            return False
    return True


def store_box(rgb):
    """Rough item box in a store photo: what differs from the border colour, also faintly (a white item on white)."""
    from PIL import ImageFilter
    a = np.asarray(rgb.filter(ImageFilter.GaussianBlur(1.5)), dtype=np.int16)
    d = np.abs(a - sp.border_bg(a.astype(np.float32))[None, None, :]).max(axis=2) > 8
    rows, cols = np.where(d.mean(1) > 0.004)[0], np.where(d.mean(0) > 0.004)[0]
    if not len(rows) or not len(cols): return (0, 0, rgb.width, rgb.height)
    return (int(cols[0]), int(rows[0]), int(cols[-1]) + 1, int(rows[-1]) + 1)


def loose(a, b):
    """Signature correlation with a loose shape test (the live cut-out may miss white ends of the item)."""
    if a is None or b is None: return -1.0
    if abs(np.log(a[1] / b[1])) > 0.3: return -1.0
    return float(np.dot(a[0], b[0]))


def find_store(lu, ref, core, supp, pool, cache, used, log):
    """The store image the live photo was cut from. Candidates whose item looks alike (24 px signatures, with the
    polish step's box and with a faint-difference box for white items) are lined up with the live photo's solid pixels
    (register); the best one wins when the grey correlation is >= 0.95 and the colour difference <= 14 (another
    colourway or angle fails), then its largest copy on the shop's CDN. Returns ((url, image, reg, first url) or None,
    best score seen)."""
    from concurrent.futures import ThreadPoolExecutor
    target = sp.item_sig(lu, True)
    best, seen = None, 0
    for start in range(0, len(pool), 8):
        batch = [u for u, _, _ in pool[start:start + 8] if u not in cache]
        with ThreadPoolExecutor(4) as ex:
            for u, data in zip(batch, ex.map(sp.fetch, batch)):
                im = sp.open_any(data) if data else None
                if im is not None: im = sp.on_white(im) if im.mode in ("RGBA", "LA", "P") else im.convert("RGB")
                cache[u] = im
        for u, pg, rk in pool[start:start + 8]:
            im = cache.get(u)
            if im is None or min(im.size) < 200 or u in used: continue
            key = "w" + u
            if key not in cache:
                sb = store_box(im); c = im.crop(sb)
                cache[key] = (sb, sp.item_sig(im, False), (sp.sig(c), c.width / max(1, c.height)))
            sb, s1, s2 = cache[key]
            if max(loose(target, s1), loose(target, s2)) < 0.75: continue
            rk2 = ("r", u)
            if rk2 not in cache:
                try:
                    cache[rk2] = register(ref, core, supp, im, sb)
                except Exception as e:
                    cache[rk2] = None; log(f"      register {u[:60]}: {str(e)[:60]}")
            reg = cache[rk2]; seen += 1
            if reg and (best is None or reg[3] > best[2][3]): best = (u, im, reg)
        if best and best[2][3] >= 0.985 and start >= 8: break
    score = None if not best else {"ncc": best[2][3], "colour": best[2][4], "url": best[0], "looked": seen}
    if not best or best[2][3] < 0.95 or best[2][4] > 14: return None, score
    u, im, reg = best
    first = u
    for v in sp.bigger(u)[:-1]:
        if v in cache and cache[v] is None: continue
        data = sp.fetch(v); big = sp.open_any(data) if data else None; cache[v] = big
        if big is None: continue
        big = sp.on_white(big) if big.mode in ("RGBA", "LA", "P") else big.convert("RGB")
        if max(big.size) <= max(im.size) * 1.05 or abs(big.width / big.height - im.width / im.height) > 0.01: continue
        if sp.match_score(sp.whole_sig(big), sp.whole_sig(im)) > 0.93:
            f = big.width / im.width
            u, im, reg = v, big, (reg[0] * f, reg[1] * f, reg[2] * f, reg[3], reg[4]); break
    return (u, im, reg, first), score


def solid_core(lu):
    """The live cut-out's solid pixels (alpha >= 0.9, eroded): reliable item colours for lining up."""
    from scipy import ndimage
    al = np.asarray(lu.getchannel("A"))
    c = ndimage.binary_erosion(al >= 230, iterations=3)
    if c.sum() < 3000: c = ndimage.binary_erosion(al >= 150, iterations=2)
    return c


def do_store(p, g, name, pool, cache, used, models, log):
    live = fetch_edge(sp.STORE + name)
    if live is None: return None, {"why": "the live photo could not be fetched (edge cache)"}
    lu = unpremul(live)          # every products/store/ file: rembg's cut-out composited the colours on black
    ref = sp.on_white(lu)
    supp = item_support(ref_rgba=lu)
    core = solid_core(lu)
    la = np.asarray(lu.getchannel("A"))
    kind = sp.kind_of(p); garment = p.get("cat") in GARMENT
    several = bool(re.search(r"(?i)\b(sets?|tracksuits?|pairs?|kit|earrings?|socks)\b", p.get("title") or "")) or kind in ("shoe", "small")
    rec = {}
    found = None
    try:
        found, score = find_store(lu, ref, core, supp, pool, cache, used, log)
        rec["match"] = score
    except Exception as e:
        rec["match_err"] = repr(e)[:120]
    mcache = {}
    if found:
        u, srgb, reg, first = found
        used.update({u, first})
        rec.update(src_url=u, src_size=list(srgb.size))
        bg = sp.border_bg(np.asarray(srgb, dtype=np.float32))
        out, r = try_source(g, srgb, bg, ref, supp, reg, True, kind, garment, several, models, mcache, "store", log, la)
        rec["store"] = r
        if out is not None:
            rec.update(source="store", model=r["model"], checks=r["checks"], notes=r.get("notes"))
            return out, rec
    # the live file itself: its true colours on white
    out, r = try_source(g, ref, np.array([255.0, 255, 255]), ref, supp, None, True, kind, garment, several, models, mcache, "live", log, la)
    rec["live"] = r
    if out is not None:
        rec.update(source="live", model=r["model"], checks=r["checks"], notes=r.get("notes"))
        return out, rec
    why = r.get("why")
    if found and (rec.get("store") or {}).get("why"): why = f"store copy: {rec['store']['why']}; live file: {why}"
    elif not found: why = f"no store copy lined up; live file: {why}"
    rec["why"] = why
    return None, rec


def do_rl(p, path, labels, models, log):
    f = os.path.join(ROOT, path)
    if not os.path.isfile(f): return None, {"why": "the site file is missing"}
    lab = labels.get(p["id"]) or {}
    no_go = sorted(set(lab.get("photo_issues") or []) & NEEDS_NEW_PHOTO)
    if no_go: return None, {"why": "needs a new photo (" + ", ".join(no_go) + "): a cut-out cannot take that out"}
    im = Image.open(f); im.load()
    rgb = sp.on_white(im) if "A" in im.getbands() else im.convert("RGB")
    ref, bgmask, bg = flat_bg(rgb)
    supp = item_support(ref_rgb=rgb, bgmask=bgmask, bg=bg)
    kind = sp.kind_of(p); garment = p.get("cat") in GARMENT
    several = bool(lab.get("is_set")) or bool(set(lab.get("photo_issues") or []) & {"multiple_views", "multiple_items"}) \
        or bool(re.search(r"(?i)\b(sets?|tracksuits?|pairs?|kit|earrings?|socks)\b", p.get("title") or "")) or kind in ("shoe", "small")
    out, r = try_source("c", rgb, bg, ref, supp, None, False, kind, garment, several, models, {}, "site", log, None, (bgmask, bg))
    rec = {"source": "site", "bg": [int(x) for x in bg], **r}
    if out is not None: rec.update(model=r["model"], checks=r["checks"])
    return out, rec


# ---------------------------------------------------------------- group d: cut-outs that lost part of the item
WD_API = "https://thor.weidian.com/detail/getItemSkuInfo/1.0?param="
WD_HEAD = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
           "Referer": "https://weidian.com/"}
_wd_next = [0.0]
_srcs = {}


def keep_pieces(alpha, keep):
    """Only the pieces of a matte that touch the keep region (the item, not the other products of a collage)."""
    from scipy import ndimage
    a = np.asarray(alpha)
    lab, n = ndimage.label(a >= 64)
    if n <= 1: return alpha
    hit = set(np.unique(lab[keep & (lab > 0)])) - {0}
    if not hit: return alpha
    return Image.fromarray(np.where(np.isin(lab, list(hit)) | (a < 64) & ndimage.binary_dilation(np.isin(lab, list(hit)), iterations=3), a, 0).astype(np.uint8))


def wd_get(url, api=False):
    """A Weidian request (the item API is paced like check_links.py: one at a time, 0.4 s apart)."""
    import urllib.request
    if api:
        wait = _wd_next[0] - time.time()
        if wait > 0: time.sleep(wait)
        _wd_next[0] = time.time() + 0.4
    for k in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=WD_HEAD), timeout=30) as r: return r.read()
        except Exception:
            time.sleep(2 + 4 * k)
    return None


def weidian_photos(item_id):
    """The listing's photos (main picture, option pictures, SKU pictures), main first, deduped, at most 12."""
    data = wd_get(WD_API + urllib.parse.quote(json.dumps({"itemId": str(item_id)})), api=True)
    try:
        res = (json.loads(data) or {}).get("result") or {}
    except Exception:
        return []
    out = []
    def add(u):
        if isinstance(u, str) and u.startswith("http") and "geilicdn" in u:
            u = u.split("?")[0]
            if u not in out: out.append(u)
    add(res.get("itemMainPic"))
    for at in res.get("attrList") or []:
        for v in (at or {}).get("attrValues") or []:
            if isinstance(v, dict): add(v.get("img"))
    for sk in res.get("skuInfos") or []:
        si = (sk or {}).get("skuInfo") if isinstance((sk or {}).get("skuInfo"), dict) else sk
        if isinstance(si, dict): add(si.get("img"))
    return out[:12]


def original_urls(p, old):
    """Where the photo the old cut-out was made from can be: RepLibrary's own image (scripts/rl_import.json src), the
    seller photo (data/seller_photos.json src), else the Weidian listing's photos."""
    if not _srcs:
        try:
            _srcs["rl"] = {str(x.get("id")): x.get("src") for x in load_json(os.path.join(ROOT, "scripts", "rl_import.json"), []) if x.get("src")}
        except Exception:
            _srcs["rl"] = {}
        _srcs["p2"] = {k: v.get("src") for k, v in (load_json(os.path.join(ROOT, "data", "seller_photos.json"), {}).get("items") or {}).items()
                       if v.get("src")}
    i = p["id"]
    if old.startswith("/img/rl/") and _srcs["rl"].get(i): return [_srcs["rl"][i]]
    if old.startswith("/img/p2/") and _srcs["p2"].get(i): return [_srcs["p2"][i]]
    if p.get("platform") == "weidian": return weidian_photos(p.get("itemId") or i)
    return []


def load_old(old):
    """The live cut-out (RGBA, straight colours) and where it was read."""
    from mirror_photos import mirror_path
    if old.startswith("/img/"):
        f = os.path.join(ROOT, old.lstrip("/").split("?")[0])
    else:
        mp = mirror_path(old); f = os.path.join(ROOT, mp.lstrip("/")) if mp else ""
    if f and os.path.isfile(f):
        im = Image.open(f); im.load()
    else:
        im = fetch_edge(old) if "supabase" in old else None
        if im is None: return None
    im = im.convert("RGBA")
    a = np.asarray(im, dtype=np.int16)
    semi = (a[..., 3] > 20) & (a[..., 3] < 235)
    # premultiplied files (rembg's plain cut-out, e.g. img/fr): no half-transparent pixel is brighter than its alpha
    if semi.sum() > 200 and float((a[..., :3].max(axis=2)[semi] > a[..., 3][semi] + 25).mean()) < 0.02:
        im = unpremul(im)
    return im


def proposals(im):
    """Rough boxes where an item may sit in a photo: the whole photo's item box and the 3 biggest separate things in it
    (a collage: the big product and the small ones)."""
    from scipy import ndimage
    out = [store_box(im)]
    a = np.asarray(im.resize((256, round(256 * im.height / im.width)) if im.width >= im.height else (round(256 * im.width / im.height), 256)), np.int16)
    m = np.abs(a - sp.border_bg(a.astype(np.float32))[None, None, :]).max(axis=2) > 25
    m = ndimage.binary_closing(m, iterations=3)
    lab, n = ndimage.label(m)
    if n:
        areas = ndimage.sum(m, lab, range(1, n + 1))
        k = im.width / a.shape[1]
        for j in np.argsort(-areas)[:3]:
            if areas[j] < 0.02 * m.size: continue
            ys, xs = np.where(lab == j + 1)
            b = (int(xs.min() * k), int(ys.min() * k), int((xs.max() + 1) * k), int((ys.max() + 1) * k))
            if b not in out: out.append(b)
    return out


MATCH = ((0.95, 14.0), (0.92, 20.0))   # (grey correlation at least, colour difference at most): the same photo. The
# old cut-outs were often made from an enlarged, sharpened or colour-lifted copy of the listing photo, which lowers both
# a little (checked by eye on 23 Nov 2026: every pair from 0.92 up was the same photo); another photo of the item (other
# angle or pose) does not line up and scores far lower.


def same_photo(ncc, colour):
    return any(ncc >= n and colour <= c for n, c in MATCH)


def find_original(lu, ref, core, supp, urls, log):
    """The listing photo the old cut-out was made from, lined up with the old cut-out's solid pixels (register, MATCH).
    Returns ((url, image, reg) or None, best score seen)."""
    best = None
    for u in urls[:12]:
        data = wd_get(u) if "geilicdn" in u else sp.fetch(u, timeout=40)
        im = sp.open_any(data, cap=2600) if data else None
        if im is None: continue
        im = sp.on_white(im) if im.mode in ("RGBA", "LA", "P") else im.convert("RGB")
        if min(im.size) < 200: continue
        for sb in proposals(im)[:3]:
            try:
                reg = register(ref, core, supp, im, sb)
            except Exception as e:
                log(f"      register: {str(e)[:60]}"); reg = None
            # a pair that passes the match rule beats one that does not, then the higher correlation
            if reg and (best is None or (same_photo(reg[3], reg[4]), reg[3]) > (same_photo(best[2][3], best[2][4]), best[2][3])):
                best = (u, im, reg)
            if best and best[2][3] >= 0.97 and same_photo(best[2][3], best[2][4]): break
        if best and best[2][3] >= 0.97 and same_photo(best[2][3], best[2][4]): break
    score = None if not best else {"ncc": best[2][3], "colour": best[2][4], "url": best[0]}
    if not best or not same_photo(best[2][3], best[2][4]): return None, score
    return best, score


def old_in_source(img, reg, size):
    """An image of the old cut-out's frame shown in the source photo's frame (source = a * old + (bx, by))."""
    a, bx, by = reg[:3]
    return img.transform(size, Image.AFFINE, (1 / a, 0, -bx / a, 0, 1 / a, -by / a), Image.BILINEAR,
                         fillcolor=0 if img.mode == "L" else (255, 255, 255))


def hanger_above(lost, old_supp, old_a):
    """The pieces of the item matte the old cut-out does not show that sit above it and look like a hanger (a hook, a
    clip bar, a string): short, thin or sparse. The old cut-out took them out on purpose; they are not a lost part and
    the new cut-out leaves them out too. A lost hood or collar is wide, tall and solid, and stays."""
    from scipy import ndimage
    drop = np.zeros(lost.shape, bool)
    rows = np.nonzero(old_supp.any(axis=1))[0]; cols = np.nonzero(old_supp.any(axis=0))[0]
    if not len(rows) or not lost.any(): return drop
    top, oh, ow = rows[0], rows[-1] - rows[0] + 1, cols[-1] - cols[0] + 1
    lab, n = ndimage.label(lost)
    for j in range(1, n + 1):
        c = lab == j
        ys, xs = np.nonzero(c)
        if len(ys) < 20 or (ys < top).mean() < 0.5: continue
        above = c[:top]
        ay, ax = np.nonzero(above)
        if not len(ay): continue
        hh, ww = top - ay.min(), ax.max() - ax.min() + 1
        fill = above.sum() / max(1, hh * ww)
        if hh < 0.08 * oh or fill < 0.4 or ww < 0.2 * ow:
            drop |= ndimage.binary_dilation(c, iterations=3) & ~(old_a >= 128)
    return drop


def do_recut(p, old, labels, models, log):
    """Group d: a live cut-out that may have lost part of the item. The photo it was made from is found again and lined
    up; a quick matte of it shows what the item really covers; when the old cut-out misses more than LOST_FLAG of that,
    the item is cut out again from the original (every check of group c, against the original photo, plus: nothing
    the old cut-out showed may go). Records: flag "intact" / "lost parts" / "no original"."""
    from scipy import ndimage
    from scipy.spatial import ConvexHull
    lu = load_old(old)
    if lu is None: return None, {"flag": "no old photo", "why": "the live photo could not be read"}
    ref_old = sp.on_white(lu); supp = item_support(ref_rgba=lu); core = solid_core(lu)
    lab = labels.get(p["id"]) or {}
    kind = sp.kind_of(p); garment = p.get("cat") in GARMENT
    several = bool(lab.get("is_set")) or bool(set(lab.get("photo_issues") or []) & {"multiple_views", "multiple_items"}) \
        or bool(re.search(r"(?i)\b(sets?|tracksuits?|pairs?|kit|earrings?|socks)\b", p.get("title") or "")) or kind in ("shoe", "small")
    urls = original_urls(p, old)
    rec = {"originals": len(urls)}
    if not urls: return None, dict(rec, flag="no original", why="no original photo to compare with (not a Weidian listing)")
    found, score = find_original(lu, ref_old, core, supp, urls, log)
    rec["match"] = score
    if not found: return None, dict(rec, flag="no original", why="the listing's photos no longer include the photo it was cut from")
    u, im, reg = found
    rec["src_url"] = u; rec["src_size"] = list(im.size)
    oa = old_in_source(lu.getchannel("A"), reg, im.size)
    ob = bbox(np.asarray(oa) >= 128)
    if not ob: return None, dict(rec, flag="no original", why="the old cut-out does not line up")
    w, h = ob[2] - ob[0], ob[3] - ob[1]
    # the region of the original the old cut-out covers, widened 20% each side. Where the item runs out of it on a side
    # that is not the photo's own edge (a lost chain loop, strap or sleeve reaching further), that side is widened and
    # the item looked at again: the region must never cut the item (23 Nov 2026: a chain and a sole cut flat at the
    # frame by the region). The quick matte does not see a white part on a white background, so for a find that will
    # be cut again the cut-out's own first model (birefnet-general) decides too.
    marg = {"left": 0.2, "top": 0.2, "right": 0.2, "bottom": 0.2}
    grown = []
    t = time.time()

    def region():
        roi = (max(0, ob[0] - round(marg["left"] * w)), max(0, ob[1] - round(marg["top"] * h)),
               min(im.width, ob[2] + round(marg["right"] * w)), min(im.height, ob[3] + round(marg["bottom"] * h)))
        src = im.crop(roi)
        old_a = np.asarray(oa.crop(roi))
        old_supp = old_a >= 26
        # keep region: the old cut-out's outline (convex hull) and a margin: a lost part lies inside it, another
        # product of a collage lies outside
        ys, xs = np.nonzero(old_supp)
        keep = np.zeros(old_supp.shape, bool)
        try:
            hull = ConvexHull(np.stack([xs, ys], 1))
            from PIL import ImageDraw
            km = Image.new("L", (src.width, src.height), 0)
            ImageDraw.Draw(km).polygon([(float(xs[v]), float(ys[v])) for v in hull.vertices], fill=255)
            keep = np.asarray(km) > 0
        except Exception:
            keep = old_supp.copy()
        keep = ndimage.binary_dilation(keep, iterations=max(3, round(0.02 * max(src.size))))
        return roi, src, old_a, old_supp, keep

    def runs_out(m, roi):
        # the band touches() reads: an item this close to a side of the region is laid out on that side as if the
        # photo cut it there (a whole sole 4 px above the region's edge was set on the bottom of the frame)
        b = max(2, round(0.006 * max(m.shape)))
        return [s for s, band, edge in (("left", m[:, :b], roi[0] == 0), ("top", m[:b], roi[1] == 0),
                                         ("right", m[:, -b:], roi[2] == im.width), ("bottom", m[-b:], roi[3] == im.height))
                if band.any() and not edge]

    for k in range(4):
        roi, src, old_a, old_supp, keep = region()
        # what the item really covers: a quick matte of the original (PHOTO_WHITE_DETECT: another model for a find
        # whose white body the quick matte cannot see on a white background either, e.g. birefnet-hr)
        dm = np.asarray(keep_pieces(matte(src, DETECT), keep)) >= 128
        # a hanger only above clothes (a top, trousers, shorts). Above sunglasses, a bag or a shoe a thin piece is a
        # temple, a handle or a strap, and lost (23 Nov 2026: a Burberry sunglasses temple was taken for a hanger)
        drop = hanger_above(dm & ~(old_a >= 64), old_supp, old_a) if kind in ("top", "pants", "shorts") \
            else np.zeros(dm.shape, bool)
        lost_old = float(((dm & ~drop) & ~(old_a >= 64)).sum() / max(1, (dm & ~drop).sum()))
        if k == 3: break
        grow = runs_out(dm, roi)
        if not grow and lost_old > LOST_FLAG:
            grow = runs_out(np.asarray(keep_pieces(matte(src, "birefnet-general"), keep)) >= 128, roi)
        if not grow: break
        for s in grow: marg[s] += 0.6
        grown += grow
    old_solid = ndimage.binary_erosion(old_a >= 230, iterations=2)
    dm = dm & ~drop
    rec["detect"] = {"lost_old": round(lost_old, 4), "s": round(time.time() - t, 1)}
    if LOST_MAX["d"] != 0.01: rec["lost_max"] = LOST_MAX["d"]
    if drop.any(): rec["detect"]["hanger"] = round(float(drop.sum() / max(1, dm.sum())), 4)
    if grown: rec["detect"]["grown"] = grown
    if lost_old <= LOST_FLAG:
        return None, dict(rec, flag="intact", why=f"intact: the old cut-out has the whole item ({100 * lost_old:.1f}% not in it)")
    rec["flag"] = "lost parts"
    log(f"      old cut-out misses {100 * lost_old:.1f}% of the item: cut out again from {u[-50:]}")
    bg = sp.border_bg(np.asarray(src, dtype=np.float32))
    ref, bgmask, _ = flat_bg(src)
    # the reference: the original photo around the whole item, the parts the old cut-out lost included (they lie
    # outside its outline when a whole sleeve or half the body went), without a hanger the old cut-out had taken out
    region = ndimage.binary_dilation(keep | dm, iterations=max(3, round(0.03 * max(src.size)))) & ~drop
    ref = Image.fromarray(np.where(region[..., None], np.asarray(ref), 255).astype(np.uint8))
    sup = item_support(ref_rgb=src, bgmask=bgmask | ~region, bg=bg)
    out, r = try_source("d", src, bg, ref, sup, None, False, kind, garment, several, models, {}, "orig", log, None,
                        (bgmask, bg), keep=keep, old_core=old_solid, drop=drop)
    rec.update({"source": "original", **r})
    if out is not None: rec.update(model=r["model"], checks=r["checks"])
    else: rec["why"] = "lost parts, not fixed: " + str(r.get("why"))
    return out, rec


# ---------------------------------------------------------------- run
def retryable(rec):
    """A photo not fixed before whose reason a new run can change (not: a person / box / collage in the photo, an item
    the photo crops, a source that is gone). d: every find flagged for lost parts (fixed or not: the newest rules decide)
    and every find whose listing photos were read but not matched."""
    if rec.get("group") == "d":
        return rec.get("flag") == "lost parts" or (rec.get("flag") == "no original" and bool(rec.get("originals")))
    w = str(rec.get("why") or "")
    return not rec.get("ok") and not w.startswith("needs a new photo") and "cut off by the photo" not in w \
        and "missing" not in w


def state_path(shard):
    k, n = shard
    return os.path.join(STATE_DIR, f"{k}-of-{n}.json")


def load_done():
    done = {}
    if os.path.isdir(STATE_DIR):
        for f in sorted(os.listdir(STATE_DIR)):
            if f.endswith(".json"):
                for k, v in (load_json(os.path.join(STATE_DIR, f), {}).get("items") or {}).items():
                    if v.get("v") == VERSION: done[k] = v
    return done


def sheet(rows, path):
    """rows: (label, before RGB, after RGB or None, text). Before on the site's grey well (#F5F5F5) as it shows today."""
    T, cols = 260, 3
    if not rows: return
    sh = Image.new("RGB", (cols * (2 * T + 24), ((len(rows) + cols - 1) // cols) * (T + 34)), (255, 255, 255))
    d = ImageDraw.Draw(sh)
    for k, (lab, before, after, text) in enumerate(rows):
        cx, cy = (k % cols) * (2 * T + 24), (k // cols) * (T + 34)
        b = before.copy(); b.thumbnail((T, T)); sh.paste(b, (cx + 4, cy + 4))
        if after is not None:
            a = after.copy(); a.thumbnail((T, T)); sh.paste(a, (cx + T + 8, cy + 4))
            d.rectangle((cx + T + 8, cy + 4, cx + 2 * T + 8, cy + T + 4), outline=(210, 214, 222))
        else:
            d.rectangle((cx + T + 8, cy + 4, cx + 2 * T + 8, cy + T + 4), fill=(255, 236, 236))
        d.text((cx + 6, cy + T + 8), lab, fill=(0, 0, 0))
        d.text((cx + 6, cy + T + 20), text[:88], fill=(60, 60, 60) if after is not None else (170, 20, 20))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    sh.save(path)


def on_well(im):
    """A photo as the site shows it today: transparent parts on the grey photo well."""
    if "A" not in im.getbands(): return im.convert("RGB")
    c = Image.new("RGBA", im.size, (245, 245, 245, 255)); c.alpha_composite(im.convert("RGBA")); return c.convert("RGB")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--group", default="a,b,c")
    ap.add_argument("--ids", default="")
    ap.add_argument("--shard", default="0/1")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--models", default=",".join(MODELS))
    ap.add_argument("--redo", action="store_true")
    ap.add_argument("--max-minutes", type=float, default=0, help="stop starting new photos after this many minutes")
    ap.add_argument("--retry", action="store_true", help="also do the photos not fixed before, unless the photo itself is the problem")
    a = ap.parse_args(argv)
    shard = shards.parse(a.shard)
    groups = set(a.group.split(","))
    models = [m for m in a.models.split(",") if m]
    items = {p["id"]: p for p in load_catalog()[1]}
    labels = (load_json(os.path.join(ROOT, "data", "catalog_ai.json"), {}) or {}).get("items") or {}
    tg = load_json(TARGETS, {})
    only = set(a.ids.replace(" ", "").split(",")) - {""}
    done = {} if a.redo else load_done()
    jobs = []                       # (id, group, key, name or path)
    for g in ("a", "b", "c", "d"):
        if g not in groups: continue
        for i, x in tg.get(g) or []:
            if only and i not in only: continue
            if not shards.mine(i, shard) or i not in items: continue
            if g in ("a", "b") and MODEL_SHOT.search(x): continue          # never a model shot
            if g == "d" and items[i].get("img") != x: continue              # the find shows another photo now
            key = x if g in ("a", "b") else ("d:" + i) if g == "d" else i
            if key in done and not (a.retry and retryable(done[key])): continue
            jobs.append((i, g, key, x))
    if a.limit: jobs = jobs[:a.limit]
    print(f"photo_white: {len(jobs)} photos in shard {a.shard} ({', '.join(sorted(groups))}), {len(done)} done before", flush=True)
    sp_ = state_path(shard)
    st = load_json(sp_, {"items": {}}); st.setdefault("items", {})
    cands, logs = sp.load_cands(), sp.load_log()
    pools, caches, useds = {}, {}, {}
    rows, nsheet, t0 = [], 0, time.time()
    for n, (i, g, key, x) in enumerate(jobs):
        if a.max_minutes and time.time() - t0 > a.max_minutes * 60:
            print("time limit reached; the rest waits for the next run", flush=True); break
        p = items[i]
        print(f"[{n + 1}/{len(jobs)}] {g} {i} {x} {p.get('title')}", flush=True)
        t = time.time()
        try:
            if g == "c":
                out, rec = do_rl(p, x, labels, models, lambda s: print(s, flush=True))
            elif g == "d":
                out, rec = do_recut(p, x, labels, models, lambda s: print(s, flush=True))
            else:
                if i not in pools: pools[i], caches[i], useds[i] = sp.pool_for(i, cands.get(i), logs.get(i)), {}, set()
                out, rec = do_store(p, g, x, pools[i], caches[i], useds[i], models, lambda s: print(s, flush=True))
        except Exception as e:
            out, rec = None, {"why": "error: " + repr(e)[:160]}
        rec.update(v=VERSION, id=i, group=g, at=now(), s=round(time.time() - t))
        if g == "c": rec["old"] = "/" + x
        elif g == "d": rec["old"] = x
        else: rec["old"] = sp.STORE + x
        if out is not None:
            folder = {"c": "rl", "d": "recut"}.get(g, "store")
            fn = (i + ".webp") if g in ("c", "d") else x
            os.makedirs(OUT[folder], exist_ok=True)
            buf = io.BytesIO(); out.save(buf, "WEBP", quality=90, method=6); data = buf.getvalue()
            open(os.path.join(OUT[folder], fn), "wb").write(data)
            rec.update(ok=True, file=f"img/white/{folder}/{fn}", kb=round(len(data) / 1024))
        else:
            rec["ok"] = False
        st["items"][key] = rec; st["at"] = now()
        save_json(sp_, st)
        print(f"   -> {'OK ' + rec.get('file', '') if rec['ok'] else 'NOT FIXED: ' + str(rec.get('why'))} ({rec['s']} s)", flush=True)
        try:
            if g == "d" and rec.get("flag") != "lost parts": raise StopIteration
            before = on_well(Image.open(os.path.join(ROOT, x)) if g == "c" else load_old(x) if g == "d" else (fetch_edge(sp.STORE + x) or Image.new("RGB", (8, 8))))
            rows.append((f"{g} {key}", before, out, (rec.get("model") or "") + " " + json.dumps(rec.get("checks") or {})[:70] if rec["ok"] else str(rec.get("why"))))
        except Exception:
            pass
        if len(rows) >= 24:
            nsheet += 1; sheet(rows, os.path.join(SHEETS, f"sheet-{shard[0]}-of-{shard[1]}-{nsheet:02d}.png")); rows = []
    if rows:
        nsheet += 1; sheet(rows, os.path.join(SHEETS, f"sheet-{shard[0]}-of-{shard[1]}-{nsheet:02d}.png"))
    res = [st["items"][k] for _, _, k, _ in jobs if k in st["items"]]
    print("summary: %d photos, %d fixed, %d not fixed; %.0f s" % (len(res), sum(1 for r in res if r.get("ok")),
          sum(1 for r in res if not r.get("ok")), time.time() - t0), flush=True)
    print("remaining %d" % (len(jobs) - len(res)), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
