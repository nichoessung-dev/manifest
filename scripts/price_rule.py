# -*- coding: utf-8 -*-
"""The price a find shows, worked out from its Weidian listing (owner, 23 Nov 2026: "a lot of the prices is not accurate").

Weidian's own "from" price (itemDiscountLowPrice, what the friend import and the partner swaps used to show) is the
cheapest SKU of the listing. Sellers often add a cheap SKU that is not the item: a link to another listing, a deposit,
the postage, a box or a bag, a refill, a "write a note" option. So the find showed 1 to 20 yuan for a jacket.
shown_price() takes the cheapest REAL variant instead:
  1. every SKU's price (discountPrice, else originalPrice; fen to yuan) and stock
  2. SKUs named like a placeholder are left out (PLACEHOLDER below: link, deposit, postage, price difference, contact us)
  3. prices the site treats as placeholders anyway are left out: under 5 yuan, or 99,999 and up (site.js isPH)
  4. add-ons sold with the item are left out when the listing has anything else: an option named exactly like a box,
     a bag, an adjuster, a refill or the packaging (ADDON below)
  5. only the SKUs in stock, when any is
  6. SKUs far below the rest are left out: under FLOOR times the median price of the remaining SKUs
  7. the cheapest of what is left, rounded to whole yuan (the catalogue stores whole yuan)
A listing without SKUs has one price (itemDiscountLowPrice, else itemOriginalLowPrice), checked the same way.

shown_price(result) -> {"status", "price", "prices", "low", "high", "n", "dropped"}
  status: "ok"; "sold_out" (a price, but nothing in stock); "no_price" (only placeholder prices: ask the seller);
          "gone" (Weidian answered without a listing). price is None unless status is ok or sold_out.
  prices: every real variant's price (whole yuan, ascending, at most 40); price is the first.
  low/high: the lowest and highest SKU price of the listing as Weidian shows them (placeholders included), in yuan.
pick(current, prices, cheapest): the price a find shows. A listing can hold several models at their own prices (a
"collection" listing, or joggers and shorts in one), and a find may be one of the dearer ones, so a current price that
is still one of the real variant prices (within 2%) stays, moved to that variant's exact price; anything else (an old
price, a placeholder) becomes the cheapest real variant.
No network here: scripts/prices.py and scripts/bake_swaps.py fetch getItemSkuInfo and pass its "result".
"""
import re

RULE = "v1"            # bump when the rule changes: data/prices.json records which rule set each price
FLOOR = 0.3            # a SKU under 30% of the median of the listing's real SKUs is not the item (a link, a note, a refill)
MIN_REAL = 5           # site.js isPH: under 5 yuan is a placeholder ("ask me")
MAX_REAL = 99999       # site.js isPH: 99,999 yuan and up is "not for sale"

# SKU names that are never the item itself (checked on 552 listings, 23 Nov 2026). Only words that do not turn up in
# real variant names: "备注" (note the size), "鞋带" (orange laces), "不带盒子" (without the box), "礼盒装" (the gift-box
# version) and "配手提袋" (comes with a bag) all name real variants. Cheap add-ons are step 4 (ADDON) and FLOOR.
PLACEHOLDER = re.compile(
    r"链接|专拍|补拍|补差|差价|补邮|邮费|运费|快递费|定金|订金|押金|预付|尾款|"
    r"不发货|拍下不发|勿拍|不要拍|别拍|联系客服|咨询客服|"
    r"(?<![a-z])(deposit|postage|shipping fee|freight)s?(?![a-z])|(new|other|this|another|old)\s*link|link\s*[:：]|^\s*links?\s*$|"
    r"https?[:：]|www\.|yupoo|微信",
    re.I)
# An option (one part of a SKU name, "colour;size") that is exactly one of these is an add-on, not the item: the box, a
# bag, the packaging, a strap adjuster, a refill, laces. Seen on bracelets, bangles and watches (box 21, bag 18, adjuster
# 13 yuan next to a bracelet at 49 to 68). Left out only when the listing has other SKUs.
ADDON = {"盒子", "鞋盒", "礼盒", "包装盒", "原盒", "表盒", "首饰盒", "手提袋", "包装袋", "防尘袋", "礼品袋", "调节器", "包装",
         "整套包装", "配件", "赠品", "鞋带", "笔芯", "giftbox", "shoebox", "dustbag"}
_STRIP = re.compile(r"[\s()（）【】\[\]]+")


def is_addon(title):
    return any(_STRIP.sub("", part).lower() in ADDON for part in str(title or "").split(";"))


def _yuan(fen):
    try:
        v = float(fen)
    except (TypeError, ValueError):
        return 0.0
    return v / 100.0 if v > 0 else 0.0


def _median(vals):
    s = sorted(vals)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def whole(y):
    """Whole yuan, halves up (the catalogue stores whole yuan; Python's round() would send 104.5 to 104)."""
    return int(y + 0.5)


def skus(res):
    """[(price yuan, stock or None, title)] for every SKU of a getItemSkuInfo result; [] when it has none."""
    out = []
    for s in (res or {}).get("skuInfos") or []:
        si = s.get("skuInfo") if isinstance(s.get("skuInfo"), dict) else s
        y = _yuan(si.get("discountPrice")) or _yuan(si.get("originalPrice"))
        st = si.get("stock")
        out.append((y, st if isinstance(st, (int, float)) else None, str(si.get("title") or "")))
    return out


def is_gone(res):
    """Weidian answers a deleted or hidden listing without a title and without a main photo (scripts/check_links.py)."""
    return not ((res or {}).get("itemTitle") or (res or {}).get("itemMainPic"))


def shown_price(res):
    res = res or {}
    if is_gone(res):
        return {"status": "gone", "price": None, "prices": [], "low": None, "high": None, "n": 0, "dropped": 0}
    rows = skus(res)
    if not rows:   # a listing without options: one price
        y = _yuan(res.get("itemDiscountLowPrice")) or _yuan(res.get("itemOriginalLowPrice")) or _yuan(res.get("itemLowPrice"))
        st = res.get("itemStock")
        rows = [(y, st if isinstance(st, (int, float)) else None, "")]
    prices = [y for y, _, _ in rows if y > 0]
    low, high = (min(prices), max(prices)) if prices else (None, None)
    real = [r for r in rows if MIN_REAL <= r[0] < MAX_REAL and not PLACEHOLDER.search(r[2])]
    real = [r for r in real if not is_addon(r[2])] or real
    out = {"status": "no_price", "price": None, "prices": [], "low": _clean(low), "high": _clean(high), "n": len(rows), "dropped": len(rows) - len(real)}
    if not real:
        return out
    stocked = [r for r in real if r[1] is None or r[1] > 0]
    pool = stocked or real
    med = _median([r[0] for r in pool])
    keep = [r for r in pool if r[0] >= FLOOR * med]
    out["dropped"] = len(rows) - len(keep) - (len(real) - len(pool))
    out["prices"] = sorted({whole(r[0]) for r in keep})[:40]
    out["price"] = out["prices"][0]
    out["status"] = "ok" if stocked else "sold_out"
    item_stock = res.get("itemStock")
    if isinstance(item_stock, (int, float)) and item_stock <= 0:
        out["status"] = "sold_out"
    return out


def _clean(y):
    if y is None:
        return None
    return int(y) if y == int(y) else round(y, 2)


def pick(current, prices, cheapest):
    """The price to show (see the top): the real variant price nearest the current one when it is within 2% (or 1 yuan),
    else the cheapest real variant."""
    try:
        cur = float(current or 0)
    except (TypeError, ValueError):
        cur = 0.0
    near = [y for y in (prices or []) if abs(cur - y) <= max(1.0, 0.02 * y)]
    if cur >= MIN_REAL and near:
        return min(near, key=lambda y: abs(cur - y))
    return cheapest
