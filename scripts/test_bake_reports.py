#!/usr/bin/env python3
"""Tests for the report rule in scripts/bake_reports.py (no network). Run: python3 scripts/test_bake_reports.py"""
import datetime, os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bake_reports as B

NOW = datetime.datetime(2026, 11, 5, 12, 0, tzinfo=datetime.timezone.utc)
ISO = lambda d: d.strftime("%Y-%m-%dT%H:%M:%S+00:00")
_n = [0]


def rep(pid="p1", member=True, age_h=24 * 30, verified=True, ip=None, net=None, tok=None, reason="dead", ago_h=1, uid=None):
    """One product_reports row. Every call is a new person on a new IP and network unless ip/net/uid/tok say otherwise."""
    _n[0] += 1
    n = _n[0]
    at = NOW - datetime.timedelta(hours=ago_h)
    return {"product_id": pid, "reason": reason,
            "user_id": (uid or "00000000-0000-0000-0000-%012d" % n) if member else None,
            "account_created": ISO(at - datetime.timedelta(hours=age_h)) if member else None,
            "verified": verified if member else False,
            "ip_hash": ip or "ip%d" % n, "net_hash": net or "net%d" % n, "tok_hash": tok or "tok%d" % n, "created_at": ISO(at)}


def run(rows, views=None, overrides=None, prev=None):
    return B.decide(rows, views or {}, overrides or {}, prev or {}, NOW)


class Abuse(unittest.TestCase):
    def test_one_person_spamming(self):
        # the same member 50 times (the API stores one, but the rule must not care), then 20 fresh browsers on the same IP
        rows = [rep(uid="u-spammer", ip="ipA", net="netA") for _ in range(50)]
        rows += [rep(member=False, ip="ipA", net="netA") for _ in range(20)]
        out = run(rows)
        self.assertEqual(out["hidden"], [])
        w = out["watch"][0]
        self.assertEqual((w["people"], w["nets"], w["score"]), (1, 1, 1.0))

    def test_many_accounts_one_ip(self):
        rows = [rep(ip="ipX", net="netX") for _ in range(25)]          # 25 real-looking members behind one IP
        out = run(rows)
        self.assertEqual(out["hidden"], [])
        self.assertEqual(out["watch"][0]["people"], 1)

    def test_many_ips_one_network(self):
        rows = [rep(net="net24") for _ in range(25)]                   # 25 members, 25 IPs, one /24
        out = run(rows)
        self.assertEqual(out["hidden"], [])
        self.assertEqual(out["watch"][0]["score"], B.NET_CAP)
        self.assertEqual(out["watch"][0]["nets"], 1)

    def test_new_accounts_count_zero(self):
        rows = [rep(age_h=0.2) for _ in range(12)]                    # 12 accounts made minutes before reporting
        out = run(rows)
        self.assertEqual(out["hidden"], [])
        self.assertEqual(out["watch"], [])                             # score 0: not even watched

    def test_guests_alone_cannot_remove(self):
        rows = [rep(member=False) for _ in range(60)]                 # a proxy farm: 60 guests, 60 IPs, 60 networks
        out = run(rows)
        self.assertEqual(out["hidden"], [])
        self.assertEqual(out["watch"][0]["score"], B.ANON_CAP)

    def test_unconfirmed_accounts_count_as_guests(self):
        rows = [rep(verified=False) for _ in range(30)]
        self.assertEqual(run(rows)["hidden"], [])

    def test_popular_item_three_throwaways(self):
        views = {"hot": 1500}
        fresh = [rep("hot", age_h=0.5) for _ in range(3)]              # made just before the attack
        self.assertEqual(run(fresh, views)["hidden"], [])
        day_old = [rep("hot", age_h=3) for _ in range(3)]              # made a few hours before
        self.assertEqual(run(day_old, views)["hidden"], [])
        aged = [rep("hot") for _ in range(3)] + [rep("hot", member=False) for _ in range(5)]   # even old accounts + guests
        out = run(aged, views)
        self.assertEqual(out["hidden"], [])
        self.assertGreater(out["watch"][0]["need"], out["watch"][0]["score"])

    def test_three_throwaways_on_a_quiet_item(self):
        self.assertEqual(run([rep("quiet", age_h=2) for _ in range(3)])["hidden"], [])

    def test_two_people_never_enough(self):
        rows = [rep(ip="ip1", net="n1"), rep(ip="ip2", net="n2")] + [rep(member=False, ip="ip1", net="n1") for _ in range(9)]
        self.assertEqual(run(rows)["hidden"], [])


class RealReports(unittest.TestCase):
    def test_dead_link_four_members(self):
        rows = [rep("dead1", reason="dead") for _ in range(4)]
        out = run(rows, {"dead1": 40})
        self.assertEqual(out["hidden"], ["dead1"])
        it = out["items"][0]
        self.assertEqual((it["people"], it["nets"], it["reasons"]), (4, 4, {"dead": 4}))
        self.assertEqual(it["by"], "reports")
        self.assertEqual(it["since"], "2026-11-05")

    def test_dead_link_three_members_and_guests(self):
        rows = [rep("d2") for _ in range(2)] + [rep("d2", member=False) for _ in range(4)]
        self.assertEqual(run(rows)["hidden"], ["d2"])                  # 2 + 1.2 = 3.2 >= 3

    def test_popular_item_really_dead(self):
        rows = [rep("hot2") for _ in range(8)] + [rep("hot2", member=False) for _ in range(6)]
        out = run(rows, {"hot2": 1500})                               # needs 7.0; 8 members (one /24 each) + guests
        self.assertEqual(out["hidden"], ["hot2"])

    def test_threshold_scales_with_views(self):
        self.assertEqual(B.threshold(0), 3.0)
        self.assertEqual(B.threshold(100), 4.0)
        self.assertEqual(B.threshold(700), 6.0)
        self.assertEqual(B.threshold(10 ** 7), B.MAX_NEED)

    def test_old_reports_fall_out_of_the_window(self):
        rows = [rep("old", ago_h=24 * 31) for _ in range(5)]
        self.assertEqual(run(rows)["hidden"], [])


class OwnerAndBrakes(unittest.TestCase):
    def test_sticky_until_keep(self):
        first = run([rep("s1") for _ in range(4)])
        self.assertEqual(first["hidden"], ["s1"])
        later = run([], prev=first)                                     # the reports aged out: still removed
        self.assertEqual(later["hidden"], ["s1"])
        self.assertEqual(later["items"][0]["since"], "2026-11-05")
        back = run([], overrides={"keep": {"s1": "2026-11-05"}}, prev=later)
        self.assertEqual(back["hidden"], [])

    def test_keep_ignores_older_reports_but_not_new_ones(self):
        old = [rep("k1", ago_h=48) for _ in range(4)]
        ovr = {"keep": {"k1": "2026-11-04"}}
        self.assertEqual(run(old, overrides=ovr)["hidden"], [])
        new = [rep("k1", ago_h=2) for _ in range(4)]                   # reported again after the owner cleared it
        self.assertEqual(run(old + new, overrides=ovr)["hidden"], ["k1"])
        self.assertEqual(run(old + new, overrides={"keep": ["k1"]})["hidden"], [])   # a plain list keeps it for good

    def test_owner_hide(self):
        out = run([], overrides={"hide": ["h1"]})
        self.assertEqual(out["hidden"], ["h1"])
        self.assertEqual(out["items"][0]["by"], "owner")
        self.assertEqual(run([], overrides={}, prev=out)["hidden"], [])  # taken out of "hide": back

    def test_brake_on_mass_removal(self):
        rows = []
        for i in range(40):
            rows += [rep("m%02d" % i) for _ in range(4)]
        out = run(rows)
        self.assertEqual(len(out["hidden"]), B.MAX_NEW_PER_RUN)
        self.assertEqual(out["held"], 40 - B.MAX_NEW_PER_RUN)
        self.assertTrue(all(w.get("held") for w in out["watch"]))
        nxt = run(rows, prev=out)                                       # the next run takes the next batch
        self.assertEqual(len(nxt["hidden"]), 40)

    def test_output_has_no_personal_data(self):
        rows = [rep("pd") for _ in range(4)] + [rep("pw")]
        blob = __import__("json").dumps(run(rows))
        for r in rows:
            for k in ("user_id", "ip_hash", "net_hash", "tok_hash", "account_created"):
                self.assertNotIn('"%s"' % r[k], blob)

if __name__ == "__main__":
    unittest.main(verbosity=2)
