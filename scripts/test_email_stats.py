"""Tests for scripts/email_stats.py on fake data (no network). Run: python scripts/test_email_stats.py"""
import datetime, json, os, re, sys, tempfile, uuid
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import email_stats as E

NOW = datetime.datetime(2026, 12, 10, 18, 0, tzinfo=datetime.timezone.utc)   # a Thursday
UTC = datetime.timezone.utc


def u7(t, n=0):
    """A UUIDv7 for time t (as mailer.py makes them); n keeps ids of the same moment apart."""
    ms = int(t.timestamp() * 1000)
    h = "%012x" % ms + "7" + "%03x" % (n % 4096) + "8" + "%015x" % n
    return str(uuid.UUID(h))


def at(days=0, hours=0, seconds=0):
    return NOW - datetime.timedelta(days=days, hours=hours, seconds=seconds)


def ts(t): return t.isoformat()


# ------------------------------------------------------------------ the Bayesian probability
assert E.p_beats(25, 500, 40, 500) == E.p_beats(25, 500, 40, 500), "fixed seed: the same number every run"
assert abs(E.p_beats(25, 500, 40, 500) - 0.97) < 0.01          # research note table: 0.97
assert abs(E.p_beats(25, 500, 35, 500) - 0.91) < 0.015         # 0.91
assert abs(E.p_beats(10, 100, 10, 100) - 0.5) < 0.02
assert E.p_beats(40, 500, 25, 500) < 0.05
assert 0 <= E.p_beats(5, 3, 1, 1) <= 1, "more clicks than sends is capped"

# ------------------------------------------------------------------ the ramp
PLAN = E.RAMP_PLAN
assert [E.cap_for(PLAN, d) for d in (1, 3, 4, 7, 8, 14, 15, 21, 22, 28, 29, 400)] == [150, 150, 250, 250, 400, 400, 700, 700, 1200, 1200, 2500, 2500]
assert E.norm_ramp([(3, 150), (7, 250), (14, 400), (21, 700), (28, 1200), (None, 2500)]) == PLAN
assert E.norm_ramp({3: 150, 7: 250, 14: 400, 21: 700, 28: 1200, None: 2500}) == PLAN
assert E.norm_ramp([(1, 150), (4, 250), (8, 400), (15, 700), (22, 1200), (29, 2500)]) == PLAN
assert E.norm_ramp([(0, 150), (3, 250), (7, 400), (14, 700), (21, 1200), (28, 2500)]) == PLAN
assert E.norm_ramp([(3, 150), (7, 250), (14, 400), (21, 700), (28, 1200)])[-1] == (29, None, 1200)
assert E.norm_ramp([(1, 3, 150), (4, None, 250)]) == [(1, 3, 150), (4, None, 250)]
assert E.norm_ramp("nonsense") is None and E.norm_ramp([(3, -1)]) is None and E.norm_ramp([]) is None
with tempfile.TemporaryDirectory() as d:
    p = os.path.join(d, "mailer.py")
    open(p, "w").write("import sys\nraise SystemExit('must never run')\nRAMP = [(3, 100), (None, 900)]\n")
    assert E.ramp_from_mailer(p) == [(1, 3, 100), (4, None, 900)], "read, not run"
    open(p, "w").write("def cap(d): return 5\n")
    assert E.ramp_from_mailer(p) is None
    assert E.ramp_from_mailer(os.path.join(d, "missing.py")) is None

# ------------------------------------------------------------------ bot rules
BROWSER = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1"
assert E.BOT.search("Mozilla/5.0 (compatible; bingbot/2.0)") and not E.BOT.search("Mozilla/5.0 (Linux; Android 10; CUBOT X30) AppleWebKit/537.36")
assert E.BOT.pattern == E.load_bot().pattern and E.load_bot("/no/such/file").pattern == E.BOT_FALLBACK
B = u7(at(days=1), 1)
times = {B: [at(days=1)]}
def click(sec, ua=BROWSER, asn=2119, net="n1", purpose=None, age=None):
    return {"t": at(days=1) + datetime.timedelta(seconds=sec), "send_id": B, "ua": ua, "asn": asn,
            "meta": {"net": net, "purpose": purpose, "age_ms": age}}
cases = [
    (click(3600), False, []),
    (click(3600, ua="python-requests/2.31"), True, ["ua"]),
    (click(3600, ua="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 HeadlessChrome/120"), True, ["ua"]),
    (click(3600, purpose="prefetch;anonymous-client-ip"), True, ["prefetch"]),
    (click(2), True, ["fast"]),
    (click(12), False, ["quick"]),
    (click(12, asn=8075), True, ["quick", "cloud"]),
    (click(4000, asn=8075), False, ["cloud"]),
    (click(4000, asn=26211), True, ["scanner"]),
]
for i, (c, _, _) in enumerate(cases): c["meta"]["net"] = "n%d" % i      # one network each: no bursts here
got = E.score_clicks([c for c, _, _ in cases], times)
for (c, bot, why), g in zip(cases, got):
    assert (g["bot"], g["why"]) == (bot, why), (g["bot"], g["why"], bot, why)
burst = E.score_clicks([click(5000, net="x"), click(5001, net="x"), click(5003.5, net="x"), click(5001, net="y")], times)
assert [c["bot"] for c in burst] == [True, True, False, False], "two clicks from one network within 2 s, on one email"
# without the batch's send times (a click older than the window): the age the tracker stored
assert E.score_clicks([{**click(9999, net="z"), "send_id": "other", "meta": {"age_ms": 1500}}], {})[0]["why"] == ["fast"]
assert E.to_agent("www.puroclassico.com/go/mycnbox") and E.to_agent("mycnbox.com/login/main-login") and E.to_agent("www.kakobuy.com/item")
assert not E.to_agent("www.puroclassico.com/product/123") and not E.to_agent("evil.com/go/x")

# ------------------------------------------------------------------ the whole bake on fake data
W0A, W0B, PICKS, OLD = u7(at(days=2), 10), u7(at(days=2), 11), u7(at(days=0, hours=2), 12), u7(at(days=9), 13)
sends, n = [], 0
def send(batch, tpl, t, variant=None, status="sent", stream="newsletter"):
    global n; n += 1
    sid = u7(t, 100 + n)
    sends.append({"id": sid, "batch_id": batch, "template": tpl, "stream": stream, "variant": variant, "status": status, "provider": "plunk", "created_at": ts(t)})
    return sid
for i in range(40): send(W0A, "w0", at(days=2) + datetime.timedelta(seconds=i), "w0-row:a", stream="onboarding")
for i in range(40): send(W0B, "w0", at(days=2) + datetime.timedelta(seconds=i), "w0-row:b", stream="onboarding")
for i in range(100): send(PICKS, "picks", at(days=0, hours=2) + datetime.timedelta(seconds=i))
send(PICKS, "picks", at(days=0, hours=2), status="failed")
old_ids = [send(OLD, "picks", at(days=9) + datetime.timedelta(seconds=i)) for i in range(50)]
first_picks = [s["id"] for s in sends if s["batch_id"] == PICKS and s["status"] == "sent"][:3]

events = []
def ev(typ, sid, t, link=None, ua=BROWSER, asn=2119, **meta):
    events.append({"send_id": sid, "type": typ, "link": link, "ua": ua, "asn": asn, "meta": meta, "created_at": ts(t)})
ev("delivered", first_picks[0], at(hours=1), mbox="gmail"); ev("delivered", first_picks[1], at(hours=1), mbox="gmail")
ev("bounce", first_picks[2], at(hours=1), kind="hard", mbox="outlook"); ev("bounce", first_picks[1], at(hours=1), kind="soft", mbox="gmail")
ev("bounce", first_picks[0], at(hours=1), kind="suppressed")
ev("complaint", old_ids[0], at(days=3))                            # an email of the week before: prev7
ev("unsubscribe", first_picks[0], at(hours=1), source="header", template="picks", mbox="icloud")
ev("unsubscribe", None, at(hours=5), source="link")                 # an old email, no send on record: "other"
for i in range(6): ev("click", W0B, at(days=1, hours=i), "card-%d" % (i % 2 + 1), dest="www.puroclassico.com/product/1", net="h%d" % i)
for i in range(2): ev("click", W0A, at(days=1, hours=i), "coupon", dest="www.puroclassico.com/go/mycnbox", net="a%d" % i)
ev("click", PICKS, at(hours=1), "card-1", dest="www.puroclassico.com/product/2", net="p1")
ev("click", PICKS, at(hours=1, seconds=-1), "card-1", dest="mycnbox.com/goodsDetail", net="p2")
ev("click", PICKS, at(days=0, hours=2) + datetime.timedelta(seconds=2), "card-2", dest="www.puroclassico.com/product/3", net="p3")   # 2 s after its send: a scanner
ev("click", PICKS, at(seconds=30), "browse", ua="Mozilla/5.0 (compatible; Googlebot/2.1)", dest="www.puroclassico.com/", net="p4")
health = {"members": 900, "opted_in": 600, "alerts_only": 40, "paused": 5, "sunset": 30, "suppressed": 3, "unsubscribed_30d": 7}
out = E.build(sends, events, NOW, [s for s in sends if s["variant"]], [], health, at(days=9), E.RAMP_PLAN, "plan")

k7, kp = out["kpi"]["d7"], out["kpi"]["prev7"]
assert (k7["sent"], k7["failed"], k7["delivered"], k7["bounces"], k7["soft"], k7["blocked"]) == (180, 1, 2, 1, 1, 1), k7
assert (k7["complaints"], k7["unsubs"], k7["clicks"], k7["human"], k7["agent"]) == (0, 2, 12, 10, 3), k7
assert (kp["sent"], kp["complaints"]) == (50, 1), kp
assert out["weeks"][-1] == "2026-W50" and len(out["weeks"]) == E.WEEKS
rows = {t["t"]: t for t in out["templates"]}
assert list(rows) == ["w0", "picks", "other"], list(rows)
picks_w50 = dict(zip(out["cols"], rows["picks"]["w"][-1]))
assert (picks_w50["sent"], picks_w50["failed"], picks_w50["human"], picks_w50["agent"], picks_w50["bounces"]) == (100, 1, 2, 1, 1), picks_w50
assert rows["picks"]["w"][-2] is not None and dict(zip(out["cols"], rows["picks"]["w"][-2]))["complaints"] == 1
assert rows["w0"]["stream"] == "onboarding" and dict(zip(out["cols"], rows["other"]["w"][-1]))["unsubs"] == 1
links = {(l[0], l[1]): l[2:] for l in out["links"]}
assert links[("w0", "card-1")] == [3, 3, 0] and links[("w0", "coupon")] == [2, 2, 2] and links[("picks", "card-2")] == [1, 0, 0]
(x,) = out["experiments"]
assert (x["name"], x["template"], x["control"]) == ("w0-row", "w0", "a")
a, b = x["arms"]
assert (a["arm"], a["sends"], a["human"], a["p"], a["batches"]) == ("a", 40, 2, None, 1)
assert (b["arm"], b["sends"], b["human"], b["rate"]) == ("b", 40, 6, 0.15) and 0.9 < b["p"] < 1
w = out["warmup"]
assert (w["day"], w["cap"], w["sent_today"], w["first"]) == (10, 400, 100, "2026-12-01"), w
assert w["days"][-1] == ["2026-12-10", 100, 400] and len(w["days"]) == 10 and w["days"][0] == ["2026-12-01", 50, 150]
assert out["bots"]["clicks"] == 12 and out["bots"]["human"] == 10 and out["bots"]["reasons"] == {"ua": 1, "fast": 1}
assert out["health"] == health and out["since"] == "2026-12-01"
# 30 days, streams and mailbox groups
k30 = out["kpi"]["d30"]
assert (k30["sent"], k30["complaints"], k30["unsubs"], k30["human"]) == (230, 1, 2, 10), k30
st = {r["s"]: dict(zip(out["cols"], r["d7"])) for r in out["streams"]}
assert list(st) == ["onboarding", "newsletter", "other"], list(st)
assert (st["onboarding"]["sent"], st["onboarding"]["human"], st["newsletter"]["sent"], st["newsletter"]["bounces"], st["other"]["unsubs"]) == (80, 8, 100, 1, 1), st
assert dict(zip(out["cols"], [r for r in out["streams"] if r["s"] == "newsletter"][0]["d30"]))["sent"] == 150
mb = {r["m"]: dict(zip(out["mcols"], r["d7"])) for r in out["mailbox"]}
assert list(mb) == ["gmail", "outlook", "icloud"], list(mb)
assert (mb["gmail"]["delivered"], mb["gmail"]["soft"], mb["outlook"]["bounces"], mb["icloud"]["unsubs"]) == (2, 1, 1, 1), mb
assert "clicks" not in out["mcols"], "clicks carry no address, so no mailbox group"
# the warning and stop lines
al = out["alarms"]
assert al["complaints"]["state"] == "stop" and al["complaints"]["rate_30d"] == round(100 / 230, 3) and al["complaints"]["worst_send"] == 1, al["complaints"]
assert al["bounces"]["state"] == "warn" and al["bounces"]["worst_send"] == 1.0 and al["bounces"]["rate_7d"] == round(100 / 180, 2), al["bounces"]
assert al["unsubs"]["state"] == "stop" and al["unsubs"]["worst_send"] == 1.0, al["unsubs"]
assert al["machine"]["state"] is None and al["machine"]["clicks_30d"] == 12, "too few clicks to judge"
def delivered_state(n_delivered, n=100, hours=5):
    t0 = at(hours=hours)
    ss = [{"id": u7(t0, 7000 + i), "batch_id": "D", "template": "picks", "stream": "newsletter", "variant": None, "status": "sent",
           "provider": "plunk", "created_at": ts(t0 + datetime.timedelta(seconds=i))} for i in range(n)]
    evs = [{"send_id": ss[i]["id"], "type": "delivered", "meta": {"mbox": "gmail"}, "created_at": ts(t0 + datetime.timedelta(seconds=i + 3))} for i in range(n_delivered)]
    return E.build(ss, evs, NOW)["alarms"]["delivered"]["state"]
assert [delivered_state(k) for k in (100, 98, 97, 95, 94, 0)] == ["ok", "ok", "warn", "warn", "stop", None]
assert delivered_state(50, hours=1) is None, "emails younger than 2 hours wait for their reports"

# no sends at all yet
empty = E.build([], [], NOW, health={"opted_in": 5})
assert all(v["state"] is None for v in empty["alarms"].values()), empty["alarms"]
assert empty["streams"] == [] and empty["mailbox"] == []
# the state rules on their own: 3 complaints in a day stop sending; 2 in one send warn; a big machine share
def one(n_sent, complaints=0, clicks=0, bots=0, at_day=1, batch_size=None):
    t0 = at(days=at_day)
    ss = [{"id": u7(t0, 5000 + i), "batch_id": "B%d" % (i // (batch_size or n_sent)), "template": "picks", "stream": "newsletter",
           "variant": None, "status": "sent", "provider": "plunk", "created_at": ts(t0 + datetime.timedelta(seconds=i))} for i in range(n_sent)]
    evs = [{"send_id": ss[i]["id"], "type": "complaint", "meta": {}, "created_at": ts(at(hours=2))} for i in range(complaints)]
    evs += [{"send_id": "B0", "type": "click", "link": "card-1", "ua": "curl/8" if i < bots else BROWSER, "asn": 2119,
             "meta": {"net": "x%d" % i, "dest": "www.puroclassico.com/"}, "created_at": ts(t0 + datetime.timedelta(hours=3, minutes=i))} for i in range(clicks)]
    return E.build(ss, evs, NOW)["alarms"]
assert one(5000)["complaints"]["state"] == "ok"
assert one(5000, complaints=2)["complaints"]["state"] == "warn", "2 in one send"
assert one(5000, complaints=2, batch_size=2500)["complaints"]["state"] == "warn"
assert one(5000, complaints=3)["complaints"]["state"] == "stop", "3 in 24 hours: Plunk's new-project line"
assert one(2500, complaints=1)["complaints"]["state"] == "ok"      # 0.04% over 30 days
assert one(2000, complaints=1)["complaints"]["state"] == "warn"    # 0.05%: the warning line
assert one(900, complaints=1)["complaints"]["state"] == "stop"     # 0.11%: one complaint on a small list is already the stop line
assert one(1000, clicks=40, bots=10)["machine"]["state"] == "ok"
assert one(1000, clicks=40, bots=15)["machine"]["state"] == "warn"
assert one(1000, clicks=40, bots=20)["machine"]["state"] == "stop"
assert empty["ready"] and empty["since"] is None and empty["templates"] == [] and empty["warmup"]["day"] == 0 and empty["warmup"]["cap"] == 150

# ------------------------------------------------------------------ main(): fake Supabase, public output
TABLES = {"email_sends": sends, "email_events": events}
def fake_fetch(path):
    table, _, query = path.partition("?")
    rows = list(TABLES[table])
    for part in query.split("&"):
        k, _, v = part.partition("=")
        if k in ("select", "order", "limit"): continue
        op, _, val = v.partition(".")
        if op == "gte": rows = [r for r in rows if r[k] >= val.replace("Z", "+00:00")]
        elif op == "lt": rows = [r for r in rows if r[k] < val.replace("Z", "+00:00")]
        elif op == "eq": rows = [r for r in rows if str(r.get(k)) == val]
        elif op == "neq": rows = [r for r in rows if str(r.get(k)) != val]
        elif v == "not.is.null": rows = [r for r in rows if r.get(k) is not None]
    if "order=created_at.asc" in query: rows.sort(key=lambda r: r["created_at"])
    return rows[:1] if "limit=1" in query else rows
E.fetch_all, E.count = fake_fetch, lambda path: 7
saved_key = os.environ.get("SUPABASE_SERVICE_KEY")
os.environ["SUPABASE_SERVICE_KEY"] = "test"
with tempfile.TemporaryDirectory() as d:
    p = os.path.join(d, "data", "email_stats.json")
    assert E.main(p) == 0
    text = open(p, encoding="utf-8").read()
    data = json.loads(text)
    assert data["ready"] and data["generated"] and data["health"]["opted_in"] == 7
    assert not re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-", text), "no ids in the public file"
    assert "@" not in text, "no addresses in the public file"
    assert not E.write(dict(data, generated="2030-01-01T00:00:00+00:00"), p), "only the time changed: not written again"
    # the tables are not there yet: the empty state, with whatever counts work
    def broken(path): raise OSError("404 relation does not exist")
    E.fetch_all = broken
    assert E.main(p) == 0
    assert json.load(open(p)) | {"generated": None} == {"generated": None, "ready": False, "health": {k: 7 for k in health}}
del os.environ["SUPABASE_SERVICE_KEY"]
assert E.main("/nonexistent/x.json") == 0, "no key: nothing written, no failure"
if saved_key is not None: os.environ["SUPABASE_SERVICE_KEY"] = saved_key
print("email stats: all tests passed")
