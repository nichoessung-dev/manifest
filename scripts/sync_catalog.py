#!/usr/bin/env python3
"""Keep derived catalog files in sync with index.html (the source of truth).

Regenerates, only when something actually changed:
  - products.json   read by functions/product/[id].js (per-product SEO) and the drops/newsletter scripts
  - sitemap.xml     every live product URL
  - thumbs/<id>.webp  480px card thumbnails served straight from Cloudflare Pages (no Supabase egress)

Run from the repo root:  python scripts/sync_catalog.py [--no-thumbs]
"""
import concurrent.futures as cf
import datetime
import io
import json
import os
import re
import sys
import urllib.request

SITE = "https://www.puroclassico.com"
THUMB_DIR = "thumbs"
THUMB_PX = 480
PRODUCT_FIELDS = ("title", "brand", "cat", "seller", "img", "price", "usd", "platform", "g")


def load_catalog(path="index.html"):
    html = open(path, encoding="utf-8").read()
    start = html.find("return [", html.find("function loadProducts()"))
    if start < 0:
        sys.exit("loadProducts() array not found in index.html")
    start += len("return ")
    end = html.find("];", start) + 1
    # The array is a JS object literal: quote the bare keys so it parses as JSON.
    return json.loads(re.sub(r'([{,])([A-Za-z_]\w*):', r'\1"\2":', html[start:end]))


def write_if_changed(path, text):
    old = open(path, encoding="utf-8").read() if os.path.exists(path) else None
    if old == text:
        return False
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return True


def build_products_json(items):
    out = {}
    for p in items:
        row = {k: p.get(k, "") for k in PRODUCT_FIELDS}
        if str(row.get("img", "")).startswith("/"):   # site-hosted image: emails/Discord need an absolute URL
            row["img"] = SITE + row["img"]
        if p.get("itemId"):
            row["itemId"] = p["itemId"]
        out[p["id"]] = row
    return json.dumps(out, ensure_ascii=False, separators=(",", ":"))


def build_sitemap(items):
    today = datetime.date.today().isoformat()
    urls = [(SITE + "/", "daily", "1.0"), (SITE + "/privacy.html", "yearly", "0.2"), (SITE + "/terms.html", "yearly", "0.2")]
    urls += [(SITE + "/product/" + p["id"], "weekly", "0.7") for p in items]
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    lines += [f"<url><loc>{u}</loc><lastmod>{today}</lastmod><changefreq>{c}</changefreq><priority>{pr}</priority></url>" for u, c, pr in urls]
    lines.append("</urlset>")
    return "\n".join(lines) + "\n"


def make_thumb(p):
    from PIL import Image
    dest = os.path.join(THUMB_DIR, p["id"] + ".webp")
    if os.path.exists(dest):
        return "skip"
    try:
        req = urllib.request.Request(p["img"], headers={"User-Agent": "puroclassico-thumbs/1.0"})
        raw = urllib.request.urlopen(req, timeout=40).read()
        im = Image.open(io.BytesIO(raw))
        im = im.convert("RGBA") if im.mode in ("RGBA", "LA", "P") else im.convert("RGB")
        im.thumbnail((THUMB_PX, THUMB_PX), Image.LANCZOS)
        im.save(dest, "WEBP", quality=78, method=6)
        return "made"
    except Exception as e:  # a bad source image must not stop the run; the card falls back to the full image
        print("thumb failed", p["id"], str(e)[:80])
        return "fail"


def sync_thumbs(items):
    os.makedirs(THUMB_DIR, exist_ok=True)
    # A tiny 404 page here makes a missing thumbnail a cheap 404 instead of the SPA fallback (the whole index.html).
    write_if_changed(os.path.join(THUMB_DIR, "404.html"), "<!doctype html><title>404</title>\n")
    live = {p["id"] for p in items}
    removed = 0
    for name in os.listdir(THUMB_DIR):
        if name.endswith(".webp") and name[:-5] not in live:
            os.remove(os.path.join(THUMB_DIR, name))
            removed += 1
    todo = [p for p in items if p.get("img")]
    with cf.ThreadPoolExecutor(max_workers=16) as ex:
        results = list(ex.map(make_thumb, todo))
    print(f"thumbs: made {results.count('made')}, kept {results.count('skip')}, failed {results.count('fail')}, removed {removed}")


def main():
    items = load_catalog()
    print("catalog products:", len(items))
    products = build_products_json(items)
    if write_if_changed("products.json", products):
        print("products.json updated")
        # The sitemap's lastmod only moves when the catalog itself changed.
        if write_if_changed("sitemap.xml", build_sitemap(items)):
            print("sitemap.xml updated")
    if "--no-thumbs" not in sys.argv:
        sync_thumbs(items)


if __name__ == "__main__":
    main()
