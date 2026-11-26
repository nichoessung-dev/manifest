#!/usr/bin/env python3
"""Tests for the Engagement bake in scripts/bake_stats.py (no network). Run: python3 scripts/test_bake_engagement.py"""
import datetime, os, sys, unittest
os.environ.setdefault("SUPABASE_SERVICE_KEY", "test")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bake_stats as B

NOW = datetime.datetime(2026, 11, 26, 12, 0, tzinfo=datetime.timezone.utc)


def summary(visits=10, first="2026-09-01T00:00:00+00:00", entries=None, **kw):
    """One visit_summary() result as Postgres returns it (numbers can come back as floats or null)."""
    s = {"visits": visits, "avg_s": 61.25, "median_s": 40.0, "bounce": 2, "pages": 15, "finds": 20, "find_s": 300, "find_n": 18,
         "buys": 3, "buy_visits": 2, "returning": 4, "ret_median_s": 55.0, "new_median_s": None,
         "hist": [2, 3, 1, 2, 1, 1], "entries": entries if entries is not None else [["/", 6, 40.0, 1]], "first": first}
    s.update(kw)
    return s


class Engagement(unittest.TestCase):
    def test_period_shape_and_rounding(self):
        p = B.visit_period(summary())
        self.assertEqual(p["visits"], 10)
        self.assertEqual(p["avg_s"], 61.2)                       # rounded to 1 place
        self.assertIsNone(p["new_median_s"])
        self.assertEqual(p["hist"], [2, 3, 1, 2, 1, 1])
        self.assertEqual(p["entries"], [["/", "homepage", 6, 40.0, 1]])

    def test_rare_and_odd_entries_left_out(self):
        rows = [["/", 50, 30, 5], ["/brand/stone-island", 5, 22.5, 1], ["/typed-by-someone", 4, 9, 4], ["", 9, 3, 9], ["javascript:x", 99, 1, 1]]
        p = B.visit_period(summary(entries=rows))
        self.assertEqual([e[0] for e in p["entries"]], ["/", "/brand/stone-island"])
        self.assertEqual(p["entries"][1][1], "brand and category hubs")

    def test_empty_period(self):
        p = B.visit_period({"visits": 0, "hist": None, "entries": None, "avg_s": None, "median_s": None})
        self.assertEqual((p["visits"], p["avg_s"], p["hist"], p["entries"]), (0, None, [0] * 6, []))

    def test_prev_full_only_when_timer_ran_through_the_previous_period(self):
        summ = {"7": (summary(), summary()), "30": (summary(), summary())}
        e = B.engagement_from(summ, [], "2026-11-01T08:00:00+00:00", NOW)   # 25 days of data
        self.assertTrue(e["w"]["7"]["prev_full"])                 # needs 14 days
        self.assertFalse(e["w"]["30"]["prev_full"])               # needs 60 days
        self.assertEqual(e["since"], "2026-11-01")
        self.assertTrue(e["ready"])

    def test_no_visits_yet(self):
        summ = {"7": (summary(0, first=None), summary(0, first=None)), "30": (summary(0, first=None), summary(0, first=None))}
        e = B.engagement_from(summ, [], None, NOW)
        self.assertIsNone(e["since"])
        self.assertFalse(e["w"]["7"]["prev_full"])

    def test_daily_fills_30_days(self):
        daily = [["2026-11-25", 12, 70.5, 33, 2, 1], ["2026-11-26", 4, 20, 9.5, 1, 0]]
        e = B.engagement_from({"7": (summary(), summary())}, daily, "2026-11-25T00:00:00Z", NOW)
        d = e["daily"]
        self.assertEqual(len(d["days"]), 30)
        self.assertEqual(d["days"][-1], "2026-11-26")
        self.assertEqual(d["visits"][-2:], [12, 4])
        self.assertEqual(d["median_s"][-2:], [33.0, 9.5])
        self.assertEqual(d["visits"][0], 0)                       # a day without visits is 0 visits ...
        self.assertIsNone(d["median_s"][0])                       # ... and no median


if __name__ == "__main__":
    unittest.main()
