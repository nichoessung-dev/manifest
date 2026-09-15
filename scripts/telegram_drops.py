# -*- coding: utf-8 -*-
# Posts newly-added products to a Telegram channel/group via the Bot API (the Telegram "drops bot").
# Mirrors discord_drops.py. Runs on GitHub Actions cron. State (posted ids) in telegram_posted.json,
# committed back to the repo each run so nothing is double-posted.
#
# Secrets/env: TELEGRAM_BOT_TOKEN  (from @BotFather)
#              TELEGRAM_CHAT_ID    (e.g. @puroclassico  or a numeric -100... group/channel id; the bot must be an admin)
# Optional env: TG_PER_RUN (max products per run, default 10)
import json, os, time, random, html, urllib.request, urllib.parse

SITE  = "https://puroclassico.com"
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
CHAT  = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
LIMIT = int(os.environ.get("TG_PER_RUN", "10"))
PJSON = "products.json"
POSTED = "telegram_posted.json"

def load(p, default):
    try:
        with open(p, encoding="utf-8") as f: return json.load(f)
    except Exception:
        return default

def api(method, payload):
    url = "https://api.telegram.org/bot%s/%s" % (TOKEN, method)
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())

def caption(pid, p):
    brand = html.escape(p.get("brand") or "")
    title = html.escape(p.get("title") or brand or "New find")
    cat   = html.escape(p.get("cat") or "")
    usd   = p.get("usd") or 0
    price = ("$%.0f" % float(usd)) if usd else ""
    line2 = " · ".join([x for x in (brand, cat) if x])
    parts = ["<b>%s</b>" % title]
    if line2: parts.append(line2)
    if price: parts.append("<b>%s</b>" % price)
    return "\n".join(parts)

def post(pid, p):
    url = "%s/product/%s" % (SITE, urllib.parse.quote(pid))
    payload = {
        "chat_id": CHAT,
        "photo": p.get("img"),
        "caption": caption(pid, p),
        "parse_mode": "HTML",
        "reply_markup": {"inline_keyboard": [[{"text": "🛒 View on Puro Classico", "url": url}]]},
    }
    return api("sendPhoto", payload)

def main():
    if not TOKEN or not CHAT:
        print("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set — nothing to do."); return
    products = load(PJSON, {})
    if isinstance(products, list):
        products = {str(x.get("id")): x for x in products if x.get("id")}
    posted = set(str(x) for x in load(POSTED, []))
    pool = [pid for pid in products.keys() if pid not in posted and (products.get(pid) or {}).get("img")]
    if not pool:
        print("Whole catalog posted (%d) — resetting cycle." % len(posted)); posted = set()
        pool = [pid for pid in products.keys() if (products.get(pid) or {}).get("img")]
    random.shuffle(pool)
    sent = 0
    for pid in pool[:LIMIT]:
        p = products.get(pid) or {}
        try:
            post(pid, p); posted.add(pid); sent += 1
            print("posted", pid, "-", p.get("title"))
            time.sleep(3)   # Telegram: stay well under ~20 msgs/min to a channel
        except Exception as e:
            print("FAIL", pid, str(e)[:160]); break
    with open(POSTED, "w", encoding="utf-8") as f:
        json.dump(sorted(posted), f)
    print("done: posted %d this run, %d total tracked" % (sent, len(posted)))

if __name__ == "__main__":
    main()
