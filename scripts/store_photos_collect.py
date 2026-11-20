# -*- coding: utf-8 -*-
"""Candidate store photos for the partner's finds (owner, 20 Nov 2026; rules in data/store_photos_rules.md).

Step 2 of 3, run where the Brave Search API is reachable (the Claude Code container; GitHub Actions has no Brave key):
  1. GitHub (store-photos.yml step=name): claude-haiku-5-5 names the exact model of each find from its photo + title and
     writes search queries in English, Norwegian, German and French -> data/store_photo_names.json   (rule 12)
  2. HERE, this script: per find, most viewed first (data/stats.json "p"[id][0]):
       - Brave image searches for each named query (local-language ones with that country), Brave web searches for the
         exact name (English + Norwegian) to find store pages that image search misses (miinto, Farfetch-fed shops)
       - every promising page is read for its whole gallery: Shopify <page>.json, else JSON-LD "image", og:image and the
         page's own gallery images (same image host as og:image, appearing more than once)
       - candidates are grouped by store (host), so step 3 can take one store's complete photoshoot (rules 5, 13)
     No site is excluded for being a marketplace (rule 14: resellers reuse the official photo); only replica sellers and
     buying agents are skipped, which never carry store photos. Images known to be under 800 px are dropped.
  3. GitHub (store-photos.yml step=pick): scripts/store_photos_pick.py chooses, cuts out and uploads.
Writes data/store_photo_candidates.json {"items": {id: {"name", "q", "p": [pages], "c": [[img, page index, w, h,
"s" page gallery | "b" Brave hit], ...]}}}.

  python scripts/store_photos_collect.py [--limit 300] [--offset 0] [--ids 1,2] [--redo]
"""
import argparse, html as htmlmod, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from catalog_common import COLOURS, ROOT, load_catalog, load_json  # noqa: E402

OUT = os.path.join(ROOT, "data", "store_photo_candidates.json")
NAMES = os.path.join(ROOT, "data", "store_photo_names.json")
API = "https://api.search.brave.com/res/v1/"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36"
MIN_SIDE = 800
MAX_HOSTS, PER_HOST, MAX_C = 8, 9, 48
# replica sellers and buying agents: their photos are never the store's own
SKIP_HOSTS = ("weidian.", "geilicdn.", "taobao.", "tmall.", "1688.", "alicdn.", "yupoo.", "pandabuy", "cnfans", "kakobuy",
              "superbuy", "sugargoo", "hoobuy", "allchinabuy", "mulebuy", "acbuy", "litbuy", "oopbuy", "orientdig", "dhgate.",
              "aliexpress.", "puroclassico.", "wikipedia.", "wikimedia.", "youtube.", "ytimg.", "tiktok.")
CAT_WORD = {"Shoes": "sneakers", "Outerwear": "jacket", "Tops": "", "Pants": "pants", "Shorts": "shorts", "Bags": "bag",
            "Accessories": "", "Headwear": "cap", "Toys": "toy"}
COUNTRY = {"no": "NO", "de": "DE", "fr": "FR", "en": ""}
PAUSE = 1.05
_last = [0.0]


def get(url, headers=None, timeout=15):
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers or {"User-Agent": UA}), timeout=timeout) as r:
        return r.read(3_000_000)


def brave(kind, q, country=""):
    url = API + kind + "/search?count=" + ("30" if kind == "images" else "12") + "&q=" + urllib.parse.quote(q)
    if country: url += "&country=" + country
    for k in range(3):
        wait = PAUSE - (time.time() - _last[0])
        if wait > 0: time.sleep(wait)
        _last[0] = time.time()
        try:
            d = json.loads(get(url, {"X-Subscription-Token": "x", "Accept": "application/json"}, 20))
            return d.get("results") or [] if kind == "images" else (d.get("web") or {}).get("results") or []
        except urllib.error.HTTPError as e:
            if e.code == 422 and country: return brave(kind, q)  # country not supported: search without it
            if e.code != 429: print("  brave", e.code, q, flush=True); return []
        except Exception as e:
            print("  brave", e, flush=True)
        time.sleep(3 * (k + 1))
    return []


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
JUNK = re.compile(r"logo|icon|sprite|favicon|placeholder|payment|badge|flag|banner|avatar|swatch|loader|spinner|klarna|"
                  r"/thumb|_thumb|-thumb|thumbnail|_small|_xs\b|50x50|100x100|1x1", re.I)


def page_gallery(page):
    """Full-size gallery images of a product page (up to 12), best first."""
    u = urllib.parse.urlsplit(page)
    m = re.search(r"/products/([^/?#]+)", u.path)
    if m:  # Shopify: the whole gallery at full size
        try:
            d = json.loads(get(f"{u.scheme}://{u.netloc}{u.path[:m.end()]}.json", {"User-Agent": UA, "Accept": "application/json"}))
            out = []
            for im in ((d.get("product") or {}).get("images") or [])[:12]:
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
    found = []

    def add(s):
        s = htmlmod.unescape(s or "").replace("\\/", "/").strip()
        if s.startswith("//"): s = "https:" + s
        if s.startswith("/"): s = f"{u.scheme}://{u.netloc}{s}"
        sz = re.search(r"-(\d{2,4})x(\d{2,4})\.(?:jpe?g|png|webp)", s, re.I)  # WordPress size copies
        if sz and max(int(sz.group(1)), int(sz.group(2))) < MIN_SIDE: return
        if s.startswith("http") and not JUNK.search(s) and s not in found: found.append(s)

    for blk in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', h, re.S | re.I):
        try: data = json.loads(blk)
        except Exception: continue
        stack = data if isinstance(data, list) else [data]
        while stack:
            x = stack.pop(0)
            if isinstance(x, dict):
                if str(x.get("@type", "")).lower() in ("product", "productgroup") or "image" in x:
                    im = x.get("image")
                    for v in (im if isinstance(im, list) else [im]):
                        add(v.get("url") or v.get("contentUrl") if isinstance(v, dict) else v)
                stack.extend(v for v in x.values() if isinstance(v, (dict, list)))
            elif isinstance(x, list):
                stack.extend(x)
    og = re.search(r'<meta[^>]+property=["\']og:image(?::secure_url)?["\'][^>]+content=["\']([^"\']+)', h, re.I) or \
        re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image', h, re.I)
    if not og: return [(s, 0, 0) for s in found[:12]]
    og_u = htmlmod.unescape(og.group(1)).replace("\\/", "/")
    og_u = urllib.parse.urljoin(page, "https:" + og_u if og_u.startswith("//") else og_u)
    os_ = urllib.parse.urlsplit(og_u)
    # every image URL on the page: absolute ones anywhere, relative ones in src / data-src / href attributes
    imgs = [htmlmod.unescape(s).replace("\\/", "/") for s in IMG_RE.findall(h)]
    imgs += [urllib.parse.urljoin(page, htmlmod.unescape(s)) for s in REL_RE.findall(h)]
    imgs = [s for s in imgs if not s.split("?")[0].lower().endswith(".avif")]

    def stem_of(path): return re.sub(r"\.(jpe?g|png|webp|avif)$", "", path, flags=re.I)
    # (a) files named after the og:image file (careofcarl: 26158811r.jpg -> zoom/26158811r_1.jpg), largest variant
    ostem = stem_of(os.path.basename(os_.path))
    sib = {}
    if len(ostem) >= 6:
        for s in imgs:
            base = os.path.basename(urllib.parse.urlsplit(s).path)
            if not base.startswith(ostem): continue
            score = 2 if re.search(r"zoom|large|original|full|2000|1600|1200", s, re.I) else 1
            if score > sib.get(base, (0, ""))[0]: sib[base] = (score, s)
    # (b) images on the og:image host that the page shows more than once (gallery + zoom + thumbs: miinto)
    counts = {}
    for s in imgs:
        su = urllib.parse.urlsplit(s)
        if su.netloc != os_.netloc: continue
        c = counts.setdefault(stem_of(su.path), [0, s]); c[0] += 1
    gal = []
    for st, (n, s) in sorted(counts.items(), key=lambda kv: -kv[1][0]):
        if n < 2: continue
        su = urllib.parse.urlsplit(s)
        if os_.query and su.query != os_.query: s = f"{su.scheme}://{su.netloc}{su.path}?{os_.query}"  # og:image's size
        gal.append(s)
    if len(sib) > 1:
        for base in sorted(sib): add(sib[base][1])
    elif len(gal) > 1:
        for s in gal: add(s)
    else:
        add(og_u)
    return [(s, 0, 0) for s in found[:12]]


def collect(p, nm):
    qs = queries(p, nm)
    hits, pages_rank = [], {}
    for q, lang in qs:
        for r in brave("images", q, COUNTRY.get(lang, "")):
            img = (r.get("properties") or {}).get("url") or ""
            page = r.get("url") or ""
            if not img or not page or skip(page) or skip(img): continue
            pr = r.get("properties") or {}
            w, h = int(pr.get("width") or 0), int(pr.get("height") or 0)
            if max(w, h) and max(w, h) < MIN_SIDE: continue
            hits.append((img, page, w, h))
            pages_rank[page] = pages_rank.get(page, 0) + 1
    name = (nm or {}).get("name") or qs[0][0]
    web = []
    for q, c in ((name, ""), (((nm or {}).get("queries") or {}).get("no") or "", "NO")):
        if isinstance(q, list): q = q[0] if q else ""
        if q:
            for r in brave("web", q, c)[:6]:
                if r.get("url") and not skip(r["url"]): web.append(r["url"])
    to_read = list(dict.fromkeys(web[:8] + [pg for pg, _ in sorted(pages_rank.items(), key=lambda kv: -kv[1])][:8]))[:14]
    with ThreadPoolExecutor(8) as ex:
        galleries = dict(zip(to_read, ex.map(page_gallery, to_read)))
    pages, cands, seen = [], [], set()
    by_host = {}

    def add(img, page, w, h, kind):
        key = re.sub(r"[?#].*$", "", img) if "miinto" not in img else img
        if key in seen or skip(img): return
        seen.add(key)
        by_host.setdefault(host_of(page), []).append([img, page, w, h, kind])

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
    return {"name": name, "q": [q for q, _ in qs], "p": pages, "c": cands}


def partner_ids(items):
    swaps = (load_json(os.path.join(ROOT, "data", "link_swaps.json"), {}) or {}).get("swaps") or {}
    stats = (load_json(os.path.join(ROOT, "data", "stats.json"), {}) or {}).get("p") or {}
    by = {p["id"]: p for p in items}
    ids = [i for i in swaps if i in by]
    ids.sort(key=lambda i: (-(stats.get(i) or [0])[0], i))
    return ids, by


def save(data):
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("{\"items\": {\n")
        rows = [json.dumps(k) + ": " + json.dumps(v, ensure_ascii=False, separators=(",", ":")) for k, v in data["items"].items()]
        f.write(",\n".join(rows))
        f.write("\n}}\n")
    os.replace(tmp, OUT)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=300)
    ap.add_argument("--offset", type=int, default=0)
    ap.add_argument("--ids", default="")
    ap.add_argument("--redo", action="store_true")
    a = ap.parse_args()
    ids, by = partner_ids(load_catalog()[1])
    ids = [i for i in a.ids.split(",") if i] if a.ids else ids[a.offset:a.offset + a.limit]
    names = (load_json(NAMES, {}) or {}).get("items") or {}
    data = load_json(OUT, {"items": {}})
    todo = [i for i in ids if a.redo or i not in data["items"]]
    print(f"{len(ids)} partner finds asked, {len(todo)} to search", flush=True)
    for n, i in enumerate(todo, 1):
        p = by[i]
        try:
            data["items"][i] = collect(p, names.get(i))
        except Exception as e:
            print(f"  {i} failed: {e!r}", flush=True); continue
        e = data["items"][i]
        hosts = {host_of(e["p"][c[1]]) for c in e["c"]}
        print(f"[{n}/{len(todo)}] {i} {e['name']}: {len(e['c'])} candidates from {len(hosts)} stores", flush=True)
        if n % 10 == 0: save(data)
    save(data)
    print("done,", len(data["items"]), "finds in", os.path.relpath(OUT, ROOT))


if __name__ == "__main__":
    main()
