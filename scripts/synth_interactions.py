#!/usr/bin/env python3
"""Synthetic favourites and signed-in product views shaped like the real Supabase tables (Nov 2026: 715 members, about
1,600 favourites, 32,000 product views of which roughly a third by signed-in members), for testing scripts/bake_also.py
without the service key. Nothing here is real data.

How the fake members behave:
  - Each member follows 1 to 3 hidden "scenes": random groups of 6 to 10 brands (a stand-in for tastes such as old money,
    UK drill or Japanese street that the catalogue does not label). Content similarity cannot see a scene; co-likes can.
  - Each member has 1 to 3 favourite categories and a price level.
  - A pick comes from the member's scenes (most of the time) or from the whole catalogue by popularity (noise), weighted
    by view popularity, category and price fit. Some picks are followed by a second listing of the same brand and item
    type, as when people compare sellers (content similarity can see this).
  - Activity is heavy tailed: most members save 0 to 3 finds, a few save dozens. Favourites per find come out like the
    real data/stats.json (about 1,100 finds with one favourite, 130 with two, a few dozen with three or more).
--signal sets how much members follow their scenes (0..1); 0.8 is the default, 0.5 is a weak-signal check.

python3 scripts/synth_interactions.py --root . --out-dir /tmp/synth [--members 715] [--seed 1] [--signal 0.8]
"""
import argparse, bisect, collections, datetime, json, math, os, random, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bake_also as B   # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=B.ROOT)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--members", type=int, default=715)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--signal", type=float, default=0.8)
    a = ap.parse_args(argv)
    rnd = random.Random(a.seed)
    items = B.load_catalog(a.root)
    ai = (B.load_json(os.path.join(a.root, "data", "catalog_ai.json"), {}) or {}).get("items") or {}
    stats = B.load_json(os.path.join(a.root, "data", "stats.json"), {}) or {}
    pv = {k: (v[0] or 0) for k, v in (stats.get("p") or {}).items()}
    ids = [str(p["id"]) for p in items]
    brand = [p.get("brand") or "" for p in items]
    cat = [p.get("cat") or "" for p in items]
    kind = [((ai.get(i) or {}).get("item") or "") for i in ids]
    lp = [None if B.is_ph(p.get("price")) else math.log(float(p["price"])) for p in items]
    pop = [1.0 + pv.get(i, 0) for i in ids]

    brands = sorted({b for b in brand if b})
    rnd.shuffle(brands)
    scenes, k = [], 0
    while k < len(brands):
        n = rnd.randint(6, 10); scenes.append(set(brands[k:k + n])); k += n
    by_scene = [[i for i in range(len(items)) if brand[i] in s] for s in scenes]
    by_bk = collections.defaultdict(list)
    for i in range(len(items)): by_bk[(brand[i], kind[i])].append(i)
    cats = sorted(set(cat))

    def weighted(pool, w):
        acc, tot = [], 0.0
        for i in pool: tot += w(i); acc.append(tot)
        x = rnd.random() * tot
        return pool[min(len(pool) - 1, bisect.bisect_left(acc, x))]

    now = datetime.datetime(2026, 11, 5, 12, tzinfo=datetime.timezone.utc)
    favs, views, seen_fav = [], [], set()
    for m in range(a.members):
        uid = "%08x-0000-4000-8000-%012x" % (rnd.getrandbits(32), rnd.getrandbits(48))
        my_scenes = rnd.sample(range(len(scenes)), rnd.choice([1, 1, 1, 2, 2, 3]))
        my_cats = set(rnd.sample(cats, rnd.choice([1, 2, 2, 3])))
        centre = rnd.gauss(5.2, 0.6); spread = 0.7
        nf = 0 if rnd.random() < 0.42 else max(1, int(rnd.paretovariate(1.2)))
        nf = min(nf, 60)
        nv = int(nf * rnd.uniform(2, 6) + rnd.paretovariate(1.2) * 4)
        nv = min(nv, 400)
        pool = [i for s in my_scenes for i in by_scene[s]]

        def w(i):
            c = 1.0 if cat[i] in my_cats else 0.25
            pr = 1.0 if lp[i] is None else math.exp(-((lp[i] - centre) / spread) ** 2 / 2) + 0.1
            return pop[i] ** 0.6 * c * pr

        def pick():
            if pool and rnd.random() < a.signal: return weighted(pool, w)
            return weighted(rnd.sample(range(len(items)), 400), w)

        t = now - datetime.timedelta(days=rnd.uniform(5, 150))
        mine = []
        while len(mine) < nf:
            i = pick()
            if i in mine: continue
            mine.append(i)
            if rnd.random() < 0.3:                                  # compares another listing of the same thing
                sib = [j for j in by_bk[(brand[i], kind[i])] if j != i]
                if sib and len(mine) < nf: mine.append(rnd.choice(sib))
        for i in mine:
            t += datetime.timedelta(hours=rnd.uniform(1, 72))
            if (uid, i) in seen_fav: continue
            seen_fav.add((uid, i))
            favs.append({"user_id": uid, "product_id": ids[i], "platform": items[i].get("platform"), "created_at": t.isoformat()})
            if rnd.random() < 0.85:
                views.append({"user_id": uid, "product_id": ids[i], "viewed_at": (t - datetime.timedelta(minutes=rnd.uniform(1, 600))).isoformat()})
        tv = now - datetime.timedelta(days=rnd.uniform(1, 170))
        for _ in range(nv):
            i = pick() if rnd.random() < 0.8 else weighted(rnd.sample(range(len(items)), 400), lambda j: pop[j])
            tv += datetime.timedelta(minutes=rnd.uniform(1, 2000))
            views.append({"user_id": uid, "product_id": ids[i], "viewed_at": min(tv, now).isoformat()})
    os.makedirs(a.out_dir, exist_ok=True)
    for name, rows in (("favorites.json", favs), ("views.json", views)):
        with open(os.path.join(a.out_dir, name), "w") as f: json.dump(rows, f)
    savers = len({r["user_id"] for r in favs})
    print(f"synthetic: {a.members} members, {savers} with favourites, {len(favs)} favourites, {len(views)} signed-in views, "
          f"{len(scenes)} hidden scenes, signal {a.signal}")


if __name__ == "__main__":
    main()
