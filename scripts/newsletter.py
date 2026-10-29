# -*- coding: utf-8 -*-
"""
Puro Classico automated email job. Run modes:
  python newsletter.py welcome     -> one-time welcome (+Discord) to new signups not yet welcomed
  python newsletter.py newsletter  -> 2x/week: the most viewed and saved finds, weighted by each member's taste
  python newsletter.py saved       -> weekly: "you saved this" for members who starred something in the last week
  python newsletter.py sync        -> mirror members into Brevo contacts

Env (from GitHub Actions secrets):
  BREVO_API_KEY, SUPABASE_SERVICE_KEY, UNSUB_SECRET
Optional: SITE_URL (default https://www.puroclassico.com), ACTIVE_DAYS (default 21), MAX_SEND (safety cap)
"""
import os, sys, json, re, time, math, hmac, hashlib, urllib.request, urllib.error
from datetime import datetime, timezone, timedelta

SUPA_URL = "https://uptpghuduqjqmrxwatbm.supabase.co"
# www, not the bare domain: the bare domain answers with a 301, and a one-click unsubscribe POST (RFC 8058) must not be
# redirected, so Gmail's unsubscribe button failed. Every other link also saves a redirect hop.
SITE     = os.environ.get("SITE_URL", "https://www.puroclassico.com")
SVC      = os.environ["SUPABASE_SERVICE_KEY"]
BREVO    = os.environ["BREVO_API_KEY"]
UNSUB_SECRET = os.environ["UNSUB_SECRET"]
ACTIVE_DAYS  = int(os.environ.get("ACTIVE_DAYS", "21"))
MAX_SEND     = int(os.environ.get("MAX_SEND", "280"))   # safety cap for one run of one mode
# One budget for the whole day (22 Oct 2026): Brevo's free plan sends 300 emails a day across every mode, and with ~250
# opted-in members a Tuesday or Friday newsletter alone could use it up, so the welcome emails (they carry the MyCNBox
# coupon link) failed for the rest of the day. Marketing modes now take only what is left after a reserve for new members.
DAILY_CAP    = int(os.environ.get("DAILY_CAP", "300"))
MARGIN, RESERVE_MIN = 15, 40
LOGO = SUPA_URL + "/storage/v1/object/public/products/email/logo.png"
DISC = SUPA_URL + "/storage/v1/object/public/products/email/discord.png"
MYCNBOX_LOGO = SUPA_URL + "/storage/v1/object/public/products/email/mycnbox.png"
MYCNBOX_URL  = "https://mycnbox.com/login/main-login?inviteCode=AACPYA"
# Our own address for the Discord invite: it redirects to the current invite (DISCORD_INVITE in functions/_lib/site.js),
# so emails already sent keep working when the invite is replaced. Never put a discord.gg link in an email.
DISCORD_URL  = "https://www.puroclassico.com/discord"
# Campaign tags on links to our own site (29 Oct 2026): main() sets CAMPAIGN to the mode (welcome, ordering, mycnbox,
# newsletter, saved), so /admin shows product page views and buy clicks per email. Never added to MyCNBox, Discord or
# unsubscribe links. utm_source stays "email", so track.js still counts these visits as ~email.
CAMPAIGN = "newsletter"

def site_link(url):
    """A link to our own site with the email campaign tags; a #fragment stays at the end."""
    base, h, frag = url.partition("#")
    if base.count("/") == 2: base += "/"                       # https://www.puroclassico.com -> https://www.puroclassico.com/
    return base + ("&" if "?" in base else "?") + "utm_source=email&utm_medium=email&utm_campaign=" + CAMPAIGN + h + frag

def sb(path, method="GET", body=None, extra=None):
    url = SUPA_URL + "/rest/v1/" + path
    h = {"apikey": SVC, "Authorization": "Bearer " + SVC, "Content-Type": "application/json"}
    if extra: h.update(extra)
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers=h)
    r = urllib.request.urlopen(req, timeout=40)
    t = r.read().decode()
    return json.loads(t) if t else []

def sb_all(path, page=1000):
    """Every row of a GET: Supabase returns at most 1,000 rows per request, so read in pages (Range header). The path must
    carry an order= so the pages don't overlap. Before this, only the first 1,000 product views were read."""
    out, start = [], 0
    while True:
        rows = sb(path, extra={"Range-Unit": "items", "Range": "%d-%d" % (start, start + page - 1)})
        out += rows
        if len(rows) < page: return out
        start += page

def since(days):
    return (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")

def hide(msg):
    """The job log of this repository is public: an error text is printed without any email address in it."""
    return re.sub(r"[\w.+%-]+@[\w-]+(?:\.[\w-]+)+", "<address>", str(msg))[:200]

def brevo_send(to_email, subject, html, unsub=None, tag=None):
    body = {"sender": {"name": "Puro Classico", "email": "news@puroclassico.com"},
            "to": [{"email": to_email}], "subject": subject, "htmlContent": html}
    if tag: body["tags"] = [tag]          # Brevo's statistics split by tag: welcome, ordering, mycnbox, newsletter, saved
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

def brevo_get(path):
    try:
        req = urllib.request.Request("https://api.brevo.com/v3/" + path, headers={"api-key": BREVO, "accept": "application/json"})
        return json.loads(urllib.request.urlopen(req, timeout=30).read().decode())
    except Exception as e:
        print("budget: Brevo %s not readable (%s)" % (path.split("?")[0], hide(e)[:80])); return None

def sent_today():
    """Emails Brevo has accepted today (UTC). If its statistics can't be read: an estimate from today's new members."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    r = brevo_get("smtp/statistics/aggregatedReport?startDate=%s&endDate=%s" % (today, today))
    if isinstance(r, dict) and r.get("requests") is not None: return int(r["requests"])
    print("budget: Brevo statistics unavailable, estimating from today's welcome emails")
    try: n = len(sb_all("profiles?select=id&welcomed_at=gte.%sT00:00:00Z&order=id" % today))
    except Exception: n = 10
    return 2 * n + 15

def credits_left():
    """Brevo's own count of send credits left (the free plan's daily limit), when the account answers."""
    for p in (brevo_get("account") or {}).get("plan") or []:
        if p.get("creditsType") == "sendLimit":
            print("budget: Brevo plan %s, %s send credits left" % (p.get("type"), p.get("credits")))
            try: return int(p.get("credits"))
            except (TypeError, ValueError): return None
    return None

def reserve():
    """Room kept for the rest of today's welcome, ordering and MyCNBox emails: about 2.9 per new member."""
    try: per_hour = len(sb_all("profiles?select=created_at&created_at=gte.%s&order=created_at" % since(7))) / 168.0
    except Exception: per_hour = 1.0
    now = datetime.now(timezone.utc)
    return max(RESERVE_MIN, int(math.ceil(2.9 * per_hour * (24 - now.hour - now.minute / 60.0))))

def slots(mode):
    """How many emails this marketing mode may send now without eating into the room new members need."""
    left = min(x for x in (DAILY_CAP - sent_today(), credits_left()) if x is not None)
    r = 0 if mode == "mycnbox" else reserve()
    n = max(0, min(MAX_SEND, left - MARGIN - r))
    print("budget: %d left today, %d kept for new members, %d for %s" % (left, r, n, mode))
    return n

def welcomed_lately(pr, hours=48):
    """New members get the welcome, ordering and MyCNBox emails in their first days: no newsletter on top."""
    try: return bool(pr.get("welcomed_at")) and datetime.fromisoformat(pr["welcomed_at"].replace("Z", "+00:00")) > datetime.now(timezone.utc) - timedelta(hours=hours)
    except Exception: return False

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

_EMAIL_IMG = {}
def email_img(pid, src):
    """A square JPEG of the product on a light grey background, for emails.
    The catalogue pictures are WebP with a transparent background: Brevo turns them into JPEG with a BLACK background and
    jagged edges, and Gmail ignores object-fit, so they were also squashed. Made once per product and kept in Supabase storage."""
    if pid in _EMAIL_IMG: return _EMAIL_IMG[pid]
    path = "email/p/%s.jpg" % re.sub(r"[^A-Za-z0-9_-]", "", str(pid))
    public = SUPA_URL + "/storage/v1/object/public/products/" + path
    out = src
    try:
        try:
            urllib.request.urlopen(urllib.request.Request(public, method="HEAD"), timeout=15); out = public
        except urllib.error.HTTPError:
            import io
            from PIL import Image
            raw = urllib.request.urlopen(urllib.request.Request(src, headers={"User-Agent": "Mozilla/5.0 PuroClassicoMail/1.0"}), timeout=30).read()
            im = Image.open(io.BytesIO(raw)); im.load()
            im = im.convert("RGBA")
            box = im.getbbox()                                   # trim the empty transparent margin, then centre with even padding
            if box: im = im.crop(box)
            side = int(max(im.size) * 1.12)
            canvas = Image.new("RGB", (side, side), (247, 247, 248))
            canvas.paste(im, ((side - im.width) // 2, (side - im.height) // 2), im)
            canvas = canvas.resize((480, 480), Image.LANCZOS)       # shown at 228 px: sharp on phones and retina screens
            buf = io.BytesIO(); canvas.save(buf, "JPEG", quality=88, optimize=True, progressive=True)
            req = urllib.request.Request(SUPA_URL + "/storage/v1/object/products/" + path, data=buf.getvalue(), method="POST",
                headers={"apikey": SVC, "Authorization": "Bearer " + SVC, "Content-Type": "image/jpeg",
                         "x-upsert": "true", "Cache-Control": "max-age=31536000"})
            urllib.request.urlopen(req, timeout=30); out = public
    except Exception as e:
        print("email picture for %s not made: %s" % (pid, hide(e)))
    _EMAIL_IMG[pid] = out
    return out

# ---------------------------------------------------------------- email template (v9 site look)
# Tokens mirror ds.css v9: white page, #F5F5F5 wells, ink #0A0A0A, primary #171717 on #FAFAFA, muted #6B6B6B,
# hairlines #E5E5E5, 12px cards, round pills, Inter. Every critical style is inline (Gmail can drop <style>);
# the <style> blocks in wrap() only add dark mode, the phone layout and (separately) Outlook.com dark ([data-ogsc]).
FONT = "Inter,-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif"
INK, MUT, LINE, WELL, PRI, PRI_FG = "#0A0A0A", "#6B6B6B", "#E5E5E5", "#F5F5F5", "#171717", "#FAFAFA"

def pre(text):
    """Preheader for wrap(): put it first in the inner HTML; wrap() lifts it into the hidden preview line."""
    return "<!--pre:%s-->" % esc(text).replace("--", "- -")

def h1(text):
    return ('<h1 class="pc-ink pc-h1" style="margin:0 0 12px;font-family:%s;font-size:30px;line-height:1.15;font-weight:700;'
            'letter-spacing:-0.025em;color:%s;text-align:center;">%s</h1>') % (FONT, INK, text)

def h2(text, align="center"):
    return ('<h2 class="pc-ink" style="margin:0 0 8px;font-family:%s;font-size:20px;line-height:1.25;font-weight:700;'
            'letter-spacing:-0.02em;color:%s;text-align:%s;">%s</h2>') % (FONT, INK, align, text)

def lead(text, size=16, mb=24):
    return ('<p class="pc-mut" style="margin:0 auto %dpx;max-width:440px;font-family:%s;font-size:%dpx;line-height:1.55;'
            'color:%s;text-align:center;">%s</p>') % (mb, FONT, size, MUT, text)

def hr(m="32px 0"):
    return ('<table role="presentation" width="100%%" cellpadding="0" cellspacing="0" style="margin:%s;"><tr>'
            '<td class="pc-line" height="1" style="height:1px;line-height:1px;font-size:1px;background:%s;">&nbsp;</td></tr></table>') % (m, LINE)

def btn(href, label, kind="primary", rel=""):
    """Bulletproof pill: a table cell carries the colour, the padded <a> is the hit area. kind: primary | outline."""
    r = (' rel="%s"' % rel) if rel else ""
    if kind == "outline":
        td = ('<td class="pc-out" align="center" bgcolor="#FFFFFF" style="border:1px solid %s;border-radius:999px;background:#FFFFFF;mso-padding-alt:13px 26px;">' % LINE)
        a = ('<a class="pc-ink" href="%s"%s style="display:inline-block;padding:13px 26px;font-family:%s;font-size:15px;line-height:18px;'
             'font-weight:600;color:%s;text-decoration:none;border-radius:999px;mso-padding-alt:0;">%s</a>') % (href, r, FONT, INK, label)
    else:
        td = ('<td class="pc-btn" align="center" bgcolor="%s" style="border-radius:999px;background:%s;mso-padding-alt:14px 30px;">' % (PRI, PRI))
        a = ('<a class="pc-btn-a" href="%s"%s style="display:inline-block;padding:14px 30px;font-family:%s;font-size:15px;line-height:18px;'
             'font-weight:600;color:%s;text-decoration:none;border-radius:999px;mso-padding-alt:0;">%s</a>') % (href, r, FONT, PRI_FG, label)
    return ('<table role="presentation" align="center" cellpadding="0" cellspacing="0" style="margin:0 auto;"><tr>%s%s</td></tr></table>' % (td, a))

def card(pid, p):
    img = esc(email_img(pid, p.get("img")) if p.get("img") else "")
    url = esc(site_link(SITE + "/product/" + urllib.parse.quote(pid)))   # track.js counts buy clicks from these visits as ~email
    title = esc(p.get("title") or "")
    well = ('<a href="%s" style="display:block;text-decoration:none;"><img class="pc-img" src="%s" width="232" height="232" alt="%s" '
            'style="display:block;width:100%%;max-width:232px;height:auto;margin:0 auto;border:0;outline:none;"></a>' % (url, img, title)) if img else "&nbsp;"
    pill = ('<td class="%s" align="center" bgcolor="%s" style="border-radius:999px;background:%s;mso-padding-alt:9px 0;%s">'
            '<a class="%s" href="%s" style="display:block;padding:9px 0;font-family:%s;font-size:13px;line-height:16px;font-weight:600;'
            'color:%s;text-decoration:none;border-radius:999px;mso-padding-alt:0;">%s</a></td>')
    pills = ('<table role="presentation" width="100%%" cellpadding="0" cellspacing="0" style="margin-top:12px;"><tr>%s'
             '<td width="8" style="width:8px;font-size:0;line-height:0;">&nbsp;</td>%s</tr></table>') % (
        pill % ("pc-out", "#FFFFFF", "#FFFFFF", "width:40%%;border:1px solid %s;" % LINE, "pc-ink", url + "#qc", FONT, INK, "QC"),
        pill % ("pc-btn", PRI, PRI, "", "pc-btn-a", url, FONT, PRI_FG, "Buy"))
    return ('<td class="pc-col" width="50%%" valign="top" style="width:50%%;padding:0 8px 28px;vertical-align:top;">'
            '<table role="presentation" width="100%%" cellpadding="0" cellspacing="0">'
            '<tr><td class="pc-well" bgcolor="%s" style="padding:14px;background:%s;border-radius:12px;">%s</td></tr>'
            '<tr><td style="padding:12px 2px 0;">'
            '<div class="pc-mut" style="font-family:%s;font-size:12px;line-height:16px;font-weight:500;color:%s;">%s</div>'
            '<a href="%s" class="pc-ink" style="display:block;height:38px;overflow:hidden;margin-top:3px;font-family:%s;font-size:14px;line-height:19px;font-weight:600;color:%s;text-decoration:none;">%s</a>'
            '<div class="pc-ink" style="margin-top:6px;font-family:%s;font-size:15px;line-height:20px;font-weight:700;color:%s;">%s</div>'
            '%s</td></tr></table></td>') % (WELL, WELL, well, FONT, MUT, esc(p.get("brand") or ""), url, FONT, INK, title,
                                            FONT, INK, usd(p), pills)

def grid(prods):
    rows = ""
    for i in range(0, len(prods), 2):
        pair = prods[i:i+2]
        cells = [card(pid, p) for pid, p in pair]
        cells[0] = cells[0].replace("padding:0 8px 28px;", "padding:0 8px 28px 0;", 1)   # gutter sits between the two cards
        if len(cells) > 1: cells[1] = cells[1].replace("padding:0 8px 28px;", "padding:0 0 28px 8px;", 1)
        cells = "".join(cells)
        if len(pair) == 1: cells += '<td class="pc-col pc-empty" width="50%" style="width:50%;"></td>'
        rows += "<tr>%s</tr>" % cells
    return ('<table role="presentation" width="100%" cellpadding="0" cellspacing="0" >'
            + rows + '</table>')

DARK_CSS = (
    # body reset, phone layout and dark mode; inline styles already give the light look, so a client that drops this block stays correct.
    # The Outlook.com [data-ogsc]/[data-ogsb] rules go in a second <style> in wrap(), so a client that rejects attribute selectors
    # cannot take the phone layout down with them. The color-scheme meta tags declare light/dark (no :root rule).
    "body{margin:0!important;padding:0!important;-webkit-text-size-adjust:100%;-ms-text-size-adjust:100%}"
    "a{text-decoration:none}"
    "@media only screen and (max-width:600px){"
    ".pc-pad{padding-left:20px!important;padding-right:20px!important}"
    ".pc-h1{font-size:26px!important}"
    ".pc-col{display:block!important;width:100%!important;box-sizing:border-box;padding-left:0!important;padding-right:0!important}"
    ".pc-empty{display:none!important}"
    ".pc-img{max-width:220px!important}"
    ".pcv-d{display:none!important;max-height:0!important;overflow:hidden!important}"
    ".pcv-m{display:block!important;max-height:none!important;overflow:visible!important}}"
    "@media (prefers-color-scheme:dark){__DARK__}"
)
_DARK_RULES = [
    (".pc-bg", "background:#0A0A0A!important;background-color:#0A0A0A!important"),
    (".pc-card", "background:#171717!important;background-color:#171717!important"),
    (".pc-well", "background:#262626!important;background-color:#262626!important"),
    (".pc-ink", "color:#FAFAFA!important"),
    (".pc-mut", "color:#A1A1A1!important"),
    (".pc-line", "background:#262626!important;background-color:#262626!important"),
    (".pc-btn", "background:#E5E5E5!important;background-color:#E5E5E5!important"),
    (".pc-btn-a", "color:#171717!important"),
    (".pc-out", "background:#0A0A0A!important;background-color:#0A0A0A!important;border-color:#333333!important"),
    (".pc-well .pc-out", "background:#262626!important;background-color:#262626!important"),
]
def _dark():
    return "".join("%s{%s}" % (sel, rule) for sel, rule in _DARK_RULES)

def wrap(inner, unsub):
    pre_text = ""
    m = re.match(r"<!--pre:(.*?)-->", inner, re.S)
    if m: pre_text, inner = m.group(1), inner[m.end():]
    ogsc = "".join("[data-ogsc] %s{%s}" % (sel, rule) for sel, rule in _DARK_RULES) + \
           "[data-ogsb] .pc-bg,[data-ogsb] .pc-out{background:#0A0A0A!important}[data-ogsb] .pc-well{background:#262626!important}[data-ogsb] .pc-btn{background:#E5E5E5!important}"
    css = DARK_CSS.replace("__DARK__", _dark())
    hidden = ('<div style="display:none;max-height:0;max-width:0;overflow:hidden;opacity:0;mso-hide:all;font-size:1px;line-height:1px;color:#FFFFFF;">%s%s</div>'
              % (pre_text, "&#8199;&#65279;&#847; " * 60)) if pre_text else ""
    return ("""<!DOCTYPE html><html lang="en" xmlns="http://www.w3.org/1999/xhtml" xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta http-equiv="X-UA-Compatible" content="IE=edge">
<meta name="color-scheme" content="light dark"><meta name="supported-color-schemes" content="light dark"><meta name="x-apple-disable-message-reformatting">
<title>Puro Classico</title>
<!--[if mso]><noscript><xml><o:OfficeDocumentSettings><o:PixelsPerInch>96</o:PixelsPerInch></o:OfficeDocumentSettings></xml></noscript><style>table,td,h1,h2,p,a,div{font-family:Arial,Helvetica,sans-serif!important}</style><![endif]-->
<style>%s</style>
<style>%s</style></head>
<body class="pc-bg" style="margin:0;padding:0;background:#FFFFFF;">%s
<table role="presentation" class="pc-bg" width="100%%" cellpadding="0" cellspacing="0" bgcolor="#FFFFFF" style="background:#FFFFFF;margin:0;padding:0;font-family:%s;">
<tr><td align="center" style="padding:0;">
<!--[if mso]><table role="presentation" width="600" cellpadding="0" cellspacing="0" align="center"><tr><td><![endif]-->
<table role="presentation" width="100%%" cellpadding="0" cellspacing="0" style="max-width:600px;margin:0 auto;">
<tr><td class="pc-pad" style="padding:28px 32px 20px;">
<table role="presentation" width="100%%" cellpadding="0" cellspacing="0"><tr>
<td align="left"><a href="%s" class="pc-ink" style="font-family:%s;font-size:18px;line-height:24px;font-weight:700;letter-spacing:-0.02em;color:#0A0A0A;text-decoration:none;">Puro Classico</a></td>
<td align="right"><a href="%s" class="pc-mut" style="font-family:%s;font-size:14px;line-height:24px;font-weight:500;color:#6B6B6B;text-decoration:none;">Browse Finds</a></td>
</tr></table></td></tr>
<tr><td class="pc-pad" style="padding:0 32px;"><table role="presentation" width="100%%" cellpadding="0" cellspacing="0"><tr><td class="pc-line" height="1" style="height:1px;line-height:1px;font-size:1px;background:#E5E5E5;">&nbsp;</td></tr></table></td></tr>
<tr><td class="pc-pad" style="padding:44px 32px 8px;font-family:%s;">%s</td></tr>
<tr><td class="pc-pad" style="padding:24px 32px 40px;">
<table role="presentation" width="100%%" cellpadding="0" cellspacing="0"><tr><td class="pc-line" height="1" style="height:1px;line-height:1px;font-size:1px;background:#E5E5E5;">&nbsp;</td></tr></table>
<p class="pc-mut" style="margin:20px 0 6px;font-family:%s;font-size:12px;line-height:1.6;color:#6B6B6B;text-align:center;">You get this email because you have an account at <a href="%s" class="pc-mut" style="color:#6B6B6B;text-decoration:underline;">puroclassico.com</a>. Our links to shopping agents are affiliate links. <a href="%s" class="pc-mut" style="color:#6B6B6B;text-decoration:underline;">Unsubscribe from marketing emails</a>.</p>
<p class="pc-mut" style="margin:0;font-family:%s;font-size:12px;line-height:1.6;color:#6B6B6B;text-align:center;">&copy; Puro Classico</p>
</td></tr>
</table>
<!--[if mso]></td></tr></table><![endif]-->
</td></tr></table></body></html>""") % (css, ogsc, hidden, FONT, esc(site_link(SITE)), FONT, esc(site_link(SITE)), FONT, FONT, inner, FONT, esc(site_link(SITE)), esc(unsub), FONT)

WELCOME_SUBJECT = "You're in: your MyCNBox coupons are inside"

def welcome_html(uid):
    """1st email, sent to every new member. The sign-up window promises "we email you up to $500 in MyCNBox new-user
    coupons", so the coupon link comes first, in the same words as the site (21 Oct 2026); before, it was the last button
    of email 2."""
    steps = [("1", "Make An Agent Account", "Sign up free with an agent like MyCNBox or KakoBuy. They buy from Chinese sellers for you."),
             ("2", "Order And Check QC", "Open a find, buy it through your agent and check the warehouse photos before anything ships."),
             ("3", "Ship One Parcel", "Bundle your haul into one parcel and pick a shipping line that fits your country and budget.")]
    # stacked rows on every screen (like the ordering steps), so it reads right even when a client drops <style>
    spacer = '<tr><td height="10" style="height:10px;line-height:10px;font-size:10px;">&nbsp;</td></tr>'
    cells = spacer.join(
        ('<tr><td class="pc-well" valign="top" bgcolor="#F5F5F5" style="padding:18px;vertical-align:top;background:#F5F5F5;border-radius:12px;">'
         '<table role="presentation" width="100%%" cellpadding="0" cellspacing="0"><tr><td valign="top" style="width:28px;padding:0 14px 0 0;vertical-align:top;">'
         '<table role="presentation" cellpadding="0" cellspacing="0"><tr><td class="pc-btn" align="center" valign="middle" bgcolor="#171717" width="28" height="28" '
         'style="width:28px;height:28px;border-radius:999px;background:#171717;font-family:%s;font-size:13px;line-height:28px;font-weight:700;"><span class="pc-btn-a" style="color:#FAFAFA;">%s</span></td></tr></table></td>'
         '<td valign="top" style="vertical-align:top;">'
         '<div class="pc-ink" style="margin:4px 0 4px;font-family:%s;font-size:15px;line-height:20px;font-weight:600;color:#0A0A0A;">%s</div>'
         '<div class="pc-mut" style="font-family:%s;font-size:14px;line-height:21px;color:#6B6B6B;">%s</div></td></tr></table></td></tr>')
        % (FONT, n, FONT, h, FONT, b) for n, h, b in steps)
    # the coupon block comes first, right under the intro (the sign-up window promises it): a grey well like the step rows
    coupons = ('<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>'
        '<td class="pc-well" align="center" bgcolor="#F5F5F5" style="padding:28px 22px 30px;background:#F5F5F5;border-radius:12px;text-align:center;">'
        '<img src="' + MYCNBOX_LOGO + '" alt="MyCNBox" width="48" height="48" style="display:inline-block;width:48px;height:48px;border:0;border-radius:12px;">'
        '<div style="height:12px;line-height:12px;font-size:12px;">&nbsp;</div>'
        + h2("Your MyCNBox Coupons")
        + lead("New to MyCNBox? Sign up with our link for up to $500 in new-user coupons. It's free and takes about a minute.", 15, 20)
        + btn(MYCNBOX_URL, "Claim Your Coupons", "primary", "sponsored nofollow noopener")
        + '</td></tr></table>')
    inner = (pre("Your MyCNBox coupons are inside, plus how your first haul works.")
      + h1("You're In. Find It. QC It. Buy It.")
      + lead("Thousands of quality-checked Weidian, Taobao and 1688 finds, one tap from your agent. Save what you like with the star and pick up where you left off any time.")
      + coupons
      + '<div style="height:24px;line-height:24px;font-size:24px;">&nbsp;</div>'
      + btn(esc(site_link(SITE)), "Browse Finds", "outline")
      + hr("44px 0 36px")
      + h2("Your First Haul In 3 Steps", "left")
      + '<div style="height:8px;line-height:8px;font-size:8px;">&nbsp;</div>'
      + '<table role="presentation" width="100%" cellpadding="0" cellspacing="0">' + cells + '</table>'
      + hr("36px 0 32px")
      + h2("Join The Community")
      + lead("Early drops, QC talk and haul reviews from other members over on Discord.", 15, 20)
      + btn(DISCORD_URL, '<img src="%s" alt="" width="18" height="18" style="width:18px;height:18px;vertical-align:-3px;margin-right:8px;border:0;border-radius:4px;">Join Our Discord' % DISC, "outline"))
    return wrap(inner, unsub_url(uid))

def run_welcome(profiles):
    sent = 0
    for pr in profiles:
        if pr.get("welcomed"): continue
        email = pr.get("email")
        if not email: continue
        ok, msg = brevo_send(email, WELCOME_SUBJECT, welcome_html(pr["id"]), unsub_url(pr["id"]), "welcome")
        if ok:
            sb("profiles?id=eq." + pr["id"], "PATCH", {"welcomed": True, "welcomed_at": datetime.now(timezone.utc).isoformat()}, {"Prefer": "return=minimal"})
            sent += 1
        else:
            print("FAIL welcome:", hide(msg))
        if sent >= MAX_SEND: break
        time.sleep(0.3)
    print("welcome sent:", sent)

def run_welcome_test(_profiles=None):
    email = os.environ.get("TEST_EMAIL", "").strip()
    if not email: print("TEST_EMAIL not set"); return
    ok, msg = brevo_send(email, WELCOME_SUBJECT, welcome_html("test"), None, "test")
    print("welcome-test sent" if ok else ("FAIL welcome-test: " + hide(msg)))

ORDERING_SUBJECT = "How to order from Puro Classico (1:47 video)"
VIDEO_PAGE = SITE + "/how-to-order"

def ordering_html(uid):
    """Build the 'How to order' email: the video guide (phone thumbnail on phones, 16:9 on desktop) + the 6 steps in short.
    Used by the real send and the test send."""
    steps = [
        ("1", "Create Your Free MyCNBox Account", "Sign up through Puro Classico and unlock up to $500 in new-user coupons."),
        ("2", "Tap Buy via MyCNBox", "Open any find on Puro Classico. The exact listing opens inside MyCNBox, pre-filled."),
        ("3", "Pick Size And Colour, Check Out", "You only pay for the item + delivery to the warehouse in China. International shipping comes later."),
        ("4", "Check Your QC Photos", "Real photos appear under Warehouse. Check logos, stitching, colour and the size tag."),
        ("5", "Submit Packing And Pay Shipping", "Combine your items into one parcel, choose a carrier and apply your coupon."),
        ("6", "Track It Under Parcels", "It leaves the warehouse within 24 hours and usually arrives in 1-3 weeks."),
    ]
    rows = ""
    for n, h, b in steps:
        rows += ('<tr><td valign="top" style="padding:0 14px 20px 0;vertical-align:top;width:28px;">'
                 '<table role="presentation" cellpadding="0" cellspacing="0"><tr><td class="pc-btn" align="center" valign="middle" bgcolor="#171717" width="28" height="28" '
                 'style="width:28px;height:28px;border-radius:999px;background:#171717;font-family:%s;font-size:13px;line-height:28px;font-weight:700;">'
                 '<span class="pc-btn-a" style="color:#FAFAFA;">%s</span></td></tr></table></td>'
                 '<td valign="top" style="padding:0 0 20px;vertical-align:top;">'
                 '<div class="pc-ink" style="margin:4px 0 4px;font-family:%s;font-size:15px;line-height:20px;font-weight:600;color:#0A0A0A;">%s</div>'
                 '<div class="pc-mut" style="font-family:%s;font-size:14px;line-height:21px;color:#6B6B6B;">%s</div></td></tr>') % (FONT, n, FONT, h, FONT, esc(b))
    video = ('<a class="pcv-d" href="%s" style="display:block;text-decoration:none;">'
             '<img src="%s/media/how-to-order-email.jpg" width="536" alt="Watch: How to order with MyCNBox (1:47)" style="display:block;width:100%%;max-width:536px;height:auto;border:0;border-radius:12px;margin:0 auto;"></a>'
             '<!--[if !mso]><!--><a class="pcv-m" href="%s" style="display:none;max-height:0;overflow:hidden;text-decoration:none;">'
             '<img src="%s/media/how-to-order-email-portrait.jpg" width="280" alt="Watch: How to order with MyCNBox (1:47)" style="display:block;width:280px;max-width:85%%;height:auto;border:0;border-radius:12px;margin:0 auto;"></a><!--<![endif]-->'
             ) % (esc(site_link(VIDEO_PAGE + "?f=landscape")), SITE, esc(site_link(VIDEO_PAGE + "?f=portrait")), SITE)
    inner = (pre("Watch the 1:47 video, then follow 6 short steps from Buy to your door.")
      + h1("How To Order Your First Find")
      + lead("First haul from China? Watch the 1:47 video and you'll know the whole flow, from tapping Buy to tracking your parcel.")
      + '<div style="text-align:center;margin:0 0 24px;">' + video + '</div>'
      + btn(esc(site_link(VIDEO_PAGE)), "&#9654;&nbsp; Watch The Video")
      + hr("44px 0 36px")
      + h2("The 6 Steps In Short", "left")
      + '<div style="height:12px;line-height:12px;font-size:12px;">&nbsp;</div>'
      + '<table role="presentation" width="100%" cellpadding="0" cellspacing="0">' + rows + '</table>'
      + '<div style="height:8px;line-height:8px;font-size:8px;">&nbsp;</div>'
      + btn(MYCNBOX_URL, "Claim Your MyCNBox Coupons", "outline", "sponsored nofollow noopener")
      + '<p class="pc-mut" style="margin:24px auto 0;max-width:420px;font-family:' + FONT + ';font-size:14px;line-height:1.6;color:#6B6B6B;text-align:center;">Stuck on anything? Ask in our <a href="' + DISCORD_URL + '" class="pc-ink" style="color:#0A0A0A;text-decoration:underline;">Discord</a>. Members share QC tips and haul reviews daily.</p>')
    # wrap() returns the full document; its <style> in <head> swaps in the vertical video thumbnail on phones.
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
        ok, msg = brevo_send(email, ORDERING_SUBJECT, ordering_html(pr["id"]), unsub_url(pr["id"]), "ordering")
        if ok:
            sb("profiles?id=eq." + pr["id"], "PATCH", {"ordering_sent": True}, {"Prefer": "return=minimal"})
            sent += 1
        else:
            print("FAIL ordering:", hide(msg))
        if sent >= MAX_SEND: break
        time.sleep(0.3)
    print("ordering sent:", sent)

def run_ordering_test(_profiles=None):
    """Send the ordering guide to a single TEST_EMAIL, ignoring DB gating and marking nothing. For previews."""
    email = os.environ.get("TEST_EMAIL", "").strip()
    if not email: print("TEST_EMAIL not set"); return
    ok, msg = brevo_send(email, ORDERING_SUBJECT, ordering_html("test"), None)
    print("ordering-test sent" if ok else ("FAIL ordering-test: " + hide(msg)))

def mycnbox_html(uid):
    """3rd email in the sequence: nudge to create a MyCNBox account (our featured agent)."""
    inner = (pre("Free sign-up, about a minute. Your new-member coupons are waiting.")
      + '<div style="text-align:center;margin:0 0 20px;"><img src="' + MYCNBOX_LOGO + '" alt="MyCNBox" width="64" height="64" style="display:inline-block;width:64px;height:64px;border:0;border-radius:16px;"></div>'
      + h1("Ready To Order? Set Up MyCNBox")
      + lead("To actually buy your finds you need an <strong class=\"pc-ink\" style=\"color:#0A0A0A;font-weight:600;\">agent</strong>: the service that buys each item in China, checks it and ships it to you. "
             "We've tried them all, and <strong class=\"pc-ink\" style=\"color:#0A0A0A;font-weight:600;\">MyCNBox</strong> is the one we recommend: the cleanest app, fast QC photos and the best new-member coupon bundle.", 16, 28)
      + btn(MYCNBOX_URL, "Create Your Free MyCNBox Account", "primary", "sponsored nofollow noopener")
      + lead("Signing up is free and takes about a minute. Grab your new-member coupons before your first haul.", 13, 0).replace("margin:0 auto 0px", "margin:16px auto 0")
      + hr("40px 0 28px")
      + '<p class="pc-mut" style="margin:0 auto;max-width:420px;font-family:' + FONT + ';font-size:14px;line-height:1.6;color:#6B6B6B;text-align:center;">New to all this? Read our quick <a href="' + esc(site_link(SITE + '/#tutorial')) + '" class="pc-ink" style="color:#0A0A0A;text-decoration:underline;">How to order</a> guide first, or ask in the <a href="' + DISCORD_URL + '" class="pc-ink" style="color:#0A0A0A;text-decoration:underline;">Discord</a>.</p>')
    return wrap(inner, unsub_url(uid))

def run_mycnbox(profiles):
    """Sent AGENT_DELAY_MINUTES (default 1 day) after signup, once, to welcomed users who haven't had it yet."""
    delay_m = int(os.environ.get("AGENT_DELAY_MINUTES", "1440"))
    cutoff  = datetime.now(timezone.utc) - timedelta(minutes=delay_m)
    def eligible(pr):
        if not pr.get("welcomed") or pr.get("agent_sent"): return False
        wa = pr.get("welcomed_at")
        if not wa: return True
        try: return datetime.fromisoformat(wa.replace("Z", "+00:00")) <= cutoff
        except: return True
    due = [pr for pr in profiles if pr.get("email") and eligible(pr)]
    cap = slots("mycnbox") if due else 0
    sent = fails = 0
    for pr in due:
        if sent >= cap: print("::warning::mycnbox: %d members wait for tomorrow to stay under the Brevo daily cap" % (len(due) - sent)); break
        ok, msg = brevo_send(pr["email"], "Set up MyCNBox, your finds are waiting", mycnbox_html(pr["id"]), unsub_url(pr["id"]), "mycnbox")
        if ok:
            sb("profiles?id=eq." + pr["id"], "PATCH", {"agent_sent": True}, {"Prefer": "return=minimal"})
            sent += 1; fails = 0
        else:
            print("FAIL mycnbox:", hide(msg)); fails += 1
            if fails >= 5: print("stopping: 5 sends in a row failed (daily cap reached?)"); break
        time.sleep(0.3)
    print("mycnbox sent:", sent)

def run_mycnbox_test(_profiles=None):
    email = os.environ.get("TEST_EMAIL", "").strip()
    if not email: print("TEST_EMAIL not set"); return
    ok, msg = brevo_send(email, "Set up MyCNBox, your finds are waiting", mycnbox_html("test"), None)
    print("mycnbox-test sent" if ok else ("FAIL mycnbox-test: " + hide(msg)))

def load_stats():
    """Site-wide popularity per product from data/stats.json: [views all time, views 30 days, views 7 days, favourites]."""
    try:
        req = urllib.request.Request(SITE + "/data/stats.json", headers={"User-Agent": "Mozilla/5.0"})
        return json.loads(urllib.request.urlopen(req, timeout=40).read().decode()).get("p") or {}
    except Exception as e:
        print("could not load stats:", e); return {}

def pop_score(v):
    """Favourites weigh the most, then this week's views, then the month's."""
    v = list(v) + [0, 0, 0, 0]
    return 10 * v[3] + 2 * v[2] + v[1] + 0.05 * v[0]

def run_newsletter(profiles):
    import random
    prod, ids = load_products()
    stats = load_stats()
    score = {i: pop_score(stats[i]) for i in ids if i in stats}
    ranked = sorted((i for i in score if score[i] > 0), key=lambda i: -score[i])
    POOL = ranked[:max(60, len(ranked) // 8)]                # only the most viewed and favourited products can go in an email
    print("popular pool: %d of %d products" % (len(POOL), len(ids)))
    if len(POOL) < 6: print("not enough popularity data - nothing sent"); return
    top_score = score[POOL[0]] or 1.0
    def pick(n, weight, exclude=(), per_brand=2, rnd=None):
        """Best n from the popular pool by weight; at most per_brand per brand so one label does not fill the email."""
        order = sorted(POOL, key=lambda i: -(weight(i) * ((0.75 + 0.5 * rnd.random()) if rnd else 1)))
        out, seen_b = [], {}
        for i in order:
            if i in exclude: continue
            b = prod[i].get("brand") or ""
            if seen_b.get(b, 0) >= per_brand: continue
            seen_b[b] = seen_b.get(b, 0) + 1; out.append((i, prod[i]))
            if len(out) >= n: break
        return out
    # each member's taste: brands and categories they viewed, favourites count triple
    views = sb_all("product_views?select=user_id,product_id,brand,cat,viewed_at&user_id=not.is.null&viewed_at=gte.%s&order=viewed_at.desc" % since(60))
    favs  = sb_all("favorites?select=user_id,product_id&order=user_id,product_id")
    print("taste data: %d product views (60 days), %d favourites" % (len(views), len(favs)))
    by_user = {}
    def U(u): return by_user.setdefault(u, {"brands": {}, "cats": {}, "seen": set(), "last": None, "favs": 0})
    for v in views:
        u = U(v["user_id"]); b = v.get("brand"); c = v.get("cat")
        if b: u["brands"][b] = u["brands"].get(b, 0) + 1
        if c: u["cats"][c] = u["cats"].get(c, 0) + 1
        u["seen"].add(v["product_id"])
        t = v.get("viewed_at")
        if t and (u["last"] is None or t > u["last"]): u["last"] = t
    for f in favs:
        u = U(f["user_id"]); pid = f["product_id"]; u["seen"].add(pid); u["favs"] += 1; p = prod.get(pid) or {}
        if p.get("brand"): u["brands"][p["brand"]] = u["brands"].get(p["brand"], 0) + 3
        if p.get("cat"): u["cats"][p["cat"]] = u["cats"].get(p["cat"], 0) + 3
    cutoff = datetime.now(timezone.utc) - timedelta(days=ACTIVE_DAYS)
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    def tier(pr):   # who goes first when the day's budget runs short: active savers, active, savers, the rest
        u = by_user.get(pr["id"]); act = False
        if u and u["last"]:
            try: act = datetime.fromisoformat(u["last"].replace("Z", "+00:00")) >= cutoff
            except Exception: act = True
        fav = bool(u and u["favs"])
        return 0 if act and fav else 1 if act else 2 if fav else 3
    queue = [pr for pr in profiles if pr.get("email") and not welcomed_lately(pr)]
    queue.sort(key=lambda pr: (tier(pr), hashlib.sha256((pr["id"] + day).encode()).hexdigest()))   # a different order each day within a tier
    cap = slots("newsletter")
    print("newsletter queue: %d members (%d welcomed in the last 48 h left out)" % (len(queue), len(profiles) - len(queue)))
    sent = fails = 0
    for pr in queue:
        if sent >= cap: print("::warning::newsletter: %d members not sent today to stay under the Brevo daily cap" % (len(queue) - sent)); break
        email = pr.get("email"); uid = pr["id"]
        u = by_user.get(uid)
        active = False
        if u and u["last"]:
            try: active = datetime.fromisoformat(u["last"].replace("Z", "+00:00")) >= cutoff
            except: active = True
        perso = bool(active and u and u["brands"])
        rnd = random.Random(uid + day)                       # a different mix each send, stable within one send
        if perso:
            bt = float(max(u["brands"].values())); ct = float(max(u["cats"].values())) if u["cats"] else 1.0
            tset = [b for b, _ in sorted(u["brands"].items(), key=lambda kv: -kv[1])[:3]]
            def w(i):
                p = prod[i]
                taste = 3.0 * u["brands"].get(p.get("brand"), 0) / bt + 1.0 * u["cats"].get(p.get("cat"), 0) / ct
                return (score[i] / top_score) * (1.0 + taste)      # popularity first, their taste multiplies it up to 5x
            recs = pick(6, w, exclude=u["seen"], rnd=rnd)
            if len(recs) < 6: recs += pick(6 - len(recs), w, exclude={i for i, _ in recs}, rnd=rnd)
            shown = [b for b in tset if any(p.get("brand") == b for _, p in recs)]
            intro = (pre("The most viewed and saved finds right now, matched to what you've been eyeing.")
                     + h1("Popular Finds Picked For You")
                     + lead("The most viewed and saved finds right now, picked to match what you've been eyeing%s." %
                            (" (" + esc(", ".join(shown[:2])) + ")" if shown else ""), 16, 36))
            subject = ("Popular %s finds picked for you" % shown[0]) if shown else "Popular finds picked for you"
            body = intro + grid(recs)
            body += '<div style="height:8px;line-height:8px;font-size:8px;">&nbsp;</div>' + btn(esc(site_link(SITE)), "Browse All Finds")
        else:
            recs = pick(6, lambda i: score[i] / top_score, rnd=rnd)
            intro = (pre("What everyone is viewing and saving on Puro Classico right now.")
                     + h1("Most Popular Right Now")
                     + lead("What everyone is viewing and saving on Puro Classico right now.", 16, 36))
            subject = "The most popular finds at Puro Classico right now"
            body = intro + grid(recs)
            body += '<div style="height:8px;line-height:8px;font-size:8px;">&nbsp;</div>' + btn(esc(site_link(SITE)), "Browse All Finds")
        if os.environ.get("DRY_RUN"):
            print("DRY tier %d %s | %s | %s" % (tier(pr), "perso" if perso else "generic", subject, "; ".join("%s (%d)" % (p.get("title", "")[:28], score[i]) for i, p in recs)))
            sent += 1; continue
        html = wrap(body, unsub_url(uid))
        ok, msg = brevo_send(email, subject, html, unsub_url(uid), "newsletter")
        if ok: sent += 1; fails = 0
        else:
            print("FAIL news:", hide(msg)); fails += 1
            if fails >= 5: print("stopping: 5 sends in a row failed (daily cap reached?)"); break
        time.sleep(0.35)
    print("newsletter %s: %d" % ("would send (dry run)" if os.environ.get("DRY_RUN") else "sent", sent))

def load_gone():
    """Finds the weekly link check found removed or sold out (data/link_health.json): never sent as "still in the catalogue"."""
    try:
        req = urllib.request.Request(SITE + "/data/link_health.json", headers={"User-Agent": "Mozilla/5.0"})
        h = json.loads(urllib.request.urlopen(req, timeout=40).read().decode())
        return set(map(str, (h.get("dead") or []) + (h.get("sold_out") or [])))
    except Exception as e:
        print("link check not readable:", hide(e)); return set()

def run_saved(profiles):
    """Weekly nudge: 'you saved this' for members who starred something in the last SAVED_DAYS days (each save is mentioned once)."""
    days = int(os.environ.get("SAVED_DAYS", "7"))
    prod, _ = load_products()
    gone = load_gone()
    try: favs = sb_all("favorites?select=user_id,product_id,created_at&created_at=gte.%s&order=created_at.desc,user_id,product_id" % since(days + 1))
    except Exception as e: print("favorites have no created_at to go by - nothing sent:", e); return
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    recent = {}
    for f in favs:
        try: fresh = datetime.fromisoformat((f.get("created_at") or "").replace("Z", "+00:00")) >= cutoff
        except Exception: fresh = False
        if fresh and f["product_id"] in prod and f["product_id"] not in gone: recent.setdefault(f["user_id"], []).append(f["product_id"])
    due = [pr for pr in profiles if pr.get("email") and recent.get(pr["id"]) and not welcomed_lately(pr)]
    cap = slots("saved") if due else 0
    sent = fails = 0
    for pr in due:
        if sent >= cap: print("::warning::saved: %d members not sent today to stay under the Brevo daily cap" % (len(due) - sent)); break
        email = pr["email"]; uid = pr["id"]; ids = recent[uid]
        recs = [(i, prod[i]) for i in ids[:4]]
        first = recs[0][1]
        subject = "Still thinking about the %s?" % (first.get("title") or "find you saved")[:60]
        body = (pre("Your saved finds are still in the catalogue, one tap from your agent.")
                + h1("Still Thinking It Over?")
                + lead("You saved %s this week. %s still in the catalogue, one tap from your agent." %
                       ("this" if len(recs) == 1 else "these", "It is" if len(recs) == 1 else "They are"), 16, 36)) + grid(recs)
        body += '<div style="height:8px;line-height:8px;font-size:8px;">&nbsp;</div>' + btn(esc(site_link(SITE + "/?saved=1")), "See Your Saved Finds")
        if os.environ.get("DRY_RUN"): print("DRY saved | %s | %d items" % (subject, len(recs))); sent += 1; continue
        ok, msg = brevo_send(email, subject, wrap(body, unsub_url(uid)), unsub_url(uid), "saved")
        if ok: sent += 1; fails = 0
        else:
            print("FAIL saved:", hide(msg)); fails += 1
            if fails >= 5: print("stopping: 5 sends in a row failed (daily cap reached?)"); break
        time.sleep(0.35)
    print("saved-finds emails %s: %d" % ("would send (dry run)" if os.environ.get("DRY_RUN") else "sent", sent))

def run_sync(profiles):
    """Mirror members into Brevo contacts so opens and clicks show per person there. Nothing is blocked here: who gets marketing email is still decided by marketing_opt_in."""
    done = 0
    for pr in profiles:
        email = pr.get("email")
        if not email: continue
        body = {"email": email, "updateEnabled": True}
        req = urllib.request.Request("https://api.brevo.com/v3/contacts", data=json.dumps(body).encode(),
            headers={"api-key": BREVO, "accept": "application/json", "content-type": "application/json"}, method="POST")
        try: urllib.request.urlopen(req, timeout=30); done += 1
        except urllib.error.HTTPError as e: print("FAIL sync:", e.code, hide(e.read().decode()))
        time.sleep(0.12)
    print("contacts synced to Brevo:", done)

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "newsletter"
    global CAMPAIGN   # the campaign tag on site links in this run's emails (site_link)
    CAMPAIGN = mode if mode in ("welcome", "ordering", "mycnbox", "saved", "welcome-test", "ordering-test", "mycnbox-test") else "newsletter"
    if mode == "ordering-test":
        run_ordering_test(); return
    if mode == "mycnbox-test":
        run_mycnbox_test(); return
    if mode == "welcome-test":
        run_welcome_test(); return
    if mode == "welcome":
        profiles = sb_all("profiles?select=id,email,welcomed,welcomed_at&order=id")     # welcome = transactional, all signups
    elif mode == "ordering":
        profiles = sb_all("profiles?welcomed=eq.true&select=id,email,welcomed,welcomed_at,ordering_sent&order=id")  # ordering guide = 2nd in sequence, transactional
    elif mode == "mycnbox":
        # 3rd in sequence: the create-a-MyCNBox-account nudge is marketing, so only members who opted in to marketing email
        profiles = sb_all("profiles?welcomed=eq.true&marketing_opt_in=eq.true&select=id,email,welcomed,welcomed_at,agent_sent&order=id")
    elif mode == "sync":
        profiles = sb_all("profiles?select=id,email&order=id")
    else:
        profiles = sb_all("profiles?marketing_opt_in=eq.true&select=id,email,welcomed,welcomed_at&order=id")
    print("mode=%s profiles=%d" % (mode, len(profiles)))
    {"welcome": run_welcome, "ordering": run_ordering, "mycnbox": run_mycnbox, "saved": run_saved, "sync": run_sync}.get(mode, run_newsletter)(profiles)

if __name__ == "__main__":
    main()
