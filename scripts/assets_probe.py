# -*- coding: utf-8 -*-
"""Check which image models the OpenAI key can use (and whether transparent output works) and that the Pixabay key answers.
Writes out/probe/report.json and any test images. Run by the Assets workflow; prints no secrets."""
import base64, json, os, urllib.error, urllib.parse, urllib.request

OUT = "out/probe"; os.makedirs(OUT, exist_ok=True)
OK = os.environ.get("OPENAI_API_KEY", "").strip(); PK = os.environ.get("PIXABAY_API_KEY", "").strip()


def call(url, body=None, headers=None, timeout=240):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None, headers=headers or {}, method="POST" if body is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r: return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        t = e.read().decode("utf-8", "replace")
        try: return e.code, json.loads(t)
        except Exception: return e.code, {"raw": t[:300]}
    except Exception as e: return 0, {"raw": type(e).__name__}


rep = {"openai_key_present": bool(OK), "pixabay_key_present": bool(PK)}
H = {"Authorization": "Bearer " + OK, "Content-Type": "application/json"}
st, j = call("https://api.openai.com/v1/models", headers=H)
ids = sorted(m.get("id", "") for m in j.get("data", [])) if st == 200 else []
rep["models_status"] = st; rep["models_error"] = None if st == 200 else str((j.get("error") or {}).get("message") or j)[:300]
rep["n_models"] = len(ids)
rep["image_models"] = [i for i in ids if "image" in i or "dall" in i]
rep["audio_models"] = [i for i in ids if "transcribe" in i or "whisper" in i or "tts" in i]
rep["video_models"] = [i for i in ids if "sora" in i or "video" in i]
PROMPT = "A cartoon sticker of a shocked paper price tag character with big round eyes and a tiny open mouth, bold clean black outlines, flat colours, centred, no text, no logos"
gen = {}
for model in ["gpt-image-2", "gpt-image-1.5", "gpt-image-1", "gpt-image-1-mini"]:
    done = False
    for bg in ("transparent", None):
        body = {"model": model, "prompt": PROMPT, "size": "1024x1024", "quality": "low", "n": 1}
        if bg: body.update(background=bg, output_format="png")
        st, j = call("https://api.openai.com/v1/images/generations", body, H)
        key = "%s|%s" % (model, bg or "default")
        if st == 200 and j.get("data"):
            b = j["data"][0].get("b64_json"); fn = "%s_%s.png" % (model.replace(".", "_"), bg or "default")
            if b: open(os.path.join(OUT, fn), "wb").write(base64.b64decode(b))
            gen[key] = {"ok": True, "file": fn if b else None, "usage": j.get("usage")}; done = True; break
        gen[key] = {"ok": False, "status": st, "error": str((j.get("error") or {}).get("message") or j)[:300]}
    if done: break                                             # the first model that works is enough
rep["generation"] = gen
if PK:
    st, j = call("https://pixabay.com/api/videos/?" + urllib.parse.urlencode({"key": PK, "q": "counting money cash hands", "per_page": 5, "safesearch": "true"}))
    rep["pixabay_videos"] = {"status": st, "total": j.get("totalHits"), "sample": [{"id": h.get("id"), "duration": h.get("duration"), "tags": h.get("tags"), "user": h.get("user"),
        "sizes": {k: [v.get("width"), v.get("height")] for k, v in (h.get("videos") or {}).items()}} for h in (j.get("hits") or [])[:5]]} if st == 200 else {"status": st, "error": str(j.get("raw") or j)[:200]}
text = json.dumps(rep, indent=1)
for secret in (OK, PK):
    if secret: text = text.replace(secret, "***")
open(os.path.join(OUT, "report.json"), "w").write(text); print(text)
