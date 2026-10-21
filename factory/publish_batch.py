# -*- coding: utf-8 -*-
"""Put finished videos on an orphan branch videos-batch-NN (the layout of "previews-batch", which the Post videos workflow reads):
<id>.mp4 + <id>.json per video, plus INDEX.md. The branch is replaced on every run (force push). Never main.

  python factory/publish_batch.py --nn 01 --ids vf-a,vf-b,...          # videos from out/<id>/, scores from factory/scores.json
  python factory/publish_batch.py --nn 03 --ids ... --report factory/final_report.md     # the last batch carries the final report
  python factory/publish_batch.py --nn 01 --ids ... --dry-run          # build the folder, push nothing

Each <id>.json is the render's own meta file with the caption's hashtag line set to the owner's fixed one.
"""
import argparse, glob, json, os, re, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
HASHTAGS = "#grisch #oldmoney #taobao #mycnbox #cnfans"
REMOTE = "https://github.com/nichoessung-dev/manifest"


def fixed_caption(cap):
    parts = cap.rstrip().split("\n\n")
    if parts and parts[-1].lstrip().startswith("#"): parts = parts[:-1]
    cap = "\n\n".join(parts + [HASHTAGS])
    return cap.replace("—", ",").replace("–", ",")


def script_info(i):
    """Title, hook line, product ids and sources of one id, read from the factory scripts."""
    for name, kind in (("styles_new.json", "style"), ("stories_new.json", "story")):
        p = os.path.join(HERE, name)
        if not os.path.exists(p): continue
        for st in json.load(open(p, encoding="utf-8")):
            if st.get("id") != i: continue
            if kind == "style":
                prods = []
                for ln in st["lines"]:
                    for pid in ln.get("products") or []:
                        if str(pid) not in prods: prods.append(str(pid))
                return {"kind": kind, "title": st.get("title", ""), "hook": st["lines"][0].get("say", ""), "products": prods,
                        "sources": ["$%s: %s" % (x["usd"], x["url"]) for x in st.get("sources") or []]}
            return {"kind": kind, "title": st.get("label", "").replace("*", ""), "hook": st.get("hook", ""), "products": [], "sources": []}
    return {}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--nn", required=True); ap.add_argument("--ids", required=True)
    ap.add_argument("--out-root", default=os.path.join(ROOT, "out")); ap.add_argument("--report"); ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if not re.fullmatch(r"\d{2}", a.nn): raise SystemExit("--nn is two digits, like 01")
    branch = "videos-batch-" + a.nn
    ids = [i.strip() for i in a.ids.split(",") if i.strip()]
    if not ids or any(not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,48}", i) for i in ids): raise SystemExit("bad id list")
    scores = json.load(open(os.path.join(HERE, "scores.json"), encoding="utf-8")) if os.path.exists(os.path.join(HERE, "scores.json")) else {}
    work = tempfile.mkdtemp(prefix=branch + "-"); rows = []
    for i in ids:
        mp4 = sorted(glob.glob(os.path.join(a.out_root, i, "*.mp4"))); js = sorted(glob.glob(os.path.join(a.out_root, i, "short-*.json")))
        if not mp4 or not js: raise SystemExit("no finished video for %s in %s" % (i, os.path.join(a.out_root, i)))
        meta = json.load(open(js[0], encoding="utf-8"))
        if not meta.get("voiceover"): raise SystemExit("%s has no voiceover: not fit for a batch" % i)
        if meta.get("missing_assets"): raise SystemExit("%s is missing library files" % i)
        meta["caption"] = fixed_caption(meta.get("caption", "")); meta["file"] = i + ".mp4"
        shutil.copy(mp4[0], os.path.join(work, i + ".mp4")); json.dump(meta, open(os.path.join(work, i + ".json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
        s = dict(script_info(i), **scores.get(i, {})); rows.append((i, s, meta))
    L = ["# %s" % branch, "", "Finished videos, voice on. Nothing here is posted: the Post videos workflow posts an id only when the owner runs it with ref %s." % branch, "",
         "| id | kind | title | length | score | hook line | product ids | shop-price sources |", "|---|---|---|---|---|---|---|---|"]
    for i, s, meta in rows:
        kind = s.get("kind", "") + (" (needs owner approval)" if s.get("kind") == "story" else "")
        L.append("| %s | %s | %s | %.1fs | %s | %s | %s | %s |" % (i, kind, s.get("title", "").replace("|", "/"), meta.get("seconds", 0), s.get("score", ""), s.get("hook", "").replace("|", "/"),
                                                              " ".join(s.get("products", [])), " ".join(s.get("sources", [])) or "none"))
    L += ["", "Scores are 1 to 10 for hook, clarity and look (the mean of the three). Stories are \"approved\": false: the owner approves each one before it is posted.",
          "Shop-price sources: the page each \"around $X in the shop\" was read on (details in factory/sources.md on the video-factory branch). News sources: factory/stories_new.json.", ""]
    if a.report: L += ["", open(a.report, encoding="utf-8").read()]
    open(os.path.join(work, "INDEX.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    if a.dry_run: print("dry run: folder", work); return
    g = lambda *c: subprocess.run(["git"] + list(c), cwd=work, check=True)
    g("init", "-q", "-b", branch); g("add", "-A")
    g("-c", "user.name=video-factory", "-c", "user.email=video-factory@users.noreply.github.com", "commit", "-qm", "%s: %d videos [skip ci]" % (branch, len(rows)))
    if branch in ("main", "master") or not branch.startswith("videos-batch-"): raise SystemExit("refusing to push %s" % branch)
    g("push", "-f", REMOTE, "HEAD:refs/heads/" + branch); print("pushed", branch, len(rows), "videos")


if __name__ == "__main__":
    main()
