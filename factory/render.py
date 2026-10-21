# -*- coding: utf-8 -*-
"""Render factory scripts with the voice, one after the other, and QA each one. Stops cleanly when ElevenLabs credits run out.

  python factory/render.py vf-puffer-1200 vf-cable-knit-450          # style ids (factory/styles_new.json) or story ids (factory/stories_new.json)
  python factory/render.py --all-new                                 # every script that has no finished video in out/ yet

Needs ELEVENLABS_API_KEY in the environment (or "proxy" when the cloud environment adds it to the request itself).
For each id: checks the credits left (make_short.py --credits), skips the video if its spoken characters do not fit, renders it to
out/<id>/, runs factory/qa.py and appends a line to factory/render_log.jsonl (characters used, seconds, problems, sheet path).
A render that comes out silent is treated as the end of the credits: the loop stops there.
"""
import json, os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import qa as Q

MUSIC = "1Jl7ptfgdvN4FlMiEW0Y3NZpzKhIGDlrx"                   # the one track the owner's videos already use
HASHTAGS = "#grisch #oldmoney #taobao #mycnbox #cnfans"
FIXED_OUTRO = "Want to see what's on the China side? The spreadsheet is in the bio. Join the China side!"


def env():
    e = dict(os.environ, STYLES_FILE=os.path.join(HERE, "styles_new.json"), STORIES_FILE=os.path.join(HERE, "stories_new.json"),
             SHORTS_STORY_MUSIC=MUSIC, SHORTS_HASHTAGS=HASHTAGS)
    return e


def credits():
    r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "make_short.py"), "--credits"], capture_output=True, text=True, env=env())
    try: d = json.loads(r.stdout.strip().splitlines()[-1]); return d["character_limit"] - d["character_count"], d
    except Exception: return None, {"error": (r.stdout + r.stderr)[-300:]}


def scripts():
    st = {s["id"]: ("style", s) for s in json.load(open(os.path.join(HERE, "styles_new.json"), encoding="utf-8"))}
    p = os.path.join(HERE, "stories_new.json")
    if os.path.exists(p): st.update({s["id"]: ("story", s) for s in json.load(open(p, encoding="utf-8"))})
    return st


def spoken_chars(kind, s):
    if kind == "style": return sum(len(l.get("say") or "") for l in s["lines"])
    return len(s["hook"]) + sum(len(b["say"]) for b in s["beats"][:4]) + len(FIXED_OUTRO)


def main():
    all_s = scripts(); ids = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--all-new" in sys.argv: ids = [i for i in all_s if not os.path.exists(os.path.join(ROOT, "out", i))]
    log = open(os.path.join(HERE, "render_log.jsonl"), "a", encoding="utf-8")
    for i in ids:
        if i not in all_s: print("unknown id", i); continue
        kind, s = all_s[i]; need = spoken_chars(kind, s); left, info = credits()
        if left is None: print("cannot read credits:", info); break
        if left < need * 1.05: print("credits left %d < %d needed for %s: stopping" % (left, need, i)); break
        out = os.path.join(ROOT, "out", i); t0 = time.time()
        r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "make_short.py"), "--format", kind, "--id", i, "--out", out], capture_output=True, text=True, env=env())
        open(os.path.join(out, "render.log"), "w").write(r.stdout + r.stderr) if os.path.isdir(out) else None
        after, _ = credits(); used = (left - after) if after is not None else None
        if r.returncode: rec = {"id": i, "kind": kind, "ok": False, "error": (r.stdout + r.stderr)[-600:]}
        else:
            q = Q.qa(out); rec = {"id": i, "kind": kind, "ok": True, "chars_used": used, "chars_script": need, "seconds": q["seconds"], "problems": q["problems"], "sheet": q["sheet"],
                                  "warnings": [l.strip() for l in r.stdout.splitlines() if "WARNING" in l], "render_s": round(time.time() - t0)}
        log.write(json.dumps(rec, ensure_ascii=False) + "\n"); log.flush(); print(json.dumps(rec, ensure_ascii=False))
        if rec.get("ok") and "no voiceover" in rec["problems"]: print("the voice is gone (credits used up or the key failed): stopping"); break


if __name__ == "__main__":
    main()
