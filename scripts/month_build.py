# -*- coding: utf-8 -*-
"""Builds slideshows for the month videos (owner, 25 Nov 2026: videos only, 4 a day per account, the owner's own voice made
locally). Each slideshow is packed as <id>.zip (the slide pictures + slides.json with the line to say on each slide) and put on
the GitHub release "month-content". scripts/local_videos.py (run on the owner's PC, which has the GPU) turns each one into a
video with the owner's voice and music, and scripts/month_queue.py schedules the videos in Postiz.

  python scripts/month_build.py --account second --count 40 [--minutes 320]
  python scripts/month_build.py --account main --count 60

second = Qualityfinds (rug pictures, Google image model; checks on Claude), main = puroclassico.com (real QC photos, no image cost).
The usage records (slides_used.json / finds_used.json) are saved after every slideshow, so a photo is never used twice.
Stops at the first failed Qualityfinds build: a failure there only spends more images.
"""
import argparse, json, os, shutil, subprocess, sys, time, zipfile
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TAG = os.environ.get("MONTH_TAG", "month-content")


def sh(cmd, **kw):
    print("+", " ".join(cmd)[:200], flush=True); return subprocess.run(cmd, **kw)


def ensure_release():
    if sh(["gh", "release", "view", TAG], capture_output=True).returncode:
        sh(["gh", "release", "create", TAG, "--prerelease", "--title", "Month videos: slideshows", "--notes", "Slideshow packs for the month videos (scripts/month_build.py). Not a software release."], check=True)


def save_state(path):
    """Commit this account's usage record right away (merged onto the newest main), so the next slideshow and other jobs see it."""
    tmp = os.path.join(os.environ.get("RUNNER_TEMP", "/tmp"), "state-" + os.path.basename(path)); shutil.copy(path, tmp)
    for n in range(5):
        sh(["git", "fetch", "-q", "origin", "main"]); sh(["git", "reset", "-q", "--hard", "FETCH_HEAD"])
        sh([sys.executable, os.path.join(ROOT, "scripts", "merge_state.py"), tmp, path])
        sh(["git", "add", path])
        if not sh(["git", "diff", "--cached", "--quiet"]).returncode: return
        sh(["git", "commit", "-q", "-m", "chore: month build state [skip ci]"])
        if not sh(["git", "push", "-q", "origin", "HEAD:main"]).returncode: return
        time.sleep(6 * (n + 1))
    print("::warning::could not save", path)


def rug_lines(out):
    log = json.load(open(os.path.join(out, "log.txt"), encoding="utf-8"))
    def line(x):
        ns = x.get("label") or x.get("name") or []; us = x.get("usd") or []
        ns = ns if isinstance(ns, list) else [ns]; us = us if isinstance(us, list) else [us]
        return ", and ".join(str(n).lower() + (", %d dollars" % u if isinstance(u, (int, float)) and u else "") for n, u in zip(ns, us + [None] * len(ns)))
    return [line(x) for x in log["slides"]]


def pack(account, out, meta_path, k):
    meta = json.load(open(meta_path, encoding="utf-8"))
    images = [os.path.join(out, os.path.basename(i)) for i in meta.get("images") or []]
    if account == "second":
        says = rug_lines(out)
    else:
        names, prices = meta.get("names") or [], meta.get("prices") or []
        says = [(str(n).lower() + (", %d dollars" % p if isinstance(p, (int, float)) and p else "")) if n else "" for n, p in zip(names, prices + [None] * len(names))]
    if len(images) < 4 or len(says) < len(images) - 1: raise RuntimeError("pack: %d images, %d lines" % (len(images), len(says)))
    pid = "%s-%s-%02d" % ("qf" if account == "second" else "pc", datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S"), k)
    pk = {"id": pid, "account": account, "caption": meta.get("caption") or "", "cover": "00.jpg",
          "slides": [{"img": "%02d.jpg" % (j + 1), "say": says[j]} for j in range(len(images) - 1)]}
    z = os.path.join(ROOT, "out", pid + ".zip")
    with zipfile.ZipFile(z, "w", zipfile.ZIP_STORED) as f:
        for j, p in enumerate(images): f.write(p, "%02d.jpg" % j)
        f.writestr("slides.json", json.dumps(pk, ensure_ascii=False, indent=1))
    return z, pid


def build_cmd(account, out):
    if account == "second":
        return [sys.executable, os.path.join(ROOT, "scripts", "make_rug.py"), "--n", os.environ.get("FINDS_SLIDES", "6"), "--own", "0",
                "--state", "slides_used.json", "--commit-state", "--avoid", "scripts/slides_exclude.json", "--out", out]
    cmd = [sys.executable, os.path.join(ROOT, "scripts", "make_finds.py"), "--folder", os.environ["FINDS_FOLDER"], "--slides", os.environ.get("FINDS_SLIDES", "9"),
           "--hold", "0.8", "--own", "1", "--state", "finds_used.json", "--commit-state", "--out", out]
    covers = os.environ.get("FINDS_COVERS", "1gRUw48kSbbNU5RKjFUdPdgwR8SQvjSyM")
    return cmd + ["--covers", covers]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--account", choices=["main", "second"], required=True)
    ap.add_argument("--count", type=int, default=10); ap.add_argument("--minutes", type=float, default=320)
    a = ap.parse_args(); t0 = time.time(); ensure_release(); made = 0; fails = 0
    state = "slides_used.json" if a.account == "second" else "finds_used.json"
    for k in range(a.count):
        if time.time() - t0 > a.minutes * 60: print("time is up: stopping"); break
        out = os.path.join(ROOT, "out", "mb-%s-%02d" % (a.account, k)); shutil.rmtree(out, ignore_errors=True); os.makedirs(out)
        print("::group::slideshow %d of %d (%s)" % (k + 1, a.count, a.account), flush=True)
        r = sh(build_cmd(a.account, out))
        metas = [os.path.join(out, f) for f in os.listdir(out) if f.endswith(".json") and f not in ("log.json",)]
        metas = [m for m in metas if os.path.basename(m) in ("rug.json",) or os.path.basename(m).startswith("finds-")]
        if os.path.exists(os.path.join(ROOT, state)): save_state(state)
        if r.returncode or not metas:
            print("::endgroup::"); print("::warning::slideshow %d was not made" % (k + 1))
            fails += 1
            if a.account == "second" and fails >= 2: print("stopping: two Qualityfinds builds in a row failed, more would only spend images"); break
            continue
        fails = 0
        try:
            z, pid = pack(a.account, out, metas[0], k)
            sh(["gh", "release", "upload", TAG, z, "--clobber"], check=True); made += 1; print("uploaded", pid)
        except Exception as e: print("::warning::could not pack slideshow %d: %s" % (k + 1, str(e)[:200]))
        print("::endgroup::")
    print("slideshows made:", made)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary: open(summary, "a").write("### Month slideshows (%s): %d made\n" % (a.account, made))
    if not made: raise SystemExit("no slideshow was made")


if __name__ == "__main__":
    main()
