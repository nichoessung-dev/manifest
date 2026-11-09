#!/usr/bin/env python3
"""Unit tests for scripts/seller_photos.py and scripts/apply_seller_photos.py, no network and no API:
python3 scripts/test_seller_photos.py"""
import hashlib, io, json, os, shutil, sys, tempfile, unittest
from types import SimpleNamespace

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import seller_photos as S          # noqa: E402
import apply_seller_photos as A    # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLE = os.path.join(HERE, "testdata", "weidian_sku_sample.json")
TAG = '<script type="application/json" id="pc-catalog">'


def photo(w, h, colour=(20, 20, 20), bg=(244, 244, 241), item=0.8):
    im = Image.new("RGB", (w, h), bg)
    d = ImageDraw.Draw(im)
    iw, ih = w * item, h * item
    d.rectangle(((w - iw) / 2, (h - ih) / 2, (w + iw) / 2, (h + ih) / 2), fill=colour)
    return im


def jpg(im):
    b = io.BytesIO(); im.save(b, "JPEG", quality=90); return b.getvalue()


class FakeSource:
    def __init__(self, files):
        self.files, self.asked, self.requests = files, [], 0

    def image(self, url):
        self.asked.append(url); self.requests += 1
        if url not in self.files:
            raise ValueError("404")
        return self.files[url]


def args(**kw):
    a = SimpleNamespace(min_side=900, max_cands=6, max_downloads=12, verbose=False, ids="", limit=0, redo=False,
                        min_item_px=800, rembg_model="threshold", mock=True, recut=False, bg="none", fill=0.86,
                        shadow=0.16, max_parts=3)
    a.__dict__.update(kw)
    return a


class ParseCandidates(unittest.TestCase):
    def setUp(self):
        self.d = json.load(open(SAMPLE, encoding="utf-8"))

    def test_order_dedupe_labels_and_filters(self):
        c = S.parse_candidates(self.d)
        urls = [x["url"] for x in c]
        base = "https://si.geilicdn.com/pcitem1234567890-"
        self.assertEqual(urls, [
            base + "1a2b0000018f2c3d4e5f0a20b2c3_1279_1706.jpg",   # main picture first, query removed
            base + "black0000_1440_1920.jpg",                     # option photo, same URL as two SKUs: once
            base + "white0000_640_853.jpg",                       # protocol-relative URL made https
            base + "grey0000.png",                                # http made https, no size in the name
            base + "blue0000_1080_1080.webp",                     # SKU-only photo
            base + "detail0000_1200_1600.jpg",                    # any other listing photo in the answer
        ])
        self.assertEqual([x["from"] for x in c], ["main", "option", "option", "option", "sku", "other"])
        self.assertEqual(c[1]["label"], "黑色 / 黑色;M / 黑色;L")
        self.assertEqual(c[0]["hint"], (1279, 1706))
        self.assertIsNone(c[3]["hint"])
        self.assertFalse(any("shoplogo" in u or "avatar" in u or "example.com" in u for u in urls))

    def test_result_alone_and_empty(self):
        self.assertEqual(len(S.parse_candidates(self.d["result"])), 6)
        self.assertEqual(S.parse_candidates({"status": {"code": 0}, "result": {}}), [])
        self.assertEqual(S.parse_candidates({}), [])


class SizeFilter(unittest.TestCase):
    def test_short_side_dedupe_and_cap(self):
        b = "https://si.geilicdn.com/x-"
        files = {b + "big_1000_1300.jpg": jpg(photo(1000, 1300)),
                 b + "lie_1000_1000.jpg": jpg(photo(1000, 800)),          # name says big, photo is 800 px high
                 b + "dupe.jpg": jpg(photo(1000, 1300)),                  # the same photo under another URL
                 b + "red.jpg": jpg(photo(1000, 1300, colour=(200, 20, 20))),  # same shape, other colour: kept
                 b + "exact900.jpg": jpg(photo(900, 1200, colour=(20, 120, 20)))}
        cands = [{"url": b + "small_640_853.jpg", "from": "main", "label": "", "hint": (640, 853)},
                 {"url": b + "big_1000_1300.jpg", "from": "main", "label": "", "hint": (1000, 1300)},
                 {"url": b + "lie_1000_1000.jpg", "from": "sku", "label": "", "hint": (1000, 1000)},
                 {"url": b + "dupe.jpg", "from": "sku", "label": "", "hint": None},
                 {"url": b + "missing.jpg", "from": "sku", "label": "", "hint": None},
                 {"url": b + "red.jpg", "from": "sku", "label": "", "hint": None},
                 {"url": b + "exact900.jpg", "from": "sku", "label": "", "hint": None}]
        src = FakeSource(files)
        kept, why = S.gather(cands, src, args())
        self.assertEqual([k["url"] for k in kept], [b + "big_1000_1300.jpg", b + "red.jpg", b + "exact900.jpg"])
        self.assertNotIn(b + "small_640_853.jpg", src.asked)              # skipped by its name, never downloaded
        self.assertEqual(why, {"under 900 px (by name)": 1, "under 900 px": 1, "same photo twice": 1, "download failed": 1})
        kept2, _ = S.gather(cands, FakeSource(files), args(max_cands=1))
        self.assertEqual(len(kept2), 1)
        src3 = FakeSource(files)
        S.gather(cands, src3, args(max_downloads=2))
        self.assertEqual(len(src3.asked), 2)


class Selection(unittest.TestCase):
    def test_order_and_skips(self):
        items = [{"id": str(i), "platform": "weidian", "title": "T %d" % i} for i in range(1, 9)]
        items.append({"id": "99", "platform": "taobao"})
        labels = {
            "1": {"is_clean_product_photo": False, "photo_issues": ["multiple_views"]},        # not a FIRST issue
            "2": {"is_clean_product_photo": False, "photo_issues": ["busy_background"]},
            "3": {"is_clean_product_photo": False, "photo_issues": ["blurry_or_low_res"]},
            "4": {"is_clean_product_photo": True, "photo_issues": []},                          # clean: left out
            "5": {"is_clean_product_photo": False, "photo_issues": ["worn_by_person"]},          # dead: left out
            "6": {"error": "http 500"},                                                         # no label: left out
            "7": {"is_clean_product_photo": False, "photo_issues": ["hanger_or_rack"]},          # done already
            "8": {"is_clean_product_photo": False, "photo_issues": ["text_or_watermark"]},
            "99": {"is_clean_product_photo": False, "photo_issues": ["worn_by_person"]},         # not Weidian
        }
        st = {"1": [900, 500, 100, 0], "2": [50, 10, 5, 0], "3": [40, 10, 5, 0], "7": [0, 999, 0, 0], "8": [0, 0, 0, 0]}
        store = {"items": {"7": {"status": "ok"}, "8": {"status": "error"}}}
        got = [p["id"] for p in S.select(items, labels, store, st, {"5"}, args())]
        # FIRST issues before the rest; within them recent views x severity (3: 15 x 2.0 = 30 beats 2: 15 x 1.6 = 24);
        # an error record is retried; the most viewed find comes last because multiple_views alone is not a FIRST issue
        self.assertEqual(got, ["3", "2", "8", "1"])
        self.assertEqual([p["id"] for p in S.select(items, labels, store, st, {"5"}, args(redo=True))], ["7", "3", "2", "8", "1"])
        self.assertEqual([p["id"] for p in S.select(items, labels, store, st, {"5"}, args(limit=2))], ["3", "2"])
        self.assertEqual([p["id"] for p in S.select(items, labels, store, st, set(), args(ids="4,99,7"))], ["4"])


class Picker(unittest.TestCase):
    def test_judge(self):
        good = {"choice": 2, "same_item": True, "same_colour": True, "clean": True, "confidence": 0.86, "reason": "plain"}
        self.assertEqual(S.judge(good, 3, 0.8)[0], 2)
        self.assertEqual(S.judge(dict(good, confidence=0.79), 3, 0.8)[0], -1)
        self.assertEqual(S.judge(dict(good, same_colour=False), 3, 0.8)[0], -1)
        self.assertEqual(S.judge(dict(good, choice=3), 3, 0.8)[0], -1)              # out of range
        self.assertEqual(S.judge(dict(good, choice=-1), 3, 0.8)[0], -1)
        self.assertEqual(S.judge({"choice": "x"}, 3, 0.8)[0], -1)
        self.assertNotIn("\u2014", S.judge(dict(good, reason="a \u2014 b"), 3, 0.8)[2])

    def test_request_shape(self):
        kept = [{"from": "main", "label": "", "thumb": b"x"}, {"from": "option", "label": "黑色", "thumb": b"y"}]
        c = S.request_content({"brand": "B", "title": "B Hoodie Black", "cat": "Tops"}, {"colour": "Black"}, b"z", kept)
        self.assertEqual([x["type"] for x in c], ["text", "image", "text", "image", "text", "image", "text"])
        self.assertIn("seller option: 黑色", c[4]["text"])
        self.assertIn("numbered 0 to 1", c[-1]["text"])
        txt = S.PROMPT + json.dumps(S.SCHEMA)
        self.assertNotIn("\u2014", txt); self.assertNotIn("\u2013", txt)


class CutOut(unittest.TestCase):
    def test_ok_and_gates(self):
        p = {"id": "1", "cat": "Accessories", "title": "Wallet Black"}
        out, notes, st, fd, how = S.cut_out(photo(1000, 1300), p, args())
        self.assertEqual((out.size, out.mode), ((1200, 1200), "RGBA"))
        self.assertLessEqual(fd, 4.0)
        with self.assertRaises(S.Skip):                                  # item touches the photo edge
            S.cut_out(photo(1000, 1300, item=1.0), p, args())
        with self.assertRaises(S.Skip) as e:                             # item too small: never upscaled
            S.cut_out(photo(1000, 1300, item=0.4), p, args())
        self.assertIn("never upscaled", str(e.exception))


class MockRun(unittest.TestCase):
    def test_end_to_end_mock(self):
        tmp = tempfile.mkdtemp()
        try:
            cat = [{"id": "7001", "platform": "weidian", "cat": "Tops", "brand": "B", "title": "B Tee Black", "img": "/x.webp"},
                   {"id": "7002", "platform": "weidian", "cat": "Tops", "brand": "B", "title": "B Tee Navy", "img": "/x.webp"}]
            open(os.path.join(tmp, "index.html"), "w").write("<html>" + TAG + json.dumps(cat) + "</script></html>")
            json.dump({"items": {"7001": {"is_clean_product_photo": False, "photo_issues": ["worn_by_person"]},
                                 "7002": {"is_clean_product_photo": False, "photo_issues": ["hanger_or_rack"]}}},
                      open(os.path.join(tmp, "labels.json"), "w"))
            argv = ["--mock", "--index", os.path.join(tmp, "index.html"), "--labels", os.path.join(tmp, "labels.json"),
                    "--stats", os.path.join(tmp, "none.json"), "--link-health", os.path.join(tmp, "none.json"),
                    "--store", os.path.join(tmp, "store.json"), "--outdir", os.path.join(tmp, "p2"),
                    "--rembg-model", "threshold", "--sheets", os.path.join(tmp, "sheets")]
            self.assertEqual(S.main(argv), 0)
            st = json.load(open(os.path.join(tmp, "store.json")))
            for i in ("7001", "7002"):
                r = st["items"][i]
                self.assertIn(r["status"], ("ok", "error"))              # the mock Weidian fails ~10% of lookups
                if r["status"] == "ok":
                    self.assertTrue(r["file"].endswith("p2/%s.webp" % i))
                    self.assertTrue(os.path.isfile(os.path.join(tmp, "p2", i + ".webp")))
                    self.assertEqual(r["model"], "mock")
                    self.assertTrue(all(min(c[1], c[2]) >= 900 for c in r["candidates"]))
                    self.assertNotIn("collage", r["src"])
            self.assertEqual(len(st["runs"]), 1)
            self.assertTrue(os.listdir(os.path.join(tmp, "sheets")))
            # a second run skips finds that are done
            S.main(argv)
            self.assertEqual(json.load(open(os.path.join(tmp, "store.json")))["runs"][-1]["asked"],
                             sum(1 for r in st["items"].values() if r["status"] == "error"))
        finally:
            shutil.rmtree(tmp)


class ApplyRevert(unittest.TestCase):
    """On a copy of the real index.html (falls back to a small made-up one when it is not there)."""
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        real = os.path.join(os.path.dirname(HERE), "index.html")
        dst = os.path.join(self.tmp, "index.html")
        if os.path.isfile(real):
            shutil.copy(real, dst)
        else:
            cat = [{"id": "11", "platform": "weidian", "title": "a", "img": "https://x.supabase.co/a.webp", "variants": [["Black", 1]]},
                   {"id": "12", "platform": "weidian", "title": "b", "img": "/img/p/12.webp"},
                   {"id": "13", "platform": "weidian", "title": "c", "img": "https://x.supabase.co/c.webp"},
                   {"id": "14", "platform": "weidian", "title": "d", "img": "https://x.supabase.co/d.webp"}]
            open(dst, "w").write("<html>" + TAG + json.dumps(cat, separators=(",", ":")) + "</script></html>")
        _, items, _, _ = S.load_catalog(dst)
        self.ids = [p["id"] for p in items if p.get("platform") == "weidian"][:4]
        self.before = open(dst, "rb").read()
        self.items = items
        os.makedirs(os.path.join(self.tmp, "img", "p2"))
        os.makedirs(os.path.join(self.tmp, "data"))
        cut = Image.new("RGBA", (1200, 1200), (0, 0, 0, 0))
        recs = {}
        for n, i in enumerate(self.ids):
            name = i + (".v2" if n == 1 else "") + ".webp"
            cut.save(os.path.join(self.tmp, "img", "p2", name), "WEBP")
            recs[i] = {"status": "ok", "file": "img/p2/" + name, "confidence": 0.9, "model": "claude-haiku-5-5", "src": "u"}
        recs[self.ids[2]]["confidence"] = 0.5                       # under the bar: not switched
        recs[self.ids[3]]["model"] = "mock"                          # a test result: never switched
        recs["nope"] = {"status": "ok", "file": "img/p2/nope.webp", "confidence": 0.9, "model": "m"}
        json.dump({"items": recs}, open(os.path.join(self.tmp, "data", "seller_photos.json"), "w"))

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_apply_then_revert(self):
        idx = os.path.join(self.tmp, "index.html")
        A.main(["--root", self.tmp])                                 # report only
        self.assertEqual(open(idx, "rb").read(), self.before)
        A.main(["--root", self.tmp, "--write", "--report", os.path.join(self.tmp, "r.md")])
        _, after, _, _ = S.load_catalog(idx)
        changed = {x["id"]: y["img"] for x, y in zip(self.items, after) if x != y}
        self.assertEqual(changed, {self.ids[0]: "/img/p2/%s.webp" % self.ids[0], self.ids[1]: "/img/p2/%s.v2.webp" % self.ids[1]})
        html_after = open(idx, "rb").read()
        self.assertEqual(len(html_after) - len(self.before),
                         sum(len(v) for v in changed.values()) - sum(len(x["img"]) for x in self.items if x["id"] in changed))
        # run again: nothing more to do
        A.main(["--root", self.tmp, "--write"])
        self.assertEqual(open(idx, "rb").read(), html_after)
        log = os.path.join(self.tmp, "data", "seller_photos_applied.json")
        self.assertEqual(len(json.load(open(log))["batches"]), 1)
        A.main(["--root", self.tmp, "--revert", log, "--write"])
        self.assertEqual(hashlib.sha256(open(idx, "rb").read()).hexdigest(), hashlib.sha256(self.before).hexdigest())


if __name__ == "__main__":
    unittest.main(verbosity=2)
