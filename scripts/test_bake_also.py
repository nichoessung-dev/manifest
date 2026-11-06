#!/usr/bin/env python3
"""Unit tests for scripts/bake_also.py on a small made-up catalogue: python3 scripts/test_bake_also.py"""
import json, os, shutil, sys, tempfile, unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bake_also as B   # noqa: E402

BRANDS = ["Alpha", "Bravo", "Charlie", "Delta", "Echo"]
ITEMS = [("Hoodie", "Tops"), ("T-Shirt", "Tops"), ("Sneakers", "Shoes"), ("Cap", "Headwear")]
COLS = ["Black", "White", "Navy"]


def make_root(tmp):
    cat, ai = [], {}
    n = 0
    for b in BRANDS:
        for it, c in ITEMS:
            for col in COLS:
                for k in range(2):
                    n += 1
                    pid = str(1000 + n)
                    cat.append({"id": pid, "platform": "weidian", "cat": c, "brand": b, "title": f"{b} {it} {col} {k}",
                                "price": 100 + 10 * k + 40 * ITEMS.index((it, c)), "qc": k, "img": "/x.webp"})
                    ai[pid] = {"item": it, "cat": c, "colour": col, "model_name": "Logo" if k else "Box", "title_base": f"{b} {it}"}
    os.makedirs(os.path.join(tmp, "data"))
    with open(os.path.join(tmp, "index.html"), "w") as f:
        f.write('<html><script type="application/json" id="pc-catalog">' + json.dumps(cat) + "</script></html>")
    for name, d in (("catalog_ai.json", {"items": ai}), ("link_health.json", {"dead": [cat[5]["id"]]}), ("reported.json", {"hidden": [cat[6]["id"]]})):
        with open(os.path.join(tmp, "data", name), "w") as f: json.dump(d, f)
    return cat


class BakeAlso(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.cat = make_root(self.tmp)
        self.out = os.path.join(self.tmp, "data", "also.json")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def run_bake(self, favs, views=()):
        fp, vp = os.path.join(self.tmp, "f.json"), os.path.join(self.tmp, "v.json")
        for path, rows in ((fp, favs), (vp, views)):
            with open(path, "w") as f: json.dump(list(rows), f)
        doc = B.main(["--root", self.tmp, "--favorites-file", fp, "--views-file", vp, "--no-eval", "--now", "2026-11-05T12:00:00+00:00"])
        return doc, B.decode(doc)

    def pair_favs(self, a, b, members):
        rows = []
        for m in range(members):
            u = "user-%d-secret" % m
            rows += [{"user_id": u, "product_id": a, "created_at": "2026-10-01T00:00:00Z"},
                     {"user_id": u, "product_id": b, "created_at": "2026-10-02T00:00:00Z"}]
        return rows

    def test_every_find_has_neighbours_never_itself_dead_or_reported(self):
        doc, d = self.run_bake([])
        dead, rep = self.cat[5]["id"], self.cat[6]["id"]
        self.assertEqual(len(d), len(self.cat))
        for pid, lst in d.items():
            self.assertEqual(len(lst), B.K_OUT, pid)
            ids = [x[0] for x in lst]
            self.assertNotIn(pid, ids); self.assertNotIn(dead, ids); self.assertNotIn(rep, ids)
            self.assertEqual(len(ids), len(set(ids)))
            for _, s, cf in lst:
                self.assertTrue(0 < s <= 0.99); self.assertFalse(cf)

    def test_pairs_need_three_members(self):
        a, b = self.cat[0]["id"], self.cat[-1]["id"]                # different brand, item and colour: not content neighbours
        pos = {p["id"]: i for i, p in enumerate(self.cat)}
        now = B.parse_ts("2026-11-05T12:00:00+00:00")
        for members, want in ((2, False), (3, True)):
            bk = B.baskets(self.pair_favs(a, b, members), [], pos, now)
            cfn, _ = B.cf_neighbours(bk, len(self.cat))
            self.assertEqual(any(j == pos[b] for j, _, _ in cfn[pos[a]]), want, members)
        _, d = self.run_bake(self.pair_favs(a, b, 2))
        self.assertNotIn(b, [x[0] for x in d[a]])
        _, d = self.run_bake(self.pair_favs(a, b, 40))               # strong evidence: the co-like makes the list
        hit = [x for x in d[a] if x[0] == b]
        self.assertTrue(hit and hit[0][2], "a pair held by many members is a co-like")
        self.assertTrue(any(x[0] == a and x[2] for x in d[b]))

    def test_weak_evidence_does_not_override_content(self):
        a, b = self.cat[0]["id"], self.cat[-1]["id"]
        _, d0 = self.run_bake([])
        _, d3 = self.run_bake(self.pair_favs(a, b, 3))               # 3 members: allowed, but too little to beat close finds
        self.assertEqual([x[0] for x in d0[a]][:6], [x[0] for x in d3[a]][:6])

    def test_no_user_ids_in_file(self):
        a, b = self.cat[0]["id"], self.cat[-1]["id"]
        self.run_bake(self.pair_favs(a, b, 5))
        with open(self.out) as f: body = f.read()
        self.assertNotIn("user-", body); self.assertNotIn("secret", body)
        self.assertEqual(set(json.loads(body)), {"v", "generated", "k", "ids", "n"})

    def test_brand_diversity(self):
        _, d = self.run_bake([])
        brand = {p["id"]: p["brand"] for p in self.cat}
        for pid, lst in d.items():
            own = sum(1 for x in lst if brand[x[0]] == brand[pid])
            self.assertLessEqual(own, B.BRAND_CAP_SAME)
            for b in BRANDS:
                if b != brand[pid]: self.assertLessEqual(sum(1 for x in lst if brand[x[0]] == b), B.BRAND_CAP_OTHER)

    def test_same_type_first(self):
        _, d = self.run_bake([])
        p = self.cat[0]
        top = [x[0] for x in d[p["id"]][:3]]
        byid = {q["id"]: q for q in self.cat}
        self.assertTrue(all(byid[t]["brand"] == p["brand"] and "Hoodie" in byid[t]["title"] for t in top))

    def test_unchanged_file_is_not_rewritten(self):
        self.run_bake([])
        with open(self.out) as f: m1 = f.read()
        doc = json.loads(m1); doc["generated"] = "1999-01-01T00:00:00+00:00"
        changed, _ = B.write_if_changed(self.out, doc)
        self.assertFalse(changed)
        with open(self.out) as f: self.assertEqual(f.read(), m1)

    def test_encoding_round_trip(self):
        doc, d = self.run_bake([])
        ids = set(doc["ids"])
        for row in doc["n"]:
            self.assertEqual(len(row) % 2, 0)
            for c in row[1::2]: self.assertEqual(c % 2, 0)             # even scores
        for lst in d.values():
            for j, _, _ in lst: self.assertIn(j, ids)

    def test_evaluation_runs_and_prints_aggregates_only(self):
        rows = []
        for m in range(30):
            u = "member-%d" % m
            for k, p in enumerate(self.cat[(m % 10) * 3:(m % 10) * 3 + 3]):
                rows.append({"user_id": u, "product_id": p["id"], "created_at": "2026-10-%02dT00:00:00Z" % (k + 1)})
        items = B.load_catalog(self.tmp)
        ai = B.load_json(os.path.join(self.tmp, "data", "catalog_ai.json"), {})["items"]
        feats, df = B.build_features(items, ai, {})
        pos = {f.id: i for i, f in enumerate(feats)}
        res = B.evaluate(feats, df, rows, [], pos, set(), B.parse_ts("2026-11-05T12:00:00+00:00"), verbose=False)
        self.assertEqual(set(res), {"popularity", "content", "content+brands", "colikes", "blend"})
        for r in res.values():
            self.assertEqual(r["members"], 30)
            self.assertTrue(0 <= r["hit12_single"] <= 1 and 0 <= r["hit12_multi"] <= 1)
        self.assertGreater(res["blend"]["hit12_multi"], 0.5)        # every member's pattern is shared by 3 members


if __name__ == "__main__":
    unittest.main()
