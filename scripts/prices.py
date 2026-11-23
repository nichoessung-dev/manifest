# -*- coding: utf-8 -*-
"""Keep the shown prices right: look each find's listing up on Weidian and set its catalogue price to the cheapest real
variant (scripts/price_rule.py). Owner, 23 Nov 2026: "a lot of the prices is not accurate can you fix that".

Where the prices came from, and why so many were wrong (measured 23 Nov 2026):
  - the original spreadsheet finds (Weidian, all Taobao and 1688): one price copied once and never looked at again, so
    sellers' price changes never reached the site, and copied placeholder prices (1 to 20 yuan) stayed
  - the friend's finds (scripts/import_friend.py) and the partner swaps (scripts/bake_swaps.py): Weidian's "from" price,
    the cheapest SKU, which is often a placeholder (a link, a deposit, a box, a refill)
  - the RepLibrary finds (scripts/import_rl.py): RepLibrary's price, copied once
Now every visible Weidian find is looked up again, most viewed first, and its price follows the listing.

  check   look up the item each find's Buy button opens (for a partner-swapped find, the partner's item) with Weidian's
          public item API, one request at a time with a pause, and record the result in data/prices.json:
          {"rule": "v1", "items": {find id: {"item", "checked" (UTC), "status", "price", "low", "high", "n", "dropped"}}}
          status ok / sold_out: price is the cheapest real variant in whole yuan, prices every real variant's price;
          no_price: only placeholder prices (the seller wants to be asked); gone: no listing (asked twice). low and
          high: the listing's own range, placeholders included.
  apply   set "price", "usd" (price / 7.142857, the catalogue's own rate) and the variant prices of every find whose
          latest check (ok or sold_out, still the item in force) disagrees with the catalogue: a price the listing still
          has for one of its real variants stays (a collection listing has a price per model), anything else becomes
          the cheapest real variant (price_rule.pick). Surgical edits inside the
          pc-catalog block of index.html (same order, same format, nothing else touched), verified before writing. Each
          written batch goes into data/prices_applied.json with the old and new values: `apply --revert FILE --write`
          puts them back (all batches, or one with --batch; disable the Prices workflow first, or its next run applies
          the checks again). It also writes functions/_lib/price_checks.js, the day
          each shown price was confirmed, for the "checked" note on the product pages, and data/prices_unresolved.json,
          the visible finds without a real price (gone, placeholder prices only, unchecked Taobao or 1688 placeholders).
  merge   take the newer record of each find from another data/prices.json (the Prices workflow, after a rebase)
  report  the shown prices against the latest checks (the 23 Nov 2026 measurement)

Which finds a check run takes, most viewed first (data/stats.json: 30 days, then all time): never checked, checked for
another item or rule, or checked longer ago than its tier allows: the 300 most viewed every day, the next 1,700 every
3 days, the rest every 10 days (70 to 100% of that, fixed per find, so the finds of one big run come due on different
days). Finds hidden on the site (data/reported.json "hidden", look-alikes of swapped finds in data/link_swaps.json
"hide") are skipped. Taobao and 1688 have no public price lookup: those finds keep their catalogue price, unless they
are swapped to a Weidian item.

  python scripts/prices.py check [--limit 1500] [--max-minutes 50] [--ids 1,2] [--pause 1.0] [--workers 1]
  python scripts/prices.py apply [--write] [--ids 1,2] [--revert data/prices_applied.json [--batch N]]
  python scripts/prices.py merge OTHER.json
  python scripts/prices.py report [--top 300] [--under-usd 5] [--md out.md]
"""
import argparse, collections, json, os, sys, time, urllib.parse, urllib.request, zlib
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from catalog_common import ROOT, load_catalog, load_json  # noqa: E402
import price_rule  # noqa: E402

DATA = os.path.join(ROOT, "data", "prices.json")
LOG = os.path.join(ROOT, "data", "prices_applied.json")
JS = os.path.join(ROOT, "functions", "_lib", "price_checks.js")   # the product pages say when the price was checked
OPEN = os.path.join(ROOT, "data", "prices_unresolved.json")         # visible finds without a real price, for the owner
SHOW_DAYS = 30                                # a check older than this is not shown on the product page
API = "https://thor.weidian.com/detail/getItemSkuInfo/1.0?param="
H = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
     "Referer": "https://weidian.com/"}
RATE = 7.142857                               # CNY per USD, the catalogue's own rate (scripts/import_friend.py)
TIERS = ((300, 1), (2000, 3), (None, 10))     # (rank below, days between checks): most viewed first and most often
SLACK = timedelta(hours=3)                    # a find checked 23 hours ago counts as a day old (the schedule drifts)
MAX_BATCHES = 400                             # data/prices_applied.json keeps the first batch and the newest ones


def now_utc():
    return datetime.now(timezone.utc).replace(second=0, microsecond=0)


def stamp(t):
    return t.strftime("%Y-%m-%dT%H:%MZ")


def parse_stamp(s):
    try:
        return datetime.strptime(s, "%Y-%m-%dT%H:%MZ").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


# ------------------------------------------------------------------ data files
def load_prices(path=DATA):
    d = load_json(path, {})
    d.setdefault("items", {})
    return d


def save_prices(d, path=DATA):
    """One line per find, so a run's commit shows exactly the finds it checked."""
    d["rule"] = price_rule.RULE
    items = d.get("items") or {}
    lines = ["{", '"note": %s,' % json.dumps(d.get("note") or "Latest Weidian price check per find, written by scripts/prices.py. "
             "price: cheapest real variant (scripts/price_rule.py), whole yuan; low/high: the listing's own range.", ensure_ascii=False),
             '"rule": %s,' % json.dumps(d["rule"]), '"updated": %s,' % json.dumps(d.get("updated") or stamp(now_utc())), '"items": {']
    keys = sorted(items)
    for k, i in enumerate(keys):
        lines.append("%s: %s%s" % (json.dumps(i), json.dumps(items[i], ensure_ascii=False, separators=(",", ":"), sort_keys=True),
                                   "," if k < len(keys) - 1 else ""))
    lines += ["}", "}"]
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    os.replace(tmp, path)


def site_state():
    """(hidden find ids, swaps {find id: [platform, item id]}, swap prices {find id: [item, cny, usd]}, look-alikes)."""
    rep = load_json(os.path.join(ROOT, "data", "reported.json"), {})
    sw = load_json(os.path.join(ROOT, "data", "link_swaps.json"), {})
    return set(map(str, rep.get("hidden") or [])), sw.get("swaps") or {}, sw.get("price") or {}, set(map(str, sw.get("hide") or []))


def item_of(p, swaps):
    """The Weidian item the find's Buy button opens, or None (a Taobao or 1688 listing: no public price lookup)."""
    s = swaps.get(str(p["id"]))
    if s and s[0] == "weidian" and str(s[1]).isdigit():
        return str(s[1])
    if p.get("platform") == "weidian":
        return str(p.get("itemId") or p["id"])
    return None


def views_of():
    st = load_json(os.path.join(ROOT, "data", "stats.json"), {}).get("p") or {}

    def v(i):
        x = st.get(str(i))
        return (x[1] if isinstance(x, list) and len(x) > 1 else 0, x[0] if isinstance(x, list) and x else 0)
    return v


def ranked_visible(items, hidden, hide):
    v = views_of()
    vis = [p for p in items if str(p["id"]) not in hidden and str(p["id"]) not in hide]
    order = {p["id"]: k for k, p in enumerate(items)}
    return sorted(vis, key=lambda p: (-v(p["id"])[0], -v(p["id"])[1], order[p["id"]]))


# ------------------------------------------------------------------ check
def lookup(item):
    """getItemSkuInfo's result, or None when Weidian did not answer (retried with growing pauses: it refuses bursts)."""
    url = API + urllib.parse.quote(json.dumps({"itemId": str(item)}))
    for wait in (0, 5, 15, 40):
        if wait:
            time.sleep(wait)
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=25) as r:
                d = json.load(r)
        except Exception:
            continue
        if (d.get("status") or {}).get("code") == 0:
            return d.get("result") or {}
    return None


def record(item, res, when):
    r = price_rule.shown_price(res)
    return {"item": str(item), "checked": stamp(when), "status": r["status"], "price": r["price"], "prices": r["prices"],
            "low": r["low"], "high": r["high"], "n": r["n"], "dropped": r["dropped"], "rule": price_rule.RULE}


def target(p, rec):
    """The price the find should show after this check (price_rule.pick), or None when the check gave no real price."""
    if not rec or rec.get("status") not in ("ok", "sold_out") or not rec.get("price"):
        return None
    return int(price_rule.pick(p.get("price"), rec.get("prices") or [rec["price"]], rec["price"]))


def due(items, recs, hidden, swaps, hide, now):
    """[(find, item)] to look up, most viewed first."""
    out = []
    for rank, p in enumerate(ranked_visible(items, hidden, hide)):
        item = item_of(p, swaps)
        if not item:
            continue
        rec = recs.get(str(p["id"]))
        if not rec or rec.get("item") != item or rec.get("rule") != price_rule.RULE:
            out.append((p, item)); continue
        days = next(d for top, d in TIERS if top is None or rank < top)
        # 70 to 100% of the tier's days, fixed per find: finds checked in one big run come due again on different days
        days *= 0.7 + 0.3 * (zlib.crc32(str(p["id"]).encode()) % 1000) / 1000.0
        t = parse_stamp(rec.get("checked"))
        if t is None or now - t >= timedelta(days=days) - SLACK:
            out.append((p, item))
    return out


def check_one(item, pause):
    """(item, record or None): one lookup (a second one before calling a listing gone), then a pause."""
    res = lookup(item)
    time.sleep(pause)
    if res is not None and price_rule.is_gone(res):
        time.sleep(4)                       # a listing is only called gone when a second lookup agrees
        res2 = lookup(item)
        time.sleep(pause)
        if res2 is None or not price_rule.is_gone(res2):
            res = res2
    return item, (record(item, res, now_utc()) if res is not None else None)


def cmd_check(a):
    _, items, _, _ = load_catalog()
    hidden, swaps, _, hide = site_state()
    d = load_prices()
    recs = d["items"]
    t0 = time.time()
    if a.ids:
        want = [x for x in a.ids.replace(" ", "").split(",") if x]
        by = {str(p["id"]): p for p in items}
        todo = [(by[i], item_of(by[i], swaps)) for i in want if i in by and item_of(by[i], swaps)]
    else:
        todo = due(items, recs, hidden, swaps, hide, now_utc())
    total_due = len(todo)
    todo = todo[:a.limit] if a.limit else todo
    print("%d finds due for a price check, %d this run" % (total_due, len(todo)), flush=True)
    finds_of = collections.OrderedDict()   # item -> its finds: finds swapped to the same partner item share one lookup
    for p, item in todo:
        finds_of.setdefault(item, []).append(str(p["id"]))
    state = {"done": 0, "errors": 0, "streak": 0, "changed": 0, "stop": ""}

    def work(item):
        if state["stop"] or (a.max_minutes and time.time() - t0 > a.max_minutes * 60):
            state["stop"] = state["stop"] or "time up, limit reached"
            return item, "skip"
        return check_one(item, a.pause)

    with ThreadPoolExecutor(max(1, a.workers)) as ex:
        for item, rec in ex.map(work, list(finds_of)):
            if rec == "skip":
                continue
            if rec is None:
                state["errors"] += 1; state["streak"] += 1
                if state["streak"] >= 25 and not state["stop"]:
                    state["stop"] = "25 lookups in a row failed: Weidian is refusing, stopping (the records so far are kept)"
                continue
            state["streak"] = 0
            for i in finds_of[item]:
                old = recs.get(i) or {}
                if (old.get("price"), old.get("status")) != (rec["price"], rec["status"]):
                    state["changed"] += 1
                recs[i] = dict(rec); state["done"] += 1
            if state["done"] and state["done"] % 200 < len(finds_of[item]):
                print("  %d checked, %d errors, %.0f s" % (state["done"], state["errors"], time.time() - t0), flush=True)
                d["updated"] = stamp(now_utc()); save_prices(d)
    if state["stop"]:
        print(state["stop"], flush=True)
    d["updated"] = stamp(now_utc())
    save_prices(d)
    st = collections.Counter(recs[str(p["id"])]["status"] for p, _ in todo if str(p["id"]) in recs)
    print("checked %d finds (%d with a new price or status), %d lookup errors; left due %d; statuses of this run's finds: %s"
          % (state["done"], state["changed"], state["errors"], max(0, total_due - state["done"]), dict(st)), flush=True)
    if state["done"] == 0 and todo:
        return 2
    return 0


# ------------------------------------------------------------------ apply
def esc(v):
    return json.dumps(v, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def usd_of(cny):
    return round(cny / RATE, 2)


def edit_object(obj, p, new, usd):
    """The object's text with price, usd and the variant prices set for `new` yuan; None when a field is not there
    exactly once (the edit is then left out and reported)."""
    old_usd, old_var = p.get("usd"), p.get("variants")
    new_var = [[v[0], new] + list(v[2:]) if isinstance(v, list) and len(v) >= 2 else v for v in (old_var or [])]
    for key, a, b in (("price", p.get("price"), new), ("usd", old_usd, usd), ("variants", old_var, new_var)):
        if key == "variants" and old_var is None:
            continue
        x, y = '"%s":%s' % (key, esc(a)), '"%s":%s' % (key, esc(b))
        if obj.count(x) != 1 or obj.count('"%s":' % key) != 1:
            return None
        obj = obj.replace(x, y)
    return obj


_DEC = json.JSONDecoder()


def object_span(raw, pid):
    """(start, end) of the find's object inside the catalogue's JSON text (decoded, so a "}" in a title is no problem)."""
    k = raw.find('{"id":%s,' % esc(str(pid)))
    if k < 0:
        return None
    return k, _DEC.raw_decode(raw, k)[1]


def write_catalog(changes, why):
    """changes: [(find id, old price, new price, new usd or None)]. Returns (applied, failed); writes index.html and
    appends the batch to the log."""
    html, items, s, e = load_catalog()
    raw = html[s:e]
    by = {str(p["id"]): p for p in items}
    out, applied, failed = raw, [], []
    for pid, old, new, usd in changes:
        p = by.get(pid)
        sp = object_span(out, pid) if p else None
        if not sp:
            failed.append((pid, "not in the catalogue")); continue
        if p.get("price") != old:
            failed.append((pid, "price changed meanwhile")); continue
        usd = usd_of(new) if usd is None else usd
        obj = edit_object(out[sp[0]:sp[1]], p, new, usd)
        if obj is None:
            failed.append((pid, "field not found exactly once")); continue
        out = out[:sp[0]] + obj + out[sp[1]:]
        applied.append({"id": pid, "old": [old, p.get("usd")], "new": [new, usd]})
    after = json.loads(out)
    assert len(after) == len(items) and all(str(x["id"]) == str(y["id"]) for x, y in zip(items, after)), "order or count changed"
    want = {c["id"]: c["new"] for c in applied}
    for x, y in zip(items, after):
        for k in set(x) | set(y):
            if x.get(k) == y.get(k):
                continue
            i = str(x["id"])
            assert i in want and k in ("price", "usd", "variants"), "unexpected change %s %s" % (i, k)
            assert y["price"] == want[i][0] and y["usd"] == want[i][1], "wrong value %s" % i
            assert all(v[1] == want[i][0] for v in y.get("variants") or [] if isinstance(v, list) and len(v) >= 2), "variants %s" % i
    if applied:
        open(os.path.join(ROOT, "index.html"), "w", encoding="utf-8").write(html[:s] + out + html[e:])
        log = load_json(LOG, {"batches": []})
        log.setdefault("batches", []).append({"date": stamp(now_utc()), "kind": why, "rule": price_rule.RULE, "changes": applied})
        if len(log["batches"]) > MAX_BATCHES:
            log["batches"] = log["batches"][:1] + log["batches"][-(MAX_BATCHES - 1):]
        with open(LOG + ".tmp", "w", encoding="utf-8") as f:
            f.write('{"note": "Price changes written by scripts/prices.py (old and new [price, usd] per find). Revert: python scripts/prices.py apply --revert data/prices_applied.json --write",\n"batches": [\n')
            f.write(",\n".join(json.dumps(b, ensure_ascii=False, separators=(",", ":")) for b in log["batches"]))
            f.write("\n]}\n")
        os.replace(LOG + ".tmp", LOG)
    return applied, failed


def plan(items, recs, swaps, only=None):
    out, why = [], collections.Counter()
    for p in items:
        i = str(p["id"])
        if only and i not in only:
            continue
        rec = recs.get(i)
        if not rec:
            continue
        if rec.get("status") not in ("ok", "sold_out") or not rec.get("price"):
            why["no real price (%s): kept" % rec.get("status")] += 1; continue
        if rec.get("item") != item_of(p, swaps):
            why["the Buy button opens another item now: waits for its check"] += 1; continue
        new = target(p, rec)
        if new == p.get("price"):
            why["already right (%s)" % ("the cheapest real variant" if new == rec["price"] else "the price of one of the listing's variants")] += 1; continue
        out.append((i, p.get("price"), new, None))
    return out, why


def bake_checks(items, recs, swaps):
    """functions/_lib/price_checks.js: for each find whose shown price was confirmed on its live listing in the last
    SHOW_DAYS days, the day and that price (the product page shows "checked <day>" only while the price is the same).
    Written only when it changed. Returns the number of finds in it."""
    cut = now_utc() - timedelta(days=SHOW_DAYS)
    rows = {}
    for p in items:
        i = str(p["id"])
        r = recs.get(i)
        if not r or r.get("item") != item_of(p, swaps) or target(p, r) is None:
            continue
        t = parse_stamp(r.get("checked"))
        if t is None or t < cut:
            continue
        rows[i] = (t.strftime("%Y-%m-%d"), target(p, r))
    days = sorted({d for d, _ in rows.values()})
    di = {d: k for k, d in enumerate(days)}
    out = ("// GENERATED by scripts/prices.py from data/prices.json (the Prices workflow). Do not edit by hand.\n"
           "// PRICE_CHECK[find id] = [index in PRICE_DAYS, yuan]: the day that price was confirmed on the find's live Weidian\n"
           "// listing (the cheapest real variant, scripts/price_rule.py). Pages show the day only while the price is the same.\n"
           "export const PRICE_DAYS = " + json.dumps(days) + ";\n"
           "export const PRICE_CHECK = " + json.dumps({i: [di[d], v] for i, (d, v) in sorted(rows.items())}, separators=(",", ":")) + ";\n")
    old = open(JS, encoding="utf-8").read() if os.path.exists(JS) else None
    if out != old:
        with open(JS + ".tmp", "w", encoding="utf-8") as f:
            f.write(out)
        os.replace(JS + ".tmp", JS)
    return len(rows)


def bake_unresolved(items, recs, hidden, swaps, hide):
    """data/prices_unresolved.json: the visible finds the check could not give a real price, most viewed first, so the
    owner can decide whether to hide them (owner hides go in data/report_overrides.json, never here):
      gone      the Weidian listing is gone (asked twice)
      no_price  the listing only has placeholder prices (ask the seller)
      unchecked_placeholder  Taobao or 1688 finds showing a placeholder price (under 5 yuan: "Ask seller"), which no
                public price lookup can check
      unchecked_cheap  Taobao or 1688 finds outside Accessories under 28 yuan (about $4): maybe a wholesale or
                placeholder price, which no public price lookup can check either
      big_drop  finds whose price a check cut to under a third of a real old price (30 yuan or more): the listing
                may sell something else now (seen: an "AirPods Max" listing now selling 12 yuan earbuds), worth a look
    plus the count of visible Taobao and 1688 finds whose price nobody can check."""
    out = {"gone": [], "no_price": [], "unchecked_placeholder": [], "unchecked_cheap": [], "big_drop": []}
    last = {}
    for b in load_json(LOG, {}).get("batches") or []:
        for c in b.get("changes") or []:
            last[c["id"]] = (c["old"][0], c["new"][0], b.get("date"))
    unchecked = 0
    for p in ranked_visible(items, hidden, hide):
        i, item = str(p["id"]), item_of(p, swaps)
        row = [i, p.get("title"), p.get("price")]
        if not item:
            unchecked += 1
            if not price_rule.MIN_REAL <= float(p.get("price") or 0) < price_rule.MAX_REAL:
                out["unchecked_placeholder"].append(row)
            elif p.get("cat") != "Accessories" and float(p.get("price") or 0) < 28:
                out["unchecked_cheap"].append(row)
            continue
        r = recs.get(i)
        if r and r.get("item") == item and r.get("status") in ("gone", "no_price"):
            out[r["status"]].append(row + [r.get("checked")])
        ch = last.get(i)
        if ch and ch[1] == p.get("price") and (ch[0] or 0) >= 30 and ch[1] * 3 < ch[0]:
            out["big_drop"].append([i, p.get("title"), ch[0], ch[1], ch[2]])
    doc = {"note": "Visible finds without a real price (scripts/prices.py apply), most viewed first: [id, title, catalogue price, "
                   "checked]; big_drop: [id, title, old price, new price, when]. Hiding them is the owner's call "
                   "(data/report_overrides.json).",
           "counts": dict({k: len(v) for k, v in out.items()}, unchecked_taobao_1688=unchecked)}
    doc.update(out)
    txt = json.dumps(doc, ensure_ascii=False, indent=0)
    old = open(OPEN, encoding="utf-8").read() if os.path.exists(OPEN) else None
    if txt != old:
        with open(OPEN + ".tmp", "w", encoding="utf-8") as f:
            f.write(txt)
        os.replace(OPEN + ".tmp", OPEN)
    return doc["counts"]


def cmd_apply(a):
    _, items, _, _ = load_catalog()
    only = set(x for x in (a.ids or "").replace(" ", "").split(",") if x)
    if a.revert:
        log = load_json(a.revert, {"batches": []})
        batches = log.get("batches") or []
        if a.batch is not None:
            batches = [batches[a.batch]]
        by = {str(p["id"]): p for p in items}
        changes, seen = [], set()
        for b in reversed(batches):
            for c in reversed(b.get("changes") or []):
                i = c["id"]
                if (only and i not in only) or i in seen or i not in by:
                    continue
                if by[i].get("price") == c["new"][0]:
                    changes.append((i, c["new"][0], c["old"][0], c["old"][1])); seen.add(i)
        why = collections.Counter({"to put back": len(changes)})
        kind = "revert"
    else:
        _, swaps, _, _ = site_state()
        changes, why = plan(items, load_prices()["items"], swaps, only)
        kind = "apply"
    for k, n in why.most_common():
        print("  %s: %d" % (k, n))
    up = sum(1 for _, o, n, _ in changes if n > (o or 0))
    print("%d price changes (%d up, %d down)" % (len(changes), up, len(changes) - up))
    for i, o, n, _ in changes[:40]:
        print("  %s: %s -> %s yuan" % (i, o, n))
    if not a.write:
        print("report only (add --write to change index.html)"); return 0
    applied, failed = write_catalog(changes, kind) if changes else ([], [])
    print("written: %d, not applied: %d %s" % (len(applied), len(failed), failed[:10]))
    _, items, _, _ = load_catalog()
    hidden, swaps, _, hide = site_state()
    recs = load_prices()["items"]
    print("%d finds with a recent price check for the product pages (%s)" % (bake_checks(items, recs, swaps), os.path.relpath(JS, ROOT)))
    print("visible finds without a real price (%s): %s" % (os.path.relpath(OPEN, ROOT), bake_unresolved(items, recs, hidden, swaps, hide)))
    return 0


# ------------------------------------------------------------------ merge (the workflow, after a rebase)
def cmd_merge(a):
    d, other = load_prices(), load_prices(a.other)
    n = 0
    for i, r in (other.get("items") or {}).items():
        cur = d["items"].get(i)
        if not cur or (parse_stamp(r.get("checked")) or datetime.min.replace(tzinfo=timezone.utc)) > \
                (parse_stamp(cur.get("checked")) or datetime.min.replace(tzinfo=timezone.utc)):
            d["items"][i] = r; n += 1
    d["updated"] = max(d.get("updated") or "", other.get("updated") or "")
    save_prices(d)
    print("merged %d newer records" % n)
    return 0


# ------------------------------------------------------------------ report
def shown_price(p, swaps, swap_price):
    """What the site shows for the find (site.js / index.html): the partner item's price while that item is in force."""
    s, pr = swaps.get(str(p["id"])), swap_price.get(str(p["id"]))
    if s and isinstance(pr, list) and len(pr) == 3 and str(pr[0]) == str(s[1]) and float(pr[1] or 0) > 0:
        return float(pr[1]), "swap"
    return float(p.get("price") or 0), "catalogue"


def band(shown, live):
    if not price_rule.MIN_REAL <= shown < price_rule.MAX_REAL:
        return "placeholder shown (Ask seller)"
    d = abs(shown - live) / live
    if abs(shown - live) <= 1 or d <= 0.02:
        return "right (within 2%)"
    if d <= 0.10:
        return "off by 2 to 10%"
    if d <= 0.25:
        return "off by 10 to 25%"
    if d <= 0.50:
        return "off by 25 to 50%"
    return "off by more than 50%"


def cmd_report(a):
    _, items, _, _ = load_catalog()
    hidden, swaps, swap_price, hide = site_state()
    recs = load_prices()["items"]
    vis = ranked_visible(items, hidden, hide)
    top = vis[:a.top]
    low = [p for p in vis if float(p.get("usd") or 0) < a.under_usd]
    sets = [("%d most viewed visible finds" % a.top, top), ("visible finds under $%g" % a.under_usd, low)]
    L = ["# Shown prices against the live listings (%s)" % stamp(now_utc()), ""]
    for name, ps in sets:
        c, direction, rows = collections.Counter(), collections.Counter(), []
        for p in ps:
            item = item_of(p, swaps)
            rec = recs.get(str(p["id"]))
            if not item:
                c["no public price lookup (%s)" % p.get("platform")] += 1; continue
            if not rec or rec.get("item") != item:
                c["not checked yet"] += 1; continue
            if rec["status"] not in ("ok", "sold_out"):
                c["no real price on the listing (%s)" % rec["status"]] += 1; continue
            shown, src = shown_price(p, swaps, swap_price)
            want = price_rule.pick(shown, rec.get("prices") or [rec["price"]], rec["price"])
            b = band(shown, want); c[b] += 1
            if not b.startswith("right"):
                direction["shown too low" if shown < want else "shown too high"] += 1
                rows.append((p["id"], p.get("title"), shown, src, want, rec.get("low"), rec.get("high")))
        L += ["## %s (%d)" % (name, len(ps)), ""] + ["- %s: %d" % kv for kv in c.most_common()] + \
             ["- %s: %d" % kv for kv in direction.most_common()] + [""]
        L += ["| id | title | shown | live | listing range |", "|---|---|---:|---:|---|"]
        L += ["| %s | %s | %s (%s) | %s | %s to %s |" % (r[0], str(r[1]).replace("|", "/"), r[2], r[3], r[4], r[5], r[6]) for r in rows]
        L.append("")
    txt = "\n".join(L) + "\n"
    if a.md:
        os.makedirs(os.path.dirname(os.path.abspath(a.md)), exist_ok=True)
        open(a.md, "w", encoding="utf-8").write(txt)
    print(txt if not a.md else "\n".join(l for l in L if l.startswith("#") or l.startswith("- ")))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("--limit", type=int, default=1500)
    c.add_argument("--max-minutes", type=float, default=0)
    c.add_argument("--ids", default="")
    c.add_argument("--pause", type=float, default=1.0)
    c.add_argument("--workers", type=int, default=1, help="lookups at a time (Weidian refuses more than a few a second)")
    c = sub.add_parser("apply")
    c.add_argument("--write", action="store_true")
    c.add_argument("--ids", default="")
    c.add_argument("--revert", default="")
    c.add_argument("--batch", type=int, default=None)
    c = sub.add_parser("merge")
    c.add_argument("other")
    c = sub.add_parser("report")
    c.add_argument("--top", type=int, default=300)
    c.add_argument("--under-usd", type=float, default=5)
    c.add_argument("--md", default="")
    a = ap.parse_args(argv)
    return {"check": cmd_check, "apply": cmd_apply, "merge": cmd_merge, "report": cmd_report}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
