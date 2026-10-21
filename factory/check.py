# -*- coding: utf-8 -*-
"""Rule check for factory scripts, before anything is rendered.

  python factory/check.py                 # styles_new.json and stories_new.json
  python factory/check.py vf-puffer-1200  # one id

Style videos: ids start with "vf-", 6 to 10 lines, about 20 to 40 seconds, no em or en dashes, none of the banned words,
every product a live find with QC photos, every on-screen and spoken spreadsheet price equal to round(cny * 0.14),
every shop price backed by a "sources" entry of the script and a line in factory/sources.md, only the 55 drive clips and the
music already used, credits that name exactly the creators of the clips used, only the owner's sounds, only library pictures
that exist, the fixed coupon wording.
Stories: 4 beats, approved false, sources, the same word rules, clips only from the pool the existing stories use.
Exit code 1 when anything fails.
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import finds as F
try:
    sys.path.insert(0, os.path.join(ROOT, "scripts")); import make_short as _MS; HOOK_SIZE = _MS.hook_size
except Exception: HOOK_SIZE = None

BANNED = [r"\bfakes?\b", r"\breplicas?\b", r"\bcounterfeits?\b", r"\b1\s*:\s*1\b", r"same as (the )?real", r"\bdupes?\b"]
DASHES = ["—", "–", "‒", "―"]
COUPON = "up to $500 in MyCNBox new-user coupons"
HASHTAGS = "#grisch #oldmoney #taobao #mycnbox #cnfans"
LIBRARY = {"buzzer-wrong", "cash-drawer", "facepalm", "jacket-on-hanger", "knit-folded", "knit-on-hanger", "knit-shoulder-bumps", "lone-sock",
           "magnifier", "parrot-loud", "price-tag-shock", "thumbs-down", "tick-badge", "trophy-mini", "white-sneaker-puddle"}
OWN_SFX = {"bell"}
BAD_CUTOUT = {"964484272869": "white tee on a white photo: the cut-out eats the shirt", "962854952761": "white tee on a white photo: the cut-out eats the shirt",
              "7776333723": "photo does not load"}
WPS = 2.75                                                     # spoken words per second at the renderer's pace (speed 1.03)
NUM = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
       "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30,
       "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}


def spoken_numbers(s):
    """Dollar amounts in a spoken line: "$55", "55 dollars", "fifty-five dollars", "a hundred and thirty dollars"."""
    out = [int(x.replace(",", "")) for x in re.findall(r"\$\s?([\d,]+)", s)]
    out += [int(x.replace(",", "")) for x in re.findall(r"\b([\d,]+)\s+dollars?\b", s)]
    for m in re.finditer(r"\b((?:a|one|two|three|four|five|six|seven|eight|nine)?\s?hundred(?:\s+and)?\s*)?([a-z]+(?:-[a-z]+)?)?\s+dollars?\b", s.lower()):
        h, w = m.group(1), m.group(2); val = 0
        if h: val += 100 * (NUM.get(h.split()[0], 1) if h.split()[0] not in ("a", "hundred") else 1)
        if w:
            parts = w.split("-")
            if all(p in NUM for p in parts): val += sum(NUM[p] for p in parts)
            elif not h: continue
        if val: out.append(val)
    return out


def text_of(o):
    return json.dumps(o, ensure_ascii=False)


def word_rules(label, blob, errs, full=None):
    """blob: what is said or shown. full: the whole record (citations included), checked for dashes only."""
    for d in DASHES:
        if d in (full if full is not None else blob): errs.append("%s: has a dash character %r (use a comma, colon or full stop)" % (label, d))
    low = re.sub(r"https?://\S+", "", blob.lower())
    for b in BANNED:
        if re.search(b, low): errs.append("%s: banned wording /%s/" % (label, b))
    if "coupon" in low and COUPON.lower() not in low: errs.append("%s: coupon wording must be exactly %r" % (label, COUPON))
    if re.search(r"#\w", re.sub(r"https?://\S+", "", blob)): errs.append("%s: no hashtags inside scripts (the caption line is fixed)" % label)


def load_sources_md():
    p = os.path.join(HERE, "sources.md")
    return open(p, encoding="utf-8").read() if os.path.exists(p) else ""


def check_style(st, finds, clips, allowed_music, src_md):
    errs, warns = [], []; sid = st.get("id", "?")
    if not re.fullmatch(r"vf-[a-z0-9][a-z0-9-]{1,45}", sid): errs.append("id must look like vf-some-words (max 48 chars)")
    word_rules(sid, text_of({k: v for k, v in st.items() if k != "sources"}), errs, text_of(st))      # sources are citations (URLs), never said or shown
    lines = st.get("lines") or []
    if not 6 <= len(lines) <= 10: errs.append("%d lines (want 6 to 10)" % len(lines))
    if not st.get("title"): errs.append("no title")
    if st.get("music") not in allowed_music: errs.append("music %r is not one already used" % st.get("music"))
    shop = {}                                                  # shop prices this script may say: value -> source entry
    for s in st.get("sources") or []:
        try: v = int(s["usd"])
        except Exception: errs.append("sources entry without a whole-dollar usd: %r" % s); continue
        if not s.get("url") or not s.get("checked"): errs.append("sources entry %s needs url and checked" % v)
        elif s["url"] not in src_md: errs.append("shop price $%d: %s is not in factory/sources.md" % (v, s["url"]))
        shop[v] = s
    allowed_say = set(shop)
    used_handles, words, secs = set(), 0, 0.0
    first = (lines[0].get("say") or "") if lines else ""
    if len(first.split()) > 9: warns.append("first line is %d words: the hook should read in under 2 seconds" % len(first.split()))
    for k, ln in enumerate(lines, 1):
        say = ln.get("say") or ""
        if not say: errs.append("line %d: nothing said" % k)
        w = len(say.split()); words += w; secs += w / WPS + float(ln.get("pad", 0.14)) + 0.25
        if w > 22: warns.append("line %d: %d words is long for one line" % (k, w))
        line_prices = set()
        for pid in ln.get("products") or []:
            f = finds.get(str(pid))
            if not f: errs.append("line %d: product %s is not an eligible find (missing, no QC photos, dead or sold out)" % (k, pid)); continue
            line_prices.add(f["usd"]); allowed_say.add(f["usd"])
            if str(pid) in BAD_CUTOUT: errs.append("line %d: product %s: %s" % (k, pid, BAD_CUTOUT[str(pid)]))
        for pid, tag in (ln.get("tags") or {}).items():
            if str(pid) not in [str(x) for x in ln.get("products") or []]: errs.append("line %d: tag for %s, which is not on the line" % (k, pid))
            big = str(tag[0]) if tag else ""; bad = len(tag) > 2 and tag[2] == "bad"
            for m in re.findall(r"\$([\d,]+)", big):
                v = int(m.replace(",", ""))
                if bad:                                    # struck through: a sourced shop price, or (games) the find's own price
                    own = finds.get(str(pid)) and v == finds[str(pid)]["usd"]
                    if v not in shop and not own: errs.append("line %d: shop price $%d on screen has no source" % (k, v))
                elif finds.get(str(pid)) and v != finds[str(pid)]["usd"]:
                    if not re.search(r"total", " ".join(map(str, tag)).lower()): errs.append("line %d: tag $%d for %s, the find costs $%d" % (k, v, pid, finds[str(pid)]["usd"]))
            if len(tag) > 1 and re.search(r"in the shop", str(tag[1]).lower()) and not bad: warns.append("line %d: 'in the shop' tag not marked bad" % k)
            if len(tag) > 1: word_rules("line %d tag" % k, str(tag[1]), errs)
        for d in ln.get("drive") or []:
            fid = d[0] if isinstance(d, list) else d; start = float(d[1]) if isinstance(d, list) and len(d) > 1 else 0.0
            c = clips.get(fid)
            if not c: errs.append("line %d: drive clip %s is not one of the 55" % (k, fid)); continue
            if c.get("kind") == "video" and start > max(0.0, c["seconds"] - 0.6): errs.append("line %d: start %.1fs is past the end of %s (%.1fs)" % (k, start, fid, c["seconds"]))
            if c.get("credit") and c["credit"] != "unknown": used_handles.add(c["credit"])
        if ln.get("clips"): errs.append("line %d: 'clips' (Pexels) is not allowed in style videos: only the drive clips" % k)
        if ln.get("stock"): errs.append("line %d: 'stock' clips are not allowed: only the drive clips" % k)
        ins = ln.get("insert") or []
        for i in (ins if isinstance(ins, list) else [ins]):
            slug = i.get("slug") if isinstance(i, dict) else i
            if slug not in LIBRARY: errs.append("line %d: insert %r is not in the asset library" % (k, slug))
        sf = ln.get("sfx") or []
        for h in (sf if isinstance(sf, list) else [sf]):
            n = h.get("name") if isinstance(h, dict) else h
            if n not in OWN_SFX: errs.append("line %d: sfx %r is not one of the owner's sounds" % (k, n))
        if ln.get("hook") and len(str(ln["hook"]).replace("*", "").split()) > 12: warns.append("line %d: hook over 12 words" % k)
        if ln.get("hook") and HOOK_SIZE:
            n_l, px = HOOK_SIZE(str(ln["hook"]))
            if px < 84 or n_l > 3: warns.append("line %d: hook comes out small (%d lines, %d px): shorten it" % (k, n_l, px))
    for k, ln in enumerate(lines, 1):                          # spoken dollars must be a find on the video or a sourced shop price
        for v in spoken_numbers(ln.get("say") or ""):
            extra = set(st.get("totals", [])) | set(st.get("thresholds", [])) | ({500} if COUPON.lower() in (ln.get("say") or "").lower() else set())
            if v not in allowed_say and v not in extra: errs.append("line %d: says $%d, which is neither a find's price in this video nor a sourced shop price (a sum goes in \"totals\", a game's line in \"thresholds\")" % (k, v))
    for t in st.get("totals", []) + st.get("thresholds", []):
        if not isinstance(t, int): errs.append("totals and thresholds must be whole dollars")
    cred = set(re.findall(r"@[A-Za-z0-9._]+", st.get("credits") or ""))
    if used_handles and cred != used_handles: errs.append("credits %s do not match the clips used %s" % (sorted(cred), sorted(used_handles)))
    if not used_handles and st.get("credits"): errs.append("credits set but no drive clip used")
    if not 20 <= secs <= 42: (errs if not 16 <= secs <= 46 else warns).append("estimated %.0f s (want 20 to 40)" % secs)
    return errs, warns, secs


def check_story(st, pool):
    errs, warns = [], []; sid = st.get("id", "?")
    shown = {"hook": st.get("hook"), "label": st.get("label"), "beats": [{k: b.get(k) for k in ("say", "text", "gfx")} for b in st.get("beats") or []]}
    word_rules(sid, text_of(shown), errs, text_of(st))      # banned words: what is said or shown; dashes: the whole record
    if st.get("approved") is not False: errs.append("approved must be false")
    beats = st.get("beats") or []
    if len(beats) != 4: errs.append("%d beats (the renderer speaks exactly the first 4)" % len(beats))
    if not st.get("sources"): errs.append("no sources")
    if len((st.get("hook") or "").split()) > 14: warns.append("hook over 14 words")
    words = len((st.get("hook") or "").split()) + sum(len((b.get("say") or "").split()) for b in beats)
    secs = words / WPS + 5 * 0.4 + 5.0
    if not 20 <= secs <= 42: warns.append("estimated %.0f s" % secs)
    for k, b in enumerate(beats, 1):
        if len((b.get("say") or "").split()) > 26: warns.append("beat %d over 25 words" % k)
        for c in b.get("clips") or []:
            if c not in pool: errs.append("beat %d: clip %s is not in the existing story clip pool" % (k, c))
        if not b.get("clips"): errs.append("beat %d: no clips (search needs a Pexels key this setup does not have)" % k)
    for part in ("intro", "outro"):
        cs = (st.get("clips") or {}).get(part) or []
        if not cs: errs.append("no %s clips" % part)
        for c in cs:
            if c not in pool: errs.append("%s clip %s is not in the pool" % (part, c))
    if not str(st.get("confidence", "")).split(" ")[0] in ("high", "medium", "low"): errs.append("confidence must start with high, medium or low")
    return errs, warns, secs


def main():
    want = set(sys.argv[1:]); finds, _, _, _ = F.load(); src_md = load_sources_md(); bad = 0
    clips = {c["id"]: c for c in json.load(open(os.path.join(HERE, "clips.json"), encoding="utf-8"))["drive"]}
    allowed_music = {s.get("music") for s in json.load(open(os.path.join(ROOT, "scripts", "styles.json"), encoding="utf-8")) if s.get("music")}
    pool = {c["id"] for c in json.load(open(os.path.join(HERE, "clips.json"), encoding="utf-8"))["pexels"]}
    p = os.path.join(HERE, "styles_new.json")
    styles = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else []
    ids = [s.get("id") for s in styles]
    for d in {i for i in ids if ids.count(i) > 1}: print("DUPLICATE id", d); bad += 1
    for st in styles:
        if want and st.get("id") not in want: continue
        e, w, secs = check_style(st, finds, clips, allowed_music, src_md)
        print("%-4s %-44s ~%2.0fs %s" % ("OK" if not e else "FAIL", st.get("id"), secs, ("| " + "; ".join(w)) if w else ""))
        for x in e: print("      x", x)
        bad += bool(e)
    p = os.path.join(HERE, "stories_new.json")
    stories = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else []
    for st in stories:
        if want and st.get("id") not in want: continue
        e, w, secs = check_story(st, pool)
        print("%-4s %-44s ~%2.0fs %s" % ("OK" if not e else "FAIL", "[story] " + st.get("id", "?"), secs, ("| " + "; ".join(w)) if w else ""))
        for x in e: print("      x", x)
        bad += bool(e)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
