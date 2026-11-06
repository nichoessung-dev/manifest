# -*- coding: utf-8 -*-
"""Shared bits for the catalogue AI tools (catalog_audit.py, catalog_ai.py, apply_catalog_ai.py, clean_photos.py).

The catalogue lives in index.html inside <script type="application/json" id="pc-catalog">. Read it, never rewrite it
here: only apply_catalog_ai.py writes, and it does surgical string edits.
"""
import io, json, os, re, time, urllib.request, urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TAG = '<script type="application/json" id="pc-catalog">'
SITE = "https://www.puroclassico.com"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36 PuroClassicoCatalogAI/1.0"}
CATS = ["Tops", "Outerwear", "Shoes", "Pants", "Shorts", "Bags", "Accessories", "Headwear", "Toys"]

COLOURS = ["black", "white", "grey", "gray", "navy", "blue", "light blue", "dark blue", "red", "burgundy", "maroon", "wine",
           "pink", "purple", "lilac", "green", "olive", "khaki", "army green", "dark green", "mint", "yellow", "orange",
           "brown", "dark brown", "tan", "beige", "cream", "off-white", "ivory", "camel", "sand", "silver", "gold",
           "multicolour", "multicolor", "charcoal", "teal", "turquoise", "coffee", "apricot", "rose"]


def load_catalog(path=None):
    """(html, items, start, end): items is the parsed list, html[start:end] is the raw JSON text."""
    path = path or os.path.join(ROOT, "index.html")
    html = open(path, encoding="utf-8").read()
    i = html.find(TAG)
    if i < 0:
        raise SystemExit("pc-catalog block not found in " + path)
    s = i + len(TAG)
    e = html.find("</script>", s)
    return html, json.loads(html[s:e]), s, e


def img_url(p):
    """Absolute URL of a find's main photo (the original, never the resized grid copy)."""
    u = p.get("img") or ""
    if u.startswith("/"):
        return SITE + u
    return u


def source_url(p, photos=None):
    """The ORIGINAL photo of a find. Once apply_catalog_ai.py --photos has pointed "img" at the cleaned copy
    (products/pc2/<id>.webp), the original URL is the "src" that clean_photos.py recorded for it."""
    u = img_url(p)
    if "/products/pc2/" in u:
        src = ((photos or {}).get(p["id"]) or {}).get("src")
        if src:
            return src
    return u


def fetch(url, timeout=30, tries=3):
    last = None
    for k in range(tries):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout).read()
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (400, 401, 403, 404):
                break
        except Exception as e:
            last = e
        time.sleep(1.5 * (k + 1))
    raise last


def load_json(path, default):
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception:
        return default


def save_json(path, data):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")
    os.replace(tmp, path)


def no_dash(s):
    """The owner bans the em dash (and its en dash cousin used as one) in all site text."""
    s = re.sub(r"\s*[—–]\s*", " ", s or "")
    return re.sub(r"\s{2,}", " ", s).strip()
