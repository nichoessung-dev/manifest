# -*- coding: utf-8 -*-
# Posts newly-added products to a Discord channel via webhook (the #new-arrivals "drops bot").
# Runs on GitHub Actions cron. State (which ids were posted) lives in discord_posted.json,
# committed back to the repo each run so nothing is double-posted.
#
# Secrets/env: DISCORD_WEBHOOK  (channel webhook URL; set as a GitHub Actions secret)
# Optional env: DROPS_ROLE_ID   (a Discord role id to ping, e.g. a self-assign @Drops role)
#               DROPS_PER_RUN   (max products to post per run, default 5)
import json, os, time, random, urllib.request

SITE   = "https://puroclassico.com"
LOGO   = "https://uptpghuduqjqmrxwatbm.supabase.co/storage/v1/object/public/products/email/logo.png"
NAVY   = 0x1a2740
HOOK   = os.environ.get("DISCORD_WEBHOOK", "").strip()
ROLE   = os.environ.get("DROPS_ROLE_ID", "").strip()
LIMIT  = int(os.environ.get("DROPS_PER_RUN", "10"))
PJSON  = "products.json"          # present in the repo checkout (root)
POSTED = "discord_posted.json"    # list of ids already posted

def load(p, default):
    try:
        with open(p, encoding="utf-8") as f: return json.load(f)
    except Exception:
        return default

def post(payload):
    req = urllib.request.Request(HOOK + "?wait=true",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "User-Agent": "PuroClassicoBot/1.0 (+https://puroclassico.com)"},
        method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status

def embed(pid, p):
    usd = p.get("usd") or 0
    brand = p.get("brand") or ""
    cat = p.get("cat") or ""
    line = " · ".join([x for x in (brand, cat) if x])
    desc = (line + "\n" if line else "") + ("**${:.2f}**".format(float(usd)) if usd else "")
    return {
        "title": (p.get("title") or brand or "New find")[:250],
        "url": "%s/product/%s" % (SITE, pid),
        "description": desc,
        "color": NAVY,
        "image": {"url": p.get("img") or ""},
        "footer": {"text": "Puro Classico · new drop"},
    }

def main():
    if not HOOK:
        print("DISCORD_WEBHOOK not set — nothing to do."); return
    products = load(PJSON, {})
    if isinstance(products, list):  # be tolerant of either shape
        products = {str(x.get("id")): x for x in products if x.get("id")}
    posted = set(str(x) for x in load(POSTED, []))

    # pick LIMIT RANDOM products that have never been posted before
    pool = [pid for pid in products.keys() if pid not in posted]
    if not pool:
        print("Whole catalog has been posted (%d) — resetting the cycle." % len(posted))
        posted = set(); pool = list(products.keys())
    random.shuffle(pool)
    unposted = pool[:LIMIT]

    sent = 0
    for pid in unposted:
        p = products.get(pid) or {}
        if not p.get("img"):
            posted.add(pid); continue   # skip imageless, but mark so we don't retry forever
        payload = {"username": "Puro Classico", "avatar_url": LOGO, "embeds": [embed(pid, p)]}
        if sent == 0 and ROLE:
            payload["content"] = "<@&%s> new drop" % ROLE
            payload["allowed_mentions"] = {"roles": [ROLE]}
        try:
            post(payload); posted.add(pid); sent += 1
            print("posted", pid, "-", p.get("title"))
            time.sleep(1.2)   # stay well under Discord's rate limit
        except Exception as e:
            print("FAIL", pid, str(e)[:120]); break

    with open(POSTED, "w", encoding="utf-8") as f:
        json.dump(sorted(posted), f)
    print("done: posted %d this run, %d total tracked" % (sent, len(posted)))

if __name__ == "__main__":
    main()
