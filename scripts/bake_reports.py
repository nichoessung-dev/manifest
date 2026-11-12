#!/usr/bin/env python3
"""Decide which finds are removed after member reports and write data/reported.json.

Runs in GitHub Actions (.github/workflows/reports.yml) with the SUPABASE_SERVICE_KEY secret. Reads the last 30 days of
table product_reports (written only by functions/api/report.js), the 30-day views in data/stats.json and the owner's
data/report_overrides.json. Writes data/reported.json:
  {"updated": ..., "rule": {...}, "hidden": [ids], "items": [removed finds], "watch": [reported, not removed], "held": n}
read by index.html, feed.html, functions/_middleware.js and functions/product/[id].js (hidden like dead listings) and
by /admin (the review list). Counts only: no user ids, hashes or countries leave this script.

The rule (see score_product): every reporter is counted once, every IP once, every /24 network at most NET_CAP, all
guests together at most ANON_CAP. A find is removed when the score reaches its threshold (3, plus more for finds with
many views) from at least MIN_PEOPLE different IPs on at least MIN_NETS networks. So one person, one household, one
office network or a pile of fresh accounts can never remove a find, and guests alone cannot either.
A removed find stays removed (reports older than 30 days do not bring it back) until the owner adds it under "keep".
At most MAX_NEW_PER_RUN finds are removed per run; the rest wait on the watch list (a brake on coordinated attacks).

data/report_overrides.json (edited by the owner):
  {"keep": {"<id>": "YYYY-MM-DD"}, "hide": ["<id>"]}
  keep: put the find back; only reports made after that date count again, so it can be removed again if new
        reports come in (a plain list of ids, or no date, means "keep for good").
  hide: remove the find by hand, whatever its reports.
"""
import datetime, json, math, os, sys, urllib.error, urllib.request

SUPA = "https://uptpghuduqjqmrxwatbm.supabase.co"
PAGE = 1000
OUT, OVR, STATS = "data/reported.json", "data/report_overrides.json", "data/stats.json"
PHOTO = "data/photo_hidden.json"   # finds with a bad main photo (scripts/photo_hide.py), merged in by merge_photo

WINDOW_DAYS = 30
MEMBER_W = 1.0          # signed-in member with a confirmed email, account at least a day old at report time
UNVERIFIED_W = 0.3      # signed in, email not confirmed: counts like a guest
ANON_W = 0.3            # guest (browser token)
NEW_ACCOUNT_S = 3600    # accounts younger than this count 0
YOUNG_ACCOUNT_S = 86400 # accounts younger than this (but older than an hour) count YOUNG_W
YOUNG_W = 0.5
ANON_CAP = 1.5          # all guest and unconfirmed reports on one find together count at most this
NET_CAP = 1.5           # all reports from one /24 (IPv6 /48) network on one find count at most this
BASE = 3.0              # threshold for a find nobody looks at
VIEW_STEP = 100         # threshold = BASE + log2(1 + views_30d / VIEW_STEP): +1 at 100 views, +2 at 300, +3 at 700, +4 at 1500
MAX_NEED = 10.0
MIN_PEOPLE = 3          # different IPs with a counting report
MIN_NETS = 2            # different networks among them
MAX_NEW_PER_RUN = 25
WATCH_MIN = 1.0         # finds with at least this score and not removed go on the watch list
WATCH_MAX = 60


def parse_ts(s):
    try:
        return datetime.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception:
        return None


def threshold(views30):
    return round(min(MAX_NEED, BASE + math.log2(1 + max(0, views30 or 0) / VIEW_STEP)), 2)


def weight(r):
    """What one report counts for, before the per-IP, per-network and guest caps. ("member"|"guest", weight)"""
    if r.get("user_id"):
        made, at = parse_ts(r.get("account_created")), parse_ts(r.get("created_at"))
        age = (at - made).total_seconds() if made and at else -1
        if age < NEW_ACCOUNT_S:
            return "member", 0.0
        if not r.get("verified"):
            return "guest", UNVERIFIED_W
        return "member", YOUNG_W if age < YOUNG_ACCOUNT_S else MEMBER_W
    return "guest", ANON_W if r.get("tok_hash") else 0.0


def score_product(rows):
    """Score of one find from its reports (already limited to the window). Returns a dict with score, people, nets, reasons."""
    # 1. one report per reporter (member id, else browser token, else IP): the one that counts most
    by_rep = {}
    for r in rows:
        key = ("u:" + r["user_id"]) if r.get("user_id") else ("b:" + r["tok_hash"]) if r.get("tok_hash") else ("i:" + str(r.get("ip_hash")))
        kind, w = weight(r)
        if key not in by_rep or w > by_rep[key][1]:
            by_rep[key] = (kind, w, r)
    # 2. one per IP: several accounts or browsers behind one IP are one person
    by_ip = {}
    for kind, w, r in by_rep.values():
        ip = r.get("ip_hash") or "?"
        if ip not in by_ip or w > by_ip[ip][1]:
            by_ip[ip] = (kind, w, r)
    # 3. guests together at most ANON_CAP (scaled down evenly)
    guest = sum(w for k, w, _ in by_ip.values() if k == "guest")
    f = min(1.0, ANON_CAP / guest) if guest > 0 else 1.0
    # 4. one network at most NET_CAP
    nets = {}
    for k, w, r in by_ip.values():
        if w <= 0: continue
        n = r.get("net_hash") or r.get("ip_hash") or "?"
        nets[n] = nets.get(n, 0.0) + (w * f if k == "guest" else w)
    score = sum(min(NET_CAP, v) for v in nets.values())
    reasons = {}
    for _, _, r in by_rep.values():
        reasons[r.get("reason") or "other"] = reasons.get(r.get("reason") or "other", 0) + 1
    last = max((str(r.get("created_at") or "") for r in rows), default="")[:10]
    return {"score": round(score, 2), "people": sum(1 for _, w, _ in by_ip.values() if w > 0), "nets": len(nets),
            "reasons": reasons, "last": last}


def load_overrides(o):
    o = o if isinstance(o, dict) else {}
    keep = o.get("keep") or {}
    if isinstance(keep, list): keep = {str(i): "9999-12-31" for i in keep}       # a plain list: keep for good
    keep = {str(k): str(v or "9999-12-31")[:10] for k, v in keep.items()}
    hide = [str(i) for i in (o.get("hide") or [])]
    return keep, hide


def decide(rows, views30, overrides, prev, now):
    """Pure: rows = product_reports rows, views30 = {id: 30-day views}, overrides = report_overrides.json,
    prev = the last data/reported.json (or {}), now = aware datetime. Returns the new data/reported.json content."""
    keep, hide = load_overrides(overrides)
    since = now - datetime.timedelta(days=WINDOW_DAYS)
    per = {}
    for r in rows:
        pid, at = str(r.get("product_id") or ""), parse_ts(r.get("created_at"))
        if not pid or not at or at < since or at > now + datetime.timedelta(minutes=5): continue
        if pid in keep and at.date().isoformat() <= keep[pid]: continue      # cleared by the owner: older reports stop counting
        per.setdefault(pid, []).append(r)
    prev_items = {str(x.get("id")): x for x in (prev.get("items") or []) if isinstance(x, dict)}
    today = now.date().isoformat()
    items, candidates, watch = {}, [], []
    for pid, rs in per.items():
        s = score_product(rs)
        s.update(id=pid, need=threshold(views30.get(pid, 0)))
        ok = s["score"] >= s["need"] and s["people"] >= MIN_PEOPLE and s["nets"] >= MIN_NETS
        if ok:
            candidates.append(s)
        elif s["score"] >= WATCH_MIN:
            watch.append(s)
    # still removed from earlier runs (sticky until "keep"), with fresh numbers when there are any
    for pid, x in prev_items.items():
        if pid in keep or x.get("by") in ("owner", "photo"): continue   # photo: re-decided by merge_photo every run
        s = next((c for c in candidates if c["id"] == pid), None)
        if s: candidates.remove(s)
        else: s = dict(x)
        s.update(id=pid, by="reports", since=x.get("since") or today)
        watch[:] = [w for w in watch if w["id"] != pid]
        items[pid] = s
    # new removals: the clearest cases first, at most MAX_NEW_PER_RUN
    candidates.sort(key=lambda c: (-(c["score"] / c["need"]), -c["people"], c["id"]))
    held = candidates[MAX_NEW_PER_RUN:]
    for s in candidates[:MAX_NEW_PER_RUN]:
        s.update(by="reports", since=today)
        items[s["id"]] = s
    for s in held:
        s["held"] = True
        watch.append(s)
    for pid in hide:
        x = items.get(pid) or {"id": pid, "score": 0, "need": threshold(views30.get(pid, 0)), "people": 0, "nets": 0, "reasons": {}, "last": ""}
        x.update(by="owner", since=(prev_items.get(pid) or {}).get("since") or today)
        items[pid] = x
    watch.sort(key=lambda c: (-(c["score"] / c["need"]), -c["people"], c["id"]))
    out_items = sorted(items.values(), key=lambda x: (x.get("since") or "", x["id"]), reverse=True)
    return {
        "updated": now.replace(microsecond=0).isoformat(),
        "rule": {"window_days": WINDOW_DAYS, "base": BASE, "view_step": VIEW_STEP, "max_need": MAX_NEED, "min_people": MIN_PEOPLE,
                 "min_nets": MIN_NETS, "member": MEMBER_W, "guest": ANON_W, "anon_cap": ANON_CAP, "net_cap": NET_CAP,
                 "new_account_s": NEW_ACCOUNT_S, "young_account_s": YOUNG_ACCOUNT_S, "young": YOUNG_W, "max_new_per_run": MAX_NEW_PER_RUN},
        "hidden": sorted(items.keys()),
        "items": out_items,
        "watch": watch[:WATCH_MAX],
        "held": len(held),
    }


def merge_photo(out, photo, overrides, prev, now):
    """Pure: add the finds scripts/photo_hide.py hides for a bad main photo (data/photo_hidden.json) as by "photo".
    Not sticky: a find comes back when it leaves that list (a new photo). The owner's "keep" always wins."""
    keep, _ = load_overrides(overrides)
    ids = [str(i) for i in ((photo or {}).get("hidden") or [])] if isinstance(photo, dict) else []
    why = (photo or {}).get("why") or {} if isinstance(photo, dict) else {}
    have = {x["id"] for x in out["items"]}
    prev_items = {str(x.get("id")): x for x in (prev.get("items") or []) if isinstance(x, dict)}
    today = now.date().isoformat()
    add = []
    for pid in ids:
        if pid in keep or pid in have: continue
        iss = why.get(pid) or []
        add.append({"id": pid, "by": "photo", "issues": iss, "reasons": {"photo: " + i.replace("_", " "): 1 for i in iss},
                    "since": (prev_items.get(pid) or {}).get("since") if (prev_items.get(pid) or {}).get("by") == "photo" else today})
    if not add: return out
    out = dict(out)
    out["items"] = sorted(out["items"] + add, key=lambda x: (x.get("since") or "", x["id"]), reverse=True)
    out["hidden"] = sorted(set(out["hidden"]) | {x["id"] for x in add})
    out["photo"] = len(add)
    return out


def fetch_all(key, path):
    rows, start = [], 0
    while True:
        req = urllib.request.Request(f"{SUPA}/rest/v1/{path}", headers={
            "apikey": key, "Authorization": "Bearer " + key, "Range-Unit": "items", "Range": f"{start}-{start + PAGE - 1}"})
        chunk = json.load(urllib.request.urlopen(req, timeout=60))
        rows += chunk
        if len(chunk) < PAGE: return rows
        start += PAGE


def read_json(path, default):
    try:
        with open(path) as f: return json.load(f)
    except Exception:
        return default


def main():
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not key:
        print("SUPABASE_SERVICE_KEY not set"); return 1
    now = datetime.datetime.now(datetime.timezone.utc)
    since = (now - datetime.timedelta(days=WINDOW_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        rows = fetch_all(key, "product_reports?select=product_id,reason,user_id,account_created,verified,ip_hash,net_hash,tok_hash,created_at"
                              f"&created_at=gte.{since}&order=created_at.asc")
    except urllib.error.HTTPError as e:
        if e.code == 404:                                 # the table is not there yet (SQL.md not run): nothing reported
            print("product_reports not found (run SQL.md); no reports"); rows = []
        else:
            print("reports not read:", e.code, str(e.read()[:200])); return 1
    stats = read_json(STATS, {}).get("p") or {}
    views30 = {str(k): (v[1] if isinstance(v, list) and len(v) > 1 else 0) for k, v in stats.items()}
    prev = read_json(OUT, {})
    out = decide(rows, views30, read_json(OVR, {}), prev if isinstance(prev, dict) else {}, now)
    out = merge_photo(out, read_json(PHOTO, {}), read_json(OVR, {}), prev if isinstance(prev, dict) else {}, now)
    strip = lambda d: json.dumps({k: v for k, v in d.items() if k != "updated"}, sort_keys=True)
    if isinstance(prev, dict) and prev and strip(prev) == strip(out):
        print("reported unchanged:", len(out["hidden"]), "hidden"); return 0
    os.makedirs("data", exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, separators=(",", ":"))
    print(f"reported written: {len(rows)} reports, {len(out['hidden'])} hidden, {len(out['watch'])} watching, {out['held']} held")
    return 0


if __name__ == "__main__":
    sys.exit(main())
