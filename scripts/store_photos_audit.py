# -*- coding: utf-8 -*-
"""Second AI check of every store-photo set (owner, 21 Nov 2026: "im dissapointet with alot of these ... fix alot of them").

For each find with new photos, the AI sees today's site photo (0) and every new photo (1..n) and keeps only the photos
that pass the owner's rules (data/store_photos_rules.md): same exact product AND colour as photo 0, whole item, sharp,
no label/logo/tag scans, no faded or broken cut-outs, no props or lifestyle shots. It also says which photo is the main.
Results go to data/store_photos_audit.json (nothing on the live site changes; the apply step reads it later).

  python scripts/store_photos_audit.py --max-usd 25 --workers 8
"""
import argparse, io, json, os, sys, threading, time
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import store_photos_pick as sp  # noqa: E402
from catalog_common import ROOT, load_catalog, load_json  # noqa: E402
from PIL import Image  # noqa: E402

OUT = os.path.join(ROOT, "data", "store_photos_audit.json")
RULES = open(os.path.join(ROOT, "data", "store_photos_rules.md"), encoding="utf-8").read()
SIDE = 512

PROMPT = """You are the final quality check for product photos in a premium fashion catalogue.
The item is listed as "{title}". Photo 0 is the seller's photo of the item the catalogue shows today. It is a REFERENCE
only: it tells you which product and colour this is. It is often lower quality, and the goal is to REPLACE it with clean
official store photos. A candidate showing the same front view as photo 0 is exactly what we want, never a duplicate.
Photos 1 to {n} are candidate store photos (the store's own order). Judge every candidate on its own pixels.
Photo 0 can differ from the real product in small details (a zip pull, a stitch, lighting, white balance): those do NOT
make a candidate a different version. The owner prefers MUCH better photos of a very similar item over bad photos of
the exact one: a very similar item (same brand, same kind of item, same main colour, near-identical look and silhouette)
is fine. Drop only when a shopper would clearly see another item: another colour (black vs navy, grey vs beige), another
pattern or print, a big logo where photo 0 has none, or a clearly different shape (cuffed jogger vs straight leg).

DROP a candidate if ANY of these is true:
- it is clearly a different item or a clearly different colour than photo 0 (see above: very similar is fine)
- it shows a label, tag, logo, print, stamp, scan or close-up detail instead of the whole item
- the item is cut off by the frame, or the cut-out is broken: faded, washed-out, ghosted, smeared, missing parts, holes
- it is blurry, low resolution, grainy, a screenshot, or has text/price/watermark overlays
- it has props, boxes, packaging, other products, or is a lifestyle/campaign scene
- it is a tight crop of a model (face or body cut so the item is not fully shown)
- it is a near-duplicate of another candidate you keep (photo 0 does not count)
When unsure, DROP. Fewer, perfect photos are better than many mixed ones.

KEEP clean studio photos of the whole item: front, back, sides, sole/top for shoes, and full model photos of the item.
Model photos go last. The main is the best clean product-only FRONT photo among the kept ones (never a model photo);
for items whose design is on the back, the back is the main. A clean, sharp studio cut-out or white-background front of
the same item beats a seller photo (a flat-lay on a table, a hanger, a busy or grey background, a soft or dark photo).
BUT if photo 0 is itself already a clean, sharp, straight-on studio front on a white or plain background, main is 0:
keep it, and the new photos only add angles. A straight-on front always beats a 3/4 or side view for the main.
Photo 0 is BAD (never keep it as main if any clean candidate exists) when it is: on a hanger or mannequin, a flat-lay or
pile, a messy or washed-out cut-out (smeared edges, glare, ghosting), or shows a tag/hanger hook.
For a set (tracksuit, two-piece), a clean studio front of the main piece is a fine main.
Sneakers and shoes: the main is ONE shoe in clean side profile (toe pointing left or right); a pair at 3/4 or a back
view goes after it.

{owner}The owner's full rules, for reference:
{rules}

Answer with JSON only:
{{"keep": [candidate numbers in display order, product photos first, model photos last],
  "model": [the kept numbers that are model photos],
  "main": number (0 or one of keep, never a model photo),
  "why": "one short sentence"}}"""

lock = threading.Lock()


def img(u):
    # no cache: the runner ran out of memory holding thousands of full-size photos (exit 143, 21 Nov 2026)
    try:
        im = Image.open(io.BytesIO(sp.fetch(u))).convert("RGBA")
        im.thumbnail((SIDE * 2, SIDE * 2))
        return im
    except Exception:
        return None


def site_url(p):
    u = p.get("img") or ""
    return sp.SITE + u if u.startswith("/") else u


OWNER = os.path.join(ROOT, "data", "store_photos_owner.json")
MAX_CANDS = 12


def owner_text(call):
    """The owner's call on this find (data/store_photos_owner.json), for the prompt."""
    if not isinstance(call, dict): return ""
    out = []
    if call.get("drop_site"): out.append("Photo 0 is NOT this exact item: use it only for brand, kind and colour; main must be a candidate, never 0.")
    if call.get("needs_main"): out.append("Photo 0 is a bad main: choose a clean candidate front as main if there is any.")
    if call.get("needs_more"): out.append("Keep every good angle (front, back, sides, details, model photos).")
    if call.get("search_as"): out.append(f"The item is: {call['search_as']}.")
    if call.get("main") == "site": out.append("The owner keeps photo 0 as the main: main is 0.")
    if call.get("note"): out.append(f"Owner's note: {call['note']}.")
    return ("THE OWNER'S CALL ON THIS FIND (follow it): " + " ".join(out) + "\n\n") if out else ""


def audit(fid, rec, p, prev=None, call=None):
    """prev: this find's earlier audit result (--keep-prev): the photos it kept are candidates again, after the new ones,
    so a deeper second pass never loses a good photo."""
    cands = ([] if rec.get("main") in (None, "", "current") else [rec["main"]]) + list(rec.get("gallery") or [])
    old = []
    if prev:
        old = ([] if prev.get("main") in (None, "", "current") else [prev["main"]]) + list(prev.get("gallery") or [])
    cands = list(dict.fromkeys(cands + old))
    prods = cands[:MAX_CANDS - min(3, len(rec.get("model") or []) + len((prev or {}).get("model") or []))]
    models = list(dict.fromkeys(list(rec.get("model") or []) + list((prev or {}).get("model") or [])))
    cands = list(dict.fromkeys(prods + models))[:MAX_CANDS]
    if not cands: return None
    base = img(site_url(p))
    content, shown = [], []
    if base is not None:
        content += [{"type": "text", "text": "Photo 0 (today's catalogue photo):"},
                    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": sp.jpg64(base, SIDE)}}]
    for u in cands:
        im = img(u)
        if im is None: continue
        shown.append(u)
        content += [{"type": "text", "text": f"Photo {len(shown)}:"},
                    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": sp.jpg64(im, SIDE)}}]
    if not shown: return {"main": "current", "gallery": [], "model": [], "dropped": [], "why": "no candidate could be loaded", "cost": 0, "at": sp.now()}
    title = p.get("title") or p.get("name") or fid
    content.append({"type": "text", "text": PROMPT.format(title=title, n=len(shown), rules=RULES, owner=owner_text(call))})
    ans, cost = sp.claude(content, max_tokens=4000)
    pick = lambda xs: [shown[i - 1] for i in xs if isinstance(i, int) and 1 <= i <= len(shown)]
    keep = pick(ans.get("keep") or [])
    model = [u for u in pick(ans.get("model") or []) if u in keep]
    m = ans.get("main")
    main = shown[m - 1] if isinstance(m, int) and 1 <= m <= len(shown) and shown[m - 1] in keep and shown[m - 1] not in model else "current"
    gallery = [u for u in keep if u not in model and u != main]
    return {"main": main, "gallery": gallery, "model": model, "dropped": [u for u in shown if u not in keep],
            "why": str(ans.get("why") or ans.get("note") or "")[:300], "cost": round(cost, 5), "at": sp.now()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-usd", type=float, default=25.0)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--ids", default="")
    ap.add_argument("--redo", action="store_true")
    ap.add_argument("--ids-file", default="", help="a file of ids (comma or whitespace separated), added to --ids")
    ap.add_argument("--keep-prev", action="store_true", help="the photos an earlier audit kept are candidates again")
    a = ap.parse_args()
    if a.ids_file:
        import re
        with open(a.ids_file if os.path.isabs(a.ids_file) else os.path.join(ROOT, a.ids_file), encoding="utf-8") as f:
            a.ids = ",".join([i for i in a.ids.split(",") if i] + [i for i in re.split(r"[\s,]+", f.read()) if i])
    owner = load_json(OWNER, {}) or {}
    hide = set((load_json(os.path.join(ROOT, "data", "report_overrides.json"), {}) or {}).get("hide") or [])
    by = {p["id"]: p for p in load_catalog()[1]}
    items = (load_json(sp.LOG, {}) or {}).get("items") or {}
    out = load_json(OUT, {"items": {}, "spent_usd": 0.0})
    stats = (load_json(os.path.join(ROOT, "data", "stats.json"), {}) or {}).get("p") or {}
    todo = [i for i in (a.ids.split(",") if a.ids else items) if i in items and i in by and (a.redo or i not in out["items"])]
    todo = [i for i in todo if i not in hide]
    has = lambda r: bool(r) and ((r.get("main") not in (None, "", "current")) or r.get("gallery") or r.get("model"))
    todo = [i for i in todo if has(items[i]) or (a.keep_prev and has(out["items"].get(i)))]
    todo.sort(key=lambda i: -(stats.get(i) or [0])[0])
    if a.limit: todo = todo[:a.limit]
    start = out.get("spent_usd", 0.0)
    print(f"{len(todo)} finds to check; spent so far {start:.2f} USD (cap {a.max_usd})", flush=True)
    done = [0]

    def save():
        tmp = OUT + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=1, sort_keys=True); f.write("\n")
        os.replace(tmp, OUT)

    def one(fid):
        if out.get("spent_usd", 0) >= a.max_usd: return
        try:
            prev = out["items"].get(fid) if a.keep_prev else None
            if prev and prev.get("prev"): prev = prev["prev"]   # a re-run keeps comparing with the first audit
            r = audit(fid, items[fid], by[fid], prev, owner.get(fid))
            if r is not None and a.keep_prev and out["items"].get(fid):
                r["prev"] = {k: v for k, v in (out["items"][fid].get("prev") or out["items"][fid]).items() if k in ("main", "gallery", "model", "why")}
        except Exception as e:
            print(f"{fid} error {e}", flush=True); return
        if r is None: return
        with lock:
            out["items"][fid] = r
            out["spent_usd"] = round(out.get("spent_usd", 0) + r["cost"], 4)
            done[0] += 1
            n_before = len(set(([] if items[fid].get("main") in (None, "", "current") else [items[fid]["main"]]) + (items[fid].get("gallery") or []) + (items[fid].get("model") or [])))
            pv = r.get("prev") or {}
            if pv: n_before = len(pv.get("gallery") or []) + len(pv.get("model") or []) + (pv.get("main") not in (None, "", "current"))
            n_after = len(r["gallery"]) + len(r["model"]) + (0 if r["main"] == "current" else 1)
            print(f"[{done[0]}/{len(todo)}] {fid} {n_before}->{n_after} main={'new' if r['main'] != 'current' else 'site'} | {r['why'][:110]}", flush=True)
            if done[0] % 25 == 0: save()

    with ThreadPoolExecutor(a.workers) as ex:
        list(ex.map(one, todo))
    save()
    kept = sum(len(r["gallery"]) + len(r["model"]) + (r["main"] != "current") for r in out["items"].values())
    print(f"summary: checked {done[0]} finds, {len(out['items'])} in all, {kept} photos kept, "
          f"{out['spent_usd'] - start:.2f} USD this run, {out['spent_usd']:.2f} USD in total (cap {a.max_usd})", flush=True)


if __name__ == "__main__":
    main()
