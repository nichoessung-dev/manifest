# -*- coding: utf-8 -*-
"""Fix weak main photos (owner, 15 Nov 2026: "I want every picture on the site to be perfect" ... "there are some good
photos on the website so we do not need to change every single one").

Only finds whose photo is weak are touched: the vision labels (data/catalog_ai.json "photo_issues", or a photo hide in
data/photo_hidden.json other than "duplicate"). Good photos are never replaced. Per find, in this order:
  1. RETAIL: an image search (Brave Search API, BRAVE_API_KEY) limited to official retailers (RETAILERS below). A
     vision model sees the current photo + the candidates and accepts one only if it is the SAME design (logos,
     prints, pockets, details) in the SAME colour, a clean product-only shot (no model, no hands, no text). A test on
     20 finds (15 Nov) matched about 1 in 5: reps often differ from the retail item, so a no is the normal answer.
  2. SELLER: scripts/seller_photos.py already does the seller's own listing photos (Weidian); it is not repeated here.
  3. CLEAN-UP: the current photo (the real item) is edited by an image model (Gemini, GEMINI_API_KEY): remove text,
     watermarks, tags, hangers, hands and people, keep the item identical. The vision model then compares before and
     after and rejects any edit that changed the item (logos, colour, shape).
Every accepted photo is cut out (rembg isnet-general-use), put on a transparent 1200x1200 canvas and written to
out/photo-fix/<id>.webp with a before/after contact sheet. Nothing on the site changes here; data/photo_fix.json
records each find (status, step, source, reason). Applying is a separate, reversible step.

  python scripts/photo_fix.py [--limit 20] [--ids 1,2] [--steps retail,clean] [--max-usd 5] [--dry-run]
"""
import argparse, base64, io, json, os, re, sys, time, urllib.parse, urllib.request
from datetime import datetime, timezone
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from catalog_common import ROOT, load_catalog  # noqa: E402

OUT = os.path.join(ROOT, "out", "photo-fix")
LOG = os.path.join(ROOT, "data", "photo_fix.json")
SITE = "https://www.puroclassico.com"
RETAILERS = ["ssense.com", "farfetch.com", "mrporter.com", "endclothing.com", "mytheresa.com", "goat.com", "stockx.com",
             "net-a-porter.com", "luisaviaroma.com", "matchesfashion.com", "selfridges.com", "harrods.com", "flannels.com",
             "nike.com", "adidas.com", "newbalance.com", "ralphlauren.com", "acnestudios.com", "fearofgod.com",
             "stoneisland.com", "cpcompany.com", "moncler.com", "arcteryx.com", "thenorthface.com", "carhartt-wip.com"]
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"
PICK_MODEL = os.environ.get("PHOTO_FIX_MODEL", "claude-haiku-5-5")
EDIT_MODEL = os.environ.get("PHOTO_FIX_EDIT_MODEL", "gemini-2.5-flash-image")
SIZE = 1200
spent = 0.0


def now(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load(p, d):
    try:
        with open(p, encoding="utf-8") as f: return json.load(f)
    except Exception: return d


def http(url, headers=None, data=None, timeout=40):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r: return r.read()


def img_of(url):
    im = Image.open(io.BytesIO(http(url))); im.load(); return im


def b64(im, side=640):
    im = im.convert("RGBA"); im.thumbnail((side, side))
    bg = Image.new("RGB", im.size, (255, 255, 255)); bg.paste(im, (0, 0), im)
    buf = io.BytesIO(); bg.save(buf, "JPEG", quality=85); return base64.b64encode(buf.getvalue()).decode()


def claude(content, max_tokens=400):
    """One vision call; returns the parsed JSON object from the answer."""
    global spent
    body = json.dumps({"model": PICK_MODEL, "max_tokens": max_tokens, "messages": [{"role": "user", "content": content}]}).encode()
    r = json.loads(http("https://api.anthropic.com/v1/messages", {"x-api-key": os.environ["ANTHROPIC_API_KEY"],
        "anthropic-version": "2023-06-01", "content-type": "application/json"}, body, 120))
    u = r.get("usage") or {}; spent += (u.get("input_tokens", 0) * 1.0 + u.get("output_tokens", 0) * 5.0) / 1e6
    txt = "".join(c.get("text", "") for c in r.get("content", []))
    m = re.search(r"\{.*\}", txt, re.S)
    return json.loads(m.group(0)) if m else {}


def pic(im): return {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64(im)}}


def query(p, ai):
    q = f"{p.get('brand') or ''} {ai.get('title_base') or p.get('title')} {ai.get('colour') or ''}"
    return " ".join(dict.fromkeys(q.split()))


def retail(p, ai, cur):
    """Step 1: candidates from official retailers only, then a strict same-design pick."""
    cands = []
    for grp in (RETAILERS[:9], RETAILERS[9:17], RETAILERS[17:]):
        q = query(p, ai) + " (" + " OR ".join("site:" + s for s in grp) + ")"
        try:
            d = json.loads(http("https://api.search.brave.com/res/v1/images/search?count=20&safesearch=strict&q=" + urllib.parse.quote(q),
                                {"X-Subscription-Token": os.environ["BRAVE_API_KEY"], "Accept": "application/json"}))
        except Exception as e:
            print("  brave:", str(e)[:80]); continue
        for r in d.get("results", []):
            src = (r.get("source") or "").lower().replace("www.", "")
            u = (r.get("properties") or {}).get("url")
            if not u or not any(src == s or src.endswith("." + s) for s in RETAILERS): continue
            try:
                im = img_of(u)
                if min(im.size) >= 600: cands.append((im, u, src))
            except Exception: pass
            if len(cands) >= 6: break
        if len(cands) >= 6: break
    if not cands: return None, "no retailer photos"
    content = [{"type": "text", "text": "Image 0 is the item we sell (it may have a busy background, text, tags or a model). "
               f"It is listed as: {p.get('title')} by {p.get('brand')}. Images 1-{len(cands)} are retailer photos."}, pic(cur)]
    for i, (im, _, _) in enumerate(cands, 1):
        content += [{"type": "text", "text": f"Image {i}:"}, pic(im)]
    content.append({"type": "text", "text": "Pick the candidate that shows EXACTLY the same design as image 0: same logos and "
        "their size and placement, same prints, same pockets, zips, collar and cut, same colour. A similar item from the same "
        "brand is NOT a match. It must also be a clean product-only photo: no person wearing it, no hands, no text overlay, "
        "item fully in frame. Answer only JSON: {\"choice\": <number or 0 for none>, \"same_design\": bool, \"same_colour\": bool, "
        "\"clean\": bool, \"confidence\": 0-1, \"reason\": \"short\"}"})
    v = claude(content)
    k = int(v.get("choice") or 0)
    if k and v.get("same_design") and v.get("same_colour") and v.get("clean") and float(v.get("confidence") or 0) >= 0.85:
        im, u, src = cands[k - 1]
        return {"im": im, "source": u, "site": src, "verdict": v}, None
    return None, "no exact match: " + str(v.get("reason") or "")[:120]


def gemini_edit(cur):
    """Step 3: the image model removes clutter from the real photo; returns a PIL image or None."""
    prompt = ("Edit this product photo. Remove every piece of text, watermark, logo overlay that is not printed on the item, "
              "price tag, hang tag, hanger, hand, person and background clutter. Keep the product itself EXACTLY the same: "
              "same shape, colour, fabric, printed logos and details, same angle. Show the full item centred on a plain pure "
              "white background, like a clean e-commerce product photo. Do not add anything.")
    body = json.dumps({"contents": [{"parts": [{"text": prompt}, {"inline_data": {"mime_type": "image/jpeg", "data": b64(cur, 1024)}}]}],
                       "generationConfig": {"responseModalities": ["IMAGE"]}}).encode()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{EDIT_MODEL}:generateContent"
    r = json.loads(http(url, {"x-goog-api-key": os.environ["GEMINI_API_KEY"], "content-type": "application/json"}, body, 180))
    global spent; spent += 0.04
    for c in r.get("candidates", []):
        for part in (c.get("content") or {}).get("parts", []):
            d = part.get("inline_data") or part.get("inlineData")
            if d and d.get("data"): return Image.open(io.BytesIO(base64.b64decode(d["data"])))
    return None


def clean(p, cur):
    try:
        ed = gemini_edit(cur)
    except Exception as e:
        return None, "edit failed: " + str(e)[:100]
    if ed is None: return None, "edit returned no image"
    v = claude([{"type": "text", "text": "Image A is the original photo of a product, image B is an AI edit of it."}, pic(cur), pic(ed),
                {"type": "text", "text": "Is the product in B exactly the same item as in A (same shape, colour, printed logos and "
                 "their placement, details), with nothing invented or lost, and is B a clean product-only photo (no text, "
                 "tags, hangers, hands, people)? Answer only JSON: {\"same_item\": bool, \"clean\": bool, \"confidence\": 0-1, "
                 "\"reason\": \"short\"}"}])
    if v.get("same_item") and v.get("clean") and float(v.get("confidence") or 0) >= 0.85:
        return {"im": ed, "source": EDIT_MODEL, "site": "ai-cleanup", "verdict": v}, None
    return None, "edit rejected: " + str(v.get("reason") or "")[:120]


_sess = None
def cutout(im):
    global _sess
    from rembg import remove, new_session
    if _sess is None: _sess = new_session("isnet-general-use")
    rgba = remove(im.convert("RGB"), session=_sess).convert("RGBA")
    box = rgba.getchannel("A").point(lambda v: 255 if v >= 24 else 0).getbbox()
    if not box: return None
    item = rgba.crop(box); s = SIZE * 0.86 / max(item.size)
    item = item.resize((max(1, round(item.width * s)), max(1, round(item.height * s))), Image.LANCZOS)
    canvas = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    canvas.alpha_composite(item, ((SIZE - item.width) // 2, (SIZE - item.height) // 2))
    return canvas


def weak(items):
    ai = (load(os.path.join(ROOT, "data", "catalog_ai.json"), {}) or {}).get("items") or {}
    ph = (load(os.path.join(ROOT, "data", "photo_hidden.json"), {}) or {}).get("why") or {}
    st = (load(os.path.join(ROOT, "data", "stats.json"), {}) or {}).get("p") or {}
    views = lambda i: (st.get(i) or [0, 0])[1] if isinstance(st.get(i), list) and len(st.get(i)) > 1 else 0
    out = []
    for p in items:
        i = str(p.get("id")); why = [w for w in (ph.get(i) or []) if w not in ("duplicate",)]
        issues = why or (ai.get(i) or {}).get("photo_issues") or []
        if issues: out.append((i, issues))
    out.sort(key=lambda x: -views(x[0]))
    return out, ai


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=20); ap.add_argument("--ids", default="")
    ap.add_argument("--steps", default="retail,clean"); ap.add_argument("--max-usd", type=float, default=5)
    ap.add_argument("--redo", action="store_true"); ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    _, items, _, _ = load_catalog(); by = {str(p.get("id")): p for p in items}
    todo, ai = weak(items)
    log = load(LOG, {"items": {}}); done = log.setdefault("items", {})
    if a.ids: todo = [(i, ["asked"]) for i in a.ids.replace(" ", "").split(",") if i in by]
    elif not a.redo: todo = [t for t in todo if t[0] not in done]
    todo = todo[:a.limit]
    print(f"{len(todo)} finds with weak photos to try (steps: {a.steps})")
    if a.dry_run:
        for i, w in todo: print(" ", i, by[i].get("title"), w)
        return 0
    os.makedirs(OUT, exist_ok=True); steps = a.steps.split(","); pairs = []
    for i, issues in todo:
        if spent >= a.max_usd: print("budget reached"); break
        p = by[i]; u = p.get("img") or ""; u = u if u.startswith("http") else SITE + u
        rec = {"date": now(), "issues": issues, "title": p.get("title")}
        try:
            cur = img_of(u).convert("RGBA"); got, notes = None, []
            if "retail" in steps:
                got, why = retail(p, ai.get(i) or {}, cur); why and notes.append(why)
            if not got and "clean" in steps:
                got, why = clean(p, cur); why and notes.append(why)
            if got:
                out = cutout(got["im"])
                if out is None: raise RuntimeError("cut-out found no item")
                f = os.path.join(OUT, f"{i}.webp"); out.save(f, "WEBP", quality=90, method=6)
                rec.update(status="ok", step=got["site"] == "ai-cleanup" and "clean" or "retail", source=got["source"],
                           site=got["site"], verdict=got["verdict"], file=os.path.relpath(f, ROOT), notes=notes)
                pairs.append((p, cur, out, rec["step"], got["site"]))
            else:
                rec.update(status="skipped", notes=notes)
        except Exception as e:
            rec.update(status="error", notes=[str(e)[:160]])
        done[i] = rec
        print(f"  {i} {rec['status']:8} {rec.get('step', '')} {'; '.join(rec.get('notes') or [])[:110]}  (${spent:.2f})")
        with open(LOG, "w", encoding="utf-8") as fh: json.dump(log, fh, indent=1, ensure_ascii=False)
    if pairs: sheet(pairs)
    n = sum(1 for i, _ in todo if done.get(i, {}).get("status") == "ok")
    print(f"done: {n} of {len(todo)} fixed, spent about ${spent:.2f}")
    return 0


def sheet(pairs, T=360):
    s = Image.new("RGB", (2 * T + 60, len(pairs) * (T + 44) + 20), (20, 20, 22)); d = ImageDraw.Draw(s)
    for r, (p, cur, out, step, site) in enumerate(pairs):
        y = 10 + r * (T + 44); d.text((20, y), f"{p.get('id')}  {p.get('title')}   [{step}: {site}]", fill=(220, 220, 220))
        for k, im in enumerate((cur, out)):
            t = im.copy(); t.thumbnail((T, T)); bg = Image.new("RGB", (T, T), (34, 34, 38))
            bg.paste(t, ((T - t.width) // 2, (T - t.height) // 2), t); s.paste(bg, (20 + k * (T + 20), y + 20))
    s.save(os.path.join(OUT, "sheet.jpg"), quality=85)


if __name__ == "__main__":
    sys.exit(main())
