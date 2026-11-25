# -*- coding: utf-8 -*-
"""Clean the light outline of the EXISTING transparent cut-outs for the dark tiles (owner, 25 Nov 2026: in dark mode the
tiles sit on #262626, where the old cut-outs show a light rim the light well hid).

For every visible find (not hidden: data/reported.json "hidden", data/report_overrides.json "hide") whose main photo is
a transparent cut-out of products/pc (the site's own copy img/m/pc, the same bytes), /img/rl or /img/fr:
  1. the ring of backdrop colour just inside the outline: how deep it runs is measured per photo (the share of each 1 px
     ring that is a light mix of the item colour behind it and a white / light grey backdrop); those pixels take the
     colour of the item just behind the ring. A light part of the item wider than the ring (a white tape, a metal rim),
     or a light edge in front of a textured part (rhinestones, chain links, knit) is left as it is.
  2. the soft edge outside it (alpha < 0.5) that is lighter than the item next to it takes the item's colour.
  Alpha, size and every pixel deeper inside are kept: the item itself does not change.
  Light fringe on #262626 (photo_white.halo: share of the outline more than 60 levels lighter, at 800 px) before and
  after, and flags for review of what only shows on a dark tile: a hanger hook above the item ("hook"), a light neutral
  base under it ("base": a pedestal, a stand, a kept backdrop patch).
  Also measured for review: "haze", the share of the item's inside that is light and only partly opaque (an item the
  old matte left half see-through, a white tee that fades out at the hem: fine on the light well, murky on #262626; no
  edge treatment can fix that, so those finds keep a light tile), and "frame" (thin light lines next to the item: the
  display frame of the football shirt photos, a rack bar).
data/photo_edge_fix.json "frames": finds checked by eye whose thin light lines (a display frame, a rack bar) come out of
  the matte before the edge is cleaned (remove_frames: only thin, long, light neutral pieces outside the item's body;
  the item is never touched). The record says so ("fix": "frames").
Writes img/edge/<id>.webp (RGBA WebP, the source's size) and data/photo_edge/<k>-of-<n>.json; nothing is uploaded and
the site does not change: photo_cut_upload.py --set edge puts the reviewed files in storage as NEW objects
(products/pc2/<id>-e1.webp), apply_catalog_ai.py --edge switches the photos.

  python scripts/photo_edge.py [--shard k/n] [--ids 1,2] [--max-minutes 0] [--targets]
"""
import argparse, glob, hashlib, io, json, os, re, sys, time
from datetime import datetime, timezone

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from catalog_common import ROOT, load_catalog, load_json, save_json  # noqa: E402

VERSION = 1
STATE = os.path.join(ROOT, "data", "photo_edge")
FIX = os.path.join(ROOT, "data", "photo_edge_fix.json")
OUT = os.path.join(ROOT, "img", "edge")
PC = re.compile(r"^https://uptpghuduqjqmrxwatbm\.supabase\.co/storage/v1/object/public/products/pc/([0-9]{1,15})\.webp(?:\?v=([A-Za-z0-9_-]{1,20}))?$")
LOCAL = re.compile(r"^/img/(rl|fr)/([0-9]{1,15})\.webp(?:\?v=[A-Za-z0-9_-]{1,20})?$")
TOL, TEX, MARGIN, W = 22, 32, 45.0, 250.0
DARK = (38, 38, 38)


def now(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def lum(x): return x[..., 0] * 0.299 + x[..., 1] * 0.587 + x[..., 2] * 0.114


def hidden_ids():
    h = set(map(str, (load_json(os.path.join(ROOT, "data", "reported.json"), {}) or {}).get("hidden") or []))
    ov = (load_json(os.path.join(ROOT, "data", "report_overrides.json"), {}) or {}).get("hide") or []
    return h | set(map(str, ov if isinstance(ov, list) else list(ov)))


def targets():
    """Visible finds whose photo is an existing transparent cut-out: (id, src, live url, local file or '')."""
    hid, out = hidden_ids(), []
    for p in load_catalog()[1]:
        i, u = str(p["id"]), p.get("img") or ""
        if i in hid: continue
        m = PC.match(u)
        if m:
            f = os.path.join("img", "m", "pc", m.group(1) + (".v" + m.group(2) if m.group(2) else "") + ".webp")
            out.append({"id": i, "src": "pc", "live": u, "path": f, "cat": p.get("cat")}); continue
        m = LOCAL.match(u)
        if m and m.group(2) == i:
            out.append({"id": i, "src": m.group(1), "live": u, "path": f"img/{m.group(1)}/{i}.webp", "cat": p.get("cat")})
    return out


def load_source(t):
    f = os.path.join(ROOT, t["path"])
    if os.path.isfile(f):
        im = Image.open(f); im.load(); return im, "file"
    if t["src"] != "pc": return None, "missing"
    import store_photos_polish as sp   # the stored photo itself (no site copy): Supabase, a few tries
    data = sp.fetch(t["live"].split("?")[0], timeout=60, tries=3)
    if not data: return None, "fetch failed"
    im = Image.open(io.BytesIO(data)); im.load(); return im, "supabase"


def edge_fix(im):
    """(fixed RGBA, info): see the module docstring. Alpha and size kept."""
    from scipy import ndimage
    im = im.convert("RGBA"); x = np.asarray(im, np.float32)
    rgb, a = x[..., :3], x[..., 3] / 255.0
    s = max(im.size) / 1200.0
    M = ndimage.binary_closing(a >= 0.5, iterations=2) | (a >= 0.5)      # the item; pin holes in the matte closed
    if M.sum() < 500: return None, {"skip": "no item in the matte"}
    d_in = ndimage.distance_transform_edt(M)
    L = lum(rgb); mn, mx = rgb.min(axis=2), rgb.max(axis=2)
    bglike = (mn >= 175) & (mx - mn <= 40)                              # a white / light grey backdrop colour

    def light_mixed(R):
        inner = (d_in > R) & (a >= 0.9)
        if not inner.any(): inner = M; R = 1
        di, (iy, ix) = ndimage.distance_transform_edt(~inner, return_indices=True)
        C_in = rgb[iy, ix]; Lin = lum(C_in)
        t = np.clip((L - Lin) / np.maximum(W - Lin, 1.0), 0, 1)
        mixed = np.abs(rgb - (t[..., None] * W + (1 - t[..., None]) * C_in)).max(axis=2) <= TOL
        behind = di <= (R + 1 - d_in) + 2.0          # the inner pixel straight in, not another part across a gap
        inn = inner.astype(np.float32)
        m1 = ndimage.uniform_filter(np.where(inner, L, 0), 7); m2 = ndimage.uniform_filter(np.where(inner, L * L, 0), 7)
        w = np.maximum(ndimage.uniform_filter(inn, 7), 1e-3)
        plain = np.sqrt(np.maximum(m2 / w - (m1 / w) ** 2, 0))[iy, ix] <= TEX
        return M & behind & (L > Lin + MARGIN) & ((mixed & plain) | bglike), C_in

    R = int(round(6 * s)) + 1
    lm, C_in = light_mixed(R)
    rim_w, f1 = 0, None
    for d in range(1, R):
        ring = M & (d_in > d - 1) & (d_in <= d)
        f = float(lm[ring].mean()) if ring.any() else 0.0
        if f1 is None: f1 = f
        if f >= 0.12 and f >= 0.4 * f1: rim_w = d
        else: break
    lm, C_in = light_mixed(max(rim_w, 1) + 1 + int(round(s)))
    out = rgb.copy()
    paint = lm & (d_in <= max(rim_w, max(1.0, s)))       # always the outermost ring; deeper where the photo has a ring
    out = np.where(paint[..., None], C_in, out)
    ds, (sy, sx) = ndimage.distance_transform_edt(~M, return_indices=True)
    C_s = out[sy, sx]
    soft = ~M & (a > 0) & (L > lum(C_s) + 15) & (ds <= 4 * s + 2)
    out = np.where(soft[..., None], C_s, out)
    out = np.where((a <= 0)[..., None], C_s, out)        # clear pixels: the item's colour, so resizing pulls in no white
    res = np.concatenate([np.clip(out, 0, 255), x[..., 3:4]], axis=2).round().astype(np.uint8)
    info = {"rim_w": rim_w, "rim_f1": round(f1 or 0, 3), "rim_px": int(paint.sum()), "soft_px": int(soft.sum()),
            "rim_share": round(float(paint.sum() / max(1, (M & (d_in <= 1)).sum())), 3)}
    return Image.fromarray(res, "RGBA"), info


def halo(rgba, margin=60.0, side=800):
    """photo_white.halo: the share of the outline that shows a light fringe on #262626 (more than `margin` levels
    lighter than the item just inside and the tile), at 800 px."""
    from scipy import ndimage
    im = rgba.convert("RGBA")
    if max(im.size) != side:
        k = side / max(im.size); im = im.resize((max(1, round(im.width * k)), max(1, round(im.height * k))), Image.LANCZOS)
    x = np.asarray(im, dtype=np.float32); a = x[..., 3] / 255.0
    c = x[..., :3] * a[..., None] + np.asarray(DARK, np.float32) * (1 - a[..., None])
    L = lum(c)
    solid = a >= 0.96
    if solid.sum() < 500: return None
    inner = ndimage.binary_erosion(solid, iterations=3)
    band = ((a > 0.04) & (a < 0.96)) | (solid & ~ndimage.binary_erosion(solid, iterations=2))
    w = ndimage.uniform_filter(inner.astype(np.float32), 13); s = ndimage.uniform_filter(np.where(inner, L, 0), 13)
    L_in = np.where(w > 0.02, s / np.maximum(w, 1e-6), np.nan)
    light = band & np.isfinite(L_in) & (L > np.fmax(L_in, 38.0) + margin)
    perim = solid & ~ndimage.binary_erosion(solid)
    return round(float((ndimage.binary_dilation(light, iterations=2) & perim).sum() / max(1, perim.sum())), 4)


def flags(rgba):
    """What only a dark tile shows, for review: a hanger hook above the item, a light neutral base under it."""
    from scipy import ndimage
    import clean_photos as cp
    out = []
    im = rgba.convert("RGBA"); k = 300 / max(im.size)
    sm = im.resize((max(1, round(im.width * k)), max(1, round(im.height * k))), Image.BILINEAR)
    al = sm.getchannel("A").point(lambda v: 255 if v >= 128 else 0)
    if cp._hook_rows(al): out.append("hook")
    x = np.asarray(sm, np.float32); M = x[..., 3] >= 128
    if M.sum() > 200:
        ys = np.nonzero(M.any(axis=1))[0]; top, bot = ys[0], ys[-1]
        mn, mx = x[..., :3].min(axis=2), x[..., :3].max(axis=2)
        light = M & (mn >= 205) & (mx - mn <= 18)
        lab, n = ndimage.label(light)
        if n:
            area = ndimage.sum(light, lab, range(1, n + 1))
            low = ndimage.maximum(np.arange(M.shape[0])[:, None] * np.ones_like(M), lab, range(1, n + 1))
            for j in range(n):
                if low[j] >= bot - 1 and area[j] >= 0.03 * M.sum() and light.sum() < 0.5 * M.sum():
                    out.append("base"); break
    return out


def disk(r):
    y, x = np.ogrid[-r:r + 1, -r:r + 1]
    return x * x + y * y <= r * r


def remove_frames(im, min_ext=0.08, min_elong=2.5):
    """(RGBA, info): thin, long, light neutral pieces outside the item's body cleared from the matte (a display frame, a
    rack bar). The body is the matte opened by 1.2% of the photo; nothing within a pixel of it changes. Used only for
    finds checked by eye (data/photo_edge_fix.json "frames")."""
    from scipy import ndimage
    im = im.convert("RGBA"); x = np.asarray(im, np.float32)
    rgb, a = x[..., :3], x[..., 3] / 255.0
    side = max(im.size); s = side / 1200.0
    M = a >= 0.5
    if M.sum() < 500: return im, {"frame_px": 0}
    body = ndimage.binary_opening(M, structure=disk(max(3, int(round(0.012 * side)))))
    lab, n = ndimage.label(body)
    if n:
        areas = ndimage.sum(body, lab, range(1, n + 1))
        body = np.isin(lab, [j + 1 for j in range(n) if areas[j] >= 0.02 * areas.max()])
    thin = M & ~ndimage.binary_dilation(body, iterations=1)
    mn, mx = rgb.min(axis=2), rgb.max(axis=2)
    lab, n = ndimage.label(thin & (mn >= 120) & (mx - mn <= 40), structure=np.ones((3, 3)))
    rm = np.zeros(M.shape, bool); pieces = 0
    objs = ndimage.find_objects(lab)
    for j, sl in enumerate(objs):
        c = lab[sl] == j + 1
        ext = max(sl[0].stop - sl[0].start, sl[1].stop - sl[1].start)
        if ext >= min_ext * side and ext / np.sqrt(max(int(c.sum()), 1)) >= min_elong:
            rm[sl] |= c; pieces += 1
    if not rm.any(): return im, {"frame_px": 0}
    near = ndimage.binary_dilation(rm, iterations=max(4, int(round(0.03 * side))))   # shorter pieces of the same frame
    for j, sl in enumerate(objs):
        c = lab[sl] == j + 1
        if rm[sl][c].any() or int(c.sum()) < 0.00004 * side * side: continue
        if near[sl][c].any(): rm[sl] |= c; pieces += 1
    clear = ndimage.binary_dilation(rm, iterations=2 + int(round(s))) & ~ndimage.binary_dilation(body, iterations=1)
    clear |= ndimage.binary_dilation(rm, iterations=4 + 2 * int(round(s))) & \
        ~ndimage.binary_dilation(body, iterations=2 + int(round(s)))
    na = np.where(clear, 0.0, a)
    out = np.concatenate([rgb, (na * 255)[..., None]], axis=2).round().astype(np.uint8)
    return Image.fromarray(out, "RGBA"), {"frame_px": int(clear.sum()), "frame_pieces": pieces}


def dark_measures(rgba, S=600):
    """haze: the share of the item's inside (6 px in from the filled outline, at 600 px) that is light and only partly
    opaque; frame: pixels of thin, long, light neutral pieces next to the item's body."""
    from scipy import ndimage
    im = rgba.convert("RGBA"); k = S / max(im.size)
    im = im.resize((max(1, round(im.width * k)), max(1, round(im.height * k))), Image.BILINEAR)
    x = np.asarray(im, np.float32); a = x[..., 3] / 255.0; rgb = x[..., :3]
    L = lum(rgb)
    inside = ndimage.binary_erosion(ndimage.binary_fill_holes(a > 0.08), iterations=6)
    haze = float((inside & (a > 0.08) & (a < 0.85) & (L > 150)).sum() / max(1, inside.sum()))
    M = a >= 0.5
    thin = M & ~ndimage.binary_dilation(ndimage.binary_opening(M, structure=disk(7)), iterations=1)
    mn, mx = rgb.min(axis=2), rgb.max(axis=2)
    cand = ndimage.binary_closing(thin & (mn >= 110) & (mx - mn <= 45), iterations=1) & thin
    lab, nc = ndimage.label(cand, structure=np.ones((3, 3)))
    frame = 0
    for j, sl in enumerate(ndimage.find_objects(lab)):
        h, w = sl[0].stop - sl[0].start, sl[1].stop - sl[1].start
        area = int((lab[sl] == j + 1).sum())
        if max(h, w) >= 0.08 * S and area >= 30 and max(h, w) / np.sqrt(area) >= 2.5: frame += area
    return round(haze, 4), frame


def state_file(k, n): return os.path.join(STATE, f"{k}-of-{n}.json")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--shard", default="0/1"); ap.add_argument("--ids", default="")
    ap.add_argument("--max-minutes", type=float, default=0); ap.add_argument("--targets", action="store_true")
    a = ap.parse_args(argv)
    k, n = map(int, a.shard.split("/"))
    if not (n >= 1 and 0 <= k < n): raise SystemExit("bad shard")
    ts = targets()
    if a.targets:
        import collections
        print(len(ts), dict(collections.Counter(t["src"] for t in ts))); return
    only = {x for x in a.ids.replace(" ", "").split(",") if x}
    mine = [t for t in ts if (int(hashlib.sha1(t["id"].encode()).hexdigest(), 16) % n == k) and (not only or t["id"] in only)]
    os.makedirs(OUT, exist_ok=True); os.makedirs(STATE, exist_ok=True)
    sf = state_file(k, n); st = load_json(sf, {}) or {}; items = st.get("items") or {}
    frames = set(map(str, ((load_json(FIX, {}) or {}).get("frames") or {})))
    t0 = time.time(); done = bad = 0
    print(f"shard {k}/{n}: {len(mine)} photos", flush=True)
    for t in mine:
        if a.max_minutes and time.time() - t0 > a.max_minutes * 60: print("time is up", flush=True); break
        r = items.get(t["id"]) or {}
        fix = "frames" if t["id"] in frames else ""
        if r.get("v") == VERSION and r.get("live") == t["live"] and (r.get("ok") or r.get("why")) \
                and (r.get("fix") or "") == fix: continue
        rec = {"v": VERSION, "id": t["id"], "src": t["src"], "live": t["live"], "cat": t.get("cat"), "at": now(),
               "run": os.environ.get("GITHUB_RUN_ID", ""), "ok": False}
        try:
            im, how = load_source(t)
            if im is None: rec["why"] = "no source photo (%s)" % how
            elif "A" not in im.getbands(): rec["why"] = "the photo has no transparency"
            else:
                rgba = im.convert("RGBA")
                src = rgba
                if fix == "frames":
                    src, finfo = remove_frames(rgba); rec.update(finfo); rec["fix"] = "frames"
                fx, info = edge_fix(src)
                rec.update(info); rec["source"] = how; rec["size"] = list(rgba.size)
                if fx is None: rec["why"] = info.get("skip")
                else:
                    rec["halo0"], rec["halo1"] = halo(rgba), halo(fx)
                    rec["flags"] = flags(fx)
                    rec["haze"], rec["frame"] = dark_measures(fx)
                    f = os.path.join(OUT, t["id"] + ".webp")
                    fx.save(f, "WEBP", quality=92, method=5)
                    data = open(f, "rb").read()
                    rec.update(ok=True, file=f"img/edge/{t['id']}.webp", object=f"products/pc2/{t['id']}-e1.webp",
                               kb=len(data) // 1024, sha1=hashlib.sha1(data).hexdigest())
        except Exception as e:  # noqa: BLE001
            rec["why"] = "error: %s" % str(e)[:200]
        items[t["id"]] = rec
        if rec["ok"]: done += 1
        else: bad += 1
        if (done + bad) % 100 == 0:
            save_json(sf, {"at": now(), "items": items}); print(f"  {done + bad} ({done} ok, {bad} not) {time.time() - t0:.0f} s", flush=True)
    save_json(sf, {"at": now(), "items": items})
    print(f"summary: {done + bad} photos, {done} done, {bad} not; {time.time() - t0:.0f} s", flush=True)


if __name__ == "__main__":
    main()
