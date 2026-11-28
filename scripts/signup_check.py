# -*- coding: utf-8 -*-
"""Are the new sign-ups real people? (owner, 28 Nov 2026: "I'm getting a lot of sign-ups every day, any chance there are
bots?"). Totals only, printed to the workflow log (this repository is public, so its logs are too): no address, no id,
nothing per person. Per sign-up day for the last 21 days: sign-ups, how they signed up (Google or email link), how many
email sign-ups clicked their link, how many ever signed in, came back on a later day, viewed a find or saved one; then
the busiest 10 minutes, look-alike addresses (random letters and digits), throwaway mail domains, and the mail domains
that 5 or more members share.

  python scripts/signup_check.py        needs SUPABASE_SERVICE_KEY (.github/workflows/signup-check.yml)
"""
import collections, json, os, re, sys, urllib.request
from datetime import datetime, timedelta, timezone

URL = "https://uptpghuduqjqmrxwatbm.supabase.co"
KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
H = {"apikey": KEY, "Authorization": "Bearer " + KEY, "Accept": "application/json"}
THROWAWAY = {"mailinator.com", "guerrillamail.com", "10minutemail.com", "tempmail.com", "temp-mail.org", "yopmail.com", "sharklasers.com",
             "trashmail.com", "getnada.com", "dispostable.com", "maildrop.cc", "mohmal.com", "emailondeck.com", "fakeinbox.com", "tempmailo.com",
             "throwawaymail.com", "mintemail.com", "spamgourmet.com", "mailnesia.com", "burnermail.io", "tmpmail.org", "moakt.com", "1secmail.com",
             "tempr.email", "discard.email", "inboxkitten.com", "minuteinbox.com", "emailfake.com", "mail.tm", "mail.gw", "cuvox.de", "armyspy.com",
             "dayrep.com", "einrot.com", "fleckens.hu", "gustr.com", "jourrapide.com", "rhyta.com", "superrito.com", "teleworm.us"}


def get(path, extra=None):
    req = urllib.request.Request(URL + path, headers=dict(H, **(extra or {})))
    with urllib.request.urlopen(req, timeout=60) as r: return json.loads(r.read()), r.headers


def users():
    out, page = [], 1
    while True:
        j, hd = get("/auth/v1/admin/users?page=%d&per_page=1000" % page)
        us = j.get("users") if isinstance(j, dict) else j
        if not us: return out
        out += us; page += 1
        if page > 100: return out


def column(table, col, extra=""):
    """Every value of one column (PostgREST pages of 1000)."""
    out, off = [], 0
    while True:
        rows, _ = get("/rest/v1/%s?select=%s%s" % (table, col, extra), {"Range-Unit": "items", "Range": "%d-%d" % (off, off + 999)})
        out += [r.get(col) for r in rows]
        if len(rows) < 1000: return out
        off += 1000


def ts(s):
    try: return datetime.fromisoformat(str(s).replace("Z", "+00:00")) if s else None
    except ValueError: return None


def looks_random(local):
    """An address part like 'xk3q9vd2mz' or 'user84731923': no vowels run, or a long digit tail."""
    l = re.sub(r"[._+-]", "", local.lower())
    return len(l) >= 8 and (not re.search(r"[aeiouy]{1}[a-z]*[aeiouy]", l) or bool(re.search(r"\d{6,}$", l)))


def main():
    if not KEY: sys.exit("SUPABASE_SERVICE_KEY is not set")
    us = users()
    now = datetime.now(timezone.utc); since = now - timedelta(days=21)
    favs = collections.Counter(column("favorites", "user_id"))
    views = collections.Counter(column("product_views", "user_id", "&user_id=not.is.null&created_at=gte." + since.strftime("%Y-%m-%dT%H:%M:%SZ")))
    print("members in all: %d; with a saved find: %d; viewed a find in the last 21 days while signed in: %d" % (len(us), len(favs), len(views)))
    day = collections.defaultdict(collections.Counter)
    times, domains, rnd, throw = [], collections.Counter(), 0, 0
    for u in us:
        c = ts(u.get("created_at"))
        if not c: continue
        email = (u.get("email") or "").lower(); local, _, dom = email.partition("@")
        domains[dom] += 1
        if c < since: continue
        times.append(c)
        d = day[c.date().isoformat()]
        d["signups"] += 1
        prov = ((u.get("app_metadata") or {}).get("provider") or "email")
        d["google" if prov == "google" else "email link" if prov == "email" else prov] += 1
        if prov == "email" and (u.get("email_confirmed_at") or u.get("confirmed_at")): d["clicked link"] += 1
        last = ts(u.get("last_sign_in_at"))
        if last: d["signed in"] += 1
        if last and (last - c) > timedelta(hours=20): d["came back later"] += 1
        if views.get(u.get("id")): d["viewed a find"] += 1
        if favs.get(u.get("id")): d["saved a find"] += 1
        if looks_random(local): d["random-looking address"] += 1; rnd += 1
        if dom in THROWAWAY: d["throwaway domain"] += 1; throw += 1
    cols = ["signups", "google", "email link", "clicked link", "signed in", "came back later", "viewed a find", "saved a find", "random-looking address", "throwaway domain"]
    print("\nPer sign-up day (last 21 days):")
    print("day         " + " | ".join(cols))
    for k in sorted(day):
        print(k + "  " + " | ".join("%d" % day[k][c] for c in cols))
    tot = collections.Counter()
    for v in day.values(): tot.update(v)
    print("total       " + " | ".join("%d" % tot[c] for c in cols))
    times.sort(); best = 0
    for i, t in enumerate(times):
        j = i
        while j < len(times) and times[j] - t <= timedelta(minutes=10): j += 1
        best = max(best, j - i)
    print("\nbusiest 10 minutes: %d sign-ups" % best)
    print("random-looking addresses: %d, throwaway mail domains: %d (of %d sign-ups in 21 days)" % (rnd, throw, len(times)))
    print("mail domains shared by 5 or more members:", ", ".join("%s %d" % kv for kv in domains.most_common() if kv[1] >= 5))


if __name__ == "__main__":
    main()
