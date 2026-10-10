# -*- coding: utf-8 -*-
"""Hands finished videos to Postiz: one straight away, or a list with one every few days at a set Norwegian time.

  python scripts/schedule_videos.py --items belt-beats-sneakers,tee-four-dollars --start "2026-10-11 18:23" --every 2
  python scripts/schedule_videos.py --items tutorial --start now

An item is a style id whose finished video is on the "previews-batch" branch (<id>.mp4 and <id>.json, made by the Style previews
workflow: the very files the owner watched), or "tutorial" (media/how-to-order-portrait.mp4 in this repo).
A time that already has a post within half an hour is left alone, so running this twice never queues a video twice.

Env: POSTIZ_API_KEY, SHORTS_CHANNELS (optional), GITHUB_REPOSITORY. DRY_RUN=1 prints the plan and sends nothing.
"""
import argparse, hashlib, json, os, re, subprocess, sys, urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import post_short as P

ROOT = P.ROOT
TZ = ZoneInfo("Europe/Oslo")
REPO = os.environ.get("GITHUB_REPOSITORY", "nichoessung-dev/manifest")
DRY = bool(os.environ.get("DRY_RUN", "").strip())
TUTORIAL = {"format": "tutorial", "ids": [], "voiceover": True, "file": os.path.join(ROOT, "media", "how-to-order-portrait.mp4"),
            "product_url": "https://www.puroclassico.com/how-to-order",
            "caption": "How to order your first finds, step by step (1:47)\n\n"
                       "Advertisement: we earn a commission from MyCNBox when you order.\n\n"
                       "1. Make a free MyCNBox account\n2. Tap Buy via MyCNBox on any find\n3. Pick size and colour, check out\n"
                       "4. Check your QC photos\n5. Submit packing and pay shipping\n6. Track your parcel\n\n"
                       "Link in bio.\n\n#howtoorder #mycnbox #spreadsheet #finds #haul"}


def fetch(url, path):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) PuroClassicoShorts/1.0"})
    with urllib.request.urlopen(req, timeout=300) as r: data = r.read()
    open(path, "wb").write(data); return data


def prepare(item, ref, out):
    """The meta file for one item, with its video on disk."""
    if item == "tutorial":
        meta = dict(TUTORIAL)
        if not os.path.exists(meta["file"]): raise SystemExit("the tutorial video is not in the repo: %s" % meta["file"])
    else:
        base = "https://raw.githubusercontent.com/%s/%s/%s" % (REPO, ref, item)
        video = os.path.join(out, item + ".mp4")
        meta = json.loads(fetch(base + ".json", os.path.join(out, item + ".src.json")).decode("utf-8"))
        data = fetch(base + ".mp4", video)
        if len(data) < 200000: raise SystemExit("the video for %s is too small to be real (%d bytes)" % (item, len(data)))
        meta["file"] = video
    print("  %s: %.1f MB, md5 %s" % (item, os.path.getsize(meta["file"]) / 1e6, hashlib.md5(open(meta["file"], "rb").read()).hexdigest()))
    path = os.path.join(out, item + ".json"); json.dump(meta, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1); return path


def queued(first, last):
    """Times of the posts Postiz already holds between the first and the last wanted time (drafts do not count)."""
    out, t = [], first - timedelta(hours=1)
    while t < last + timedelta(hours=1):                        # asked for a week at a time
        e = min(t + timedelta(days=7), last + timedelta(hours=1))
        q = "?startDate=%s&endDate=%s" % (t.strftime("%Y-%m-%dT%H:%M:%S.000Z"), e.strftime("%Y-%m-%dT%H:%M:%S.000Z"))
        for p in P.call("GET", "/posts" + q).get("posts", []):
            if any(isinstance(v, str) and v.lower() == "draft" for v in p.values()): continue
            try: out.append(datetime.strptime((p.get("publishDate") or "")[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc))
            except Exception: pass
        t = e
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--items", required=True, help="comma list: style ids and/or 'tutorial'")
    ap.add_argument("--start", default="now", help="'now', or the first posting time in Norwegian time: YYYY-MM-DD HH:MM")
    ap.add_argument("--every", type=int, default=2, help="days between two videos")
    ap.add_argument("--ref", default="previews-batch", help="branch or commit that holds the finished style videos")
    a = ap.parse_args()
    items = [i.strip() for i in a.items.split(",") if i.strip()]
    bad = [i for i in items if not re.match(r"^[a-z0-9][a-z0-9-]{1,48}$", i)]
    if bad or not items: raise SystemExit("not a usable item list: %s" % (bad or "empty"))
    if not re.match(r"^[A-Za-z0-9._/-]{1,80}$", a.ref): raise SystemExit("not a usable branch or commit")
    if len(set(items)) != len(items): raise SystemExit("an item is in the list twice")
    out = os.path.join(ROOT, "out", "schedule"); os.makedirs(out, exist_ok=True)
    now = datetime.now(timezone.utc)
    if a.start.strip().lower() == "now":
        if len(items) != 1: raise SystemExit("'now' posts one video: give one item, or a start time for a list")
        path = prepare(items[0], a.ref, out); print("posting now:", items[0])
        if DRY: print("DRY_RUN: nothing sent"); return
        sys.exit(subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "post_short.py"), path], env=dict(os.environ, SCHEDULE_AT="")).returncode)
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})$", a.start.strip())
    if not m or a.every < 1: raise SystemExit("start must be 'now' or YYYY-MM-DD HH:MM (Norwegian time), and every at least 1")
    y, mo, d, hh, mi = (int(x) for x in m.groups()); first = datetime(y, mo, d, hh, mi, tzinfo=TZ)
    plan = []
    for k, item in enumerate(items):                            # the same clock time on each day, whatever the daylight-saving shift
        day = (first + timedelta(days=k * a.every)).date()
        plan.append((item, datetime(day.year, day.month, day.day, hh, mi, tzinfo=TZ).astimezone(timezone.utc)))
    if plan[0][1] < now + timedelta(minutes=15): raise SystemExit("the first time is in the past or less than 15 minutes away")
    have = [] if DRY and not P.KEY else queued(plan[0][1], plan[-1][1])
    made = 0
    for item, t in plan:
        local = t.astimezone(TZ).strftime("%a %d %b %H:%M")
        if any(abs((t - h).total_seconds()) < 1800 for h in have): print("%s: a post is already queued around %s, left alone" % (item, local)); continue
        path = prepare(item, a.ref, out)
        if DRY: print("DRY_RUN: would queue %s for %s (Norwegian time)" % (item, local)); continue
        r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "post_short.py"), path], env=dict(os.environ, SCHEDULE_AT=t.strftime("%Y-%m-%dT%H:%M:%S.000Z")))
        if r.returncode: raise SystemExit("could not queue %s for %s: stopped, nothing after it was sent" % (item, local))
        made += 1; print("queued %s for %s (Norwegian time)" % (item, local))
    print("videos queued:", made, "of", len(plan))
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as f:
            f.write("### Videos queued in Postiz\n\n" + "".join("- %s: **%s**\n" % (t.astimezone(TZ).strftime("%a %d %b %H:%M"), i) for i, t in plan))


if __name__ == "__main__":
    main()
