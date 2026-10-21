# -*- coding: utf-8 -*-
"""Writes factory/sources.md from factory/shop_prices.json: every confirmed shop price, the page it was read on and the date.
Only entries with found=true are listed; a script may only say a shop price that is in this file (factory/check.py checks it).
"""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
d = json.load(open(os.path.join(HERE, "shop_prices.json"), encoding="utf-8"))
rows = {}
for k in sorted(d):                                            # later passes override earlier ones for the same key
    for x in d[k]:
        if x.get("found"): rows[x["key"]] = x
        elif x["key"] in rows and k > "pass1": pass
L = ["# Shop prices", "", "Every \"around $X in the shop\" in a factory script comes from this list. Say = the price rounded down to two significant figures.",
     "A price that could not be confirmed on the day is not listed, so it cannot be used.", "",
     "| key | item | seller | price seen | say | checked | page |", "|---|---|---|---|---|---|---|"]
for key, x in sorted(rows.items()):
    L.append("| %s | %s | %s (%s) | $%s %s | around $%s | %s | %s |" % (key, x["product_name"].replace("|", "/"), x["seller"].replace("|", "/"), x["seller_kind"],
             ("{:,.2f}".format(x["price_usd"]).rstrip("0").rstrip(".")), "" if x["currency_shown"] == "USD" else "(" + x["currency_shown"][:60].replace("|", "/") + ")",
             "{:,}".format(x["say_usd"]), x["checked"], x["url"]))
L += ["", "## Notes per price", ""]
for key, x in sorted(rows.items()):
    L.append("- **%s**: %s Evidence: %s" % (key, x["match_note"].replace("\n", " "), x["evidence"].replace("\n", " ")))
open(os.path.join(HERE, "sources.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
print("sources.md:", len(rows), "confirmed prices")
