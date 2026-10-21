# -*- coding: utf-8 -*-
"""Build factory/stories_new.json from the fact-checked news drafts (factory/news_research.json).

Only stories a skeptic re-checked are kept ("pass" or "fixed"; "drop" is left out and listed in factory/news_dropped.md).
Clips: each beat gets two clips from the pool the existing stories already use (clips.json "pexels"), picked by matching the beat's
"show" phrases, text and the story's themes against each clip's summary, tags and best_for; intro and outro clips the same way from
the hook and themes. A clip is used once per story. "approved" is always false.

  python factory/build_stories.py
"""
import json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
STOP = set("a an the and or of in on to for with from by at is are be it its this that your you their our not no as into over under up down".split())


def words(s):
    return [w for w in re.findall(r"[a-z0-9]+", (s or "").lower()) if w not in STOP and len(w) > 2]


def score(clip, phrases):
    hay = " ".join([clip.get("summary", "")] + clip.get("tags", []) + clip.get("best_for", [])).lower()
    hw = set(words(hay)); s = 0.0
    for p in phrases:
        pw = words(p)
        if not pw: continue
        hit = sum(1 for w in pw if w in hw or any(h.startswith(w[:5]) for h in hw if len(w) > 5))
        s += hit / len(pw)
        if p.lower() in hay: s += 1.0
    s += 0.15 * (clip.get("quality") or 3)
    bad = (clip.get("issues") or "").lower()
    if "horizontal" in bad: s -= 0.6
    if "face" in bad and "close" in bad: s -= 0.3
    return s


def pick(pool, used, phrases, n=2):
    ranked = sorted((c for c in pool if c["id"] not in used), key=lambda c: -score(c, phrases))
    out = [c["id"] for c in ranked[:n]]; used.update(out); return out


def main():
    research = json.load(open(os.path.join(HERE, "news_research.json"), encoding="utf-8"))
    pool = json.load(open(os.path.join(HERE, "clips.json"), encoding="utf-8"))["pexels"]
    keep, dropped = [], []
    cp = os.path.join(HERE, "story_clips.json"); hand = json.load(open(cp, encoding="utf-8")) if os.path.exists(cp) else {}
    for st in research:
        if st.get("verdict") == "drop" or st.get("status") == "dropped":
            dropped.append(st); continue
        used = set(); th = st.get("themes") or []
        beats = []
        for b in st["beats"][:4]:
            show = b.get("show") if isinstance(b.get("show"), list) else [b.get("show") or ""]
            beats.append({"say": b["say"], "show": show, "text": b.get("text", ""), "gfx": b.get("gfx") or {},
                          "clips": b.get("clips") or pick(pool, used, show + [b.get("text", "")] + th[:2])})
        out = {"id": st["id"], "hook": st["hook"], "label": st.get("label") or st["hook"], "beats": beats,
               "takeaway": st.get("takeaway", ""), "sources": st.get("sources", []), "source_notes": st.get("source_notes", []),
               "claims": st.get("claims", []), "confidence": st.get("confidence", ""), "themes": th, "approved": False,
               "clips": {"intro": pick(pool, used, [st["hook"]] + th[:3]), "outro": pick(pool, used, th[-3:] + [st.get("takeaway", "")])}}
        h = hand.get(st["id"])
        if h:                                                  # hand-picked: intro, beats 1-4, outro
            out["clips"] = {"intro": h[0], "outro": h[5]}
            for b, c in zip(out["beats"], h[1:5]): b["clips"] = c
        if st.get("update_of"): out["update_of"] = st["update_of"]
        if st.get("notes"): out["notes"] = st["notes"]
        keep.append(out)
    json.dump(keep, open(os.path.join(HERE, "stories_new.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    L = ["# News ideas left out", "", "Dropped after research or fact-checking. A dropped idea is better than a weak or wrong video.", ""]
    for d in dropped:
        L.append("- **%s** (idea %s): %s" % (d.get("id"), d.get("idea_no"), (d.get("drop_reason") or "; ".join(d.get("problems", [])) or "").replace("\n", " ")))
    open(os.path.join(HERE, "news_dropped.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("stories:", len(keep), "dropped:", len(dropped))


if __name__ == "__main__":
    main()
