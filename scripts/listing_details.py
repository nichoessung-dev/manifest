# -*- coding: utf-8 -*-
"""Colours, sizes, a photo per colour and the seller's size chart for Weidian finds (owner, 15 Nov 2026: "when they
swap color the picture also swaps to that color", "ask users for height and weight and use the seller's size chart").

Per find (Weidian only, 93% of the catalogue), read-only, one request at a time with a pause:
  1. getItemSkuInfo: the option lists (colour / size) with each option's photo, and the SKUs (colour;size + stock)
  2. getDetailDesc: the description images, where sellers put their size chart
  3. one vision call (claude-haiku-5-5): small thumbnails of the description images + the option names ->
     which image is the size chart (or none) and the colour names in English
  4. only if there is a chart: one vision call on that image at full size -> the table as numbers, every length in
     cm and every weight in kg (Chinese charts often give weight in jin, half a kilo, sometimes labelled "G")
Writes data/listing_details.json {"items": {id: {...}}} and out/listing-details/report.html (every find: colour photos,
sizes, the chart image next to the table read from it) for a human check. Nothing on the site changes.

  python scripts/listing_details.py [--limit 50] [--ids 1,2] [--max-usd 3] [--redo]
"""
import argparse, base64, io, json, os, re, sys, time, urllib.parse, urllib.request
from datetime import datetime, timezone
from html import escape
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from catalog_common import ROOT, load_catalog  # noqa: E402

LOG = os.path.join(ROOT, "data", "listing_details.json")
OUT = os.path.join(ROOT, "out", "listing-details")
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
H = {"User-Agent": UA, "Referer": "https://weidian.com/"}
MODEL = os.environ.get("LISTING_MODEL", "claude-haiku-5-5")
PAUSE = 1.0
spent = 0.0

COLOUR_ZH = {"黑": "Black", "白": "White", "灰": "Grey", "红": "Red", "蓝": "Blue", "藏青": "Navy", "藏蓝": "Navy", "深蓝": "Navy",
             "绿": "Green", "黄": "Yellow", "粉": "Pink", "紫": "Purple", "棕": "Brown", "咖": "Brown", "卡其": "Khaki",
             "米": "Beige", "杏": "Apricot", "橙": "Orange", "银": "Silver", "金": "Gold", "军绿": "Olive", "酒红": "Burgundy"}


def now(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def wd(api, param):
    url = f"https://thor.weidian.com/detail/{api}/1.0?param=" + urllib.parse.quote(json.dumps(param))
    for wait in (0, 5, 15, 40):
        if wait: time.sleep(wait)
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=25) as r: d = json.load(r)
            if (d.get("status") or {}).get("code") == 0: return d.get("result") or {}
        except Exception: pass
    return None


def fetch_img(u):
    with urllib.request.urlopen(urllib.request.Request(u, headers=H), timeout=25) as r:
        im = Image.open(io.BytesIO(r.read())); im.load(); return im.convert("RGB")


def jpg64(im, side):
    im = im.copy(); im.thumbnail((side, side * 3)); b = io.BytesIO(); im.save(b, "JPEG", quality=82)
    return base64.b64encode(b.getvalue()).decode()


def claude(content, max_tokens=900):
    global spent
    body = json.dumps({"model": MODEL, "max_tokens": max_tokens, "messages": [{"role": "user", "content": content}]}).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, headers={
        "x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01", "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r: d = json.load(r)
    u = d.get("usage") or {}; spent += (u.get("input_tokens", 0) * 1.0 + u.get("output_tokens", 0) * 5.0) / 1e6
    txt = "".join(c.get("text", "") for c in d.get("content", []))
    m = re.search(r"\{.*\}", txt, re.S)
    return json.loads(m.group(0)) if m else {}


def colour_guess(zh):
    for k in sorted(COLOUR_ZH, key=len, reverse=True):
        if k in zh: return COLOUR_ZH[k]
    return None


def options(res):
    """{'colour': [{'zh','img'}], 'size': [...]} from attrList; the attribute with photos is the colour one."""
    col, size = [], []
    for a in res.get("attrList") or []:
        vals = [{"zh": str(v.get("attrValue") or "").strip(), "img": v.get("img") or ""} for v in a.get("attrValues") or []]
        t = str(a.get("attrTitle") or "")
        if any(v["img"] for v in vals) or re.search(r"颜色|颜|色|colou?r|款", t, re.I): col += vals
        else: size += vals
    skus = []
    for s in res.get("skuInfos") or []:
        si = s.get("skuInfo") if isinstance(s.get("skuInfo"), dict) else s
        skus.append({"t": si.get("title"), "stock": si.get("stock")})
    return col, size, skus


def find_chart(desc, col, p):
    """One call: which description image is the size chart, and English names for the colour options."""
    thumbs = []
    for k, u in enumerate(desc[:24]):
        try: thumbs.append((k, fetch_img(u)))
        except Exception: pass
    content = [{"type": "text", "text": f"Listing: {p.get('title')} ({p.get('brand')}). These are the listing's description images, numbered."}]
    for k, im in thumbs:
        content += [{"type": "text", "text": f"Image {k}:"}, {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": jpg64(im, 256)}}]
    content.append({"type": "text", "text": "1) Which image contains a size chart (a table of sizes with measurements)? Give its number, or -1.\n"
        "2) Translate these colour option names to short English colour names (keep extra words like 'pants' in English): "
        + json.dumps([c["zh"] for c in col], ensure_ascii=False)
        + '\nAnswer only JSON: {"chart": <number>, "colours": ["...", ...]}'})
    return claude(content, 400), dict(thumbs)


def read_chart(im):
    w, h = im.size
    if max(w, h) > 1600: im = im.copy(); im.thumbnail((1600, 1600))
    return claude([{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": jpg64(im, 1600)}},
        {"type": "text", "text": "Read this clothing/shoe size chart. Return every size row with its measurements. Convert all lengths to "
         "cm. Weights: Chinese charts often give weight in jin (斤, half a kilogram), sometimes labelled 'G' or '斤'; ranges like 90-130 "
         "for an adult are jin, so divide by 2. Give weight in kg. Use these keys when present: shoulder, chest, length, sleeve, waist, "
         "hip, inseam, foot_length, height_min, height_max, weight_min, weight_max. measured: 'flat' when chest/waist are the garment laid "
         "flat (half the way round), 'round' when all the way round, 'body' when they are body measurements. Answer only JSON, no other "
         "text: {\"unit_note\": \"a few words\", \"measured\": \"flat|round|body\", \"rows\": [{\"size\": \"S\", \"chest\": 120, ...}], "
         "\"confidence\": 0-1}"}], 2000)


def report(rows):
    h = ["<!doctype html><meta charset=utf-8><title>Listing details test</title><style>body{font:14px system-ui,sans-serif;background:#111;color:#eee;margin:24px}"
         ".f{border:1px solid #333;border-radius:12px;padding:16px;margin:0 0 18px}.c{display:inline-block;margin:4px;text-align:center;font-size:12px}"
         ".c img{width:110px;height:110px;object-fit:contain;background:#ddd;border-radius:8px;display:block}table{border-collapse:collapse;margin-top:8px}"
         "td,th{border:1px solid #444;padding:3px 8px}.ch{max-width:520px;display:block;margin-top:8px;border-radius:8px}.m{color:#999}</style>"]
    for i, r in rows:
        h.append(f"<div class=f><b>{escape(r.get('title') or i)}</b> <span class=m>{i}</span><div class=m>sizes: {escape(', '.join(r.get('sizes') or []) or 'none')}"
                 f" | chart: {escape(r.get('chart_status', ''))}</div>")
        for c in r.get("colours") or []:
            h.append(f"<span class=c><img src='{escape(c.get('img') or '')}' referrerpolicy=no-referrer>{escape(c.get('en') or c.get('zh'))}<br><span class=m>{escape(c.get('zh'))}</span></span>")
        ch = r.get("chart") or {}
        if ch.get("rows"):
            keys = [k for k in ["size", "shoulder", "chest", "length", "sleeve", "waist", "hip", "inseam", "foot_length", "height_min", "height_max", "weight_min", "weight_max"]
                    if any(k in row for row in ch["rows"])]
            h.append("<table><tr>" + "".join(f"<th>{k}</th>" for k in keys) + "</tr>" + "".join(
                "<tr>" + "".join(f"<td>{escape(str(row.get(k, '')))}</td>" for k in keys) + "</tr>" for row in ch["rows"]) + "</table>")
            h.append(f"<div class=m>{escape(str(ch.get('unit_note', '')))} | confidence {ch.get('confidence')}</div>")
        if r.get("chart_img"): h.append(f"<img class=ch src='{escape(r['chart_img'])}' referrerpolicy=no-referrer>")
        h.append("</div>")
    os.makedirs(OUT, exist_ok=True)
    open(os.path.join(OUT, "report.html"), "w", encoding="utf-8").write("".join(h))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=50); ap.add_argument("--ids", default="")
    ap.add_argument("--max-usd", type=float, default=3); ap.add_argument("--redo", action="store_true")
    ap.add_argument("--done", default="", help="also skip the ids in this file's items (data/sizes.json)")
    ap.add_argument("--max-minutes", type=float, default=0)
    a = ap.parse_args()
    _, items, _, _ = load_catalog()
    st = (json.load(open(os.path.join(ROOT, "data", "stats.json"))) if os.path.exists(os.path.join(ROOT, "data", "stats.json")) else {}).get("p") or {}
    views = lambda i: (st.get(i) or [0, 0])[1] if isinstance(st.get(i), list) and len(st.get(i)) > 1 else 0
    wdn = [p for p in items if p.get("platform") == "weidian"]
    log = json.load(open(LOG)) if os.path.exists(LOG) else {"items": {}}
    done = log.setdefault("items", {})
    skip = set()
    if a.done and os.path.exists(a.done):
        try: skip = set((json.load(open(a.done)).get("items") or {}).keys())
        except Exception: pass
    t0 = time.time()
    if a.ids:
        want = set(a.ids.replace(" ", "").split(",")); todo = [p for p in wdn if str(p["id"]) in want]
    else:
        todo = sorted((p for p in wdn if a.redo or (str(p["id"]) not in done and str(p["id"]) not in skip)), key=lambda p: -views(str(p["id"])))
    todo = todo[:a.limit]
    print(f"{len(todo)} Weidian finds")
    rows = []
    for p in todo:
        if spent >= a.max_usd: print("budget reached, limit reached"); break
        if a.max_minutes and time.time() - t0 > a.max_minutes * 60: print("time up, limit reached"); break
        i = str(p["id"]); iid = str(p.get("itemId") or i)
        rec = {"date": now(), "title": p.get("title")}
        res = wd("getItemSkuInfo", {"itemId": iid}); time.sleep(PAUSE)
        if res is None: rec["status"] = "error"; done[i] = rec; continue
        col, size, skus = options(res)
        dres = wd("getDetailDesc", {"vItemId": iid}) or {}; time.sleep(PAUSE)
        desc = [x.get("url") for x in ((dres.get("item_detail") or {}).get("desc_content") or []) if x.get("url")]
        rec.update(sizes=[s["zh"] for s in size], skus=skus, n_desc=len(desc))
        try:
            v, thumbs = find_chart(desc, col, p) if (desc or col) else ({}, {})
        except Exception as e:
            v, thumbs = {}, {}; rec["note"] = "pick failed: " + str(e)[:80]
        names = v.get("colours") or []
        rec["colours"] = [{"zh": c["zh"], "en": (names[k] if k < len(names) and names[k] else colour_guess(c["zh"]) or c["zh"]), "img": c["img"]} for k, c in enumerate(col)]
        k = v.get("chart", -1)
        if isinstance(k, int) and 0 <= k < len(desc):
            rec["chart_img"] = desc[k]
            try:
                ch = read_chart(fetch_img(desc[k])); rec["chart"] = ch
                rec["chart_status"] = f"read ({len(ch.get('rows') or [])} sizes)" if ch.get("rows") else "found, unreadable"
            except Exception as e:
                rec["chart_status"] = "read failed: " + str(e)[:60]
        else:
            rec["chart_status"] = "no chart in listing"
        rec["status"] = "ok"; done[i] = rec; rows.append((i, rec))
        print(f"  {i} {len(rec['colours'])} colours ({sum(1 for c in rec['colours'] if c['img'])} with photo), {len(rec['sizes'])} sizes, chart: {rec['chart_status']}  (${spent:.2f})")
        with open(LOG, "w", encoding="utf-8") as f: json.dump(log, f, ensure_ascii=False, indent=1)
    report(rows)
    ok = [r for _, r in rows]
    print(f"done: {len(ok)} finds | colour photos for {sum(1 for r in ok if any(c['img'] for c in r['colours']))} | "
          f"2+ colours {sum(1 for r in ok if len(r['colours']) > 1)} | chart read {sum(1 for r in ok if (r.get('chart') or {}).get('rows'))} | spent ${spent:.2f}")


if __name__ == "__main__":
    sys.exit(main())
