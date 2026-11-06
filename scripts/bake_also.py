#!/usr/bin/env python3
""""People who liked this also liked": for every find, the ~12 most related finds, written to data/also.json.

Runs in GitHub Actions next to bake_stats.py (.github/workflows/stats.yml, every 6 hours) with the SUPABASE_SERVICE_KEY
secret, read exactly like bake_stats.py does. Two signals are blended per find:

  1. Co-likes from other members (item-to-item collaborative filtering). A signed-in member's favourites (weight 1) and
     the finds they opened (product_views rows with their user id, last VIEW_DAYS days, weight VIEW_W) form one basket.
     Two finds are related when many baskets hold both: cosine similarity of the two finds' member vectors, each member
     counted less the more finds they touched (1 / log2(2 + basket size)), shrunk towards 0 while few members back the
     pair (support / (support + SHRINK)). A pair is used only when at least MIN_SUPPORT different members hold both, so
     no single member's list can be read back from the file. No user id, count per member or anything personal is written.
  2. Content similarity, so every find (new, unpopular, or never favourited) has good neighbours: same item type (the AI
     labels in data/catalog_ai.json), brand, model name, colour, a close price and shared title words (TF-IDF).

The co-like weight per find grows with the number of members who touched it (ALPHA_MAX * u / (u + K_CONF)), so the
file leans on content today and on members' behaviour as the data grows. The final 12 are picked with diversity caps
(at most BRAND_CAP_SAME from the find's own brand, BRAND_CAP_OTHER from any other brand, MODEL_CAP of one model, one
listing per title). Dead listings (data/link_health.json) and finds removed after reports (data/reported.json) are never
picked as neighbours.

Every run also prints an offline evaluation to the Actions log (aggregate numbers only): leave-one-out hit rate@12 of
the members' latest favourite, for popularity, content only, content plus brand affinity, co-likes only and the blend.

File format (read by /also.js and functions/_lib/also.js; keep the three in step):
  {"v":1, "generated":..., "k":12, "ids":[id, ...], "n":[[d, c, d, c, ...], ...]}
  ids are sorted by category, item type and brand, so related finds sit close together. n[i] lists find i's neighbours
  as pairs: d = (neighbour's position in ids) - i, c = score * 100 rounded to an even number (2..98), plus 100 when other
  members' co-likes back the pair. Small deltas and even scores keep the file small after compression.

Local runs (no service key): python3 scripts/bake_also.py --favorites-file favs.json [--views-file views.json]
  The files hold Supabase-shaped rows: [{"user_id": ..., "product_id": ..., "created_at"|"viewed_at": ...}, ...].
  Without either, the file is content similarity only. Synthetic files: scripts/synth_interactions.py.
"""
import argparse, bisect, collections, datetime, gzip, json, math, os, random, re, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TAG = '<script type="application/json" id="pc-catalog">'
SUPA = "https://uptpghuduqjqmrxwatbm.supabase.co"
PAGE = 1000

K_OUT = 12            # neighbours written per find
K_POOL = 40           # content candidates kept per find before blending (plus 20 of other brands)
MIN_SUPPORT = 3       # a co-like pair needs this many different members (k-anonymity, see the docstring)
SHRINK = 4.0          # support / (support + SHRINK): pairs backed by few members count less
FAV_W = 1.0           # a favourite in a member's basket
VIEW_W = 0.35         # an opened find in a member's basket (signed-in product_views)
VIEW_MAX = 0.6        # several opens of the same find add up to this
VIEW_DAYS = 180       # opened finds older than this are left out
USER_MAX_ITEMS = 300  # a basket keeps the member's latest 300 finds (bounds the pair count for very heavy users)
ALPHA_MAX = 0.75      # most a find's list can lean on co-likes
K_CONF = 25.0         # members touching a find at which co-likes get half of ALPHA_MAX
CF_NORM = "abs"       # co-like score of a pair: "abs" = sim / CF_REF capped at 1 (weak pairs stay weak); "max" = scaled
CF_REF = 0.25         #   per find so its best pair is 1 (tried: lifted single weak pairs too much on synthetic data)
# Brand affinity ("fans of this brand also like that brand") is built and evaluated every run, but adds nothing to the
# lists while BRAND_AFF_W is 0: on synthetic data it did not beat content similarity. The log's "content+brands" line
# shows it at BRAND_AFF_TRY on the real data; raise BRAND_AFF_W if that line wins there.
BRAND_AFF_W = 0.0     # most a related brand adds to content_score (same brand adds 0.22)
BRAND_AFF_TRY = 0.08
BRAND_SHRINK = 10.0   # brand pairs backed by few members count less
BRAND_CONF = 15.0     # members who touched a brand at which its affinities get half weight
AFF_BRANDS = 4        # related brands whose finds are added as candidates
BRAND_CAP_SAME = 7
BRAND_CAP_OTHER = 3
MODEL_CAP = 4
EVAL_MIN_USERS = 20   # the evaluation runs only with this many members holding 2+ favourites

STOP = {"the", "and", "with", "for", "of", "in", "a", "an", "rep", "reps", "new", "men", "mens", "women", "womens", "style",
        "edition", "version", "x", "by", "on", "best", "batch", "quality", "high", "top", "1", "pcs", "set"}
COLOUR_WORDS = {"black", "white", "grey", "gray", "navy", "blue", "light", "dark", "red", "burgundy", "maroon", "wine", "pink",
                "purple", "lilac", "green", "olive", "khaki", "army", "mint", "yellow", "orange", "brown", "tan", "beige", "cream",
                "off", "ivory", "camel", "sand", "silver", "gold", "multicolour", "multicolor", "charcoal", "teal", "turquoise",
                "coffee", "apricot", "rose", "colour", "color", "colors", "colours"}
# Coarser item groups, so a zip hoodie and a hoodie, or jeans and cargo pants, still count as close.
GROUP = {"t-shirt": "tee", "long sleeve": "tee", "tank top": "tee", "jersey": "tee", "hoodie": "sweat", "zip hoodie": "sweat",
         "sweatshirt": "sweat", "quarter zip": "sweat", "fleece": "sweat", "sweater": "knit", "cardigan": "knit",
         "puffer jacket": "puffer", "down jacket": "puffer", "vest": "puffer", "coat": "jacket", "blazer": "jacket",
         "overshirt": "shirt", "jeans": "pants", "cargo pants": "pants", "track pants": "pants", "sweatpants": "pants",
         "joggers": "pants", "trousers": "pants", "leggings": "pants", "swim shorts": "shorts", "tracksuit": "set",
         "sneakers": "shoes", "boots": "shoes", "loafers": "shoes", "slides": "sandals", "clogs": "sandals", "clog": "sandals",
         "cap": "cap", "trucker cap": "cap", "hat": "cap", "bucket hat": "cap", "visor": "cap", "beanie": "beanie",
         "balaclava": "beanie", "wallet": "wallet", "card holder": "wallet", "sunglasses": "glasses", "glasses": "glasses",
         "bracelet": "jewellery", "necklace": "jewellery", "ring": "jewellery", "earrings": "jewellery", "brooch": "jewellery",
         "toy": "toy", "figure": "toy", "keychain": "toy"}
GENERIC_MODELS = {"", "replica", "logo", "classic", "basic", "other", "none", "unknown", "standard"}


# ------------------------------------------------------------------ data in

def fetch_all(path, key):
    """Every row of a Supabase GET, 1,000 per request (the same access as bake_stats.py). path must carry an order=."""
    rows, start = [], 0
    while True:
        req = urllib.request.Request(f"{SUPA}/rest/v1/{path}", headers={
            "apikey": key, "Authorization": "Bearer " + key, "Range-Unit": "items", "Range": f"{start}-{start + PAGE - 1}"})
        chunk = json.load(urllib.request.urlopen(req, timeout=60))
        rows += chunk
        if len(chunk) < PAGE: return rows
        start += PAGE


def read_supabase(key, now):
    """(favourites, views) rows from Supabase. A missing created_at column or an unreadable product_views is not fatal."""
    try: favs = fetch_all("favorites?select=user_id,product_id,created_at&order=user_id.asc,product_id.asc", key)
    except Exception as e:
        print("favorites: no created_at column, read without it:", str(e)[:80])
        favs = fetch_all("favorites?select=user_id,product_id&order=user_id.asc,product_id.asc", key)
    since = (now - datetime.timedelta(days=VIEW_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    try: views = fetch_all("product_views?select=user_id,product_id,viewed_at&user_id=not.is.null&viewed_at=gte." + since +
                           "&order=viewed_at.asc,user_id.asc,product_id.asc", key)
    except Exception as e: print("signed-in product views not read:", str(e)[:80]); views = []
    return favs, views


def load_rows(path):
    if not path: return []
    with open(path, encoding="utf-8") as f: d = json.load(f)
    if isinstance(d, dict): d = d.get("rows") or d.get("favorites") or d.get("views") or []
    return [r for r in d if isinstance(r, dict)]


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f: return json.load(f)
    except Exception: return default


def load_catalog(root):
    with open(os.path.join(root, "index.html"), encoding="utf-8") as f: html = f.read()
    i = html.find(TAG)
    if i < 0: raise SystemExit("pc-catalog block not found in index.html")
    s = i + len(TAG)
    return json.loads(html[s:html.find("</script>", s)])


def parse_ts(s):
    try: return datetime.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception: return None


# ------------------------------------------------------------------ content features

def words(s):
    return re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)?", str(s or "").lower())


def is_ph(cny):
    try: return not (5 <= float(cny) < 99999)
    except Exception: return True


class Feat:
    __slots__ = ("id", "brand", "cat", "item", "group", "model", "colour", "cols", "lp", "vec", "toks", "pop", "qc", "title")


def build_features(items, ai, stats):
    """One Feat per find: normalised brand, category, AI item type and group, brand-scoped model name, colour words, log
    price, a TF-IDF vector of the title words that are not brand, colour or filler, and a 0..1 popularity prior
    (30-day views from data/stats.json; favourites are left out so the evaluation does not see its own answers)."""
    pv = {pid: (v[1] if len(v) > 1 else 0) + (v[2] if len(v) > 2 else 0) for pid, v in ((stats or {}).get("p") or {}).items()}
    mx = math.log1p(max(pv.values()) if pv else 1) or 1.0
    feats, df = [], collections.Counter()
    for p in items:
        a = ai.get(str(p.get("id"))) or {}
        f = Feat()
        f.id = str(p.get("id"))
        f.brand = str(p.get("brand") or "").strip().lower()
        f.cat = str(a.get("cat") or p.get("cat") or "").strip().lower()
        f.item = str(a.get("item") or "").strip().lower() or f.cat
        f.group = GROUP.get(f.item) or (f.item.split()[-1] if f.item else f.cat)
        m = str(a.get("model_name") or "").strip().lower()
        f.model = f.brand + "|" + m if m not in GENERIC_MODELS and m != f.brand else ""
        f.colour = str(a.get("colour") or "").strip().lower()
        f.cols = frozenset(w for w in words(f.colour) if w not in ("light", "dark", "off"))
        f.lp = None if is_ph(p.get("price")) else math.log(float(p["price"]))
        bw = set(words(f.brand))
        f.title = (f.brand + "|" + str(p.get("title") or "").strip().lower())
        f.toks = sorted({w for w in words(a.get("title_base") or p.get("title")) if w not in bw and w not in STOP
                         and w not in COLOUR_WORDS and (len(w) >= 2 or w.isdigit())})
        f.pop = math.log1p(pv.get(f.id, 0)) / mx
        f.qc = 1 if (p.get("qc") or 0) > 0 else 0
        df.update(f.toks)
        feats.append(f)
    n = len(feats)
    for f in feats:
        v = {t: math.log(n / df[t]) for t in f.toks if df[t] > 1}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        f.vec = {t: x / norm for t, x in v.items()}
    return feats, df


def content_score(a, b, aff=None):
    """0..1: how alike two finds are. aff (weighted(brand_affinity(...))) adds how much the members who like a's brand
    also like b's brand; without it this is content only (no member data)."""
    s = 0.0
    if a.item == b.item: s += 0.30
    elif a.group == b.group: s += 0.18
    elif a.cat == b.cat: s += 0.06
    if a.brand and a.brand == b.brand: s += 0.22
    elif aff: s += aff.get(a.brand, {}).get(b.brand, 0.0)
    if a.model and a.model == b.model: s += 0.25
    if a.colour and a.colour == b.colour: s += 0.12
    elif a.cols & b.cols: s += 0.06
    if a.lp is not None and b.lp is not None: s += 0.13 * math.exp(-abs(a.lp - b.lp) / 0.45)
    else: s += 0.04
    va, vb = a.vec, b.vec
    if len(va) > len(vb): va, vb = vb, va
    cos = 0.0
    for t, x in va.items():
        y = vb.get(t)
        if y: cos += x * y
    s += 0.25 * cos
    s += 0.03 * b.pop + 0.015 * b.qc                 # a quality prior: among equally close finds, the looked-at ones first
    return min(1.0, s / 1.30)


def content_pools(feats, df, aff=None, k=K_POOL):
    """For every find, its K_POOL most similar finds by content_score (plus the best K_POOL // 2 of other brands), as
    [(j, score), ...] best first. Candidates come from buckets (same brand+model, brand+item, brand+group, item+colour,
    item, group, brand, and with aff the same group from related brands), the nearest by price inside the large buckets,
    plus title-word postings, so each find is compared with a few hundred finds, not all 9,000."""
    n = len(feats)
    buckets = collections.defaultdict(list)
    for i, f in enumerate(feats):
        if f.model: buckets["m:" + f.model].append(i)
        buckets["bi:" + f.brand + "|" + f.item].append(i)
        buckets["bg:" + f.brand + "|" + f.group].append(i)
        for c in f.cols or ("",): buckets["ic:" + f.item + "|" + c].append(i)
        buckets["i:" + f.item].append(i)
        buckets["g:" + f.group].append(i)
        buckets["b:" + f.brand].append(i)
    # big buckets (and the buckets of related brands) are read around the find's own price: sorted by log price once
    lpk = lambda j: feats[j].lp if feats[j].lp is not None else 99.0
    byprice = {}

    def sorted_bucket(key):
        if key not in byprice:
            srt = sorted(buckets.get(key) or (), key=lambda j: (lpk(j), j))
            byprice[key] = (srt, [lpk(j) for j in srt])
        return byprice[key]

    post = collections.defaultdict(list)
    max_df = max(30, n // 40)
    for i, f in enumerate(feats):
        for t in f.vec:
            if df[t] <= max_df: post[t].append(i)

    def near(key, i, m):
        lst = buckets.get(key) or ()
        if len(lst) <= min(m, 120): return lst
        srt, prices = sorted_bucket(key)
        r = bisect.bisect_left(prices, lpk(i))
        return srt[max(0, r - m // 2): r + m // 2 + 1]

    out = []
    for i, f in enumerate(feats):
        cand = set()
        if f.model: cand.update(near("m:" + f.model, i, 200))
        cand.update(near("bi:" + f.brand + "|" + f.item, i, 160))
        cand.update(near("bg:" + f.brand + "|" + f.group, i, 80))
        for c in f.cols or ("",): cand.update(near("ic:" + f.item + "|" + c, i, 90))
        cand.update(near("i:" + f.item, i, 70))
        cand.update(near("g:" + f.group, i, 40))
        cand.update(near("b:" + f.brand, i, 30))
        if aff:                                       # the same kind of thing from the brands this brand's fans also like
            for b2, _ in sorted(aff.get(f.brand, {}).items(), key=lambda e: -e[1])[:AFF_BRANDS]:
                cand.update(near("bg:" + b2 + "|" + f.group, i, 24))
        acc = collections.Counter()
        for t, x in f.vec.items():
            for j in post.get(t, ()):
                acc[j] += x * feats[j].vec[t]
        cand.update(j for j, _ in acc.most_common(80))
        cand.discard(i)
        sc = [(j, content_score(f, feats[j], aff)) for j in cand]
        sc.sort(key=lambda e: (-e[1], e[0]))
        # the best k, plus the best k // 2 of other brands, so the diversity caps always have enough to choose from
        other = [e for e in sc[k:] if feats[e[0]].brand != f.brand][:k // 2]
        out.append(sc[:k] + other)
    return out


# ------------------------------------------------------------------ co-likes (item-to-item collaborative filtering)

def baskets(fav_rows, view_rows, pos, now, view_w=VIEW_W):
    """{member: {find index: weight}}: favourites weigh FAV_W, opened finds view_w each up to VIEW_MAX. Only finds in the
    catalogue. Each basket keeps the member's USER_MAX_ITEMS latest finds."""
    since = now - datetime.timedelta(days=VIEW_DAYS)
    w = collections.defaultdict(lambda: collections.defaultdict(float))
    last = collections.defaultdict(dict)
    for r in view_rows:
        u, i = r.get("user_id"), pos.get(str(r.get("product_id") or ""))
        if not u or i is None or view_w <= 0: continue
        t = parse_ts(r.get("viewed_at"))
        if t and t < since: continue
        w[u][i] = min(VIEW_MAX, w[u][i] + view_w)
        last[u][i] = max(last[u].get(i, ""), str(r.get("viewed_at") or ""))
    for r in fav_rows:
        u, i = r.get("user_id"), pos.get(str(r.get("product_id") or ""))
        if not u or i is None: continue
        w[u][i] = max(w[u][i], FAV_W)
        last[u][i] = max(last[u].get(i, ""), str(r.get("created_at") or "9"))
    out = {}
    for u, items in w.items():
        items = {i: x for i, x in items.items() if x > 0}
        if len(items) > USER_MAX_ITEMS:
            keep = sorted(items, key=lambda i: last[u].get(i, ""), reverse=True)[:USER_MAX_ITEMS]
            items = {i: items[i] for i in keep}
        if items: out[u] = items
    return out


def cf_neighbours(bk, n, min_support=MIN_SUPPORT, shrink=SHRINK, k=K_POOL):
    """(neighbours, members): neighbours[i] = [(j, sim, support), ...] best first, only pairs that at least min_support
    different members hold; members[i] = how many members touched find i."""
    C, S = collections.defaultdict(float), collections.Counter()
    norm, members = [0.0] * n, [0] * n
    for items in bk.values():
        iuf = 1.0 / math.log2(2 + len(items))
        lst = sorted(items.items())
        for a, wa in lst:
            norm[a] += wa * wa * iuf; members[a] += 1
        for x in range(len(lst)):
            a, wa = lst[x]
            for y in range(x + 1, len(lst)):
                b, wb = lst[y]
                key = a * n + b
                C[key] += wa * wb * iuf; S[key] += 1
    nb = collections.defaultdict(list)
    for key, s in S.items():
        if s < min_support: continue
        a, b = divmod(key, n)
        sim = C[key] / math.sqrt(norm[a] * norm[b]) * (s / (s + shrink))
        nb[a].append((b, sim, s)); nb[b].append((a, sim, s))
    out = [[] for _ in range(n)]
    for a, lst in nb.items():
        lst.sort(key=lambda e: (-e[1], e[0]))
        out[a] = lst[:k]
    return out, members


def brand_affinity(bk, feats, min_support=MIN_SUPPORT, shrink=BRAND_SHRINK, conf=BRAND_CONF, k=12):
    """{brand: {other brand: 0..1}}: "members who like this brand also like that one", the same cosine-with-shrinkage
    as cf_neighbours on brand level, where even a few hundred members give dense, reliable numbers. A brand pair needs
    min_support different members. Scaled per brand so its closest brand is 1, times the brand's own confidence
    m / (m + conf), m = members who touched the brand."""
    C, S = collections.defaultdict(float), collections.Counter()
    norm, members = collections.defaultdict(float), collections.Counter()
    for items in bk.values():
        v = collections.defaultdict(float)
        for i, w in items.items():
            if feats[i].brand: v[feats[i].brand] += w
        if not v: continue
        iuf = 1.0 / math.log2(2 + len(items))
        lst = sorted((b, min(3.0, x)) for b, x in v.items())
        for b, x in lst: norm[b] += x * x * iuf; members[b] += 1
        for p in range(len(lst)):
            for q in range(p + 1, len(lst)):
                key = (lst[p][0], lst[q][0])
                C[key] += lst[p][1] * lst[q][1] * iuf; S[key] += 1
    raw = collections.defaultdict(dict)
    for (a, b), s in S.items():
        if s < min_support: continue
        sim = C[(a, b)] / math.sqrt(norm[a] * norm[b]) * (s / (s + shrink))
        raw[a][b] = sim; raw[b][a] = sim
    out = {}
    for a, d in raw.items():
        top = sorted(d.items(), key=lambda e: (-e[1], e[0]))[:k]
        mx = top[0][1] or 1.0
        c = members[a] / (members[a] + conf)
        out[a] = {b: round(c * x / mx, 4) for b, x in top}
    return out


def weighted(aff, w):
    """brand_affinity scaled by w for content_score; None when w is 0 (content only)."""
    if not aff or w <= 0: return None
    return {a: {b: w * x for b, x in d.items()} for a, d in aff.items()}


# ------------------------------------------------------------------ blend + diversity

def pick_diverse(anchor, ranked, feats, banned, k=K_OUT):
    """ranked: [(j, score, cf), ...] best first. The best k under the diversity caps; if the caps leave fewer than k, the
    rest are filled from what the caps skipped (still never the find itself, a banned find or a repeated title)."""
    out, skipped, per_brand, per_model, titles = [], [], collections.Counter(), collections.Counter(), set()
    titles_anchor = feats[anchor].title
    for e in ranked:
        j = e[0]
        if j == anchor or j in banned: continue
        f = feats[j]
        if f.title in titles: continue
        cap = BRAND_CAP_SAME if f.brand == feats[anchor].brand else BRAND_CAP_OTHER
        if per_brand[f.brand] >= cap or (f.model and per_model[f.model] >= MODEL_CAP) or \
           (f.title == titles_anchor and any(feats[x[0]].title == titles_anchor for x in out)):
            skipped.append(e); continue
        out.append(e); titles.add(f.title); per_brand[f.brand] += 1
        if f.model: per_model[f.model] += 1
        if len(out) >= k: return out
    for e in skipped:
        if len(out) >= k: break
        if feats[e[0]].title in titles: continue
        out.append(e); titles.add(feats[e[0]].title)
    return out


def blend(feats, pools, cfn, members, banned, aff=None, alpha_max=ALPHA_MAX, k_conf=K_CONF, k=K_OUT):
    """Final neighbour lists: [(j, score, cf_backed), ...] per find."""
    res = []
    for i, f in enumerate(feats):
        cand = {j: [s, 0.0] for j, s in pools[i]}
        cf = cfn[i] if cfn else []
        alpha = 0.0
        if cf:
            mx = (cf[0][1] if CF_NORM == "max" else CF_REF) or 1.0
            alpha = alpha_max * members[i] / (members[i] + k_conf)
            for j, sim, _ in cf:
                if j not in cand: cand[j] = [content_score(f, feats[j], aff), 0.0]
                cand[j][1] = min(1.0, sim / mx)
        ranked = sorted(((j, (1 - alpha) * c + alpha * x, x > 0) for j, (c, x) in cand.items()), key=lambda e: (-e[1], e[0]))
        res.append(pick_diverse(i, ranked, feats, banned, k))
    return res


# ------------------------------------------------------------------ file out

def encode(feats, lists, now):
    order = sorted(range(len(feats)), key=lambda i: (feats[i].cat, feats[i].group, feats[i].item, feats[i].brand,
                                                       feats[i].lp if feats[i].lp is not None else 99.0, feats[i].id))
    rank = {i: r for r, i in enumerate(order)}
    n = []
    for i in order:
        row = []
        for j, s, cf in lists[i]:
            row += [rank[j] - rank[i], max(2, min(98, 2 * int(round(s * 50)))) + (100 if cf else 0)]   # even: compresses better
        n.append(row)
    return {"v": 1, "generated": now.replace(microsecond=0).isoformat(), "k": K_OUT, "ids": [feats[i].id for i in order], "n": n}


def decode(doc):
    """{id: [(id, score 0..1, cf_backed), ...]}: the same reading as /also.js (used by the tests)."""
    ids, out = doc["ids"], {}
    for i, row in enumerate(doc["n"]):
        out[ids[i]] = [(ids[i + row[x]], (row[x + 1] % 100) / 100.0, row[x + 1] >= 100) for x in range(0, len(row), 2)]
    return out


def write_if_changed(path, doc):
    new = json.dumps(doc, separators=(",", ":"))
    old = ""
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f: old = f.read()
    strip = lambda s: re.sub(r'"generated":"[^"]*",', "", s, count=1)
    if strip(old) == strip(new):
        print("also.json unchanged"); return False, new
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f: f.write(new)
    return True, new


# ------------------------------------------------------------------ offline evaluation

def split_holdout(fav_rows, pos, seed=7):
    """({member: hidden find index}, {member: their latest other favourite}) for every member with 2+ favourites: the
    latest by created_at is hidden (a seeded random one when the column is missing)."""
    rnd = random.Random(seed)
    favs_by = collections.defaultdict(set)
    for r in fav_rows:
        i = pos.get(str(r.get("product_id") or ""))
        if r.get("user_id") and i is not None: favs_by[r["user_id"]].add((str(r.get("created_at") or ""), i))
    test, last = {}, {}
    for u, st in sorted(favs_by.items()):
        lst = sorted(st)
        if len({i for _, i in lst}) < 2: continue
        held = lst[-1][1] if all(t for t, _ in lst) else rnd.choice(lst)[1]
        others = [x for x in lst if x[1] != held]
        test[u], last[u] = held, others[-1][1]
    return test, last


def evaluate(feats, df, fav_rows, view_rows, pos, banned, now, seed=7, params=None, methods=None, verbose=True):
    """Leave-one-out evaluation. For every member with 2+ favourites the latest favourite is hidden, with every other
    trace of that member on that find. Brand affinities and co-likes are rebuilt without the hidden finds, the lists
    are made again, and each method ranks finds the member has not touched:
      single = the 12 neighbours of the member's latest other favourite (what a product page row shows),
      multi  = the summed neighbour scores of all the member's other finds, best 12 (what For you and the feed can do).
    hit@12 = share of members whose hidden favourite is among those 12. Prints aggregate numbers only."""
    P = dict(alpha_max=ALPHA_MAX, k_conf=K_CONF, view_w=VIEW_W)
    P.update(params or {})
    test, last = split_holdout(fav_rows, pos, seed)
    if len(test) < EVAL_MIN_USERS:
        if verbose: print(f"eval: only {len(test)} members with 2+ favourites, at least {EVAL_MIN_USERS} needed: skipped")
        return {}
    held_pid = {u: feats[i].id for u, i in test.items()}
    keep = lambda r: held_pid.get(r.get("user_id")) != str(r.get("product_id"))
    bk = baskets([r for r in fav_rows if keep(r)], [r for r in view_rows if keep(r)], pos, now, P["view_w"])
    cfn, members = cf_neighbours(bk, len(feats))
    aff = brand_affinity(bk, feats)
    a_try, a_use = weighted(aff, BRAND_AFF_TRY), weighted(aff, BRAND_AFF_W)
    methods = methods or ("popularity", "content", "content+brands", "colikes", "blend")
    pools0 = content_pools(feats, df)
    pools_try = content_pools(feats, df, a_try) if "content+brands" in methods else None
    pools_use = pools0 if a_use is None else content_pools(feats, df, a_use)
    lists = {}
    if "content" in methods: lists["content"] = blend(feats, pools0, None, members, banned)
    if "content+brands" in methods: lists["content+brands"] = blend(feats, pools_try, None, members, banned, a_try)
    if "colikes" in methods: lists["colikes"] = [pick_diverse(i, [(j, s, True) for j, s, _ in cfn[i]], feats, banned) for i in range(len(feats))]
    if "blend" in methods: lists["blend"] = blend(feats, pools_use, cfn, members, banned, a_use, P["alpha_max"], P["k_conf"])
    popc = collections.Counter()
    for items in bk.values():
        for i, x in items.items(): popc[i] += x
    pop_rank = [i for i, _ in sorted(popc.items(), key=lambda e: (-e[1], e[0]))]
    res = {}
    for name in methods:
        hs = hm = 0; cov = set()
        for u, held in test.items():
            seen = set(bk.get(u, {}))
            if name == "popularity":
                top = [i for i in pop_rank if i not in seen][:K_OUT]
                hs += held in top; hm += held in top; cov.update(top); continue
            L = lists[name]
            single = [j for j, _, _ in L[last[u]] if j not in seen][:K_OUT]
            hs += held in single; cov.update(single)
            sc = collections.Counter()
            for i, w in bk.get(u, {}).items():
                for j, s, _ in L[i]:
                    if j not in seen: sc[j] += w * s
            hm += held in [j for j, _ in sorted(sc.items(), key=lambda e: (-e[1], e[0]))[:K_OUT]]
        n = len(test)
        res[name] = {"members": n, "hit12_single": round(hs / n, 4), "hit12_multi": round(hm / n, 4), "coverage": len(cov)}
    if verbose:
        pairs = sum(len(x) for x in cfn) // 2
        print(f"eval (leave-one-out, {len(test)} members with 2+ favourites; {sum(1 for x in cfn if x)} finds and {pairs} pairs "
              f"with co-likes from {MIN_SUPPORT}+ members, {len(aff)} brands with related brands, after hiding)")
        for name, r in res.items():
            print(f"eval {name:>15}: hit@12 one find {r['hit12_single']:.3f}   all their finds {r['hit12_multi']:.3f}   different finds shown {r['coverage']}")
    return res


# ------------------------------------------------------------------ main

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=ROOT, help="repo root (index.html, data/)")
    ap.add_argument("--out", default=None, help="output file (default <root>/data/also.json)")
    ap.add_argument("--favorites-file", help="local JSON rows instead of Supabase favorites (user_id, product_id, created_at)")
    ap.add_argument("--views-file", help="local JSON rows instead of Supabase product_views (user_id, product_id, viewed_at)")
    ap.add_argument("--no-eval", action="store_true", help="skip the offline evaluation")
    ap.add_argument("--now", help="ISO time to treat as now (tests)")
    a = ap.parse_args(argv)
    t0 = time.time()
    now = parse_ts(a.now) if a.now else datetime.datetime.now(datetime.timezone.utc)
    out = a.out or os.path.join(a.root, "data", "also.json")
    items = load_catalog(a.root)
    ai = (load_json(os.path.join(a.root, "data", "catalog_ai.json"), {}) or {}).get("items") or {}
    stats = load_json(os.path.join(a.root, "data", "stats.json"), {})
    lh = load_json(os.path.join(a.root, "data", "link_health.json"), {}) or {}
    rep = load_json(os.path.join(a.root, "data", "reported.json"), {}) or {}
    dead = {str(x) for x in (lh.get("dead") or [])} | {str(x) for x in (rep.get("hidden") or [])}

    if a.favorites_file or a.views_file:
        favs, views = load_rows(a.favorites_file), load_rows(a.views_file)
        print(f"local data: {len(favs)} favourites, {len(views)} signed-in views")
    elif os.environ.get("SUPABASE_SERVICE_KEY"):
        favs, views = read_supabase(os.environ["SUPABASE_SERVICE_KEY"], now)
        print(f"supabase: {len(favs)} favourites, {len(views)} signed-in views (last {VIEW_DAYS} days)")
    else:
        favs, views = [], []
        print("no SUPABASE_SERVICE_KEY and no --favorites-file: content similarity only")

    feats, df = build_features(items, ai, stats)
    pos = {f.id: i for i, f in enumerate(feats)}
    banned = {pos[x] for x in dead if x in pos}
    bk = baskets(favs, views, pos, now)
    aff = brand_affinity(bk, feats)
    a_use = weighted(aff, BRAND_AFF_W)
    pools = content_pools(feats, df, a_use)
    t1 = time.time()
    cfn, members = cf_neighbours(bk, len(feats))
    lists = blend(feats, pools, cfn, members, banned, a_use)
    doc = encode(feats, lists, now)
    changed, body = write_if_changed(out, doc)
    with_cf = sum(1 for L in lists if any(cf for _, _, cf in L))
    short = sum(1 for L in lists if len(L) < K_OUT)
    gz = len(gzip.compress(body.encode(), 9))
    print(f"also.json {'written' if changed else 'kept'}: {len(feats)} finds, {with_cf} with co-likes from "
          f"{sum(1 for x in bk.values() if len(x) >= 2)} members' baskets, {len(aff)} brands with related brands, {short} with fewer than {K_OUT}; "
          f"{len(body) / 1024:.0f} KB raw, {gz / 1024:.0f} KB gzip; content {t1 - t0:.1f} s, total {time.time() - t0:.1f} s")
    if not a.no_eval and favs:
        try: evaluate(feats, df, favs, views, pos, banned, now)
        except Exception as e: print("eval failed:", str(e)[:120])
    return doc


if __name__ == "__main__":
    main()
