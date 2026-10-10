# -*- coding: utf-8 -*-
"""Fill the asset library that the "style" videos reuse: generated pictures (OpenAI Images API) and stock clips (Pixabay).

What to make is listed in scripts/assets.json (slug -> picture prompt or stock search). The files do not live on main but on the
git branch "assets" (locally: any folder):   <lib>/gen/<slug>.png   <lib>/stock/<slug>.mp4   <lib>/library.json
A slug that is in the library is never made again unless --force: assets are made once and reused across videos.

  python scripts/make_assets.py --lib assets-lib --style the-belt          # what that video uses ("" or auto: what all videos use)
  python scripts/make_assets.py --lib assets-lib --slugs price-tag-shock,cash-count
  python scripts/make_assets.py --lib assets-lib --all --dry-run           # no keys, no network: only says what it would do

Needs: pillow. Keys: OPENAI_API_KEY (pictures), PIXABAY_API_KEY (stock). A missing key or a failed asset never fails the run:
the exit code is 0 unless the arguments, assets.json or styles.json are not valid. Prints no secrets.
A picture that was delivered (and paid for) but is not usable, or a prompt the content policy refuses, is counted in <lib>/failed.json:
after 2 runs like that the slug is left alone until its prompt (or size, quality, model chain) changes, or --force.
"""
import argparse, base64, datetime, hashlib, io, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPEC = os.environ.get("ASSETS_FILE", "").strip() or os.path.join(ROOT, "scripts", "assets.json")      # both paths can be pointed elsewhere for tests
STYLES = os.environ.get("STYLES_FILE", "").strip() or os.path.join(ROOT, "scripts", "styles.json")
STATE = os.path.join(ROOT, "shorts_posted.json")           # the renderer's counters: "style" says which video a run without an id renders
OK = os.environ.get("OPENAI_API_KEY", "").strip(); PK = os.environ.get("PIXABAY_API_KEY", "").strip()
SLUG = re.compile(r"[a-z0-9][a-z0-9-]{1,48}"); SIZE = re.compile(r"auto|\d{3,4}x\d{3,4}"); QUAL = ("low", "medium", "high", "auto")      # used with fullmatch
FILES = {"image": "gen/%s.png", "stock": "stock/%s.mp4"}
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"   # Pixabay answers 403 to Python's own user agent
DEFAULTS = {"model_chain": ["gpt-image-2.5-flare", "gpt-image-2.5-sunburst", "gpt-image-1.5", "gpt-image-1"], "quality": "medium", "size": "1024x1024", "style_suffix": ""}
WAITS = (8, 24)            # seconds before the 2nd and 3rd try after HTTP 429 / 5xx / no answer
EDGE = 16                  # transparent border kept round a trimmed picture, px
MAX_MP4 = 24 << 20         # a stock clip larger than this is not taken (it has to fit on a git branch)
TRIES = 2                  # runs in which a picture may be paid for and thrown away (or refused) before its slug is left alone
try: BUDGET = float(os.environ.get("ASSETS_BUDGET", "") or 1200)      # seconds: after this no new asset and no further try is started
except ValueError: BUDGET = 1200.0
T0 = time.time()
NOTES = []                 # things the owner should see in the run summary, besides the rows


class Fail(Exception):               # this asset cannot be made; the run goes on. dud: it cost money or would fail the same way again (counted in failed.json)
    def __init__(self, msg, dud=False): Exception.__init__(self, msg); self.dud = dud
class Stop(Fail): pass               # nothing of this kind can be made in this run (key refused, no credit)


def scrub(t):
    for k in (OK, PK):
        if k: t = t.replace(k, "***").replace(urllib.parse.quote_plus(k), "***")
    return t


def tidy(t, n):                                           # a piece of an answer for the log: keys are masked BEFORE it is cut (a cut inside a key would leave its start readable)
    return re.sub(r"(?i)([?&]key=)[^&\s\"'<>\\]*", r"\1***", scrub(t))[:n]


def now(fmt="%Y-%m-%dT%H:%M:%SZ"): return datetime.datetime.now(datetime.timezone.utc).strftime(fmt)


def say(*a): print(scrub(" ".join(str(x) for x in a)), flush=True)


def die(msg): say("error:", msg); sys.exit(2)


def late(): return time.time() - T0 > BUDGET


# the only two functions that touch the network (tests replace them)
def call(url, body=None, headers=None, timeout=180):
    """One JSON request -> (status, answer as a dict). Status 0 = no answer. Never prints or returns the url: Pixabay's carries the key."""
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None, headers=headers or {}, method="POST" if body is not None else "GET")
    def parsed(t):
        try: j = json.loads(t)
        except Exception: j = None
        return j if isinstance(j, dict) else {"raw": tidy(t, 200)}
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r: return r.status, parsed(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e: return e.code, parsed(e.read().decode("utf-8", "replace"))
    except Exception as e: return 0, {"raw": type(e).__name__}


def grab(url, timeout=120, limit=MAX_MP4):
    """The bytes of a file (at most `limit`)."""
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=timeout) as r: b = r.read(limit + 1)
    if len(b) > limit: raise ValueError("the file is larger than %d MB" % (limit >> 20))
    return b


def errtext(j):
    e = j.get("error"); return tidy(re.sub(r"\s+", " ", str((e.get("message") if isinstance(e, dict) else e) or j.get("raw") or "no details")), 160)


def verdict(st, j):                                       # what an answer of the Images API means for the model chain
    e = j.get("error") if isinstance(j.get("error"), dict) else {}; code = str(e.get("code") or ""); msg = str(e.get("message") or "").lower()
    if st == 200: return "ok"
    if code in ("content_policy_violation", "moderation_blocked") or "safety system" in msg or "content policy" in msg: return "refused"
    if st == 401 or code in ("invalid_api_key", "insufficient_quota", "billing_hard_limit_reached"): return "stop"
    if st in (0, 408, 409, 429) or st >= 500: return "retry"
    return "next"                                         # any other 4xx: this model, or one of the parameters on this model, is not supported


def check_png(b, transparent):
    """A generated picture -> (png bytes, (w, h)), trimmed to its content plus a small border when transparent. ValueError when it is not usable."""
    try: im = Image.open(io.BytesIO(b)); im.load()
    except Exception: raise ValueError("the picture does not decode")
    if not transparent: im = im.convert("RGB")
    else:
        if im.mode not in ("RGBA", "LA") and "transparency" not in im.info: raise ValueError("the picture has no alpha channel")
        im = im.convert("RGBA"); a = im.getchannel("A"); box = a.point(lambda v: 255 if v > 8 else 0).getbbox()
        if box is None: raise ValueError("the picture is empty")
        if a.histogram()[0] < 0.01 * im.size[0] * im.size[1]: raise ValueError("the background is not transparent")
        cut = im.crop(box); im = Image.new("RGBA", (cut.size[0] + 2 * EDGE, cut.size[1] + 2 * EDGE), (0, 0, 0, 0)); im.paste(cut, (EDGE, EDGE))
    out = io.BytesIO(); im.save(out, "PNG", optimize=True); return out.getvalue(), im.size


def gen_image(a, D):
    """One picture through the model chain -> (png bytes, fields for library.json). Fail when no model delivers (a dud when a delivered picture
    was not usable or the prompt is refused), Stop when the key is no use."""
    transparent = a.get("transparent", True); prompt = a["prompt"].strip(); suffix = str(D.get("style_suffix") or "").strip(); why = "no answer yet"; paid = 0
    if suffix: prompt = (prompt if prompt[-1:] in ".!?" else prompt + ".") + " " + suffix
    for model in D["model_chain"]:
        body = {"model": model, "prompt": prompt, "size": a.get("size") or D["size"], "quality": a.get("quality") or D["quality"], "n": 1, "output_format": "png"}
        if transparent: body["background"] = "transparent"
        for wait in WAITS + (None,):
            if late(): raise Fail("out of time in this run (%s)" % why, paid > 0)
            st, j = call("https://api.openai.com/v1/images/generations", body, {"Authorization": "Bearer " + OK, "Content-Type": "application/json"}, 240); v = verdict(st, j)
            if v != "retry" or wait is None: break
            say("    %s: HTTP %s, next try in %d s" % (model, st, wait)); time.sleep(wait)
        if v == "refused": raise Fail("refused by the content policy: " + errtext(j), True)
        if v == "stop": raise Stop("OpenAI does not accept the key or the account is out of credit (HTTP %s%s)" % (st, "" if st == 401 else ": " + errtext(j)), paid > 0)      # a 401 text quotes part of the key
        if v == "ok":
            d = j.get("data"); b64 = d[0].get("b64_json") if isinstance(d, list) and d and isinstance(d[0], dict) else None
            try:
                png, size = check_png(base64.b64decode(b64 if isinstance(b64, str) else ""), transparent)
                return png, {"model": model, "prompt": prompt, "size": list(size)}
            except ValueError as e: why = "%s: %s" % (model, e); paid += 1      # delivered and billed, and thrown away
        else: why = "%s: HTTP %s %s" % (model, st, errtext(j))
        say("    " + why)                                 # ... and on to the next model
    raise Fail(why, paid > 0)


def sig(a, D):                                            # changes when anything that is asked of the Images API for this picture changes
    ask = [a["prompt"].strip(), str(D.get("style_suffix") or "").strip(), a.get("size") or D["size"], a.get("quality") or D["quality"], a.get("transparent", True), D["model_chain"]]
    return hashlib.sha256(json.dumps(ask).encode("utf-8")).hexdigest()[:16]


def pixabay_url(u):                                       # a clip is only ever downloaded from Pixabay's own hosts, over https
    try: p = urllib.parse.urlsplit(str(u or "")); h = (p.hostname or "").lower()
    except ValueError: return False
    return p.scheme == "https" and (h == "pixabay.com" or h.endswith(".pixabay.com"))


def pick(hits, minsec, pinned=False):
    """The Pixabay hit to take and which of its files: the first portrait clip that is long and sharp enough, otherwise the first landscape one."""
    best = None
    for h in hits:
        if not isinstance(h, dict) or not (pinned or float(h.get("duration") or 0) >= minsec): continue
        for name in ("medium", "large", "small"):
            r = (h.get("videos") or {}).get(name) or {}; w, ht = int(r.get("width") or 0), int(r.get("height") or 0)
            if pixabay_url(r.get("url")) and (pinned or min(w, ht) >= 720) and int(r.get("size") or 0) <= MAX_MP4:
                if ht > w or pinned: return h, r
                best = best or (h, r); break
    return best


def gen_stock(a):
    """One stock clip -> (mp4 bytes, fields for library.json)."""
    pid = a.get("pixabay_id"); q = {"key": PK, "per_page": 50, "safesearch": "true"}; q.update({"id": str(pid)} if pid is not None else {"q": a["query"].strip()})
    for wait in WAITS + (None,):
        if late(): raise Fail("out of time in this run")
        st, j = call("https://pixabay.com/api/videos/?" + urllib.parse.urlencode(q), None, {"User-Agent": UA, "Accept": "application/json"}, 60)   # the key is in this url: it is never printed
        if not (st in (0, 429) or st >= 500) or wait is None: break
        say("    Pixabay: HTTP %s, next try in %d s" % (st, wait)); time.sleep(wait)
    if st != 200:
        if "api key" in errtext(j).lower(): raise Stop("Pixabay does not accept the key (HTTP %s)" % st)
        raise Fail("Pixabay search: HTTP %s %s" % (st, errtext(j)))
    hits = j.get("hits") if isinstance(j.get("hits"), list) else []; minsec = a.get("min_seconds", 3); got = pick(hits, minsec, pid is not None)
    if not got: raise Fail("no clip of %s s or more and 720 px or more, with a file on pixabay.com, among %d Pixabay hits" % (minsec, len(hits)))
    h, r = got
    for wait in (5, None):
        try: b = grab(r["url"]); break
        except Exception as e:
            if wait is None or isinstance(e, ValueError): raise Fail("the download failed (%s)" % ("HTTP %s" % e.code if isinstance(e, urllib.error.HTTPError) else e if isinstance(e, ValueError) else type(e).__name__))
            time.sleep(wait)
    if len(b) < 20000 or b[4:8] != b"ftyp": raise Fail("the download is not an mp4 file")
    return b, {"source": "pixabay:%s" % h.get("id"), "query": str(a.get("query") or ""), "credit": str(h.get("user") or ""), "page": str(h.get("pageURL") or ""),
               "seconds": h.get("duration"), "size": [int(r.get("width") or 0), int(r.get("height") or 0)]}


def faults(v):                                            # what is wrong with one entry of assets.json ([] = nothing)
    if not isinstance(v, dict) or v.get("kind") not in FILES: return ['"kind" must be "image" or "stock"']
    out = []
    if v["kind"] == "image":
        if not (isinstance(v.get("prompt"), str) and v["prompt"].strip()): out.append('"prompt" is missing')
        if "size" in v and not (isinstance(v["size"], str) and SIZE.fullmatch(v["size"])): out.append('"size" must look like 1024x1024')
        if "quality" in v and v["quality"] not in QUAL: out.append('"quality" must be low, medium or high')
        if not isinstance(v.get("transparent", True), bool): out.append('"transparent" must be true or false')
    else:
        pid = v.get("pixabay_id"); q = v.get("query"); ms = v.get("min_seconds", 3)
        if pid is not None and (isinstance(pid, bool) or not re.fullmatch(r"\d{1,12}", str(pid))): out.append('"pixabay_id" must be a number')
        if not (isinstance(q, str) and 0 < len(q.strip()) <= 100) and not (pid is not None and q is None): out.append('"query" is missing or longer than 100 characters')
        if isinstance(ms, bool) or not isinstance(ms, (int, float)) or ms < 0: out.append('"min_seconds" must be a number')
    return out


def load_spec():
    """scripts/assets.json -> (defaults, {slug: asset}). Exits when the file is not valid."""
    try:
        with open(SPEC, encoding="utf-8") as f: spec = json.load(f)
    except Exception as e: die("assets.json cannot be read (%s)" % e)
    if not isinstance(spec, dict): die("assets.json must be one object: slug -> asset")
    D = dict(DEFAULTS); d = spec.get("_defaults", {}); bad = []
    if isinstance(d, dict): D.update(d)
    else: bad.append("_defaults: must be an object")
    if not (isinstance(D["model_chain"], list) and D["model_chain"] and all(isinstance(m, str) and m.strip() for m in D["model_chain"])): bad.append("_defaults: \"model_chain\" must be a list of model names")
    if not isinstance(D["style_suffix"], str): bad.append("_defaults: \"style_suffix\" must be text")
    bad += ["_defaults: " + w for w in faults(dict(D, kind="image", prompt="x", transparent=True))]
    for slug, v in spec.items():
        if slug == "_defaults": continue
        if not SLUG.fullmatch(slug): bad.append("%r: not a valid slug (lower-case letters, digits and hyphens, 2 to 49 characters)" % slug[:60])
        else: bad += ["%s: %s" % (slug, w) for w in faults(v)]
    if bad: die("assets.json is not valid:\n  " + "\n  ".join(bad))
    return D, {k: v for k, v in spec.items() if k != "_defaults"}


def style_slugs(want):
    """The asset slugs the lines of one video use ("insert" and "stock"), in order of first use. No id, "auto" or an id that is not there: those of
    all videos, starting with the one the renderer picks by itself (make_short.py fmt_style: the "style" counter in shorts_posted.json), so that
    the assets of the video that is rendered next are made before --max or the time limit cut in."""
    try:
        with open(STYLES, encoding="utf-8") as f: vids = json.load(f)
        if not isinstance(vids, list): vids = None
    except Exception as e: die("styles.json cannot be read (%s)" % e)
    if vids is None: die("styles.json must be a list of videos")
    mine = [v for v in vids if isinstance(v, dict) and v.get("id") == want] if want and want != "auto" else []
    if mine: say('style "%s"' % want)
    else:
        try:
            with open(STATE, encoding="utf-8") as f: st = json.load(f)
            n = int(st.get("style", 0)) % len(vids)
        except Exception: n = 0                           # no state yet (or not readable): the renderer starts at the first video too
        vids = [v for v in vids[n:] + vids[:n] if isinstance(v, dict)]
        say(("no style with the id %r: " % want[:60] if want and want != "auto" else "") + "checking the assets of all %d styles" % len(vids) + (', "%s" first (the next one in the rotation)' % str(vids[0].get("id"))[:60] if vids else ""))
    out = []
    for v in mine or vids:
        for ln in v.get("lines") or []:
            if not isinstance(ln, dict): continue
            ins = ln.get("insert") or []; st = ln.get("stock") or []      # read the way make_short.py reads them: one entry or a list of entries
            for s in [(i.get("slug") if isinstance(i, dict) else i) for i in (ins if isinstance(ins, list) else [ins])] + [(d[0] if isinstance(d, list) and d else d) for d in (st if isinstance(st, list) else [st])]:
                if s is not None and s != "" and s not in out: out.append(s)
    return out


def load_lib(lib, dry=False):
    """library.json -> {slug: row}. A file that cannot be read is never written over: it is moved aside (library.broken-<UTC time>.json, which the
    save step puts on the branch next to the new one), so the rows of the other slugs (credits, prompts) are not lost."""
    p = os.path.join(lib, "library.json")
    if not os.path.exists(p): return {}
    try:
        with open(p, encoding="utf-8-sig") as f: L = json.load(f)      # utf-8-sig: an edit by hand may have left a byte order mark
        return {k: v for k, v in L.items() if isinstance(v, dict)}
    except Exception: pass
    keep = "library.broken-%s.json" % now("%Y%m%dT%H%M%SZ"); how = "a real run keeps it as library.broken-<time>.json and starts a new one"
    if not dry:
        try: os.replace(p, os.path.join(lib, keep)); save_lib(lib, {}); how = "it is kept as %s and a new one is started" % keep
        except Exception as e: how = "it could not be moved aside (%s) and is replaced by a new one" % type(e).__name__
    NOTES.append("library.json cannot be read: %s (the files on disk are kept and listed again when they are asked for)" % how); say("warning: " + NOTES[-1]); return {}


def load_bad(lib):                                        # failed.json: slug -> {"tries", "request", "why", "last"}, the pictures that were paid for and not usable
    try:
        with open(os.path.join(lib, "failed.json"), encoding="utf-8-sig") as f: B = json.load(f)
        return {k: v for k, v in B.items() if isinstance(v, dict)}
    except Exception: return {}


def put(path, data):                                      # written next to the target, then moved over it: never a half-written file
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".tmp", "wb") as f: f.write(data)
    os.replace(path + ".tmp", path)


def save_json(lib, name, J): put(os.path.join(lib, name), (scrub(json.dumps(J, indent=1, sort_keys=True, ensure_ascii=False)) + "\n").encode("utf-8"))
def save_lib(lib, L): save_json(lib, "library.json", L)


def have(lib, slug, kind):                                # is the file of a slug on disk and whole?
    p = os.path.join(lib, FILES[kind] % slug)
    try:
        if kind == "image":
            with Image.open(p) as im: im.verify()
            return True
        with open(p, "rb") as f: return f.read(12)[4:8] == b"ftyp" and os.path.getsize(p) >= 20000
    except Exception: return False


def entry(lib, f, kind, **more):                          # one row of library.json
    with open(os.path.join(lib, f), "rb") as fh: b = fh.read()
    e = {"file": f, "kind": kind, "created": now(), "bytes": len(b), "sha256": hashlib.sha256(b).hexdigest(), "credit": "", "page": ""}
    e.update(more); return e


def main():
    ap = argparse.ArgumentParser(description="Fill the asset library (generated pictures, stock clips) from scripts/assets.json.")
    ap.add_argument("--lib", required=True, help="the library folder (a checkout of the assets branch)")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--style", help='id of a video in styles.json: the assets its lines use ("" or auto: those of all videos)')
    g.add_argument("--slugs", help="asset slugs, comma separated")
    g.add_argument("--all", action="store_true", help="every asset in assets.json")
    ap.add_argument("--force", action="store_true", help="make the chosen assets again even when they exist, or after they were given up on (failed.json)")
    ap.add_argument("--dry-run", action="store_true", help="no keys, no network: only say what would be made or reused")
    ap.add_argument("--max", type=int, default=12, help="the most new assets made in one run (cost guard, default 12)")
    a = ap.parse_args()
    try: sys.stdout.reconfigure(errors="backslashreplace")      # an odd character in an error text must never stop the run
    except Exception: pass
    if a.max < 0: die("--max must be 0 or more")
    if os.path.exists(a.lib) and not os.path.isdir(a.lib): die("--lib is not a folder")
    del NOTES[:]; D, spec = load_spec()
    if a.all: slugs = list(spec)
    elif a.slugs is not None:
        slugs = [s.strip() for s in a.slugs.split(",") if s.strip()]; bad = [s for s in slugs if not SLUG.fullmatch(s)]      # checked before any path is built from them
        if bad or not slugs: die("--slugs: not valid: " + ", ".join(repr(s[:40]) for s in bad) if bad else "--slugs is empty")
    else: slugs = style_slugs("".join(a.style.split()))      # an id never has white space in it (the Shorts workflow strips it the same way)
    slugs = [s for k, s in enumerate(slugs) if s not in slugs[:k]]
    L, B = ({}, {}) if not os.path.isdir(a.lib) else (load_lib(a.lib, a.dry_run), load_bad(a.lib)); res = []; made = 0
    off = {} if a.dry_run else {k: "%s is not set: no %s can be made in this run" % (name, what) for k, name, what, key in (("image", "OPENAI_API_KEY", "pictures", OK), ("stock", "PIXABAY_API_KEY", "stock clips", PK)) if not key}
    def row(state, slug, note=""): res.append((state, slug, note)); say("%-10s %-26s %s" % (state, slug, note))
    def tries(slug, req): b = B.get(slug) or {}; return b["tries"] if b.get("request") == req and isinstance(b.get("tries"), int) else 0
    def dud(slug, req, e):                                # money went on a picture that was thrown away, or the prompt is refused: counted, so that it is not paid for run after run
        if not e.dud: return
        B[slug] = {"tries": tries(slug, req) + 1, "request": req, "why": str(e)[:200], "last": now()}
        try: save_json(a.lib, "failed.json", B)
        except Exception as x: say("warning: failed.json could not be written (%s)" % type(x).__name__)
    say("asset library: %s, %d asset%s to look at%s" % (a.lib, len(slugs), "" if len(slugs) == 1 else "s", " (dry run: nothing is made)" if a.dry_run else ""))
    for slug in slugs:
        if not isinstance(slug, str) or not SLUG.fullmatch(slug): row("skipped", repr(slug)[:26], "not a valid slug"); continue
        s = spec.get(slug)
        if s is None: row("skipped", slug, "not in assets.json" + (" (its file is in the library)" if any(have(a.lib, slug, k) for k in FILES) else "")); continue
        kind = s["kind"]; f = FILES[kind] % slug; what = "%s %s" % (s.get("size") or D["size"], s.get("quality") or D["quality"]) if kind == "image" else "Pixabay"
        req = sig(s, D) if kind == "image" else ""
        if have(a.lib, slug, kind) and not a.force:
            if not a.dry_run and (L.get(slug) or {}).get("file") != f:      # a file somebody put there by hand: list it, never pay for it again
                L[slug] = entry(a.lib, f, kind, source="added by hand", **{"prompt" if kind == "image" else "query": ""}); save_lib(a.lib, L)
            if not a.dry_run and B.pop(slug, None) is not None: save_json(a.lib, "failed.json", B)
            row("reused", slug, f); continue
        if tries(slug, req) >= TRIES and not a.force:
            row("skipped", slug, "not usable in %d runs (%s): left alone until its prompt changes, or run Assets with this slug and force" % (tries(slug, req), str(B[slug].get("why") or "no details")[:120])); continue
        if made >= a.max: row("deferred", slug, "over the limit of %d new assets in one run (--max)" % a.max); continue
        if a.dry_run: made += 1; row("would make", slug, "%s (%s, %s)" % (f, kind, what)); continue
        if kind in off: row("failed", slug, off[kind]); continue
        if late(): row("deferred", slug, "out of time in this run"); continue
        made += 1
        try:
            b, more = gen_image(s, D) if kind == "image" else gen_stock(s)
            put(os.path.join(a.lib, f), b); L[slug] = entry(a.lib, f, kind, **more); save_lib(a.lib, L)
            if B.pop(slug, None) is not None: save_json(a.lib, "failed.json", B)
            row("made", slug, "%s  %s  %sx%s  %d kB" % (f, more.get("model") or more.get("source"), more["size"][0], more["size"][1], len(b) // 1000))
        except Stop as e: off[kind] = str(e); row("failed", slug, str(e)); dud(slug, req, e)
        except Fail as e: row("failed", slug, str(e)); dud(slug, req, e)
        except Exception as e: row("failed", slug, "unexpected error (%s)" % type(e).__name__)
    n = {}
    for r in res: n[r[0]] = n.get(r[0], 0) + 1
    line = ", ".join("%d %s" % (n.get(k, 0), k) for k in ("would make", "made", "reused", "failed", "skipped", "deferred") if n.get(k) or k in (("would make", "reused") if a.dry_run else ("made", "reused", "failed")))
    say("assets: " + line)
    out = os.environ.get("GITHUB_STEP_SUMMARY")
    if out:
        md = "### Asset library%s\n\n%s\n\n" % (" (dry run)" if a.dry_run else "", line) + "".join("**Warning:** %s\n\n" % w for w in NOTES)
        if res: md += "| | asset | |\n|---|---|---|\n" + "".join("| %s | `%s` | %s |\n" % (st, sl.replace("`", "'").replace("|", "/"), re.sub(r"\s+", " ", note).replace("|", "/")) for st, sl, note in res) + "\n"
        try:
            with open(out, "a", encoding="utf-8") as f: f.write(scrub(md))
        except Exception: pass


if __name__ == "__main__":
    main()
