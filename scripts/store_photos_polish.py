# -*- coding: utf-8 -*-
"""Premium store photos (owner, 22 Nov 2026: the store photos "look cheap / blurry, not premium enough"; target look:
pure white cut-out, Zalando / SSENSE product-shot style).

For every live store photo of a find (catalogue "img" in products/store/ and the extra angles in store-gallery.json):
  1. best source: the store image the photo was cut from, found again among the find's candidates
     (data/store_photo_candidates.json + shard files: the image URLs the collector saw on the shop pages), matched to the
     live photo by shape and a perceptual signature so the SAME photo / angle is kept, then asked from the shop's CDN at
     the largest size it serves (Shopify original, SSENSE / END. / MR PORTER / Zalando / StockX / SFCC width params ...).
     Without a match the live file itself is the source.
  2. cut-out: birefnet-general and isnet-general-use (rembg) on the source (or the live alpha when the live file is the
     source); the cleaner edge wins (boundary on real image edges, little fuzz, no specks). Then specks are dropped,
     enclosed background gaps stay open (bag handles) while gaps the matting ate inside the item are filled, the
     background colour is taken out of the semi-transparent edge (no halo), faint alpha is choked.
  3. sharpness: the item's real resolution is measured (a CDN or the old pipeline may have upscaled it); under the size
     it is shown at, Real-ESRGAN (scripts/restore.py models, realesr-general x4v3 + wdn) enlarges it, guarded: the result
     shrunk back must match the input, both blurred 1.2 px (mean diff on the item under 4.5, under 8 on the high-detail
     pixels where logos and text are), else Lanczos. Then a light unsharp mask.
  4. framing: 1600 x 1600, flat #FFFFFF, item centred, fill by type (tops / outerwear 82% of the height, pants 86%,
     shoes 84% of the width a little below centre (a contact shadow was tried and is off: SHADOW), bags 78%, small
     accessories 70%), WebP q90.
  5. upload to Supabase products/store2/<same name>.webp (the live products/store/ files are never touched).
Model shots (-m / -dm) are not cut out: only re-sent at a higher resolution when the store serves a larger copy.

State (resumable): data/store_photos_polish.json, or data/store_photos_polish/<k>-of-<n>.json for shard k of n.
Local copies: out/store-polish/<name>.webp (+ <name>.json notes).

  python scripts/store_photos_polish.py [--ids 1,2] [--limit 40] [--shard 0/1] [--redo] [--dry]
"""
import argparse, glob, io, os, re, sys, threading, time, urllib.error, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import numpy as np
from PIL import Image, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from catalog_common import ROOT, load_catalog, load_json, save_json  # noqa: E402
import store_photos_shards as shards  # noqa: E402

SUPA = "https://uptpghuduqjqmrxwatbm.supabase.co"
STORE = SUPA + "/storage/v1/object/public/products/store/"
STORE2 = SUPA + "/storage/v1/object/public/products/store2/"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36"
OUT = os.path.join(ROOT, "out", "store-polish")
STATE = os.path.join(ROOT, "data", "store_photos_polish.json")
STATE_DIR = os.path.join(ROOT, "data", "store_photos_polish")
SIZE = 1600
ESRGAN_BELOW = 1100      # real item resolution (long side) under which Real-ESRGAN is tried
POOL_MAX = 70            # candidates looked at per find (src pages first)
VERSION = 2              # 2: same-photo check after the cut-out, one store image per live photo
SHADOW = False           # contact shadow under shoes: tried in the pilot, it read as a grey smudge on pure white; off

# fill by type: (share of the width, share of the height, centre y) the item may take; it is scaled to the tighter one
FILL = {
    "top": (0.86, 0.82, 0.50),
    "pants": (0.80, 0.86, 0.50),
    "shorts": (0.84, 0.80, 0.50),
    "shoe": (0.84, 0.74, 0.54),
    "bag": (0.78, 0.78, 0.50),
    "small": (0.70, 0.70, 0.50),
}
SMALL_WORDS = r"sunglass|glasses|belt|cap\b|hat\b|beanie|wallet|card ?holder|watch|bracelet|ring\b|necklace|chain|earring|keychain|key ring|scarf|glove|socks|tie\b|lighter"


def now(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def kind_of(p):
    cat = (p.get("cat") or "").lower(); t = (p.get("title") or "").lower()
    if cat == "shoes" or re.search(r"sneaker|shoe|boot|slide|loafer|trainer|jordan|yeezy|dunk|foam runner", t): return "shoe"
    if cat == "bags" or re.search(r"\bbag\b|duffle|backpack|tote|briefcase|pouch|keepall", t):
        return "small" if re.search(r"wallet|card ?holder|pouch", t) else "bag"
    if cat in ("accessories", "headwear", "toys") or re.search(SMALL_WORDS, t): return "small"
    if cat == "shorts" or re.search(r"\bshorts\b|swim", t): return "shorts"
    if cat == "pants" or re.search(r"pants|jeans|trousers|joggers|cargo", t): return "pants"
    return "top"


# ---------------------------------------------------------------- fetching (polite: per-host gap, retries, skip-not-fail)
_host_lock, _host_next = threading.Lock(), {}


def fetch(url, timeout=30, tries=2):
    host = urllib.parse.urlsplit(url).netloc
    for k in range(tries):
        with _host_lock:
            t = max(time.time(), _host_next.get(host, 0)); _host_next[host] = t + 0.35   # about 3 requests / s per host
        time.sleep(max(0, t - time.time()))
        try:
            h = {"User-Agent": UA, "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
                 "Referer": "https://" + host + "/"}
            with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code in (400, 401, 403, 404, 410) or k == tries - 1: return None
        except Exception:
            if k == tries - 1: return None
        time.sleep(2 + 3 * k)
    return None


def open_any(data, cap=2600):
    """The image, at most cap px on its long side (a 6000 px original would only cost memory: it is shown at 1376)."""
    try:
        im = Image.open(io.BytesIO(data))
        if im.width * im.height > 60e6: return None
        if im.format == "JPEG": im.draft("RGB", (cap, cap))
        im.load()
        if max(im.size) > cap: im = im.copy(); im.thumbnail((cap, cap), Image.LANCZOS)
        return im
    except Exception:
        return None


def bigger(u):
    """Larger copies the shop's CDN serves for an image URL, largest first (the URL itself last)."""
    out = []
    s = urllib.parse.urlsplit(u); host = s.netloc.lower(); q = urllib.parse.parse_qsl(s.query, keep_blank_values=True)

    def with_q(path=None, drop=(), put=None):
        qq = [(k, v) for k, v in q if k.lower() not in drop]
        for k, v in (put or {}).items():
            qq = [(a, b) for a, b in qq if a != k] + [(k, v)]
        return urllib.parse.urlunsplit((s.scheme, s.netloc, path if path is not None else s.path, urllib.parse.urlencode(qq), ""))
    # Shopify: the original sits behind the name without its _1080x / _800x800 suffix and without width/crop params
    if "cdn.shopify.com" in host or "/cdn/shop/" in s.path:
        p = re.sub(r"_(\d+x\d*|x\d+|\d+x)(_crop_\w+)?(@\dx)?(?=\.\w+$)", "", s.path)
        out.append(with_q(p, drop=("width", "height", "crop", "w", "h")))
    if "ssensemedia.com" in host:
        out.append(re.sub(r"/images/[^/]+/", "/images/b_white,g_center,f_auto,q_auto:best,w_2400/", u, count=1))
    if re.search(r"mrporter|net-a-porter|theoutnet|yoox", host):
        out.append(re.sub(r"/w\d+_q\d+(\.\w+)$", r"/w2000_q80\1", u))
    if "farfetch-contents.com" in host:
        out += [re.sub(r"_\d+(\.\w+)$", r"_2048\1", u), re.sub(r"_\d+(\.\w+)$", r"_1000\1", u)]
    if "mytheresa.com" in host:
        out.append(re.sub(r"img\.mytheresa\.com/\d+/\d+/\d+/", "img.mytheresa.com/2310/2612/100/", u))
    if "endclothing.com" in host:
        out.append(re.sub(r"w_\d+", "w_2400", u))
    if "ztat.net" in host:
        out.append(with_q(put={"imwidth": "2400"}))
    if "stockx.com" in host:
        out.append(with_q(drop=("w", "h", "q", "dpr"), put={"w": "2000", "q": "90"}))
    if "goat.com" in host:
        out.append(re.sub(r"/transform/v1/attachments/", "/attachments/", u))
    if "demandware.static" in u or "/dw/image/" in u:
        out.append(with_q(drop=("sw", "sh", "sm", "sfrm", "q"), put={"sw": "2400", "q": "95"}))
    if "/is/image/" in s.path:   # Scene7
        out.append(with_q(drop=("wid", "hei", "fmt", "qlt", "$", "op_sharpen"), put={"wid": "2400", "fmt": "png-alpha" if False else "jpg", "qlt": "95"}))
    if "cloudinary" in host or "/upload/" in s.path and re.search(r"/w_\d+", s.path):
        out.append(re.sub(r"\bw_\d+", "w_2400", u))
    if re.search(r"/\d{2,4}x\d{2,4}[^/]*/", s.path):   # path size folders (600x600_grey/...) -> zoom
        pass
    gen = {k.lower() for k, _ in q} & {"width", "w", "imwidth", "wid", "size", "resize", "height", "h"}
    if gen:
        out.append(with_q(drop=("width", "w", "imwidth", "wid", "height", "h", "size", "resize")))
    out.append(u)
    seen, res = set(), []
    for x in out:
        if x and x not in seen: seen.add(x); res.append(x)
    return res


# ---------------------------------------------------------------- image helpers
def on_white(im):
    im = im.convert("RGBA"); bg = Image.new("RGBA", im.size, (255, 255, 255, 255)); bg.alpha_composite(im)
    return bg.convert("RGB")


def border_bg(a):
    """Median colour of the image border (the studio background)."""
    b = np.concatenate([a[:4].reshape(-1, 3), a[-4:].reshape(-1, 3), a[:, :4].reshape(-1, 3), a[:, -4:].reshape(-1, 3)])
    return np.median(b, axis=0)


def fg_box(rgb):
    """Bounding box of what differs from the border colour (rough, for matching only)."""
    a = np.asarray(rgb, dtype=np.int16)
    d = np.abs(a - border_bg(a)[None, None, :]).max(axis=2) > 22
    rows, cols = np.where(d.mean(1) > 0.004)[0], np.where(d.mean(0) > 0.004)[0]
    if not len(rows) or not len(cols): return (0, 0, rgb.width, rgb.height)
    return (int(cols[0]), int(rows[0]), int(cols[-1]) + 1, int(rows[-1]) + 1)


def alpha_box(alpha, thr=24):
    m = np.asarray(alpha) >= thr
    ys, xs = np.where(m)
    if not len(ys): return None
    return (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)


def sig(rgb_crop):
    """24x24 grey, zero mean / unit variance: compared by correlation."""
    g = np.asarray(rgb_crop.convert("L").resize((24, 24), Image.BILINEAR), dtype=np.float32).ravel()
    g = g - g.mean(); n = np.linalg.norm(g)
    return g / n if n > 1e-6 else g


def item_sig(im, cut):
    """(signature, aspect) of the item: cut-outs by their alpha box, store photos by their foreground box."""
    if cut:
        b = alpha_box(im.getchannel("A"))
        if not b: return None
        c = on_white(im.crop(b))
    else:
        rgb = im.convert("RGB"); b = fg_box(rgb); c = rgb.crop(b)
    return sig(c), c.width / max(1, c.height)


def whole_sig(im):
    rgb = on_white(im) if im.mode == "RGBA" else im.convert("RGB")
    return sig(rgb), rgb.width / max(1, rgb.height)


def match_score(a, b):
    if a is None or b is None: return -1
    (sa, ra), (sb, rb) = a, b
    if abs(np.log(ra / rb)) > 0.10: return -1
    return float(np.dot(sa, sb))


def eff_scale(rgb, mask=None):
    """Share of its pixel size the image really has: the smallest scale whose down-and-up round trip loses almost
    nothing (an upscaled photo survives a strong shrink; a sharp one does not)."""
    g = rgb.convert("L"); w, h = g.size
    a = np.asarray(g, dtype=np.float32)
    m = np.ones_like(a, bool) if mask is None else (np.asarray(mask) >= 128)
    if m.sum() < 1000: return 1.0
    for s in (0.35, 0.45, 0.55, 0.65, 0.75, 0.85):
        sm = g.resize((max(8, round(w * s)), max(8, round(h * s))), Image.LANCZOS).resize((w, h), Image.LANCZOS)
        err = np.abs(np.asarray(sm, dtype=np.float32) - a)[m].mean()
        if err < 1.1: return s
    return 1.0


# ---------------------------------------------------------------- matting
_sess = {}


def matte(rgb, model):
    from rembg import remove, new_session
    if model not in _sess:
        import onnxruntime as ort
        o = ort.SessionOptions()   # no memory arena: BiRefNet otherwise keeps 10+ GB after a few photos
        o.enable_cpu_mem_arena = False; o.enable_mem_pattern = False
        _sess[model] = new_session(model, sess_opts=o)
    src = rgb
    if max(src.size) > 2400: src = src.copy(); src.thumbnail((2400, 2400), Image.LANCZOS)
    m = remove(src, session=_sess[model], only_mask=True)
    m = m.convert("L")
    return m.resize(rgb.size, Image.LANCZOS) if m.size != rgb.size else m


def clean_alpha(alpha, rgb=None, bg=None):
    """Specks out, gaps decided, faint fringe choked. Returns (alpha L, notes)."""
    from scipy import ndimage
    a = np.asarray(alpha, dtype=np.float32) / 255.0
    notes = []
    solid = a >= 0.5
    lab, n = ndimage.label(solid)
    if n > 1:
        areas = ndimage.sum(solid, lab, range(1, n + 1))
        big = areas.max()
        drop = [k + 1 for k, ar in enumerate(areas) if ar < 0.015 * big]
        if drop:
            dm = np.isin(lab, drop)
            # also the faint pixels around a dropped speck
            dm = ndimage.binary_dilation(dm, iterations=2) & ~ndimage.binary_dilation(np.isin(lab, [k for k in range(1, n + 1) if k not in drop]), iterations=1)
            a[dm] = 0; notes.append(f"{len(drop)} specks out")
    # faint haze far from the item (alpha under 0.5 that is not next to it) goes
    near = ndimage.binary_dilation(a >= 0.5, iterations=3)
    if (~near & (a > 0)).any(): a[~near] = 0
    # gaps: enclosed clear regions
    clear = a < 0.5
    lab, n = ndimage.label(clear)
    if n > 1:
        edge = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
        filled = 0
        for k in range(1, n + 1):
            if k in edge: continue
            reg = lab == k
            if rgb is not None and bg is not None:
                px = np.asarray(rgb, dtype=np.float32)[reg]
                if np.abs(px - bg[None, :]).max(axis=1).mean() < 22: continue    # real gap: the background shows
            if rgb is None and reg.sum() > 0.002 * a.size: continue              # no source: keep larger gaps open
            a[reg] = 1.0; filled += 1
        if filled: notes.append(f"{filled} gaps filled")
    # choke the faint fringe a little (no grey halo), keep the edge soft over ~1 px
    a = np.clip((a - 0.06) / 0.88, 0, 1)
    return Image.fromarray((a * 255).round().astype(np.uint8)), notes


def decontaminate(rgb, alpha, bg):
    """Take the background colour out of the semi-transparent edge: F = (I - (1 - a) B) / a."""
    I = np.asarray(rgb, dtype=np.float32); a = np.asarray(alpha, dtype=np.float32)[..., None] / 255.0
    edge = (a > 0.02) & (a < 0.98)
    F = np.where(edge, (I - (1 - a) * bg[None, None, :]) / np.maximum(a, 0.02), I)
    return Image.fromarray(np.clip(F, 0, 255).round().astype(np.uint8))


def edge_score(alpha, rgb):
    """Higher is cleaner: the boundary on real image edges, little fuzz, no specks."""
    from scipy import ndimage
    a = np.asarray(alpha, dtype=np.float32) / 255.0
    hard = a >= 0.5
    if hard.sum() < 500: return -1e9
    perim = hard ^ ndimage.binary_erosion(hard)
    fuzz = ((a > 0.06) & (a < 0.94)).sum() / max(1, perim.sum())
    g = np.asarray(rgb.convert("L"), dtype=np.float32)
    gm = np.hypot(ndimage.sobel(g, 0), ndimage.sobel(g, 1))
    grad = float(gm[ndimage.binary_dilation(perim, iterations=1)].mean())
    lab, n = ndimage.label(hard)
    speck = 0.0
    if n > 1:
        areas = np.sort(ndimage.sum(hard, lab, range(1, n + 1)))
        speck = float(areas[areas < 0.015 * areas[-1]].sum() / areas.sum())
    return grad - 6.0 * max(0.0, fuzz - 2.5) - 400.0 * speck


# ---------------------------------------------------------------- enlarging
def sr_tiled(net, rgb, tile=192, pad=12):
    """The 4x model in tiles (a whole 1000 px photo would need several GB of memory)."""
    import torch
    x = np.asarray(rgb, dtype=np.float32) / 255.0
    H, W = x.shape[:2]
    out = np.zeros((H * 4, W * 4, 3), dtype=np.float32)
    for y0 in range(0, H, tile):
        for x0 in range(0, W, tile):
            y1, x1 = min(H, y0 + tile), min(W, x0 + tile)
            ya, xa, yb, xb = max(0, y0 - pad), max(0, x0 - pad), min(H, y1 + pad), min(W, x1 + pad)
            t = torch.from_numpy(np.ascontiguousarray(x[ya:yb, xa:xb])).permute(2, 0, 1).unsqueeze(0)
            with torch.no_grad(): y = net(t).clamp_(0, 1)[0].permute(1, 2, 0).numpy()
            out[y0 * 4:y1 * 4, x0 * 4:x1 * 4] = y[(y0 - ya) * 4:(y0 - ya + y1 - y0) * 4, (x0 - xa) * 4:(x0 - xa + x1 - x0) * 4]
    return Image.fromarray((out * 255.0).round().astype("uint8"))


def esrgan(rgb, tw, th):
    """(image at tw x th, note). Real-ESRGAN with the guard, else Lanczos."""
    lz = rgb.resize((tw, th), Image.LANCZOS)
    try:
        from restore import _load
        net = _load()
        if net is None: return lz, "lanczos (no Real-ESRGAN model)"
        sr = sr_tiled(net, rgb)
        out = sr.resize((tw, th), Image.LANCZOS)
        # the guard compares the result shrunk back with the input, both slightly blurred (1.2 px): the model's
        # sharpening and JPEG clean-up then cancel out and only changed shapes count (a redrawn letter, a moved seam).
        # Pilot, 22 Nov 2026: the plain diff rejected 16 of 31 clean results (Jordan swoosh, Moncler badge looked
        # right at 100%); blurred, true results score under 4 / 7.1
        blur = lambda im: np.asarray(im.filter(ImageFilter.GaussianBlur(1.2)), dtype=np.float32)
        back, src = blur(out.resize(rgb.size, Image.LANCZOS)), blur(rgb)
        d = np.abs(back - src).max(axis=2)
        raw = np.asarray(rgb, dtype=np.float32)
        item = raw.min(axis=2) < 250                               # not the white around it
        if item.sum() < 500: return lz, "lanczos (tiny item)"
        from scipy import ndimage
        g = raw.mean(axis=2); gm = np.hypot(ndimage.sobel(g, 0), ndimage.sobel(g, 1))
        detail = item & (gm > np.percentile(gm[item], 90))         # logos, text, seams
        mad, mdet = float(d[item].mean()), float(d[detail].mean()) if detail.any() else 0.0
        if mad > 4.5 or mdet > 8.0:
            return lz, f"lanczos (Real-ESRGAN rejected: diff {mad:.1f} / detail {mdet:.1f})"
        return out, f"Real-ESRGAN (diff {mad:.1f} / detail {mdet:.1f})"
    except Exception as e:
        return lz, "lanczos (" + str(e)[:60] + ")"


def place(rgb, alpha, kind, notes, shadow_ok=True):
    """rgb / alpha cropped to the item, at source resolution -> the 1600 x 1600 white photo."""
    fw, fh, cy = FILL[kind]
    w, h = rgb.size
    s = min(fw * SIZE / w, fh * SIZE / h)
    tw, th = max(1, round(w * s)), max(1, round(h * s))
    es = eff_scale(rgb, alpha)
    real = max(w, h) * es
    notes["real_px"] = round(real)
    notes["shown_px"] = max(tw, th)
    if real < ESRGAN_BELOW and max(tw, th) > real * 1.08:
        inp = rgb
        if es < 0.97:   # back to the real resolution first, so the model sees the true detail scale
            inp = rgb.resize((max(8, round(w * es)), max(8, round(h * es))), Image.LANCZOS)
        if max(inp.size) * 4 < max(tw, th):  # a 4x pass still short: Lanczos the rest after it (rare)
            pass
        big, note = esrgan(inp, tw, th)
        notes["up"] = note
    else:
        big = rgb.resize((tw, th), Image.LANCZOS)
        notes["up"] = "lanczos" if max(tw, th) > max(w, h) else "downscale"
    big = big.filter(ImageFilter.UnsharpMask(radius=0.9, percent=40, threshold=2))
    a = alpha.resize((tw, th), Image.LANCZOS)
    canvas = Image.new("RGB", (SIZE, SIZE), (255, 255, 255))
    x0 = (SIZE - tw) // 2
    y0 = round(SIZE * cy - th / 2); y0 = max(0, min(SIZE - th, y0))
    if kind == "shoe" and SHADOW and shadow_ok and tw / th > 1.45:
        canvas = contact_shadow(canvas, x0, y0, tw, th, a)
        notes["shadow"] = True
    canvas.paste(big, (x0, y0), a)
    return canvas


def contact_shadow(canvas, x0, y0, tw, th, a):
    """A very soft, low shadow under the sole (side views only)."""
    m = np.asarray(a) >= 128
    cols = np.where(m.any(axis=0))[0]
    if not len(cols): return canvas
    bottom = np.array([np.where(m[:, c])[0].max() for c in cols])
    yb = y0 + int(np.percentile(bottom, 92))
    lx, rx = x0 + cols[0] + 0.06 * tw, x0 + cols[-1] - 0.06 * tw
    sh = Image.new("L", canvas.size, 0)
    from PIL import ImageDraw
    d = ImageDraw.Draw(sh)
    eh = max(6, round(0.035 * tw))
    d.ellipse((lx, yb - eh * 0.6, rx, yb + eh * 0.6), fill=60)
    sh = sh.filter(ImageFilter.GaussianBlur(max(4, eh * 0.9)))
    dark = Image.new("RGB", canvas.size, (0, 0, 0))
    k = np.asarray(sh, dtype=np.float32) * 0.42            # at most ~10% darker
    return Image.composite(dark, canvas, Image.fromarray(k.round().astype(np.uint8)))


# ---------------------------------------------------------------- data
def load_cands():
    """{id: entry}; shard files win over the top file (they hold the deep pass)."""
    out = {}
    for f in [os.path.join(ROOT, "data", "store_photo_candidates.json")] + sorted(glob.glob(os.path.join(ROOT, "data", "store_photos", "*", "store_photo_candidates.json"))):
        for k, v in (load_json(f, {}).get("items") or {}).items():
            if isinstance(v, dict) and v.get("c") and len(v["c"]) >= len((out.get(k) or {}).get("c") or []): out[k] = v
    return out


def load_log():
    out = dict(load_json(os.path.join(ROOT, "data", "store_photos.json"), {}).get("items") or {})
    for f in sorted(glob.glob(os.path.join(ROOT, "data", "store_photos", "*", "store_photos.json"))):
        for k, v in (load_json(f, {}).get("items") or {}).items(): out.setdefault(k, v)
    return out


def live_photos(items):
    """{id: [file names, main first]} of the live store photos."""
    gal = load_json(os.path.join(ROOT, "store-gallery.json"), {})
    out = {}
    for p in items:
        u = p.get("img") or ""
        names = [u[len(STORE):].split("?")[0]] if u.startswith(STORE) else []
        names += [n for n in gal.get(p["id"], []) if n not in names]
        if names: out[p["id"]] = names
    return out


def views():
    return (load_json(os.path.join(ROOT, "data", "stats.json"), {}) or {}).get("p") or {}


def state_path(shard):
    k, n = shard
    return STATE if n == 1 else os.path.join(STATE_DIR, f"{k}-of-{n}.json")


def load_done():
    done = {}
    for f in [STATE] + sorted(glob.glob(os.path.join(STATE_DIR, "*.json"))):
        for k, v in (load_json(f, {}).get("items") or {}).items():
            if v.get("v") == VERSION and v.get("done"): done[k] = v
    return done


def pool_for(i, entry, rec):
    """Candidate image URLs, most likely first: the pages the photos came from, then the chosen store, then the rest."""
    if not entry: return []
    pages = entry.get("p") or []
    src = set((rec or {}).get("src") or [])
    stores = {s for s in [(rec or {}).get("store"), (rec or {}).get("store2"), ((rec or {}).get("prev") or {}).get("store")] if s}
    host = lambda u: re.sub(r"^www\.", "", urllib.parse.urlsplit(u).netloc.lower())

    def rank(c):
        pg = pages[c[1]] if 0 <= c[1] < len(pages) else ""
        key = host(pg) + urllib.parse.urlsplit(pg).path
        if pg in src: return 0
        if key in stores: return 1
        if host(pg) in {s.split("/")[0] for s in stores}: return 2
        return 3
    cs = sorted(entry["c"], key=rank)
    seen, out = set(), []
    for c in cs:
        u = c[0]; base = re.sub(r"[?#].*$", "", u)
        if base in seen: continue
        seen.add(base); out.append((u, pages[c[1]] if 0 <= c[1] < len(pages) else "", rank(c)))
    return out[:POOL_MAX]


# ---------------------------------------------------------------- one find
def upload(name, data, dry):
    if dry: return STORE2 + name
    key = os.environ["SUPABASE_SERVICE_KEY"]
    req = urllib.request.Request(SUPA + "/storage/v1/object/products/store2/" + name, data=data, method="POST", headers={
        "User-Agent": UA, "Authorization": "Bearer " + key, "apikey": key, "Content-Type": "image/webp",
        "x-upsert": "true", "Cache-Control": "max-age=31536000"})
    waits = [3, 8, 20, 40, 60]
    for k in range(len(waits) + 1):
        try:
            urllib.request.urlopen(req, timeout=60).read(); return STORE2 + name
        except urllib.error.HTTPError as e:
            if e.code not in (408, 429, 500, 502, 503, 504, 520, 522, 524, 544) or k == len(waits): raise
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if k == len(waits): raise
        time.sleep(waits[k])


def find_source(live_im, is_model, pool, cache, used=()):
    """(url, image, score) of the largest store copy of this exact photo, or None. cache: url -> image|None."""
    target = whole_sig(live_im) if is_model else item_sig(live_im, True)
    best = None
    for start in range(0, len(pool), 8):
        batch = [u for u, _, _ in pool[start:start + 8] if u not in cache]
        with ThreadPoolExecutor(4) as ex:
            for u, data in zip(batch, ex.map(fetch, batch)):
                im = open_any(data) if data else None
                if im is not None:
                    im = on_white(im) if im.mode in ("RGBA", "LA", "P") else im.convert("RGB")
                cache[u] = im
        for u, pg, rk in pool[start:start + 8]:
            im = cache.get(u)
            if im is None or min(im.size) < 200 or u in used: continue
            key = ("w" if is_model else "i") + u
            if key not in cache: cache[key] = whole_sig(im) if is_model else item_sig(im, False)
            sc = match_score(target, cache[key])
            if sc > 0.90 and (best is None or sc > best[2] + 0.02 or (sc > best[2] - 0.02 and max(im.size) > max(best[1].size))):
                best = (u, im, sc)
        if best and best[2] > 0.95 and start >= 8: break
    if not best: return None
    # the same photo at a larger size from the CDN
    u, im, sc = best
    for v in bigger(u)[:-1]:
        if v in cache and cache[v] is None: continue
        data = fetch(v); big = open_any(data) if data else None; cache[v] = big
        if big is None: continue
        big = on_white(big) if big.mode in ("RGBA", "LA", "P") else big.convert("RGB")
        if max(big.size) <= max(im.size) * 1.05: continue
        if match_score(whole_sig(big), whole_sig(im)) > 0.93:
            u, im = v, big; break
    return u, im, sc, best[0]


def same_item(a, b, N=96):
    """Correlation of the two items (each cropped to its own box, on white, grey 96 x 96): a polished photo must show
    the very photo it replaces (pilot, 22 Nov 2026: a back view matched to the front of the same jacket scored 0.93-0.94,
    a different jacket 0.85; true matches 0.97 and up)."""
    def it(im):
        g = on_white(im).convert("L"); m = np.asarray(g) < 243
        ys, xs = np.where(m)
        if not len(ys): return None
        v = np.asarray(g.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1)).resize((N, N), Image.BILINEAR), dtype=np.float32).ravel()
        v = v - v.mean(); n = np.linalg.norm(v)
        return v / n if n > 1e-6 else None
    x, y = it(a), it(b)
    return -1.0 if x is None or y is None else float(np.dot(x, y))


SAME_MIN = 0.96


def polish_photo(name, live_im, kind, src):
    """(1600 photo, notes) for a product cut-out."""
    notes = {}
    cands = []
    if src:
        rgb = src[1]
        # the item region of the store photo, with margin (faster matting, same result)
        b = fg_box(rgb); pad = round(0.04 * max(rgb.size))
        b = (max(0, b[0] - pad), max(0, b[1] - pad), min(rgb.width, b[2] + pad), min(rgb.height, b[3] + pad))
        rgb = rgb.crop(b)
        bg = border_bg(np.asarray(src[1], dtype=np.float32))
        for model in ("birefnet-general", "isnet-general-use"):
            try:
                al = matte(rgb, model)
                al, cn = clean_alpha(al, rgb, bg)
                cands.append((edge_score(al, rgb), model, al, cn))
            except Exception as e:
                notes.setdefault("matte_err", []).append(f"{model}: {str(e)[:80]}")
        notes["source"] = "store"
    else:
        live = live_im.convert("RGBA")
        rgb = live.convert("RGB"); al0 = live.getchannel("A")
        a = np.asarray(al0)
        lowa = (a > 0) & (a < 64)
        bg = np.median(np.asarray(rgb, dtype=np.float32)[lowa], axis=0) if lowa.sum() > 50 else np.array([255.0, 255, 255])
        flat = on_white(live)
        al, cn = clean_alpha(al0, None, None)
        cands.append((edge_score(al, flat), "current", al, cn))
        try:
            al2 = matte(flat, "birefnet-general")
            # never larger than the live alpha (it was already cut): only a cleaner edge
            al2 = Image.fromarray(np.minimum(np.asarray(al2), np.asarray(al0)))
            al2, cn2 = clean_alpha(al2, None, None)
            # birefnet must agree with the live cut-out (it must not drop parts of the item)
            A, B = np.asarray(al) >= 128, np.asarray(al2) >= 128
            iou = (A & B).sum() / max(1, (A | B).sum())
            if iou > 0.97: cands.append((edge_score(al2, flat), "birefnet-general", al2, cn2))
            else: notes["birefnet_iou"] = round(float(iou), 3)
        except Exception as e:
            notes["matte_err"] = str(e)[:80]
        notes["source"] = "current"
    if not cands: return None, {"error": "matting failed", **notes}
    cands.sort(key=lambda c: -c[0])
    score, model, al, cn = cands[0]
    notes["matte"] = model; notes["edge"] = {c[1]: round(c[0], 1) for c in cands}
    if cn: notes["clean"] = cn
    b = alpha_box(al, 8)
    if not b: return None, {"error": "empty cut-out", **notes}
    # cut by the frame: more than 25% of a border is item -> a cropped photo, keep the live one
    m = np.asarray(al) >= 128
    if src and max(m[:2].mean(), m[-2:].mean(), m[:, :2].mean(), m[:, -2:].mean()) > 0.25:
        return None, {"error": "item cut off by the frame", **notes}
    rgb = decontaminate(rgb, al, bg)
    pad = 2
    b = (max(0, b[0] - pad), max(0, b[1] - pad), min(rgb.width, b[2] + pad), min(rgb.height, b[3] + pad))
    rgb, al = rgb.crop(b), al.crop(b)
    # the RGB outside the item must be white before enlarging (no dark rim pulled in by the filters)
    flat = Image.composite(rgb, Image.new("RGB", rgb.size, (255, 255, 255)), al)
    out = place(flat, al, kind, notes)
    return out, notes


def model_photo(live_im, src):
    """A model shot at a higher resolution, or None when the store has no larger copy."""
    if not src: return None, {"source": "current", "skip": "no larger store copy"}
    im = src[1]
    if max(im.size) < max(live_im.size) * 1.25: return None, {"source": "store", "skip": "store copy not larger"}
    im = im.copy(); im.thumbnail((SIZE, SIZE), Image.LANCZOS)
    return im, {"source": "store", "real_px": max(src[1].size)}


def do_find(p, names, entry, rec, a):
    kind = kind_of(p)
    pool = pool_for(p["id"], entry, rec)
    cache, used = {}, set()
    res = {"v": VERSION, "kind": kind, "photos": {}, "at": now()}
    for name in names:
        info = {}
        try:
            data = fetch(STORE + name, tries=3)
            live = open_any(data) if data else None
            if live is None: info["error"] = "live file did not download"; raise StopIteration
            is_model = bool(re.search(r"-d?m\d+\.webp$", name))
            src = find_source(live if is_model else live.convert("RGBA"), is_model, pool, cache, used)
            if src:   # one store image serves one live photo (two angles never become the same picture)
                used.update({src[0], src[3]})
                info.update(src_url=src[0], src_size=list(src[1].size), match=round(src[2], 3))
            if is_model:
                out, notes = model_photo(live, src)
            else:
                out, notes = polish_photo(name, live, kind, src)
                if out is not None and src:
                    same = same_item(live, out); notes["same"] = round(same, 3)
                    if same < SAME_MIN: out, notes = None, {"error": f"store copy is another photo ({same:.2f})"}
                if out is None and src:   # the store copy failed: the live file as source
                    info["store_fail"] = notes.get("error"); out, notes = polish_photo(name, live, kind, None)
                    for k in ("src_url", "src_size", "match"): info.pop(k, None)
            info.update(notes)
            if out is None: raise StopIteration
            buf = io.BytesIO(); out.save(buf, "WEBP", quality=90, method=6); data = buf.getvalue()
            os.makedirs(OUT, exist_ok=True)
            open(os.path.join(OUT, name), "wb").write(data)
            try:
                info["url"] = upload(name, data, a.dry)
            except Exception as e:
                info["upload_error"] = repr(e)[:120]
            info["kb"] = round(len(data) / 1024)
        except StopIteration:
            pass
        except Exception as e:
            info["error"] = repr(e)[:160]
        res["photos"][name] = info
        print(f"   {name}: {info.get('source', '?')} {('match %.2f %s' % (info['match'], 'x'.join(map(str, info['src_size'])))) if 'match' in info else ''}"
              f" real {info.get('real_px', '-')} -> {info.get('shown_px', '-')} {info.get('up', info.get('skip', ''))} {info.get('matte', '')}"
              f" {info.get('error', '') or info.get('upload_error', '')}", flush=True)
    # done unless something passing went wrong (a refused upload, a download); a photo that cannot be improved is done
    # too: the site keeps its live file for it
    retry = [n for n, v in res["photos"].items() if v.get("upload_error") or v.get("error") == "live file did not download"]
    res["done"] = not retry
    return res


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", default="")
    ap.add_argument("--limit", type=int, default=40)
    ap.add_argument("--offset", type=int, default=0)
    ap.add_argument("--shard", default="0/1")
    ap.add_argument("--redo", action="store_true")
    ap.add_argument("--dry", action="store_true", help="no upload (local test)")
    a = ap.parse_args(argv)
    shard = shards.parse(a.shard)
    items = load_catalog()[1]
    by = {p["id"]: p for p in items}
    live = live_photos(items)
    v = views()
    only = [x for x in a.ids.replace(" ", "").split(",") if x]
    order = only or sorted(live, key=lambda i: (-(v.get(i) or [0])[0], i))
    order = [i for i in order if i in live and shards.mine(i, shard)]
    done = {} if a.redo else load_done()
    todo = [i for i in order if i not in done][a.offset:a.offset + a.limit]
    print(f"polish: {len(order)} finds with store photos in this shard, {len(done)} done before, {len(todo)} now", flush=True)
    cands, log = load_cands(), load_log()
    sp = state_path(shard)
    st = load_json(sp, {"items": {}})
    st.setdefault("items", {})
    t0 = time.time()
    for n, i in enumerate(todo):
        p = by[i]
        print(f"[{n + 1}/{len(todo)}] {i} {p.get('title')} ({len(live[i])} photos, {kind_of(p)})", flush=True)
        r = do_find(p, live[i], cands.get(i), log.get(i), a)
        st["items"][i] = r; st["at"] = now()
        save_json(sp, st)
    ph = [x for i in todo for x in (st["items"].get(i) or {}).get("photos", {}).values()]
    print("summary: %d finds, %d photos: %d from a store copy (%d larger than before), %d Real-ESRGAN, %d skipped model shots, %d failed; %.0f s"
          % (len(todo), len(ph), sum(1 for x in ph if x.get("source") == "store"),
             sum(1 for x in ph if x.get("source") == "store" and max(x.get("src_size") or [0]) > 1200),
             sum(1 for x in ph if str(x.get("up", "")).startswith("Real-ESRGAN")), sum(1 for x in ph if x.get("skip")),
             sum(1 for x in ph if not x.get("url") and not x.get("skip")), time.time() - t0), flush=True)
    left = len([i for i in order if i not in load_done()])
    print(f"polish remaining {left}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
