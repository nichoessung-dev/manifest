#!/usr/bin/env python3
"""Turn the RepLibrary photos that sit on a white square (img/rl/<id>.webp) into transparent cut-outs, in place.

Uses clean_photos.py's own pipeline, imported, not copied: rembg mask (get_mask), mask tidy (tidy), quality gate
(gate), compose with a transparent background and the soft shadow in the alpha (compose, --bg none) and the fidelity
check. Differences, on purpose:
  - no upscaling: clean_photos' Real-ESRGAN / Lanczos step is not called, and the canvas is the photo's own size
    (at most 1600 px), with the item never scaled up (it keeps its size when it fills less than --fill)
  - it reads and writes img/rl/<id>.webp only, so the catalogue's "img" stays the same and index.html is not edited
  - records go to data/rl_cutout.json, never data/catalog_ai.json (apply_catalog_ai.py --photos reads that one)
Per photo the result is one of:
  already  the photo already has real transparency: untouched
  ok       cut out and written back
  kept     the mask looked wrong (gate, loose pieces, fidelity, item at the photo edge, labels say person / hand /
           box / collage): the original stays, the reason is logged
  failed   an error (retried on the next run)
Only photos that exist when the run starts are handled; finds the import adds later are picked up by a later run.

  python scripts/rl_cutout.py [--limit 20] [--max-minutes 40] [--ids 1,2] [--sheets out/rl-cutout-sheets] [--dry-run]
"""
import argparse, io, json, os, re, sys, time
from datetime import datetime, timezone
from PIL import Image, ImageDraw, ImageOps

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import clean_photos as cp  # noqa: E402
from catalog_common import ROOT, load_json, save_json  # noqa: E402

IMG = os.path.join(ROOT, "img", "rl")
LOG = os.path.join(ROOT, "data", "rl_cutout.json")
MAX_SIDE = 1600
DONE = ("ok", "kept", "already")
NEEDS_NEW_PHOTO = {"worn_by_person", "collage_or_grid", "packaging_or_box", "hand_in_photo"}


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def has_cutout(im):
    """Real transparency: at least 3% of the pixels are clear (an RGBA file that is opaque everywhere does not count)."""
    if "A" not in im.getbands():
        return False
    h = im.getchannel("A").histogram()
    return sum(h[:128]) >= 0.03 * im.width * im.height


def border_plain(im, tol=18):
    """Share of the outer 2% frame that is close to white: a cheap 'studio shot on white' test. Lifestyle photos
    (worn by a person, on a table, a hand) have busy borders; those stay as they are."""
    rgb = im.convert("RGB")
    w, h = rgb.size
    b = max(2, round(0.02 * min(w, h)))
    px = rgb.load()
    n = hit = 0
    step = max(1, min(w, h) // 300)
    for x in range(0, w, step):
        for y in list(range(0, b)) + list(range(h - b, h)):
            r, g, bl = px[x, y]; n += 1; hit += (r > 255 - tol and g > 255 - tol and bl > 255 - tol)
    for y in range(0, h, step):
        for x in list(range(0, b)) + list(range(w - b, w)):
            r, g, bl = px[x, y]; n += 1; hit += (r > 255 - tol and g > 255 - tol and bl > 255 - tol)
    return hit / max(1, n)


def contact(rows, path):
    """Before (on white, as the site showed it) | after on the dark card colour, so a leftover white box shows."""
    T, cols = 240, 3
    if not rows:
        return
    sh = Image.new("RGB", (cols * (2 * T + 20), ((len(rows) + cols - 1) // cols) * (T + 30)), (255, 255, 255))
    d = ImageDraw.Draw(sh)
    for k, (pid, before, after, text) in enumerate(rows):
        cx, cy = (k % cols) * (2 * T + 20), (k // cols) * (T + 30)
        b = Image.new("RGBA", before.size, (255, 255, 255, 255)); b.alpha_composite(before.convert("RGBA"))
        b = b.convert("RGB"); b.thumbnail((T, T)); sh.paste(b, (cx + 4, cy + 4))
        dark = Image.new("RGBA", (after or before).size, (27, 31, 39, 255)); dark.alpha_composite((after or before).convert("RGBA"))
        dark = dark.convert("RGB"); dark.thumbnail((T, T)); sh.paste(dark, (cx + T + 8, cy + 4))
        d.text((cx + 6, cy + T + 8), (pid + "  " + text)[:70], fill=(0, 0, 0) if after is not None else (170, 20, 20))
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    sh.save(path, quality=86)


def process(pid, a, labels):
    """Returns (record, before image, after image or None)."""
    path = os.path.join(IMG, pid + ".webp")
    im = ImageOps.exif_transpose(Image.open(path)); im.load()
    rec = {"date": now(), "size": list(im.size)}
    if has_cutout(im):
        rec["status"] = "already"
        return rec, im, im
    lab = (labels.get(pid) or {})
    no_go = sorted(set(lab.get("photo_issues") or []) & NEEDS_NEW_PHOTO)
    if no_go:
        rec.update(status="kept", why=["labels: " + ", ".join(no_go)])
        return rec, im, None
    plain = border_plain(im)
    rec["plain_border"] = round(plain, 3)
    if plain < a.min_plain:
        rec.update(status="kept", why=["busy background (%.0f%% of the border is white)" % (100 * plain)])
        return rec, im, None
    alpha, how = cp.get_mask(im.convert("RGB"), a)                  # rembg, as clean_photos does it
    alpha, notes = cp.tidy(alpha, a.cat_of.get(pid), False, False)
    bad, st = cp.gate(alpha, a, a.set_of.get(pid, False))
    bad += [n[9:] for n in notes if n.startswith("DAMAGED: ")]
    rec.update(mask=how, notes=notes, stats=st)
    if bad:
        rec.update(status="kept", why=bad)
        return rec, im, None
    # compose on the photo's own canvas, never enlarging the item (no upscaling)
    canvas = min(MAX_SIDE, max(im.size))
    box = alpha.point(lambda v: 255 if v >= 24 else 0).getbbox()
    share = max(box[2] - box[0], box[3] - box[1]) / canvas
    cp.SIZE = canvas
    a.fill = min(a.max_fill, share)
    out, xy, item = cp.compose(im, alpha, a)
    fd = cp.fidelity(item, out, xy)
    rec["fidelity"] = round(fd, 2)
    if fd > 4.0:
        rec.update(status="kept", why=["fidelity %.1f" % fd])
        return rec, im, None
    buf = io.BytesIO(); out.save(buf, "WEBP", quality=a.quality, method=5)   # method 6: 25x slower for ~3% smaller files
    rec.update(status="ok", kb=len(buf.getvalue()) // 1024)
    if not a.dry_run:
        tmp = path + ".part"
        open(tmp, "wb").write(buf.getvalue())
        os.replace(tmp, path)
    return rec, im, out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=20, help="photos to look at this run (0 = all)")
    ap.add_argument("--max-minutes", type=float, default=40)
    ap.add_argument("--ids", default="")
    ap.add_argument("--retry-kept", action="store_true", help="look again at photos kept earlier")
    ap.add_argument("--rembg-model", default="isnet-general-use")
    ap.add_argument("--max-fill", type=float, default=0.86, help="item long side / canvas at most (clean_photos --fill)")
    ap.add_argument("--shadow", type=float, default=0.16)
    ap.add_argument("--max-parts", type=int, default=3)
    ap.add_argument("--min-plain", type=float, default=0.80, help="share of the border that must be white to try")
    ap.add_argument("--quality", type=int, default=84)
    ap.add_argument("--sheets", default=os.path.join(ROOT, "out", "rl-cutout-sheets"))
    ap.add_argument("--sheet-max", type=int, default=60, help="photos on the contact sheets (first ones of the run)")
    ap.add_argument("--dry-run", action="store_true", help="no files and no log written (sheets still made)")
    a = ap.parse_args()
    a.bg, a.recut, a.fill = "none", False, a.max_fill

    log = load_json(LOG, {})
    labels = (load_json(os.path.join(ROOT, "data", "catalog_ai.json"), {}) or {}).get("items", {})
    # category / set hints from the import list (tidy trims hangers on garments; a set may have two big pieces)
    rows = load_json(os.path.join(ROOT, "scripts", "rl_import.json"), [])
    a.cat_of = {r["id"]: r.get("cat") for r in rows}
    # several big pieces are right for sets, pairs of shoes and pairs of earrings / studs / cufflinks
    a.set_of = {r["id"]: r.get("cat") == "Shoes" or bool(re.search(
        r"(?i)\b(sets?|tracksuits?|pairs?|earrings?|studs?|cufflinks?|ear cuffs?)\b", r.get("title") or "")) for r in rows}
    have = sorted(f[:-5] for f in os.listdir(IMG) if f.endswith(".webp")) if os.path.isdir(IMG) else []
    want = set(a.ids.replace(" ", "").split(",")) - {""}
    todo = [i for i in have if (not want or i in want)
            and (log.get(i, {}).get("status") not in DONE or (a.retry_kept and log[i].get("status") == "kept"))]
    if a.limit:
        todo = todo[:a.limit]
    print("photos in img/rl: %d, logged %d, this run %d%s" % (len(have), len(log), len(todo), " (dry run)" if a.dry_run else ""))
    t0, count, sheet_rows, n_sheet = time.time(), {}, [], 0
    for k, pid in enumerate(todo):
        if time.time() - t0 > a.max_minutes * 60:
            print("time limit reached; the next run goes on"); break
        try:
            rec, before, after = process(pid, a, labels)
        except Exception as e:  # noqa: BLE001 (logged, retried next run)
            rec, before, after = {"date": now(), "status": "failed", "why": [str(e)[:160]]}, None, None
        count[rec["status"]] = count.get(rec["status"], 0) + 1
        if rec["status"] in ("kept", "failed"):
            print("  %s %s: %s" % (pid, rec["status"], "; ".join(rec.get("why") or [])))
        if not a.dry_run:
            log[pid] = rec
            if (k + 1) % 20 == 0:
                save_json(LOG, log)
        if before is not None and rec["status"] != "already" and n_sheet * 24 + len(sheet_rows) < a.sheet_max:
            sheet_rows.append((pid, before, after, rec["status"] + " " + "; ".join(rec.get("why") or [])))
            if len(sheet_rows) == 24:
                n_sheet += 1; contact(sheet_rows, os.path.join(a.sheets, "sheet-%02d.jpg" % n_sheet)); sheet_rows = []
    if sheet_rows:
        n_sheet += 1; contact(sheet_rows, os.path.join(a.sheets, "sheet-%02d.jpg" % n_sheet))
    if not a.dry_run:
        save_json(LOG, log)
    left = sum(1 for i in have if log.get(i, {}).get("status") not in DONE)
    print("done: %s in %.0f s; not done yet %d" % (", ".join("%s %d" % kv for kv in sorted(count.items())) or "nothing",
                                                    time.time() - t0, left))


if __name__ == "__main__":
    main()
