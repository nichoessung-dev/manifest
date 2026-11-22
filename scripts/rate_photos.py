# -*- coding: utf-8 -*-
"""Rate every listing's LIVE photo set by the standard of big luxury e-commerce stores (owner, 22 Nov 2026).

For each find in data/photo_rate_ids.txt the AI sees the live main photo (catalogue "img", photo 1, ~1024 px) and the
extra store angles (store-gallery.json, photos 2..n, ~512 px) and answers with tags:
  good  = store-ready set (stands alone)          hide = not worth showing (stands alone)
  lowq / angle / few / wrong / dup                = what is wrong (any combination)
plus a "why" that names the photo numbers, a per-photo verdict list and a confidence. Nothing on the site changes.

Results go to data/photo_ratings_parts/<part>.json; merge_photo_ratings() builds data/photo_ratings.json.

  python scripts/rate_photos.py --mode live --part calib-sonnet --limit 20 --model claude-sonnet-5-5
  python scripts/rate_photos.py --mode batch --shard 0 --shards 8 --model claude-sonnet-5-5 --max-usd 25
"""
import argparse, base64, glob, io, json, os, sys, time, urllib.error, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from catalog_common import ROOT, SITE, UA, load_catalog  # noqa: E402
from PIL import Image  # noqa: E402

import anthropic  # noqa: E402

IDS = os.path.join(ROOT, "data", "photo_rate_ids.txt")
PARTS = os.path.join(ROOT, "data", "photo_ratings_parts")
OUT = os.path.join(ROOT, "data", "photo_ratings.json")
STORE = "https://uptpghuduqjqmrxwatbm.supabase.co/storage/v1/object/public/products/store/"
MAIN_SIDE, ANGLE_SIDE, MAX_ANGLES = 1024, 512, 7
TAGS = ["good", "hide", "lowq", "angle", "few", "wrong", "dup"]
# USD per 1M tokens (input, output), standard rates; the Batches API bills half of this
PRICE = {"claude-opus-5-5": (4.0, 20.0), "claude-sonnet-5-5": (2.0, 10.0), "claude-haiku-5-5": (0.10, 0.50)}

SYSTEM = """You are the photo QA lead of a big luxury fashion e-commerce store (the standard of SSENSE, Mr Porter, \
Farfetch, Zalando, END.). You decide whether a listing's photo set would be accepted on a product page there.

You get photo 1 (the MAIN photo, the one shoppers see first) and sometimes more angles (photos 2..n), with each photo's \
ORIGINAL pixel size. Judge the set on its own pixels.

Tags (use exactly these):
- "good": the whole set is store-ready: every photo sharp and clean, the correct product, a proper main (a clean \
straight-on product shot of the whole item, white or plain studio background, or a full clean model shot), decent \
angles, and at least 3 usable photos including the main. "good" stands alone.
- "hide": the listing is not worth showing: the photos are unusable and nothing is salvageable (main broken, \
unrecognisable, a screenshot, a collage, a photo of a screen, a box or a pile, junk), or the item itself looks like \
junk. "hide" stands alone.
- Otherwise any combination of:
  "lowq": too low quality: blurry, soft, pixelated, upscaled (blocky or smeared texture, fake sharpening), JPEG \
artifacts, low resolution (original under about 700 px on the long side), noisy or dark phone photo, bad cut-out \
(jagged or haloed edges, missing parts, ghosting, grey fringe), washed out or wrong colour, cheap looking \
(wrinkled, dirty, cluttered or home background, glare), watermark, text, logo overlay or price tag overlay.
  "angle": bad angle or composition: the main is on a hanger, on a mannequin, a flat-lay on a bed or floor, a pile, \
a detail or label close-up, a tilted or skewed shot, the item cut off by the frame, a tight model crop, a bad model \
photo (mirror selfie, awkward pose, item hidden), the item small in the frame, or shoes not in a clean side or 3/4 view.
  "few": fewer than 3 usable photos in total (count only photos that would pass QA).
  "wrong": a photo shows a different product, colour, pattern or model than the title, or than the other photos.
  "dup": two photos are the same or near-identical shot.
Be strict like a real luxury store's photo QA: when unsure between "good" and a problem, pick the problem. A typical \
seller or marketplace photo is NOT good. Only clean official-store quality is good.

The owner will fix the listings automatically from your answer, so be specific:
- "photos": one entry per photo shown: {"i": photo number, "ok": true if this photo would pass QA as it is, \
"issue": "" if ok, else a few words naming the problem (e.g. "hanger main", "blurry", "different colour: navy not \
black", "label close-up", "duplicate of 2", "upscaled, smeared texture", "cut off at the bottom")}.
- "why": one or two short sentences naming the photo numbers and what to do (e.g. "1 is a hanger shot on a door; \
needs a clean studio front. 3 shows a grey version, drop it.").
- "conf": your confidence in the tags, 0 to 1."""

SCHEMA = {"type": "object", "additionalProperties": False, "required": ["tags", "photos", "why", "conf"], "properties": {
    "tags": {"type": "array", "items": {"type": "string", "enum": TAGS}},
    "photos": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["i", "ok", "issue"],
               "properties": {"i": {"type": "integer"}, "ok": {"type": "boolean"}, "issue": {"type": "string"}}}},
    "why": {"type": "string"}, "conf": {"type": "number"}}}


def now(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def site_url(u):
    if u.startswith("/"): return SITE + u
    if "supabase.co" in u: return SITE + "/api/img?u=" + urllib.parse.quote(u, safe="")
    return u


def fetch(url, tries=5):
    last = None
    for k in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as r: return r.read()
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (400, 401, 403, 404, 410): break
        except Exception as e:
            last = e
        time.sleep(2 ** k)
    raise last


def jpg(url, side):
    """(base64 JPEG at most side px, original (w, h)); nothing is kept in memory after this returns."""
    im = Image.open(io.BytesIO(fetch(url))); im.load(); size = im.size
    if im.mode in ("P", "LA", "RGBA") or "transparency" in im.info:
        im = im.convert("RGBA"); bg = Image.new("RGBA", im.size, (255, 255, 255, 255)); bg.alpha_composite(im); im = bg
    im = im.convert("RGB"); im.thumbnail((side, side), Image.LANCZOS)
    b = io.BytesIO(); im.save(b, "JPEG", quality=88)
    return base64.b64encode(b.getvalue()).decode(), size


def build(fid, p, gal):
    """The user content for one find, or (None, reason) when the main photo cannot be loaded."""
    urls = [(p.get("img") or "", MAIN_SIDE)] + [(STORE + n, ANGLE_SIDE) for n in (gal.get(fid) or [])[:MAX_ANGLES]]
    content, shown, fails = [], 0, []
    for k, (u, side) in enumerate(urls):
        try:
            data, (w, h) = jpg(site_url(u), side)
        except Exception as e:
            if k == 0: return None, f"main photo failed to load: {type(e).__name__} {str(e)[:80]}"
            fails.append(k + 1); continue
        shown += 1
        label = "Photo 1 (MAIN)" if k == 0 else f"Photo {shown}"
        content += [{"type": "text", "text": f"{label}, original {w}x{h} px:"},
                    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": data}}]
    title = p.get("title") or fid
    note = f" ({len(fails)} more listed photo(s) failed to load and are not counted.)" if fails else ""
    content.append({"type": "text", "text": f'The listing is titled "{title}". It has {shown} photo(s) in total.{note} '
                    "Rate this photo set."})
    return content, shown


def params(model, content):
    return {"model": model, "max_tokens": 4000, "system": SYSTEM, "messages": [{"role": "user", "content": content}],
            "thinking": {"type": "adaptive"}, "output_config": {"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}}}


def cost_of(model, usage, batch):
    pi, po = PRICE.get(model, (4.0, 20.0))
    c = (usage.input_tokens * pi + (getattr(usage, "cache_creation_input_tokens", 0) or 0) * pi * 1.25
         + (getattr(usage, "cache_read_input_tokens", 0) or 0) * pi * 0.1 + usage.output_tokens * po) / 1e6
    return c * (0.5 if batch else 1.0)


def finish(msg, model, n, batch):
    """A rating record from one response."""
    cost = cost_of(model, msg.usage, batch)
    if msg.stop_reason == "refusal":
        return {"error": "refusal", "cost": round(cost, 5), "at": now()}
    txt = "".join(b.text for b in msg.content if b.type == "text")
    try:
        a = json.loads(txt)
    except ValueError:
        return {"error": f"bad answer ({msg.stop_reason}): {txt[:120]}", "cost": round(cost, 5), "at": now()}
    tags = [t for t in dict.fromkeys(a.get("tags") or []) if t in TAGS]
    if "hide" in tags: tags = ["hide"]
    elif "good" in tags and len(tags) > 1: tags = [t for t in tags if t != "good"]   # strict: a problem beats good
    if "hide" not in tags and n < 3:
        tags = [t for t in tags if t != "good"]
        if "few" not in tags: tags.append("few")
    if not tags: tags = ["lowq"]
    return {"tags": tags, "why": str(a.get("why") or "")[:400], "conf": round(float(a.get("conf") or 0), 2),
            "photos": a.get("photos") or [], "n": n, "model": model, "at": now(), "cost": round(cost, 5)}


def load_part(name):
    path = os.path.join(PARTS, name + ".json")
    try: return path, json.load(open(path, encoding="utf-8"))
    except Exception: return path, {"ratings": {}, "spent_usd": 0.0}


def save(path, d):
    os.makedirs(PARTS, exist_ok=True)
    json.dump(d, open(path + ".tmp", "w", encoding="utf-8"), ensure_ascii=False, indent=0, sort_keys=True)
    os.replace(path + ".tmp", path)


def spent_all():
    t = 0.0
    for f in glob.glob(os.path.join(PARTS, "*.json")):
        try: t += json.load(open(f, encoding="utf-8")).get("spent_usd", 0)
        except Exception: pass
    return t


def merge():
    """data/photo_ratings.json from the shard parts (s*.json)."""
    out = {}
    for f in sorted(glob.glob(os.path.join(PARTS, "s*.json"))):
        for i, r in json.load(open(f, encoding="utf-8")).get("ratings", {}).items():
            if "tags" in r: out[i] = {k: r[k] for k in ("tags", "why", "conf", "photos", "n", "model", "at")}
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1, sort_keys=True)
    print(f"{len(out)} ratings -> {OUT}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["live", "batch", "merge"], default="live")
    ap.add_argument("--model", default="claude-sonnet-5-5")
    ap.add_argument("--part", default="")
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--shards", type=int, default=1)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--ids", default="")
    ap.add_argument("--redo", action="store_true")
    ap.add_argument("--max-usd", type=float, default=25.0, help="hard stop: all parts together")
    ap.add_argument("--est-usd", type=float, default=0.006, help="expected cost per find (for the budget check)")
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    if a.mode == "merge": return merge()
    ids = [i for i in open(IDS, encoding="utf-8").read().split() if i]
    if a.ids: ids = [i for i in a.ids.split(",") if i]
    ids = ids[a.shard::a.shards]
    path, part = load_part(a.part or f"s{a.shard}")
    client = anthropic.Anthropic(max_retries=8)
    batch = a.mode == "batch"

    if batch and part.get("batch_id") and not part.get("batch_done"):
        collect(client, a, path, part); return
    todo = [i for i in ids if a.redo or "tags" not in part["ratings"].get(i, {})]
    if a.limit: todo = todo[:a.limit]
    base = spent_all()
    est = len(todo) * a.est_usd * (0.5 if batch else 1.0)
    print(f"{len(todo)} finds, model {a.model}, spent so far {base:.3f} USD, this run about {est:.2f} USD", flush=True)
    if base + est > a.max_usd: raise SystemExit(f"budget: {base:.2f} + {est:.2f} > {a.max_usd} USD, not started")
    _, items, _, _ = load_catalog()
    byid = {str(p.get("id")): p for p in items}
    gal = json.load(open(os.path.join(ROOT, "store-gallery.json"), encoding="utf-8"))

    def one(fid):
        p = byid.get(fid)
        if not p: return fid, None, "not in the catalogue"
        content, n = build(fid, p, gal)
        return fid, content, n

    if not batch:
        spent = 0.0
        def rate(fid):
            fid, content, n = one(fid)
            if content is None: return fid, {"error": n, "at": now()}
            return fid, finish(client.messages.create(**params(a.model, content)), a.model, n, False)
        with ThreadPoolExecutor(a.workers) as ex:
            for k, (fid, r) in enumerate(ex.map(rate, todo), 1):
                part["ratings"][fid] = r; spent += r.get("cost", 0)
                part["spent_usd"] = round(part.get("spent_usd", 0) + r.get("cost", 0), 5)
                print(f"[{k}/{len(todo)}] {fid} {r.get('tags') or r.get('error')} {r.get('conf', '')} | {r.get('why', '')[:150]}", flush=True)
                if k % 20 == 0: save(path, part)
                if base + spent > a.max_usd: print("budget reached, stopping"); break
        save(path, part); print(f"spent {spent:.4f} USD this run"); return

    # batch: build every request (images only as base64 strings, about 150 KB a find), submit, then wait
    reqs, ns = [], {}
    with ThreadPoolExecutor(a.workers) as ex:
        for fid, content, n in ex.map(one, todo):
            if content is None: part["ratings"][fid] = {"error": n, "at": now()}; continue
            reqs.append({"custom_id": fid, "params": params(a.model, content)}); ns[fid] = n
    print(f"submitting {len(reqs)} requests", flush=True)
    b = client.messages.batches.create(requests=reqs)
    del reqs
    part.update({"batch_id": b.id, "batch_done": False, "batch_model": a.model, "batch_n": ns})
    save(path, part)
    collect(client, a, path, part)


def collect(client, a, path, part):
    bid, model = part["batch_id"], part.get("batch_model", a.model)
    t0 = time.time()
    while True:
        b = client.messages.batches.retrieve(bid)
        if b.processing_status == "ended": break
        if time.time() - t0 > 5 * 3600: print(f"batch {bid} still running; run again to collect"); return
        print(f"batch {bid}: {b.processing_status} {b.request_counts}", flush=True)
        time.sleep(60)
    spent = 0.0
    for res in client.messages.batches.results(bid):
        fid = res.custom_id
        if res.result.type == "succeeded":
            r = finish(res.result.message, model, part["batch_n"].get(fid, 1), True)
        else:
            r = {"error": f"batch {res.result.type}", "at": now()}
        spent += r.get("cost", 0); part["ratings"][fid] = r
    part["spent_usd"] = round(part.get("spent_usd", 0) + spent, 5)
    part["batch_done"] = True
    save(path, part)
    print(f"batch {bid} collected, {spent:.4f} USD; part total {part['spent_usd']:.4f} USD")


if __name__ == "__main__":
    main()
