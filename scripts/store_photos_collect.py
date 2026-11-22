# -*- coding: utf-8 -*-
"""Candidate store photos for the partner's finds (owner, 20 Nov 2026; rules in data/store_photos_rules.md).

Step 2 of 3, run where the Brave Search API is reachable (the Claude Code container; GitHub Actions has no Brave key):
  1. GitHub (store-photos.yml step=name): claude-haiku-5-5 names the exact model of each find from its photo + title and
     writes search queries in English, Norwegian, German and French -> data/store_photo_names.json   (rule 12)
  2. HERE, this script: per find, most viewed first (data/stats.json "p"[id][0]):
       - Brave image searches for each named query (local-language ones with that country), Brave web searches for the
         exact name (English + Norwegian) to find store pages that image search misses (miinto, Farfetch-fed shops)
       - 3 search requests per find with SEARCH_PROVIDER serper (Google via serper.dev, SERPER_API_KEY; the default
         when that key is set) or brave (BRAVE_API_KEY): 2 image searches + 1 web search; product pages are read before
         category pages, and listing pages are followed to the products named like the exact model
       - only the MAIN product's gallery is read from a page (up to 16): Shopify <page>.json, the page's own JSON-LD
         Product (never a list of products or other colours), then the main image's product-id family (careofcarl
         <sku>_<n>, SFCC/Scene7 <sku>_<view>) or, for hashed names, the pictures next to it in the page's gallery
         markup that appear about as often as it; recommendations and "you may also like" are left out
       - candidates are grouped by store (host), so step 3 can take one store's complete photoshoot (rules 5, 13)
     No site is excluded for being a marketplace (rule 14: resellers reuse the official photo); only replica sellers and
     buying agents are skipped, which never carry store photos. Images known to be under 800 px are dropped.
  3. GitHub (store-photos.yml step=pick): scripts/store_photos_pick.py chooses, cuts out and uploads.
Writes data/store_photo_candidates.json {"items": {id: {"name", "q", "p": [pages], "c": [[img, page index, w, h,
"s" page gallery | "b" Brave hit], ...]}}}.

  python scripts/store_photos_collect.py [--limit 300] [--offset 0] [--ids 1,2] [--named-only] [--redo]
The Brave key: BRAVE_API_KEY (GitHub secret); without it the request goes keyless (the Claude Code proxy adds one).
"""
import argparse, html as htmlmod, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from catalog_common import COLOURS, ROOT, load_catalog, load_json  # noqa: E402
import store_photos_shards as shards  # noqa: E402

OUT = os.path.join(ROOT, "data", "store_photo_candidates.json")
NAMES = os.path.join(ROOT, "data", "store_photo_names.json")
API = "https://api.search.brave.com/res/v1/"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36"
MIN_SIDE = 800
MAX_HOSTS, PER_HOST, MAX_C = 8, 16, 72  # groups (a page's photoshoot, or a store's loose hits), photos each, total
# replica sellers and buying agents: their photos are never the store's own
SKIP_HOSTS = ("weidian.", "geilicdn.", "taobao.", "tmall.", "1688.", "alicdn.", "yupoo.", "pandabuy", "cnfans", "kakobuy",
              "superbuy", "sugargoo", "hoobuy", "allchinabuy", "mulebuy", "acbuy", "litbuy", "oopbuy", "orientdig", "dhgate.",
              "aliexpress.", "puroclassico.", "wikipedia.", "wikimedia.", "youtube.", "ytimg.", "tiktok.")
CAT_WORD = {"Shoes": "sneakers", "Outerwear": "jacket", "Tops": "", "Pants": "pants", "Shorts": "shorts", "Bags": "bag",
            "Accessories": "", "Headwear": "cap", "Toys": "toy"}
COUNTRY = {"no": "NO", "de": "DE", "fr": "FR", "en": ""}
PAUSE = 1.05
_last = [0.0]
_html = {}  # page -> its HTML, for following product links from listing pages
GENERIC = set("""jacket jackets hooded hoodie hoodies puffer sneakers sneaker trainers shoes low-top high-top men's mens women's
sweater sweatshirt crewneck t-shirt shirt long sleeve sleeves pants trousers jeans shorts zip-up full-zip fleece cotton
leather belt watch steel stainless black white grey navy brown green most likely exact model name unconfirmed selfwinding
oyster perpetual sportswear joggers tracksuit hybrid padded check-lined logo""".split())


def get(url, headers=None, timeout=15):
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers or {"User-Agent": UA}), timeout=timeout) as r:
        return r.read(3_000_000)


PROVIDER = (os.environ.get("SEARCH_PROVIDER") or ("serper" if os.environ.get("SERPER_API_KEY") else "brave")).lower()
SERPER = "https://google.serper.dev/"
requests_used = [0]


def brave(kind, q, country=""):
    url = API + kind + "/search?count=" + ("30" if kind == "images" else "20") + "&q=" + urllib.parse.quote(q)
    if country: url += "&country=" + country
    for k in range(3):
        wait = PAUSE - (time.time() - _last[0])
        if wait > 0: time.sleep(wait)
        _last[0] = time.time()
        try:
            requests_used[0] += 1
            d = json.loads(get(url, {"X-Subscription-Token": os.environ.get("BRAVE_API_KEY") or "x", "Accept": "application/json"}, 20))
            return d.get("results") or [] if kind == "images" else (d.get("web") or {}).get("results") or []
        except urllib.error.HTTPError as e:
            if e.code == 422 and country: return brave(kind, q)  # country not supported: search without it
            if e.code in (401, 402, 403):  # no key or no credit: stop rather than record finds with no candidates
                raise SystemExit(f"Brave Search refused the request (HTTP {e.code}): stopping")
            if e.code != 429: print("  brave", e.code, q, flush=True); return []
        except Exception as e:
            print("  brave", e, flush=True)
        time.sleep(3 * (k + 1))
    return []


def serper(kind, q, country=""):
    """Google results through serper.dev (SERPER_API_KEY): kind "images" -> /images, "web" -> /search."""
    body = json.dumps({"q": q, "gl": (country or "us").lower(), "num": 30 if kind == "images" else 20}).encode()
    for k in range(3):
        try:
            requests_used[0] += 1
            req = urllib.request.Request(SERPER + ("images" if kind == "images" else "search"), data=body, method="POST",
                                         headers={"X-API-KEY": os.environ.get("SERPER_API_KEY") or "", "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as r: d = json.load(r)
            return d.get("images") or [] if kind == "images" else d.get("organic") or []
        except urllib.error.HTTPError as e:
            if e.code in (401, 402, 403):  # no key or no credit: stop rather than record finds with no candidates
                raise SystemExit(f"Serper refused the request (HTTP {e.code}): stopping")
            if e.code != 429: print("  serper", e.code, q, flush=True); return []
        except Exception as e:
            print("  serper", e, flush=True)
        time.sleep(3 * (k + 1))
    return []


def search_images(q, country=""):
    """[(image url, page url, width, height)] from the chosen provider."""
    out = []
    if PROVIDER == "serper":
        for r in serper("images", q, country):
            out.append((r.get("imageUrl") or "", r.get("link") or "", int(r.get("imageWidth") or 0), int(r.get("imageHeight") or 0)))
    else:
        for r in brave("images", q, country):
            pr = r.get("properties") or {}
            out.append((pr.get("url") or "", r.get("url") or "", int(pr.get("width") or 0), int(pr.get("height") or 0)))
    return out


def search_web(q, country=""):
    """[page url] from the chosen provider."""
    if PROVIDER == "serper": return [r.get("link") for r in serper("web", q, country) if r.get("link")]
    return [r.get("url") for r in brave("web", q, country) if r.get("url")]


def host_of(u):
    h = urllib.parse.urlsplit(u).netloc.lower()
    return h[4:] if h.startswith("www.") else h


def skip(u):
    h = host_of(u)
    return not h or any(s in h for s in SKIP_HOSTS)


def strip_colours(q):
    for c in sorted(COLOURS, key=len, reverse=True): q = re.sub(r"(?i)\b" + re.escape(c) + r"\b", " ", q)
    return re.sub(r"\s+", " ", q).strip()


def queries(p, nm):
    """[(query, lang)] from the named model (step 1), or from the title when the find has not been named yet."""
    out = []
    if nm and nm.get("queries"):
        qs = nm["queries"]
        for q in (qs.get("en") or [])[:2]: out.append((q, "en"))
        for lang in ("no", "de", "fr"):
            v = qs.get(lang)
            for q in ([v] if isinstance(v, str) else (v or []))[:1]: out.append((q, lang))
    if not out:
        title = re.sub(r"\s+", " ", p.get("title") or "").strip()
        brand = p.get("brand") or ""
        q1 = title if brand.lower() in title.lower() else f"{brand} {title}"
        q2 = strip_colours(q1)
        w = CAT_WORD.get(p.get("cat"), "")
        if w and w not in q2.lower(): q2 += " " + w
        out = [(q1, "en")] + ([(q2, "en")] if q2.lower() != q1.lower() else [])
    seen, res = set(), []
    for q, l in out:
        q = re.sub(r"\s+", " ", q or "").strip()
        if q and q.lower() not in seen: seen.add(q.lower()); res.append((q, l))
    return res


IMG_RE = re.compile(r"""https?:(?:\\?/){2}[^\s"'<>()\\]+?\.(?:jpe?g|png|webp|avif)(?:\?[^\s"'<>()\\]*)?""", re.I)
REL_RE = re.compile(r"""(?:src|data-src|data-zoom|data-large|href)=["']((?!https?:|//|data:)[^"'\s]+?\.(?:jpe?g|png|webp)(?:\?[^"'\s]*)?)["']""", re.I)
# image servers whose URLs have no file extension: Scene7 (/is/image/), Salsify, Cloudinary-style upload paths
IMG_NOEXT_RE = re.compile(r"""https?:(?:\\?/){2}[^\s"'<>()\\]+?/(?:is/image|image/upload)/[^\s"'<>()\\?]+(?:\?[^\s"'<>()\\]*)?""", re.I)
JUNK = re.compile(r"logo|icon|sprite|favicon|placeholder|payment|badge|flag|banner|avatar|swatch|loader|spinner|klarna|"
                  r"/thumb|_thumb|-thumb|thumbnail|_small|_xs\b|50x50|100x100|1x1", re.I)


_links = {}  # listing page -> [(product url, product name)] found in its JSON-LD ItemList
PER_PAGE = 16
SIZE_HINT = re.compile(r"zoom|large|original|full|2000|1600|1500|1200|hi-?res", re.I)


def _abs(page, s):
    s = htmlmod.unescape(s or "").replace("\\/", "/").replace("\\u002F", "/").strip()
    if s.startswith("//"): s = "https:" + s
    return urllib.parse.urljoin(page, s)


def _stem(path):
    return re.sub(r"\.(jpe?g|png|webp|avif|tiff?)$", "", os.path.basename(path), flags=re.I)


def _family(url):
    """The product id at the start of an image file name (careofcarl 26158811r_1, Scene7 SKU_ALT1, SFCC 12345_A),
    or None for hashes and UUIDs that carry no product id."""
    st = _stem(urllib.parse.urlsplit(url).path)
    if re.fullmatch(r"[0-9a-f]{24,}|[0-9A-Fa-f]{8}(-[0-9A-Fa-f]{4}){3}-[0-9A-Fa-f]{12}", st): return None
    fam = re.sub(r"_[A-Za-z0-9*]{1,6}$", "", st)  # the view suffix: _1, _A, _FLAT, _ALT2
    if "_" in fam: fam = fam.split("_")[0] if re.search(r"\d", fam.split("_")[0]) else fam
    return fam.lower() if len(fam) >= 5 and re.search(r"\d", fam) and re.fullmatch(r"[A-Za-z0-9*-]+", fam) else None


def _ld_products(h):
    """(Product nodes outside lists, [(url, name)] of products inside an ItemList)."""
    own, listed = [], []
    for blk in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', h, re.S | re.I):
        try: data = json.loads(blk.strip())
        except Exception: continue
        stack = [(data, False)]
        while stack:
            x, in_list = stack.pop(0)
            if isinstance(x, list):
                stack.extend((v, in_list) for v in x); continue
            if not isinstance(x, dict): continue
            t = x.get("@type"); t = " ".join(t) if isinstance(t, list) else str(t or "")
            if t.lower() in ("itemlist", "offercatalog", "collectionpage"):
                stack.extend((v, True) for v in x.values() if isinstance(v, (dict, list))); continue
            if t.lower() in ("product", "productgroup"):
                if in_list: listed.append((x.get("url") or (x.get("offers") or {}).get("url") if isinstance(x.get("offers"), dict) else x.get("url"), x.get("name") or ""))
                else: own.append(x)
                continue  # never read related products nested inside a product
            stack.extend((v, in_list) for v in x.values() if isinstance(v, (dict, list)))
    return own, listed


def _ld_images(node):
    out = []
    for k in ("image", "images"):
        im = node.get(k)
        for v in (im if isinstance(im, list) else [im]):
            if isinstance(v, dict): v = v.get("url") or v.get("contentUrl")
            if isinstance(v, str) and v: out.append(v)
    return out  # never a ProductGroup's variants: those are the other colours


def page_gallery(page):
    """The MAIN product's gallery on a store page (up to 16, full size), never the recommendations, other colours or
    other products on it. A listing page (several products) gives no photos; its products are kept in _links."""
    u = urllib.parse.urlsplit(page)
    m = re.search(r"/products/([^/?#]+)", u.path)
    if m:  # Shopify: the product's own media, in the store's order
        try:
            d = json.loads(get(f"{u.scheme}://{u.netloc}{u.path[:m.end()]}.json", {"User-Agent": UA, "Accept": "application/json"}))
            out = []
            for im in ((d.get("product") or {}).get("images") or [])[:PER_PAGE]:
                s = im.get("src") or ""
                if s.startswith("//"): s = "https:" + s
                if s: out.append((s, im.get("width") or 0, im.get("height") or 0))
            if out: return out
        except Exception:
            pass
    try:
        h = get(page).decode("utf-8", "replace")
    except Exception:
        return []
    _html[page] = h
    found = []

    def add(s):
        s = _abs(page, s)
        sz = re.search(r"-(\d{2,4})x(\d{2,4})\.(?:jpe?g|png|webp)", s, re.I)  # WordPress size copies
        if sz and max(int(sz.group(1)), int(sz.group(2))) < MIN_SIDE: return
        if s.startswith("http") and not JUNK.search(s) and s not in found: found.append(s)

    own, listed = _ld_products(h)
    if len(own) > 1:  # several top-level products: keep the one this page is about, if any
        mine = [x for x in own if (x.get("url") or "").split("?")[0].rstrip("/") == page.split("?")[0].rstrip("/")]
        if not mine: listed += [(x.get("url"), x.get("name") or "") for x in own]
        own = mine
    if not own and len(listed) >= 2:  # a listing: no photos, its products may be followed
        _links[page] = [(_abs(page, l), n) for l, n in listed if l]
        return []
    ld_imgs = [_abs(page, s) for x in own[:1] for s in _ld_images(x)]
    og = re.search(r'<meta[^>]+property=["\']og:image(?::secure_url)?["\'][^>]+content=["\']([^"\']+)', h, re.I) or \
        re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image', h, re.I)
    main = _abs(page, og.group(1)) if og else (ld_imgs[0] if ld_imgs else "")
    if not main:
        return []
    ms = urllib.parse.urlsplit(main)
    # every image URL on the page with its positions: absolute ones anywhere, relative ones in src/data-src/href
    occ = {}
    for mt in IMG_RE.finditer(h): occ.setdefault(_abs(page, mt.group(0)), []).append(mt.start())
    for mt in REL_RE.finditer(h): occ.setdefault(_abs(page, mt.group(1)), []).append(mt.start(1))
    for mt in IMG_NOEXT_RE.finditer(h): occ.setdefault(_abs(page, mt.group(0)), []).append(mt.start())
    by_stem = {}  # one entry per picture: all its URLs (sizes, formats) and every position it appears at
    for s, pos in occ.items():
        if s.split("?")[0].lower().endswith(".avif"): continue
        sp = urllib.parse.urlsplit(s)
        key = (sp.netloc, _stem(sp.path))
        e = by_stem.setdefault(key, {"urls": [], "pos": []}); e["urls"].append(s); e["pos"] += pos

    def best_url(urls):
        def score(x):
            q = urllib.parse.parse_qs(urllib.parse.urlsplit(x).query)
            wid = max([int(v) for k in ("wid", "width", "w", "sw") for v in q.get(k, []) if v.isdigit()] or [0])
            return (bool(SIZE_HINT.search(x)), wid, -len(x))
        b = max(urls, key=score)
        bq = urllib.parse.urlsplit(b)
        if ms.query and bq.netloc == ms.netloc and not re.search(r"(^|&)(wid|width|w)=\d{3,}", bq.query) and re.search(r"(wid|width|w)=\d{3,}", ms.query):
            b = f"{bq.scheme}://{bq.netloc}{bq.path}?{ms.query}"  # the main image's size parameters (miinto)
        return b

    mkey = (ms.netloc, _stem(ms.path))
    fam = _family(main)
    pics = []
    # 1. the product id family of the main image (careofcarl 26158811r_1..4, Scene7/SFCC SKU sets)
    if fam:
        pics = [k for k in by_stem if k[0] == ms.netloc and (_family("x/" + k[1] + ".jpg") == fam)]
    # 2. else the gallery around the main image: pictures on its host that sit next to it in the page (chained), and
    #    appear at least half as often as the gallery's typical picture (recommendations appear once or twice)
    if len(pics) < 2 and mkey in by_stem:
        near, frontier, D = {mkey}, [mkey], 2500
        cand = {k: v for k, v in by_stem.items() if k[0] == ms.netloc}
        while frontier:
            k0 = frontier.pop()
            p0 = cand[k0]["pos"]
            for k, v in cand.items():
                if k in near: continue
                if any(abs(a - b) <= D for a in v["pos"] for b in p0):
                    near.add(k); frontier.append(k)
        counts = sorted((len(cand[k]["pos"]) for k in near if k != mkey), reverse=True)
        if counts:
            typical = counts[min(len(counts) - 1, 2)]
            near = {k for k in near if k == mkey or len(cand[k]["pos"]) >= max(2, typical / 2)}
        pics = sorted(near, key=lambda k: min(cand[k]["pos"]))
    have = set()
    for k in pics:
        add(best_url(by_stem[k]["urls"])); have.add(k[1])
    for x in ld_imgs + [main]:  # the JSON-LD photos and the main image, unless the gallery already has them
        if _stem(urllib.parse.urlsplit(x).path) not in have: add(x); have.add(_stem(urllib.parse.urlsplit(x).path))
    return [(s, 0, 0) for s in found[:PER_PAGE]]


CATEGORY_PATH = re.compile(r"/(c|l|w|b|s|collections?|categor(y|ies)|brands?|search|shop|sale|men|women|herre|dame|"
                           r"herren|damen|homme|femme)(/|$)|[?&](k|q|query|search)=", re.I)
PRODUCT_PATH = re.compile(r"/(products?|p|item|itm|dp|artikel|produkt|produit)/|-p\d{5,}|/p-[a-z0-9-]{8,}|\d{6,}|\.html?$", re.I)


def page_score(url, keys):
    """Product pages first (the exact model's name in the address, a product-style path), category pages last."""
    path = urllib.parse.urlsplit(url).path.lower() + "?" + urllib.parse.urlsplit(url).query.lower()
    sc = 2 * sum(k in path for k in keys) + (1 if PRODUCT_PATH.search(path) else 0)
    if CATEGORY_PATH.search(path) and not PRODUCT_PATH.search(path): sc -= 3
    return sc


def collect(p, nm):
    """3 search requests per find (Serper/Google or Brave, SEARCH_PROVIDER): 2 image searches (the exact name in English,
    then the Norwegian store wording with that country) and 1 web search for store pages with the exact name; then each
    store page's own gallery."""
    qs = queries(p, nm)
    img_qs = ([x for x in qs if x[1] == "en"][:1] + [x for x in qs if x[1] == "no"][:1]) or qs[:2]
    if len(img_qs) < 2: img_qs = (img_qs + [x for x in qs if x not in img_qs])[:2]
    hits, pages_rank = [], {}
    for q, lang in img_qs:
        for img, page, w, h in search_images(q, COUNTRY.get(lang, "")):
            if not img or not page or skip(page) or skip(img): continue
            if max(w, h) and max(w, h) < MIN_SIDE: continue
            hits.append((img, page, w, h))
            pages_rank[page] = pages_rank.get(page, 0) + 1
    name = re.sub(r"\s*\([^)]*\)", "", (nm or {}).get("name") or "").strip() or qs[0][0]
    brand = (p.get("brand") or "").lower()
    keys = [w for w in re.findall(r"[a-z0-9'-]{5,}", name.lower()) if w not in GENERIC and w not in brand]
    web = []
    for u in search_web(name):
        if not skip(u) and u not in web: web.append(u)
    web.sort(key=lambda u: -page_score(u, keys))
    img_pages = sorted(pages_rank, key=lambda pg: (-pages_rank[pg], -page_score(pg, keys)))
    to_read = list(dict.fromkeys(web[:10] + img_pages[:8]))[:16]
    with ThreadPoolExecutor(8) as ex:
        galleries = dict(zip(to_read, ex.map(page_gallery, to_read)))
    # listing pages (a store's brand or category page): follow its products named like the exact model
    follow = []
    if keys:
        for page in to_read:
            if galleries.get(page) and page_score(page, keys) >= 2: continue
            links = [(l, n) for l, n in _links.get(page, []) if any(k in (l + " " + n).lower() for k in keys)]
            if not links:
                for href in re.findall(r'href=["\']([^"\'#]+)["\']', _html.get(page) or ""):
                    full = urllib.parse.urljoin(page, htmlmod.unescape(href))
                    slug = urllib.parse.urlsplit(full).path.lower()
                    if host_of(full) == host_of(page) and any(k in slug for k in keys) \
                            and not slug.endswith((".jpg", ".png", ".webp", ".css", ".js")):
                        links.append((full, ""))
            n_page = 0
            for l, _ in links:
                if l in to_read or l in follow: continue
                follow.append(l); n_page += 1
                if n_page >= 3: break
        follow = sorted(follow, key=lambda u: -page_score(u, keys))[:10]
        with ThreadPoolExecutor(8) as ex:
            galleries.update(zip(follow, ex.map(page_gallery, follow)))
        to_read = follow + to_read
    pages, cands, seen = [], [], set()
    by_host = {}

    def add(img, page, w, h, kind):
        key = re.sub(r"[?#].*$", "", img) if "miinto" not in img else img
        if key in seen or skip(img): return
        seen.add(key)
        # a page with its own gallery is one photoshoot; loose image hits group by store
        by_host.setdefault(page if galleries.get(page) else host_of(page), []).append([img, page, w, h, kind])

    for page in to_read:
        for s, w, h in galleries.get(page) or []: add(s, page, w, h, "s")
    for img, page, w, h in hits: add(img, page, w, h, "b")
    # stores with a page gallery (a whole photoshoot) first, then by how many photos they have
    order = sorted(by_host, key=lambda hh: (-any(c[4] == "s" for c in by_host[hh]), -len(by_host[hh])))
    for hh in order[:MAX_HOSTS]:
        for c in by_host[hh][:PER_HOST]:
            if len(cands) >= MAX_C: break
            if c[1] not in pages: pages.append(c[1])
            cands.append([c[0], pages.index(c[1]), int(c[2] or 0), int(c[3] or 0), c[4]])
    return {"v": 2 if nm else 1, "name": name, "q": [q for q, _ in qs], "p": pages, "c": cands}


# ---- deep mode (owner, 21 Nov 2026: a second, deeper search for the finds whose kept set has fewer than 3 photos) ----
# About 6 search credits per find (Serper: a request with more than 10 results costs 2): 2 image searches (30 results)
# and 2 web searches (10 results) aimed at the brand's own store and the big retailers, with the owner's "search_as"
# name when there is one. The new candidates are ADDED to the first pass's (new first); the picker sees both.
OWNER = os.path.join(ROOT, "data", "store_photos_owner.json")
RETAIL1 = ["ssense.com", "farfetch.com", "endclothing.com", "mytheresa.com", "mrporter.com", "zalando.co.uk"]
RETAIL2 = ["net-a-porter.com", "nordstrom.com", "selfridges.com", "luisaviaroma.com", "zalando.de", "asos.com"]
SNEAK1 = ["stockx.com", "goat.com", "flightclub.com", "endclothing.com", "ssense.com", "kith.com"]
SNEAK2 = ["sneakersnstuff.com", "footlocker.com", "size.co.uk", "farfetch.com", "zalando.co.uk"]
BRAND_SITE = {
    "adidas": "adidas.com", "nike": "nike.com", "jordan": "nike.com", "stussy": "stussy.com", "louis vuitton": "louisvuitton.com",
    "moncler": "moncler.com", "stone island": "stoneisland.com", "ralph lauren": "ralphlauren.com", "polo": "ralphlauren.com",
    "gucci": "gucci.com", "dior": "dior.com", "burberry": "burberry.com", "chrome hearts": "chromehearts.com",
    "balenciaga": "balenciaga.com", "prada": "prada.com", "the north face": "thenorthface.com", "puma": "puma.com",
    "lacoste": "lacoste.com", "under armour": "underarmour.com", "corteiz": "crtz.xyz", "fendi": "fendi.com", "amiri": "amiri.com",
    "bape": "bape.com", "denim tears": "denimtears.com", "goyard": "goyard.com", "chanel": "chanel.com", "essentials": "fearofgod.com",
    "fear of god": "fearofgod.com", "new balance": "newbalance.com", "maison margiela": "maisonmargiela.com",
    "mm6": "maisonmargiela.com", "ami": "amiparis.com", "umbro": "umbro.com", "palm angels": "palmangels.com",
    "trapstar": "trapstarlondon.com", "off-white": "off---white.com", "casablanca": "casablancaparis.com",
    "lululemon": "lululemon.com", "loewe": "loewe.com", "givenchy": "givenchy.com", "apple": "apple.com",
    "carhartt": "carhartt-wip.com", "dolce & gabbana": "dolcegabbana.com", "gallery dept": "gallerydept.com",
    "c.p. company": "cpcompany.com", "dsquared2": "dsquared2.com", "hermès": "hermes.com", "hermes": "hermes.com",
    "tommy hilfiger": "tommy.com", "versace": "versace.com", "patagonia": "patagonia.com", "supreme": "supremenewyork.com",
    "dyson": "dyson.com", "saint laurent": "ysl.com", "ray-ban": "ray-ban.com", "boss": "hugoboss.com",
    "represent": "representclo.com", "valentino": "valentino.com", "hellstar": "hellstar.com", "canada goose": "canadagoose.com",
    "cartier": "cartier.com", "philipp plein": "plein.com", "loro piana": "loropiana.com", "marshall": "marshall.com",
    "rhude": "rhude.com", "arc'teryx": "arcteryx.com", "arcteryx": "arcteryx.com", "parajumpers": "parajumpers.it",
    "acne studios": "acnestudios.com", "rolex": "rolex.com", "audemars piguet": "audemarspiguet.com",
    "bottega veneta": "bottegaveneta.com", "celine": "celine.com", "miu miu": "miumiu.com", "thom browne": "thombrowne.com",
    "nike sb": "nike.com", "asics": "asics.com", "salomon": "salomon.com", "vans": "vans.com", "converse": "converse.com",
    "timberland": "timberland.com", "ugg": "ugg.com", "birkenstock": "birkenstock.com", "oakley": "oakley.com",
    "kenzo": "kenzo.com", "alexander mcqueen": "alexandermcqueen.com", "rick owens": "rickowens.eu", "vetements": "vetements.com",
    "golden goose": "goldengoose.com", "on": "on.com", "hoka": "hoka.com", "napapijri": "napapijri.com", "diesel": "diesel.com",
    "palace": "palaceskateboards.com", "kith": "kith.com", "sp5der": "sp5derworldwide.com", "broken planet": "brokenplanet.com",
    "syna": "synaworld.com", "nofs": "nofs.co.uk", "psg": "store.psg.fr", "paris saint-germain": "store.psg.fr",
}


def brand_site(p, name):
    """The brand's own store domain, from the find's brand or the named model (a team shirt's maker: Nike, Adidas, Puma)."""
    for j, text in enumerate(((p.get("brand") or "").lower(), (name or "").lower())):
        if text in BRAND_SITE: return BRAND_SITE[text]
        for k in sorted(BRAND_SITE, key=len, reverse=True):
            if j and len(k) < 4: continue  # "on", "ami" inside a model name are words, not brands
            if re.search(r"(?<![a-z])" + re.escape(k) + r"(?![a-z])", text): return BRAND_SITE[k]
    return ""


def sites(ds):
    return "(" + " OR ".join("site:" + d for d in dict.fromkeys(d for d in ds if d)) + ")"


# retailer image servers whose other views can be named from one photo (checked 21 Nov 2026): SSENSE <sku>_<0-6>,
# mytheresa P<id>[_b1|_b2|_d1..], MR PORTER / NET-A-PORTER /<id>/<in|fr|bk|cu|ou|e1|e2>/, Moncler and Stone Island
# (Thron) <code>_<view>, Ralph Lauren (Scene7) s7-<id>_<view>. Views that do not exist are dropped by the picker (404).
SIB = [
    (re.compile(r"(img\.ssensemedia\.com/images/)[^/]+(/[0-9A-Z]+_)\d(/.*)"), lambda m: [f"https://{m.group(1)}b_white,g_center,f_auto,q_auto:best{m.group(2)}{k}{m.group(3)}" for k in range(0, 7)]),
    (re.compile(r"(mytheresa\.com/image/[\d/]+/P\d+)(?:_[a-z]\d)?(\.jpg)"), lambda m: [f"https://www.{m.group(1)}{v}{m.group(2)}" for v in ("", "_b1", "_b2", "_d1", "_d2", "_d3")]),
    (re.compile(r"((?:mrporter|net-a-porter|yoox|theoutnet)\.com/variants/images/\d+/)[a-z0-9]+(/w\d+_q\d+\.jpg)"), lambda m: [f"https://www.{m.group(1)}{v}{m.group(2)}" for v in ("in", "fr", "bk", "cu", "ou", "e1", "e2")]),
    (re.compile(r"(moncler-cdn\.thron\.com/.*?/contents/)([A-Z0-9]+)_[A-Z0-9](/image/)\2_[A-Z0-9]"), lambda m: [f"https://{m.group(1)}{m.group(2)}_{v}{m.group(3)}{m.group(2)}_{v}" for v in ("F", "1", "2", "3", "4", "5")]),
    (re.compile(r"(stoneisland-cdn\.thron\.com/delivery/public/image/stoneisland/)([A-Z0-9]+)_[A-Z](/[^/]+/std/0x0/)\2_[A-Z](\.jpg)"), lambda m: [f"https://{m.group(1)}{m.group(2)}_{v}{m.group(3)}{m.group(2)}_{v}{m.group(4)}" for v in "ABCDFR"]),
    (re.compile(r"(dtcralphlauren\.scene7\.com/is/image/PoloGSI/s7-\d+)_[a-z0-9]+(\?.*)?$"), lambda m: [f"https://{m.group(1)}_{v}{m.group(2) or ''}" for v in ("lifestyle", "alternate1", "alternate2", "alternate3", "alternate4", "alternate10")]),
]


def siblings(img):
    """The other views of a retailer photo, or [] for servers without a known naming."""
    s = re.sub(r"^https?://(www\.)?", "", img)
    for rx, f in SIB:
        m = rx.search(s)
        if m: return f(m)
    if "farfetch-contents.com" in img: return [re.sub(r"_(\d{3,4})\.jpg", "_1000.jpg", img)]
    return []


credits_used = [0]


# pass 2 (22 Nov 2026, from the AI photo ratings; data/store_photos_pass2.json): stricter matching. The colour is the
# one in the find's TITLE when it names one; "fresh" finds (the rated main is a different item) are searched from scratch
# with the title as the name and never keep the earlier candidates; finds already searched by the first deep pass get
# other queries ("wide": no site filter, the exact name quoted, European stores) instead of the same ones again.
PASS2 = os.path.join(ROOT, "data", "store_photos_pass2.json")
EU = ["miinto.no", "miinto.de", "zalando.no", "sneakersnstuff.com", "kickz.com", "careofcarl.com", "boozt.com", "breuninger.com"]


def title_colour(title, brand=""):
    """The colour(s) the title names, in title order ("Navy White" -> "navy/white"); brand words are not colours
    (Off-White, Purple Brand). Pass 2 first took the longest match alone, so "Navy White" searched for white
    (Golden Goose, 22 Nov 2026: 13 of 32 two-colour finds got another colourway)."""
    t = " " + re.sub(r"[^a-z0-9/ -]", " ", (title or "").lower()) + " "
    for b in (brand or "").lower().split("/"):
        if b and any(c in b for c in COLOURS): t = t.replace(b.strip(), " ")
    t = t.replace("off-white", " ").replace("purple brand", " ")
    hits = []
    for c in sorted(COLOURS, key=len, reverse=True):
        k = t.find(" " + c + " ")
        if k >= 0 and not any(c in h for _, h in hits): hits.append((k, c))
    return "/".join(c for _, c in sorted(hits)[:2])


def deep_collect(p, nm, entry, own_call=None, hint=None):
    """The deep search for one find: returns the merged entry (new candidates first, then the first pass's)."""
    nm = nm or {}
    own_call = own_call or {}
    hint = hint or {}
    wide = bool(hint) and bool((entry or {}).get("deep")) and hint.get("mode") != "fresh"
    if hint.get("mode") == "fresh": entry = None          # never the earlier (mismatched) candidates
    name = re.sub(r"\s*\([^)]*\)", "", own_call.get("search_as") or hint.get("search_as") or nm.get("name") or (entry or {}).get("name") or p.get("title") or "").strip()
    colour = (hint.get("colour") or nm.get("colour") or "").strip() if not own_call.get("search_as") else ""
    base = name if not colour or colour.lower() in name.lower() else f"{name} {colour}"
    shoes = p.get("cat") == "Shoes" or re.search(r"(?i)sneaker|trainer|shoe|dunk|jordan \d|yeezy|air max|air force", name)
    r1, r2 = (SNEAK1, SNEAK2) if shoes else (RETAIL1, RETAIL2)
    bs = brand_site(p, name)
    if wide:
        exact = f'"{name}" {colour}'.strip() if colour and colour.lower() not in name.lower() else f'"{name}"'
        qs = [("images", base, 30), ("images", f"{base} {sites(EU)}", 30), ("web", exact, 10), ("web", f"{base} {sites([bs] + EU[:3])}", 10)]
    else:
        qs = [("images", f"{base} {sites(r1)}", 30), ("images", f"{base} {sites([bs] + r2)}", 30),
              ("web", f"{base} {sites(r1)}", 10), ("web", f"{base} {sites([bs] + r2)}", 10)]
    hits, web, pages_rank = [], [], {}
    for kind, q, num in qs:
        credits_used[0] += 2 if num > 10 else 1
        if kind == "images":
            for r in serper_n("images", q, num):
                img, page = r.get("imageUrl") or "", r.get("link") or ""
                w, h = int(r.get("imageWidth") or 0), int(r.get("imageHeight") or 0)
                if not img or not page or skip(page) or skip(img): continue
                if max(w, h) and max(w, h) < MIN_SIDE: continue
                hits.append((img, page, w, h)); pages_rank[page] = pages_rank.get(page, 0) + 1
        else:
            for r in serper_n("web", q, num):
                u = r.get("link")
                if u and not skip(u) and u not in web: web.append(u)
    brand = (p.get("brand") or "").lower()
    keys = [w for w in re.findall(r"[a-z0-9'-]{5,}", name.lower()) if w not in GENERIC and w not in brand]
    web.sort(key=lambda u: -page_score(u, keys))
    img_pages = sorted(pages_rank, key=lambda pg: (-pages_rank[pg], -page_score(pg, keys)))
    to_read = list(dict.fromkeys(web[:10] + img_pages[:6]))[:14]
    with ThreadPoolExecutor(8) as ex:
        galleries = dict(zip(to_read, ex.map(page_gallery, to_read)))
    old_seen = {re.sub(r"[?#].*$", "", c[0]) for c in (entry or {}).get("c") or []}
    seen, by_grp = set(old_seen), {}

    def add(img, page, w, h, kind, grp):
        key = re.sub(r"[?#].*$", "", img) if "miinto" not in img and "scene7" not in img else img
        if key in seen or skip(img): return
        seen.add(key); by_grp.setdefault(grp, []).append([img, page, w, h, kind])
    for page in to_read:
        for s, w, h in galleries.get(page) or []: add(s.replace("__IMAGE_PARAMS__", "b_white,g_center,f_auto,q_auto:best"), page, w, h, "s", page)
    # a retailer hit whose other views can be named becomes that page's photoshoot (kind "s"), the hit first
    for img, page, w, h in hits:
        img = img.replace("__IMAGE_PARAMS__", "b_white,g_center,f_auto,q_auto:best")
        sib = siblings(img)
        if sib and not galleries.get(page):
            galleries[page] = [1]
            add(img, page, w, h, "s", page)
            for s in sib: add(s, page, 0, 0, "s", page)
        else:
            add(img, page, w, h, "s" if galleries.get(page) else "b", page if galleries.get(page) else host_of(page))
    order = sorted(by_grp, key=lambda g: (-any(c[4] == "s" for c in by_grp[g]), -len(by_grp[g])))
    e = {k: v for k, v in (entry or {}).items()}
    pages = list(e.get("p") or [])
    new = []
    for g in order[:8]:
        for c in by_grp[g][:14]:
            if len(new) >= 64: break
            if c[1] not in pages: pages.append(c[1])
            new.append([c[0], pages.index(c[1]), int(c[2] or 0), int(c[3] or 0), c[4]])
    e["p"], e["c"] = pages, new + list(e.get("c") or [])
    e.setdefault("name", name)
    e["deep"] = {"n": len(new), "q": [q for _, q, _ in qs], "name": name}
    if hint: e["deep"]["pass"] = 2; e["deep"]["mode"] = "fresh" if hint.get("mode") == "fresh" else ("wide" if wide else "deep")
    return e


def serper_n(kind, q, num):
    """serper() with an explicit result count (credits: 1 for up to 10 results, 2 above)."""
    body = json.dumps({"q": q, "gl": "us", "num": num}).encode()
    for k in range(3):
        try:
            requests_used[0] += 1
            req = urllib.request.Request(SERPER + ("images" if kind == "images" else "search"), data=body, method="POST",
                                         headers={"X-API-KEY": os.environ.get("SERPER_API_KEY") or "", "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as r: d = json.load(r)
            return d.get("images") or [] if kind == "images" else d.get("organic") or []
        except urllib.error.HTTPError as e:
            if e.code in (401, 402, 403): raise SystemExit(f"Serper refused the request (HTTP {e.code}): stopping")
            if e.code != 429: print("  serper", e.code, q[:80], flush=True); return []
        except Exception as e:
            print("  serper", e, flush=True)
        time.sleep(3 * (k + 1))
    return []


def read_ids(a):
    ids = [i for i in (a.ids or "").split(",") if i]
    if getattr(a, "ids_file", ""):
        with open(os.path.join(ROOT, a.ids_file) if not os.path.isabs(a.ids_file) else a.ids_file, encoding="utf-8") as f:
            ids += [i for i in re.split(r"[\s,]+", f.read()) if i]
    return list(dict.fromkeys(ids))


def run_deep(a, shard, by, names):
    out = shards.path("cands", shard)
    own = load_json(out, {"items": {}})
    data = shards.merged("cands")["items"]
    owner = load_json(OWNER, {}) or {}
    hide = set((load_json(os.path.join(ROOT, "data", "report_overrides.json"), {}) or {}).get("hide") or [])
    hints = {k: v for k, v in (load_json(PASS2, {}) if a.pass2 else {}).items() if not k.startswith("_")}
    stats = (load_json(os.path.join(ROOT, "data", "stats.json"), {}) or {}).get("p") or {}
    want = sorted(hints, key=lambda i: (-(stats.get(i) or [0])[0], i)) if a.pass2 else read_ids(a)
    ids = [i for i in want if i in by and i not in hide and shards.mine(i, shard)]
    level = 2 if a.pass2 else 1
    searched = lambda i: bool((data.get(i) or {}).get("deep")) and ((data.get(i) or {}).get("deep") or {}).get("pass", 1) >= level
    todo = [i for i in ids if a.redo or not searched(i)][:a.limit or None]
    print(f"deep search: {len(ids)} target finds in shard {a.shard}, {len(todo)} to search", flush=True)
    try:
        for n, i in enumerate(todo, 1):
            try:
                e = deep_collect(by[i], names.get(i), data.get(i), owner.get(i) if isinstance(owner.get(i), dict) else None, hints.get(i))
            except SystemExit:
                raise
            except Exception as ex:
                print(f"  {i} failed: {ex!r}", flush=True); continue
            own["items"][i] = e
            hosts = {host_of(e["p"][c[1]]) for c in e["c"][:e["deep"]["n"]]}
            print(f"[{n}/{len(todo)}] {i} {e['deep']['name']}: {e['deep']['n']} new candidates from {len(hosts)} stores "
                  f"(+{len(e['c']) - e['deep']['n']} from the first pass)", flush=True)
            if n % 10 == 0: save(own, out)
    finally:
        save(own, out)
    data = shards.merged("cands")["items"]
    left = len([i for i in ids if not searched(i)])
    print(f"deep search done: {len(todo)} finds, serper credits used: {credits_used[0]} "
          f"({credits_used[0] / max(1, len(todo)):.1f} per find); deep remaining {left}")


def partner_ids(items):
    swaps = (load_json(os.path.join(ROOT, "data", "link_swaps.json"), {}) or {}).get("swaps") or {}
    stats = (load_json(os.path.join(ROOT, "data", "stats.json"), {}) or {}).get("p") or {}
    by = {p["id"]: p for p in items}
    ids = [i for i in swaps if i in by]
    ids.sort(key=lambda i: (-(stats.get(i) or [0])[0], i))
    return ids, by


def save(data, out=None):
    out = out or OUT
    os.makedirs(os.path.dirname(out), exist_ok=True)
    tmp = out + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("{\"items\": {\n")
        rows = [json.dumps(k) + ": " + json.dumps(v, ensure_ascii=False, separators=(",", ":")) for k, v in data["items"].items()]
        f.write(",\n".join(rows))
        f.write("\n}}\n")
    os.replace(tmp, out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=300)
    ap.add_argument("--offset", type=int, default=0)
    ap.add_argument("--ids", default="")
    ap.add_argument("--redo", action="store_true")
    ap.add_argument("--named-only", action="store_true", help="the next --limit finds that are named but not searched yet")
    ap.add_argument("--shard", default="0/1", help="k/n: only the finds of shard k of n (see store_photos_shards.py)")
    ap.add_argument("--deep", action="store_true", help="the deeper second search (brand store + big retailers), added to the first pass")
    ap.add_argument("--ids-file", default="", help="a file of ids (comma or whitespace separated), with --deep")
    ap.add_argument("--pass2", action="store_true", help="with --deep: the targets and hints of data/store_photos_pass2.json")
    a = ap.parse_args()
    shard = shards.parse(a.shard)
    ids, by = partner_ids(load_catalog()[1])
    if a.deep: return run_deep(a, shard, by, shards.merged("names")["items"])
    ids = [i for i in ids if shards.mine(i, shard)]
    names = shards.merged("names")["items"]
    out = shards.path("cands", shard)
    own = load_json(out, {"items": {}})  # this shard's own file: the only one it writes
    data = shards.merged("cands")  # every shard's searches: what is done already
    # done = searched with the find's exact model name (v2); entries from before the naming step are searched again
    # an entry with no candidates (the search was refused, e.g. Brave out of searches) is searched again
    done = lambda i: ((data["items"].get(i) or {}).get("v") == 2 and len((data["items"].get(i) or {}).get("c") or []) > 0) or (i not in names and i in data["items"])
    if a.ids: todo = [i for i in a.ids.split(",") if i and i in by and (a.redo or not done(i))]
    elif a.named_only: todo = [i for i in ids if i in names and (a.redo or not done(i))][a.offset:a.offset + a.limit]
    else: todo = [i for i in ids[a.offset:a.offset + a.limit] if a.redo or not done(i)]
    ids = todo
    print(f"{len(ids)} partner finds asked, {len(todo)} to search", flush=True)
    try:
        _run(todo, by, names, own, out)
    finally:
        save(own, out)
    print(f"done, {len(own['items'])} finds in {os.path.relpath(out, ROOT)}; {PROVIDER} requests used: {requests_used[0]} "
          f"({requests_used[0] / max(1, len(todo)):.1f} per find)")


def _run(todo, by, names, data, out):
    for n, i in enumerate(todo, 1):
        p = by[i]
        try:
            data["items"][i] = collect(p, names.get(i))
        except Exception as e:
            print(f"  {i} failed: {e!r}", flush=True); continue
        e = data["items"][i]
        hosts = {host_of(e["p"][c[1]]) for c in e["c"]}
        print(f"[{n}/{len(todo)}] {i} {e['name']}: {len(e['c'])} candidates from {len(hosts)} stores", flush=True)
        if n % 10 == 0: save(data, out)


if __name__ == "__main__":
    main()
