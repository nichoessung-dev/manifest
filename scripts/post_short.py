# -*- coding: utf-8 -*-
"""Publish a rendered short (from make_short.py) to the channels connected in Postiz, then collect the public links.

  python scripts/post_short.py out/short-top5-n0.json

Env: POSTIZ_API_KEY (required)
     SHORTS_CHANNELS   comma list of Postiz provider ids to post to (default: tiktok,youtube,instagram-standalone,threads)
     PINTEREST_BOARD   Pinterest board id; Pinterest is skipped unless this is set
     TIKTOK_BRANDED    "true" if the video is a paid partnership (turns on TikTok's branded-content label)
     MYCNBOX_WEBHOOK   Discord webhook that receives the TikTok link (optional)
Writes the links to <meta>.links.json and appends a line to shorts_log.json.
"""
import json, os, sys, time, uuid, urllib.request, urllib.error
from datetime import datetime, timedelta, timezone

API = "https://api.postiz.com/public/v1"
KEY = os.environ.get("POSTIZ_API_KEY", "").strip()
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WANT = [c.strip() for c in (os.environ.get("SHORTS_CHANNELS", "").strip() or "tiktok,youtube,instagram-standalone,threads").split(",") if c.strip()]
UA = "PuroClassicoShorts/1.0 (+https://www.puroclassico.com)"


def call(method, path, body=None, headers=None, timeout=120):
    h = {"Authorization": KEY, "User-Agent": UA, "Accept": "application/json"}; h.update(headers or {})
    data = body if isinstance(body, (bytes, type(None))) else json.dumps(body).encode()
    if body is not None and not isinstance(body, bytes): h["Content-Type"] = "application/json"
    req = urllib.request.Request(API + path, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        raise SystemExit("Postiz %s %s -> HTTP %s: %s" % (method, path, e.code, e.read().decode("utf-8", "replace")[:500]))
    return json.loads(raw) if raw.strip() else {}


def upload(path):
    boundary = "----pc" + uuid.uuid4().hex; ctype = "image/jpeg" if path.lower().endswith((".jpg", ".jpeg")) else "video/mp4"
    head = ("--%s\r\nContent-Disposition: form-data; name=\"file\"; filename=\"%s\"\r\nContent-Type: %s\r\n\r\n" % (boundary, os.path.basename(path), ctype)).encode()
    body = head + open(path, "rb").read() + ("\r\n--%s--\r\n" % boundary).encode()
    r = call("POST", "/upload", body, {"Content-Type": "multipart/form-data; boundary=" + boundary}, 600)
    if not r.get("path"): raise SystemExit("upload failed: %s" % r)
    return {"id": r["id"], "path": r["path"]}


def settings(provider, meta):
    title = meta["caption"].split("\n")[0]
    if provider.startswith("tiktok") and meta.get("images"):      # a photo carousel: TikTok adds a sound itself (our own audio cannot be attached)
        return {"__type": provider, "title": title[:90], "privacy_level": "PUBLIC_TO_EVERYONE", "comment": True, "duet": False, "stitch": False, "autoAddMusic": os.environ.get("TIKTOK_AUTO_MUSIC", "yes"),
                "brand_content_toggle": os.environ.get("TIKTOK_BRANDED", "").lower() == "true", "brand_organic_toggle": True, "content_posting_method": "DIRECT_POST"}
    if provider.startswith("tiktok"):
        return {"__type": provider, "title": title[:90], "privacy_level": "PUBLIC_TO_EVERYONE", "duet": True, "stitch": True, "comment": True,
                "autoAddMusic": "no", "brand_content_toggle": os.environ.get("TIKTOK_BRANDED", "").lower() == "true",
                "brand_organic_toggle": True,                      # "Your brand": the video promotes our own site
                "video_made_with_ai": bool(meta.get("voiceover")),  # the narration is an AI voice
                "content_posting_method": "DIRECT_POST"}
    if provider == "youtube":
        return {"__type": "youtube", "title": (title[:92] + " #shorts")[:100], "type": "public", "selfDeclaredMadeForKids": "no", "thumbnail": None, "tags": []}
    if provider in ("instagram", "instagram-standalone"):
        return {"__type": provider, "post_type": "post", "is_trial_reel": False, "collaborators": []}
    if provider == "pinterest":
        return {"__type": "pinterest", "board": os.environ["PINTEREST_BOARD"], "title": title[:100], "link": ref_link(meta.get("product_url") or "https://www.puroclassico.com/", "pinterest"), "dominant_color": ""}
    return {"__type": provider}


REFS = {"youtube": "yt", "threads": "threads", "pinterest": "pin", "instagram": "ig", "instagram-standalone": "ig"}


def ref_link(url, prov):
    """The site link tagged with the channel it is posted on (?ref=yt and so on); the site stores it on sign-up."""
    if not url: return url
    return url + ("&" if "?" in url else "?") + "ref=" + ("tt" if prov.startswith("tiktok") else REFS.get(prov, prov[:12]))


def list_channels():
    """Print what Postiz reports for each connected channel (no ids, nothing is posted)."""
    ints = call("GET", "/integrations"); ints = ints if isinstance(ints, list) else ints.get("integrations", [])
    rows = ["%s | name=%s | disabled=%s | keys=%s" % (i.get("identifier") or i.get("providerIdentifier"), i.get("name"), i.get("disabled"), sorted(k for k in i if k not in ("id", "picture", "token", "refreshToken"))) for i in ints]
    print("\n".join(rows)); summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary: open(summary, "a").write("### Postiz channels\n\n" + "".join("- CHANNEL %s\n" % r for r in rows))


def main():
    if not KEY: raise SystemExit("POSTIZ_API_KEY is not set")
    if len(sys.argv) > 1 and sys.argv[1] == "--list": return list_channels()
    meta_path = sys.argv[1]; meta = json.load(open(meta_path, encoding="utf-8"))
    video = meta["file"] if os.path.exists(meta["file"]) else meta_path[:-5] + ".mp4"
    ints = call("GET", "/integrations"); ints = ints if isinstance(ints, list) else ints.get("integrations", [])
    chans = []
    for it in ints:
        prov = it.get("identifier") or it.get("providerIdentifier") or ""
        if it.get("disabled"): continue
        if prov == "pinterest" and not os.environ.get("PINTEREST_BOARD"): continue
        if prov in WANT or (prov.startswith("tiktok") and "tiktok" in WANT) or (prov == "pinterest" and "pinterest" not in WANT and os.environ.get("PINTEREST_BOARD")): chans.append((prov, it["id"], it.get("name", "")))
    print("channels:", [(p, n) for p, _, n in chans])
    if not chans: raise SystemExit("no matching channels connected in Postiz (wanted %s; found %s)" % (WANT, [i.get("identifier") or i.get("providerIdentifier") for i in ints]))
    media = upload(video); print("uploaded:", media["path"])
    photos = [upload(os.path.join(os.path.dirname(meta_path), os.path.basename(i))) for i in meta.get("images") or []]   # carousel slides
    if photos: print("uploaded", len(photos), "slides")
    def files(prov): return photos if photos and prov != "youtube" else [media]                 # YouTube has no carousels: it gets the video
    # YouTube descriptions can carry a clickable link; other platforms only get the caption
    def content(prov):
        if photos and prov.startswith("tiktok"): return meta["caption"].split("\n", 1)[-1].strip()      # TikTok shows the title line itself: do not repeat it
        return meta["caption"] + ("\n\n" + ref_link(meta.get("product_url") or "", prov) if prov in ("youtube", "threads") else "")
    at = os.environ.get("SCHEDULE_AT", "").strip()               # hand the post to Postiz to publish at this time (UTC, ISO)
    if at:
        body = {"type": "schedule", "date": at, "shortLink": False, "tags": [],
                "posts": [{"integration": {"id": iid}, "value": [{"content": content(prov), "image": files(prov)}], "settings": settings(prov, meta)} for prov, iid, _ in chans]}
        res = call("POST", "/posts", body); print("scheduled for %s:" % at, json.dumps(res)[:300]); return
    first = start = datetime.now(timezone.utc); links, errors, todo = {}, {}, list(chans)
    for round_ in range(4):                                      # a channel that errors is tried again after five minutes (up to three retries)
        if round_:
            print("retrying %s in five minutes (attempt %d of 4)" % ([c[0] for c in todo], round_ + 1)); time.sleep(300)
        start = datetime.now(timezone.utc); errors = {}
        body = {"type": "now", "date": start.strftime("%Y-%m-%dT%H:%M:%S.000Z"), "shortLink": False, "tags": [],
                "posts": [{"integration": {"id": iid}, "value": [{"content": content(prov), "image": files(prov)}], "settings": settings(prov, meta)} for prov, iid, _ in todo]}
        res = call("POST", "/posts", body); print("created:", json.dumps(res)[:400])
        ids = {c[1]: c[0] for c in todo}
        q = "?startDate=%s&endDate=%s" % ((start - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%S.000Z"), (start + timedelta(hours=6)).strftime("%Y-%m-%dT%H:%M:%S.000Z"))
        for attempt in range(40):                               # TikTok only gives a public link after its own review
            time.sleep(45)
            posts = call("GET", "/posts" + q).get("posts", [])
            for p in posts:
                iid = (p.get("integration") or {}).get("id"); prov = ids.get(iid)
                pub = p.get("publishDate") or ""
                if not prov or pub[:16] < (start - timedelta(minutes=3)).strftime("%Y-%m-%dT%H:%M"): continue
                if p.get("state") == "PUBLISHED" and p.get("releaseURL"): links[prov] = p["releaseURL"]
                elif p.get("state") == "ERROR": errors[prov] = True
            print("  %2d: published %s%s" % (attempt + 1, sorted(links), (" errors " + str(sorted(errors))) if errors else ""))
            if all(c[0] in links or c[0] in errors for c in todo): break
        todo = [c for c in todo if c[0] in errors and c[0] not in links]
        if not todo: break
    start = first
    try: seen = {u for e in json.load(open(os.path.join(ROOT, "shorts_log.json"))) for u in (e.get("links") or {}).values()}
    except Exception: seen = set()
    for k, v in list(links.items()):                              # TikTok Business only reports the profile: look up the newest post there
        if k.startswith("tiktok") and "/video/" not in v and "/photo/" not in v:
            import subprocess
            for attempt in range(9):                              # the new post can take a few minutes to show on the profile
                try:
                    r = subprocess.run([sys.executable, "-m", "yt_dlp", "--flat-playlist", "--playlist-items", "1", "--print", "%(webpage_url)s", v.split("?")[0]], capture_output=True, text=True, timeout=120)
                    u = next((l.strip() for l in r.stdout.splitlines() if "/video/" in l or "/photo/" in l), None)
                except Exception as e: u = None; print("TikTok link lookup failed:", e)
                if u and u not in seen: links[k] = u; print("TikTok post link:", u); break
                print("  the new post is not on the profile yet, waiting"); time.sleep(30)
            else: print("could not find the new post's link; leaving the profile link")
    out = {"when": start.strftime("%Y-%m-%d %H:%M UTC"), "format": meta["format"], "ids": meta["ids"], "links": links, "failed": sorted(e for e in errors if e not in links),
           "pending": sorted(p for p, _, _ in chans if p not in links and p not in errors)}
    json.dump(out, open(meta_path[:-5] + ".links.json", "w"), indent=1)
    log_path = os.path.join(ROOT, "shorts_log.json")
    try: log = json.load(open(log_path))
    except Exception: log = []
    log.append(out); json.dump(log[-400:], open(log_path, "w"), indent=0)
    print(json.dumps(out, indent=1))
    hook = os.environ.get("MYCNBOX_WEBHOOK", "").strip()
    tk = next((v for k, v in links.items() if k.startswith("tiktok")), None)
    if tk: links["tiktok"] = tk
    if hook and links.get("tiktok"):
        msg = {"content": links["tiktok"], "username": "Puro Classico", "allowed_mentions": {"parse": []}}       # only the TikTok link
        req = urllib.request.Request(hook + "?wait=true", data=json.dumps(msg).encode(), headers={"Content-Type": "application/json", "User-Agent": UA}, method="POST")
        try: urllib.request.urlopen(req, timeout=30); print("sent TikTok link to the Discord webhook")
        except Exception as e: print("Discord webhook failed:", e)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as f:
            f.write("### Short posted (%s)\n\n" % meta["format"] + "".join("- **%s**: %s\n" % (k, v) for k, v in links.items()) +
                    ("".join("- %s: still processing\n" % p for p in out["pending"])) + ("".join("- %s: FAILED\n" % p for p in out["failed"])))
    if not links: raise SystemExit("nothing was published (see Postiz for the reason)")


if __name__ == "__main__":
    main()
