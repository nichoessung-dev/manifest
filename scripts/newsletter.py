# -*- coding: utf-8 -*-
"""
Puro Classico automated email job. Run modes:
  python newsletter.py welcome     -> one-time welcome (+Discord) to new signups not yet welcomed
  python newsletter.py newsletter  -> 2x/week: personalized for active viewers, generic for dormant / no-history

Env (from GitHub Actions secrets):
  BREVO_API_KEY, SUPABASE_SERVICE_KEY, UNSUB_SECRET
Optional: SITE_URL (default https://puroclassico.com), ACTIVE_DAYS (default 21), MAX_SEND (safety cap)
"""
import os, sys, json, time, hmac, hashlib, urllib.request, urllib.error
from datetime import datetime, timezone, timedelta

SUPA_URL = "https://uptpghuduqjqmrxwatbm.supabase.co"
SITE     = os.environ.get("SITE_URL", "https://puroclassico.com")
SVC      = os.environ["SUPABASE_SERVICE_KEY"]
BREVO    = os.environ["BREVO_API_KEY"]
UNSUB_SECRET = os.environ["UNSUB_SECRET"]
ACTIVE_DAYS  = int(os.environ.get("ACTIVE_DAYS", "21"))
MAX_SEND     = int(os.environ.get("MAX_SEND", "280"))   # Brevo free tier ~300/day
LOGO = SUPA_URL + "/storage/v1/object/public/products/email/logo.png"
DISC = SUPA_URL + "/storage/v1/object/public/products/email/discord.png"

def sb(path, method="GET", body=None, extra=None):
    url = SUPA_URL + "/rest/v1/" + path
    h = {"apikey": SVC, "Authorization": "Bearer " + SVC, "Content-Type": "application/json"}
    if extra: h.update(extra)
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers=h)
    r = urllib.request.urlopen(req, timeout=40)
    t = r.read().decode()
    return json.loads(t) if t else []

def brevo_send(to_email, subject, html, unsub=None):
    body = {"sender": {"name": "Puro Classico", "email": "news@puroclassico.com"},
            "to": [{"email": to_email}], "subject": subject, "htmlContent": html}
    if unsub:
        body["headers"] = {"List-Unsubscribe": "<%s>" % unsub,
                            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"}
    req = urllib.request.Request("https://api.brevo.com/v3/smtp/email",
        data=json.dumps(body).encode(),
        headers={"api-key": BREVO, "accept": "application/json", "content-type": "application/json",
                 "content-transfer-encoding": "8bit"},
        method="POST")
    try:
        r = urllib.request.urlopen(req, timeout=30); return True, r.read().decode()
    except urllib.error.HTTPError as e:
        return False, "%d %s" % (e.code, e.read().decode()[:160])

def unsub_url(uid):
    tok = hmac.new(UNSUB_SECRET.encode(), uid.encode(), hashlib.sha256).hexdigest()
    return "%s/unsubscribe?u=%s&t=%s" % (SITE, urllib.parse.quote(uid), tok)

import urllib.parse
def esc(s): return str(s if s is not None else "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"',"&quot;")

def load_products():
    req = urllib.request.Request(SITE + "/products.json", headers={"User-Agent":"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"})
    r = urllib.request.urlopen(req, timeout=40)
    d = json.loads(r.read().decode())
    # dict preserves insertion order; tail == most recently added
    ids = list(d.keys())
    return d, ids

def usd(p):
    try: return "$" + str(int(round(float(p.get("usd") or 0))))
    except: return ""

def card(pid, p):
    img = esc(p.get("img") or "")
    url = SITE + "/product/" + urllib.parse.quote(pid)
    imgtag = ('<img src="%s" width="228" alt="" style="width:228px;max-width:100%%;height:200px;object-fit:contain;background:#f7f7f8;border-radius:12px;display:block;">' % img) if img else ""
    return ('<td width="50%%" style="padding:8px;vertical-align:top;">'
            '<a href="%s" style="text-decoration:none;color:inherit;display:block;">%s'
            '<div style="font-family:monospace;font-size:10px;letter-spacing:.08em;text-transform:uppercase;color:#999;margin:10px 0 2px;">%s</div>'
            '<div style="font-size:14px;color:#111;font-weight:600;line-height:1.3;">%s</div>'
            '<div style="font-size:14px;color:#111;font-weight:700;margin-top:4px;">%s</div>'
            '</a></td>') % (url, imgtag, esc(p.get("brand") or ""), esc(p.get("title") or ""), usd(p))

def grid(prods):
    rows = ""
    for i in range(0, len(prods), 2):
        pair = prods[i:i+2]
        cells = "".join(card(pid, p) for pid, p in pair)
        if len(pair) == 1: cells += '<td width="50%"></td>'
        rows += "<tr>%s</tr>" % cells
    return '<table role="presentation" width="100%" cellpadding="0" cellspacing="0">' + rows + '</table>'

def wrap(inner, unsub):
    return ("""<table role="presentation" width="100%%" cellpadding="0" cellspacing="0" style="background:#f4f4f2;margin:0;padding:32px 0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;">
<tr><td align="center"><table role="presentation" width="100%%" cellpadding="0" cellspacing="0" style="max-width:560px;background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.06);">
<tr><td align="center" style="padding:34px 36px 6px;text-align:center;"><img src="%s" alt="Puro Classico" height="40" style="height:40px;width:auto;"><div style="height:1px;background:#ececea;margin:22px 0 0;"></div></td></tr>
<tr><td style="padding:24px 36px 8px;">%s</td></tr>
<tr><td align="center" style="padding:18px 36px 34px;text-align:center;"><div style="height:1px;background:#ececea;margin:0 0 16px;"></div>
<p style="margin:0 0 6px;font-size:12px;line-height:1.6;color:#999;">You get these because you opted in at <a href="%s" style="color:#777;">puroclassico.com</a>. <a href="%s" style="color:#777;">Unsubscribe</a>.</p>
<p style="margin:0;font-size:12px;color:#bbb;">&copy; Puro Classico</p></td></tr>
</table></td></tr></table>""") % (LOGO, inner, SITE, esc(unsub))

def run_welcome(profiles):
    sent = 0
    for pr in profiles:
        if pr.get("welcomed"): continue
        email = pr.get("email");
        if not email: continue
        inner = ('<h1 style="margin:0 0 12px;font-size:22px;color:#111;font-weight:650;text-align:center;">Welcome to Puro Classico</h1>'
          '<p style="margin:0 auto 22px;font-size:15px;line-height:1.6;color:#444;max-width:420px;text-align:center;">You\'re in. Thousands of quality-checked Weidian, Taobao and 1688 finds, one tap from your agent. Save what you like with the star, and pick up where you left off any time.</p>'
          '<div style="text-align:center;"><a href="%s" style="display:inline-block;padding:13px 32px;font-size:15px;font-weight:600;color:#fff;background:#111;text-decoration:none;border-radius:10px;">Browse the catalog</a></div>'
          '<div style="height:1px;background:#ececea;margin:26px 0 22px;"></div>'
          '<h2 style="margin:0 0 8px;font-size:16px;color:#111;font-weight:650;text-align:center;">Join the community</h2>'
          '<p style="margin:0 auto 18px;font-size:14px;line-height:1.6;color:#555;max-width:380px;text-align:center;">Early drops, QC talk and haul reviews from other members over on Discord.</p>'
          '<div style="text-align:center;"><a href="https://discord.gg/Pf3zpG3E4" style="display:inline-block;padding:12px 26px;font-size:14px;font-weight:600;color:#fff;background:#5865F2;text-decoration:none;border-radius:10px;"><img src="%s" alt="" width="20" height="20" style="width:20px;height:20px;vertical-align:middle;margin-right:9px;border-radius:4px;"><span style="vertical-align:middle;">Join our Discord</span></a></div>') % (SITE, DISC)
        html = wrap(inner, unsub_url(pr["id"]))
        ok, msg = brevo_send(email, "Welcome to Puro Classico - you're in", html, unsub_url(pr["id"]))
        if ok:
            sb("profiles?id=eq." + pr["id"], "PATCH", {"welcomed": True, "welcomed_at": datetime.now(timezone.utc).isoformat()}, {"Prefer": "return=minimal"})
            sent += 1; print("welcome ->", email)
        else:
            print("FAIL welcome", email, msg)
        if sent >= MAX_SEND: break
        time.sleep(0.3)
    print("welcome sent:", sent)

def ordering_html(uid):
    """Build the 'How to order' guide email HTML for the given user id (used by the real send + the test send)."""
    steps = [
        ("1", "Pick an agent", "An agent is the middleman that buys the item in China and ships it to you. Grab a new-member coupon bundle from the Welcome bonus page, then create a free account.", SITE + "/#welcome-bonus", "See welcome bonuses"),
        ("2", "Find your item, tap Buy", "Browse Puro Classico, open any find and tap <b>Buy via your agent</b>. The link opens the exact listing inside your agent, pre-filled - nothing to copy or paste.", None, None),
        ("3", "Agent buys & checks it", "Pay your agent for the item. They order it from the seller, receive it into your personal warehouse and take <b>QC photos</b> so you can inspect it before it ever leaves China.", None, None),
        ("4", "Approve QC, then ship", "Happy with the QC photos? Choose a courier, and the agent packs and ships your parcel. Order a few things first and <b>consolidate</b> them into one box to save a lot on shipping.", None, None),
    ]
    rows = ""
    for n, h, b, url, cta in steps:
        btn = ('<div style="margin-top:10px;"><a href="%s" style="display:inline-block;padding:9px 20px;font-size:13px;font-weight:600;color:#fff;background:#111;text-decoration:none;border-radius:8px;">%s</a></div>' % (url, cta)) if url else ""
        rows += ('<tr><td style="padding:0 0 22px;vertical-align:top;width:44px;">'
                 '<div style="width:32px;height:32px;border-radius:50%%;background:#111;color:#fff;font-weight:700;font-size:15px;text-align:center;line-height:32px;">%s</div></td>'
                 '<td style="padding:0 0 22px 6px;vertical-align:top;">'
                 '<div style="font-size:16px;font-weight:650;color:#111;margin:4px 0 4px;">%s</div>'
                 '<div style="font-size:14px;line-height:1.55;color:#555;">%s</div>%s</td></tr>') % (n, h, b, btn)
    inner = ('<h1 style="margin:0 0 10px;font-size:22px;color:#111;font-weight:650;text-align:center;">How to order, in 4 steps</h1>'
      '<p style="margin:0 auto 24px;font-size:15px;line-height:1.6;color:#444;max-width:440px;text-align:center;">First haul from China? It is easier than it looks. Here is the whole flow, start to finish.</p>'
      '<table role="presentation" width="100%" cellpadding="0" cellspacing="0">' + rows + '</table>'
      '<div style="height:1px;background:#ececea;margin:8px 0 22px;"></div>'
      '<div style="text-align:center;"><a href="' + SITE + '" style="display:inline-block;padding:13px 32px;font-size:15px;font-weight:600;color:#fff;background:#111;text-decoration:none;border-radius:10px;">Start browsing</a></div>'
      '<p style="margin:18px auto 0;font-size:13.5px;line-height:1.6;color:#777;max-width:400px;text-align:center;">Stuck on anything? Ask in our <a href="https://discord.gg/Pf3zpG3E4" style="color:#5865F2;">Discord</a> - members share QC tips and haul reviews daily.</p>')
    return wrap(inner, unsub_url(uid))

def run_ordering(profiles):
    """Ordering guide - the 2nd email in the sequence, sent GUIDE_DELAY_MINUTES after the welcome.
    Eligible = welcomed, not yet sent the guide, and welcomed >= GUIDE_DELAY_MINUTES ago (or unknown)."""
    delay_m = int(os.environ.get("GUIDE_DELAY_MINUTES", "1080"))   # default 18h; welcome.yml sets it to 1
    cutoff  = datetime.now(timezone.utc) - timedelta(minutes=delay_m)
    def eligible(pr):
        if not pr.get("welcomed") or pr.get("ordering_sent"): return False
        wa = pr.get("welcomed_at")
        if not wa: return True
        try: return datetime.fromisoformat(wa.replace("Z", "+00:00")) <= cutoff
        except: return True
    sent = 0
    for pr in profiles:
        email = pr.get("email")
        if not email or not eligible(pr): continue
        ok, msg = brevo_send(email, "How to order from Puro Classico (4 easy steps)", ordering_html(pr["id"]), unsub_url(pr["id"]))
        if ok:
            sb("profiles?id=eq." + pr["id"], "PATCH", {"ordering_sent": True}, {"Prefer": "return=minimal"})
            sent += 1; print("ordering ->", email)
        else:
            print("FAIL ordering", email, msg)
        if sent >= MAX_SEND: break
        time.sleep(0.3)
    print("ordering sent:", sent)

def run_ordering_test(_profiles=None):
    """Send the ordering guide to a single TEST_EMAIL, ignoring DB gating and marking nothing. For previews."""
    email = os.environ.get("TEST_EMAIL", "").strip()
    if not email: print("TEST_EMAIL not set"); return
    ok, msg = brevo_send(email, "How to order from Puro Classico (4 easy steps)", ordering_html("test"), None)
    print(("ordering-test -> " + email) if ok else ("FAIL ordering-test " + email + " " + msg))

def run_newsletter(profiles):
    prod, ids = load_products()
    newest = [i for i in reversed(ids)]                      # most-recent first
    def pick_new(n, exclude=()):
        out = []
        for i in newest:
            if i in exclude: continue
            if i in prod: out.append((i, prod[i]))
            if len(out) >= n: break
        return out
    # aggregate views + favorites per user
    views = sb("product_views?select=user_id,product_id,brand,cat,viewed_at")
    favs  = sb("favorites?select=user_id,product_id")
    by_user = {}
    for v in views:
        u = v["user_id"]; by_user.setdefault(u, {"brands": {}, "seen": set(), "last": None})
        b = v.get("brand");
        if b: by_user[u]["brands"][b] = by_user[u]["brands"].get(b, 0) + 1
        by_user[u]["seen"].add(v["product_id"])
        t = v.get("viewed_at")
        if t and (by_user[u]["last"] is None or t > by_user[u]["last"]): by_user[u]["last"] = t
    for f in favs:
        u = f["user_id"]; by_user.setdefault(u, {"brands": {}, "seen": set(), "last": None})
        pid = f["product_id"]; by_user[u]["seen"].add(pid)
        b = (prod.get(pid) or {}).get("brand")
        if b: by_user[u]["brands"][b] = by_user[u]["brands"].get(b, 0) + 2   # a fave weighs more
    cutoff = datetime.now(timezone.utc) - timedelta(days=ACTIVE_DAYS)
    sent = 0
    for pr in profiles:
        email = pr.get("email"); uid = pr["id"]
        if not email: continue
        u = by_user.get(uid)
        active = False
        if u and u["last"]:
            try: active = datetime.fromisoformat(u["last"].replace("Z", "+00:00")) >= cutoff
            except: active = True
        if active and u and u["brands"]:
            top = sorted(u["brands"].items(), key=lambda kv: -kv[1])
            tset = [b for b, _ in top[:3]]
            recs = [(i, p) for i, p in ((i, prod[i]) for i in newest if i in prod)
                    if (p.get("brand") in tset) and i not in u["seen"]][:6]
            if len(recs) < 6:
                recs += pick_new(6 - len(recs), exclude=set(u["seen"]) | {i for i, _ in recs})
            intro = ('<p style="margin:0 0 14px;font-size:15px;line-height:1.55;color:#333;">Picked for you, based on what you\'ve been eyeing%s:</p>' %
                     (" (" + esc(", ".join(tset[:2])) + ")" if tset else ""))
            subject = "New %s finds picked for you" % (tset[0] if tset else "arrivals")
            body = intro + grid(recs)
        else:
            recs = pick_new(6)
            intro = '<p style="margin:0 0 14px;font-size:15px;line-height:1.55;color:#333;">Fresh in the catalog this week - here\'s what just dropped:</p>'
            subject = "New arrivals at Puro Classico"
            body = intro + grid(recs)
            body += ('<div style="text-align:center;margin-top:22px;"><a href="%s" style="display:inline-block;padding:12px 30px;font-size:14px;font-weight:600;color:#fff;background:#111;text-decoration:none;border-radius:10px;">Browse all finds</a></div>' % SITE)
        html = wrap(body, unsub_url(uid))
        ok, msg = brevo_send(email, subject, html, unsub_url(uid))
        print(("news %s -> %s" % ("perso" if (active and u and u['brands']) else "generic", email)) if ok else ("FAIL news %s %s" % (email, msg)))
        if ok: sent += 1
        if sent >= MAX_SEND: break
        time.sleep(0.35)
    print("newsletter sent:", sent)

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "newsletter"
    if mode == "ordering-test":
        run_ordering_test(); return
    if mode == "welcome":
        profiles = sb("profiles?select=id,email,welcomed,welcomed_at")     # welcome = transactional, all signups
    elif mode == "ordering":
        profiles = sb("profiles?welcomed=eq.true&select=id,email,welcomed,welcomed_at,ordering_sent")  # ordering guide = 2nd in sequence, transactional
    else:
        profiles = sb("profiles?marketing_opt_in=eq.true&select=id,email,welcomed")
    print("mode=%s profiles=%d" % (mode, len(profiles)))
    {"welcome": run_welcome, "ordering": run_ordering}.get(mode, run_newsletter)(profiles)

if __name__ == "__main__":
    main()
