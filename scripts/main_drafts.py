# -*- coding: utf-8 -*-
"""Every morning: send the next puroclassico.com rug slideshows to the TikTok app as drafts (owner, 27 Nov 2026).

Takes the "pcr-" packs (month_build.py with MAIN_RUG=1) from the release "month-content", oldest first, and hands each to
Postiz for TikTok puroclassico.com with TIKTOK_METHOD=UPLOAD: the post lands in the TikTok inbox as a draft, and the owner
picks a sound and posts it. main_drafts.json records the packs sent, so a pack is never sent twice.

  python scripts/main_drafts.py            # send DRAFTS_PER_DAY (4) drafts
Env: POSTIZ_API_KEY, GH_TOKEN, DRAFTS_PER_DAY, DRY_RUN=1.
"""
import json, os, shutil, subprocess, sys, time, zipfile
from datetime import datetime, timedelta, timezone
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import post_short as P

ROOT = P.ROOT
TAG = "month-content"
STATE = os.path.join(ROOT, "main_drafts.json")
N = int(os.environ.get("DRAFTS_PER_DAY", "4")); DRY = bool(os.environ.get("DRY_RUN", "").strip())
CTA = "check out puroclassico.com for finds like this"
END = os.path.join(ROOT, "scripts", "rug", "cta_end.jpg")
ACCOUNTS = [a.strip() for a in os.environ.get("DRAFT_ACCOUNTS", "puroclassico.com,qualityfinds").split(",") if a.strip()]   # each account gets its OWN packs, never the same one (owner, 27 Nov 2026)


def main():
    try: st = json.load(open(STATE, encoding="utf-8"))
    except Exception: st = {"sent": {}}
    r = subprocess.run(["gh", "release", "view", TAG, "--json", "assets", "-q", ".assets[].name"], capture_output=True, text=True, cwd=ROOT)
    done = lambda v: bool(st["sent"].get(v))           # owner, 27 Nov 2026: never the same slideshow on both accounts, so a pack sent anywhere is used up
    packs = sorted(n[:-4] for n in r.stdout.split() if n.startswith("pcr-") and n.endswith(".zip") and not done(n[:-4]))
    print("rug slideshows not sent yet:", len(packs))
    out = os.path.join(ROOT, "out", "drafts"); os.makedirs(out, exist_ok=True); sent = 0
    plan = [(vid, ACCOUNTS[i % len(ACCOUNTS)]) for i, vid in enumerate(packs[:N * len(ACCOUNTS)])]   # N each, every account its own packs
    for vid, acct in plan:
        if DRY: print("DRY_RUN: would send", vid, "to", acct); continue
        if subprocess.run(["gh", "release", "download", TAG, "-p", vid + ".zip", "-D", out, "--clobber"], cwd=ROOT).returncode:
            print("::warning::could not download", vid); continue
        imgs = []
        with zipfile.ZipFile(os.path.join(out, vid + ".zip")) as f:
            pk = json.loads(f.read("slides.json"))
            for j, name in enumerate([pk.get("cover", "00.jpg")] + [x["img"] for x in pk["slides"]]):
                dst = "%s-%02d.jpg" % (vid, j); open(os.path.join(out, dst), "wb").write(f.read(name)); imgs.append(dst)
        if os.path.exists(END):                                # the owner's "All finds in bio" slide closes every slideshow (27 Nov 2026)
            dst = "%s-end.jpg" % vid; shutil.copy(END, os.path.join(out, dst)); imgs.append(dst)
        cap = (pk.get("caption") or "").split("\n", 1)
        meta = {"file": "", "images": imgs, "format": "main-draft",
                "caption": "\n" + (cap[1].strip() if len(cap) > 1 else "")}     # hashtags only (owner, 27 Nov 2026): no title, no text; the end slide carries the CTA
        mp = os.path.join(out, vid + ".json"); json.dump(meta, open(mp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        at = (datetime.now(timezone.utc) + timedelta(minutes=3)).strftime("%Y-%m-%dT%H:%M:00.000Z")
        env = dict(os.environ, SCHEDULE_AT=at, SHORTS_CHANNELS="tiktok", TIKTOK_ACCOUNT=acct, TIKTOK_METHOD="UPLOAD", TIKTOK_AUTO_MUSIC="no")     # auto-music on made TikTok drop photo drafts (27 Nov 2026)
        p = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "post_short.py"), mp], env=env, capture_output=True, text=True)
        print(p.stdout[-500:]); print(p.stderr[-300:])
        for x in [vid + ".zip", vid + ".json"] + imgs:
            try: os.remove(os.path.join(out, x))
            except OSError: pass
        if p.returncode: print("::warning::could not send", vid, "to", acct); continue
        st["sent"][vid] = {acct: at}; json.dump(st, open(STATE, "w", encoding="utf-8"), indent=1)
        print("sent as a draft:", vid, "to", acct, flush=True); sent += 1; time.sleep(20)
    left = len(packs) - sent
    print("drafts sent:", sent, "| rug slideshows left:", left)
    s = os.environ.get("GITHUB_STEP_SUMMARY")
    if s: open(s, "a").write("### puroclassico drafts: %d sent, %d left%s\n" % (sent, left, " (pick more items!)" if left < N * len(ACCOUNTS) * 3 else ""))


if __name__ == "__main__":
    if not P.KEY: raise SystemExit("POSTIZ_API_KEY is not set")
    main()
