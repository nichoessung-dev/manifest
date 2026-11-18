# -*- coding: utf-8 -*-
"""Turn the friend's matched listings (data/friend_match.json, scripts/match_friend.py) into approved partner swaps.

Owner, 18 Nov 2026: the friend is the partner of the swaps; a find that matches one of his listings takes his link, keeps
its views and popularity, gets the Recommended badge and the top priority group. Inserted straight into Supabase
link_swaps (service key; the same rows /partner writes, status approved, by the same partner as his earlier swaps), so
the app shows them at once and the Swaps workflow (bake_swaps.py) brings them to the server pages and the look-alike rule.
Skips a find that already has a live swap and a listing already used by one. One listing per find (the most confident).

  python scripts/friend_swaps.py [--dry-run]
Env: SUPABASE_SERVICE_KEY.
"""
import argparse, datetime, json, os, sys, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUPA = "https://uptpghuduqjqmrxwatbm.supabase.co"


def rest(path, method="GET", body=None, prefer=None):
    key = os.environ["SUPABASE_SERVICE_KEY"]
    h = {"apikey": key, "authorization": "Bearer " + key, "content-type": "application/json"}
    if prefer: h["prefer"] = prefer
    req = urllib.request.Request(f"{SUPA}/rest/v1/{path}", method=method, headers=h, data=json.dumps(body).encode() if body is not None else None)
    with urllib.request.urlopen(req, timeout=60) as r:
        t = r.read(); return json.loads(t) if t else None


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--dry-run", action="store_true"); a = ap.parse_args()
    items = (json.load(open(os.path.join(ROOT, "data", "friend_match.json"), encoding="utf-8")) or {}).get("items") or {}
    live = rest("rpc/approved_swaps", "POST", {}) or []
    have_pid = {str(r["pid"]) for r in live}; have_item = {str(r["item_id"]) for r in live}
    who = rest("link_swaps?select=by_name,by_code&status=eq.approved&by_code=not.is.null&order=id.desc&limit=1") or [{}]
    by_name, by_code = (who[0] or {}).get("by_name"), (who[0] or {}).get("by_code")
    best = {}
    for item, r in items.items():
        if r.get("status") != "matched" or not r.get("find"): continue
        pid = str(r["find"])
        if pid in have_pid or item in have_item: continue
        c = float(r.get("conf") or 0)
        if pid not in best or c > best[pid][1]: best[pid] = (item, c)
    # new finds added from his listings (scripts/import_friend.py): a swap to itself gives the badge and the top priority
    imp = (json.load(open(os.path.join(ROOT, "data", "friend_import.json"), encoding="utf-8")) if os.path.exists(os.path.join(ROOT, "data", "friend_import.json")) else {}).get("items") or {}
    html = open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()
    for item, r in imp.items():
        if r.get("status") == "ok" and item not in have_pid and item not in have_item and f'"id":"{item}"' in html: best[item] = (item, 1.0)
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    rows = [{"pid": pid, "platform": "weidian", "item_id": item, "note": "friend match (scripts/match_friend.py)",
             "status": "approved", "decided_at": now, "by_name": by_name, "by_code": by_code} for pid, (item, c) in sorted(best.items())]
    print(f"live swaps {len(live)}, matched listings {sum(1 for r in items.values() if r.get('status') == 'matched')}, new swaps {len(rows)} (partner {by_name or '?'})")
    if a.dry_run or not rows: return 0
    for i in range(0, len(rows), 200):
        rest("link_swaps", "POST", rows[i:i + 200], prefer="return=minimal")
    print(f"inserted {len(rows)} approved swaps")
    return 0


if __name__ == "__main__":
    sys.exit(main())
