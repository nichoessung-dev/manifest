#!/usr/bin/env python3
"""AI QC notes for every find with stored QC photos, kept for good in data/qc_ai.json (owner, 8 Nov 2026: "if its good
why only 30 days"). functions/api/qc-check.js answers from this file first, so a check costs once per find, loads at once
and is the same for every visitor; the live API call is only the fallback for finds not done yet.

Same prompt and rules as qc-check.js: the listing photo plus up to 5 QC photos from the QC bank (data/qc_bank.json), short
notes marked good / watch / cant_tell, never "real" or "fake". A find is done again only when its number of stored QC
photos changes (new photos), or with --redo / --pid.

  python scripts/qc_ai.py [--max 40] [--pid 7519525216] [--redo] [--dry-run]
Needs ANTHROPIC_API_KEY. Photos are read from the site copies in img/m (scripts/mirror_photos.py) when present, else
downloaded through https://www.puroclassico.com/api/img.
"""
import argparse, base64, json, os, re, sys, time, urllib.parse, urllib.request
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "qc_ai.json")
BANK = os.path.join(ROOT, "data", "qc_bank.json")
TAG = '<script type="application/json" id="pc-catalog">'
SITE = "https://www.puroclassico.com"
SB = "https://uptpghuduqjqmrxwatbm.supabase.co/storage/v1/object/public/products/"
MODEL = os.environ.get("QC_CHECK_MODEL", "claude-sonnet-5-5")
MAX_PHOTOS = 5
AREAS = ["logo", "stitching", "colour", "shape", "materials", "hardware", "tag", "other"]

PROMPT = ("Image 1 is the seller's listing photo of: {title}. The other images are buyer quality-check (QC) photos "
  "of the same item, taken at the agent's warehouse. Write short, careful notes a first-time buyer can use. Rules: only describe "
  "what is clearly visible in the QC photos; if a detail is too small, blurry or not shown, use status cant_tell; never say the "
  "item is real, fake, authentic or guaranteed; compare colour and shape with image 1; no brand history, no prices. "
  "3 to 6 checks, each note at most 14 words in plain English. Use watch only for something visible that a buyer should look "
  "at more closely. summary: one short sentence, what to ask the agent for if anything.")
SCHEMA = {"type": "object", "additionalProperties": False, "required": ["checks", "summary"], "properties": {
    "checks": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["area", "status", "note"],
        "properties": {"area": {"type": "string", "enum": AREAS}, "status": {"type": "string", "enum": ["good", "watch", "cant_tell"]},
                       "note": {"type": "string"}}}},
    "summary": {"type": "string"}}}
BANNED = re.compile(r"\b(authentic|genuine|fake|legit|guarantee)", re.I)


def catalog():
    h = open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()
    i = h.find(TAG) + len(TAG)
    return json.loads(h[i:h.find("</script>", i)])


def mirror_rel(url):
    m = re.match(r"^https://uptpghuduqjqmrxwatbm\.supabase\.co/storage/v1/object/public/products/(pc|pc2|qc)/([A-Za-z0-9_-]{1,80})\.webp(?:\?v=([A-Za-z0-9_-]{1,20}))?$", url or "")
    return "img/m/%s/%s%s.webp" % (m.group(1), m.group(2), ".v" + m.group(3) if m.group(3) else "") if m else ""


def photo(url):
    """(media_type, base64) or None: the site copy in img/m first, else a download through the site's proxy."""
    rel = mirror_rel(url)
    if rel and os.path.exists(os.path.join(ROOT, rel)):
        return "image/webp", base64.b64encode(open(os.path.join(ROOT, rel), "rb").read()).decode()
    if url.startswith("/"):
        url = SITE + url
    if url.startswith(SB):
        url = SITE + "/api/img?u=" + urllib.parse.quote(url, safe="")
    for _ in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "PuroClassicoQcAi/1.0"}), timeout=40) as r:
                ct = (r.headers.get("content-type") or "").split(";")[0]
                b = r.read()
            if ct in ("image/jpeg", "image/png", "image/webp", "image/gif") and 500 < len(b) < 4_500_000:
                return ct, base64.b64encode(b).decode()
            return None
        except Exception:
            time.sleep(3)
    return None


def check(client, p, thumbs):
    imgs = [photo(p.get("img") or "")] + [photo(t) for t in thumbs]
    listing, qcs = imgs[0], [x for x in imgs[1:] if x]
    if not qcs:
        return None, "no QC photo could be loaded"
    content = ([{"type": "image", "source": {"type": "base64", "media_type": listing[0], "data": listing[1]}}] if listing else [])
    content += [{"type": "image", "source": {"type": "base64", "media_type": m, "data": d}} for m, d in qcs]
    content.append({"type": "text", "text": ("" if listing else "There is no listing photo; image 1 is a QC photo too. ") + PROMPT.format(title=(p.get("title") or "")[:120])})
    msg = client.messages.create(model=MODEL, max_tokens=1500,
        output_config={"effort": "medium", "format": {"type": "json_schema", "schema": SCHEMA}},
        messages=[{"role": "user", "content": content}])
    if msg.stop_reason in ("refusal", "max_tokens"):
        return None, "stop_reason " + msg.stop_reason
    v = json.loads(next(b.text for b in msg.content if b.type == "text"))
    clean = lambda s, n: re.sub(r"\s+", " ", str(s or "").replace("—", ",").replace("–", ",")).strip()[:n]
    checks = [{"area": c["area"], "status": c["status"], "note": clean(c["note"], 100)} for c in v.get("checks", [])[:6]
              if c.get("note") and not BANNED.search(c["note"])]
    if not checks:
        return None, "no usable checks"
    return {"checks": checks, "summary": clean(v.get("summary"), 180), "n": len(qcs), "listing": bool(listing),
            "model": MODEL, "at": datetime.now(timezone.utc).strftime("%Y-%m-%d")}, ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=40)
    ap.add_argument("--pid", default="")
    ap.add_argument("--redo", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    bank = (json.load(open(BANK, encoding="utf-8")).get("items") or {})
    try:
        out = json.load(open(OUT, encoding="utf-8"))
    except (OSError, ValueError):
        out = {}
    items = out.setdefault("items", {})
    todo = []
    for p in catalog():
        key = "%s/%s" % (p.get("platform"), str(p.get("itemId") or p.get("id")).lstrip("0"))
        e = bank.get(key)
        n = min(MAX_PHOTOS, int(e[1])) if e and len(e) > 1 and int(e[1] or 0) > 0 else 0
        if not n or (a.pid and str(p["id"]) != a.pid):
            continue
        have = items.get(str(p["id"]))
        if have and have.get("sig") == n and not a.redo and not a.pid:
            continue
        plat, iid = key.split("/", 1)
        todo.append((p, [SB + "qc/%s-%s-%d.webp" % (plat, iid, k) for k in range(n)], n))
    print("finds with stored QC photos to check: %d (this run at most %d)" % (len(todo), a.max))
    if a.dry_run or not todo:
        return
    import anthropic
    client = anthropic.Anthropic(max_retries=4, timeout=180.0)
    done = 0
    for p, thumbs, n in todo[:a.max]:
        try:
            res, why = check(client, p, thumbs)
        except Exception as e:
            res, why = None, str(e)[:160]
        if not res:
            print("  skip %s (%s)" % (p["id"], why)); continue
        res["sig"] = n
        items[str(p["id"])] = res; done += 1
        print("  %s %s: %s" % (p["id"], (p.get("title") or "")[:40], " | ".join(c["status"] for c in res["checks"])))
        out["updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=0, sort_keys=True)   # saved after each find
    print("done: %d checked, %d stored in total" % (done, len(items)))


if __name__ == "__main__":
    main()
