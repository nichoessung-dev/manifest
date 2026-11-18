# -*- coding: utf-8 -*-
"""Match the friend's Weidian listings (data/friend_finds.json) to the finds already on the site (18 Nov 2026).

The friend is the partner of the approved partner swaps. His listings are items the site already lists from other
sellers, so each one should take over the matching find: a match becomes an approved partner swap (scripts/friend_swaps.py),
and the find keeps its views and popularity while its Buy link goes to his listing.

Per listing, one at a time with a pause (resumable, data/friend_match.json keeps every listing's state):
  1. Weidian getItemSkuInfo: Chinese title, main photo, price. Gone or sold-out listings are skipped.
  2. A vision call names it: brand, category, item type, colour, an English title (claude-haiku-5-5).
  3. Candidates: finds already on the site, scored on brand, category, item type (data/catalog_ai.json "item"), colour
     and title words; the best 8 (score threshold) go on.
  4. A second vision call sees his photo and the candidates' photos and picks the one that is the SAME product (same
     design, logos, prints and colour) or none. Accepted at confidence 0.85 or more.
Writes data/friend_match.json {"items": {item_id: {status, cls, cands, find, conf, reason, price}}} and
out/friend-match/report.html (his photo next to the chosen find) for spot checks. Nothing on the site changes here.

  python scripts/match_friend.py [--max-minutes 50] [--limit N] [--max-usd 15] [--redo-errors]
"""
import argparse, base64, io, json, os, re, sys, time, urllib.parse, urllib.request
from html import escape
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from catalog_common import ROOT, load_catalog  # noqa: E402

LIST = os.path.join(ROOT, "data", "friend_finds.json")
STATE = os.path.join(ROOT, "data", "friend_match.json")
OUT = os.path.join(ROOT, "out", "friend-match")
SITE = "https://www.puroclassico.com"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
H = {"User-Agent": UA, "Referer": "https://weidian.com/"}
CATS = ["Tops", "Outerwear", "Shoes", "Pants", "Shorts", "Bags", "Accessories", "Headwear", "Toys"]
MODEL = os.environ.get("FRIEND_MODEL", "claude-haiku-5-5")
ALIAS = {"essential": "essentials", "arcteryx": "arc'teryx", "cp": "cp company", "polo": "ralph lauren", "polo ralph lauren": "ralph lauren",
         "comme des garçons": "comme des garcons", "cdg": "comme des garcons", "ami paris": "ami", "carhart": "carhartt", "fear of god essentials": "essentials"}
spent = 0.0


def wd(item_id):
    url = "https://thor.weidian.com/detail/getItemSkuInfo/1.0?param=" + urllib.parse.quote(json.dumps({"itemId": str(item_id)}))
    for wait in (0, 5, 15, 40):
        if wait: time.sleep(wait)
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=25) as r: d = json.load(r)
            if (d.get("status") or {}).get("code") == 0: return d.get("result") or {}
        except Exception: pass
    return None


def get_img(u, headers=H):
    with urllib.request.urlopen(urllib.request.Request(u, headers=headers), timeout=40) as r:
        im = Image.open(io.BytesIO(r.read())); im.load(); return im


def jpg64(im, side=448):
    im = im.convert("RGBA"); im.thumbnail((side, side))
    bg = Image.new("RGB", im.size, (255, 255, 255)); bg.paste(im, (0, 0), im)
    b = io.BytesIO(); bg.save(b, "JPEG", quality=84); return base64.b64encode(b.getvalue()).decode()


def claude(content, max_tokens=400):
    global spent
    body = json.dumps({"model": MODEL, "max_tokens": max_tokens, "messages": [{"role": "user", "content": content}]}).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, headers={
        "x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01", "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r: d = json.load(r)
    u = d.get("usage") or {}; spent += (u.get("input_tokens", 0) * 1.0 + u.get("output_tokens", 0) * 5.0) / 1e6
    txt = "".join(c.get("text", "") for c in d.get("content", []))
    m = re.search(r"\{.*\}", txt, re.S)
    try: return json.loads(m.group(0)) if m else {"_raw": txt[:240], "_stop": d.get("stop_reason")}
    except Exception: return {"_raw": txt[:240], "_stop": d.get("stop_reason")}


def pic(im): return {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": jpg64(im)}}


def classify(im, zh):
    return claude([pic(im), {"type": "text", "text":
        "A product listing from a Chinese Weidian store. Chinese title: " + json.dumps(zh, ensure_ascii=False) + ". Name the item in "
        "English. brand: the brand whose design it is (from logos or the title; football kits: the kit maker, e.g. Nike or Adidas), '' "
        "if none. cat: exactly one of " + json.dumps(CATS) + ". item: the item type (T-Shirt, Hoodie, Jersey, Belt, Sneakers ...). colour: "
        "main colour. title: 'Brand Item Colour' style, 2-7 words, football kits as 'Argentina 2026 Home Jersey'. "
        'Answer only JSON: {"brand":"","cat":"","item":"","colour":"","title":""}'}])


def words(s): return set(w for w in re.findall(r"[a-z0-9]+", str(s).lower()) if len(w) > 1)


def nb(b): b = str(b or "").strip().lower(); return ALIAS.get(b, b)


def candidates(cls, finds, ai, n=8):
    b, cat, item, col, tw = nb(cls.get("brand")), cls.get("cat"), str(cls.get("item") or "").lower(), str(cls.get("colour") or "").lower(), words(cls.get("title"))
    out = []
    for p in finds:
        if p.get("cat") != cat: continue
        pb = nb(p.get("brand")); a = ai.get(str(p["id"])) or {}
        sc = 0.0
        if b and pb == b: sc += 3
        elif b and pb and pb != b: continue           # a different brand is never the same product
        pi = str(a.get("item") or "").lower()
        if item and pi and (item in pi or pi in item): sc += 2
        pc = str(a.get("colour") or "").lower()
        if col and pc and (col in pc or pc in col): sc += 1
        pw = words(p.get("title")); sc += 3 * len(tw & pw) / max(1, len(tw | pw))
        if sc >= 3.5: out.append((sc, p))
    out.sort(key=lambda x: -x[0])
    return [p for _, p in out[:n]]


def pick(im, cands, cls):
    content = [{"type": "text", "text": f"Image 0 is a product from a partner store ({cls.get('title')}). Images 1-{len(cands)} are products "
                "already on our site."}, pic(im)]
    for i, (p, cim) in enumerate(cands, 1):
        content += [{"type": "text", "text": f"Image {i}: {p.get('title')}"}, pic(cim)]
    content.append({"type": "text", "text": "Which candidate is the SAME product as image 0: the same design (same logos and their placement, "
        "same prints, same cut and details) in the same colour? Photos can differ (angle, model, background); the product must not. "
        "A similar item of the same brand is NOT the same product. Answer only JSON: "
        '{"choice": <number, 0 for none>, "same_design": true/false, "same_colour": true/false, "confidence": 0-1, "reason": "short"}'})
    return claude(content, 300)


def report(rows):
    h = ["<!doctype html><meta charset=utf-8><title>Friend matches</title><style>body{font:14px system-ui,sans-serif;background:#111;color:#eee;margin:20px}"
         ".r{display:flex;gap:14px;align-items:center;border-bottom:1px solid #333;padding:10px 0}img{width:150px;height:150px;object-fit:contain;background:#ddd;border-radius:8px}"
         ".m{color:#999;font-size:12px}</style>"]
    for i, r in rows:
        f = r.get("find_p") or {}
        h.append(f"<div class=r><img src='{escape(r.get('pic') or '')}' referrerpolicy=no-referrer><img src='{escape(SITE + (f.get('img') or ''))}'>"
                 f"<div><b>{escape(r['cls'].get('title',''))}</b> -> {escape(f.get('title',''))}<div class=m>{i} -> {escape(str(r.get('find')))} | conf {r.get('conf')} | {escape(r.get('reason',''))}</div></div></div>")
    os.makedirs(OUT, exist_ok=True); open(os.path.join(OUT, "report.html"), "w", encoding="utf-8").write("".join(h))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-minutes", type=float, default=50); ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--max-usd", type=float, default=15); ap.add_argument("--pause", type=float, default=0.6)
    ap.add_argument("--redo-errors", action="store_true")
    a = ap.parse_args()
    ids = json.load(open(LIST, encoding="utf-8"))["ids"]
    st = json.load(open(STATE, encoding="utf-8")) if os.path.exists(STATE) else {"items": {}}
    items = st.setdefault("items", {})
    _, cat_items, _, _ = load_catalog()
    ai = (json.load(open(os.path.join(ROOT, "data", "catalog_ai.json"), encoding="utf-8")) or {}).get("items") or {}
    swaps = json.load(open(os.path.join(ROOT, "data", "link_swaps.json"), encoding="utf-8"))
    taken_items = {v[1] for v in (swaps.get("swaps") or {}).values()}
    finds = [p for p in cat_items if p.get("img")]
    done_states = ("matched", "nomatch", "gone", "already")
    todo = [x for x in ids if (items.get(x) or {}).get("status") not in done_states and (a.redo_errors or (items.get(x) or {}).get("status") != "error")]
    print(f"friend listings {len(ids)}, to do {len(todo)}, finds on the site {len(finds)}")
    t0, n, rows, img_cache = time.time(), 0, [], {}
    for x in todo:
        if time.time() - t0 > a.max_minutes * 60 or (a.limit and n >= a.limit) or spent >= a.max_usd:
            print("time, count or budget limit reached; the next run goes on"); break
        n += 1; rec = {"date": time.strftime("%Y-%m-%d")}
        try:
            if x in taken_items: rec.update(status="already", reason="already a partner swap"); items[x] = rec; continue
            res = wd(x); time.sleep(a.pause)
            if res is None: raise RuntimeError("weidian did not answer")
            stock = res.get("itemStock")
            if not (res.get("itemTitle") or res.get("itemMainPic")) or (isinstance(stock, (int, float)) and stock <= 0):
                rec.update(status="gone", reason="listing gone or sold out"); items[x] = rec; continue
            im = get_img(res["itemMainPic"]); rec["pic"] = res["itemMainPic"]
            cls = classify(im, res.get("itemTitle") or ""); rec["cls"] = cls
            if "_raw" in cls: raise RuntimeError("naming failed: " + str(cls.get("_raw")))
            cs = candidates(cls, finds, ai)
            rec["cands"] = [str(p["id"]) for p in cs]
            if not cs: rec.update(status="nomatch", reason="no candidate"); items[x] = rec; continue
            loaded = []
            for p in cs:
                try:
                    u = p["img"] if p["img"].startswith("http") else SITE + "/cdn-cgi/image/width=448,format=webp" + p["img"]
                    if u not in img_cache: img_cache[u] = get_img(u, {"User-Agent": UA})
                    loaded.append((p, img_cache[u]))
                except Exception: pass
            if not loaded: raise RuntimeError("candidate photos failed")
            v = pick(im, loaded, cls); k = int(v.get("choice") or 0)
            ok = k and 1 <= k <= len(loaded) and v.get("same_design") and v.get("same_colour") and float(v.get("confidence") or 0) >= 0.85
            if ok:
                f = loaded[k - 1][0]
                rec.update(status="matched", find=str(f["id"]), conf=v.get("confidence"), reason=str(v.get("reason") or "")[:160])
                rows.append((x, dict(rec, find_p=f)))
            else:
                rec.update(status="nomatch" if "_raw" not in v else "error", conf=v.get("confidence"), reason=str(v.get("reason") or v.get("_raw") or "")[:240])
        except Exception as ex:   # noqa: BLE001
            rec.update(status="error", reason=str(ex)[:160])
        items[x] = rec
        if n % 25 == 0:
            print(f"  {n} done, ${spent:.2f}, {time.time() - t0:.0f} s")
            json.dump(st, open(STATE, "w", encoding="utf-8"), ensure_ascii=False)
        if len(img_cache) > 400: img_cache.clear()
    json.dump(st, open(STATE, "w", encoding="utf-8"), ensure_ascii=False)
    report(rows)
    from collections import Counter
    cnt = Counter(r.get("status") for r in items.values())
    left = sum(1 for x in ids if (items.get(x) or {}).get("status") not in done_states)
    print(f"done: {n} this run; states {dict(cnt)}; left {left} (${spent:.2f}, {time.time() - t0:.0f} s)")


if __name__ == "__main__":
    main()
