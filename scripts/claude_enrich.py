#!/usr/bin/env python3
"""Enrich catalogue finds with Claude vision labels (item type, colours, material, alt text, description).

Runs in GitHub Actions (.github/workflows/enrich.yml) through the Message Batches API (50% price).
Outputs live in data/enrich/ (see data/enrich/README.md). This script never touches git; the workflow commits.

Modes
  dry-run  build the batch request JSONL locally, send nothing, print a token and cost estimate
  pilot    submit the N most popular finds that have no labels yet (default 100)
  full     submit every find that has no labels yet (most popular first)
  status   poll submitted batches, collect results, validate, merge, retry failures, write the report

Needs ANTHROPIC_API_KEY in the environment for pilot/full/status (never for dry-run).
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import os
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRODUCTS = ROOT / "products.json"
STATS = ROOT / "data" / "stats.json"
OUT = ROOT / "data" / "enrich"
ENRICH = OUT / "enrich.json"
STATE = OUT / "batch_state.json"
FAILURES = OUT / "failures.json"
REPORT = OUT / "report.md"
DRYRUN = OUT / "dryrun"

MODEL = "claude-opus-5-5"
EFFORT = "low"
MAX_TOKENS = 4000          # thinking (adaptive, always on for this model) counts toward this
MAX_ATTEMPTS = 3           # per product, across retries
IMG_MAX = 768              # long edge after resize (resize image mode)
BATCH_MAX_BYTES = 60_000_000    # API limit is 256 MB per batch; small uploads are less likely to time out
BATCH_MAX_REQ = 10_000          # API limit is 100,000

# claude-opus-5-5 list price per million tokens; batches are half of everything.
PRICE_IN, PRICE_OUT, PRICE_CACHE_READ = 4.00, 20.00, 0.20
BATCH_DISCOUNT = 0.5
CACHE_WRITE_MULT = {"5m": 1.25, "1h": 2.0}
EST_OUTPUT_TOKENS = 450    # rough: ~150 tokens of JSON plus low-effort thinking; report.md shows the real figure
DEFAULT_MAX_COST = 60.0    # USD cap on total spend (spent + in flight + new) unless --max-cost says otherwise
COST_MARGIN = 1.2          # headroom on the measured per-find cost once results exist

# ---------------------------------------------------------------- vocabularies
ITEM_TYPES = [
    # Tops
    "t-shirt", "long sleeve t-shirt", "polo shirt", "rugby shirt", "shirt", "jersey", "tank top",
    "sweater", "cardigan", "sweatshirt", "hoodie", "zip hoodie", "quarter zip",
    # Outerwear
    "jacket", "bomber jacket", "denim jacket", "leather jacket", "puffer jacket", "windbreaker",
    "fleece jacket", "vest", "coat", "trench coat", "tracksuit",
    # Pants and shorts
    "jeans", "trousers", "cargo pants", "sweatpants", "track pants", "shorts", "swim shorts",
    # Shoes
    "sneakers", "boots", "loafers", "dress shoes", "slides", "sandals", "clogs",
    # Bags
    "backpack", "tote bag", "shoulder bag", "crossbody bag", "handbag", "belt bag", "duffel bag",
    "wallet", "card holder",
    # Accessories
    "belt", "scarf", "gloves", "sunglasses", "jewellery", "watch", "socks", "tie", "keychain", "phone case",
    # Headwear
    "cap", "beanie", "bucket hat", "hat",
    # Toys and other
    "toy", "figure", "set", "other",
]
COLOURS = ["black", "white", "grey", "navy", "blue", "light blue", "green", "olive", "brown", "beige",
           "cream", "tan", "red", "burgundy", "pink", "purple", "yellow", "orange", "gold", "silver", "multi"]
MATERIALS = ["cotton", "jersey knit", "wool", "cashmere", "knit", "fleece", "denim", "corduroy", "linen",
             "leather", "suede", "patent leather", "canvas", "nylon", "polyester", "down", "mesh", "rubber",
             "metal", "plastic", "other"]
PATTERNS = ["solid", "check", "stripe", "logo print", "monogram", "camo", "graphic", "other"]
FITS = ["slim", "regular", "relaxed", "oversized", "boxy", "cropped", "wide leg", "straight", "tapered"]


def _nullable_enum(values: list[str]) -> dict:
    return {"anyOf": [{"type": "string", "enum": values}, {"type": "null"}]}


SCHEMA = {
    "type": "object",
    "properties": {
        "item_type": {"type": "string", "enum": ITEM_TYPES},
        "colours": {"type": "array", "items": {"type": "string", "enum": COLOURS}},
        "material": _nullable_enum(MATERIALS),
        "pattern": {"type": "string", "enum": PATTERNS},
        "logo_visible": {"type": "boolean"},
        "fit": _nullable_enum(FITS),
        "alt_text": {"type": "string"},
        "description": {"type": "string"},
        "confidence": {"type": "number"},
    },
    "required": ["item_type", "colours", "material", "pattern", "logo_visible", "fit",
                 "alt_text", "description", "confidence"],
    "additionalProperties": False,
}
FIELDS = SCHEMA["required"]

# Identical bytes in every request so the shared prefix can be cached (cache_control on the block below).
SYSTEM_PROMPT = f"""You label product photos for PuroClassico, a catalogue of clothing, shoes, bags and accessories found on Chinese marketplaces (Taobao, Weidian, 1688). Each request gives you one product photo and the listing facts: title, brand and catalogue category. Fill in the JSON schema for that one product.

How to fill each field:
- item_type: the single closest type from the allowed list. Use the photo first and the title second. Use "set" when the photo shows a matching top and bottom sold together (a tracksuit with a jacket counts as "tracksuit"). Use "other" only when nothing fits.
- colours: one to three main colours of the product itself, most dominant first, from the allowed palette only. Ignore the background, packaging, tags and models' skin or hair. Use "multi" only for four or more colours with none dominant. Never list the same colour twice.
- material: only when the photo makes it plain (denim, leather, knit, corduroy, fleece, mesh, suede, puffer down) or the title names it. Otherwise null. Do not guess cashmere, wool or silk from looks alone.
- pattern: "logo print" when a logo or wordmark is repeated or large enough to be the main design, "monogram" for an all-over brand monogram, "graphic" for a picture or artwork print, "solid" for a single colour with at most a small logo.
- logo_visible: true when any brand logo, wordmark or emblem can be seen in the photo.
- fit: only for clothing when the cut is plain from the photo (for example oversized, cropped, wide leg). Otherwise null. Always null for shoes, bags, accessories, headwear and toys.
- alt_text: a plain image description for screen readers, 110 characters at most, no full stop at the end, starting with the colour and item, for example: Navy Ralph Lauren crewneck sweater with small red pony logo on the chest
- description: exactly two short factual sentences, 260 characters at most in total. Say what the photo shows (colour, item, visible details such as collar, zip, pockets, sole, hardware, logo placement, print) and you may use the title and brand facts given. Never mention a price.
- confidence: a number from 0 to 1 for how sure you are of item_type and colours together. Use below 0.5 when the photo is unclear, shows several different products, or does not match the title.

Hard rules for alt_text and description:
- Only facts you can see in the photo or read in the listing facts. Never invent materials, sizes, origin, stitching quality or anything not shown.
- No quality or legitimacy claims of any kind: never write authentic, genuine, original, legit, official, 1:1, replica, rep, fake, mirror, top quality, high quality, premium, best, perfect, flawless or luxury.
- No marketing language, no hype, no emojis, no exclamation marks, no questions, no second person.
- Use plain hyphens or commas. Never use the long dash character (the em dash) or the en dash.
- British spelling for colour. Brand names as written in the listing facts.

Allowed item types: {", ".join(ITEM_TYPES)}.
Allowed colours: {", ".join(COLOURS)}.
Allowed materials: {", ".join(MATERIALS)}.
Allowed patterns: {", ".join(PATTERNS)}.
Allowed fits: {", ".join(FITS)}."""

BANNED = re.compile(r"\b(authentic|genuine|original|legit|official|replica|reps?|fake|top[- ]quality|"
                    r"high[- ]quality|premium|best|perfect|flawless|luxury)\b|\b1\s*:\s*1\b", re.I)
DASHES = ("\u2014", "\u2015", "\u2013")   # em dash, horizontal bar, en dash


# ---------------------------------------------------------------- io helpers
def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load(path: Path, default):
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True) + "\n")
    tmp.replace(path)


def load_state() -> dict:
    st = load(STATE, {})
    st.setdefault("batches", [])
    st.setdefault("attempts", {})
    st.setdefault("usage", {"input": 0, "output": 0, "cache_read": 0, "cache_write_5m": 0, "cache_write_1h": 0})
    st.setdefault("cost_usd", 0.0)
    return st


def popularity() -> dict[str, tuple]:
    """data/stats.json p[id] = [views_all, views_30d, views_7d, favourites]."""
    p = load(STATS, {}).get("p", {})
    return {k: (v[1] if len(v) > 1 else 0, v[3] if len(v) > 3 else 0, v[0] if v else 0) for k, v in p.items()}


def in_flight(state: dict) -> set[str]:
    return {pid for b in state["batches"] if b.get("status") != "collected" for pid in b.get("ids", [])}


def select(products: dict, state: dict, enrich: dict, limit: int | None) -> list[str]:
    pop = popularity()
    busy = in_flight(state)
    ids = [k for k in products if k not in enrich and k not in busy
           and int(state["attempts"].get(k, 0)) < MAX_ATTEMPTS and products[k].get("img")]
    ids.sort(key=lambda k: tuple(-x for x in pop.get(k, (0, 0, 0))) + (k,))
    return ids[:limit] if limit else ids


# ---------------------------------------------------------------- request building
def facts_text(p: dict) -> str:
    lines = [f"Title: {p.get('title', '')}", f"Brand: {p.get('brand', '')}", f"Category: {p.get('cat', '')}"]
    return "Listing facts:\n" + "\n".join(lines)


def fetch_resized(url: str) -> str | None:
    """Download, shrink to IMG_MAX on the long edge, return base64 JPEG (or None on failure)."""
    from PIL import Image  # imported here so dry-run in url mode needs no Pillow
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "puroclassico-enrich/1.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
        im = Image.open(io.BytesIO(raw))
        im = im.convert("RGB") if im.mode != "RGB" else im
        im.thumbnail((IMG_MAX, IMG_MAX))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=82, optimize=True)
        return base64.standard_b64encode(buf.getvalue()).decode("ascii")
    except Exception as e:  # noqa: BLE001 - any fetch/decode problem just skips this product
        print(f"  image failed {url}: {e}", file=sys.stderr)
        return None


def build_request(pid: str, p: dict, image_mode: str, b64: str | None = None) -> dict:
    if image_mode == "url":
        source = {"type": "url", "url": p["img"]}
    else:
        source = {"type": "base64", "media_type": "image/jpeg", "data": b64}
    return {
        "custom_id": f"p{pid}",
        "params": {
            "model": MODEL,
            "max_tokens": MAX_TOKENS,
            # Batches can take longer than 5 minutes to work through, so the shared prefix uses the 1h TTL.
            "system": [{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral", "ttl": "1h"}}],
            "messages": [{"role": "user", "content": [
                {"type": "image", "source": source},
                {"type": "text", "text": facts_text(p)},
            ]}],
            "output_config": {"effort": EFFORT, "format": {"type": "json_schema", "schema": SCHEMA}},
        },
    }


def build_requests(ids: list[str], products: dict, image_mode: str) -> tuple[list[dict], dict[str, str]]:
    failed: dict[str, str] = {}
    if image_mode == "url":
        return [build_request(i, products[i], "url") for i in ids], failed
    with ThreadPoolExecutor(max_workers=16) as ex:
        imgs = list(ex.map(lambda i: fetch_resized(products[i]["img"]), ids))
    reqs = []
    for i, b64 in zip(ids, imgs):
        if b64 is None:
            failed[i] = "image_fetch_failed"
        else:
            reqs.append(build_request(i, products[i], "base64", b64))
    return reqs, failed


def chunk(reqs: list[dict]) -> list[list[dict]]:
    out, cur, size = [], [], 0
    for r in reqs:
        n = len(json.dumps(r))
        if cur and (size + n > BATCH_MAX_BYTES or len(cur) >= BATCH_MAX_REQ):
            out.append(cur)
            cur, size = [], 0
        cur.append(r)
        size += n
    if cur:
        out.append(cur)
    return out


# ---------------------------------------------------------------- estimates
def image_tokens(w: int, h: int) -> int:
    """Vision docs: images over 1568 px on the long edge are scaled down; tokens ~ w*h/750."""
    s = min(1.0, 1568 / max(w, h))
    return int((w * s) * (h * s) / 750) + 1


def estimate(n: int, img_tok: int, sys_tok: int, user_tok: int) -> dict:
    per_in = img_tok + user_tok
    # first request writes the 1h cache (2x), the rest read it (best effort in batches, so also show no-cache)
    cached = (sys_tok * CACHE_WRITE_MULT["1h"] * PRICE_IN + (n - 1) * sys_tok * PRICE_CACHE_READ
              + n * per_in * PRICE_IN + n * EST_OUTPUT_TOKENS * PRICE_OUT) / 1e6 * BATCH_DISCOUNT
    uncached = (n * (sys_tok + per_in) * PRICE_IN + n * EST_OUTPUT_TOKENS * PRICE_OUT) / 1e6 * BATCH_DISCOUNT
    return {"requests": n, "input_tokens_per_request": sys_tok + per_in, "output_tokens_per_request": EST_OUTPUT_TOKENS,
            "cost_usd_with_cache": round(cached, 2), "cost_usd_no_cache": round(uncached, 2)}


def rough_tokens(text: str) -> int:
    return int(len(text) / 3.5) + 1


def per_find_cost(state: dict, image_mode: str) -> float:
    """USD per request: the rough no-cache estimate, or the measured figure with margin once it is higher."""
    sc = IMG_MAX / 1200 if image_mode == "resize" else 1.0
    rough = estimate(1, image_tokens(int(1200 * sc), int(1200 * sc)),
                     rough_tokens(SYSTEM_PROMPT) + rough_tokens(json.dumps(SCHEMA)) // 2, 40)["cost_usd_no_cache"]
    done = sum(b.get("result", {}).get(k, 0) for b in state["batches"] for k in ("succeeded", "invalid"))
    measured = state["cost_usd"] / done * COST_MARGIN if done else 0.0
    return max(rough, measured)


def spend_check(state: dict, n_new: int, image_mode: str, cap: float, what: str) -> bool:
    """True when spent + in flight + new stays within cap."""
    per = per_find_cost(state, image_mode)
    inflight = sum(len(b.get("ids", [])) for b in state["batches"] if b.get("status") != "collected")
    spent = state["cost_usd"]
    total = spent + (inflight + n_new) * per
    print(f"{what}: {n_new} new, {inflight} in flight, ${spent:.2f} spent, ${per:.4f} per find, "
          f"total estimate ${total:.2f} against cap ${cap:.2f}")
    return total <= cap


def probe_sizes(urls: list[str]) -> list[tuple[int, int]]:
    from PIL import Image
    out = []
    for u in urls:
        try:
            req = urllib.request.Request(u, headers={"User-Agent": "puroclassico-enrich/1.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                out.append(Image.open(io.BytesIO(r.read())).size)
        except Exception as e:  # noqa: BLE001
            print(f"  probe failed {u}: {e}", file=sys.stderr)
    return out


# ---------------------------------------------------------------- validation
def banned_word(text: str, p: dict) -> str | None:
    """First banned word in text that is not also a whole word of the listing title or brand."""
    src = (p.get("title", "") + " " + p.get("brand", "")).lower()
    for m in BANNED.finditer(text):
        w = m.group(0).lower()
        if not re.search(r"(?<![a-z0-9])" + re.escape(w) + r"(?![a-z0-9])", src):
            return w
    return None


def check(data, p: dict) -> tuple[dict | None, str | None]:
    """Schema check plus house rules. Returns (clean record, None) or (None, reason)."""
    if not isinstance(data, dict):
        return None, "not_object"
    if set(data) != set(FIELDS):
        return None, "schema_fields"
    if data["item_type"] not in ITEM_TYPES:
        return None, "schema_item_type"
    cols = data["colours"]
    if not isinstance(cols, list) or not all(c in COLOURS for c in cols):
        return None, "colour_not_in_palette"
    cols = list(dict.fromkeys(cols))[:3]
    if not cols:
        return None, "no_colours"
    if data["material"] is not None and data["material"] not in MATERIALS:
        return None, "schema_material"
    if data["pattern"] not in PATTERNS:
        return None, "schema_pattern"
    if not isinstance(data["logo_visible"], bool):
        return None, "schema_logo_visible"
    if data["fit"] is not None and data["fit"] not in FITS:
        return None, "schema_fit"
    conf = data["confidence"]
    if not isinstance(conf, (int, float)) or isinstance(conf, bool) or not 0 <= conf <= 1:
        return None, "confidence_range"
    alt = " ".join(str(data["alt_text"]).split()).rstrip(".")
    desc = " ".join(str(data["description"]).split())
    for label, text, limit in (("alt_text", alt, 110), ("description", desc, 260)):
        if not text:
            return None, f"{label}_empty"
        if any(d in text for d in DASHES):
            return None, f"{label}_dash"
        if len(text) > limit:
            return None, f"{label}_too_long"
        if banned_word(text, p):
            return None, f"{label}_banned_word"
    if len(re.findall(r"[.!?](\s|$)", desc)) > 2:
        return None, "description_sentences"
    rec = dict(data, colours=cols, alt_text=alt, description=desc, confidence=round(float(conf), 2))
    return rec, None


# ---------------------------------------------------------------- batch api
def client():
    import anthropic  # only needed off the dry-run path
    return anthropic.Anthropic()


def add_usage(state: dict, u) -> float:
    cw = getattr(u, "cache_creation", None)
    w1h = int(getattr(cw, "ephemeral_1h_input_tokens", 0) or 0) if cw else 0
    w5m = int(getattr(cw, "ephemeral_5m_input_tokens", 0) or 0) if cw else 0
    total_w = int(getattr(u, "cache_creation_input_tokens", 0) or 0)
    if not cw:
        w1h = total_w                    # we only ever mark 1h breakpoints
    parts = {"input": int(u.input_tokens or 0), "output": int(u.output_tokens or 0),
             "cache_read": int(getattr(u, "cache_read_input_tokens", 0) or 0),
             "cache_write_5m": w5m, "cache_write_1h": w1h}
    for k, v in parts.items():
        state["usage"][k] = state["usage"].get(k, 0) + v
    cost = (parts["input"] * PRICE_IN + parts["output"] * PRICE_OUT + parts["cache_read"] * PRICE_CACHE_READ
            + w5m * PRICE_IN * CACHE_WRITE_MULT["5m"] + w1h * PRICE_IN * CACHE_WRITE_MULT["1h"]) / 1e6 * BATCH_DISCOUNT
    state["cost_usd"] = round(state["cost_usd"] + cost, 4)
    return cost


def create_batch(c, part: list[dict], known: set[str]):
    """Create one batch with no automatic SDK retry, so a timed-out upload is never sent twice.
    After an error, look for a batch the API did create before trying again."""
    import anthropic
    for attempt in range(3):
        t0 = time.time()
        try:
            return c.with_options(max_retries=0, timeout=900).messages.batches.create(requests=part)
        except (anthropic.APIConnectionError, anthropic.APITimeoutError, anthropic.InternalServerError,
                anthropic.RateLimitError) as e:
            print(f"  batch create failed (try {attempt + 1} of 3): {type(e).__name__}", file=sys.stderr)
            time.sleep(30 * (attempt + 1))
            for b in c.messages.batches.list(limit=20):
                rc = b.request_counts
                total = rc.processing + rc.succeeded + rc.errored + rc.canceled + rc.expired
                if b.id not in known and total == len(part) and b.created_at.timestamp() >= t0 - 120:
                    print(f"  found batch {b.id} created by the failed call; adopting it", file=sys.stderr)
                    return b
    raise SystemExit("could not create the batch after 3 tries")


def submit(ids: list[str], products: dict, state: dict, image_mode: str, label: str, fails: dict) -> list[str]:
    reqs, img_failed = build_requests(ids, products, image_mode)
    for pid, why in img_failed.items():
        state["attempts"][pid] = int(state["attempts"].get(pid, 0)) + 1
        fails[pid] = {"reason": why, "attempts": state["attempts"][pid], "at": now()}
    save(FAILURES, fails)
    made = []
    c = client() if reqs else None
    for part in chunk(reqs):
        b = create_batch(c, part, {x["id"] for x in state["batches"]})
        pids = [r["custom_id"][1:] for r in part]
        for pid in pids:
            state["attempts"][pid] = int(state["attempts"].get(pid, 0)) + 1
        state["batches"].append({"id": b.id, "label": label, "created": now(), "status": b.processing_status,
                                 "image_mode": image_mode, "count": len(pids), "ids": pids})
        save(STATE, state)   # saved after every batch so the workflow can commit the id even if later steps die
        made.append(b.id)
        print(f"submitted {b.id}: {len(pids)} requests ({label}, {image_mode})")
    return made


def collect(b: dict, c, products: dict, state: dict, enrich: dict, fails: dict) -> dict:
    counts = {"succeeded": 0, "invalid": 0, "errored": 0, "expired": 0, "canceled": 0}
    seen = set()
    for res in c.messages.batches.results(b["id"]):
        pid = res.custom_id[1:]
        seen.add(pid)
        kind = res.result.type
        if kind != "succeeded":
            counts[kind if kind in counts else "errored"] += 1
            reason = kind
            if kind == "errored":
                err = getattr(getattr(res.result, "error", None), "error", None) or getattr(res.result, "error", None)
                reason = f"errored:{getattr(err, 'type', 'unknown')}"
            fails[pid] = {"reason": reason, "attempts": state["attempts"].get(pid, 1), "at": now(), "batch": b["id"]}
            continue
        msg = res.result.message
        add_usage(state, msg.usage)
        if msg.stop_reason == "refusal":
            rec, why = None, "refusal"
        elif msg.stop_reason == "max_tokens":
            rec, why = None, "max_tokens"
        else:
            text = next((blk.text for blk in msg.content if blk.type == "text"), "")
            try:
                rec, why = check(json.loads(text), products.get(pid, {}))
            except json.JSONDecodeError:
                rec, why = None, "bad_json"
        if rec is None:
            counts["invalid"] += 1
            fails[pid] = {"reason": why, "attempts": state["attempts"].get(pid, 1), "at": now(), "batch": b["id"]}
            continue
        counts["succeeded"] += 1
        enrich[pid] = dict(rec, model=MODEL, at=now()[:10], img=products.get(pid, {}).get("img", ""))
        fails.pop(pid, None)
    for pid in set(b["ids"]) - seen:
        fails[pid] = {"reason": "missing_result", "attempts": state["attempts"].get(pid, 1), "at": now(), "batch": b["id"]}
    return counts


RETRYABLE = ("expired", "canceled", "missing_result", "max_tokens", "bad_json", "image_fetch_failed")


def retryable(reason: str) -> bool:
    if reason.startswith("errored:"):
        return reason != "errored:invalid_request_error"
    if reason == "refusal":
        return False
    return reason in RETRYABLE or reason.startswith(("schema", "colour", "no_colours", "confidence",
                                                     "alt_text", "description", "not_object"))


def status(args, products: dict) -> int:
    state, enrich, fails = load_state(), load(ENRICH, {}), load(FAILURES, {})
    if args.batch_id and not any(b["id"] == args.batch_id for b in state["batches"]):
        state["batches"].append({"id": args.batch_id, "label": "adopted", "created": now(),
                                 "status": "unknown", "count": 0, "ids": []})
    pending = [b for b in state["batches"] if b.get("status") != "collected"]
    if not pending:
        print("no pending batches")
        write_report(state, enrich, fails, products)
        return 0
    c = client()
    deadline = time.time() + args.wait_minutes * 60
    while True:
        for b in [b for b in state["batches"] if b.get("status") != "collected"]:
            info = c.messages.batches.retrieve(b["id"])
            rc = info.request_counts
            print(f"{b['id']}: {info.processing_status} processing={rc.processing} succeeded={rc.succeeded} "
                  f"errored={rc.errored} expired={rc.expired}")
            if info.processing_status != "ended":
                b["status"] = info.processing_status
                continue
            if not b["ids"]:   # adopted batch: recover ids from the results
                b["ids"] = [r.custom_id[1:] for r in c.messages.batches.results(b["id"])]
                b["count"] = len(b["ids"])
            b["result"] = collect(b, c, products, state, enrich, fails)
            b["status"], b["collected"] = "collected", now()
            print(f"collected {b['id']}: {b['result']}")
            save(ENRICH, enrich)
            save(FAILURES, fails)
            save(STATE, state)
            if not args.no_retry:
                again = [pid for pid, f in fails.items() if pid in b["ids"] and pid in products
                         and retryable(f["reason"]) and int(state["attempts"].get(pid, 0)) < MAX_ATTEMPTS]
                if again:
                    mode = b.get("image_mode", args.image_mode)
                    cap = args.max_cost if args.max_cost is not None else state.get("max_cost", DEFAULT_MAX_COST)
                    if spend_check(state, len(again), mode, cap, f"retry of {b['id']}"):
                        submit(again, products, state, mode, f"retry of {b['id']}", fails)
                        save(FAILURES, fails)
                    else:
                        print(f"retry of {len(again)} skipped: above the spending cap", file=sys.stderr)
        save(STATE, state)
        write_report(state, enrich, fails, products)
        left = [b for b in state["batches"] if b.get("status") != "collected"]
        if not left or time.time() + args.poll_seconds > deadline:
            print(f"{len(left)} batch(es) still pending" if left else "all batches collected")
            return 0
        time.sleep(args.poll_seconds)


# ---------------------------------------------------------------- report
def write_report(state: dict, enrich: dict, fails: dict, products: dict) -> None:
    u = state["usage"]
    live = {k: v for k, v in enrich.items() if k in products}
    by_reason: dict[str, int] = {}
    for f in fails.values():
        by_reason[f["reason"]] = by_reason.get(f["reason"], 0) + 1
    collected = [b for b in state["batches"] if b.get("status") == "collected"]
    pending = [b for b in state["batches"] if b.get("status") != "collected"]
    ok = sum(b.get("result", {}).get("succeeded", 0) for b in collected)
    per = state["cost_usd"] / ok if ok else 0
    lines = [
        "# Enrichment report", "",
        f"Updated {now()} with `{MODEL}` (effort {EFFORT}, Message Batches).", "",
        "## Coverage", "",
        f"- Labelled finds in the live catalogue: **{len(live)} / {len(products)}**",
        f"- Labelled entries no longer in the catalogue: {len(enrich) - len(live)}",
        f"- Batches collected: {len(collected)}, still pending: {len(pending)} "
        f"({sum(b.get('count', 0) for b in pending)} requests)",
        f"- Open failures: {len(fails)}", "",
        "## Failures by reason", "",
    ]
    lines += [f"- {k}: {v}" for k, v in sorted(by_reason.items(), key=lambda x: -x[1])] or ["- none"]
    lines += [
        "", "## Token usage and cost", "",
        "| | tokens |", "|---|---:|",
        f"| input (uncached) | {u['input']:,} |",
        f"| cache read | {u['cache_read']:,} |",
        f"| cache write 1h | {u['cache_write_1h']:,} |",
        f"| cache write 5m | {u['cache_write_5m']:,} |",
        f"| output (incl. thinking) | {u['output']:,} |", "",
        f"Estimated spend so far: **${state['cost_usd']:.2f}** at batch prices "
        f"(input ${PRICE_IN * BATCH_DISCOUNT:.2f}/M, output ${PRICE_OUT * BATCH_DISCOUNT:.2f}/M, "
        f"cache read ${PRICE_CACHE_READ * BATCH_DISCOUNT:.2f}/M). Per labelled find: ${per:.4f}.",
    ]
    if ok and len(products) > len(live):
        lines.append(f"Projected cost for the remaining {len(products) - len(live)} finds: "
                     f"about ${per * (len(products) - len(live)):.2f}.")
    lines += ["", "## Batches", "", "| id | label | created | requests | status | result |", "|---|---|---|---:|---|---|"]
    for b in state["batches"][-30:]:
        r = b.get("result", {})
        res = ", ".join(f"{k} {v}" for k, v in r.items() if v) if r else ""
        lines.append(f"| `{b['id']}` | {b.get('label', '')} | {b.get('created', '')} | {b.get('count', 0)} "
                     f"| {b.get('status', '')} | {res} |")
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n")


# ---------------------------------------------------------------- dry run
def dry_run(args, products: dict) -> int:
    state, enrich = load_state(), load(ENRICH, {})
    pilot_ids = select(products, state, enrich, args.n)
    full_ids = select(products, state, enrich, None)
    ids = pilot_ids if args.scope == "pilot" else full_ids
    DRYRUN.mkdir(parents=True, exist_ok=True)
    out = DRYRUN / f"requests_{args.scope}_{args.image_mode}.jsonl"
    if args.image_mode == "url":
        reqs = [build_request(i, products[i], "url") for i in ids]
    else:
        reqs, failed = build_requests(ids, products, "base64")
        if failed:
            print(f"{len(failed)} image(s) failed to download")
    with out.open("w") as f:
        for r in reqs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    parts = chunk(reqs)
    # sanity: every request uses the exact same system prompt bytes, so the prefix is cacheable
    assert len({json.dumps(r["params"]["system"]) for r in reqs}) <= 1
    assert not any(d in SYSTEM_PROMPT for d in DASHES), "system prompt contains a long dash"
    sys_tok = rough_tokens(SYSTEM_PROMPT) + rough_tokens(json.dumps(SCHEMA)) // 2
    user_tok = max(1, sum(rough_tokens(facts_text(products[i])) for i in ids) // max(1, len(ids)))
    src = (1200, 1200)
    if args.probe:
        sizes = probe_sizes([products[i]["img"] for i in ids[:args.probe]])
        if sizes:
            src = (sum(s[0] for s in sizes) // len(sizes), sum(s[1] for s in sizes) // len(sizes))
            print(f"probed {len(sizes)} images, mean size {src[0]}x{src[1]}")
    w, h = src
    sc = min(1.0, IMG_MAX / max(w, h))
    tok_url, tok_resized = image_tokens(w, h), image_tokens(int(w * sc), int(h * sc))
    report = {
        "file": str(out.relative_to(ROOT)),
        "requests_written": len(reqs),
        "batches_needed": len(parts),
        "largest_batch_mb": round(max((len(json.dumps(p)) for p in parts), default=0) / 1e6, 1),
        "catalogue_size": len(products),
        "already_labelled": len(enrich),
        "system_prompt_tokens_rough": sys_tok,
        "user_text_tokens_rough": user_tok,
        "image_tokens": {"url_mode_source_px": f"{w}x{h}", "url_mode": tok_url,
                         "resize_mode_px": f"{int(w * sc)}x{int(h * sc)}", "resize_mode": tok_resized},
        "estimate": {
            f"pilot_{len(pilot_ids)}_resize": estimate(len(pilot_ids), tok_resized, sys_tok, user_tok),
            f"pilot_{len(pilot_ids)}_url": estimate(len(pilot_ids), tok_url, sys_tok, user_tok),
            f"full_{len(full_ids)}_resize": estimate(len(full_ids), tok_resized, sys_tok, user_tok),
            f"full_{len(full_ids)}_url": estimate(len(full_ids), tok_url, sys_tok, user_tok),
        },
        "note": "rough: text ~3.5 chars/token, image ~w*h/750, output ~%d tokens incl. thinking" % EST_OUTPUT_TOKENS,
    }
    print(json.dumps(report, indent=1))
    return 0


# ---------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=["dry-run", "pilot", "full", "status"])
    ap.add_argument("--n", type=int, default=100, help="pilot size")
    ap.add_argument("--max-items", type=int, default=0, help="full: submit at most this many (0 = all left)")
    ap.add_argument("--image-mode", choices=["resize", "url"], default="resize",
                    help="resize: download and send a %dpx JPEG (fewer tokens); url: let the API fetch the image" % IMG_MAX)
    ap.add_argument("--scope", choices=["pilot", "full"], default="pilot", help="dry-run: which set to write")
    ap.add_argument("--probe", type=int, default=0, help="dry-run: download this many images to measure size")
    ap.add_argument("--max-cost", type=float, default=None,
                    help="cap on total spend in USD (spent + in flight + new); default %d, or the last cap used "
                         "for status" % DEFAULT_MAX_COST)
    ap.add_argument("--batch-id", default="", help="status: also poll this batch id")
    ap.add_argument("--wait-minutes", type=float, default=0, help="status: keep polling up to this long")
    ap.add_argument("--poll-seconds", type=int, default=120)
    ap.add_argument("--no-retry", action="store_true", help="status: do not resubmit failed items")
    args = ap.parse_args()

    products = load(PRODUCTS, {})
    if not products:
        print("products.json missing or empty", file=sys.stderr)
        return 1
    if args.mode == "dry-run":
        return dry_run(args, products)
    if args.mode == "status":
        return status(args, products)

    state, enrich = load_state(), load(ENRICH, {})
    limit = args.n if args.mode == "pilot" else (args.max_items or None)
    ids = select(products, state, enrich, limit)
    if not ids:
        print("nothing to submit: every find is labelled, in flight, or out of attempts")
        return 0
    cap = args.max_cost if args.max_cost is not None else DEFAULT_MAX_COST
    if not spend_check(state, len(ids), args.image_mode, cap, args.mode):
        print(f"estimate is above the cap ${cap:.2f}; raise max_cost or lower max_items to go ahead", file=sys.stderr)
        return 2
    state["max_cost"] = cap   # scheduled status runs use this cap for retries
    fails = load(FAILURES, {})
    submit(ids, products, state, args.image_mode, args.mode, fails)
    save(FAILURES, fails)
    save(STATE, state)
    write_report(state, enrich, fails, products)
    return 0


if __name__ == "__main__":
    sys.exit(main())
