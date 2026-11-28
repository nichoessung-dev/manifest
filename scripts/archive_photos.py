# -*- coding: utf-8 -*-
"""Cut-outs for the Archive import (scripts/import_archive.py, owner 26 Nov 2026), on GitHub's runners
(.github/workflows/import-archive.yml). Sharded: shard k of n takes the finds with int(sha1(id)) % n == k
(store_photos_shards.py), so parallel runs never write the same file.

Per staged find (data/archive_import.json) of this shard that has no final record yet:
  1. photo     the original listing's main photo ("src", the seller's own picture on alicdn), full size
  2. look      with ANTHROPIC_API_KEY one vision call (claude-haiku-5-5, as import_friend.py) on the photo and the find's
               title: is it ONE product alone, whole, with no person, hand, collage, box or text over the item? A photo
               that is not is kept out ("kept"). Without the key, only photos on a plain white studio background are tried
               (rl_cutout.py's border test)
  3. cut-out   clean_photos.py's own pipeline, imported, not copied, as rl_cutout.py runs it: rembg mask
               (isnet-general-use), mask tidy, quality gate, transparent compose with the soft shadow in the alpha,
               fidelity check. No upscaling, nothing drawn: the canvas is the photo's own size (at most 1600 px) and the
               item is never enlarged
  4. storage   Supabase products/pc2/<id>-t1.webp (a transparent cut-out: the dark tile in dark mode, photo_tiles.js
               CUT_RX), a NEW object only (x-upsert false): an existing object is never replaced. Not in the repository:
               Cloudflare Pages allows 20,000 files and the site has about 18,400
Per find the record is one of:
  cut      the cut-out is in storage ("url"): scripts/import_archive.py apply adds the find
  kept     the photo is not good enough (the vision look, the gate, the fidelity check): the find is not added
  gone     the photo no longer loads
  failed   an error: tried again on the next run
Records: data/archive_photos/<k>-of-<n>.json. Review sheets (the original photo | the cut-out on #262626 | title and
status) go to --sheets.
--set murphy (27 Nov 2026) does the same for the Da Murphy finds sheet (scripts/import_sheet.py): its staged finds
(data/sheet_import/), its records data/sheet_photos/<k>-of-<n>.json (import_archive.py SETS). Their photos are Weidian's
(geilicdn), fetched with Weidian as the referrer as import_friend.py does.

  python scripts/archive_photos.py [--set archive] [--shard 0/1] [--limit 0] [--max-minutes 0] [--ids 1,2] [--no-upload]
                                   [--no-vision] [--max-usd 1.5] [--retry-kept] [--sheets out/archive-sheets]
"""
import argparse, base64, hashlib, io, json, os, re, sys, time, urllib.error, urllib.request
from datetime import datetime, timezone

from PIL import Image, ImageDraw, ImageOps

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from catalog_common import ROOT, load_json, save_json  # noqa: E402
import store_photos_shards as shards  # noqa: E402
import import_archive as IA  # noqa: E402

SUPA = "https://uptpghuduqjqmrxwatbm.supabase.co"
PUB = SUPA + "/storage/v1/object/public/"
H = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}
MAX_SIDE = 1600
FINAL = ("cut", "kept", "gone")
VISION = os.environ.get("ARCHIVE_VISION_MODEL", "claude-haiku-5-5")
DARK = (38, 38, 38)      # ds.css --well in dark mode (#262626)
spent = [0.0]
_vision_err = []


def now(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def fetch(url):
    """The photo as RGB (EXIF turned), at most 2600 px; None when it is gone (403, 404, 410)."""
    last = None
    hd = dict(H, Referer="https://weidian.com/") if "geilicdn.com" in url else H
    for k in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=hd), timeout=45) as r: data = r.read()
            im = Image.open(io.BytesIO(data))
            if im.format == "JPEG": im.draft("RGB", (2600, 2600))
            im.load()
            im = ImageOps.exif_transpose(im)
            if max(im.size) > 2600: im = im.copy(); im.thumbnail((2600, 2600), Image.LANCZOS)
            if im.mode in ("RGBA", "LA", "P"):
                bg = Image.new("RGBA", im.size, (255, 255, 255, 255)); bg.alpha_composite(im.convert("RGBA")); im = bg
            return im.convert("RGB")
        except urllib.error.HTTPError as e:
            if e.code in (403, 404, 410): return None
            last = e
        except Exception as e:  # noqa: BLE001 (retried)
            last = e
        time.sleep(2 + 3 * k)
    raise RuntimeError("photo did not load: %s" % str(last)[:100])


def border_plain(im, tol=18):
    """Share of the outer 2% frame that is close to white (rl_cutout.py): a studio shot on white scores near 1."""
    rgb = im.convert("RGB"); w, h = rgb.size
    b = max(2, round(0.02 * min(w, h))); px = rgb.load(); n = hit = 0
    step = max(1, min(w, h) // 300)
    for x in range(0, w, step):
        for y in list(range(0, b)) + list(range(h - b, h)):
            r, g, bl = px[x, y]; n += 1; hit += (r > 255 - tol and g > 255 - tol and bl > 255 - tol)
    for y in range(0, h, step):
        for x in list(range(0, b)) + list(range(w - b, w)):
            r, g, bl = px[x, y]; n += 1; hit += (r > 255 - tol and g > 255 - tol and bl > 255 - tol)
    return hit / max(1, n)


def new_photo(rec, entry):
    """The stage chose another photo since this record was made (import_sheet.py photo RULE 2, 27 Nov 2026)."""
    return bool(rec and rec.get("src") and entry.get("src") and rec["src"] != entry["src"])


def object_name(oid, prev, src):
    """products/pc2/<id>-t1.webp; for a find whose photo changed after an earlier record, <id>-t1.v<6 hex of the photo
    link>.webp, because a stored object is never replaced (x-upsert false) and the edge caches the old one."""
    if prev and prev.get("src") and prev["src"] != src:
        return "products/pc2/%s-t1.v%s.webp" % (oid, hashlib.sha1((src or "").encode()).hexdigest()[:6])
    return "products/pc2/%s-t1.webp" % oid


def look(im, title):
    """One vision call: {"ok": bool, "issue": str, "several": bool}. {} when the call fails."""
    sm = im.copy(); sm.thumbnail((512, 512)); b = io.BytesIO(); sm.save(b, "JPEG", quality=85)
    content = [{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": base64.b64encode(b.getvalue()).decode()}},
               {"type": "text", "text":
                "This is the main photo of a shop listing for: " + json.dumps(title) + ". It will be cut out (background "
                "removed) for a product catalogue. Is it a good photo for that? ok is true only when the photo shows the "
                "product ALONE and whole: no person or body part wearing or holding it, no hand, not a collage or grid of "
                "several photos, not several different products, not a box or packaging as the subject, and NO added text, "
                "number, price tag, stamp or watermark anywhere in the photo (Chinese or English captions next to the item "
                "survive the cut-out, so they count too; only text printed on the product itself is fine), NO blurred, smudged, "
                "pixelated or painted-over patch hiding a logo or print (sellers often blur the logo; a real painted, "
                "splattered or distressed design printed on the product is fine), and it is the product named (not a size chart, not a detail close-up). A pair of shoes, a set "
                "worn as one outfit laid flat, or one item shown with its own strap is fine. several: true when the product "
                "is a pair or a set of two or more pieces. issue: '' when ok, else a few words. "
                'Answer only JSON, no code fence: {"ok":true,"several":false,"issue":""}'}]
    body = json.dumps({"model": VISION, "max_tokens": 300, "messages": [{"role": "user", "content": content}]}).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, headers={
        "x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01", "content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=90) as r: d = json.load(r)
    except Exception as e:  # noqa: BLE001 (the find is then judged without the look)
        if not _vision_err:
            body = e.read()[:200].decode("utf-8", "replace") if isinstance(e, urllib.error.HTTPError) else ""
            print("  vision call failed (only plain studio photos are tried without it): %s %s" % (str(e)[:80], body), flush=True)
            _vision_err.append(1)
        return {}
    u = d.get("usage") or {}; spent[0] += (u.get("input_tokens", 0) * 1.0 + u.get("output_tokens", 0) * 5.0) / 1e6
    m = re.search(r"\{.*\}", "".join(c.get("text", "") for c in d.get("content", [])), re.S)
    try: return json.loads(m.group(0)) if m else {}
    except ValueError: return {}


BLUR_MODEL = os.environ.get("BLUR_VISION_MODEL", "claude-sonnet-5-5")
BLUR_RATES = {"claude-sonnet-5-5": (3.0, 15.0), "claude-haiku-5-5": (1.0, 5.0)}   # USD per million tokens in, out


def blur_check(im):
    """One focused vision call (owner, 28 Nov 2026: no photo with a blurred-out logo goes live; the stage's many-rule
    look missed most of them): {"blurred": bool, "where": str}. {} when the call fails."""
    sm = im.convert("RGB"); sm.thumbnail((1024, 1024)); b = io.BytesIO(); sm.save(b, "JPEG", quality=88)
    content = [{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": base64.b64encode(b.getvalue()).decode()}},
               {"type": "text", "text":
                "This is a seller's product photo from a Chinese shop. Sellers often hide a brand logo, a print or a tag by "
                "blurring, smudging, pixelating or painting over it with a soft brush in an editor. That leaves a smeared, "
                "out-of-focus or blocky patch with soft edges on an item that is otherwise sharp. Look closely at the whole "
                "item: chest, back, sleeves, legs, hood, collar, tags. blurred: true if ANY part of the item has such a "
                "patch, even a small one. false only when everything on the item is sharp. A real printed or embroidered "
                "design that is meant to look painted, splattered, distressed, faded or washed is NOT blurring: it has crisp "
                "edges and fabric texture inside it. where: '' when false, else a few words. "
                'Answer only JSON, no code fence: {"blurred":false,"where":""}'}]
    body = json.dumps({"model": BLUR_MODEL, "max_tokens": 200, "messages": [{"role": "user", "content": content}]}).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, headers={
        "x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01", "content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=90) as r: d = json.load(r)
    except Exception as e:  # noqa: BLE001
        print("  blur check failed: %s" % str(e)[:120], flush=True); return {}
    u = d.get("usage") or {}; ri, ro = BLUR_RATES.get(BLUR_MODEL, (3.0, 15.0))
    spent[0] += (u.get("input_tokens", 0) * ri + u.get("output_tokens", 0) * ro) / 1e6
    m = re.search(r"\{.*\}", "".join(c.get("text", "") for c in d.get("content", [])), re.S)
    try: v = json.loads(m.group(0)) if m else {}
    except ValueError: return {}
    return {"blurred": bool(v.get("blurred")), "where": str(v.get("where") or "")[:60]} if "blurred" in v else {}


def recheck_blur(a, shard, staged, recs, log, log_path):
    """--recheck-blur: the blur check on this shard's cut finds that have none yet (with --ids, those again). The verdict
    goes in the record ("blur"); a blurred one becomes "kept" unless --report-only."""
    k, n = shard
    want = {x for x in a.ids.replace(" ", "").split(",") if x}
    todo = [i for i in sorted(staged) if shards.mine(i, shard) and (recs.get(i) or {}).get("status") == "cut"
            and (i in want if want else "blur" not in recs[i])]
    print("%s blur check, shard %d/%d: %d to check (%s)" % (a.set, k, n, len(todo), BLUR_MODEL), flush=True)
    t0, c = time.time(), {}
    for j, i in enumerate(todo):
        if (a.max_minutes and time.time() - t0 > a.max_minutes * 60) or spent[0] >= a.max_usd:
            print("time or budget limit reached; the next run goes on", flush=True); break
        rec = recs[i]; im = fetch(rec.get("src") or staged[i].get("src"))
        if im is None: continue
        v = blur_check(im)
        if not v: continue
        rec["blur"] = dict(v, at=now(), model=BLUR_MODEL)
        if v["blurred"]:
            print("  %s blurred: %s" % (i, v["where"]), flush=True)
            if not a.report_only: rec.update(status="kept", why=["blurred logo: " + v["where"]])
        c[v["blurred"]] = c.get(v["blurred"], 0) + 1
        if (j + 1) % 20 == 0: save_json(log_path, log); print("  %d checked, $%.2f" % (j + 1, spent[0]), flush=True)
    save_json(log_path, log)
    left = sum(1 for i in staged if shards.mine(i, shard) and (recs.get(i) or {}).get("status") == "cut" and "blur" not in recs[i])
    print("done: blurred %d, clean %d, $%.2f; left %d" % (c.get(True, 0), c.get(False, 0), spent[0], left), flush=True)


def upload(name, data):
    """'uploaded' or 'exists' (an object is never replaced)."""
    key = os.environ["SUPABASE_SERVICE_KEY"]
    req = urllib.request.Request(SUPA + "/storage/v1/object/" + name, data=data, method="POST", headers={
        **H, "Authorization": "Bearer " + key, "apikey": key, "Content-Type": "image/webp",
        "x-upsert": "false", "Cache-Control": "max-age=31536000"})
    try:
        urllib.request.urlopen(req, timeout=60).read(); return "uploaded"
    except urllib.error.HTTPError as e:
        body = e.read()[:200].decode("utf-8", "replace")
        if e.code in (400, 409) and ("Duplicate" in body or "already exists" in body or "409" in body): return "exists"
        raise RuntimeError("%s %s" % (e.code, body))


def same_remote(name, sha1):
    try:
        return hashlib.sha1(urllib.request.urlopen(PUB + name, timeout=60).read()).hexdigest() == sha1
    except Exception:
        return False


def cut(im, a, cat, several):
    """(record bits, cut-out RGBA or None): clean_photos.py's mask, tidy, gate, compose and fidelity, never enlarging."""
    import clean_photos as cp
    alpha, how = cp.get_mask(im, a)
    alpha, notes = cp.tidy(alpha, cat, False, False)
    bad, st = cp.gate(alpha, a, several)
    bad += [n[9:] for n in notes if n.startswith("DAMAGED: ")]
    rec = {"mask": how, "notes": notes, "stats": st}
    if bad: return dict(rec, why=bad), None
    canvas = min(MAX_SIDE, max(im.size))
    box = alpha.point(lambda v: 255 if v >= 24 else 0).getbbox()
    share = max(box[2] - box[0], box[3] - box[1]) / canvas
    cp.SIZE = canvas
    a.fill = min(a.max_fill, share)
    out, xy, item = cp.compose(im, alpha, a)
    fd = cp.fidelity(item, out, xy)
    rec["fidelity"] = round(fd, 2)
    if fd > 4.0: return dict(rec, why=["fidelity %.1f" % fd]), None
    return rec, out


def contact(rows, path):
    """Each find: the original photo | the cut-out on the dark tile (#262626, so a leftover white box shows) | text."""
    T, cols = 220, 3
    if not rows: return
    sh = Image.new("RGB", (cols * (2 * T + 20), ((len(rows) + cols - 1) // cols) * (T + 44)), (255, 255, 255))
    d = ImageDraw.Draw(sh)
    for k, (oid, before, after, text) in enumerate(rows):
        cx, cy = (k % cols) * (2 * T + 20), (k // cols) * (T + 44)
        b = before.convert("RGB"); b.thumbnail((T, T)); sh.paste(b, (cx + 4, cy + 4))
        tile = Image.new("RGB", (T, T), DARK)
        if after is not None:
            x = after.copy(); x.thumbnail((T, T)); tile.paste(x, ((T - x.width) // 2, (T - x.height) // 2), x)
        sh.paste(tile, (cx + T + 8, cy + 4))
        d.text((cx + 6, cy + T + 8), (oid + "  " + text)[:72], fill=(0, 0, 0) if after is not None else (170, 20, 20))
        d.text((cx + 6, cy + T + 24), text[72:144], fill=(90, 90, 90))
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    sh.save(path, quality=86)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="archive", choices=sorted(IA.SETS), help="which import (scripts/import_archive.py)")
    ap.add_argument("--shard", default="0/1"); ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--max-minutes", type=float, default=0); ap.add_argument("--ids", default="")
    ap.add_argument("--no-upload", action="store_true", help="make the cut-outs and sheets, upload and record nothing")
    ap.add_argument("--no-vision", action="store_true"); ap.add_argument("--max-usd", type=float, default=1.5)
    ap.add_argument("--retry-kept", action="store_true", help="look again at finds kept out before")
    ap.add_argument("--recheck-blur", action="store_true", help="only the blur check on cut finds (see recheck_blur)")
    ap.add_argument("--report-only", action="store_true", help="--recheck-blur: record the verdicts, change no status")
    ap.add_argument("--rembg-model", default="isnet-general-use")
    ap.add_argument("--max-fill", type=float, default=0.86); ap.add_argument("--shadow", type=float, default=0.16)
    ap.add_argument("--max-parts", type=int, default=3); ap.add_argument("--min-plain", type=float, default=0.80)
    ap.add_argument("--quality", type=int, default=84)
    ap.add_argument("--sheets", default=os.path.join(ROOT, "out", "archive-sheets"))
    ap.add_argument("--sheet-max", type=int, default=90)
    a = ap.parse_args(argv)
    a.bg, a.recut, a.fill = "none", False, a.max_fill
    shard = shards.parse(a.shard)
    k, n = shard
    folder = IA.set_of(a.set)["photos"]
    log_path = os.path.join(folder, "%d-of-%d.json" % (k, n))
    log = load_json(log_path, {}) or {}
    recs = log.setdefault("items", {})
    staged = IA.staged(a.set)
    if a.recheck_blur:
        if not os.environ.get("ANTHROPIC_API_KEY"): sys.exit("ANTHROPIC_API_KEY is not set: the blur check is a vision call")
        return recheck_blur(a, shard, staged, recs, log, log_path)
    want = {x for x in a.ids.replace(" ", "").split(",") if x}
    done_elsewhere = {}
    for f in os.listdir(folder) if os.path.isdir(folder) else []:
        if f.endswith(".json") and os.path.join(folder, f) != log_path:
            for i, r in ((load_json(os.path.join(folder, f), {}) or {}).get("items") or {}).items():
                if r.get("status") == "cut" and not new_photo(r, staged.get(i) or {}): done_elsewhere[i] = r
    mine = [i for i in staged if shards.mine(i, shard) and (not want or i in want) and i not in done_elsewhere]
    todo = [i for i in mine if (recs.get(i) or {}).get("status") not in FINAL or new_photo(recs.get(i), staged[i])
            or (a.retry_kept and recs[i].get("status") == "kept") or (want and recs.get(i, {}).get("status") != "cut")]
    if a.limit: todo = todo[:a.limit]
    vision = bool(os.environ.get("ANTHROPIC_API_KEY")) and not a.no_vision
    upload_on = not a.no_upload and bool(os.environ.get("SUPABASE_SERVICE_KEY"))
    print("%s photos, shard %d/%d: staged %d, this shard %d, to do now %d (vision %s, upload %s)"
          % (a.set, k, n, len(staged), len(mine), len(todo), "on" if vision else "off", "on" if upload_on else "off"), flush=True)
    if not a.no_upload and not upload_on: print("  SUPABASE_SERVICE_KEY is not set: nothing is uploaded or recorded", flush=True)
    t0, count, sheet_rows, n_sheet = time.time(), {}, [], 0
    for j, oid in enumerate(todo):
        if a.max_minutes and time.time() - t0 > a.max_minutes * 60: print("time limit reached; the next run goes on", flush=True); break
        v = staged[oid]; row = v["row"]
        rec, before, after = {"at": now(), "src": v.get("src")}, None, None
        try:
            im = fetch(v["src"])
            if im is None:
                rec.update(status="gone", why=["the photo no longer loads"])
            else:
                before = im
                plain = border_plain(im); rec["plain_border"] = round(plain, 3)
                several = row["cat"] == "Shoes" or bool(re.search(
                    r"(?i)\b(sets?|tracksuits?|pairs?|earrings?|studs?|cufflinks?|ear cuffs?|socks)\b", row.get("title") or ""))
                verdict = {}
                if vision and spent[0] < a.max_usd:
                    verdict = look(im, row.get("title") or "")
                    rec["vision"] = verdict
                    several = several or bool(verdict.get("several"))
                if verdict and verdict.get("ok") is False:
                    rec.update(status="kept", why=["vision: " + str(verdict.get("issue") or "not a clean product photo")[:80]])
                elif not verdict and plain < a.min_plain:
                    rec.update(status="kept", why=["busy background (%.0f%% of the border is white) and no vision look" % (100 * plain)])
                else:
                    bits, out = cut(im, a, row.get("cat"), several)
                    rec.update(bits)
                    if out is None:
                        rec["status"] = "kept"
                    else:
                        after = out
                        buf = io.BytesIO(); out.save(buf, "WEBP", quality=a.quality, method=5); data = buf.getvalue()
                        sha = hashlib.sha1(data).hexdigest()
                        name = object_name(oid, recs.get(oid), v.get("src"))
                        rec.update(kb=len(data) // 1024, sha1=sha, object=name)
                        if upload_on:
                            res = upload(name, data)
                            if res == "exists" and not same_remote(name, sha):
                                rec.update(status="kept", why=["storage already has %s with other bytes" % name])
                            else:
                                rec.update(status="cut", url=PUB + name)
                        else:
                            rec.update(status="cut (not uploaded)")
        except Exception as e:  # noqa: BLE001 (recorded, tried again next run)
            rec.update(status="failed", why=[str(e)[:160]])
        count[rec["status"]] = count.get(rec["status"], 0) + 1
        if rec["status"] in ("kept", "failed", "gone"):
            print("  %s %s: %s" % (oid, rec["status"], "; ".join(rec.get("why") or [])), flush=True)
        if upload_on:
            recs[oid] = rec
            if (j + 1) % 10 == 0: save_json(log_path, log)
        if before is not None and n_sheet * 24 + len(sheet_rows) < a.sheet_max:
            sheet_rows.append((oid, before, after, "%s %s  %s" % (rec["status"], "; ".join(rec.get("why") or []), row.get("title") or "")))
            if len(sheet_rows) == 24:
                n_sheet += 1; contact(sheet_rows, os.path.join(a.sheets, "s%d-of-%d-%02d.jpg" % (k, n, n_sheet))); sheet_rows = []
        if (j + 1) % 20 == 0: print("  %d done, $%.2f, %.0f s" % (j + 1, spent[0], time.time() - t0), flush=True)
    if sheet_rows:
        n_sheet += 1; contact(sheet_rows, os.path.join(a.sheets, "s%d-of-%d-%02d.jpg" % (k, n, n_sheet)))
    if upload_on:
        log["spent_usd"] = round(float(log.get("spent_usd") or 0) + spent[0], 4); log["at"] = now()
        save_json(log_path, log)
    left = sum(1 for i in mine if (recs.get(i) or {}).get("status") not in FINAL)
    print("done: %s in %.0f s, vision $%.2f" % (", ".join("%s %d" % kv for kv in sorted(count.items())) or "nothing",
                                               time.time() - t0, spent[0]), flush=True)
    print("left %d" % left, flush=True)


if __name__ == "__main__":
    sys.exit(main())
