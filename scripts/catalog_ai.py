# -*- coding: utf-8 -*-
"""Vision labels for every find: right category, a short clear title, and what is wrong with the photo.

Per find it sends the main photo (on white, 768 px) + brand + current title + category + the seller's variant names to a
vision model and gets back JSON:
  cat, item, model_name (the product model), model_source, title_base, colour, cat_confidence, title_confidence, confidence,
  is_clean_product_photo, photo_issues[], has_text_or_watermark, is_collage, is_set, brand_check, note
Nothing on the site changes here. Results go to data/catalog_ai.json ("items": id -> result + model + date); a rerun
skips ids already there (unless --redo), so a run can stop at any time and the next one carries on.
scripts/apply_catalog_ai.py later applies only high-confidence, rule-passing changes.

  python scripts/catalog_ai.py [--limit 500] [--ids 123,456 | --ids-file f.txt] [--order best|catalog|suspects]
                               [--model claude-haiku-5-5] [--engine claude|gemini|openai] [--workers 6]
                               [--max-minutes 50] [--max-usd 20] [--redo] [--recheck-below 0.7]
                               [--dry-run] [--mock] [--index index.html] [--out data/catalog_ai.json]

  --dry-run   no API calls: picks the finds, builds one real request (printed, image size shown) and prints the cost estimate
  --mock      no API calls: fake answers from the current title, to test the whole write/resume path
              (writes to data/catalog_ai.mock.json unless --out is given; apply_catalog_ai.py ignores model "mock")
  --recheck-below X  re-label finds whose saved confidence is below X (use with a stronger --model, e.g. gemini-2.5-pro)

Engines (the engine follows from --model when --engine is not given):
  claude  (default) Anthropic Messages API through the official SDK (pip install anthropic), structured JSON output,
          model claude-haiku-5-5; a low-confidence recheck can use --model claude-sonnet-5-5. Env ANTHROPIC_API_KEY.
  gemini  Gemini REST generateContent (GEMINI_API_KEY).     openai  gpt-4o-mini chat completions (OPENAI_API_KEY).
Keys are read from the environment only (GitHub Actions secrets) and never printed or written.
Out of credit (HTTP 402, billing_error, insufficient_quota): the run stops at once, keeps every good label it has,
writes no error records for the unfinished finds, and exits with code 3 and a clear message.
"""
import argparse, base64, concurrent.futures as cf, io, json, os, random, re, sys, threading, time, urllib.error, urllib.request
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from catalog_common import ROOT, CATS, COLOURS, load_catalog, img_url, fetch, load_json, save_json, no_dash  # noqa: E402

GEMINI = "https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent"
OPENAI = "https://api.openai.com/v1/chat/completions"
# USD per 1M tokens (input, output incl. thinking). Override with PRICE_IN / PRICE_OUT env when prices change.
PRICES = {
    "claude-haiku-5-5": (0.10, 0.50), "claude-sonnet-5-5": (2.00, 10.0), "claude-opus-5-5": (4.00, 20.0),
    "gemini-2.5-flash": (0.30, 2.50), "gemini-2.5-flash-lite": (0.10, 0.40), "gemini-2.5-pro": (1.25, 10.0),
    "gemini-3-flash": (0.50, 3.00), "gemini-flash-latest": (0.30, 2.50), "gpt-4o-mini": (0.15, 0.60), "gpt-4o": (2.50, 10.0),
    "gpt-4.1-mini": (0.40, 1.60),
}
# per find (prompt + image, answer). Claude: a 768x768 image is about 768*768/750 = 790 tokens, plus ~1,100 prompt tokens.
EST_TOKENS = {"claude": (1900, 300), "gemini": (1150, 260), "openai": (3900, 260)}
DEFAULT_MODEL = {"claude": "claude-haiku-5-5", "gemini": "gemini-2.5-flash", "openai": "gpt-4o-mini"}


class OutOfCredit(Exception):
    """The provider says the account has no credit left: stop the whole run."""
IMG_PX = 768                                                        # Gemini: one 768x768 tile = 258 tokens
ISSUES = ["worn_by_person", "hand_in_photo", "multiple_views", "multiple_items", "collage_or_grid", "text_or_watermark",
          "hanger_or_rack", "cut_out_damage", "item_cropped", "packaging_or_box", "busy_background", "blurry_or_low_res"]
ITEMS = ["T-Shirt", "Long Sleeve", "Polo", "Shirt", "Hoodie", "Zip Hoodie", "Sweatshirt", "Sweater", "Cardigan", "Tank Top",
         "Jersey", "Tracksuit", "Set", "Jacket", "Puffer Jacket", "Down Jacket", "Vest", "Coat", "Windbreaker", "Fleece",
         "Varsity Jacket", "Bomber Jacket", "Denim Jacket", "Overshirt", "Jeans", "Pants", "Cargo Pants", "Sweatpants",
         "Track Pants", "Trousers", "Shorts", "Swim Shorts", "Sneakers", "Boots", "Loafers", "Slides", "Sandals", "Shoes",
         "Bag", "Backpack", "Tote Bag", "Crossbody Bag", "Shoulder Bag", "Belt Bag", "Duffle Bag", "Wallet", "Card Holder",
         "Pouch", "Cap", "Beanie", "Bucket Hat", "Hat", "Belt", "Watch", "Necklace", "Bracelet", "Ring", "Earrings",
         "Sunglasses", "Glasses", "Socks", "Scarf", "Gloves", "Keychain", "Phone Case", "Underwear", "Perfume", "Dress",
         "Skirt", "Toy", "Figure", "Other"]

PROMPT = """You label one find on a fashion catalogue website. You get its seller photo and what we know now.

Known now:
  brand: {brand}
  current title: {title}
  current category: {cat}
  seller's variant names (often colours): {variants}

Return JSON only, with these fields:
- cat: the one category that fits the MAIN item in the photo, from: {cats}.
  Tops = t-shirts, long sleeves, polos, shirts, hoodies (also zip hoodies), sweatshirts, sweaters, cardigans, tank tops, jerseys, tracksuits and other top+bottom sets.
  Outerwear = jackets, puffers, down jackets, coats, windbreakers, fleece jackets, gilets and vests worn over clothes, varsity and bomber jackets, overshirts.
  Pants = jeans, trousers, joggers, sweatpants, cargo pants, overalls. Shorts = shorts and swim shorts (a tee + shorts set is Tops).
  Shoes = all footwear. Bags = bags, backpacks, totes, duffles, belt bags, pouches. Headwear = caps, beanies, hats, balaclavas, headbands.
  Accessories = belts, wallets, card holders, watches, jewellery, sunglasses, socks, scarves, gloves, underwear, phone cases, perfume, home items, dresses and skirts.
  Toys = toys, figures, LEGO, collectibles.
- item: the item word, from: {items}.
- model: the product line or model name ONLY if it is printed / readable in the photo, or it is already in the current title,
  or the design is unmistakable and you are certain (for example "Gel-Kayano 14", "Air Force 1", "Box Logo", "Nuptse", "Replica" for Maison Margiela GATs).
  Otherwise "". Never guess a model number. A graphic or print name (for example "Rolling Loud", "Wreath", "Polo Bear") may be used when it is readable.
- model_source: "title" (already in the current title), "visible_text" (you can read it in the photo), "design" (recognised by design only), or "none".
- title_base: the title WITHOUT the main colour: "<brand> <model if any> <item>", 2 to 7 words, at most 44 characters,
  Title Case, the brand spelled exactly "{brand}" (when brand is empty, start with the model or item).
  Start from the current title and only ADD what you are sure of (a model name, a sub-type like "Zip Hoodie" or
  "Quarter Zip"). Keep EVERY detail word of the current title (print or model names, "Check", "Washed", "Polo",
  "Striped", "21 Inch"); a colour that is part of a detail phrase stays in title_base as written ("Green Dial").
  If you cannot add anything for sure, return the current title without its colour.
  Good: "Chanel Runner", "Asics Gel-Kayano 14", "Maison Margiela Replica Gats", "Moncler Maya Down Jacket", "Stussy Dice T-Shirt", "Corteiz Alcatraz Cargo Pants".
  Rules: no colour words in title_base, no sizes, no years, no "Men's"/"Women's", no seller words (rep, replica (except the Margiela model), 1:1, batch, top quality, new, hot),
  no dashes as punctuation (hyphens inside a model name like "Gel-Kayano" are fine), no words you cannot see or do not know for sure.
  Keep useful words from the current title (model names, prints, materials like "Suede" or "Leather" when true).
- colour: the colour of the item. The current title's colour comes from the seller's listing and is usually right:
  repeat it as written unless the photo clearly shows a different colour (not a shade: navy vs blue or white vs grey
  is the same colour). You may add a clear second colour ("Navy" -> "Navy White"). Plain English (Black, White, Grey, Navy, Blue, Light Blue, Red, Burgundy, Pink, Purple, Green, Olive, Khaki,
  Yellow, Orange, Brown, Tan, Beige, Cream, Silver, Gold, Multicolour), two words at most ("Black White" for a two-tone shoe), "" if unclear.
- colour_confidence: 0 to 1, how sure you are of colour. Use 0.95+ only when the photo leaves no doubt.
- is_set: true when the find is clearly sold as two or more different garments together (tee + shorts, hoodie + pants).
- is_clean_product_photo: true only when the photo shows the item alone, whole, centred, on a plain white or very light background,
  with no person, hand, hanger, rack, box, extra views, collage, text, logo stamp or watermark added. A pair of shoes counts as one item. A set shown together is fine.
- photo_issues: list from {issues} (empty when clean).
- has_text_or_watermark: true when text, a price, a shop name, a logo stamp or a watermark is ADDED on top of the photo (print on the product itself does not count).
- is_collage: true when the image is several photos or views put together (front + back, a small inset view, a grid).
- brand_check: "matches" if the brand is visible and is {brand!r}, "different" if a different brand is clearly visible, "not_visible" otherwise.
- cat_confidence, title_confidence, confidence: numbers 0 to 1. Use 0.95+ only when you are sure from the photo.
- note: at most 12 words, only if something is odd (wrong photo, item does not match the title), else "".
"""

SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "cat": {"type": "STRING", "enum": CATS},
        "item": {"type": "STRING"},
        "model": {"type": "STRING"},
        "model_source": {"type": "STRING", "enum": ["title", "visible_text", "design", "none"]},
        "title_base": {"type": "STRING"},
        "colour": {"type": "STRING"},
        "colour_confidence": {"type": "NUMBER"},
        "is_set": {"type": "BOOLEAN"},
        "is_clean_product_photo": {"type": "BOOLEAN"},
        "photo_issues": {"type": "ARRAY", "items": {"type": "STRING", "enum": ISSUES}},
        "has_text_or_watermark": {"type": "BOOLEAN"},
        "is_collage": {"type": "BOOLEAN"},
        "brand_check": {"type": "STRING", "enum": ["matches", "different", "not_visible"]},
        "cat_confidence": {"type": "NUMBER"},
        "title_confidence": {"type": "NUMBER"},
        "confidence": {"type": "NUMBER"},
        "note": {"type": "STRING"},
    },
    "required": ["cat", "item", "model", "model_source", "title_base", "colour", "colour_confidence", "is_set", "is_clean_product_photo",
                 "photo_issues", "has_text_or_watermark", "is_collage", "brand_check", "cat_confidence",
                 "title_confidence", "confidence", "note"],
    "propertyOrdering": ["cat", "item", "model", "model_source", "title_base", "colour", "colour_confidence", "is_set", "is_clean_product_photo",
                         "photo_issues", "has_text_or_watermark", "is_collage", "brand_check", "cat_confidence",
                         "title_confidence", "confidence", "note"],
}


def openai_schema():
    """Same schema in OpenAI strict JSON-schema form."""
    conv = {"OBJECT": "object", "STRING": "string", "NUMBER": "number", "BOOLEAN": "boolean", "ARRAY": "array"}

    def c(s):
        o = {"type": conv[s["type"]]}
        if "enum" in s: o["enum"] = s["enum"]
        if s["type"] == "ARRAY": o["items"] = c(s["items"])
        if s["type"] == "OBJECT":
            o["properties"] = {k: c(v) for k, v in s["properties"].items()}
            o["required"] = list(s["properties"]); o["additionalProperties"] = False
        return o
    return {"name": "catalog_label", "strict": True, "schema": c(SCHEMA)}


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def photo_jpeg(data, px=IMG_PX):
    """The photo as the model should see it: on white (cut-outs are transparent), long side px, JPEG."""
    from PIL import Image, ImageOps
    im = ImageOps.exif_transpose(Image.open(io.BytesIO(data)))
    if "A" in im.getbands():
        bg = Image.new("RGBA", im.size, (255, 255, 255, 255)); bg.alpha_composite(im.convert("RGBA")); im = bg
    im = im.convert("RGB"); im.thumbnail((px, px), Image.LANCZOS)
    b = io.BytesIO(); im.save(b, "JPEG", quality=86); return b.getvalue()


def prompt_for(p):
    var = [v[0] for v in (p.get("variants") or []) if isinstance(v, list) and v and isinstance(v[0], str)][:8]
    return PROMPT.format(brand=p.get("brand") or "", title=p.get("title") or "", cat=p.get("cat") or "",
                         variants=", ".join(var) or "(none)", cats=", ".join(CATS), items=", ".join(ITEMS),
                         issues=", ".join(ISSUES))


def post(url, body, headers, timeout=90):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST", headers={"Content-Type": "application/json", **headers})
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read())


def thinking_cfg(model):
    if re.search(r"gemini-2\.5-(flash|flash-lite)", model):
        return {"thinkingBudget": 0}                      # labels do not need thinking; saves output tokens
    if re.search(r"gemini-2\.5-pro", model):
        return {"thinkingBudget": 128}                    # pro cannot switch thinking off
    if re.search(r"gemini-[3-9]", model):
        return {"thinkingLevel": "low"}
    return None


def call_gemini(model, text, jpg):
    body = {"contents": [{"role": "user", "parts": [{"text": text}, {"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(jpg).decode()}}]}],
            "generationConfig": {"responseMimeType": "application/json", "responseSchema": SCHEMA, "temperature": 0, "maxOutputTokens": 1024}}
    t = thinking_cfg(model)
    if t: body["generationConfig"]["thinkingConfig"] = t
    j = post(GEMINI % model, body, {"x-goog-api-key": os.environ["GEMINI_API_KEY"]})
    cand = (j.get("candidates") or [{}])[0]
    txt = "".join(p.get("text", "") for p in (cand.get("content") or {}).get("parts", []) if not p.get("thought"))
    u = j.get("usageMetadata") or {}
    return json.loads(txt), u.get("promptTokenCount", 0), u.get("candidatesTokenCount", 0) + u.get("thoughtsTokenCount", 0)


_claude = None


def call_claude(model, text, jpg):
    """Anthropic Messages API (official SDK): image + prompt in, schema-constrained JSON out."""
    global _claude
    import anthropic
    if _claude is None:
        _claude = anthropic.Anthropic(max_retries=4, timeout=90.0)      # key from ANTHROPIC_API_KEY
    kw = {}
    if model.startswith("claude-haiku-5"):
        kw["thinking"] = {"type": "disabled"}          # Haiku 5.5 allows it at effort high or below; labels need no thinking
    try:
        msg = _claude.messages.create(
            model=model, max_tokens=1024,
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": openai_schema()["schema"]}},
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": base64.standard_b64encode(jpg).decode()}},
                {"type": "text", "text": text}]}],
            **kw)
    except anthropic.APIStatusError as e:
        if e.status_code == 402 or getattr(e, "type", "") == "billing_error" or "credit balance" in str(e).lower():
            raise OutOfCredit("Anthropic: %s" % str(e)[:200])
        raise
    if msg.stop_reason == "refusal":
        raise ValueError("refusal")
    if msg.stop_reason == "max_tokens":
        raise ValueError("answer cut off at max_tokens")
    txt = next(b.text for b in msg.content if b.type == "text")
    u = msg.usage
    return json.loads(txt), (u.input_tokens or 0), (u.output_tokens or 0)


def call_openai(model, text, jpg):
    body = {"model": model, "temperature": 0, "max_tokens": 700,
            "response_format": {"type": "json_schema", "json_schema": openai_schema()},
            "messages": [{"role": "user", "content": [{"type": "text", "text": text},
                         {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(jpg).decode(), "detail": "low"}}]}]}
    j = post(OPENAI, body, {"Authorization": "Bearer " + os.environ["OPENAI_API_KEY"]})
    u = j.get("usage") or {}
    return json.loads(j["choices"][0]["message"]["content"]), u.get("prompt_tokens", 0), u.get("completion_tokens", 0)


def mock_answer(p):
    """Deterministic fake answer from the current data (for testing the pipeline, never for the site)."""
    t = p.get("title") or ""
    col = ""
    for c in sorted(COLOURS, key=len, reverse=True):
        if re.search(r"\b%s\b" % re.escape(c), t, re.I):
            col = c.title(); break
    base = no_dash(re.sub(r"\s+", " ", re.sub(r"(?i)\b(%s)\b" % "|".join(re.escape(c) for c in COLOURS), "", t)).strip())
    rnd = random.Random(p["id"])
    return {"cat": p.get("cat") if rnd.random() > 0.05 else rnd.choice(CATS), "item": "Other", "model": "", "model_source": "title",
            "title_base": base, "colour": col, "is_set": False, "is_clean_product_photo": rnd.random() > 0.2,
            "photo_issues": [], "has_text_or_watermark": False, "is_collage": False, "brand_check": "not_visible",
            "cat_confidence": round(rnd.uniform(0.6, 1), 2), "title_confidence": round(rnd.uniform(0.6, 1), 2),
            "confidence": round(rnd.uniform(0.6, 1), 2), "note": "mock"}, 0, 0


def clean_answer(r, p):
    """Make the answer safe to store: types, enums, no dashes, numbers in 0..1."""
    out = {}
    out["cat"] = r.get("cat") if r.get("cat") in CATS else p.get("cat")
    for k in ("item", "title_base", "colour", "note"):
        out[k] = no_dash(str(r.get(k) or ""))[:80]
    out["model_name"] = no_dash(str(r.get("model") or ""))[:60]   # stored apart: "model" in the file = the AI model used
    out["model_source"] = r.get("model_source") if r.get("model_source") in ("title", "visible_text", "design", "none") else "none"
    for k in ("is_set", "is_clean_product_photo", "has_text_or_watermark", "is_collage"):
        out[k] = bool(r.get(k))
    out["photo_issues"] = [x for x in (r.get("photo_issues") or []) if x in ISSUES]
    out["brand_check"] = r.get("brand_check") if r.get("brand_check") in ("matches", "different", "not_visible") else "not_visible"
    for k in ("cat_confidence", "title_confidence", "colour_confidence", "confidence"):
        try: out[k] = max(0.0, min(1.0, float(r.get(k))))
        except Exception: out[k] = 0.0
    return out


def price(model):
    pin, pout = os.environ.get("PRICE_IN"), os.environ.get("PRICE_OUT")
    if pin and pout: return float(pin), float(pout)
    for k in sorted(PRICES, key=len, reverse=True):
        if model.startswith(k): return PRICES[k]
    return PRICES["gemini-2.5-flash"]


def estimate(n, engine, model):
    ti, to = EST_TOKENS[engine]
    pin, pout = price(model)
    return n * (ti * pin + to * pout) / 1e6


def pick(items, store, a):
    done = store["items"]
    if a.ids or a.ids_file:
        want = set((a.ids or "").replace(" ", "").split(",")) - {""}
        if a.ids_file: want |= set(open(a.ids_file).read().split())
        pool = [p for p in items if p["id"] in want]
    else:
        pool = list(items)
        if a.order == "best":       # most viewed / featured first (data/stats.json when present)
            st = load_json(os.path.join(ROOT, "data", "stats.json"), {}).get("p", {})
            pool.sort(key=lambda p: -(sum((st.get(p["id"]) or [0, 0, 0])[1:3]) if isinstance(st.get(p["id"]), list) else 0))
        elif a.order == "suspects":
            aud = load_json(os.path.join(ROOT, "data", "catalog_audit.json"), {})
            sus = {s[0] for s in aud.get("categories", {}).get("suspects_all", [])}
            pool.sort(key=lambda p: 0 if p["id"] in sus else 1)
    out = []
    for p in pool:
        old = done.get(p["id"])
        if old and not a.redo:
            if a.recheck_below and old.get("model") != a.model and (old.get("confidence", 1) < a.recheck_below or old.get("cat_confidence", 1) < a.recheck_below):
                pass
            elif not (old.get("error") and a.retry_errors):
                continue
        out.append(p)
        if a.limit and len(out) >= a.limit: break
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", default=os.path.join(ROOT, "index.html"))
    ap.add_argument("--out", default=None)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--ids", default="")
    ap.add_argument("--ids-file", default="")
    ap.add_argument("--order", default="catalog", choices=["catalog", "best", "suspects"])
    ap.add_argument("--engine", default=None, choices=["claude", "gemini", "openai"])
    ap.add_argument("--model", default=None)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--max-minutes", type=float, default=0)
    ap.add_argument("--max-usd", type=float, default=0, help="stop when this run's spend passes this")
    ap.add_argument("--redo", action="store_true")
    ap.add_argument("--retry-errors", action="store_true", default=True)
    ap.add_argument("--recheck-below", type=float, default=0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--mock", action="store_true")
    a = ap.parse_args()
    a.model = a.model or os.environ.get("CATALOG_AI_MODEL")
    if not a.engine:
        m = a.model or ""
        a.engine = "gemini" if m.startswith("gemini") else "openai" if m.startswith("gpt") else "claude"
    a.model = a.model or DEFAULT_MODEL[a.engine]
    if a.mock: a.model = "mock"
    out = a.out or os.path.join(ROOT, "data", "catalog_ai.mock.json" if a.mock else "catalog_ai.json")

    _, items, _, _ = load_catalog(a.index)
    store = load_json(out, {})
    store.setdefault("items", {}); store.setdefault("runs", [])
    todo = pick(items, store, a)
    left = sum(1 for p in items if p["id"] not in store["items"])
    print("finds %d, labelled %d, not yet %d; this run: %d (%s / %s)" % (len(items), len(store["items"]), left, len(todo), a.engine, a.model))
    print("cost estimate: this run ~$%.2f, all unlabelled ~$%.2f, whole catalogue ~$%.2f (%s, %s tokens/find in/out)" % (
        estimate(len(todo), a.engine, a.model), estimate(left, a.engine, a.model), estimate(len(items), a.engine, a.model),
        a.model, EST_TOKENS[a.engine]))
    if a.dry_run:
        if todo:
            p = todo[0]
            try:
                jpg = photo_jpeg(fetch(img_url(p)))
                print("example find %s: photo %s -> %d KB JPEG at %d px" % (p["id"], img_url(p), len(jpg) // 1024, IMG_PX))
            except Exception as e:
                print("example photo could not be fetched (%s); request still shown" % str(e)[:80])
            print("---- prompt ----\n" + prompt_for(p) + "----")
            print("ids:", ",".join(x["id"] for x in todo[:30]) + (" ..." if len(todo) > 30 else ""))
        return
    if not a.mock and not os.environ.get({"claude": "ANTHROPIC_API_KEY", "gemini": "GEMINI_API_KEY", "openai": "OPENAI_API_KEY"}[a.engine]):
        sys.exit("no API key in the environment for engine %s" % a.engine)

    call = mock_answer if a.mock else None
    lock = threading.Lock()
    stats = {"ok": 0, "err": 0, "tin": 0, "tout": 0}
    t0 = time.time()
    stop = threading.Event()
    fatal = []
    pin, pout = price(a.model)
    spent = lambda: (stats["tin"] * pin + stats["tout"] * pout) / 1e6

    def one(p):
        if stop.is_set(): return
        for attempt in range(5):
            try:
                if a.mock:
                    r, ti, to = mock_answer(p)
                else:
                    jpg = photo_jpeg(fetch(img_url(p)))
                    fn = {"claude": call_claude, "gemini": call_gemini, "openai": call_openai}[a.engine]
                    r, ti, to = fn(a.model, prompt_for(p), jpg)
                res = clean_answer(r, p)
                res.update({"model": a.model, "date": now(), "was": {"cat": p.get("cat"), "title": p.get("title")}})
                with lock:
                    store["items"][p["id"]] = res; stats["ok"] += 1; stats["tin"] += ti; stats["tout"] += to
                return
            except OutOfCredit as e:
                with lock:
                    if not fatal: fatal.append(str(e))
                stop.set(); return
            except urllib.error.HTTPError as e:
                code = e.code
                body = ""
                try: body = e.read().decode("utf-8", "replace")[:400]
                except Exception: pass
                if code == 402 or "insufficient_quota" in body or "prepayment credits are depleted" in body or "credit balance" in body.lower():
                    with lock:
                        if not fatal: fatal.append("%s: http %d %s" % (a.engine, code, body[:160]))
                    stop.set(); return
                if code in (429, 500, 502, 503, 504) and attempt < 4:
                    time.sleep(min(60, 4 * 2 ** attempt) + random.random()); continue
                err = "http %d" % code
            except Exception as e:
                if stop.is_set(): return
                if attempt < 2:
                    time.sleep(3 + random.random()); continue
                err = str(e)[:120]
            with lock:
                stats["err"] += 1
                if p["id"] not in store["items"] or store["items"][p["id"]].get("error"):
                    store["items"][p["id"]] = {"error": err, "model": a.model, "date": now()}
            return

    def save():
        with lock:
            save_json(out, store)

    done_n = 0
    with cf.ThreadPoolExecutor(max(1, a.workers)) as ex:
        futs = [ex.submit(one, p) for p in todo]
        for f in cf.as_completed(futs):
            done_n += 1
            if done_n % 25 == 0:
                save()
                print("  %d/%d done, %d errors, $%.3f so far, %.0f s" % (done_n, len(todo), stats["err"], spent(), time.time() - t0), flush=True)
            if (a.max_minutes and time.time() - t0 > a.max_minutes * 60) or (a.max_usd and spent() > a.max_usd):
                if not stop.is_set(): print("  stopping early (time or money limit); the rest waits for the next run")
                stop.set()
    store["runs"].append({"date": now(), "model": a.model, "engine": a.engine, "asked": len(todo), "ok": stats["ok"],
                          "errors": stats["err"], "tokens_in": stats["tin"], "tokens_out": stats["tout"], "usd": round(spent(), 4)})
    store["runs"] = store["runs"][-200:]
    store["updated"] = now()
    save()
    print("done: %d labelled, %d errors, tokens in %d / out %d, cost $%.3f -> %s" % (stats["ok"], stats["err"], stats["tin"], stats["tout"], spent(), out))
    if fatal:
        print("::error::STOPPED: the %s account is out of credit (%s). The %d good labels are saved; top up the account "
              "(or pick another --model / engine) and run again: finished finds are skipped." % (a.engine, fatal[0], stats["ok"]))
    lab = [v for v in store["items"].values() if not v.get("error")]
    if lab:
        chg = sum(1 for v in lab if v.get("cat") != (v.get("was") or {}).get("cat"))
        dirty = sum(1 for v in lab if not v.get("is_clean_product_photo"))
        print("so far: %d labels, %d suggest another category, %d photos not clean" % (len(lab), chg, dirty))
    if fatal:
        sys.exit(3)


if __name__ == "__main__":
    main()
