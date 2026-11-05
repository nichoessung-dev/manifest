# -*- coding: utf-8 -*-
"""Clean product shots, RepLibrary style: the item alone, centred on the site card colour, same size every time, a soft shadow.

Deterministic only: no image model draws anything, so the item's shape, logo, colour and text stay exactly as in the
seller photo. Per find:
  1. download the current photo (most are already transparent cut-outs, 1200x1200 RGBA)
  2. mask: the photo's own transparency; photos without one (or with --recut) go through rembg
     (birefnet-general / isnet-general-use; only installed in the GitHub workflow)
  3. tidy the mask: drop loose specks, trim a hanger hook / rack pole sticking out of the top of a garment,
     optionally keep only the main view when the vision labels say the photo shows extra views (--keep-main-view)
  4. quality gate: skip (and log) masks that look wrong: too small / too big, many separate pieces, hazy, no cut-out
  4b. small photos (short side under 900 px): enlarged with Real-ESRGAN (scripts/restore.py) behind a shrink-back
     judge, or Lanczos when the model is missing or the judge says no
  5. compose: crop to the item, scale so its long side is --fill of the canvas, centre, soft contact shadow,
     on #f2f5fa (the site's photo card; --bg ffffff for white), 1200x1200 WebP
  6. fidelity check: the item pixels in the result must match the original (mean difference under a few levels)
Uploads to Supabase storage products/pc2/<id>.webp (default; needs SUPABASE_SERVICE_KEY) or writes img/p2/<id>.webp with --store git, records each
result in data/catalog_ai.json under "photos", and saves before/after contact sheets to --sheets for review.
The original photos are never touched; the site switch is reversible (see PLAN.md).

  python scripts/clean_photos.py [--ids 1,2 | --ids-file f | --from-labels not_clean|all] [--limit 50]
                                 [--store supabase|git|none] [--bg f2f5fa] [--fill 0.84] [--recut] [--rembg-model isnet-general-use]
                                 [--keep-main-view] [--sheets photo-sheets] [--dry-run] [--redo]
"""
import argparse, io, json, os, random, sys, time, urllib.request
from datetime import datetime, timezone
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from catalog_common import ROOT, UA, load_catalog, img_url, fetch, load_json, save_json  # noqa: E402
from photo_metrics import mask_stats  # noqa: E402

SIZE = 1200
SUPA = "https://uptpghuduqjqmrxwatbm.supabase.co"
GARMENT = {"Tops", "Outerwear"}            # hanger trimming only for these (hangers sit above the collar)
_rembg = {}


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def rembg_mask(im, model):
    """Alpha mask from rembg (workflow only). Raises when rembg is not installed."""
    from rembg import new_session, remove
    if model not in _rembg:
        _rembg[model] = new_session(model)
    rgb = im.convert("RGB")
    m = remove(rgb, session=_rembg[model], only_mask=True, post_process_mask=True)
    return m.convert("L")


def get_mask(im, a):
    if "A" in im.getbands() and not a.recut:
        al = im.getchannel("A")
        if al.getextrema()[0] < 250:
            return al, "alpha"
    on_white = Image.new("RGBA", im.size, (255, 255, 255, 255))
    on_white.alpha_composite(im.convert("RGBA"))
    return rembg_mask(on_white, a.rembg_model), "rembg:" + a.rembg_model


def label(mask):
    """4-neighbour component labels of a binary 'L' mask: (labels list, areas list, boxes list); label 0 = background."""
    w, h = mask.size
    px = list(mask.getdata())
    lab = [0] * (w * h)
    areas, boxes = [0], [None]
    for start in range(w * h):
        if px[start] < 128 or lab[start]:
            continue
        n_ = len(areas); lab[start] = n_; stack = [start]; area = 0
        x0, y0, x1, y1 = w, h, 0, 0
        while stack:
            k = stack.pop(); area += 1; x, y = k % w, k // w
            x0, y0, x1, y1 = min(x0, x), min(y0, y), max(x1, x), max(y1, y)
            for n in (k - 1 if x > 0 else -1, k + 1 if x < w - 1 else -1, k - w, k + w):
                if 0 <= n < w * h and not lab[n] and px[n] >= 128:
                    lab[n] = n_; stack.append(n)
        areas.append(area); boxes.append((x0, y0, x1 + 1, y1 + 1))
    return lab, areas, boxes


def upscale(im, alpha, a):
    """Small photos (short side under --upscale-below): enlarge to 1200 px on the long side. Real-ESRGAN (scripts/restore.py,
    the general x4v3 model the Finds job uses; it sharpens what is there and draws nothing new) when its model files
    are present, else Lanczos. Judge: the enlarged photo shrunk back must match the original (mean difference on the
    item under 6 of 255), otherwise the plain Lanczos result is used. Returns (im RGBA, alpha, note)."""
    w, h = im.size
    if min(w, h) >= a.upscale_below:
        return im, alpha, ""
    s = SIZE / max(w, h)
    nw, nh = round(w * s), round(h * s)
    lanczos = im.convert("RGBA").resize((nw, nh), Image.LANCZOS)
    big_a = alpha.resize((nw, nh), Image.LANCZOS)
    try:
        sys.path.insert(0, os.path.join(ROOT, "scripts"))
        from restore import restore, _load
        if _load() is None:
            raise RuntimeError("Real-ESRGAN model not installed")
        sr = restore(im.convert("RGB"), nw, nh).resize((nw, nh), Image.LANCZOS)
        back = sr.resize((w, h), Image.LANCZOS)
        solid = alpha.point(lambda v: 255 if v >= 250 else 0)
        diff = ImageChops.multiply(ImageChops.difference(back, im.convert("RGB")).convert("L"), solid).histogram()
        mad = sum(i * c for i, c in enumerate(diff)) / max(1, solid.histogram()[255])
        if mad > 6.0:
            out = lanczos; note = "upscaled (Lanczos; Real-ESRGAN rejected, diff %.1f)" % mad
        else:
            out = sr.convert("RGBA"); note = "upscaled (Real-ESRGAN, diff %.1f)" % mad
    except Exception as e:
        out = lanczos; note = "upscaled (Lanczos: %s)" % str(e)[:40]
    out.putalpha(big_a)
    return out, big_a, note


def tidy(alpha, cat, keep_main):
    """Remove specks (and, for garments, a thin hook above the collar). Returns (alpha, notes)."""
    notes = []
    w, h = alpha.size
    sc = 300 / max(w, h)
    sm = alpha.resize((max(1, round(w * sc)), max(1, round(h * sc))), Image.BILINEAR).point(lambda v: 255 if v >= 128 else 0)
    lab, areas, boxes = label(sm)
    if len(areas) < 2:
        return alpha, ["empty"]
    big = max(areas[1:])
    # a piece stays when it is a real part of the find (2%+ of the main piece); with keep_main only pieces of 60%+ stay
    # (two shoes of a pair, two halves of a set), so a small inset view or a box drops out
    floor = 0.6 if keep_main else 0.02
    keep_ids = {i for i in range(1, len(areas)) if areas[i] >= floor * big}
    # a small piece INSIDE or right next to the main item is part of it (a logo whose white surround was cut away):
    # keep it. Only pieces out on their own (hanger bits, rack poles, dust) are dropped.
    m = round(0.015 * max(sm.size))
    xs = [boxes[i] for i in keep_ids]
    mb = (min(b[0] for b in xs) - m, min(b[1] for b in xs) - m, max(b[2] for b in xs) + m, max(b[3] for b in xs) + m)
    if not keep_main:
        for i in range(1, len(areas)):
            b = boxes[i]
            if i not in keep_ids and b[0] >= mb[0] and b[1] >= mb[1] and b[2] <= mb[2] and b[3] <= mb[3]:
                keep_ids.add(i)
    dropped = len(areas) - 1 - len(keep_ids)
    keep = Image.frombytes("L", sm.size, bytes(255 if l in keep_ids else 0 for l in lab))
    if dropped:
        lost = sum(areas[i] for i in range(1, len(areas)) if i not in keep_ids) / big
        notes.append("dropped %d loose piece(s)" % dropped)
        if not keep_main and (dropped > 4 or lost > 0.01):
            notes.append("DAMAGED: %d pieces, %.1f%% of the item cut loose" % (dropped, 100 * lost))
    if cat in GARMENT:
        cut = _hook_rows(keep)
        if cut:
            ImageDraw.Draw(keep).rectangle((0, 0, keep.width, cut - 1), fill=0)
            notes.append("trimmed hook at top")
        flip = keep.transpose(Image.FLIP_TOP_BOTTOM)          # a rack pole can stick out under the hem too
        cut = _hook_rows(flip, thin=0.05, longest=0.6)
        if cut:
            ImageDraw.Draw(keep).rectangle((0, keep.height - cut, keep.width, keep.height), fill=0)
            notes.append("trimmed pole at bottom")
    # back to full size: keep the original soft edge, only zero the removed areas
    gate = keep.filter(ImageFilter.MaxFilter(5)).resize(alpha.size, Image.BILINEAR).point(lambda v: 255 if v >= 64 else 0)
    return ImageChops.multiply(alpha, gate), notes


def _hook_rows(m, thin=0.07, longest=0.15):
    """Rows to cut at the top: a thin part (< thin x the item's widest row) above the body, at most longest x its height."""
    box = m.getbbox()
    if not box:
        return 0
    w = m.width
    px = m.load()
    ext = []
    for y in range(box[1], box[3]):
        xs = [x for x in range(box[0], box[2]) if px[x, y]]
        ext.append((xs[-1] - xs[0] + 1) if xs else 0)
    widest = max(ext) or 1
    hgt = box[3] - box[1]
    k = 0
    while k < len(ext) and ext[k] < thin * widest:
        k += 1
    if 0.015 * hgt <= k <= longest * hgt:
        return box[1] + k
    return 0


def gate(alpha, a):
    st = mask_stats(alpha)
    bad = []
    if st["cover"] < 0.03: bad.append("item too small / mask nearly empty")
    if st["solidity"] > 0.97 and st["fill"] > 0.97: bad.append("no background removed")
    if st["parts"] > a.max_parts: bad.append("%d separate pieces" % st["parts"])
    if st["largest_share"] < 0.55 and st["parts"] > 1: bad.append("main piece only %.0f%%" % (100 * st["largest_share"]))
    if st["soft"] > 0.22: bad.append("hazy mask (%.0f%% half-transparent)" % (100 * st["soft"]))
    return bad, st


def compose(im, alpha, a):
    rgba = im.convert("RGBA"); rgba.putalpha(alpha)
    box = alpha.point(lambda v: 255 if v >= 24 else 0).getbbox()
    item = rgba.crop(box)
    target = SIZE * a.fill
    s = target / max(item.size)
    nw, nh = max(1, round(item.width * s)), max(1, round(item.height * s))
    item = item.resize((nw, nh), Image.LANCZOS)
    bg = tuple(int(a.bg[i:i + 2], 16) for i in (0, 2, 4))
    canvas = Image.new("RGBA", (SIZE, SIZE), bg + (255,))
    x = (SIZE - nw) // 2
    y = (SIZE - nh) // 2
    if a.shadow:
        ia = item.getchannel("A")
        # contact shadow: the item's footprint squashed into a thin ellipse under it, blurred
        sh_h = max(6, round(nh * 0.06))
        foot = Image.new("L", (nw, sh_h * 3), 0)
        ImageDraw.Draw(foot).ellipse((round(nw * 0.08), sh_h, round(nw * 0.92), sh_h * 2), fill=255)
        foot = foot.filter(ImageFilter.GaussianBlur(sh_h * 0.9))
        layer = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
        dark = Image.new("RGBA", foot.size, (20, 24, 32, 0)); dark.putalpha(foot.point(lambda v: round(v * a.shadow)))
        layer.alpha_composite(dark, (x, min(SIZE - foot.height, y + nh - round(sh_h * 1.6))))
        # and a very faint drop shadow of the item itself
        soft = ia.filter(ImageFilter.GaussianBlur(14)).point(lambda v: round(v * a.shadow * 0.45))
        d2 = Image.new("RGBA", item.size, (20, 24, 32, 0)); d2.putalpha(soft)
        layer.alpha_composite(d2, (x, min(SIZE - nh, y + 10)))
        canvas.alpha_composite(layer)
    canvas.alpha_composite(item, (x, y))
    return canvas.convert("RGB"), (x, y, nw, nh), item


def fidelity(item, out, xy):
    """Mean absolute difference between the item's own opaque pixels and the same pixels in the result (0 = identical)."""
    x, y, nw, nh = xy
    region = out.crop((x, y, x + nw, y + nh))
    solid = item.getchannel("A").point(lambda v: 255 if v >= 250 else 0)
    if not solid.getbbox():
        return 0.0
    diff = ImageChops.difference(region, item.convert("RGB")).convert("L")
    h = ImageChops.multiply(diff, solid).histogram()
    n = solid.histogram()[255] or 1
    return sum(i * c for i, c in enumerate(h)) / n


def upload_supabase(name, data):
    req = urllib.request.Request(SUPA + "/storage/v1/object/products/pc2/" + name, data=data, method="POST",
                                 headers={**UA, "Authorization": "Bearer " + os.environ["SUPABASE_SERVICE_KEY"],
                                          "apikey": os.environ["SUPABASE_SERVICE_KEY"], "Content-Type": "image/webp",
                                          "x-upsert": "true", "Cache-Control": "max-age=31536000"})
    urllib.request.urlopen(req, timeout=60).read()


def sheet(pairs, path, bg_before=(242, 245, 250)):
    """pairs: (id, before RGBA/RGB, after RGB or None, label). 3 pairs per row, 280 px tiles."""
    T, cols = 280, 3
    rows = (len(pairs) + cols - 1) // cols
    sh = Image.new("RGB", (cols * (2 * T + 24), rows * (T + 34)), (255, 255, 255))
    d = ImageDraw.Draw(sh)
    for k, (pid, before, after, label) in enumerate(pairs):
        cx, cy = (k % cols) * (2 * T + 24), (k // cols) * (T + 34)
        b = Image.new("RGBA", before.size, bg_before + (255,)); b.alpha_composite(before.convert("RGBA")); b = b.convert("RGB")
        b.thumbnail((T, T)); sh.paste(b, (cx + 4, cy + 4))
        if after is not None:
            af = after.copy(); af.thumbnail((T, T)); sh.paste(af, (cx + T + 8, cy + 4))
            d.rectangle((cx + T + 8, cy + 4, cx + 2 * T + 8, cy + T + 4), outline=(210, 214, 222))
        else:
            d.rectangle((cx + T + 8, cy + 4, cx + 2 * T + 8, cy + T + 4), fill=(255, 236, 236))
        d.text((cx + 6, cy + T + 8), pid, fill=(0, 0, 0))
        d.text((cx + 6, cy + T + 20), label[:90], fill=(170, 20, 20) if after is None else (60, 60, 60))
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    sh.save(path, quality=86)


def select(items, store, a):
    labels = store.get("items", {})
    photos = store.get("photos", {})
    if a.ids or a.ids_file:
        want = set(a.ids.replace(" ", "").split(",")) - {""}
        if a.ids_file: want |= set(open(a.ids_file).read().split())
        pool = [p for p in items if p["id"] in want]
    elif a.from_labels == "not_clean":
        pool = [p for p in items if labels.get(p["id"]) and not labels[p["id"]].get("error") and not labels[p["id"]].get("is_clean_product_photo")]
    elif a.from_labels == "random":
        pool = random.Random(a.seed).sample(items, min(len(items), max(a.limit, 1) * 3))
    else:
        pool = list(items)
    out = []
    for p in pool:
        if not a.redo and p["id"] in photos and photos[p["id"]].get("status") in ("ok", "skipped"):
            continue
        out.append(p)
        if a.limit and len(out) >= a.limit: break
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", default=os.path.join(ROOT, "index.html"))
    ap.add_argument("--labels", default=os.path.join(ROOT, "data", "catalog_ai.json"))
    ap.add_argument("--ids", default="")
    ap.add_argument("--ids-file", default="")
    ap.add_argument("--from-labels", default="all", choices=["all", "not_clean", "random"])
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--store", default="supabase", choices=["supabase", "git", "none"])
    ap.add_argument("--outdir", default=os.path.join(ROOT, "img", "p2"))
    ap.add_argument("--bg", default="f2f5fa", help="background hex; f2f5fa = the site's photo card")
    ap.add_argument("--fill", type=float, default=0.84)
    ap.add_argument("--shadow", type=float, default=0.16, help="shadow strength 0..1 (0 = none)")
    ap.add_argument("--recut", action="store_true", help="run rembg even when the photo already has transparency")
    ap.add_argument("--rembg-model", default="isnet-general-use")
    ap.add_argument("--keep-main-view", action="store_true", help="drop extra views when the labels say multiple_views / collage")
    ap.add_argument("--max-parts", type=int, default=3)
    ap.add_argument("--upscale-below", type=int, default=900, help="enlarge photos whose short side is under this (px)")
    ap.add_argument("--quality", type=int, default=84)
    ap.add_argument("--sheets", default=os.path.join(ROOT, "photo-sheets"))
    ap.add_argument("--dry-run", action="store_true", help="process and make sheets, but write no images and no records")
    ap.add_argument("--redo", action="store_true")
    ap.add_argument("--max-minutes", type=float, default=0)
    a = ap.parse_args()

    _, items, _, _ = load_catalog(a.index)
    store = load_json(a.labels, {})
    store.setdefault("photos", {})
    labels = store.get("items", {})
    todo = select(items, store, a)
    print("photos to do: %d (store %s, bg #%s, fill %.2f%s)" % (len(todo), a.store, a.bg, a.fill, ", dry run" if a.dry_run else ""))
    if a.store == "supabase" and not a.dry_run and not os.environ.get("SUPABASE_SERVICE_KEY"):
        sys.exit("SUPABASE_SERVICE_KEY is not set")
    pairs, n_ok, n_skip, n_err, n_sheet = [], 0, 0, 0, 0
    t0 = time.time()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    for k, p in enumerate(todo):
        if a.max_minutes and time.time() - t0 > a.max_minutes * 60:
            print("time limit reached; the rest waits for the next run"); break
        pid = p["id"]
        rec = {"date": now(), "src": img_url(p)}
        try:
            im = ImageOps.exif_transpose(Image.open(io.BytesIO(fetch(img_url(p)))))
            im.load()
            alpha, how = get_mask(im, a)
            lab = labels.get(pid) or {}
            multi = bool(set(lab.get("photo_issues") or []) & {"multiple_views", "collage_or_grid"}) or lab.get("is_collage")
            keep_main = a.keep_main_view and multi and not lab.get("is_set")
            alpha, notes = tidy(alpha, p.get("cat"), keep_main)
            im, alpha, up = upscale(im, alpha, a)
            if up: notes.append(up)
            bad, st = gate(alpha, a)
            bad += [n[9:] for n in notes if n.startswith("DAMAGED: ")]       # a broken old cut-out: needs a new photo
            rec.update({"mask": how, "notes": notes, "stats": st})
            if bad:
                rec.update({"status": "skipped", "why": bad}); n_skip += 1
                pairs.append((pid, im, None, "SKIP: " + "; ".join(bad)))
                print("  %s skipped: %s" % (pid, "; ".join(bad)))
            else:
                out, xy, item = compose(im, alpha, a)
                fd = fidelity(item, out, xy)
                if fd > 4.0:
                    rec.update({"status": "skipped", "why": ["fidelity %.1f" % fd]}); n_skip += 1
                    pairs.append((pid, im, None, "SKIP: fidelity %.1f" % fd))
                else:
                    buf = io.BytesIO(); out.save(buf, "WEBP", quality=a.quality, method=6); data = buf.getvalue()
                    v = int((store["photos"].get(pid) or {}).get("v") or 0) + 1
                    if not a.dry_run:
                        if a.store == "git":
                            os.makedirs(a.outdir, exist_ok=True)
                            open(os.path.join(a.outdir, pid + ".webp"), "wb").write(data)
                        elif a.store == "supabase":
                            upload_supabase(pid + ".webp", data)
                    rec.update({"status": "ok", "v": v, "store": a.store, "kb": len(data) // 1024, "fidelity": round(fd, 2)})
                    n_ok += 1
                    pairs.append((pid, im, out, "%s %s %dKB" % (how, "; ".join(notes), len(data) // 1024)))
        except Exception as e:
            rec.update({"status": "error", "why": [str(e)[:160]]}); n_err += 1
            print("  %s error: %s" % (pid, str(e)[:160]))
        if not a.dry_run:
            store["photos"][pid] = rec
            if (k + 1) % 20 == 0:
                save_json(a.labels, store)
        if len(pairs) == 24:
            n_sheet += 1; sheet(pairs, os.path.join(a.sheets, "sheet-%s-%03d.jpg" % (stamp, n_sheet))); pairs = []
    if pairs:
        n_sheet += 1; sheet(pairs, os.path.join(a.sheets, "sheet-%s-%03d.jpg" % (stamp, n_sheet)))
    if not a.dry_run:
        save_json(a.labels, store)
    print("done: %d cleaned, %d skipped, %d errors in %.0f s; sheets in %s" % (n_ok, n_skip, n_err, time.time() - t0, a.sheets))


if __name__ == "__main__":
    main()
