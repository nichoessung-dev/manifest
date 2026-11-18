# -*- coding: utf-8 -*-
"""The rug slides already posted, collected for reuse (owner, 18 Nov 2026: "what about we reuse some old photos from previous
videos"). Every image the Postiz queue holds for the Qualityfinds TikTok account over the last DAYS days, with the post it came
from, goes to data/rug_library.json {"updated", "slides": [{"url", "post", "date", "k", "used"}]}. The first image of a post
is its cover (k 0). Reused slides cost no image generation; scripts/slides_to_video.py can make videos from them.

  python scripts/rug_library.py [--days 60] [--account qualityfinds]
Env: POSTIZ_API_KEY.
"""
import argparse, json, os, sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import post_short as P  # noqa: E402

OUT = os.path.join(P.ROOT, "data", "rug_library.json")


def images_of(post):
    """Image URLs of a Postiz post, wherever the API keeps them (image list, a JSON string, or the value items)."""
    found = []
    def walk(v):
        if isinstance(v, str):
            s = v.strip()
            if s.startswith("[") or s.startswith("{"):
                try: walk(json.loads(s)); return
                except Exception: pass
            if s.startswith("http") and any(x in s.lower() for x in (".jpg", ".jpeg", ".png", ".webp")): found.append(s)
        elif isinstance(v, dict):
            for k, x in v.items():
                if k in ("path", "url", "image", "images", "value", "content") or isinstance(x, (list, dict)): walk(x)
        elif isinstance(v, list):
            for x in v: walk(x)
    walk(post)
    seen, out = set(), []
    for u in found:
        if u not in seen: seen.add(u); out.append(u)
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--days", type=int, default=60); ap.add_argument("--account", default="qualityfinds")
    a = ap.parse_args()
    if not P.KEY: sys.exit("POSTIZ_API_KEY is not set")
    old = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {"slides": []}
    used = {s["url"]: s.get("used", 0) for s in old.get("slides", [])}
    now = datetime.now(timezone.utc); slides, posts, shown = [], 0, False; shown_detail = [False]
    for back in range(0, a.days, 7):
        end, start = now - timedelta(days=back), now - timedelta(days=min(a.days, back + 7))
        q = "?startDate=%s&endDate=%s" % (start.strftime("%Y-%m-%dT%H:%M:%S.000Z"), end.strftime("%Y-%m-%dT%H:%M:%S.000Z"))
        for p in P.call("GET", "/posts" + q).get("posts", []):
            name = str((p.get("integration") or {}).get("name") or "").lower()
            if a.account and a.account not in name: continue
            if not shown: print("sample post keys:", sorted(p.keys())); shown = True
            imgs = images_of(p)
            if len(imgs) < 3 and p.get("id"):              # the list leaves the media out: read the post itself
                try:
                    d = P.call("GET", "/posts/%s" % p["id"])
                    if not shown_detail[0]: print("post detail keys:", sorted(d.keys()) if isinstance(d, dict) else type(d).__name__, str(d)[:400]); shown_detail[0] = True
                    imgs = images_of(d)
                except SystemExit as e:
                    if not shown_detail[0]: print("post detail failed:", str(e)[:200]); shown_detail[0] = True
            if len(imgs) < 3: continue                      # a carousel has a cover and several slides
            posts += 1
            for k, u in enumerate(imgs):
                slides.append({"url": u, "post": p.get("id"), "date": (p.get("publishDate") or "")[:10], "k": k, "used": used.get(u, 0)})
    uniq = {s["url"]: s for s in slides}
    out = {"updated": now.isoformat(timespec="seconds"), "account": a.account, "posts": posts, "slides": sorted(uniq.values(), key=lambda s: (s["date"], s["post"] or "", s["k"]))}
    json.dump(out, open(OUT, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print("posts with slides: %d, slide images: %d (covers %d)" % (posts, len(uniq), sum(1 for s in uniq.values() if s["k"] == 0)))


if __name__ == "__main__":
    main()
