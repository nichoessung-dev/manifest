# -*- coding: utf-8 -*-
"""Keeps the next days of month videos queued in Postiz (owner, 25 Nov 2026: videos only, 4 a day per account).

Takes the finished videos from the release "month-videos" (scripts/local_videos.py), oldest first, and schedules each in the
next free slot of its account: the TikTok account it was made for, plus the puroclassico YouTube and Instagram.
month_queue.json records every video queued, so no video is ever posted twice.

  python scripts/month_queue.py                 # fill the next DAYS days (at most MAX_NEW new posts per run: Postiz rate limit)
  python scripts/month_queue.py --old           # list the queued posts this script did not make (nothing is changed)
  python scripts/month_queue.py --old --delete  # delete those (the old silent videos and carousels the month videos replace)
  python scripts/month_queue.py --redo          # swap queued posts that are not yet photo slideshows (same time slot)

Env: POSTIZ_API_KEY, GH_TOKEN, MONTH_DAYS (7), MONTH_MAX_NEW (20), DRY_RUN=1.
"""
import argparse, json, os, subprocess, sys, time, zipfile
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import post_short as P

ROOT = P.ROOT
TZ = ZoneInfo("Europe/Oslo")
TAG = "month-videos"
STATE = os.path.join(ROOT, "month_queue.json")
SLOTS = {"main": ["09:23", "13:23", "17:23", "21:23"], "second": ["10:43", "14:43", "18:43", "22:43"]}     # Norwegian time, 4 a day each
ACCOUNT = {"main": "puroclassico.com", "second": "qualityfinds"}
CHANNELS = "tiktok,youtube,instagram-standalone"
DAYS = int(os.environ.get("MONTH_DAYS", "7")); MAX_NEW = int(os.environ.get("MONTH_MAX_NEW", "20")); DRY = bool(os.environ.get("DRY_RUN", "").strip())


def load():
    try: return json.load(open(STATE, encoding="utf-8"))
    except Exception: return {"queued": {}}


def save(st): json.dump(st, open(STATE, "w", encoding="utf-8"), indent=1, ensure_ascii=False)


def videos():
    r = subprocess.run(["gh", "release", "view", TAG, "--json", "assets", "-q", ".assets[].name"], capture_output=True, text=True, cwd=ROOT)
    names = set(r.stdout.split())
    return sorted(n[:-4] for n in names if n.endswith(".mp4") and n[:-4] + ".json" in names)


def posts(start, end):
    out, t = [], start
    while t < end:
        e = min(t + timedelta(days=7), end)
        q = "?startDate=%s&endDate=%s" % (t.strftime("%Y-%m-%dT%H:%M:%S.000Z"), e.strftime("%Y-%m-%dT%H:%M:%S.000Z"))
        out += P.call("GET", "/posts" + q).get("posts", []); t = e
    return out


def old(delete):
    """Posts waiting in Postiz that this script did not make: the old silent videos and carousels."""
    st = load(); mine = {pid for v in st["queued"].values() for pid in v.get("posts", [])}
    times = {v["at"][:16] for v in st["queued"].values()}      # a month video is never "old", even if its post id was not read
    now = datetime.now(timezone.utc); rows = []
    for p in posts(now + timedelta(minutes=5), now + timedelta(days=40)):
        if p.get("state") not in (None, "QUEUE") or p.get("id") in mine or (p.get("publishDate") or "")[:16] in times: continue
        rows.append(p)
    rows.sort(key=lambda p: p.get("publishDate") or "")
    for p in rows:
        it = p.get("integration") or {}
        print("%s  %-22s %-18s %s" % ((p.get("publishDate") or "")[:16], it.get("providerIdentifier"), it.get("name"), (p.get("content") or "").split("\n")[0][:50]))
    print("old queued posts:", len(rows))
    if not delete or DRY: return
    gone = 0
    for p in rows:
        try: P.call("DELETE", "/posts/" + p["id"]); gone += 1
        except SystemExit as e:
            if "404" in str(e): gone += 1; continue      # already gone with its group
            print("could not delete", p["id"], str(e)[:120])
        time.sleep(2)
    print("deleted:", gone)


SLIDES_REV = "slides1"          # owner, 26 Nov 2026: TikTok and Instagram get photo slideshows, YouTube the voiced video
CTA = "check out puroclassico.com for finds like this"


def queue_one(vid, acct, at, out):
    """Schedule a finished pack at `at` as a photo slideshow (TikTok, Instagram) plus its voiced video (YouTube);
    returns the Postiz post ids, or None when it failed."""
    if subprocess.run(["gh", "release", "download", TAG, "-p", vid + ".*", "-D", out, "--clobber"], cwd=ROOT).returncode:
        print("::warning::could not download", vid); return None
    if subprocess.run(["gh", "release", "download", "month-content", "-p", vid + ".zip", "-D", out, "--clobber"], cwd=ROOT).returncode:
        print("::warning::could not download the pack", vid); return None
    imgs = []
    with zipfile.ZipFile(os.path.join(out, vid + ".zip")) as f:
        pk = json.loads(f.read("slides.json"))
        for j, name in enumerate([pk.get("cover", "00.jpg")] + [x["img"] for x in pk["slides"]]):
            dst = "%s-%02d.jpg" % (vid, j); open(os.path.join(out, dst), "wb").write(f.read(name)); imgs.append(dst)
    mp = os.path.join(out, vid + ".json"); meta = json.load(open(mp, encoding="utf-8")); meta["file"] = os.path.join(out, vid + ".mp4")
    cap = (pk.get("caption") or meta.get("caption") or "").split("\n", 1)
    meta.update(images=imgs, format="month-slides", caption=cap[0] + "\n\n" + CTA + ("\n\n" + cap[1].strip() if len(cap) > 1 else ""))
    json.dump(meta, open(mp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    env = dict(os.environ, SCHEDULE_AT=at, SHORTS_CHANNELS=CHANNELS, TIKTOK_ACCOUNT=ACCOUNT[acct], TIKTOK_METHOD="DIRECT_POST", TIKTOK_VIDEO_METHOD="DIRECT_POST")
    r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "post_short.py"), mp], env=env, capture_output=True, text=True)
    print(r.stdout[-600:]); print(r.stderr[-400:])
    for x in [vid + ".mp4", vid + ".zip"] + imgs:
        try: os.remove(os.path.join(out, x))
        except OSError: pass
    if r.returncode: print("::warning::could not queue", vid); return None
    ids = []
    try: ids = [x.get("postId") for x in json.loads(r.stdout.split("scheduled for %s:" % at, 1)[1].strip().splitlines()[0]) if x.get("postId")]
    except Exception: pass
    return ids


def redo():
    """Queued posts whose video has since been remade with another voice: delete the old posts and queue the new video
    in the same slot. Soonest first, at most MAX_NEW per run (Postiz rate limit)."""
    st = load(); q = st.setdefault("queued", {}); now = datetime.now(timezone.utc)
    out = os.path.join(ROOT, "out", "month"); os.makedirs(out, exist_ok=True)
    md = os.path.join(out, "metas"); os.makedirs(md, exist_ok=True)
    subprocess.run(["gh", "release", "download", TAG, "-p", "*.json", "-D", md, "--clobber"], cwd=ROOT, capture_output=True)
    voice = {}
    for vid in q:
        try: m = json.load(open(os.path.join(md, vid + ".json"), encoding="utf-8")); voice[vid] = m.get("rev") or m.get("voice") or "chatterbox"
        except Exception: voice[vid] = None
    rows = sorted((v["at"], vid) for vid, v in q.items()
                  if voice.get(vid) and voice[vid].endswith("|half") and v.get("rev") != SLIDES_REV
                  and datetime.strptime(v["at"][:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc) > now + timedelta(minutes=25))
    print("queued posts to swap to slideshows:", len(rows))
    if DRY or not rows: return
    live = {}
    for p in posts(now, now + timedelta(days=40)):
        if p.get("state") in (None, "QUEUE"): live.setdefault((p.get("publishDate") or "")[:16], []).append(p["id"])
    made = 0
    for at, vid in rows:
        if made >= MAX_NEW: print("swapped", made, "this run (Postiz rate limit): the next run goes on"); break
        v = q[vid]
        for pid in set(v.get("posts", [])) | set(live.get(at[:16], [])):
            try: P.call("DELETE", "/posts/" + pid)
            except SystemExit as e:
                if "404" not in str(e): print("could not delete", pid, str(e)[:120])
            time.sleep(1)
        ids = queue_one(vid, v["account"], at, out)
        if ids is None: v["posts"] = []; save(st); print("::warning::slot left empty, the next run tries again:", vid, at); break
        v["posts"] = ids; v["rev"] = SLIDES_REV; made += 1; save(st)
        print("swapped %s at %s" % (vid, at), flush=True); time.sleep(20)
    left = len(rows) - made
    print("swapped:", made, "| still to swap:", left)
    s = os.environ.get("GITHUB_STEP_SUMMARY")
    if s: open(s, "a").write("### Slideshow swap: %d swapped, %d left\n" % (made, left))
    save(st)


def fill():
    st = load(); q = st.setdefault("queued", {}); now = datetime.now(timezone.utc)
    taken = {(v["account"], v["at"]) for v in q.values()}
    todo = {"main": [], "second": []}
    for vid in videos():
        if vid in q: continue
        todo["second" if vid.startswith("qf-") else "main"].append(vid)
    out = os.path.join(ROOT, "out", "month"); os.makedirs(out, exist_ok=True); made = 0
    for acct in ("second", "main"):
        for d in range(DAYS + 1):
            day = (now.astimezone(TZ) + timedelta(days=d)).date()
            for s in SLOTS[acct]:
                t = datetime(day.year, day.month, day.day, int(s[:2]), int(s[3:]), tzinfo=TZ).astimezone(timezone.utc)
                at = t.strftime("%Y-%m-%dT%H:%M:%S.000Z")
                if t < now + timedelta(minutes=25) or t > now + timedelta(days=DAYS) or (acct, at) in taken: continue
                if not todo[acct]: break
                if made >= MAX_NEW: print("made", made, "this run (Postiz rate limit): the next run goes on"); save(st); return
                vid = todo[acct].pop(0)
                if DRY: print("DRY_RUN: %s -> %s %s" % (vid, acct, t.astimezone(TZ).strftime("%a %d %b %H:%M"))); continue
                ids = queue_one(vid, acct, at, out)
                if ids is None: todo[acct].insert(0, vid); save(st); return
                q[vid] = {"account": acct, "at": at, "posts": ids, "rev": SLIDES_REV}; taken.add((acct, at)); made += 1; save(st)
                print("queued %s for %s (%s)" % (vid, t.astimezone(TZ).strftime("%a %d %b %H:%M"), acct), flush=True)
                time.sleep(20)
    left = {k: len(v) for k, v in todo.items()}
    print("new posts queued:", made, "| finished videos not yet queued:", left)
    s = os.environ.get("GITHUB_STEP_SUMMARY")
    if s: open(s, "a").write("### Month videos queued: %d new\n\nwaiting: %s\n" % (made, left))
    save(st)


if __name__ == "__main__":
    if not P.KEY: raise SystemExit("POSTIZ_API_KEY is not set")
    ap = argparse.ArgumentParser(); ap.add_argument("--old", action="store_true"); ap.add_argument("--delete", action="store_true")
    ap.add_argument("--redo", action="store_true"); a = ap.parse_args()
    old(a.delete) if a.old else redo() if a.redo else fill()
