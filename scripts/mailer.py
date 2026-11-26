# -*- coding: utf-8 -*-
"""
Puro Classico email engine (Email v2, 26 Nov 2026). It does all the sending; scripts/newsletter.py stays in the repo as
the old reference only. Run by .github/workflows/email.yml.

  python scripts/mailer.py run        every 15 minutes, everything due now, in this order:
                                        1. W0, the coupon email, to new members (all of them: they asked for it at sign-up)
                                        2. the welcome series W1 to W3 when due (marketing consent)
                                        3. saved-find alerts (daily, from 16:00 UTC)
                                        4. weekly picks (Thursday from 16:00 UTC, in daily slices while the domain warms up)
                                        5. win-back emails, then the sunset flag
  python scripts/mailer.py backfill   by hand, after an outage: one combined, honest "sorry this is late" W0 for members
                                        who signed up in the last 14 days and got no welcome. Older unwelcomed members are
                                        marked welcomed without an email. Respects the warm-up cap: run it again the next
                                        day for the rest.
  python scripts/mailer.py preview [DIR]  every template and variant as HTML files in DIR (default email_preview): sample
                                        members, real catalogue data over HTTP. No sends, no database writes, no uploads.
  python scripts/mailer.py test       TEST_TEMPLATE (a template, a preview name, or "all") to TEST_EMAIL only, with real
                                        tracked links. Nothing is written to profiles or email_sends (no test in /stats).
  python scripts/mailer.py import-suppression   once: Brevo's blocked contacts (BREVO_API_KEY) into email_suppression.
  Any other mode exits 2 (the old engine sent the newsletter on a typo).

Providers (one adapter each, one setting per stream, GitHub Actions variables):
  PROVIDER_AUTOMATED  welcome series, alerts, win-back   plunk (default) or ahasend, from FROM_AUTOMATED
  PROVIDER_NEWS       weekly picks                        plunk (default) or ahasend, from FROM_NEWS
  FROM_NAME, REPLY_TO, FOOTER_ADDRESS (the postal address line in every footer; left out when empty).
  Secrets: PLUNK_API_KEY, AHASEND_API_KEY and AHASEND_ACCOUNT_ID, SUPABASE_SERVICE_KEY, UNSUB_SECRET.
  A stream on Plunk without PLUNK_API_KEY: one ::warning:: line and exit 0 (the daily health check reports it). A stream
  set to ahasend without its keys stops the run at the start with an error.
Settings: ALERTS_PARTNER_ONLY (default 1), EMAIL_LOGOS (default 1), MAX_DAILY, MAX_PER_RUN, SUNSET_MIN_EMAILS (default 0),
STOP_LINES_OFF_UNTIL (a date: the stop lines are ignored until then, after the owner has checked).
Needs scripts/email_v2.sql and scripts/email_v2_engine.sql in Supabase.

Rules (owner, brief and the final research report, 26 Nov 2026):
- Addresses come from Supabase Auth (admin API), never from profiles.email, which the browser writes: only members whose
  auth email is confirmed (or Google sign-in). If the admin API cannot be read the run stops.
- One email_sends row per send, written before the provider call ('sending'), then 'sent' or 'failed'. A unique index on
  (member_id, template, campaign_key) over every row that did not fail makes a re-run safe; alerts, picks and win-back
  use a dated campaign key. Each call carries an Idempotency-Key (the row id), so a retried request never sends twice.
- Suppression list and opt-out are read again right before each send: /v1/send ignores Plunk's subscription state.
  `subscribed` is never sent to Plunk (true would re-subscribe people who left).
- Clicks are counted per email, not per person (tracking_law.md): links carry the batch id that every recipient of one
  template, variant and day shares. No open pixel; Plunk's and AhaSend's own tracking are off. Unsubscribe and the
  List-Unsubscribe header are always direct.
- No email settings page (owner, 26 Nov 2026): the footer has Unsubscribe only. The two yes-switches that page held stay
  off for everyone: "Measure my email clicks" (profiles.email_track: links with the send's own id) and "Personalise my
  emails from finds I view" (profiles.email_personal). Picks use saves, style and size. The code still honours a yes.
- Marketing cap: 1 a day (20 hours) and 3 a week per member, counting alerts, weekly picks and win-back; the welcome
  series and W0 do not count, but the welcome series and marketing email still keep 20 hours apart (one email a day,
  W0 excepted). Weekly picks only after W3.
- Warm-up by engagement: weekly picks and alerts go first to members active (a product view or a sign-in) within 30
  days, in daily slices, then 60, then 90 days (PICKS_RAMP); the daily cap table (RAMP) stays as a second safety, W0
  never waits for it. Win-back starts in week 4.
- Stop lines (read from email_events before marketing goes out): complaints at 0.1% of 30 days' sends, 3 complaints in
  24 hours in the first 30 days (Plunk switches a new project off at 7), or hard bounces at 2% of the last day's sends.
  Marketing then stops with an ::error:: until the owner clears it; W0 still goes out.
- Win-back after 60 and 90 days without a visit or sign-in; sunset (no marketing) after 120, lifted by the next visit.
- Logo watches, monogram bags and the brands in LUXURY go in emails like any other find (owner, 26 Nov 2026);
  EMAIL_LOGOS=0 leaves them out again. Never a find whose title has a banned word. At least 500 characters of real text.
- Subjects: under 25 characters for weekly picks, 25 to 35 for alerts and the welcome series, no emojis, no first names,
  no fashion brand names; preheaders of 30 to 50 characters.
- Public logs: never an email address (hide()).
"""
import hashlib, hmac, html as htmllib, io, json, math, os, random, re, sys, time, unicodedata, urllib.error, urllib.parse, urllib.request, uuid
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mail_links  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUPA_URL = "https://uptpghuduqjqmrxwatbm.supabase.co"
SITE = mail_links.SITE
FB_SITE = "https://fb.puroclassico.com"
PLUNK_API = "https://next-api.useplunk.com"
AHASEND_API = "https://api.ahasend.com"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"


def env(name, default=""):
    return (os.environ.get(name) or "").strip() or default


SVC = env("SUPABASE_SERVICE_KEY")
PLUNK_KEY = env("PLUNK_API_KEY")
AHA_KEY, AHA_ACCOUNT = env("AHASEND_API_KEY"), env("AHASEND_ACCOUNT_ID")
FROM = {"automated": env("FROM_AUTOMATED", "hello@notify.puroclassico.com"), "news": env("FROM_NEWS", "news@news.puroclassico.com")}
FROM_NAME = env("FROM_NAME", "Puro Classico")
REPLY_TO = env("REPLY_TO", "hello@puroclassico.com")
FOOTER_ADDRESS = env("FOOTER_ADDRESS")
ALERTS_PARTNER_ONLY = env("ALERTS_PARTNER_ONLY", "1") not in ("0", "false", "no")
MAX_DAILY = int(env("MAX_DAILY", "0") or 0)
MAX_PER_RUN = int(env("MAX_PER_RUN", "600"))
SEND_PAUSE = float(env("SEND_PAUSE", "0.15"))
CHECK_WAIT = float(env("CHECK_WAIT", "45"))
SUNSET_MIN_EMAILS = int(env("SUNSET_MIN_EMAILS", "0") or 0)

# Warm-up. RAMP: days since the first send (day 1 = that day) -> the most emails of all kinds that day, W0 never held
# back. PICKS_RAMP: until day -> weekly picks and alerts only for members active within this many days, and at most
# this many weekly picks a day (None: no slice, RAMP alone). Research: start with engaged members, grow 1.5 to 2 times a
# week, never double suddenly (Google), and a new Plunk project switches itself off at 7 complaints in 24 hours.
RAMP = ((3, 150), (7, 250), (14, 400), (21, 700), (28, 1200), (None, 2500))
PICKS_RAMP = ((7, 30, 150), (14, 60, 300), (21, 90, 600), (None, 90, None))
WINBACK_FROM_DAY = 22                   # win-back starts in week 4 of sending
FREQ_GAP = timedelta(hours=20)          # 1 marketing email a day per member ...
FREQ_WEEK = 3                           # ... and 3 a week
FREQ_TEMPLATES = ("alert", "picks", "wb1", "wb2")   # what counts; the welcome series and W0 do not
ENGAGED = timedelta(days=30)            # a product view or a sign-in in the last 30 days: goes first in every stream
SEND_HOUR = 16                          # 16:00 UTC, early evening in Europe: series due times, alerts, picks, win-back
W0_WINDOW = timedelta(hours=48)         # run mode welcomes members of the last 48 hours (older ones: backfill)
W0_LATE = timedelta(hours=12)           # a member who waited longer than this gets the honest late version
BACKFILL_DAYS = 14
ONBOARD_DAYS = {1: 1, 2: 3, 3: 6}       # W1 the day after W0, W2 on day 3, W3 on day 6 (16:00 UTC)
ONBOARD_WINDOW = timedelta(days=21)     # the welcome series is for new members only
PICKS_WEEKDAY = 3                       # Thursday
WINBACK = (60, 90)                      # WB1 and WB2 after this many days without a visit or sign-in
SUNSET_DAYS = 120
SAVE_ALIVE = timedelta(days=90)         # a save not touched for 90 days stops alerting
DROP_PCT, DROP_USD, DROP_MAX = 0.10, 5.0, 0.60   # a price alert: at least 10% and $5; over 60% is a price correction
QC_MIN_NEW = 3                          # new QC photos: the first set, or at least 3 more
RULE_WIDE = 300                         # a prices batch with more changes than this is a rule-wide re-price, not news
MAX_FAILS = 3                           # failed tries of one email to one member before it is given up
MAX_HTML = 90 * 1024                    # Gmail clips at about 102 KB and the cut hides the unsubscribe link
MIN_TEXT = 500                          # characters of real text in every email
STOP_COMPLAINT_RATE, STOP_NEW_COMPLAINTS, STOP_BOUNCE_RATE = 0.001, 3, 0.02

FB_REF, FB_INVITE, SITE_CODE = "fbpartner", "AADAXV", "AACPYA"

# template -> stream (email_sends.stream), sender group (provider and From address) and campaign (utm_campaign on our
# links; bump_product_view in the owner's SQL only accepts welcome, ordering, mycnbox, newsletter and saved)
TEMPLATES = {
    "w0":      {"stream": "onboarding", "group": "automated", "campaign": "welcome"},
    "w0-late": {"stream": "onboarding", "group": "automated", "campaign": "welcome"},
    "w1":      {"stream": "onboarding", "group": "automated", "campaign": "ordering"},
    "w2":      {"stream": "onboarding", "group": "automated", "campaign": "mycnbox"},
    "w3":      {"stream": "onboarding", "group": "automated", "campaign": "newsletter"},
    "picks":   {"stream": "newsletter", "group": "news",      "campaign": "newsletter"},
    "alert":   {"stream": "alerts",     "group": "automated", "campaign": "saved"},
    "wb1":     {"stream": "winback",    "group": "automated", "campaign": "newsletter"},
    "wb2":     {"stream": "winback",    "group": "automated", "campaign": "newsletter"},
}
W0S = ("w0", "w0-late")
ONBOARD_TEMPLATES = ("w1", "w2", "w3")
ONBOARD_LAST = len(ONBOARD_TEMPLATES)   # onboard_step at or past this: the series is done
# A/B tests: arm = hash(member, experiment), fixed per member, stored as email_sends.variant "<experiment>:<arm>"
EXPERIMENTS = {"w0-row": ("a", "b"),          # a: no products, b: ends with one row of 2 partner finds
               "picks-subject": ("a", "b")}   # a: "Picked for you this week", b: count and item type ("6 picks: tops and shoes")

# The sign-up link and bonus line of each agent, the same as WB_LINKS and AGENT_REG in index.html and the
# /guides/agent-coupons table: only what the site already says. If a line changes on the site, change it here too.
# (name, sign-up link, invite code or "", bonus line, terms line, guide page, its offer is coupons)
AGENTS = {
    "mycnbox":   ("MyCNBox", "", SITE_CODE, "A coupon pack worth up to $500, mostly shipping coupons with a minimum spend, one per parcel.", "", "/guides/mycnbox-coupon-code", True),
    "kakobuy":   ("KakoBuy", "https://ikako.vip/r/w5war", "w5war", "Up to $410 in welcome coupons.", "Split across several coupons with minimum spends, mostly for shipping.", "/guides/kakobuy-coupon-code", True),
    "oopbuy":    ("Oopbuy", "https://oopbuy.com/register?inviteCode=LHQC0OS8O", "", "New-user coupons on your first orders.", "", "/guides/agent-coupons", True),
    "litbuy":    ("Litbuy", "https://litbuy.com/register?inviteCode=N3GYNRNL7", "", "Up to $165 in shipping coupons.", "", "/guides/agent-coupons", True),
    "boonbuy":   ("Boonbuy", "https://boonbuy.com/register?inviteCode=NA6R4R4EC", "", "40% off shipping plus a coupon pack.", "", "/guides/agent-coupons", True),
    "hipobuy":   ("Hipobuy", "https://hipobuy.com/register?inviteCode=6DJ8GVKLE", "", "Up to $450 coupon bundle.", "", "/guides/agent-coupons", True),
    "joyagoo":   ("Joyagoo", "https://joyagoo.com/register?ref=301083138", "", "Up to ¥1,200 coupon pack.", "", "/guides/agent-coupons", True),
    "usfans":    ("USFans", "https://usfans.com/register?ref=VKZFJG", "", "", "", "/guides/agent-coupons", False),
    "gtbuy":     ("GTBuy", "https://gtbuy.com/register?inviteCode=KI06I91RM", "", "Up to $300 coupon bundle.", "", "/guides/agent-coupons", True),
    "lovegobuy": ("LoveGoBuy", "https://www.lovegobuy.com/?invite_code=9WJ54Y", "", "Welcome coupons for new members.", "", "/guides/agent-coupons", True),
    "itaobuy":   ("iTaoBuy", "https://www.itaobuy.com/register?inviteCode=6SMA234Z", "", "Up to 10% off your first order.", "", "/guides/agent-coupons", False),
    "cssbuy":    ("CSSBuy", "https://www.cssbuy.com/register?invite=R0dfOUY5QkM1RkU=", "", "A ¥25 new-user coupon.", "", "/guides/agent-coupons", True),
    "hubbuy":    ("Hubbuy", "https://www.hubbuy.com/signUp?utm_source=website&utm_medium=ambassador&utm_campaign=linksharing&inviteCode=082A1BdE", "", "Up to ¥300 in coupons.", "", "/guides/agent-coupons", True),
    "bbdbuy":    ("BBDBuy", "https://www.bbdbuyeu.com/register?inviteCode=uDi7jz", "", "", "", "/guides/agent-coupons", False),
    "sugargoo":  ("Sugargoo", "https://www.sugargoo.com/register?memberId=3751749728009774836", "", "New-member coupon pack.", "", "/guides/agent-coupons", True),
    "superbuy":  ("Superbuy", "https://www.superbuy.com/en/page/login?partnercode=Expx5X&type=register", "", "Up to ¥560 new-user gift.", "", "/guides/agent-coupons", False),
    "fishgoo":   ("Fishgoo", "https://www.fishgoo.com/#/login?memberId=3920775520241738078&ref=fishgoo", "", "Up to $500 in coupons.", "", "/guides/agent-coupons", True),
}
# The click tracker only redirects to these hosts (ALLOW in functions/e/[[path]].js); a link elsewhere would land on the
# homepage, so every destination is checked against the same list before an email goes out.
ALLOW = re.compile(r"^(www\.|fb\.)?puroclassico\.com$|^(m\.)?mycnbox\.com$|^ikako\.vip$|^(www\.)?(kakobuy|oopbuy|lovegobuy|sugargoo|litbuy|hipobuy|boonbuy|joyagoo|usfans|gtbuy|itaobuy|cssbuy|hubbuy|bbdbuy|bbdbuyeu|superbuy|fishgoo)\.com$", re.I)
# Logo watches, monogram bags and these brands go in emails since 26 Nov 2026 (owner). The final report rated them the
# biggest risk to the Plunk account (its terms ban mail that links to content infringing someone's IP, and one email in
# ten goes to an AI check), so EMAIL_LOGOS=0 (a GitHub Actions variable) leaves them out again with no code change.
EMAIL_LOGOS = env("EMAIL_LOGOS", "1") not in ("0", "false", "no")
LUXURY = {"rolex", "audemarspiguet", "ap", "patekphilippe", "omega", "cartier", "louisvuitton", "lv", "hermes", "chanel",
          "dior", "christiandior", "gucci", "goyard", "vancleef", "vancleefarpels"}
LUX_TITLE = re.compile(r"\bmonogram\b|\bwatch(es)?\b(?!\s*(hat|cap|beanie))", re.I)
# Copy rules (CLAUDE.md): "replica", "fake" and "1:1" never appear in an email, so a find whose title carries one is left out.
BANNED_TITLE = re.compile(r"\b(replicas?|fakes?|reps)\b|1:1", re.I)


class Fatal(Exception):
    """The run cannot go on safely (no addresses, no tables, a provider without its keys): ::error:: and exit 1."""


class Stop(Exception):
    """Stop sending for this run (spending cap, refused key, paused domain, 5 failures in a row)."""


class NoSQL(Exception):
    """The Email v2 tables or columns are not in Supabase yet (scripts/email_v2.sql, scripts/email_v2_engine.sql): nothing
    is sent, and the run ends green with a warning (the daily health check reports it), not red every 15 minutes."""


def missing_sql(e):
    """A Supabase answer that means the SQL was not run: an unknown table (PGRST205) or column (42703)."""
    return isinstance(e, SupaError) and e.status in (400, 404) and ("PGRST205" in e.text or "42703" in e.text)


STOP_MARK = "[stop] "   # email_sends.error of a send a Stop ended: not the member's failure, so it never counts toward MAX_FAILS


# ---------------------------------------------------------------- small helpers
def utcnow():
    t = env("MAILER_NOW")           # tests and previews: a fixed "now"
    return parse_ts(t) if t else datetime.now(timezone.utc)


def parse_ts(s):
    if not s: return None
    if isinstance(s, datetime): return s if s.tzinfo else s.replace(tzinfo=timezone.utc)
    s = str(s).strip().replace("Z", "+00:00").replace(" ", "T", 1)
    s = re.sub(r"\.(\d{6})\d+", r".\1", s)
    try: d = datetime.fromisoformat(s)
    except ValueError: return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def iso(d): return d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def day_at(d, hour=0): return d.astimezone(timezone.utc).replace(hour=hour, minute=0, second=0, microsecond=0)


def hide(msg):
    """The job log of this repository is public: an error text is printed without any email address in it."""
    return re.sub(r"[\w.+%-]+@[\w-]+(?:\.[\w-]+)+", "<address>", str(msg))[:300]


def esc(s): return str(s if s is not None else "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def say(*a): print(*a, flush=True)


def gh_output(name, value):
    """A step output for the workflow (the health check reads which step ran)."""
    p = env("GITHUB_OUTPUT")
    if p:
        with open(p, "a", encoding="utf-8") as f: f.write("%s=%s\n" % (name, re.sub(r"[\r\n]+", " ", str(value))[:300]))


def arm_of(member_id, exp):
    arms = EXPERIMENTS[exp]
    return arms[int(hashlib.sha256(("%s|%s" % (member_id, exp)).encode()).hexdigest(), 16) % len(arms)]


def token(uid): return hmac.new(env("UNSUB_SECRET").encode(), str(uid).encode(), hashlib.sha256).hexdigest()


def usd(v):
    try: return "$" + str(int(round(float(v or 0))))
    except (TypeError, ValueError): return ""


def http(url, method="GET", body=None, headers=None, timeout=40):
    """(status, headers, text). HTTP errors come back as a status; network errors raise."""
    data = body if body is None or isinstance(body, bytes) else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    try:
        r = urllib.request.urlopen(req, timeout=timeout)
        return r.status, r.headers, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.headers, (e.read() or b"").decode("utf-8", "replace")


def html_text(h, links=True):
    """The readable text of an email: for AhaSend's plain-text part (with link targets) and the 500-character rule."""
    h = re.sub(r"(?is)<(style|head|title)[^>]*>.*?</\1>", " ", h)
    h = re.sub(r'(?is)<div style="display:none;[^"]*">.*?</div>', " ", h)              # the hidden preheader
    h = re.sub(r"(?is)<!--.*?-->", " ", h)
    if links:
        h = re.sub(r'(?is)<a [^>]*?href="([^"]+)"[^>]*>(.*?)</a>',
                   lambda m: "%s (%s)" % (re.sub(r"<[^>]+>", "", m.group(2)).strip(), htmllib.unescape(m.group(1))) if re.sub(r"<[^>]+>", "", m.group(2)).strip() else "", h)
    h = re.sub(r"(?i)<br\s*/?>|</(p|div|h1|h2|tr|table)>", "\n", h)
    h = htmllib.unescape(re.sub(r"<[^>]+>", " ", h)).replace(" ", " ").replace("﻿", "").replace("͏", "")
    lines = [re.sub(r"[ \t\xa0]+", " ", ln).strip() for ln in h.split("\n")]
    return "\n".join(ln for ln in lines if ln)


def text_len(h): return len(re.sub(r"\s+", " ", html_text(h, links=False)))


# ---------------------------------------------------------------- Supabase
class SupaError(Exception):
    def __init__(self, status, text, path):
        super().__init__("%s %s: %s" % (status, path.split("?")[0], hide(text)[:200]))
        self.status, self.text = status, text or ""


def sb_headers(extra=None):
    h = {"apikey": SVC, "Authorization": "Bearer " + SVC, "Content-Type": "application/json", "Accept": "application/json"}
    if extra: h.update(extra)
    return h


def sb(path, method="GET", body=None, prefer=None, extra=None):
    h = sb_headers(extra)
    if prefer: h["Prefer"] = prefer
    for attempt in range(3):
        try:
            st, hd, t = http(SUPA_URL + "/rest/v1/" + path, method, body, h)
        except (urllib.error.URLError, OSError) as e:
            if attempt == 2 or method == "POST": raise SupaError(0, str(e), path)
            time.sleep(2 * (attempt + 1)); continue
        if st >= 500 and method != "POST" and attempt < 2:
            time.sleep(2 * (attempt + 1)); continue
        if st >= 400: raise SupaError(st, t, path)
        return json.loads(t) if t.strip() else []


def sb_all(path, page=1000):
    """Every row of a GET (Supabase returns at most 1,000 per request). The path carries an order=."""
    out, start = [], 0
    while True:
        rows = sb(path, extra={"Range-Unit": "items", "Range": "%d-%d" % (start, start + page - 1)})
        out += rows
        if len(rows) < page: return out
        start += page


def sb_count(path):
    """How many rows a filter matches (Content-Range), without reading them."""
    st, hd, t = http(SUPA_URL + "/rest/v1/" + path, headers=sb_headers({"Prefer": "count=exact", "Range-Unit": "items", "Range": "0-0"}))
    if st >= 400: raise SupaError(st, t, path)
    m = re.search(r"/(\d+)$", (hd.get("Content-Range") if hd else "") or "")
    return int(m.group(1)) if m else len(json.loads(t or "[]"))


def chunks(xs, n):
    xs = list(xs)
    for i in range(0, len(xs), n): yield xs[i:i + n]


def in_list(ids): return "(" + ",".join(str(i) for i in ids) + ")"


def auth_users():
    """Every Supabase Auth user (admin API), id -> user. The only source of addresses: profiles.email is written by the
    browser, so a member could put a stranger's address there. Pages are read until one comes back empty (the server
    may hand out fewer than per_page), or the X-Total-Count is reached."""
    out, page = {}, 1
    h = {"apikey": SVC, "Authorization": "Bearer " + SVC, "Accept": "application/json"}
    while True:
        url = "%s/auth/v1/admin/users?page=%d&per_page=1000" % (SUPA_URL, page)
        try:
            st, hd, t = http(url, headers=h)
            if st >= 500: time.sleep(3); st, hd, t = http(url, headers=h)
        except (urllib.error.URLError, OSError) as e:
            raise Fatal("the Supabase admin API (auth users) did not answer (%s): no member addresses, nothing sent" % hide(e))
        if st != 200:
            raise Fatal("the Supabase admin API (auth users) answered %d: no member addresses, nothing sent (profiles.email is never used)" % st)
        try:
            j = json.loads(t); users = j.get("users") if isinstance(j, dict) else j
        except ValueError: users = None
        if not isinstance(users, list): raise Fatal("the Supabase admin API (auth users) gave no user list: nothing sent")
        for u in users:
            if isinstance(u, dict) and u.get("id"): out[u["id"]] = u
        try: total = int((hd.get("X-Total-Count") if hd else None) or 0)
        except ValueError: total = 0
        if not users or (total and len(out) >= total): return out
        page += 1
        if page > 500: raise Fatal("auth users: more than 500 pages")


_STATE_WARNED = []


def state_get(key):
    try:
        rows = sb("email_state?key=eq.%s&select=value" % urllib.parse.quote(key))
        return rows[0]["value"] if rows else None
    except SupaError as e:
        if e.status in (400, 404):
            if not _STATE_WARNED: say("::warning::email_state is missing: run scripts/email_v2_engine.sql (alerts cannot see stock and QC changes)")
            _STATE_WARNED.append(1); return None
        raise


def state_put(key, value):
    try:
        sb("email_state?on_conflict=key", "POST", {"key": key, "value": value, "updated_at": iso(utcnow())},
           prefer="resolution=merge-duplicates,return=minimal")
    except SupaError as e:
        say("email_state %s not saved: %s" % (key, e))


# ---------------------------------------------------------------- providers
class Result:
    def __init__(self, ok, provider_id=None, error=None, contact=None, note=None):
        self.ok, self.provider_id, self.error, self.contact, self.note = ok, provider_id, error, contact, note


def retry_after(hd, default=2.0):
    try: return min(60.0, max(1.0, float((hd.get("Retry-After") if hd else None) or default)))
    except (TypeError, ValueError): return default


def plunk_error(code, text):
    try:
        e = json.loads(text)["error"]; f = (e.get("errors") or [{}])[0]
        return "%d %s: %s%s" % (code, e.get("code"), e.get("message"), " [%s: %s]" % (f.get("field"), f.get("message")) if f.get("field") else "")
    except Exception:
        return "%d %s" % (code, (text or "")[:160])


def plunk_send(to, subject, html, unsub, key, from_email, from_name):
    """One email through Plunk's POST /v1/send, as the old send that worked (to, subject, body, from {name, email},
    headers), plus `reply` (Reply-To, never a header) and an Idempotency-Key (the email_sends id: Plunk runs a key at most
    once in 24 hours). Our List-Unsubscribe pair replaces Plunk's. 429 with Retry-After: the rate limit (wait, same key);
    429 without it: the spending or free-plan cap (Stop). 401 and 403 stop the run: every other send would fail too."""
    body = {"to": to, "subject": subject, "body": html, "from": {"name": from_name, "email": from_email}}
    if REPLY_TO: body["reply"] = REPLY_TO
    if unsub: body["headers"] = {"List-Unsubscribe": "<%s>" % unsub, "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"}
    data = json.dumps(body).encode()
    h = {"Authorization": "Bearer " + PLUNK_KEY, "Content-Type": "application/json", "Accept": "application/json", "Idempotency-Key": str(key)}
    waits = errs = inflight = 0
    while True:
        try:
            st, hd, t = http(PLUNK_API + "/v1/send", "POST", data, h, timeout=30)
        except (urllib.error.URLError, OSError) as e:      # no answer: try again with the same key (never twice at Plunk)
            errs += 1
            if errs <= 2: time.sleep(2 ** errs); continue
            return Result(False, error="no answer from Plunk: %s" % e)
        if 200 <= st < 300:
            try: j = json.loads(t)
            except ValueError: j = {}
            try: e0 = (j.get("data") or {}).get("emails")[0]
            except Exception:
                # accepted, but not in the documented shape: counted as sent, so a later run never sends it again
                return Result(True, note="accepted, answer not understood") if j.get("success") is True else Result(False, error="unexpected answer: " + t[:160])
            if e0.get("status") == "throttled": return Result(False, error="throttled by Plunk")
            return Result(True, e0.get("email"), contact=(e0.get("contact") or {}).get("id"))
        if st == 429:
            if not (hd and hd.get("Retry-After")):
                raise Stop("Plunk refused the send with 429 and no Retry-After: the monthly spending or free-plan cap is reached (%s)" % plunk_error(st, t))
            waits += 1
            if waits > 6: return Result(False, error="rate limited 6 times in a row")
            time.sleep(retry_after(hd)); continue
        if st == 409:                                      # the key was used: an earlier try of this very email
            try: osc = (json.loads(t)["error"].get("details") or {}).get("originalStatusCode")
            except Exception: osc = -1
            if isinstance(osc, int) and 200 <= osc < 300: return Result(True, note="sent by an earlier try (idempotent replay)")
            if osc is None:
                inflight += 1
                if inflight <= 3: time.sleep(3); continue
                return Result(True, note="still in flight at Plunk, counted as sent so it is never sent twice")
            return Result(False, error="an earlier try of this email failed at Plunk (%s)" % osc)
        if st in (401, 403): raise Stop("Plunk refused the key or the sender (%s)" % plunk_error(st, t))
        if 400 <= st < 500 and re.search(r"verif", t, re.I) and re.search(r"domain|sender|from", t, re.I):
            raise Stop("Plunk refused the sender %s: is its domain verified in Plunk? (%s)" % (from_email.split("@")[-1], plunk_error(st, t)))
        if st >= 500:
            errs += 1
            if errs <= 2: time.sleep(2 ** errs); continue
        return Result(False, error=plunk_error(st, t))


def plunk_status(eid):
    """The email's status at Plunk (GET /emails/{id}): SENT, DELIVERED, FAILED ... or None."""
    try:
        st, _, t = http(PLUNK_API + "/emails/" + urllib.parse.quote(str(eid)), headers={"Authorization": "Bearer " + PLUNK_KEY, "Accept": "application/json"}, timeout=20)
        if st != 200: return None
        j = json.loads(t)
        return (j.get("status") or (j.get("data") or {}).get("status") or "").upper() or None
    except Exception:
        return None


def ahasend_send(to, subject, html, unsub, key, from_email, from_name):
    """One email through AhaSend's POST /v2/accounts/{account}/messages: our HTML and a text part made from it, our
    List-Unsubscribe pair, reply_to (never a header), tracking off for this email, Idempotency-Key (24 hours: a replay
    answers the stored result, an in-progress request 409 with Retry-After). Every message passes AhaSend's template
    engine, so brace pairs that read as template syntax are broken up first."""
    safe = lambda s: re.sub(r"\{([{%#])", r"{ \1", s)
    body = {"from": {"email": from_email, "name": from_name}, "recipients": [{"email": to}], "subject": safe(subject),
            "html_content": safe(html), "text_content": safe(html_text(html)), "tracking": {"open": False, "click": False}}
    if REPLY_TO: body["reply_to"] = {"email": REPLY_TO}
    if unsub: body["headers"] = {"List-Unsubscribe": "<%s>" % unsub, "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"}
    data = json.dumps(body).encode()
    url = "%s/v2/accounts/%s/messages" % (AHASEND_API, urllib.parse.quote(AHA_ACCOUNT))
    h = {"Authorization": "Bearer " + AHA_KEY, "Content-Type": "application/json", "Accept": "application/json", "Idempotency-Key": str(key)}
    waits = errs = 0
    while True:
        try:
            st, hd, t = http(url, "POST", data, h, timeout=30)
        except (urllib.error.URLError, OSError) as e:
            errs += 1
            if errs <= 2: time.sleep(2 ** errs); continue
            return Result(False, error="no answer from AhaSend: %s" % e)
        try: j = json.loads(t) if t.strip() else {}
        except ValueError: j = {}
        msg = j.get("message") if isinstance(j, dict) else None
        if 200 <= st < 300:
            try: m0 = (j.get("data") or [])[0]
            except Exception: return Result(True, note="accepted, answer not understood")
            if m0.get("status") == "error" or not m0.get("id"): return Result(False, error="AhaSend: %s" % (m0.get("error") or "not sent"))
            return Result(True, m0.get("id"))
        if st in (409, 429, 503) or (st >= 500 and errs < 2):
            waits += 1
            if waits > 6: return Result(False, error="AhaSend %d after 6 tries: %s" % (st, msg or t[:120]))
            if st >= 500 and st != 503: errs += 1
            time.sleep(retry_after(hd, 2 ** min(waits, 4))); continue
        if st in (401, 402, 403): raise Stop("AhaSend refused the key, the account or the domain (%d %s)" % (st, msg or t[:120]))
        return Result(False, error="AhaSend %d: %s" % (st, msg or t[:160]))


ADAPTERS = {"plunk": plunk_send, "ahasend": ahasend_send}


def providers():
    """group -> provider name, or None when that group cannot send (Plunk without a key). An unknown provider, or a
    group set to AhaSend without its keys, stops the run here: never a silent fallback."""
    out = {}
    for grp, var in (("automated", "PROVIDER_AUTOMATED"), ("news", "PROVIDER_NEWS")):
        p = env(var, "plunk").lower()
        if p not in ADAPTERS: raise Fatal("%s is %r: use plunk or ahasend" % (var, p))
        if p == "ahasend" and not (AHA_KEY and AHA_ACCOUNT): raise Fatal("%s is ahasend, but AHASEND_API_KEY or AHASEND_ACCOUNT_ID is not set" % var)
        out[grp] = p if (p == "ahasend" or PLUNK_KEY) else None
    return out


# ---------------------------------------------------------------- catalogue data
def local_text(rel):
    try:
        with open(os.path.join(ROOT, rel), encoding="utf-8") as f: return f.read()
    except OSError:
        return None


def site_json(rel, default=None):
    """A data file the site serves (products.json, data/*.json), read over HTTP like the old engine, or from this
    checkout when the site does not answer."""
    try:
        st, _, t = http(SITE + "/" + rel, headers={"User-Agent": UA, "Accept": "application/json"}, timeout=60)
        if st == 200: return json.loads(t)
        say("%s answered %d, reading the checkout's copy" % (rel, st))
    except Exception as e:
        say("%s not readable over HTTP (%s), reading the checkout's copy" % (rel, hide(e)[:80]))
    t = local_text(rel)
    try: return json.loads(t) if t else default
    except ValueError: return default


def old_money():
    t = local_text("functions/_lib/content.js") or ""
    m = re.search(r"export const OLD_MONEY = \{\s*brands:\s*(\[[^\]]*\])", t)
    try: return json.loads(m.group(1)) if m else []
    except ValueError: return []


# Your style (the welcome tour's "What's your style?", profiles.style): PC_STY_DEF and pcStyleMatch in index.html, same
# brands and words. 2 a core match, 1 a softer one, 0 none.
_OLD = ["Ralph Lauren", "Loro Piana", "Lacoste", "Burberry", "Moncler", "Hermes", "Maison Margiela", "Celine", "Loewe",
        "Brunello Cucinelli", "Golden Goose", "Zegna", "Max Mara", "Tom Ford", "Barbour", "Bottega Veneta", "Saint Laurent", "Ami",
        "Acne Studios", "Prada", "Miu Miu", "The Row", "Kiton", "Cartier", "Rolex", "Polo Ralph Lauren", "Sandro", "Arc'teryx Veilance"]
STYLES = {
    "old": {"name": "Old money", "brands": None,
            "soft": re.compile(r"\b(cable.?knit|cashmere|merino|quarter.?zip|oxford shirt|loafers?|penny|boat shoes?|knit polo|polo shirt|cardigan|chinos?|quilted|harrington|tweed|linen shirt|gilet)\b", re.I)},
    "archive": {"name": "Archive", "brands": ["Rick Owens", "Maison Margiela", "MM6 Maison Margiela", "Raf Simons", "Comme des Garcons", "Yohji Yamamoto", "Y-3", "Helmut Lang", "Undercover", "Number Nine", "Number (N)ine",
        "Vivienne Westwood", "Chrome Hearts", "Enfants Riches Deprimes", "ERD", "Alyx", "1017 Alyx 9SM", "Kapital", "Visvim", "Needles", "Mastermind", "Jil Sander", "Maison Mihara Yasuhiro", "Vetements", "Mowalola",
        "Jean Paul Gaultier", "Issey Miyake", "Dries Van Noten", "Ann Demeulemeester", "Boris Bidjan Saberi", "Julius", "Saint Michael", "Hysteric Glamour", "Martine Rose", "Our Legacy", "Guidi", "Kiko Kostadinov", "Craig Green"],
        "soft": re.compile(r"\b(archive|ramones?|geobasket|tabi|drkshdw|kiss boots?)\b", re.I)},
    "street": {"name": "Streetwear", "brands": ["Supreme", "Balenciaga", "Corteiz", "Stussy", "Hellstar", "Essentials", "Fear of God", "Fear of God Essentials", "Bape", "A Bathing Ape", "Palace", "Trapstar", "Represent", "Nike", "Jordan", "Air Jordan",
        "Denim Tears", "Broken Planet", "Sp5der", "Syna World", "Gallery Dept", "Off-White", "Palm Angels", "Rhude", "Kith", "Aime Leon Dore", "Cole Buxton", "Travis Scott", "Cactus Jack", "Vlone", "Eric Emanuel", "Yeezy",
        "Carhartt", "Purple Brand", "Amiri", "Human Made", "Anti Social Social Club", "Drew House", "Nocta", "Carsicko", "Sicko", "Godspeed", "Who Decides War", "Cactus Plant Flea Market", "Protect London", "No Faith Studios",
        "Dime", "Golf Wang", "Kaws", "Evisu", "Racer Worldwide", "Fyredwrld", "Akimbo", "Revenge", "Vicinity", "6PM", "Derschutze", "Mertra", "Minus Two"],
        "soft": re.compile(r"\b(dunks?|air force|af1|air max|jordan|yeezy|tech fleece|box logo|graphic tee|nuptse)\b", re.I)},
    "women": {"name": "Women", "brands": ["Skims", "Alo Yoga", "Brandy Melville", "Juicy Couture", "Polene", "Chloe", "Isabel Marant", "Jimmy Choo", "I AM GIA", "Alice Hollywood", "Van Cleef & Arpels", "Tiffany", "Jaded London", "Rhode", "Miu Miu"],
              "word": re.compile(r"\b(women'?s?|womens|wmns|ladies|dress|skirt|bikini|heels|stiletto|bra|leggings|crop top|handbag|blouse|corset)\b", re.I)},
}
_STY_BRAND = None


def sty_norm(s):
    s = unicodedata.normalize("NFD", str(s or ""))
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", "", s)


def style_match(p, k):
    global _STY_BRAND
    if _STY_BRAND is None:
        STYLES["old"]["brands"] = (old_money() or _OLD) + ["Hermès", "Polo Ralph Lauren", "Brunello Cucinelli", "Loro Piana"]
        _STY_BRAND = {}
        for key, d in STYLES.items():
            for b in d["brands"]:
                n = sty_norm(b)
                if n: _STY_BRAND.setdefault(n, set()).add(key)
    d = STYLES[k]; bs = _STY_BRAND.get(sty_norm(p.get("brand"))); own = bool(bs and k in bs); title = p.get("title") or ""
    if k == "women":
        if p.get("g") == "w" or own or d["word"].search(title): return 2
        if p.get("cat") == "Bags" and not re.search(r"backpack|duffle|duffel|messenger|waist ?bag|belt ?bag|sling|luggage|suitcase|trolley", title, re.I): return 1
        if p.get("cat") == "Accessories" and re.search(r"\b(necklace|bracelet|earrings?|rings?|pendant|scarf|sunglass(es)?|hair|jewel(le)?ry|charm|brooch|anklet)\b", title, re.I): return 1
        return 0
    if own: return 2
    if p.get("cat") != "Toys" and d["soft"].search(title) and not bs: return 1
    return 0


def kept_out(p):
    """Never in an email: a find whose title has a word the copy rules ban. With EMAIL_LOGOS=0 also a luxury logo item
    (the brands in LUXURY, collaborations included, watches, monogram pieces)."""
    t = p.get("title") or ""
    if BANNED_TITLE.search(t): return True
    if EMAIL_LOGOS: return False
    parts = re.split(r"\s+(?:x|&|and)\s+|\s*[/,+]\s*", str(p.get("brand") or ""), flags=re.I)
    return any(sty_norm(b) in LUXURY for b in parts + [p.get("brand") or ""]) or bool(LUX_TITLE.search(t))


class Catalog:
    """The finds members can see, with the partner swaps applied (the swapped finds are the partner's: "_rec"), plus
    popularity, QC photo counts, sizes and the day each find first appeared. kept_out() finds are left out."""

    def __init__(self):
        prod = site_json("products.json", {}) or {}
        sw = site_json("data/link_swaps.json", {}) or {}
        self.swaps = sw.get("swaps") or {}
        price = sw.get("price") or {}
        rep = site_json("data/reported.json", {}) or {}
        hidden = set(map(str, rep.get("hidden") or [])) | set(map(str, sw.get("hide") or [])) | set(map(str, sw.get("hide_of") or {}))
        lh = site_json("data/link_health.json", {}) or {}
        self.health = lh
        self.dead = set(map(str, lh.get("dead") or []))
        self.sold_out = set(map(str, lh.get("sold_out") or []))
        for pid, s in self.swaps.items():
            p = prod.get(pid)
            if not p: continue
            p["_rec"] = True; p["_plat0"] = p.get("platform"); p["platform"] = s[0]
            pr = price.get(pid)
            if isinstance(pr, list) and len(pr) == 3 and str(pr[0]) == str(s[1]) and (pr[1] or 0) > 0:
                p["price"] = pr[1]
                if (pr[2] or 0) > 0: p["usd"] = pr[2]
        self.p = {str(k): v for k, v in prod.items() if str(k) not in hidden and str(k) not in self.dead and not kept_out(v)}
        self.stats = (site_json("data/stats.json", {}) or {}).get("p") or {}
        self.bank = site_json("data/qc_bank.json", {}) or {}
        self.qc_n = self._qc_counts()
        self.sizes = (site_json("data/sizes.json", {}) or {}).get("items") or {}
        self.first_day = self._rowdays()
        self.plus = self._plus()
        self.partners = sorted((i for i, p in self.p.items() if p.get("_rec") and p.get("img") and i not in self.sold_out),
                               key=lambda i: -self.pop(i))
        say("catalogue: %d finds for emails, %d partner finds, %d with QC photos" % (len(self.p), len(self.partners), len(self.qc_n)))

    def _qc_counts(self):
        """QC photos per find: the catalogue's own count (functions/_lib/catalog.js) or the QC bank's, the higher one,
        the way scripts/apply_qc_counts.py raises them (a swapped find shows the partner item's QC photos)."""
        items = self.bank.get("items") or {}
        cat = {}
        t = local_text("functions/_lib/catalog.js")
        m = re.search(r"export const ROWS = (\[.*\]);", t or "")
        if m:
            try: cat = {str(r[0]): int(r[8] or 0) for r in json.loads(m.group(1))}
            except Exception: cat = {}
        out = {}
        for pid, p in self.p.items():
            n = cat.get(pid, 0)
            b = None; s = self.swaps.get(pid)
            if s: b = items.get("%s/%s" % (s[0], str(s[1]).lstrip("0")))
            if not (b and b[1]): b = items.get("%s/%s" % (p.get("_plat0") or p.get("platform"), str(p.get("itemId") or pid).lstrip("0")))
            if b and b[1]: n = max(n, int(b[0] or 0), int(b[1]))
            if n > 0: out[pid] = n
        return out

    def _rowdays(self):
        t = local_text("functions/_lib/rowdays.js") or ""
        try:
            days = json.loads(re.search(r"export const DAYS = (\[[^\]]*\]);", t).group(1))
            codes = json.loads(re.search(r"export const ROWDAY = (\{.*\});", t).group(1))
        except Exception:
            return {}
        out = {}
        for pid, c in codes.items():
            w = len(c) // 2
            try: i = int(c[:w], 36)
            except ValueError: continue
            if 0 < i < len(days): out[str(pid)] = parse_ts(days[i])   # day 0 is the start of the history: older finds
        return out

    def _plus(self):
        t = local_text("functions/_lib/counts.js") or ""
        f = re.search(r'FINDS_PLUS = "([^"]+)"', t); q = re.search(r'QC_PLUS = "([^"]+)"', t)
        fl = lambda n: "{:,}+".format(n // 100 * 100)
        return {"finds": f.group(1) if f else fl(len(self.p)), "qc": q.group(1) if q else fl(len(self.qc_n))}

    def pop(self, pid):
        v = list(self.stats.get(pid) or []) + [0, 0, 0, 0]
        return 10 * v[3] + 2 * v[2] + v[1] + 0.05 * v[0]

    def qc(self, pid): return self.qc_n.get(pid, 0)

    def available(self, pid): return pid in self.p and pid not in self.sold_out

    def partner(self, pid): return bool((self.p.get(pid) or {}).get("_rec"))

    def model(self, pid):
        s = self.swaps.get(pid)
        return "%s/%s" % (s[0], s[1]) if s else pid

    def new_since(self, when):
        """Finds members can see that first appeared after this day (functions/_lib/rowdays.js)."""
        if not self.first_day or not when: return 0
        d = day_at(when)
        return sum(1 for pid in self.p if pid in self.first_day and self.first_day[pid] > d)

    def fresh_partners(self, when):
        """Partner finds that first appeared after this day, most popular first (None when there are none)."""
        d = day_at(when)
        return [i for i in self.partners if i in self.first_day and self.first_day[i] > d] or None


# ---------------------------------------------------------------- members
PROFILE_COLS = ("id,created_at,welcomed,welcomed_at,marketing_opt_in,agent,referred_by,style,size,ordering_sent,agent_sent,"
                "email_freq,email_paused_until,onboard_step,onboard_at,email_sunset_at,email_alert_at,email_click_at,"
                "email_track,email_personal")


class Member:
    def __init__(self, p, u):
        self.id = p["id"]; self.p = p
        self.email = (u.get("email") or "").strip()
        self.email_l = self.email.lower()
        prov = ((u.get("app_metadata") or {}).get("provider") or "").lower()
        provs = [str(x).lower() for x in ((u.get("app_metadata") or {}).get("providers") or [])]
        self.confirmed = bool(u.get("email_confirmed_at")) or prov == "google" or "google" in provs
        banned = parse_ts(u.get("banned_until"))
        self.blocked = bool(u.get("deleted_at")) or bool(u.get("is_anonymous")) or bool(banned and banned > utcnow())
        self.last_sign_in = parse_ts(u.get("last_sign_in_at"))
        self.created = parse_ts(p.get("created_at")) or parse_ts(u.get("created_at"))
        self.fb = (p.get("referred_by") or "") == FB_REF
        self.opt_in = p.get("marketing_opt_in") is True
        self.freq = (p.get("email_freq") or "weekly").strip().lower()
        self.paused_until = parse_ts(p.get("email_paused_until"))
        self.sunset_at = parse_ts(p.get("email_sunset_at"))
        self.welcomed = p.get("welcomed") is True
        self.welcomed_at = parse_ts(p.get("welcomed_at"))
        self.onboard_at = parse_ts(p.get("onboard_at"))
        self.alert_at = parse_ts(p.get("email_alert_at"))
        self.click_at = parse_ts(p.get("email_click_at"))
        self.track = p.get("email_track") is True          # yes to "Measure my email clicks"
        self.personal = p.get("email_personal") is True    # yes to "Personalise my emails from finds I view"
        a = str(p.get("agent") or "").strip().lower()
        self.agent = a if a in AGENTS else None
        st = str(p.get("style") or "").strip().lower()
        self.styles = [] if st in ("", "all") else [k for k in st.split(",") if k in STYLES]
        sz = p.get("size")
        if isinstance(sz, str):
            try: sz = json.loads(sz)
            except ValueError: sz = None
        self.size = sz if isinstance(sz, dict) else {}
        step = int(p.get("onboard_step") or 0)
        if step < 1 and p.get("ordering_sent"): step = 1       # the old engine's ordering guide covered W1
        if step < 2 and p.get("agent_sent"): step = 2          # and its MyCNBox nudge W2
        self.step = step
        self.last_view = None; self.seen = set(); self.viewed = {}; self.saves = {}; self.brands = {}; self.cats = {}; self.emailed = set()
        self._taste = None

    def last_active(self):
        """The day of the last visit (a product view) or sign-in: used to stop and restart email, allowed without a
        separate yes (tracking_law: close to CNIL's deliverability exemption)."""
        return max([d for d in (self.created, self.last_sign_in, self.last_view, self.click_at) if d] or [datetime(2000, 1, 1, tzinfo=timezone.utc)])

    def engaged(self, now):
        return any(d and d >= now - ENGAGED for d in (self.last_view, self.last_sign_in, self.click_at))

    def sunset(self):
        return bool(self.sunset_at) and self.last_active() <= self.sunset_at

    def mail_ok(self, suppressed):
        return bool(self.email) and "@" in self.email and self.confirmed and not self.blocked and self.email_l not in suppressed

    def may_market(self, now, stream):
        if not self.opt_in or self.freq == "paused": return False
        if self.freq == "alerts" and stream != "alerts": return False
        if self.paused_until and self.paused_until > now: return False
        if now - self.last_active() >= timedelta(days=SUNSET_DAYS): return False   # sunset, flagged or not yet
        return not self.sunset()

    def onboarding_done(self, now):
        """W3 sent, or the welcome series is long over (members from before it: their sign-up date counts)."""
        start = self.welcomed_at or self.created
        return self.step >= 3 or bool(start and start < now - ONBOARD_WINDOW)


def load_members():
    try:
        profiles = sb_all("profiles?select=%s&order=id" % PROFILE_COLS)
    except SupaError as e:
        if e.status == 400: raise NoSQL("profiles is missing the Email v2 columns (%s): run scripts/email_v2.sql in Supabase" % hide(e.text)[:120])
        raise Fatal("profiles not readable: %s" % e)
    users = auth_users()
    out = [Member(p, users[p["id"]]) for p in profiles if p.get("id") in users]
    say("members: %d profiles, %d auth users, %d with a confirmed address" % (len(profiles), len(users), sum(1 for m in out if m.confirmed and m.email)))
    return out


def load_activity(members, now):
    """Product views (120 days) and saved finds, per member. The last visit counts for everyone (when to stop email);
    which finds were viewed counts only for members who said yes to personalisation (taste_weight, pick_finds)."""
    by = {m.id: m for m in members}
    views = sb_all("product_views?select=user_id,product_id,brand,cat,viewed_at&user_id=not.is.null&viewed_at=gte.%s&order=viewed_at.desc" % iso(now - timedelta(days=SUNSET_DAYS)))
    taste_from = now - timedelta(days=60)
    for v in views:
        m = by.get(v.get("user_id"))
        if not m: continue
        t = parse_ts(v.get("viewed_at")); pid = str(v.get("product_id"))
        if t and (m.last_view is None or t > m.last_view): m.last_view = t
        if t and (pid not in m.viewed or t > m.viewed[pid]): m.viewed[pid] = t
        m.seen.add(pid)
        if t and t >= taste_from:
            if v.get("brand"): m.brands[v["brand"]] = m.brands.get(v["brand"], 0) + 1
            if v.get("cat"): m.cats[v["cat"]] = m.cats.get(v["cat"], 0) + 1
    try: favs = sb_all("favorites?select=user_id,product_id,created_at&order=user_id,product_id")
    except SupaError: favs = sb_all("favorites?select=user_id,product_id&order=user_id,product_id")
    for f in favs:
        m = by.get(f.get("user_id"))
        if m: m.saves[str(f.get("product_id"))] = parse_ts(f.get("created_at"))
    say("activity: %d product views (%d days), %d saved finds" % (len(views), SUNSET_DAYS, len(favs)))


def load_emailed(members, now):
    """Finds each member got in an email in the last 60 days (email_sends.meta.items): weekly picks never repeat them."""
    by = {m.id: m for m in members}
    rows = sb_all("email_sends?select=member_id,meta&status=neq.failed&created_at=gte.%s&meta=not.is.null&order=created_at" % iso(now - timedelta(days=60)))
    for r in rows:
        m = by.get(r.get("member_id"))
        if m and isinstance(r.get("meta"), dict): m.emailed.update(map(str, r["meta"].get("items") or []))


# ---------------------------------------------------------------- picking finds
_STY_CACHE, _SIZE_CACHE = {}, {}


def member_taste(cat, m):
    """Brands and categories from saves (a save counts 3) and, only with the member's yes to personalisation, from the
    finds they viewed in the last 60 days. Once per member."""
    if m._taste is None:
        b, c = (dict(m.brands), dict(m.cats)) if m.personal else ({}, {})
        for s in m.saves:
            p = cat.p.get(s) or {}
            if p.get("brand"): b[p["brand"]] = b.get(p["brand"], 0) + 3
            if p.get("cat"): c[p["cat"]] = c.get(p["cat"], 0) + 3
        m._taste = (b, c, float(max(list(b.values()) + [1])), float(max(list(c.values()) + [1])))
    return m._taste


def sizes_of(cat, pid):
    if pid not in _SIZE_CACHE:
        have = set()
        for s in (cat.sizes.get(pid) or {}).get("s") or []:
            for part in re.split(r"[/\s-]+", str(s).upper()): have.add(part)
        _SIZE_CACHE[pid] = have
    return _SIZE_CACHE[pid]


def taste_weight(cat, m, pid):
    """How well a find fits this member: brands and categories (member_taste), their style (profiles.style) and their
    usual size (profiles.size, when the listing shows its sizes)."""
    p = cat.p[pid]
    b, c, bt, ct = member_taste(cat, m)
    w = 1.0 + 3.0 * b.get(p.get("brand"), 0) / bt + 1.0 * c.get(p.get("cat"), 0) / ct
    if m.styles:
        s = 0
        for k in m.styles:
            if (pid, k) not in _STY_CACHE: _STY_CACHE[(pid, k)] = style_match(p, k)
            s = max(s, _STY_CACHE[(pid, k)])
        w *= 2.0 if s == 2 else 1.3 if s == 1 else 0.6
    mine = str((m.size.get("eu") if p.get("cat") == "Shoes" else m.size.get("l")) or "").strip().upper() if m.size else ""
    if mine:
        have = sizes_of(cat, pid)
        if have: w *= 1.15 if mine in have else 0.4
    return w


def pick_finds(cat, m, n, rnd, exclude=(), pool=None, per_brand=2, qc_first=True):
    """n finds for this member: their taste times popularity, finds with QC photos first, at most per_brand per brand
    and one per model, never one they saved or got by email lately (nor viewed, with their yes to personalisation),
    never a dead, sold-out or kept_out() find."""
    pool = cat.partners if pool is None else pool
    top = max([cat.pop(i) for i in pool[:1]] + [1.0]) or 1.0
    skip = set(exclude) | set(m.saves) | m.emailed | (m.seen if m.personal else set())
    scored = []
    for i in pool:
        if i in skip or not cat.available(i): continue
        w = (cat.pop(i) / top + 0.02) * taste_weight(cat, m, i) * (0.7 + 0.6 * rnd.random())
        scored.append(((1 if (qc_first and cat.qc(i)) else 0), w, i))
    scored.sort(key=lambda x: (-x[0], -x[1]))
    out, brands, models = [], {}, set()
    for _, _, i in scored:
        b = cat.p[i].get("brand") or ""
        if brands.get(b, 0) >= per_brand or cat.model(i) in models: continue
        brands[b] = brands.get(b, 0) + 1; models.add(cat.model(i)); out.append(i)
        if len(out) >= n: break
    return out


def similar(cat, m, pids, n):
    """Up to n partner finds like these saved ones (same brand first, then category), popular first."""
    brands = {(cat.p.get(i) or {}).get("brand") for i in pids}; cats = {(cat.p.get(i) or {}).get("cat") for i in pids}
    pool = [i for i in cat.partners if (cat.p[i].get("brand") in brands or cat.p[i].get("cat") in cats)]
    pool.sort(key=lambda i: (cat.p[i].get("brand") not in brands, -cat.pop(i)))
    return pick_finds(cat, m, n, random.Random(m.id + "alert"), exclude=pids, pool=pool, qc_first=False)


# ---------------------------------------------------------------- email look (newsletter.py primitives, v9 site look)
# Tokens mirror ds.css v9: white page, #F5F5F5 wells, ink #0A0A0A, primary #171717 on #FAFAFA, muted #6B6B6B, hairlines
# #E5E5E5, 12px cards, round pills, Inter. Every critical style is inline (Gmail can drop <style>); the <style> blocks only
# add dark mode, the phone layout (520 px) and Outlook.com dark ([data-ogsc]).
FONT = "Inter,-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif"
MONO = "'SFMono-Regular',Menlo,Consolas,'Liberation Mono',monospace"
INK, MUT, LINE, WELL, PRI, PRI_FG = "#0A0A0A", "#6B6B6B", "#E5E5E5", "#F5F5F5", "#171717", "#FAFAFA"
LOGO_MYCNBOX = SUPA_URL + "/storage/v1/object/public/products/email/mycnbox.png"
SPACE = '<div style="height:%dpx;line-height:%dpx;font-size:%dpx;">&nbsp;</div>'


def sp(px): return SPACE % (px, px, px)


def h1(text):
    return ('<h1 class="pc-ink pc-h1" style="margin:0 0 12px;font-family:%s;font-size:30px;line-height:1.15;font-weight:700;'
            'letter-spacing:-0.025em;color:%s;text-align:center;">%s</h1>') % (FONT, INK, text)


def h2(text, align="center"):
    return ('<h2 class="pc-ink" style="margin:0 0 8px;font-family:%s;font-size:20px;line-height:1.25;font-weight:700;'
            'letter-spacing:-0.02em;color:%s;text-align:%s;">%s</h2>') % (FONT, INK, align, text)


def lead(text, size=16, mb=24):
    return ('<p class="pc-mut" style="margin:0 auto %dpx;max-width:440px;font-family:%s;font-size:%dpx;line-height:1.55;'
            'color:%s;text-align:center;">%s</p>') % (mb, FONT, size, MUT, text)


def small(text, mt=16, align="center"):
    return ('<p class="pc-mut" style="margin:%dpx auto 0;max-width:440px;font-family:%s;font-size:13px;line-height:1.6;color:%s;'
            'text-align:%s;">%s</p>') % (mt, FONT, MUT, align, text)


def tlink(href, label, nowrap=False):
    return '<a href="%s" class="pc-ink" style="color:%s;text-decoration:underline;%s">%s</a>' % (esc(href), INK, "white-space:nowrap;" if nowrap else "", label)


def hr(m="32px 0"):
    return ('<table role="presentation" width="100%%" cellpadding="0" cellspacing="0" style="margin:%s;"><tr>'
            '<td class="pc-line" height="1" style="height:1px;line-height:1px;font-size:1px;background:%s;">&nbsp;</td></tr></table>') % (m, LINE)


def btn(href, label, kind="primary", rel=""):
    """Bulletproof pill: a table cell carries the colour, the padded <a> is the hit area. kind: primary | outline."""
    r = (' rel="%s"' % rel) if rel else ""
    href = esc(href)
    if kind == "outline":
        td = ('<td class="pc-out" align="center" bgcolor="#FFFFFF" style="border:1px solid %s;border-radius:999px;background:#FFFFFF;mso-padding-alt:13px 26px;">' % LINE)
        a = ('<a class="pc-ink" href="%s"%s style="display:inline-block;padding:13px 26px;font-family:%s;font-size:15px;line-height:18px;'
             'font-weight:600;color:%s;text-decoration:none;border-radius:999px;mso-padding-alt:0;">%s</a>') % (href, r, FONT, INK, label)
    else:
        td = ('<td class="pc-btn" align="center" bgcolor="%s" style="border:1px solid #5C5C5C;border-radius:999px;background:%s;mso-padding-alt:14px 30px;">' % (PRI, PRI))
        a = ('<a class="pc-btn-a" href="%s"%s style="display:inline-block;padding:14px 30px;font-family:%s;font-size:15px;line-height:18px;'
             'font-weight:600;color:%s;text-decoration:none;border-radius:999px;mso-padding-alt:0;">%s</a>') % (href, r, FONT, PRI_FG, label)
    return '<table role="presentation" align="center" cellpadding="0" cellspacing="0" style="margin:0 auto;"><tr>%s%s</td></tr></table>' % (td, a)


def well(inner, pad="28px 22px 30px"):
    return ('<table role="presentation" width="100%%" cellpadding="0" cellspacing="0"><tr>'
            '<td class="pc-well" align="center" bgcolor="%s" style="padding:%s;background:%s;border-radius:12px;text-align:center;">%s</td></tr></table>') % (WELL, pad, WELL, inner)


def code_box(code):
    """The invite code as large text (copyable with a long press, never an image)."""
    return ('<div class="pc-mut" style="margin:0 0 8px;font-family:%s;font-size:12px;line-height:16px;font-weight:600;letter-spacing:0.08em;color:%s;">INVITE CODE</div>'
            '<table role="presentation" align="center" cellpadding="0" cellspacing="0" style="margin:0 auto;"><tr>'
            '<td class="pc-out" align="center" bgcolor="#FFFFFF" style="padding:12px 24px;border:1px dashed #BDBDBD;border-radius:12px;background:#FFFFFF;">'
            '<span class="pc-ink" style="font-family:%s;font-size:30px;line-height:36px;font-weight:700;letter-spacing:4px;color:%s;-webkit-user-select:all;user-select:all;">%s</span>'
            '</td></tr></table>') % (FONT, MUT, MONO, INK, esc(code))


def logo(src, alt, px=48):
    return ('<img src="%s" alt="%s" width="%d" height="%d" style="display:inline-block;width:%dpx;height:%dpx;border:0;border-radius:12px;">'
            % (esc(src), esc(alt), px, px, px, px)) if src else ""


def step_rows(steps):
    """Numbered rows (round number, title, one line); the text is escaped here."""
    rows = ""
    for n, (t, b) in enumerate(steps, 1):
        rows += ('<tr><td valign="top" style="padding:0 14px 20px 0;vertical-align:top;width:28px;">'
                 '<table role="presentation" cellpadding="0" cellspacing="0"><tr><td class="pc-btn" align="center" valign="middle" bgcolor="#171717" width="28" height="28" '
                 'style="width:28px;height:28px;border-radius:999px;background:#171717;font-family:%s;font-size:13px;line-height:28px;font-weight:700;">'
                 '<span class="pc-btn-a" style="color:#FAFAFA;">%d</span></td></tr></table></td>'
                 '<td valign="top" style="padding:0 0 20px;vertical-align:top;">'
                 '<div class="pc-ink" style="margin:4px 0 4px;font-family:%s;font-size:15px;line-height:20px;font-weight:600;color:#0A0A0A;">%s</div>'
                 '<div class="pc-mut" style="font-family:%s;font-size:14px;line-height:21px;color:#6B6B6B;">%s</div></td></tr>') % (FONT, n, FONT, esc(t), FONT, esc(b))
    return '<table role="presentation" width="100%" cellpadding="0" cellspacing="0">' + rows + '</table>'


_EMAIL_IMG = {}


def email_img(pid, src, upload):
    """A square JPEG of the find on a light grey background (the catalogue's WebP cut-outs turn black and jagged in some
    clients, and Gmail ignores object-fit). Made once per find and kept in Supabase storage (email/p/<id>.jpg). Without
    upload (preview) an existing picture is used, or the catalogue's own."""
    if pid in _EMAIL_IMG: return _EMAIL_IMG[pid]
    path = "email/p/%s.jpg" % re.sub(r"[^A-Za-z0-9_-]", "", str(pid))
    public = SUPA_URL + "/storage/v1/object/public/products/" + path
    out = src
    try:
        st, _, _ = http(public, "HEAD", headers={"User-Agent": UA}, timeout=15)
        if st == 200: out = public
        elif upload and SVC and src:
            from PIL import Image
            req = urllib.request.Request(src, headers={"User-Agent": "Mozilla/5.0 PuroClassicoMail/2.0"})
            raw = urllib.request.urlopen(req, timeout=30).read()
            im = Image.open(io.BytesIO(raw)); im.load(); im = im.convert("RGBA")
            box = im.getbbox()
            if box: im = im.crop(box)
            side = int(max(im.size) * 1.12)
            canvas = Image.new("RGB", (side, side), (247, 247, 248))
            canvas.paste(im, ((side - im.width) // 2, (side - im.height) // 2), im)
            canvas = canvas.resize((480, 480), Image.LANCZOS)
            buf = io.BytesIO(); canvas.save(buf, "JPEG", quality=88, optimize=True, progressive=True)
            st, _, t = http(SUPA_URL + "/storage/v1/object/products/" + path, "POST", buf.getvalue(),
                            {"apikey": SVC, "Authorization": "Bearer " + SVC, "Content-Type": "image/jpeg", "x-upsert": "true", "Cache-Control": "max-age=31536000"}, timeout=30)
            if st < 300: out = public
    except Exception as e:
        say("email picture for %s not made: %s" % (pid, hide(e)[:100]))
    _EMAIL_IMG[pid] = out
    return out


_AGENT_LOGO = {}


def agent_logo(key, upload):
    """A PNG of the agent's logo for emails (email/agent-<key>.png, made once from the site's /img/agents WebP). MyCNBox
    has its own. Without upload the site's WebP is used."""
    if key == "mycnbox": return LOGO_MYCNBOX
    if key in _AGENT_LOGO: return _AGENT_LOGO[key]
    path = "email/agent-%s.png" % key
    public = SUPA_URL + "/storage/v1/object/public/products/" + path
    webp = SITE + "/img/agents/%s.webp" % key
    out = webp
    try:
        st, _, _ = http(public, "HEAD", headers={"User-Agent": UA}, timeout=15)
        if st == 200: out = public
        elif upload and SVC:
            from PIL import Image
            raw = urllib.request.urlopen(urllib.request.Request(webp, headers={"User-Agent": "Mozilla/5.0 PuroClassicoMail/2.0"}), timeout=30).read()
            im = Image.open(io.BytesIO(raw)); im.load(); im = im.convert("RGBA").resize((96, 96), Image.LANCZOS)
            buf = io.BytesIO(); im.save(buf, "PNG", optimize=True)
            st, _, _ = http(SUPA_URL + "/storage/v1/object/products/" + path, "POST", buf.getvalue(),
                            {"apikey": SVC, "Authorization": "Bearer " + SVC, "Content-Type": "image/png", "x-upsert": "true", "Cache-Control": "max-age=31536000"}, timeout=30)
            if st < 300: out = public
    except Exception as e:
        say("agent logo %s not made: %s" % (key, hide(e)[:100]))
    _AGENT_LOGO[key] = out
    return out


class Ctx:
    """One email being written. Every link goes through the click tracker with this email's id (the batch id, or the
    send's own id for a member who said yes to measuring clicks), campaign and a stable link key. Members of the
    partner's site (fb.*) get his invite code and fb.* links, as fb_swap() did in newsletter.py."""

    def __init__(self, template, uid, link_id, fb=False, upload=True):
        self.t, self.uid, self.fb, self.upload = template, str(uid), fb, upload
        self.campaign = TEMPLATES[template]["campaign"]
        self.sid = mail_links.sid22(link_id) if isinstance(link_id, uuid.UUID) else str(link_id)
        self.site = FB_SITE if fb else SITE
        self.code = FB_INVITE if fb else SITE_CODE
        self.links = []

    def link(self, key, dest):
        host = urllib.parse.urlsplit(dest).hostname or ""
        if not ALLOW.match(host): raise ValueError("link %s goes to %s, which the click tracker does not allow" % (key, host))
        u = mail_links.track(self.sid, self.campaign, key, dest)
        if self.fb and u.startswith(mail_links.SITE): u = FB_SITE + u[len(mail_links.SITE):]
        self.links.append((key, dest, u))
        return u

    def page(self, key, path): return self.link(key, self.site + path)

    def invite(self, key="coupon"):
        """The MyCNBox sign-up through /go/ (counted per placement; on fb.* it carries the partner's code)."""
        return self.link(key, "%s/go/mycnbox?k=invite&p=email-%s" % (self.site, self.t))

    def unsub(self): return "%s/unsubscribe?u=%s&t=%s" % (self.site, urllib.parse.quote(self.uid), token(self.uid))

    def img(self, pid, src): return email_img(pid, src, self.upload)


def card(ctx, cat, n, pid, note=""):
    p = cat.p[pid]
    url = ctx.site + "/product/" + urllib.parse.quote(pid)
    href = esc(ctx.link("card-%d" % n, url))
    img = esc(ctx.img(pid, p.get("img")) if p.get("img") else "")
    title = esc(p.get("title") or "")
    qc = cat.qc(pid)
    well_ = ('<a href="%s" style="display:block;text-decoration:none;"><img class="pc-img" src="%s" width="232" height="232" alt="%s" '
             'style="display:block;width:100%%;max-width:232px;height:auto;margin:0 auto;border:0;outline:none;"></a>' % (href, img, title)) if img else "&nbsp;"
    pill = ('<td class="%s" align="center" bgcolor="%s" style="border-radius:999px;background:%s;mso-padding-alt:9px 0;%s">'
            '<a class="%s" href="%s" style="display:block;padding:9px 0;font-family:%s;font-size:13px;line-height:16px;font-weight:600;'
            'color:%s;text-decoration:none;border-radius:999px;mso-padding-alt:0;">%s</a></td>')
    buy = pill % ("pc-btn", PRI, PRI, "border:1px solid #5C5C5C;", "pc-btn-a", href, FONT, PRI_FG, "Buy")
    if qc:
        qcp = pill % ("pc-out", "#FFFFFF", "#FFFFFF", "width:40%%;border:1px solid %s;" % LINE, "pc-ink", esc(ctx.link("card-%d-qc" % n, url + "#qc")), FONT, INK, "QC")
        pills = qcp + '<td width="8" style="width:8px;font-size:0;line-height:0;">&nbsp;</td>' + buy
    else:
        pills = buy
    pills = '<table role="presentation" width="100%%" cellpadding="0" cellspacing="0" style="margin-top:12px;"><tr>%s</tr></table>' % pills
    note = ('<div class="pc-ink" style="margin:0 0 4px;font-family:%s;font-size:13px;line-height:17px;font-weight:700;color:%s;">%s</div>' % (FONT, INK, note)) if note else ""
    qline = ('<div class="pc-mut" style="margin-top:2px;font-family:%s;font-size:12px;line-height:16px;color:%s;">%d QC photo%s</div>' % (FONT, MUT, qc, "" if qc == 1 else "s")) if qc else ""
    return ('<td class="pc-col" width="50%%" valign="top" style="width:50%%;padding:0 8px 28px;vertical-align:top;">'
            '<table role="presentation" width="100%%" cellpadding="0" cellspacing="0">'
            '<tr><td class="pc-well-img" bgcolor="%s" style="padding:14px;background:%s;border-radius:12px;">%s</td></tr>'
            '<tr><td style="padding:12px 2px 0;">%s'
            '<div class="pc-mut" style="font-family:%s;font-size:12px;line-height:16px;font-weight:500;color:%s;">%s</div>'
            '<a href="%s" class="pc-ink" style="display:block;height:38px;overflow:hidden;margin-top:3px;font-family:%s;font-size:14px;line-height:19px;font-weight:600;color:%s;text-decoration:none;">%s</a>'
            '<div class="pc-ink" style="margin-top:6px;font-family:%s;font-size:15px;line-height:20px;font-weight:700;color:%s;">%s</div>%s'
            '%s</td></tr></table></td>') % (WELL, WELL, well_, note, FONT, MUT, esc(p.get("brand") or ""), href, FONT, INK, title,
                                            FONT, INK, usd(p.get("usd")), qline, pills)


def grid(ctx, cat, pids, start=1, notes=None):
    """2-up cards on every screen; card numbers (link keys card-1 ...) go on from start."""
    rows = ""
    for i in range(0, len(pids), 2):
        pair = pids[i:i + 2]
        cells = [card(ctx, cat, start + i + k, pid, (notes or {}).get(pid, "")) for k, pid in enumerate(pair)]
        cells[0] = cells[0].replace("padding:0 8px 28px;", "padding:0 8px 28px 0;", 1)
        if len(cells) > 1: cells[1] = cells[1].replace("padding:0 8px 28px;", "padding:0 0 28px 8px;", 1)
        if len(pair) == 1: cells.append('<td class="pc-col pc-empty" width="50%" style="width:50%;"></td>')
        rows += "<tr>%s</tr>" % "".join(cells)
    return '<table role="presentation" width="100%" cellpadding="0" cellspacing="0">' + rows + '</table>'


DARK_CSS = (
    "body{margin:0!important;padding:0!important;-webkit-text-size-adjust:100%;-ms-text-size-adjust:100%}"
    "a{text-decoration:none}"
    "@media only screen and (max-width:520px){"
    ".pc-pad{padding-left:20px!important;padding-right:20px!important}"
    ".pc-h1{font-size:26px!important}"
    ".pc-col{padding-bottom:20px!important}"
    ".pc-well-img{padding:8px!important}"
    ".pc-img{max-width:220px!important}"
    ".pc-ag{padding:16px 10px 18px!important}}"
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

WHY_NEW = "You get this email because you just created an account at %s."
WHY_ALL = "You get this email because you have an account at %s and asked for emails."
WHY_SAVED = "You get this email because you saved finds at %s and asked for emails."


def wrap(ctx, inner, pre_text, why):
    """The whole email: hidden preheader, text header, content, footer (why they get it and the affiliate line;
    Unsubscribe; the postal address from FOOTER_ADDRESS; the copyright line)."""
    dark = "".join("%s{%s}" % (s, r) for s, r in _DARK_RULES)
    ogsc = "".join("[data-ogsc] %s{%s}" % (s, r) for s, r in _DARK_RULES) + \
        "[data-ogsb] .pc-bg,[data-ogsb] .pc-out{background:#0A0A0A!important}[data-ogsb] .pc-well{background:#262626!important}[data-ogsb] .pc-btn{background:#E5E5E5!important}"
    hidden = ('<div style="display:none;max-height:0;max-width:0;overflow:hidden;opacity:0;mso-hide:all;font-size:1px;line-height:1px;color:#FFFFFF;">%s%s</div>'
              % (esc(pre_text), "&#8199;&#65279;&#847; " * 60)) if pre_text else ""
    host = urllib.parse.urlsplit(ctx.site).hostname.replace("www.", "")
    home = esc(ctx.page("header", "/"))
    browse = esc(ctx.page("header-browse", "/"))
    fl = '<a href="%s" class="pc-mut" style="color:#6B6B6B;text-decoration:underline;">%s</a>'
    foot_site = fl % (esc(ctx.page("footer-site", "/")), host)
    links = fl % (esc(ctx.unsub()), "Unsubscribe")
    p = '<p class="pc-mut" style="margin:%s;font-family:%s;font-size:12px;line-height:1.6;color:#6B6B6B;text-align:center;">%s</p>'
    footer = (p % ("20px 0 6px", FONT, (why % foot_site) + " Our links to shopping agents are affiliate links.")
              + p % ("0 0 6px", FONT, links)
              + (p % ("0 0 6px", FONT, esc(FOOTER_ADDRESS)) if FOOTER_ADDRESS else "")
              + p % ("0", FONT, "&copy; Puro Classico"))
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
<td align="right"><a href="%s" class="pc-mut" style="font-family:%s;font-size:14px;line-height:24px;font-weight:500;color:#6B6B6B;text-decoration:none;">Browse finds</a></td>
</tr></table></td></tr>
<tr><td class="pc-pad" style="padding:0 32px;"><table role="presentation" width="100%%" cellpadding="0" cellspacing="0"><tr><td class="pc-line" height="1" style="height:1px;line-height:1px;font-size:1px;background:#E5E5E5;">&nbsp;</td></tr></table></td></tr>
<tr><td class="pc-pad" style="padding:40px 32px 8px;font-family:%s;">%s</td></tr>
<tr><td class="pc-pad" style="padding:24px 32px 40px;">
<table role="presentation" width="100%%" cellpadding="0" cellspacing="0"><tr><td class="pc-line" height="1" style="height:1px;line-height:1px;font-size:1px;background:#E5E5E5;">&nbsp;</td></tr></table>
%s
</td></tr>
</table>
<!--[if mso]></td></tr></table><![endif]-->
</td></tr></table></body></html>""") % (DARK_CSS.replace("__DARK__", dark), ogsc, hidden, FONT, home, FONT, browse, FONT, FONT, inner, footer)


class Mail:
    def __init__(self, subject, html, pre="", items=(), variant=None):
        self.subject, self.html, self.pre, self.items, self.variant = subject, html, pre, list(items), variant


def mail(ctx, subject, inner, pre, why, items=(), variant=None):
    return Mail(subject, wrap(ctx, inner, pre, why), pre, items, variant)


# ---------------------------------------------------------------- templates
def agent_key(m): return m.agent if m.agent and m.agent != "mycnbox" else "mycnbox"


def agent_card(ctx, key):
    """The coupon block for the member's agent: MyCNBox (default) or the agent they picked."""
    name, url, code, bonus, terms, guide, coupons = AGENTS[key]
    code = ctx.code if key == "mycnbox" else code
    href = ctx.invite("coupon") if key == "mycnbox" else ctx.link("coupon", url)
    label = "Claim your coupons" if coupons else "Sign up with %s" % name
    lines = esc(bonus)
    if key != "mycnbox": lines = (lines + " " if lines else "") + esc(terms or "Sign-up offers are set by %s and can change." % name)
    return well(logo(agent_logo(key, ctx.upload), name) + sp(14)
                + (code_box(code) + sp(18) if code else "")
                + btn(href, label, "primary", "sponsored nofollow noopener")
                + '<p class="pc-mut" style="margin:16px auto 0;max-width:400px;font-family:%s;font-size:13px;line-height:1.6;color:%s;text-align:center;">%s</p>' % (FONT, MUT, lines))


def w0_subject(ctx, key, late=False):
    name, _, code, _, _, _, coupons = AGENTS[key]
    code = ctx.code if key == "mycnbox" else code
    if late: return "Sorry this is late: code %s" % code if code else "Sorry, your welcome email is late"
    if code: return "Your %s coupons: code %s" % (name, code)
    return ("Your %s welcome coupons" if coupons else "Your %s sign-up link is here") % name


def w0_pre(key):
    name, _, _, bonus, _, _, coupons = AGENTS[key]
    if key == "mycnbox": return "Up to $500 in coupons for your first orders."
    t = bonus or "Your %s sign-up link, one tap away." % name
    return t if len(t) >= 30 else t + " Sign up free."


def cat_plus(cat, k):
    return (cat.plus.get(k) if cat else None) or {"finds": "10,600+", "qc": "1,300+"}[k]


def five_steps(cat, agent_name):
    """The 5 steps of the 56-second video (how-to-order.html transcript)."""
    return [("Find it", "Search %s finds, or filter by brand and category in one tap." % cat_plus(cat, "finds")),
            ("Check it", "Open the QC photos: real photos from people who already bought it."),
            ("Tap Buy", "The exact listing opens in %s, the agent that buys it for you in China." % agent_name),
            ("Approve it", "It arrives at the %s warehouse and they photograph your item. Looks right? Approve it." % agent_name),
            ("Ship it", "Everything goes into one parcel, and it usually reaches you in about 1 to 3 weeks.")]


def video_block(ctx):
    return ('<a href="%s" style="display:block;text-decoration:none;"><img src="%s" width="536" alt="Watch: how to order from China (0:56)" '
            'style="display:block;width:100%%;max-width:536px;height:auto;border:0;border-radius:12px;margin:0 auto;"></a>') % (
        esc(ctx.page("video", "/how-to-order?f=landscape")), esc(SITE + "/media/tutorial-email.jpg"))


def guide_label(guide): return "Compare agent coupons" if guide == "/guides/agent-coupons" else "How the coupons work"


def links_row(ctx, video_key, guide):
    return ('<p class="pc-mut" style="margin:0;font-family:%s;font-size:14px;line-height:1.7;color:%s;text-align:center;">%s&nbsp;&nbsp;&middot; &nbsp;%s</p>'
            % (FONT, MUT, tlink(ctx.page(video_key, "/how-to-order"), "Watch the 56-second video", True), tlink(ctx.page("guide", guide), guide_label(guide), True)))


def how_it_works(name):
    return small("How it works: sign up with the button and the coupons land in your %s account. Then open any find on "
                 "Puro Classico and tap Buy: the exact listing opens in %s, ready to order." % (esc(name), esc(name)), 20)


def render_w0(ctx, m, cat, arm="a"):
    key = agent_key(m)
    name, _, _, _, _, guide, coupons = AGENTS[key]
    intro = ("Thanks for joining Puro Classico. Here is the coupon pack we promised when you signed up." if key == "mycnbox"
             else "Thanks for joining Puro Classico. You picked %s as your agent, so here is your sign-up link." % esc(name))
    inner = (h1("Your %s %s" % (esc(name), "coupons" if coupons else "sign-up link"))
             + lead(intro)
             + agent_card(ctx, key) + how_it_works(name) + sp(22)
             + links_row(ctx, "video", guide))
    items = []
    if arm == "b" and cat:
        items = pick_finds(cat, m, 2, random.Random(m.id + "w0"))
        if len(items) == 2:
            inner += hr("40px 0 32px") + h2("Two finds to start with") + lead("Popular finds with real photos, one tap from your agent.", 15, 24) + grid(ctx, cat, items)
        else: items = []
    return mail(ctx, w0_subject(ctx, key), inner, w0_pre(key), WHY_NEW, items, "w0-row:%s" % arm)


def render_w0_late(ctx, m, cat):
    key = agent_key(m)
    name, _, _, _, _, guide, _ = AGENTS[key]
    inner = (h1("Sorry this is late")
             + lead("Our emails were down for a few days, so your welcome email is late. Here is everything in one place: your coupons and how your first order works.")
             + agent_card(ctx, key)
             + hr("40px 0 32px") + h2("Your first order in 5 steps", "left") + sp(12)
             + step_rows(five_steps(cat, name))
             + video_block(ctx) + sp(18)
             + links_row(ctx, "video-link", guide))
    return mail(ctx, w0_subject(ctx, key, late=True), inner, "Your coupons plus your first order in 5 steps.", WHY_NEW.replace("just created", "created"))


def render_w1(ctx, m, cat):
    key = agent_key(m)
    name, url, code, _, _, _, coupons = AGENTS[key]
    code = ctx.code if key == "mycnbox" else code
    signup = ctx.invite("coupon") if key == "mycnbox" else ctx.link("coupon", url)
    ask = ("No %s account yet? Sign up with code %s for the new-user coupons." % (esc(name), esc(code))) if code else ("No %s account yet? Sign up with our link." % esc(name))
    inner = (h1("Your first order, start to finish")
             + lead("Watch the 56-second video, then follow the same 5 steps. You pay for the item first, and for shipping later, once for one parcel.")
             + video_block(ctx) + sp(20)
             + btn(ctx.page("video-btn", "/how-to-order"), "Watch the video")
             + hr("40px 0 32px") + h2("The 5 steps", "left") + sp(12)
             + step_rows(five_steps(cat, name))
             + (small("The video shows MyCNBox. With %s the steps are the same." % esc(name), 0) + sp(16) if key != "mycnbox" else "")
             + well(lead(ask, 15, 18) + btn(signup, "Claim your coupons" if coupons else "Sign up with %s" % esc(name), "outline", "sponsored nofollow noopener"), "24px 20px 26px")
             + small("Stuck on anything? Ask in our %s. Members share QC tips and haul reviews daily." % tlink(ctx.page("discord", "/discord"), "Discord"), 24))
    return mail(ctx, "Your first order, start to finish", inner, "A 56-second video and 5 steps to your door.", WHY_ALL)


def render_w2(ctx, m, cat):
    def ag(key, k):
        name, url, code, _, _, _, _ = AGENTS[key]
        code = ctx.code if key == "mycnbox" else code
        href = ctx.invite("agent-" + key) if key == "mycnbox" else ctx.link("agent-" + key, url)
        text = {"mycnbox": "Up to $500 in coupons, mostly for shipping, one per parcel.",
                "kakobuy": "Up to $410 in coupons, split across several with minimum spends."}[key]
        return ('<td class="pc-col" width="50%%" valign="top" style="width:50%%;padding:%s;vertical-align:top;">'
                '<table role="presentation" width="100%%" cellpadding="0" cellspacing="0"><tr><td class="pc-well pc-ag" align="center" bgcolor="%s" style="padding:20px 14px 22px;background:%s;border-radius:12px;text-align:center;">'
                '%s<div class="pc-ink" style="margin:10px 0 2px;font-family:%s;font-size:15px;line-height:20px;font-weight:700;color:%s;">%s</div>'
                '<div class="pc-ink" style="margin:0 0 6px;font-family:%s;font-size:14px;line-height:20px;font-weight:600;color:%s;">Code <span style="-webkit-user-select:all;user-select:all;">%s</span></div>'
                '<div class="pc-mut" style="margin:0 0 14px;font-family:%s;font-size:12px;line-height:17px;color:%s;">%s</div>%s</td></tr></table></td>') % (
            "0 6px 0 0" if k == 0 else "0 0 0 6px", WELL, WELL, logo(agent_logo(key, ctx.upload), name, 40), FONT, INK, esc(name), FONT, INK, esc(code), FONT, MUT, esc(text),
            btn(href, "Sign up", "outline", "sponsored nofollow noopener").replace("padding:13px 26px", "padding:10px 20px"))
    agents = '<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>' + ag("mycnbox", 0) + ag("kakobuy", 1) + '</tr></table>'
    checks = [("Logo", "Shape, size and position. Compare it with the listing photos and other QC photos of the same find."),
              ("Stitching", "Straight, even lines and no loose threads, around the logo and along the seams."),
              ("Colour", "Warehouse light can shift colours a little. Compare with the listing photos under neutral light."),
              ("Size tag", "The tag should show the size you ordered. Not sure? Compare with the measurements in the size chart.")]
    inner = (h2("Got your agent account?")
             + lead("Sign up with one of these and the new-user coupons go straight into your account.", 15, 18)
             + agents
             + hr("36px 0 32px")
             + h1("How to check QC photos")
             + lead("When your item reaches the agent's warehouse, they photograph it before it ships. Check these four things.")
             + step_rows(checks)
             + small("Something looks wrong? You can usually ask the agent for a return or exchange before it ships.", 0) + sp(24)
             + btn(ctx.page("qc-checker", "/tools/qc-checker"), "Open the QC checker")
             + small(tlink(ctx.page("qc-guide", "/guides/how-to-qc"), "Read the full QC guide"), 18))
    return mail(ctx, "How to check your QC photos", inner, "Logo, stitching, colour and the size tag.", WHY_ALL)


def taste_line(m):
    bits = []
    if m.saves: bits.append("what you saved")
    if m.personal and m.seen: bits[:1] = ["what you viewed and saved" if m.saves else "what you viewed"]
    if m.styles: bits.append("your style (%s)" % ", ".join(STYLES[k]["name"] for k in m.styles))
    sz = (m.size or {}).get("l") or ""
    if sz: bits.append("your usual size (%s)" % sz)
    if not bits: return "the most viewed and saved finds right now"
    return bits[0] if len(bits) == 1 else ", ".join(bits[:-1]) + " and " + bits[-1]


SAVE_TIP = "Tap the star on any find to save it. We email you when its price drops, it is back in stock or new QC photos arrive."


def render_w3(ctx, m, cat, picks):
    if len(picks) < 4: return None           # not enough finds left for this member: no email rather than a thin one
    subj = "%d finds picked for your style" % len(picks) if m.styles else "%d finds picked just for you" % len(picks)
    inner = (h1("%d picks for you" % len(picks))
             + lead("Picked from %s." % esc(taste_line(m)), 16, 32)
             + grid(ctx, cat, picks) + sp(8)
             + btn(ctx.page("browse", "/"), "Browse all finds")
             + small(SAVE_TIP, 24))
    return mail(ctx, subj, inner, "Matched to your saves, style and size.", WHY_ALL, picks)


CAT_WORD = {"Tops": "tops", "Shoes": "shoes", "Outerwear": "outerwear", "Accessories": "accessories", "Pants": "pants",
            "Bags": "bags", "Shorts": "shorts", "Headwear": "headwear", "Toys": "toys"}


def picks_subject(cat, picks, arm):
    """Under 25 characters. a: curiosity; b: the count and the item types."""
    if arm == "a": return "Picked for you this week"
    counts = {}
    for i in picks:
        w = CAT_WORD.get(cat.p[i].get("cat"))
        if w: counts[w] = counts.get(w, 0) + 1
    top = [w for w, _ in sorted(counts.items(), key=lambda kv: -kv[1])]
    for s in (("%d picks: %s and %s" % (len(picks), top[0], top[1])) if len(top) > 1 else "",
              ("%d picks: %s" % (len(picks), top[0])) if top else ""):
        if s and len(s) < 25: return s
    return "%d new picks for you" % len(picks)


def render_picks(ctx, m, cat, picks, arm="a"):
    if len(picks) < 4: return None
    k = sum(1 for i in picks if cat.qc(i))
    pre = (("All %d come with real QC photos." if k == len(picks) else "%d of them come with real QC photos.") % k) if k else "New finds matched to your saves and style."
    inner = (h1("This week's picks")
             + lead("%d finds we think you'll like, picked from %s.%s" % (len(picks), esc(taste_line(m)), " Finds with QC photos come first." if k else ""), 16, 32)
             + grid(ctx, cat, picks) + sp(8)
             + btn(ctx.page("browse", "/"), "Browse all finds")
             + small(SAVE_TIP, 24))
    return mail(ctx, picks_subject(cat, picks, arm), inner, pre, WHY_ALL, picks, "picks-subject:%s" % arm)


def change_note(c):
    if c["type"] == "price": return "Now %s, was %s" % (usd(c["new"]), usd(c["old"]))
    if c["type"] == "stock": return "Back in stock"
    n = max(1, int(c.get("n1", 0)) - int(c.get("n0", 0)))
    return ("%d new QC photo%s" % (n, "" if n == 1 else "s")) if c.get("n0") else "%d QC photos, the first set" % n


def render_alert(ctx, m, cat, changes, more):
    """changes: [{type: price|stock|qc, id, old, new, n0, n1}], one per saved find, biggest news first."""
    pids = [c["id"] for c in changes]
    notes = {c["id"]: esc(change_note(c)) for c in changes}
    if len(changes) == 1:
        c = changes[0]
        subj = {"price": "A saved find dropped to %s" % usd(c.get("new")), "stock": "A saved find is back in stock",
                "qc": "New QC photos for a saved find"}[c["type"]]
        title = {"price": "A saved find dropped in price", "stock": "A saved find is back in stock", "qc": "New QC photos for a saved find"}[c["type"]]
        pre = {"price": "Now %s, was %s. One tap from your agent." % (usd(c.get("new")), usd(c.get("old"))),
               "stock": "It is back in stock, one tap from your agent.", "qc": "%s to check before you buy." % change_note(c)}[c["type"]]
        intro = "You saved this find. Here is what changed, and a few similar finds you might like."
    else:
        subj = "%d updates on your saved finds" % len(changes)
        title = "News on your saved finds"
        pre = ""
        for c in changes:
            nxt = (pre + "; " if pre else "") + change_note(c)
            if len(nxt) > 48: break
            pre = nxt
        pre = (pre or "Price drops, restocks and QC photos.") + "."
        intro = "You saved these finds. Here is what changed since your last alert, and a few similar finds."
    inner = h1(esc(title)) + lead(intro, 16, 32) + grid(ctx, cat, pids, 1, notes)
    if more:
        inner += hr("12px 0 32px") + h2("More like this") + lead("Similar finds, one tap from your agent.", 15, 24) + grid(ctx, cat, more, len(pids) + 1)
    inner += sp(8) + btn(ctx.page("saved", "/?saved=1"), "See your saved finds")
    return mail(ctx, subj, inner, pre, WHY_SAVED, pids + list(more))


def wb1_picks(cat, m, last, rnd):
    """4 finds for WB1: partner finds new since the last visit first, topped up with the most popular ones."""
    picks = pick_finds(cat, m, 4, rnd, pool=cat.fresh_partners(last) or [])
    return picks + pick_finds(cat, m, 4 - len(picks), rnd, exclude=picks) if len(picks) < 4 else picks


def render_wb1(ctx, m, cat, n_new, picks):
    subj = ("%s new finds since your visit" % "{:,}".format(n_new)) if n_new >= 10 else "New finds since your last visit"
    head = ("%s new finds since your last visit" % "{:,}".format(n_new)) if n_new >= 10 else subj
    inner = (h1(esc(head))
             + lead("The spreadsheet has grown since you last stopped by. Here are some of the most viewed new finds, with real QC photos where we have them.", 16, 32)
             + (grid(ctx, cat, picks) + sp(8) if picks else "")
             + btn(ctx.page("browse", "/"), "Browse all finds"))
    return mail(ctx, subj, inner, "The most viewed new finds, one tap away.", WHY_ALL, picks)


def render_wb2(ctx, m, cat):
    """Day 90. A visit (a sign-in or a find opened) keeps the emails coming, so "Yes" opens the site (counted per email,
    like every link); "No" is the unsubscribe page, direct like the footer link, where one tap stops everything."""
    inner = (h1("Keep getting our weekly picks?")
             + lead("It has been a while since your last visit. If you still want our picks, stop by the site once and we will keep sending them. No hard feelings either way.", 16, 28)
             + btn(ctx.page("keep", "/"), "Yes, take me to the finds") + sp(12)
             + btn(ctx.unsub(), "No, stop all emails", "outline")
             + small("If you don't stop by, we will stop sending in a few weeks. Your account and your saved finds stay.", 24))
    return mail(ctx, "Keep getting our weekly picks?", inner, "Visit once to keep them, or unsubscribe.", WHY_ALL)


# ---------------------------------------------------------------- sending
class Sender:
    """Every send of a run goes through here: guard, caps, stop lines, a fresh look at opt-out and suppression, the
    email_sends row before the call, the call through the stream's provider, the row after it, the member's profile."""

    def __init__(self, mode, now, provs):
        self.mode, self.now, self.provs = mode, now, provs
        self.today = day_at(now)
        self.batches = {}
        self.stats = {"attempted": 0, "sent": 0, "failed": 0}
        self.per_tpl = {}
        self.sends = []            # this run's accepted Plunk emails, for the delivery check
        self.fails_in_row = 0
        self.stopped = None
        self.stopline = None       # None: not read yet; "": clear; text: why marketing stopped
        self.suppressed = set()
        self.keys = {}             # (member, template, campaign_key) -> when, for rows that did not fail
        self.failed = {}           # (member, template, campaign_key) -> failed tries
        self.log_loaded = False
        self.recent = {}           # member -> marketing send times (FREQ_TEMPLATES), last 7 days
        self.today_n = 0
        self.today_tpl = {}
        self.today_at = []         # (template, when) of today's sends
        self.cap = None
        self.day_n = 1
        self.run_n = 0             # capped sends this run

    def can(self, template): return bool(self.provs.get(TEMPLATES[template]["group"]))

    # -- what was sent before
    def load_keys(self, flt):
        rows = sb_all("email_sends?select=member_id,template,campaign_key,status,error,created_at&%s&order=created_at" % flt)
        for r in rows:
            k = (r.get("member_id"), r.get("template"), r.get("campaign_key"))
            if r.get("status") == "failed":
                if not str(r.get("error") or "").startswith(STOP_MARK): self.failed[k] = self.failed.get(k, 0) + 1
            else: self.keys[k] = parse_ts(r.get("created_at")) or self.now

    def load_log(self):
        """Today's volume, the warm-up day and each member's recent marketing emails (frequency caps)."""
        if self.log_loaded: return
        rows = sb_all("email_sends?select=member_id,template,stream,status,created_at&status=neq.failed&created_at=gte.%s&order=created_at" % iso(self.now - timedelta(days=7)))
        for r in rows:
            t = parse_ts(r.get("created_at"))
            if not t: continue
            if t >= self.today:
                self.today_n += 1; self.today_tpl[r.get("template")] = self.today_tpl.get(r.get("template"), 0) + 1
                self.today_at.append((r.get("template"), t))
            if r.get("member_id") and r.get("template") in FREQ_TEMPLATES:
                self.recent.setdefault(r["member_id"], []).append(t)
        first = sb("email_sends?select=created_at&status=eq.sent&stream=neq.test&order=created_at.asc&limit=1")
        t0 = parse_ts(first[0].get("created_at")) if first else None
        self.day_n = (self.today - day_at(t0)).days + 1 if t0 else 1
        self.cap = next(c for d, c in RAMP if d is None or self.day_n <= d)
        if MAX_DAILY: self.cap = min(self.cap, MAX_DAILY)
        self.log_loaded = True
        say("warm-up: day %d of sending, today's cap %d, %d sent today so far" % (self.day_n, self.cap, self.today_n))

    def ramp(self):
        """(active within days, weekly picks a day or None) for today's warm-up week."""
        self.load_log()
        return next((a, s) for d, a, s in PICKS_RAMP if d is None or self.day_n <= d)

    def budget(self):
        self.load_log()
        return max(0, min(self.cap - self.today_n, MAX_PER_RUN - self.run_n))

    def freq_ok(self, mid):
        self.load_log()
        ts = self.recent.get(mid) or []
        if any(t > self.now - FREQ_GAP for t in ts): return False
        return sum(1 for t in ts if t > self.now - timedelta(days=7)) < FREQ_WEEK

    def marketing_ok(self):
        """The stop lines, read once a run before the first marketing email."""
        if self.stopline is None:
            try: self.stopline = stop_lines(self) or ""
            except SupaError as e: self.stopline = "the stop lines could not be read (%s)" % e
            if self.stopline:
                say("::error::marketing email stopped: %s. Check the cause, then set STOP_LINES_OFF_UNTIL to restart (W0 still goes out)" % self.stopline)
                gh_output("stopline", self.stopline)
        return not self.stopline

    def batch(self, template, variant):
        """The batch id every recipient of this template and variant shares today (the id in the tracked links)."""
        k = (template, variant)
        if k not in self.batches:
            v = "variant=eq.%s" % urllib.parse.quote(variant) if variant else "variant=is.null"
            rows = sb("email_sends?select=batch_id&template=eq.%s&%s&batch_id=not.is.null&stream=neq.test&created_at=gte.%s&order=created_at.asc&limit=1"
                      % (urllib.parse.quote(template), v, iso(self.today)))
            self.batches[k] = uuid.UUID(rows[0]["batch_id"]) if rows else mail_links.new_send_id()
        return self.batches[k]

    def fresh_ok(self, m, template):
        """Opt-out and suppression, read again right before the send."""
        rows = sb("profiles?id=eq.%s&select=marketing_opt_in,email_freq,email_paused_until,email_sunset_at,welcomed" % urllib.parse.quote(m.id))
        if not rows: return False
        p = rows[0]
        if sb("email_suppression?email=eq.%s&select=email" % urllib.parse.quote(m.email_l, safe="")): return False
        if template in W0S: return p.get("welcomed") is not True
        if p.get("marketing_opt_in") is not True: return False
        freq = (p.get("email_freq") or "weekly").lower()
        if freq == "paused" or (freq == "alerts" and TEMPLATES[template]["stream"] != "alerts"): return False
        pu = parse_ts(p.get("email_paused_until"))
        if pu and pu > self.now: return False
        ss = parse_ts(p.get("email_sunset_at"))
        return not (ss and m.last_active() <= ss)

    def send(self, m, template, key, build, patch=None, undo=None, capped=True):
        """build(None) -> the A/B variant (it picks the batch), build(ctx) -> Mail or None. True when it went out.
        capped: counts against the warm-up cap (not W0 in run mode). The frequency caps apply to FREQ_TEMPLATES."""
        if self.stopped or not self.can(template): return False
        gk = (m.id, template, key)
        if gk in self.keys or self.failed.get(gk, 0) >= MAX_FAILS: return False
        if template not in W0S and not self.marketing_ok(): return False
        if capped and self.budget() <= 0: return False
        freq = template in FREQ_TEMPLATES
        if freq and not self.freq_ok(m.id): return False
        # One email a day in all: the welcome series (which does not count toward the 3 a week) and marketing email
        # keep 20 hours apart from each other. W0 never waits.
        if freq and m.onboard_at and self.now - m.onboard_at < FREQ_GAP: return False
        if template in ONBOARD_TEMPLATES and any(t > self.now - FREQ_GAP for t in (self.load_log() or self.recent.get(m.id) or [])): return False
        if not self.fresh_ok(m, template): return False
        tpl = TEMPLATES[template]
        sid = mail_links.new_send_id()
        bid = self.batch(template, build(None))
        ctx = Ctx(template, m.id, sid if m.track else bid, m.fb, upload=True)
        mail = build(ctx)
        if mail is None: return False
        size = len(mail.html.encode("utf-8"))
        if size > MAX_HTML:
            say("::warning::%s for one member is %d KB, over the 90 KB limit: not sent" % (template, size // 1024)); return False
        if text_len(mail.html) < MIN_TEXT: say("::warning::%s has under %d characters of text" % (template, MIN_TEXT))
        prov = self.provs[tpl["group"]]
        meta = {"items": mail.items} if mail.items else None
        row = {"id": str(sid), "batch_id": str(bid), "member_id": m.id, "stream": tpl["stream"], "template": template,
               "campaign": tpl["campaign"], "variant": mail.variant, "subject": mail.subject, "provider": prov,
               "status": "sending", "campaign_key": key, "meta": meta}
        try:
            sb("email_sends", "POST", row, prefer="return=minimal")
        except SupaError as e:
            if e.status == 409 and "pkey" not in e.text:       # the guard: this email was sent (or is going) already
                self.keys[gk] = self.now; return False
            if e.status != 409:                                 # 409 on the primary key: our own row, a retried request
                raise Fatal("email_sends not writable (%s): run scripts/email_v2.sql and scripts/email_v2_engine.sql" % e)
        self.stats["attempted"] += 1
        try:
            res = ADAPTERS[prov](m.email, mail.subject, mail.html, ctx.unsub(), sid, FROM[tpl["group"]], FROM_NAME)
        except Stop as e:
            self._finish(sid, Result(False, error=STOP_MARK + str(e))); self.stopped = str(e); self.stats["failed"] += 1
            return False
        self._finish(sid, res, meta)
        pt = self.per_tpl.setdefault(template, [0, 0])
        if res.ok:
            self.stats["sent"] += 1; pt[0] += 1; self.fails_in_row = 0
            self.keys[gk] = self.now
            if self.log_loaded:
                self.today_n += 1; self.today_tpl[template] = self.today_tpl.get(template, 0) + 1
                self.today_at.append((template, self.now))
            if capped: self.run_n += 1
            if freq: self.recent.setdefault(m.id, []).append(self.now)
            if patch: patch_profile(m.id, patch)
            if res.provider_id and prov == "plunk": self.sends.append((sid, res.provider_id, template, m, undo))
        else:
            self.stats["failed"] += 1; pt[1] += 1; self.fails_in_row += 1
            self.failed[gk] = self.failed.get(gk, 0) + 1
            say("FAIL %s: %s" % (template, hide(res.error)))
            if self.fails_in_row >= 5: self.stopped = "5 sends in a row failed"
        if SEND_PAUSE: time.sleep(SEND_PAUSE)
        return res.ok

    def _finish(self, sid, res, meta=None):
        upd = {"status": "sent" if res.ok else "failed", "provider_id": res.provider_id,
               "error": hide(res.error or res.note or "")[:300] or None}
        if res.contact: upd["meta"] = dict(meta or {}, contact=res.contact)
        try: sb("email_sends?id=eq.%s" % sid, "PATCH", upd, prefer="return=minimal")
        except SupaError as e: say("email_sends row not updated: %s" % e)

    def check_delivery(self):
        """Plunk marks a send that fails inside SES as FAILED and sends no event: look this run's sends up and mark
        those rows failed (W0 and the welcome series also go back a step, so a later run tries again with a new key)."""
        if not self.sends or not PLUNK_KEY: return
        if CHECK_WAIT: time.sleep(CHECK_WAIT)
        pending, bad = list(self.sends), 0
        for _ in range(3):
            nxt = []
            for sid, eid, template, m, undo in pending:
                st = plunk_status(eid)
                if st in ("FAILED", "CANCELLED"):
                    bad += 1
                    try: sb("email_sends?id=eq.%s" % sid, "PATCH", {"status": "failed", "error": "%s at Plunk after it was accepted" % st.lower()}, prefer="return=minimal")
                    except SupaError as e: say("email_sends row not marked failed: %s" % e)
                    if undo: patch_profile(m.id, undo)
                    self.stats["sent"] -= 1; self.stats["failed"] += 1
                elif st in ("PENDING", "SENDING", "SCHEDULED"):
                    nxt.append((sid, eid, template, m, undo))
            if not nxt: break
            pending = nxt
            if CHECK_WAIT: time.sleep(min(30, CHECK_WAIT))
        say("delivery check: %d sends looked up at Plunk, %d failed there after it accepted them" % (len(self.sends), bad))


def stop_lines(S):
    """None, or why marketing email must not go out now (final report, "Stop the next send"): spam complaints at 0.1%
    of the last 30 days' sends; in the first 30 days of sending, 3 or more complaints in 24 hours (Plunk switches a new
    project off at 7); hard bounces at 2% or more of the last day of sending (and at least 2). Provider blocks of
    addresses already on Amazon's list (kind "suppressed") are not complaints about us. STOP_LINES_OFF_UNTIL, a date set
    by the owner after checking, switches the lines off until then."""
    now = S.now
    off = parse_ts(env("STOP_LINES_OFF_UNTIL"))
    if off and off > now:
        say("::warning::the stop lines are off until %s (STOP_LINES_OFF_UNTIL)" % iso(off)); return None
    since = now - timedelta(days=30)
    ev = sb_all("email_events?select=type,send_id,meta,created_at&type=in.(complaint,bounce)&created_at=gte.%s&order=created_at" % iso(since))
    kind = lambda e: (e.get("meta") or {}).get("kind") if isinstance(e.get("meta"), dict) else None
    complaints = [e for e in ev if e.get("type") == "complaint" and kind(e) != "suppressed"]
    sends30 = sb_count("email_sends?select=id&status=eq.sent&stream=neq.test&created_at=gte.%s" % iso(since))
    if complaints and (not sends30 or len(complaints) / float(sends30) >= STOP_COMPLAINT_RATE):
        return "%d spam complaints in 30 days, %.2f%% of %d sends (the line is 0.1%%)" % (len(complaints), 100.0 * len(complaints) / max(1, sends30), sends30)
    S.load_log()
    day = [e for e in complaints if (parse_ts(e.get("created_at")) or since) >= now - timedelta(hours=24)]
    if S.day_n <= 30 and len(day) >= STOP_NEW_COMPLAINTS:
        return "%d spam complaints in the last 24 hours in the first 30 days of sending (Plunk switches a new project off at 7)" % len(day)
    last = sb("email_sends?select=created_at&status=eq.sent&stream=neq.test&order=created_at.desc&limit=1")
    t = parse_ts(last[0].get("created_at")) if last else None
    if t:
        ids = {r["id"] for r in sb_all("email_sends?select=id&status=eq.sent&stream=neq.test&created_at=gte.%s&order=id" % iso(t - timedelta(hours=24)))}
        hard = sum(1 for e in ev if e.get("type") == "bounce" and kind(e) == "hard" and e.get("send_id") in ids)
        if ids and hard >= 2 and hard / float(len(ids)) >= STOP_BOUNCE_RATE:
            return "hard bounces at %.1f%% of the last day's sends (%d of %d, the line is 2%%)" % (100.0 * hard / len(ids), hard, len(ids))
    return None


# ---------------------------------------------------------------- streams
def ts_now(S): return iso(S.now)


def patch_profile(mid, body):
    try: sb("profiles?id=eq.%s" % urllib.parse.quote(mid), "PATCH", body, prefer="return=minimal")
    except SupaError as e: say("profile not updated: %s" % e)


def stream_w0(S, members, cat_get, backfill=False):
    """W0 to new members. run: members of the last 48 hours, never held back by the cap (the honest late version once
    they waited over 12 hours). backfill: the last 14 days within the cap; older ones are marked welcomed, no email."""
    now = S.now
    if not S.can("w0"): say("w0: no provider for the welcome emails"); return
    if backfill:
        old = [m for m in members if not m.welcomed and m.created and m.created < now - timedelta(days=BACKFILL_DAYS)]
        for m in old:
            patch_profile(m.id, {"welcomed": True, "onboard_step": ONBOARD_LAST})   # no welcome series for them either
            m.welcomed, m.step = True, 4
        say("backfill: %d unwelcomed members older than %d days marked welcomed, no email" % (len(old), BACKFILL_DAYS))
        window = timedelta(days=BACKFILL_DAYS)
    else:
        window = W0_WINDOW
    due = [m for m in members if not m.welcomed and m.created and m.created >= now - window and m.mail_ok(S.suppressed)]
    if not backfill:
        waiting = sum(1 for m in members if not m.welcomed and m.created and now - timedelta(days=BACKFILL_DAYS) <= m.created < now - W0_WINDOW)
        if waiting: say("::notice::%d members of the last 14 days got no welcome yet: run the email workflow in backfill mode" % waiting)
    if not due: say("w0: nobody new"); return
    for part in chunks([m.id for m in due], 80):
        S.load_keys("template=in.(w0,w0-late)&member_id=in.%s" % in_list(part))
    due.sort(key=lambda m: m.created, reverse=backfill)
    sent = 0
    for i, m in enumerate(due):
        if S.stopped: break
        if any((m.id, t, "w0") in S.keys for t in W0S):         # sent before, the profile was not marked: mark it now
            patch_profile(m.id, {"welcomed": True, "welcomed_at": ts_now(S)}); continue
        if backfill and S.budget() <= 0:
            say("::warning::backfill: the warm-up cap is used up for today, %d members wait: run backfill again tomorrow" % (len(due) - i)); break
        late = (now - m.created) > W0_LATE
        template = "w0-late" if late else "w0"
        a = arm_of(m.id, "w0-row")

        def build(ctx, m=m, a=a, template=template):
            if ctx is None: return None if template == "w0-late" else "w0-row:%s" % a
            return render_w0_late(ctx, m, cat_get()) if template == "w0-late" else render_w0(ctx, m, cat_get() if a == "b" else None, a)
        patch = {"welcomed": True, "welcomed_at": ts_now(S), "onboard_at": ts_now(S), "email_last_at": ts_now(S)}
        if late: patch["onboard_step"] = max(1, m.step)              # the late version carries the order guide (W1)
        if S.send(m, template, "w0", build, patch, {"welcomed": False}, capped=backfill):
            sent += 1
            m.welcomed, m.welcomed_at, m.onboard_at = True, now, now
            if late: m.step = max(1, m.step)
    say("w0: %d of %d new members welcomed" % (sent, len(due)))


def onboard_due(m, step):
    return day_at(m.welcomed_at, SEND_HOUR) + timedelta(days=ONBOARD_DAYS[step])


def stream_onboarding(S, members, cat_get, act_get):
    """W1 to W3 when due, one at a time, at least 20 hours after the last one. They do not count toward the marketing
    cap, but they do toward the day's warm-up volume."""
    now = S.now
    if not S.can("w1"): return
    due = []
    for m in members:
        if not m.welcomed or not m.welcomed_at or m.welcomed_at < now - ONBOARD_WINDOW or m.step >= ONBOARD_LAST: continue
        if not m.mail_ok(S.suppressed) or not m.may_market(now, "onboarding"): continue
        if m.onboard_at and now - m.onboard_at < FREQ_GAP: continue
        step = m.step + 1
        if now >= onboard_due(m, step): due.append((m, step))
    if not due: say("welcome series: nothing due"); return
    for part in chunks([m.id for m, _ in due], 80):
        S.load_keys("template=in.(%s)&member_id=in.%s" % (",".join(ONBOARD_TEMPLATES), in_list(part)))
    due.sort(key=lambda ms: (not ms[0].engaged(now), ms[0].welcomed_at))
    sent = 0
    for i, (m, step) in enumerate(due):
        if S.stopped: break
        template = "w%d" % step
        if (m.id, template, template) in S.keys:               # sent before, the step was not saved
            patch_profile(m.id, {"onboard_step": step}); continue
        if S.budget() <= 0:
            say("::warning::welcome series: today's warm-up cap is used up, %d wait for tomorrow" % (len(due) - i)); break
        if step == 3: act_get()

        def build(ctx, m=m, step=step):
            if ctx is None: return None
            cat = cat_get()
            if step == 1: return render_w1(ctx, m, cat)
            if step == 2: return render_w2(ctx, m, cat)
            return render_w3(ctx, m, cat, pick_finds(cat, m, 6, random.Random(m.id + "w3")))
        if S.send(m, template, template, build, {"onboard_step": step, "onboard_at": ts_now(S), "email_last_at": ts_now(S)}, {"onboard_step": step - 1}):
            sent += 1; m.step, m.onboard_at = step, now
    say("welcome series: %d sent (%d due)" % (sent, len(due)))


def alert_events(S, cat):
    """News about finds: price drops from data/prices_applied.json (rule-wide batches skipped), back in stock and new QC
    photos from a comparison with the last pass's snapshot (email_state). The first pass only takes the snapshot."""
    now = S.now
    events = []
    batches = (site_json("data/prices_applied.json", {}) or {}).get("batches") or []
    prev = None
    for i, b in enumerate(batches):
        rule, ch = b.get("rule"), b.get("changes") or []
        wide = i == 0 or rule != prev or len(ch) > RULE_WIDE or b.get("kind") != "apply"
        prev = rule
        at = parse_ts(b.get("date"))
        if wide or not at or at < now - timedelta(days=8): continue
        for c in ch:
            try: o, n = float(c["old"][1]), float(c["new"][1])
            except (KeyError, IndexError, TypeError, ValueError): continue
            if o > 0 and n > 0 and o - n >= DROP_USD and DROP_PCT <= (o - n) / o <= DROP_MAX:
                events.append({"type": "price", "id": str(c.get("id")), "at": iso(at), "old": o, "new": n})
    snap = state_get("alert_snapshot") or {}
    kept = [e for e in (state_get("alert_events") or []) if parse_ts(e.get("at")) and parse_ts(e["at"]) >= now - timedelta(days=8)]
    cur = {"sold_out": sorted(cat.sold_out), "checked": cat.health.get("checked"), "qc": cat.qc_n, "at": iso(now)}
    if snap:
        if snap.get("checked") != cur["checked"]:
            at = iso(parse_ts(cur["checked"]) or now)
            for pid in set(snap.get("sold_out") or []) - cat.sold_out:
                if pid in cat.p: kept.append({"type": "stock", "id": pid, "at": at})
        qat = iso(parse_ts(cat.bank.get("updated")) or now)
        old = snap.get("qc") or {}
        for pid, n in cat.qc_n.items():
            n0 = int(old.get(pid, 0) or 0)
            if n > n0 and (n0 == 0 or n - n0 >= QC_MIN_NEW):
                kept.append({"type": "qc", "id": pid, "at": qat, "n0": n0, "n1": n})
    state_put("alert_snapshot", cur)
    state_put("alert_events", kept[-5000:])
    return events + kept


def alert_changes(m, cat, by_pid, now):
    """The news on this member's saved finds since their last alert (and since they saved each find), one per find. A
    save counts while it is alive: saved in the last 90 days, or (with their yes to personalisation) viewed since."""
    since = max(m.alert_at or now - timedelta(days=7), now - timedelta(days=7))
    best = {}
    for pid, saved_at in m.saves.items():
        if pid not in by_pid or pid not in cat.p or pid in cat.sold_out: continue
        if ALERTS_PARTNER_ONLY and not cat.partner(pid): continue
        touched = max([d for d in (saved_at, m.viewed.get(pid) if m.personal else None) if d] or [None]) if saved_at else None
        if touched and touched < now - SAVE_ALIVE: continue
        for e in by_pid[pid]:
            at = parse_ts(e["at"])
            if not at or at <= since or (saved_at and at <= saved_at): continue
            if e["type"] == "price" and float(cat.p[pid].get("usd") or 0) > e["new"] * 1.02: continue   # gone up again
            rank = {"stock": 0, "price": 1, "qc": 2}[e["type"]]
            if pid not in best or rank < best[pid][0]: best[pid] = (rank, e)
    order = sorted(best.values(), key=lambda r: (r[0], -(r[1].get("old", 0) - r[1].get("new", 0))))
    return [e for _, e in order][:4]


def stream_alerts(S, members, cat_get, act_get, state):
    now = S.now
    today = now.strftime("%Y-%m-%d")
    if now < day_at(now, SEND_HOUR) or state.get("alerts") == today or not S.can("alert"): return
    if not S.marketing_ok(): return
    cat = cat_get(); act_get()
    by_pid = {}
    for e in alert_events(S, cat): by_pid.setdefault(e["id"], []).append(e)
    key = "alert-" + today
    S.load_keys("campaign_key=eq.%s" % key)
    active, _ = S.ramp()
    due = []
    for m in members:
        if not m.saves or not m.mail_ok(S.suppressed) or not m.may_market(now, "alerts"): continue
        if now - m.last_active() > timedelta(days=active): continue          # warm-up: the most active first
        ch = alert_changes(m, cat, by_pid, now)
        if ch: due.append((m, ch))
    say("alerts: news on %d finds, %d members to tell (active within %d days)" % (len(by_pid), len(due), active))
    due.sort(key=lambda mc: not mc[0].engaged(now))
    sent = 0
    for i, (m, ch) in enumerate(due):
        if S.stopped: break
        if S.budget() <= 0: say("::warning::alerts: today's warm-up cap is used up, %d wait" % (len(due) - i)); break

        def build(ctx, m=m, ch=ch):
            if ctx is None: return None
            return render_alert(ctx, m, cat, ch, similar(cat, m, [c["id"] for c in ch], 2))
        if S.send(m, "alert", key, build, {"email_alert_at": ts_now(S), "email_last_at": ts_now(S)},
                  {"email_alert_at": iso(m.alert_at) if m.alert_at else None}):
            sent += 1
    say("alerts: %d sent" % sent)
    if not S.stopped: state["alerts"] = today; state_put("passes", state)


def picks_window(now):
    """The Thursday this week's picks belong to (they carry on, 16:00 to midnight UTC, until the next Wednesday)."""
    thu = day_at(now - timedelta(days=(now.weekday() - PICKS_WEEKDAY) % 7))
    if now < thu.replace(hour=SEND_HOUR) or now.hour < SEND_HOUR: return None
    return thu


def stream_picks(S, members, cat_get, act_get, state):
    """Weekly picks from Thursday 16:00 UTC: members active within the warm-up window, engaged first, in daily slices
    while the domain is new; the rest go on the next days until Wednesday. One a week per member."""
    now = S.now
    thu = picks_window(now)
    if not thu or not S.can("picks"): return
    key = "picks-%s" % thu.strftime("%Y-%m-%d")
    if state.get("picks") == key: return
    active, slice_ = S.ramp()
    act_get()                 # the last visit first: may_market and the activity window both read it
    cand = [m for m in members if m.mail_ok(S.suppressed) and m.may_market(now, "newsletter") and m.onboarding_done(now)
            and now - m.last_active() <= timedelta(days=active)]
    if cand: S.load_keys("campaign_key=eq.%s" % key)
    cand = [m for m in cand if (m.id, "picks", key) not in S.keys]
    if not cand:
        state["picks"] = key; state_put("passes", state); say("weekly picks: everyone active within %d days has this week's" % active); return
    room = S.budget()
    if slice_: room = min(room, max(0, slice_ - S.today_tpl.get("picks", 0)))
    ready = [m for m in cand if S.freq_ok(m.id)]
    if room <= 0 or not ready:
        say("weekly picks: %d wait (%s)" % (len(cand), "no room today" if room <= 0 else "frequency caps")); return
    if not S.marketing_ok(): return
    cat = cat_get(); load_emailed(members, now)
    ready.sort(key=lambda m: (not m.engaged(now), hashlib.sha256((m.id + key).encode()).hexdigest()))
    share = min(len(ready), room)
    if len(ready) > room:
        # Short of room: today's room is spread evenly over the hours left today (however often the timer runs), and
        # the members it does not reach go on tomorrow.
        hours_left = max(1, int(math.ceil((day_at(now) + timedelta(days=1) - now).total_seconds() / 3600.0)))
        this_hour = sum(1 for t, at in S.today_at if t == "picks" and at >= now.replace(minute=0, second=0, microsecond=0))
        share = max(0, int(math.ceil((room + this_hour) / float(hours_left))) - this_hour)
        say("weekly picks: %d to go, room for %d more today: %d this run" % (len(ready), room, share))
    sent = 0
    for m in ready:
        if S.stopped or sent >= share or S.budget() <= 0: break
        a = arm_of(m.id, "picks-subject")

        def build(ctx, m=m, a=a):
            if ctx is None: return "picks-subject:%s" % a
            return render_picks(ctx, m, cat, pick_finds(cat, m, 6, random.Random(m.id + key)), a)
        if S.send(m, "picks", key, build, {"email_news_at": ts_now(S), "email_last_at": ts_now(S)}): sent += 1
    say("weekly picks %s: %d sent this run, %d were due" % (key, sent, len(cand)))


def stream_winback(S, members, cat_get, act_get, state):
    """WB1 after 60 days without a visit or sign-in, WB2 after 90 (and at least 10 days after WB1), never to members
    gone for 120 days or more (sunset: no re-engagement blasts). Starts in week 4 of sending."""
    now = S.now
    today = now.strftime("%Y-%m-%d")
    if now < day_at(now, SEND_HOUR) or state.get("winback") == today or not S.can("wb1"): return
    S.load_log()
    if S.day_n < WINBACK_FROM_DAY: return
    if not S.marketing_ok(): return
    act_get()
    due = [m for m in members if m.mail_ok(S.suppressed) and m.may_market(now, "winback") and m.onboarding_done(now)
           and timedelta(days=WINBACK[0]) <= now - m.last_active() < timedelta(days=SUNSET_DAYS)]
    if due: S.load_keys("template=in.(wb1,wb2)&created_at=gte.%s" % iso(now - timedelta(days=200)))
    cat = cat_get() if due else None
    sent = 0
    due.sort(key=lambda m: m.last_active(), reverse=True)
    for m in due:
        if S.stopped: break
        if S.budget() <= 0: say("::warning::win-back: today's warm-up cap is used up"); break
        last = m.last_active(); ep = last.strftime("%Y-%m-%d")
        k1, k2 = "wb1-" + ep, "wb2-" + ep
        if (m.id, "wb1", k1) not in S.keys:
            def build(ctx, m=m, last=last):
                if ctx is None: return None
                return render_wb1(ctx, m, cat, cat.new_since(last), wb1_picks(cat, m, last, random.Random(m.id + "wb1")))
            if S.send(m, "wb1", k1, build, {"email_last_at": ts_now(S)}): sent += 1
        elif (now - last >= timedelta(days=WINBACK[1]) and (m.id, "wb2", k2) not in S.keys
              and S.keys[(m.id, "wb1", k1)] <= now - timedelta(days=10)):
            if S.send(m, "wb2", k2, lambda ctx, m=m: None if ctx is None else render_wb2(ctx, m, cat), {"email_last_at": ts_now(S)}): sent += 1
    say("win-back: %d sent (%d members without a visit for %d to %d days)" % (sent, len(due), WINBACK[0], SUNSET_DAYS))
    if not S.stopped: state["winback"] = today; state_put("passes", state)


def stream_sunset(S, members, act_get, state):
    """Daily: opted in and no product view and no sign-in for 120 days (and SUNSET_MIN_EMAILS emails since, default 0):
    email_sunset_at is set, and no marketing goes out until they come back. A later view or sign-in lifts it."""
    now = S.now
    today = now.strftime("%Y-%m-%d")
    if now < day_at(now, SEND_HOUR) or state.get("sunset") == today: return
    act_get()
    lifted = [m for m in members if m.sunset_at and m.last_active() > m.sunset_at]
    for m in lifted:
        patch_profile(m.id, {"email_sunset_at": None}); m.sunset_at = None
    cand = [m for m in members if m.opt_in and not m.sunset_at and now - m.last_active() >= timedelta(days=SUNSET_DAYS)]
    counts = {}
    if SUNSET_MIN_EMAILS:
        for part in chunks(cand, 60):
            since = min(m.last_active() for m in part)
            rows = sb_all("email_sends?select=member_id,created_at&status=eq.sent&member_id=in.%s&created_at=gte.%s&order=created_at" % (in_list(m.id for m in part), iso(since)))
            la = {m.id: m.last_active() for m in part}
            for r in rows:
                t = parse_ts(r.get("created_at"))
                if t and t > la.get(r.get("member_id"), now): counts[r["member_id"]] = counts.get(r["member_id"], 0) + 1
    n = 0
    for m in cand:
        if counts.get(m.id, 0) >= SUNSET_MIN_EMAILS:
            patch_profile(m.id, {"email_sunset_at": ts_now(S)}); m.sunset_at = now; n += 1
    say("sunset: %d members paused after %d days without a visit, %d came back" % (n, SUNSET_DAYS, len(lifted)))
    state["sunset"] = today; state_put("passes", state)


# ---------------------------------------------------------------- modes
def need(*names):
    miss = [n for n in names if not env(n)]
    if miss: raise Fatal("missing settings: %s" % ", ".join(miss))


def lazy(fn):
    box = []

    def get():
        if not box: box.append(fn())
        return box[0]
    return get


def mode_run(mode, provs):
    need("SUPABASE_SERVICE_KEY", "UNSUB_SECRET")
    now = utcnow()
    S = Sender(mode, now, provs)
    try:
        S.suppressed = {str(r.get("email") or "").lower() for r in sb_all("email_suppression?select=email&order=email")}
    except SupaError as e:
        if missing_sql(e): raise NoSQL("email_suppression is missing: run scripts/email_v2.sql, then scripts/email_v2_engine.sql, in Supabase")
        raise Fatal("email_suppression not readable (%s): run scripts/email_v2.sql in Supabase" % e)
    members = load_members()
    cat_get = lazy(Catalog)
    act_get = lazy(lambda: load_activity(members, now) or True)
    try:
        if mode == "backfill":
            stream_w0(S, members, cat_get, backfill=True)
        else:
            state = state_get("passes") or {}
            stream_w0(S, members, cat_get)
            for fn in (stream_onboarding, stream_alerts, stream_picks, stream_winback):
                if S.stopped: break
                if fn is stream_onboarding: fn(S, members, cat_get, act_get)
                else: fn(S, members, cat_get, act_get, state)
            stream_sunset(S, members, act_get, state)
    finally:
        if S.stopped: say("::error::sending stopped: %s" % hide(S.stopped))
        S.check_delivery()
        say("per template: " + (", ".join("%s %d sent %d failed" % (t, v[0], v[1]) for t, v in sorted(S.per_tpl.items())) or "nothing sent"))
        say("summary: mode=%s providers=%s attempted=%d sent=%d failed=%d" % (mode, ",".join("%s:%s" % kv for kv in sorted(provs.items())), S.stats["attempted"], S.stats["sent"], S.stats["failed"]))
    if S.stopped and S.stopped != "5 sends in a row failed": return 1
    if S.stats["attempted"] and S.stats["failed"] * 2 > S.stats["attempted"]:
        say("::error::%d of %d sends failed" % (S.stats["failed"], S.stats["attempted"])); return 1
    return 0


def mode_import_suppression():
    """Once, before the first send: every address Brevo blocked (hard bounces, spam complaints, unsubscribes, blocks by
    hand) goes into email_suppression. Without a working BREVO_API_KEY nothing happens."""
    need("SUPABASE_SERVICE_KEY")
    key = env("BREVO_API_KEY")
    if not key: say("import-suppression: no BREVO_API_KEY, nothing to import"); return 0
    got, offset = [], 0
    while True:
        st, _, t = http("https://api.brevo.com/v3/smtp/blockedContacts?limit=100&offset=%d" % offset, headers={"api-key": key, "accept": "application/json"})
        if st in (401, 403): say("import-suppression: Brevo refused the key (%d), nothing imported" % st); return 0
        if st != 200: say("::warning::import-suppression: Brevo answered %d, nothing imported" % st); return 0
        cs = (json.loads(t or "{}") or {}).get("contacts") or []
        got += cs
        if len(cs) < 100 or offset > 100000: break
        offset += 100
    reason = {"hardBounce": "hard_bounce", "contactFlaggedAsSpam": "complaint"}
    rows, seen = [], set()
    for c in got:
        email = str(c.get("email") or "").strip().lower()
        if "@" not in email or email in seen: continue
        seen.add(email)
        code = str((c.get("reason") or {}).get("code") or "")
        rows.append({"email": email, "reason": reason.get(code, "manual"), "source": "brevo", "detail": ("brevo " + code).strip()[:200]})
    for part in chunks(rows, 500):
        sb("email_suppression?on_conflict=email", "POST", part, prefer="resolution=ignore-duplicates,return=minimal")
    by = {}
    for r in rows: by[r["reason"]] = by.get(r["reason"], 0) + 1
    say("import-suppression: %d blocked addresses from Brevo copied (%s); addresses already on the list were kept as they were"
        % (len(rows), ", ".join("%s %d" % kv for kv in sorted(by.items())) or "none"))
    return 0


# ---------------------------------------------------------------- preview and test (sample members, real catalogue)
def fake_member(n, cat, **kw):
    p = {"id": "00000000-0000-4000-8000-%012d" % n, "created_at": iso(utcnow()), "welcomed": True, "marketing_opt_in": True,
         "agent": kw.get("agent"), "referred_by": FB_REF if kw.get("fb") else None, "style": kw.get("style"), "size": kw.get("size"),
         "email_personal": bool(kw.get("personal"))}
    m = Member(p, {"email": "preview@example.com", "email_confirmed_at": iso(utcnow())})
    if cat and kw.get("taste"):
        top = cat.partners[:400]
        rnd = random.Random(n)
        for i in rnd.sample(top, min(12, len(top))):
            m.seen.add(i); b = cat.p[i].get("brand"); m.brands[b] = m.brands.get(b, 0) + 1
        for i in rnd.sample(top, min(3, len(top))): m.saves[i] = utcnow() - timedelta(days=5)
    return m


def fake_changes(cat, kind):
    rnd = random.Random(7)
    pool = [i for i in cat.partners[:300] if cat.qc(i)]
    a, b = rnd.sample(pool, 2)
    c = next((i for i in pool if cat.qc(i) >= 12 and i not in (a, b)), pool[0])
    pa = float(cat.p[a].get("usd") or 30)
    drop = {"type": "price", "id": a, "old": round(pa * 1.25 + 5, 2), "new": pa}
    if kind == "drop": return [drop]
    return [{"type": "stock", "id": b}, drop, {"type": "qc", "id": c, "n0": cat.qc(c) - 9, "n1": cat.qc(c)}]


# name -> (template, what the sample member and the email get)
VARIANTS = [
    ("w0-a", "w0", {"arm": "a"}), ("w0-b", "w0", {"arm": "b", "style": "street"}), ("w0-kakobuy", "w0", {"arm": "a", "agent": "kakobuy"}),
    ("w0-oopbuy", "w0", {"arm": "a", "agent": "oopbuy"}), ("w0-usfans", "w0", {"arm": "a", "agent": "usfans"}), ("w0-fb", "w0", {"arm": "a", "fb": True}),
    ("w0-late", "w0-late", {}), ("w0-late-fb", "w0-late", {"fb": True}),
    ("w1", "w1", {}), ("w1-kakobuy", "w1", {"agent": "kakobuy"}), ("w2", "w2", {}), ("w2-fb", "w2", {"fb": True}),
    ("w3", "w3", {"style": "street", "size": {"l": "M"}, "taste": True}),
    ("picks-a", "picks", {"arm": "a", "taste": True}), ("picks-b", "picks", {"arm": "b", "taste": True, "style": "old", "personal": True}),
    ("alert", "alert", {"changes": "mixed"}), ("alert-drop", "alert", {"changes": "drop"}),
    ("wb1", "wb1", {"taste": True}), ("wb2", "wb2", {}),
]


def compose(name, template, opts, cat, link_id, upload):
    names = [v[0] for v in VARIANTS]
    m = fake_member(names.index(name) + 1 if name in names else 99, cat, **opts)
    ctx = Ctx(template, m.id, link_id, m.fb, upload)
    rnd = random.Random(name)
    if template == "w0": out = render_w0(ctx, m, cat, opts.get("arm", "a"))
    elif template == "w0-late": out = render_w0_late(ctx, m, cat)
    elif template == "w1": out = render_w1(ctx, m, cat)
    elif template == "w2": out = render_w2(ctx, m, cat)
    elif template == "w3": out = render_w3(ctx, m, cat, pick_finds(cat, m, 6, rnd))
    elif template == "picks": out = render_picks(ctx, m, cat, pick_finds(cat, m, 6, rnd), opts.get("arm", "a"))
    elif template == "alert":
        ch = fake_changes(cat, opts.get("changes"))
        out = render_alert(ctx, m, cat, ch, similar(cat, m, [c["id"] for c in ch], 2))
    elif template == "wb1":
        last = utcnow() - timedelta(days=63)
        out = render_wb1(ctx, m, cat, cat.new_since(last), wb1_picks(cat, m, last, rnd))
    else: out = render_wb2(ctx, m, cat)
    return m, ctx, out


def mode_preview(out_dir):
    if not env("UNSUB_SECRET"): os.environ["UNSUB_SECRET"] = "preview-only"   # links are signed, but not with the live key
    os.makedirs(out_dir, exist_ok=True)
    cat = Catalog()
    rows = []
    for name, template, opts in VARIANTS:
        _, ctx, out = compose(name, template, opts, cat, mail_links.new_send_id(), upload=False)
        kb = len(out.html.encode("utf-8")) / 1024.0
        with open(os.path.join(out_dir, name + ".html"), "w", encoding="utf-8") as f: f.write(out.html)
        rows.append((name, template, out.subject, out.pre, kb, text_len(out.html), len(ctx.links)))
        say("preview %-12s %-8s %4.1f KB %4d chars %2d links  %s | %s" % (name, template, kb, text_len(out.html), len(ctx.links), out.subject, out.pre))
        if kb * 1024 > MAX_HTML: say("::warning::%s is %.0f KB, over the 90 KB limit" % (name, kb))
    idx = "".join('<tr><td><a href="%s.html">%s</a></td><td>%s</td><td>%s</td><td>%s</td><td>%.1f KB</td><td>%d</td><td>%d</td></tr>'
                  % (n, n, t, esc(s), esc(pr), kb, tl, ln) for n, t, s, pr, kb, tl, ln in rows)
    with open(os.path.join(out_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write('<!doctype html><meta charset="utf-8"><title>Email preview</title><body style="font-family:sans-serif;padding:24px">'
                '<h1>Email preview</h1><p>%s. Sample members, real catalogue.</p><table cellpadding="6"><tr><th>Name</th><th>Template</th>'
                '<th>Subject</th><th>Preheader</th><th>Size</th><th>Text</th><th>Links</th></tr>%s</table>' % (iso(utcnow()), idx))
    say("preview: %d emails in %s" % (len(rows), out_dir))
    return 0


def mode_test(provs):
    need("UNSUB_SECRET")
    to = env("TEST_EMAIL")
    if not to: raise Fatal("TEST_EMAIL is not set")
    want = env("TEST_TEMPLATE", "all").lower()
    names = [v for v in VARIANTS if want == "all" or v[0] == want] or [v for v in VARIANTS if v[1] == want][:1]
    if not names: raise Fatal("TEST_TEMPLATE %r unknown: use all, a template (%s) or a preview name (%s)" % (want, ", ".join(TEMPLATES), ", ".join(v[0] for v in VARIANTS)))
    cat = Catalog()
    ok = bad = 0
    for name, template, opts in names:
        prov = provs.get(TEMPLATES[template]["group"])
        if not prov: say("test %s: no provider for its stream, skipped" % name); continue
        sid = mail_links.new_send_id()      # its own id in the links: test clicks never mix with a real email's
        m, ctx, out = compose(name, template, opts, cat, sid, upload=True)
        tpl = TEMPLATES[template]
        try: res = ADAPTERS[prov](to, out.subject, out.html, ctx.unsub(), sid, FROM[tpl["group"]], FROM_NAME)
        except Stop as e: res = Result(False, error=str(e))
        say(("test %s sent through %s: %s" % (name, prov, out.subject)) if res.ok else ("FAIL test %s: %s" % (name, hide(res.error))))
        ok, bad = ok + res.ok, bad + (not res.ok)
        time.sleep(1)
    say("summary: mode=test attempted=%d sent=%d failed=%d" % (ok + bad, ok, bad))
    return 1 if bad * 2 > ok + bad else 0


MODES = ("run", "backfill", "preview", "test", "import-suppression")


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    mode = argv[0] if argv else ""
    if mode not in MODES:
        say("::error::unknown mode %r: use one of %s (nothing is sent)" % (mode, ", ".join(MODES)))
        return 2
    try:
        if mode == "preview": return mode_preview(argv[1] if len(argv) > 1 else env("PREVIEW_DIR", "email_preview"))
        if mode == "import-suppression": return mode_import_suppression()
        provs = providers()
        if not any(provs.values()):
            say("::warning::PLUNK_API_KEY is not set: no emails are sent (the daily health check reports this)")
            gh_output("nokey", "1")
            return 0
        for grp, p in sorted(provs.items()):
            if not p: say("::warning::PLUNK_API_KEY is not set: the %s emails are not sent" % grp); gh_output("nokey", "1")
        if mode == "test": return mode_test(provs)
        return mode_run(mode, provs)
    except NoSQL as e:
        say("::warning::%s. Nothing is sent until then (the daily health check reports this)." % hide(e)); gh_output("nosql", "1"); return 0
    except Fatal as e:
        say("::error::%s" % hide(e)); return 1
    except SupaError as e:
        if missing_sql(e):
            say("::warning::a table or column of Email v2 is missing (%s): run scripts/email_v2.sql, then scripts/email_v2_engine.sql, in Supabase. Nothing more is sent until then." % hide(e)[:160])
            gh_output("nosql", "1"); return 0
        say("::error::Supabase did not answer as expected: %s" % hide(e)); return 1


if __name__ == "__main__":
    sys.exit(main())
