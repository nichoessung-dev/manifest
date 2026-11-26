#!/usr/bin/env python3
"""Email v2 stats (26 Nov 2026): data/email_stats.json, the Email section of /stats (stats.html).

Reads email_sends, email_events, email_suppression and a few profile counts with the service key (tables in
scripts/email_v2.sql) and writes aggregates only. The site and this repository are public: no ids, no addresses, no
per-person rows. Clicks are counted per email and link, never per person (tracking_law: the links carry the email's
batch id, shared by everyone who got that email, version and day), so nothing here rebuilds anyone's click history.

  python scripts/email_stats.py            (SUPABASE_SERVICE_KEY; run and committed by .github/workflows/stats.yml)

What it writes:
  kpi          the last 7 days, the 7 before and the last 30: sent, failed, delivered, bounces, complaints, unsubscribes,
               clicks, human clicks and human clicks to agents, for the emails sent in each period
  alarms       the research report's warning and stop lines, as "ok", "warn" or "stop" (None: nothing to judge yet):
               complaints over 30 days, hard bounces and unsubscribes per send, the machine share of clicks
  streams      the kpi numbers per stream (onboarding, newsletter, alerts, winback), last 7 and 30 days
  mailbox      delivered, bounces, complaints and unsubscribes per mailbox group (gmail, outlook, yahoo, icloud, other):
               the webhook and the unsubscribe pages store only the group of the address; clicks have no group
  templates    the kpi numbers per email (template) and ISO week, the last WEEKS weeks
  links        human clicks per link key (coupon, card-1, ...) in the last 30 days
  experiments  per A/B test and arm (email_sends.variant "<test>:<arm>"): sends, human clicks, the rate, and the
               Bayesian probability that the arm beats the control (Beta(1,1) priors, Monte Carlo, fixed seed)
  warmup       today's sends against the day's cap (the ramp in scripts/mailer.py when it has one, else the plan's)
  health       members opted in, alerts only, paused, stopped for inactivity (sunset), suppressed, unsubscribed lately
  bots         how many clicks the bot rules left out, and why

Human or bot is decided here, from the raw facts the click tracker stores (functions/e/[[path]].js), so the rules can
change and every past click is scored again on the next run. A click scores points; BOT_AT or more is a bot:
  ua        3  no browser user agent, or one the BOT pattern of functions/go/[agent].js names (read from that file)
  prefetch  3  a browser loading ahead (Sec-Purpose / Purpose: prefetch, prerender, preview)
  fast      3  less than FAST_S seconds after the email went out (the nearest send of its batch at or before the click)
  burst     3  two or more clicks from the same network (the tracker's daily-salted network hash) on one email within BURST_S seconds
  scanner   3  a network that only runs mail and web security scanners (SCANNER_ASN)
  quick     2  FAST_S to QUICK_S seconds after the email went out
  cloud     2  a cloud or security-gateway network (CLOUD_ASN): scanners run there, but so do VPNs and some people
"""
import ast, bisect, collections, datetime, json, os, random, re, sys, urllib.error, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUPA = "https://uptpghuduqjqmrxwatbm.supabase.co"
OUT = os.path.join(ROOT, "data", "email_stats.json")
PAGE = 1000
WEEKS = 12                      # ISO weeks in the per-email table
WINDOW_DAYS = 7 * (WEEKS + 2)   # sends and events read on each run (the table's weeks plus two)
LINK_DAYS = 30
DRAWS, SEED = 20000, 20261126   # Monte Carlo draws for the A/B probabilities, fixed seed: the same data gives the same number
ORDER = ["w0", "w1", "w2", "w3", "picks", "alert", "winback1", "winback2"]

# Streams (email_sends.stream) and mailbox groups (meta.mbox on provider and unsubscribe events: gmail, outlook, yahoo,
# icloud or other, from the address's domain when the event was written; clicks carry no address, so no group).
STREAMS = ["onboarding", "newsletter", "alerts", "winback", "service", "other"]
MBOX = ["gmail", "outlook", "yahoo", "icloud", "other"]
MBOX_COLS = ["delivered", "bounces", "soft", "complaints", "unsubs"]
# Warning and stop lines in % (research report): complaints over the last 30 days, hard bounces and unsubscribes in one
# send (or over the last 7 days, which covers the small daily welcome sends), and the machine share of clicks (30 days).
ALARM = {"complaints": (0.05, 0.1), "bounces": (1.0, 2.0), "unsubs": (None, 1.0), "machine": (35.0, 50.0),
         "delivered": (98.0, 95.0)}   # delivered out of sent: a warning under 98%, stop under 95% (only with delivery reports)
DELIVERY_WAIT_H = 2         # emails younger than this are left out of the delivered share (their reports may still come)
COMPLAINTS_SEND_WARN = 2    # 2 complaints in one send: a warning whatever the rate
COMPLAINTS_24H_STOP = 3     # Plunk's new-project limit warns at 3 complaints in 24 hours and switches the project off at 7
SEND_MIN = 100              # per-send lines only for sends of this many emails (one complaint in 30 emails says little)
CLICKS_MIN = 20             # the machine share only from this many clicks in 30 days

FAST_S, QUICK_S, BURST_S, BOT_AT = 5, 30, 2, 3
# Check these against your own clicks (select asn, count(*) from email_events where type = 'click' group by 1) and add to them.
SCANNER_ASN = {26211: "Proofpoint", 22843: "Proofpoint", 16417: "Cisco IronPort", 198605: "Avast"}
CLOUD_ASN = {8075: "Microsoft", 8068: "Microsoft", 8069: "Microsoft", 15169: "Google", 396982: "Google Cloud", 16509: "Amazon",
             14618: "Amazon", 14061: "DigitalOcean", 16276: "OVH", 24940: "Hetzner", 63949: "Akamai (Linode)", 20473: "Vultr",
             31898: "Oracle Cloud", 45102: "Alibaba Cloud", 132203: "Tencent Cloud", 53813: "Zscaler", 22616: "Zscaler",
             44444: "Forcepoint", 40934: "Fortinet", 54538: "Palo Alto Networks"}
UA_OK = re.compile(r"^(Mozilla|Opera)/[0-9.]+ \(")
PREFETCH = re.compile(r"prefetch|prerender|preview", re.I)
# Agents a link can go to (the agent part of ALLOW in functions/e/[[path]].js); our own /go/<agent> redirects count too.
AGENT_HOST = re.compile(r"^(m\.)?mycnbox\.com$|^ikako\.vip$|^(www\.)?(kakobuy|oopbuy|lovegobuy|sugargoo|litbuy|hipobuy|boonbuy|joyagoo|usfans|gtbuy|itaobuy|cssbuy|hubbuy|bbdbuy|superbuy|fishgoo)\.com$", re.I)
OWN_HOST = re.compile(r"^(www\.|fb\.)?puroclassico\.com$", re.I)

# The warm-up plan (days since the first Plunk send, day 1 = that day): used when scripts/mailer.py has no RAMP literal.
RAMP_PLAN = [(1, 3, 150), (4, 7, 250), (8, 14, 400), (15, 21, 700), (22, 28, 1200), (29, None, 2500)]
RAMP_NAMES = ("RAMP", "WARMUP_RAMP", "WARMUP", "RAMP_TABLE", "WARMUP_CAPS")
BOT_FALLBACK = (r"(?<!cu)bot|crawl|spider|slurp|preview|fetch|scan|check|monitor|proxy|compatible;|-user/|headless|phantomjs|puppeteer"
                r"|playwright|selenium|lighthouse|facebookexternalhit|meta-external|mimecast|proofpoint|barracuda|symantec|sophos|fireeye"
                r"|trendmicro|zscaler|safelinks|virustotal")


def load_bot(path=os.path.join(ROOT, "functions", "go", "[agent].js")):
    """The BOT pattern of functions/go/[agent].js (the /go redirect's list of crawlers, previews and mail scanners),
    read from its string pieces, so both places always use the same list. The copy above is only for a missing file."""
    try:
        src = open(path, encoding="utf-8").read()
        m = re.search(r"const BOT = new RegExp\(((?:\s*\+?\s*\"(?:[^\"\\]|\\.)*\")+)\s*,\s*\"i\"\)", src)
        return re.compile("".join(json.loads('"%s"' % p) for p in re.findall(r"\"((?:[^\"\\]|\\.)*)\"", m.group(1))), re.I)
    except Exception:
        return re.compile(BOT_FALLBACK, re.I)


BOT = load_bot()


# ------------------------------------------------------------------ small helpers
def parse_ts(s):
    try: return datetime.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception: return None


def iso(t): return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def week_of(t):
    y, w, _ = t.isocalendar()
    return "%d-W%02d" % (y, w)


def last_weeks(now, n=WEEKS):
    monday = (now - datetime.timedelta(days=now.weekday())).replace(hour=12, minute=0, second=0, microsecond=0)
    return [week_of(monday - datetime.timedelta(weeks=k)) for k in range(n - 1, -1, -1)]


def uuid7_time(u):
    """The send time inside a UUIDv7 (its first 48 bits, in ms), or None for another kind of id."""
    h = str(u or "").replace("-", "").lower()
    if len(h) != 32 or h[12] != "7": return None
    try: return datetime.datetime.fromtimestamp(int(h[:12], 16) / 1000, datetime.timezone.utc)
    except Exception: return None


def to_agent(dest):
    host, _, path = str(dest or "").partition("/")
    return bool(AGENT_HOST.match(host)) or (bool(OWN_HOST.match(host)) and path.startswith("go/"))


def meta_of(row):
    m = row.get("meta")
    if isinstance(m, str):
        try: m = json.loads(m)
        except Exception: m = None
    return m if isinstance(m, dict) else {}


# ------------------------------------------------------------------ warm-up ramp
def norm_ramp(v):
    """A ramp literal as (first day, last day or None, cap) triples, or None when it cannot be read as one.
    Pairs are (last day, cap), or (first day, cap) when the first pair starts at day 0 or 1; a dict is {day: cap}."""
    try:
        if isinstance(v, dict): v = sorted(v.items(), key=lambda kv: (kv[0] is None, kv[0] or 0))
        v = [tuple(x) for x in v]
        if not v: return None
        if all(len(x) == 3 for x in v):
            out = [(int(a), None if b is None else int(b), int(c)) for a, b, c in v]
        elif all(len(x) == 2 for x in v):
            days = [x[0] for x in v]
            if days[0] in (0, 1) and len(v) > 1:          # start days (0-based ones are moved to day 1 = the first day)
                shift = 1 if days[0] == 0 else 0
                starts = [int(d) + shift for d in days]
                out = [(starts[i], starts[i + 1] - 1 if i + 1 < len(v) else None, int(v[i][1])) for i in range(len(v))]
            else:                                         # last days, the last one may be None ("after that")
                out, first = [], 1
                for d, cap in v:
                    out.append((first, None if d is None else int(d), int(cap)))
                    if d is None: break
                    first = int(d) + 1
                if out[-1][1] is not None: out.append((out[-1][1] + 1, None, out[-1][2]))
        else:
            return None
        if any(c <= 0 for _, _, c in out) or any(b is not None and b < a for a, b, _ in out): return None
        return out
    except Exception:
        return None


def ramp_from_mailer(path=os.path.join(ROOT, "scripts", "mailer.py")):
    """The warm-up ramp from scripts/mailer.py, read without running that file: a top-level RAMP (or WARMUP_RAMP, WARMUP,
    RAMP_TABLE, WARMUP_CAPS) literal. None when the file or a usable literal is not there."""
    try: tree = ast.parse(open(path, encoding="utf-8").read())
    except Exception: return None
    for node in tree.body:
        targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) else []
        if not any(isinstance(t, ast.Name) and t.id in RAMP_NAMES for t in targets) or node.value is None: continue
        try: r = norm_ramp(ast.literal_eval(node.value))
        except Exception: r = None
        if r: return r
    return None


def cap_for(ramp, day):
    for a, b, c in ramp:
        if day >= a and (b is None or day <= b): return c
    return ramp[-1][2] if day > 0 else ramp[0][2]


# ------------------------------------------------------------------ bots
def score_clicks(clicks, send_times):
    """Marks each click (dicts with t, send_id, ua, asn, meta) with c["bot"] (True/False) and c["why"] (the rules it hit).
    send_times: {batch or send id: sorted send datetimes}. Re-runnable: it only reads the stored facts."""
    groups = collections.defaultdict(list)
    for c in clicks:
        net = meta_of(c).get("net")
        if net: groups[(c.get("send_id"), net)].append(c)
    burst = set()
    for g in groups.values():
        g.sort(key=lambda c: c["t"])
        for a, b in zip(g, g[1:]):
            if (b["t"] - a["t"]).total_seconds() <= BURST_S: burst.update((id(a), id(b)))
    for c in clicks:
        m, pts, why = meta_of(c), 0, []
        ua = str(c.get("ua") or "")
        if not UA_OK.match(ua) or BOT.search(ua): pts += 3; why.append("ua")
        if PREFETCH.search(str(m.get("purpose") or "")): pts += 3; why.append("prefetch")
        age = None
        times = send_times.get(c.get("send_id"))
        if times:
            i = bisect.bisect_right(times, c["t"]) - 1
            if i >= 0: age = (c["t"] - times[i]).total_seconds()
        if age is None and isinstance(m.get("age_ms"), (int, float)): age = m["age_ms"] / 1000.0
        if age is not None and age < FAST_S: pts += 3; why.append("fast")
        elif age is not None and age < QUICK_S: pts += 2; why.append("quick")
        if id(c) in burst: pts += 3; why.append("burst")
        try: asn = int(c.get("asn")) if c.get("asn") is not None else None
        except (TypeError, ValueError): asn = None
        if asn in SCANNER_ASN: pts += 3; why.append("scanner")
        elif asn in CLOUD_ASN: pts += 2; why.append("cloud")
        c["bot"], c["why"] = pts >= BOT_AT, why
    return clicks


# ------------------------------------------------------------------ A/B
def p_beats(ctrl_h, ctrl_n, arm_h, arm_n, draws=DRAWS, seed=SEED):
    """P(arm's rate > control's rate) with Beta(1,1) priors: Monte Carlo, fixed seed. Successes are capped at trials."""
    rng = random.Random(seed)
    ch, ah = min(ctrl_h, ctrl_n), min(arm_h, arm_n)
    a1, a2, b1, b2 = 1 + ch, 1 + ctrl_n - ch, 1 + ah, 1 + arm_n - ah
    wins = sum(1 for _ in range(draws) if rng.betavariate(b1, b2) > rng.betavariate(a1, a2))
    return round(wins / draws, 3)


def split_variant(v):
    v = str(v or "")
    if ":" not in v: return None
    name, arm = v.rsplit(":", 1)
    return (name, arm) if name and arm else None


# ------------------------------------------------------------------ the aggregates
COLS = ["sent", "failed", "delivered", "bounces", "soft", "complaints", "unsubs", "clicks", "human", "agent"]


def build(sends, events, now, exp_sends=(), old_clicks=(), health=None, first_send=None, ramp=None, ramp_source="plan"):
    """Everything in data/email_stats.json except "generated", from raw rows (pure, for the tests)."""
    ramp = ramp or RAMP_PLAN
    weeks = last_weeks(now)
    wset = set(weeks)
    d7, d14, d30 = now - datetime.timedelta(days=7), now - datetime.timedelta(days=14), now - datetime.timedelta(days=LINK_DAYS)

    # every email: its template, version and send time, under its own id and under its batch id
    owner, send_times, stream_of = {}, collections.defaultdict(list), collections.defaultdict(collections.Counter)
    all_sends = {}
    for s in list(sends) + list(exp_sends):
        if s.get("id"): all_sends.setdefault(s["id"], s)
    for s in all_sends.values():
        t = parse_ts(s.get("created_at"))
        if not t: continue
        s["_t"] = t
        tpl = s.get("template") or "other"
        if s.get("stream"): stream_of[tpl][s["stream"]] += 1
        owner[s["id"]] = (tpl, s.get("variant"), t)
        send_times[s["id"]].append(t)
        b = s.get("batch_id")
        if b:
            send_times[b].append(t)
            prev = owner.get(b)
            if not prev or t < prev[2]: owner[b] = (tpl, s.get("variant"), t)
    for k in send_times: send_times[k].sort()

    def cohort(sid, fallback):
        o = owner.get(sid)
        if o: return o[0], o[1], o[2]
        return "other", None, uuid7_time(sid) or fallback

    stream_name = lambda tpl: (stream_of[tpl].most_common(1) or [["other"]])[0][0] if tpl != "other" else "other"
    zero = lambda cols=COLS: dict.fromkeys(cols, 0)
    table = collections.defaultdict(lambda: collections.defaultdict(zero))      # template -> week -> counts
    kpi = {"d7": zero(), "prev7": zero(), "d30": zero()}
    for k in kpi.values(): k["blocked"] = 0
    streams = collections.defaultdict(lambda: {"d7": zero(), "d30": zero()})
    boxes = collections.defaultdict(lambda: {"d7": zero(MBOX_COLS), "d30": zero(MBOX_COLS)})
    # one send = one batch (every recipient of one email, version and day): for the per-send alarm lines
    batch_of = {sid: s.get("batch_id") or sid for sid, s in all_sends.items()}
    batches = collections.defaultdict(lambda: {"t": None, "sent": 0, "bounces": 0, "complaints": 0, "unsubs": 0})

    def add(tpl, t, col, n=1, mbox=None, batch=None):
        if t is None: return
        w = week_of(t)
        if w in wset: table[tpl][w][col] += n
        wins = (["d7"] if t >= d7 else ["prev7"] if t >= d14 else []) + (["d30"] if t >= d30 else [])
        for k in wins:
            kpi[k][col] = kpi[k].get(col, 0) + n
            if k != "prev7":
                streams[stream_name(tpl)][k][col] += n
                if mbox in MBOX and col in MBOX_COLS: boxes[mbox][k][col] += n
        if batch and t >= d30 and col in batches[batch]: batches[batch][col] += n

    settled = now - datetime.timedelta(hours=DELIVERY_WAIT_H)
    deliv = {"sent": 0, "delivered": 0}   # emails sent 2 hours to 7 days ago, and the delivery reports for them
    for s in sends:
        if "_t" not in s: continue
        failed = s.get("status") == "failed"
        add(s.get("template") or "other", s["_t"], "failed" if failed else "sent", batch=batch_of.get(s.get("id")))
        if not failed and d7 <= s["_t"] <= settled: deliv["sent"] += 1
        b = batches[batch_of.get(s.get("id"))]
        if not failed and (b["t"] is None or s["_t"] < b["t"]): b["t"] = s["_t"]

    clicks, complaints_24h = [], 0
    for e in list(events) + list(old_clicks):
        t = parse_ts(e.get("created_at"))
        if not t: continue
        typ, m = e.get("type"), meta_of(e)
        if typ == "click":
            c = dict(e); c["t"] = t; clicks.append(c); continue
        sid = e.get("send_id")
        tpl, _, ct = cohort(sid, t) if sid else ("other", None, t)
        mb, bt = m.get("mbox"), batch_of.get(sid)
        if typ == "delivered":
            add(tpl, ct, "delivered", mbox=mb)
            if d7 <= ct <= settled: deliv["delivered"] += 1
        elif typ == "bounce":
            kind = m.get("kind")
            if kind == "suppressed":
                if ct >= d7: kpi["d7"]["blocked"] += 1
                elif ct >= d14: kpi["prev7"]["blocked"] += 1
                if ct >= d30: kpi["d30"]["blocked"] += 1
            else: add(tpl, ct, "soft" if kind == "soft" else "bounces", mbox=mb, batch=bt)
        elif typ == "complaint" and m.get("kind") != "suppressed":
            add(tpl, ct, "complaints", mbox=mb, batch=bt)
            if t >= now - datetime.timedelta(hours=24): complaints_24h += 1
        elif typ == "unsubscribe": add(tpl, ct, "unsubs", mbox=mb, batch=bt)

    score_clicks(clicks, send_times)
    links = collections.defaultdict(lambda: [0, 0, 0])
    exp_h = collections.Counter()
    bots = {"days": LINK_DAYS, "clicks": 0, "human": 0, "reasons": collections.Counter()}
    for c in clicks:
        tpl, variant, ct = cohort(c.get("send_id"), c["t"])
        human, agent = not c["bot"], (not c["bot"]) and to_agent(meta_of(c).get("dest"))
        add(tpl, ct, "clicks")
        if human: add(tpl, ct, "human")
        if agent: add(tpl, ct, "agent")
        if variant and human: exp_h[variant] += 1
        if c["t"] >= d30:
            row = links[(tpl, c.get("link") or "?")]
            row[0] += 1; row[1] += human; row[2] += agent
            bots["clicks"] += 1; bots["human"] += human
            bots["reasons"].update(c["why"] if c["bot"] else [])
    bots["reasons"] = dict(sorted(bots["reasons"].items(), key=lambda kv: -kv[1]))

    order = {t: i for i, t in enumerate(ORDER)}
    tpls = sorted(table, key=lambda t: (t == "other", order.get(t, 99), -sum(r["sent"] for r in table[t].values()), t))
    templates = [{"t": t, "stream": (stream_of[t].most_common(1) or [[None]])[0][0],
                  "w": [[table[t][w][c] for c in COLS] if w in table[t] else None for w in weeks]} for t in tpls]

    # A/B tests: every send with a version, all time (kept 25 months), and the human clicks on its links
    arms = collections.defaultdict(lambda: {"sends": 0, "batches": set(), "first": None, "last": None, "tpl": collections.Counter()})
    for s in all_sends.values():
        sv = split_variant(s.get("variant"))
        if not sv or s.get("status") == "failed" or "_t" not in s: continue
        a = arms[s["variant"]]
        a["sends"] += 1; a["batches"].add(s.get("batch_id") or s["id"]); a["tpl"][s.get("template") or "other"] += 1
        a["first"] = min(a["first"] or s["_t"], s["_t"]); a["last"] = max(a["last"] or s["_t"], s["_t"])
    by_exp = collections.defaultdict(dict)
    for v, a in arms.items():
        name, arm = split_variant(v)
        by_exp[name][arm] = a
    experiments = []
    for name in sorted(by_exp, key=lambda n: -max(a["last"].timestamp() for a in by_exp[n].values())):
        group = by_exp[name]
        ctrl = "a" if "a" in group else sorted(group)[0]
        tpl = sum((a["tpl"] for a in group.values()), collections.Counter()).most_common(1)[0][0]
        cn, ch = group[ctrl]["sends"], exp_h[name + ":" + ctrl]
        out = []
        for arm in sorted(group):
            a, h = group[arm], exp_h[name + ":" + arm]
            out.append({"arm": arm, "sends": a["sends"], "batches": len(a["batches"]), "human": h,
                        "rate": round(h / a["sends"], 4) if a["sends"] else 0,
                        "p": None if arm == ctrl else p_beats(ch, cn, h, a["sends"])})
        experiments.append({"name": name, "template": tpl, "control": ctrl, "arms": out,
                            "first": min(a["first"] for a in group.values()).date().isoformat(),
                            "last": max(a["last"] for a in group.values()).date().isoformat()})

    # warm-up: day 1 is the day of the first Plunk send
    today = now.date()
    sent_by_day = collections.Counter(s["_t"].date() for s in sends if "_t" in s and s.get("status") != "failed")
    day = max(0, (today - first_send.date()).days + 1) if first_send else 0
    warm = {"day": day, "cap": cap_for(ramp, max(day, 1)), "sent_today": sent_by_day.get(today, 0),
            "first": first_send.date().isoformat() if first_send else None, "source": ramp_source,
            "ramp": [list(r) for r in ramp], "days": []}
    if first_send:
        for k in range(min(day, 14) - 1, -1, -1):
            d = today - datetime.timedelta(days=k)
            warm["days"].append([d.isoformat(), sent_by_day.get(d, 0), cap_for(ramp, (d - first_send.date()).days + 1)])

    # the warning and stop lines (research report: "watch a few numbers"); None when there is nothing to judge yet
    pct = lambda a, b: a / b * 100 if b else None
    rnd = lambda v, nd=2: None if v is None else round(v, nd)
    def worst(col, since):   # the highest rate in one send of SEND_MIN or more emails, sent since then
        return max((v[col] / v["sent"] * 100 for v in batches.values() if v["t"] and v["t"] >= since and v["sent"] >= SEND_MIN), default=None)
    def level(*xs):
        xs = [x for x in xs if x is not None]
        return max(xs) if xs else None
    def state(v, warn, stop):
        if v is None: return None
        return "stop" if stop is not None and v >= stop else "warn" if warn is not None and v >= warn else "ok"
    k7, k30 = kpi["d7"], kpi["d30"]
    c_rate = pct(k30["complaints"], k30["sent"])
    c_worst = max((v["complaints"] for v in batches.values() if v["t"] and v["t"] >= d30), default=0)
    c_state = state(c_rate, *ALARM["complaints"])
    if c_state and complaints_24h >= COMPLAINTS_24H_STOP: c_state = "stop"
    elif c_state == "ok" and c_worst >= COMPLAINTS_SEND_WARN: c_state = "warn"
    b_rate, b_worst = pct(k7["bounces"], k7["sent"]), worst("bounces", d7)
    u_rate, u_worst = pct(k7["unsubs"], k7["sent"]), worst("unsubs", d7)
    share = pct(bots["clicks"] - bots["human"], bots["clicks"])
    d_rate = pct(deliv["delivered"], deliv["sent"]) if deliv["delivered"] else None   # no reports at all: the workflow is not set up
    alarms = {
        "delivered": {"state": None if d_rate is None else "stop" if d_rate < ALARM["delivered"][1] else "warn" if d_rate < ALARM["delivered"][0] else "ok",
                      "rate_7d": rnd(d_rate, 1), "warn": ALARM["delivered"][0], "stop": ALARM["delivered"][1]},
        "complaints": {"state": c_state, "rate_30d": rnd(c_rate, 3), "count_30d": k30["complaints"], "worst_send": c_worst, "last_24h": complaints_24h,
                       "warn": ALARM["complaints"][0], "stop": ALARM["complaints"][1]},
        "bounces": {"state": state(level(b_rate, b_worst), *ALARM["bounces"]), "rate_7d": rnd(b_rate), "worst_send": rnd(b_worst),
                    "warn": ALARM["bounces"][0], "stop": ALARM["bounces"][1]},
        "unsubs": {"state": state(level(u_rate, u_worst), *ALARM["unsubs"]), "rate_7d": rnd(u_rate), "worst_send": rnd(u_worst),
                   "warn": ALARM["unsubs"][0], "stop": ALARM["unsubs"][1]},
        "machine": {"state": state(share, *ALARM["machine"]) if bots["clicks"] >= CLICKS_MIN else None, "share_30d": rnd(share, 1),
                    "clicks_30d": bots["clicks"], "warn": ALARM["machine"][0], "stop": ALARM["machine"][1]},
    }
    s_order = {s: i for i, s in enumerate(STREAMS)}
    stream_rows = [{"s": s, "d7": [v["d7"][c] for c in COLS], "d30": [v["d30"][c] for c in COLS]}
                   for s, v in sorted(streams.items(), key=lambda kv: (s_order.get(kv[0], 98), kv[0]))]
    box_rows = [{"m": g, "d7": [boxes[g]["d7"][c] for c in MBOX_COLS], "d30": [boxes[g]["d30"][c] for c in MBOX_COLS]} for g in MBOX if g in boxes]

    firsts = [s["_t"] for s in all_sends.values() if "_t" in s]
    return {"ready": True, "since": min(firsts).date().isoformat() if firsts else None, "weeks": weeks, "cols": COLS,
            "kpi": kpi, "alarms": alarms, "streams": stream_rows, "mcols": MBOX_COLS, "mailbox": box_rows, "templates": templates,
            "links": [[t, l, v[0], v[1], v[2]] for (t, l), v in sorted(links.items(), key=lambda kv: (-kv[1][1], -kv[1][0], kv[0]))][:40],
            "experiments": experiments, "warmup": warm, "health": health or {}, "bots": bots,
            "rules": {"fast_s": FAST_S, "quick_s": QUICK_S, "burst_s": BURST_S, "bot_at": BOT_AT, "draws": DRAWS}}


# ------------------------------------------------------------------ Supabase
def _req(path, method="GET", headers=None):
    key = os.environ["SUPABASE_SERVICE_KEY"]
    h = {"apikey": key, "Authorization": "Bearer " + key}
    h.update(headers or {})
    return urllib.request.Request("%s/rest/v1/%s" % (SUPA, path), method=method, headers=h)


def fetch_all(path):
    rows, start = [], 0
    while True:
        req = _req(path, headers={"Range-Unit": "items", "Range": "%d-%d" % (start, start + PAGE - 1)})
        chunk = json.load(urllib.request.urlopen(req, timeout=60))
        rows += chunk
        if len(chunk) < PAGE: return rows
        start += PAGE


def count(path):
    """Rows matching a PostgREST filter, from the Content-Range header (no rows downloaded); None when it fails."""
    try:
        r = urllib.request.urlopen(_req(path, method="HEAD", headers={"Prefer": "count=exact"}), timeout=60)
        n = (r.headers.get("Content-Range") or "").rsplit("/", 1)[-1]
        return int(n) if n.isdigit() else None
    except Exception as e:
        print("count failed:", path.split("?")[0], str(e)[:60]); return None


def health_counts(now):
    t, d30 = iso(now), iso(now - datetime.timedelta(days=30))
    return {"members": count("profiles?select=id"),
            "opted_in": count("profiles?select=id&marketing_opt_in=is.true"),
            "alerts_only": count("profiles?select=id&marketing_opt_in=is.true&email_freq=eq.alerts"),
            "paused": count("profiles?select=id&marketing_opt_in=is.true&email_paused_until=gt." + t),
            "sunset": count("profiles?select=id&marketing_opt_in=is.true&email_sunset_at=not.is.null"),
            "suppressed": count("email_suppression?select=email"),
            "unsubscribed_30d": count("profiles?select=id&unsubscribed_at=gte." + d30)}


def write(out, path=OUT):
    """Writes the file unless only "generated" changed (no commit churn). Returns whether it wrote."""
    new = json.dumps(out, separators=(",", ":"), ensure_ascii=False)
    try: old = open(path, encoding="utf-8").read()
    except Exception: old = ""
    strip = lambda s: re.sub(r'"generated":"[^"]*",?', "", s)
    if strip(old) == strip(new):
        print("email stats unchanged"); return False
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f: f.write(new)
    return True


SEND_COLS = "id,batch_id,template,stream,variant,status,provider,created_at"
EVENT_COLS = "send_id,type,link,ua,asn,meta,created_at"


def main(path=OUT):
    if not os.environ.get("SUPABASE_SERVICE_KEY"):
        print("email stats: SUPABASE_SERVICE_KEY is not set, nothing written"); return 0
    now = datetime.datetime.now(datetime.timezone.utc)
    since = iso(now - datetime.timedelta(days=WINDOW_DAYS))
    head = {"generated": now.replace(microsecond=0).isoformat()}
    try:
        sends = fetch_all("email_sends?select=%s&created_at=gte.%s&order=created_at.asc" % (SEND_COLS, since))
    except Exception as e:
        # the tables are not there yet (scripts/email_v2.sql not run): /stats shows "starts counting once set up"
        print("email stats: email_sends not readable (%s), writing the empty state" % str(e)[:80])
        write({**head, "ready": False, "health": health_counts(now)}, path); return 0
    events = fetch_all("email_events?select=%s&created_at=gte.%s&order=id.asc" % (EVENT_COLS, since))
    exp_sends = fetch_all("email_sends?select=%s&variant=not.is.null&order=created_at.asc" % SEND_COLS)
    oldest = min([t for t in (parse_ts(s.get("created_at")) for s in exp_sends) if t] or [None], key=lambda t: t or now)
    old_clicks = []
    if oldest and iso(oldest) < since:   # A/B tests older than the window: their clicks from before it as well
        old_clicks = fetch_all("email_events?select=%s&type=eq.click&created_at=gte.%s&created_at=lt.%s&order=id.asc" % (EVENT_COLS, iso(oldest), since))
    first = (fetch_all("email_sends?select=created_at&provider=eq.plunk&status=neq.failed&order=created_at.asc&limit=1")
             or fetch_all("email_sends?select=created_at&status=neq.failed&order=created_at.asc&limit=1"))   # no provider written
    first_send = parse_ts(first[0]["created_at"]) if first else None
    ramp = ramp_from_mailer()
    out = {**head, **build(sends, events, now, exp_sends, old_clicks, health_counts(now), first_send,
                           ramp or RAMP_PLAN, "mailer.py" if ramp else "plan")}
    wrote = write(out, path)
    k = out["kpi"]["d7"]
    print("email stats %s: %d sends and %d events read; last 7 days %d sent, %d human of %d clicks; %d A/B tests; warm-up day %d"
          % ("written" if wrote else "unchanged", len(sends), len(events), k["sent"], k["human"], k["clicks"], len(out["experiments"]), out["warmup"]["day"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
