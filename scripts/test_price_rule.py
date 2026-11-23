# -*- coding: utf-8 -*-
"""Tests for scripts/price_rule.py and the catalogue edits of scripts/prices.py: python scripts/test_price_rule.py

The listings below are real Weidian answers from the 23 Nov 2026 price check, cut down to the SKUs that matter.
"""
import json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import price_rule as pr  # noqa: E402
import prices  # noqa: E402


def listing(rows, title="x", **kw):
    """A getItemSkuInfo result: rows are (yuan, stock, SKU name)."""
    res = {"itemTitle": title, "itemMainPic": "https://si.geilicdn.com/x.jpg", "skuInfos": [
        {"skuInfo": {"title": t, "discountPrice": int(round(y * 100)), "originalPrice": int(round(y * 100)), "stock": st}} for y, st, t in rows]}
    if rows:
        res["itemDiscountLowPrice"] = int(round(min(y for y, _, _ in rows) * 100))
    res.update(kw)
    return res


CASES = [
    # (what, result, expected status, expected price)
    ("Nike Kyrie 6 4398141712: catalogue said 1 yuan, every size is 79",
     listing([(79, 166665, "401 藏青 ; %s" % s) for s in ("40", "41", "42", "43", "44")]), "ok", 79),
    ("Montblanc pen 6406833678: a 2-pack of refills at 10 yuan is not the pen",
     listing([(10, 9892, "黑色笔芯(2支装);2支装黑色签字笔笔芯"), (10, 0, "黑色笔芯(2支装);More new:https://bf-style.x.yupoo.com"),
              (105, 0, "海洋系列（海洋）;签字笔"), (105, 5, "海洋系列（海洋）;钢笔"), (69, 994, "鳄鱼黑本子(不带盒子，不带签字笔);本子选这个选项"),
              (113, 727, "黑色金夹(新款配手提袋，一百周年系列);签字笔"), (113, 900, "黑色金夹(新款配手提袋，一百周年系列);钢笔"),
              (115, 971, "枪色(莎士比亚限量款);签字笔"), (115, 988, "枪色(莎士比亚限量款);钢笔"), (119, 996, "奥运黑银(奥运特别款);签字笔"),
              (290, 97, "黑色公文包;包包选这个选项(公文包 39x29x7cm)")]), "ok", 69),
    ("bracelet 7739786803: adjuster 13, bag 18 and box 21 are add-ons, the bracelets start at 49",
     listing([(13, 80326, "调节器"), (18, 83747, "手提袋"), (21, 98670, "盒子"), (49, 98372, "NO.02女款钢色+盒子"),
              (57, 98889, "NO.05滴油鳄鱼手链+盒子"), (62, 72485, "NO.01男款钢色+盒子"), (62, 96729, "NO.01男款黑色+盒子"),
              (68, 98358, "NO.03大鳄鱼黑色+盒子")]), "ok", 49),
    ("bangle 7908146459: the gift box option at 25, the bangle at 82",
     listing([(25, 692, "礼盒;16cm白金色"), (25, 858, "礼盒;16cm黄金色")] + [(82, 900, "白金色;%scm" % s) for s in range(15, 21)]), "ok", 82),
    ("watch 7717333737: the box at 40",
     listing([(40, 989, "盒子"), (108, 50, "黑色"), (108, 50, "白色"), (116, 50, "金色"), (116, 50, "银色")]), "ok", 108),
    ("GGDB 6716583439: one 20 yuan 'write a number' SKU among 340 yuan shoes",
     listing([(20, 999999, "31请备注数字，否则默认发5#米色;38")] + [(340, 999, "%d;%d" % (c, s)) for c in range(1, 4) for s in range(36, 44)]
             + [(369, 999, "定制%d;40" % c) for c in range(3)]), "ok", 340),
    ("a listing that moved: 'New Link: https://...' is its only SKU",
     listing([(999, 0, "New Link：https://k.youshop10.com/BP63VMF")]), "no_price", None),
    ("watch 7643100615: 'ask us for other colours' is not a variant",
     listing([(481, 100, "需要其他颜色可以咨询客服"), (753, 92, "橄榄绿-39mm"), (753, 97, "橄榄绿-36mm"), (753, 100, "粉色-36mm")]), "ok", 753),
    ("multi-model hoodie listing 7841602810: the 79 yuan models on sale are real",
     listing([(79, 1990, "BB-0%d(特价);L" % k) for k in range(5, 10)] + [(180, 900, "BB-32;M"), (180, 900, "BB-33;M")]
             + [(260, 900, "BB-%d;M" % k) for k in range(14, 23)] + [(270, 900, "BB-0%d;L" % k) for k in range(1, 4)]
             + [(380, 900, "BB-2%d;L" % k) for k in range(4, 9)] + [(650, 900, "BB-3%d;L" % k) for k in range(4, 7)]), "ok", 79),
    ("scarf: '礼盒装' (gift-box version) is a real variant, not the box",
     listing([(60, 970, "1;普通装"), (60, 989, "3;普通装"), (80, 994, "1;礼盒装")]), "ok", 60),
    ("shoes with 'note your size' in every SKU name",
     listing([(546, 999, "%d;36-45码 无半码（下单请备注尺码）;GZ" % k) for k in range(1, 9)]), "ok", 546),
    ("only the out-of-stock SKUs are cheap: the price is what can be bought",
     listing([(199, 0, "Down 灰色;XS"), (199, 0, "Down 灰色;XXXL"), (464, 5, "Down 灰色;M"), (464, 5, "Down 灰色;L")]), "ok", 464),
    ("nothing in stock: the price still shows, status sold_out",
     listing([(120, 0, "黑色;M"), (120, 0, "黑色;L")]), "sold_out", 120),
    ("1 yuan 'ask me' SKUs only", listing([(1, 999, "黑色"), (1, 999, "白色")]), "no_price", None),
    ("a listing without options", {"itemTitle": "x", "itemDiscountLowPrice": 25900, "itemStock": 30}, "ok", 259),
    ("a listing without options at 1 yuan", {"itemTitle": "x", "itemDiscountLowPrice": 100, "itemStock": 30}, "no_price", None),
    ("a gone listing (Weidian answers without title and photo)", {"offlineItem": False, "purpleShop": False}, "gone", None),
    ("half yuan rounds up", listing([(104.5, 9, "黑色")]), "ok", 105),
    ("a listing that sells the box itself keeps it", listing([(35, 9, "盒子"), (35, 9, "礼盒")]), "ok", 35),
    ("deposit and postage SKUs", listing([(50, 9, "定金"), (12, 9, "补邮费"), (300, 9, "黑色;M"), (300, 9, "黑色;L")]), "ok", 300),
]


def test_rule():
    bad = 0
    for what, res, status, price in CASES:
        r = pr.shown_price(res)
        ok = r["status"] == status and r["price"] == price
        bad += not ok
        print("%s  %s: %s %s" % ("ok  " if ok else "FAIL", what, r["status"], r["price"]))
    return bad


PICKS = [
    # (what, current catalogue price, real variant prices, expected shown price)
    ("collection listing 7820381351: the find's own model at 458 stays", 458, [298, 398, 428, 458, 498, 590], 458),
    ("a price 2 yuan off a variant moves to it", 264, [110, 130, 136, 240, 266], 266),
    ("an old price that is no variant becomes the cheapest", 602, [301], 301),
    ("a placeholder becomes the cheapest", 1, [79], 79),
    ("a placeholder is never kept, even when a variant is close", 3, [4, 79], 4),
    ("no current price", 0, [120, 150], 120),
]


def test_pick():
    bad = 0
    for what, cur, ps, want in PICKS:
        got = pr.pick(cur, ps, ps[0])
        bad += got != want
        print("%s  %s: %s" % ("ok  " if got == want else "FAIL", what, got))
    return bad


def test_edit():
    """prices.edit_object changes price, usd and the variant prices of one catalogue object, nothing else."""
    p = {"id": "7664348037", "platform": "weidian", "cat": "Shoes", "brand": "Adidas", "title": "Adidas Samba Sneakers White {x}",
         "price": 2, "usd": 0.25, "qc": 1, "seller": "Weidian Marketplace", "rating": 0, "views": 0, "variants": [["Standard", 2]],
         "img": "https://x/y.webp", "g": "m"}
    raw = prices.esc([p, dict(p, id="1", title="Other")])
    sp = prices.object_span(raw, "7664348037")
    obj = prices.edit_object(raw[sp[0]:sp[1]], p, 178, prices.usd_of(178))
    after = json.loads(raw[:sp[0]] + obj + raw[sp[1]:])
    want = dict(p, price=178, usd=24.92, variants=[["Standard", 178]])
    ok = after[0] == want and after[1] == dict(p, id="1", title="Other")
    print("%s  catalogue edit: price, usd and variants only" % ("ok  " if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    n = test_rule() + test_pick() + test_edit()
    print("all passed" if not n else "%d failed" % n)
    sys.exit(1 if n else 0)
