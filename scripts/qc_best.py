#!/usr/bin/env python3
"""The best QC photo per find (owner, 8 Nov 2026: "when hovering a image show the best qc picture"). For every find with
stored QC photos (data/qc_bank.json) Claude Haiku looks at the photos once and picks the one that shows the whole item
most clearly, like a product photo (not a tag, label or stitching close-up). Written to data/qc_best.json as
{"items": {"<find id>": index}}; the card hover in index.html shows that photo first. Only indices are stored.

  python scripts/qc_best.py [--max 120] [--redo]
Needs ANTHROPIC_API_KEY. Photos come from the site copies in img/m, else through the site's image proxy.
"""
import argparse, json, os, sys
from datetime import datetime, timezone
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from qc_ai import catalog, photo, SB, BANK, ROOT   # same catalogue, photo loading and bank paths as the QC notes

OUT = os.path.join(ROOT, "data", "qc_best.json")
MODEL = os.environ.get("QC_BEST_MODEL", "claude-haiku-5-5")
PROMPT = ("These {n} photos are buyer QC photos of one item: {title}. Which photo shows the WHOLE item most clearly, "
          "like a product photo a shopper would want to see first? Prefer the full item, front view, in focus, well lit. "
          "Avoid close-ups of tags, labels, stitching, soles or hardware, and photos with a hand covering it. "
          "Photos are numbered from 0 in the order given.")
SCHEMA = {"type": "object", "additionalProperties": False, "required": ["best"], "properties": {"best": {"type": "integer"}}}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--max", type=int, default=120); ap.add_argument("--redo", action="store_true")
    a = ap.parse_args()
    bank = (json.load(open(BANK, encoding="utf-8")).get("items") or {})
    try: out = json.load(open(OUT, encoding="utf-8"))
    except (OSError, ValueError): out = {}
    items = out.setdefault("items", {}); sig = out.setdefault("sig", {})
    todo = []
    for p in catalog():
        key = "%s/%s" % (p.get("platform"), str(p.get("itemId") or p.get("id")).lstrip("0"))
        e = bank.get(key); n = min(5, int(e[1])) if e and len(e) > 1 and int(e[1] or 0) > 0 else 0
        pid = str(p["id"])
        if n < 2 or (pid in items and sig.get(pid) == n and not a.redo):
            continue
        plat, iid = key.split("/", 1)
        todo.append((p, [SB + "qc/%s-%s-%d.webp" % (plat, iid, k) for k in range(n)], n))
    print("finds to pick a best QC photo for: %d (at most %d this run)" % (len(todo), a.max))
    if not todo: return
    import anthropic
    client = anthropic.Anthropic(max_retries=4, timeout=120.0)
    done = 0
    for p, urls, n in todo[:a.max]:
        imgs = [photo(u) for u in urls]
        if not all(imgs):
            print("  skip %s (a photo did not load)" % p["id"]); continue
        content = [{"type": "image", "source": {"type": "base64", "media_type": m, "data": d}} for m, d in imgs]
        content.append({"type": "text", "text": PROMPT.format(n=n, title=(p.get("title") or "")[:100])})
        try:
            msg = client.messages.create(model=MODEL, max_tokens=200, thinking={"type": "disabled"},
                output_config={"format": {"type": "json_schema", "schema": SCHEMA}}, messages=[{"role": "user", "content": content}])
            best = int(json.loads(next(b.text for b in msg.content if b.type == "text"))["best"])
        except Exception as e:
            print("  skip %s (%s)" % (p["id"], str(e)[:120])); continue
        if not 0 <= best < n:
            continue
        items[str(p["id"])] = best; sig[str(p["id"])] = n; done += 1
        print("  %s: photo %d of %d" % (p["id"], best, n))
    out["updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    json.dump(out, open(OUT, "w", encoding="utf-8"), indent=0, sort_keys=True)
    print("done: %d picked, %d in total" % (done, len(items)))


if __name__ == "__main__":
    main()
