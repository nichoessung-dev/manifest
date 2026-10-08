# -*- coding: utf-8 -*-
"""Keeps the next few days of carousel posts queued inside Postiz, which publishes them on time by itself.

GitHub's scheduler is too unreliable to post at a set time, so each time this runs it only tops up the queue:
for every posting slot in the next DAYS days that has no post yet, it builds a carousel and schedules it in Postiz.
It also sends new TikTok post links to the Discord webhook.

Env: POSTIZ_API_KEY, FINDS_FOLDER (Drive folder id), SHORTS_CHANNELS, MYCNBOX_WEBHOOK (optional)
"""
import json, os, subprocess, sys, urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import post_short as P

ROOT = P.ROOT
SLOTS = ["08:23", "12:23", "16:23", "20:23"]                                   # posting times, Norwegian time
DAYS = 5                                                     # how far ahead the queue is kept full
TZ = ZoneInfo("Europe/Oslo")
PROFILE = "https://www.tiktok.com/@puroclassico.com"
MODE = os.environ.get("FINDS_MODE", "video")                 # "video" (full-screen slideshow with sound) or "carousel" (swipeable photos)
AUDIO = os.environ.get("FINDS_AUDIO", "1Jl7ptfgdvN4FlMiEW0Y3NZpzKhIGDlrx")   # the owner's sound, a Drive file id


def wanted_slots(now):
    out = []
    for d in range(DAYS + 1):
        day = (now.astimezone(TZ) + timedelta(days=d)).date()
        for s in SLOTS:
            t = datetime(day.year, day.month, day.day, int(s[:2]), int(s[3:]), tzinfo=TZ).astimezone(timezone.utc)
            if now + timedelta(minutes=20) <= t <= now + timedelta(days=DAYS): out.append(t)
    return out


def queued(now):
    """Times of the posts Postiz already holds for the coming days."""
    q = "?startDate=%s&endDate=%s" % ((now - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S.000Z"), (now + timedelta(days=DAYS + 1)).strftime("%Y-%m-%dT%H:%M:%S.000Z"))
    out = []
    for p in P.call("GET", "/posts" + q).get("posts", []):
        if any(isinstance(v, str) and v.lower() == "draft" for v in p.values()): continue      # a draft will not publish, so its slot is free
        try: out.append(datetime.strptime((p.get("publishDate") or "")[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc))
        except Exception: pass
    return out


def top_up():
    now = datetime.now(timezone.utc); have = queued(now); made = 0
    print("posts already queued:", sorted(t.strftime("%m-%d %H:%M") for t in have))
    for t in wanted_slots(now):
        if any(abs((t - h).total_seconds()) < 1800 for h in have): continue
        out = os.path.join(ROOT, "out", t.strftime("%m%d-%H%M")); os.makedirs(out, exist_ok=True)
        r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "make_finds.py"), "--folder", os.environ["FINDS_FOLDER"], "--slides", "7", "--commit-state", "--out", out] + (["--video"] if MODE == "video" else []) + (["--audio", AUDIO] if AUDIO else []))
        metas = [f for f in os.listdir(out) if f.endswith(".json")]
        if r.returncode or not metas: print("could not build the carousel for", t); continue
        env = dict(os.environ, SCHEDULE_AT=t.strftime("%Y-%m-%dT%H:%M:%S.000Z"))
        r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "post_short.py"), os.path.join(out, metas[0])], env=env)
        if r.returncode: print("could not schedule", t); continue
        made += 1; print("queued a carousel for", t.astimezone(TZ).strftime("%a %d %b %H:%M"), "(Norwegian time)")
    print("new posts queued:", made)


def send_links():
    """Send TikTok posts that have appeared on the profile since last time to the Discord webhook (the link only)."""
    hook = os.environ.get("MYCNBOX_WEBHOOK", "").strip(); path = os.path.join(ROOT, "discord_sent.json")
    try:
        r = subprocess.run([sys.executable, "-m", "yt_dlp", "--flat-playlist", "--playlist-items", "1-8", "--print", "%(webpage_url)s", PROFILE], capture_output=True, text=True, timeout=180)
        urls = [l.strip() for l in r.stdout.splitlines() if "/video/" in l or "/photo/" in l]
    except Exception as e: print("could not read the TikTok profile:", e); return
    if not urls: print("no posts read from the TikTok profile"); return
    if not os.path.exists(path):                              # first run: remember what is there, send nothing old
        seen = set(urls)
        try: seen |= {u for e in json.load(open(os.path.join(ROOT, "shorts_log.json"))) for u in (e.get("links") or {}).values()}
        except Exception: pass
        json.dump(sorted(seen), open(path, "w"), indent=0); print("remembered", len(seen), "existing TikTok posts"); return
    seen = set(json.load(open(path))); new = [u for u in reversed(urls) if u not in seen]
    for u in new:
        if hook:
            req = urllib.request.Request(hook + "?wait=true", data=json.dumps({"content": u, "username": "Puro Classico", "allowed_mentions": {"parse": []}}).encode(),
                                         headers={"Content-Type": "application/json", "User-Agent": P.UA}, method="POST")
            try: urllib.request.urlopen(req, timeout=30); print("sent to Discord:", u)
            except Exception as e: print("Discord webhook failed:", e); continue
        seen.add(u)
    json.dump(sorted(seen), open(path, "w"), indent=0); print("new TikTok links:", len(new))


if __name__ == "__main__":
    if not P.KEY: raise SystemExit("POSTIZ_API_KEY is not set")
    send_links()
    top_up()
