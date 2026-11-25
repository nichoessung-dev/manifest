"""Test the ElevenLabs key and make short voice samples to pick a narrator from.

Prints the plan's credit allowance and the available models, then reads the same line with
several stock voices on the newest turbo model. The mp3s go to the release "voice-samples".
Env: ELEVENLABS_API_KEY, GH_TOKEN, VOICES (optional comma list of voice names or ids),
MODEL (optional model id), TEXT (optional).
"""
import json, os, re, subprocess, sys, urllib.request, urllib.error

KEY = os.environ["ELEVENLABS_API_KEY"].strip()
API = "https://api.elevenlabs.io/v1"
TEXT = os.environ.get("TEXT") or ("Here is what I bought from China. These sneakers, only twenty-five dollars, "
                                  "and the quality is crazy. Check out puro classico dot com, for finds like this.")
PREFER = ["Brian", "Liam", "Chris", "Will", "Adam", "Eric", "Jessica", "Sarah", "Laura", "Charlie"]


def call(path, body=None, raw=False):
    req = urllib.request.Request(API + path, data=json.dumps(body).encode() if body else None,
                                 headers={"xi-api-key": KEY, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            data = r.read()
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code} on {path}: {e.read()[:400].decode(errors='replace')}")
    return data if raw else json.loads(data)


sub = call("/user/subscription")
print(f"plan: {sub.get('tier')} | credits used {sub.get('character_count')} of {sub.get('character_limit')} "
      f"| resets {sub.get('next_character_count_reset_unix')}")

models = call("/models")
ids = [m["model_id"] for m in models if m.get("can_do_text_to_speech")]
print("tts models:", ", ".join(ids))
model = os.environ.get("MODEL") or next((i for i in ids if re.search(r"v4.*turbo|turbo.*v4", i)), None) \
    or next((i for i in ids if "v4" in i), None) or "eleven_multilingual_v2"
for m in models:
    if m["model_id"] == model:
        print("using", model, "| cost factor", m.get("model_rates", {}).get("character_cost_multiplier"))

voices = call("/voices")["voices"]
want = [v.strip() for v in os.environ.get("VOICES", "").split(",") if v.strip()]
pick = []
for w in want or PREFER:
    v = next((v for v in voices if v["voice_id"] == w or v["name"].split(" ")[0].lower() == w.lower()), None)
    if v and v not in pick: pick.append(v)
pick = pick[:6]
os.makedirs("samples", exist_ok=True)
for v in pick:
    audio = call(f"/text-to-speech/{v['voice_id']}?output_format=mp3_44100_128",
                 {"text": TEXT, "model_id": model}, raw=True)
    name = re.sub(r"[^a-z0-9]+", "-", v["name"].lower()).strip("-")
    path = f"samples/{name}.mp3"
    open(path, "wb").write(audio)
    labels = v.get("labels") or {}
    print(f"sample {path}: {v['name']} ({labels.get('gender','')}, {labels.get('accent','')}, {labels.get('age','')}) id {v['voice_id']}")

sub = call("/user/subscription")
print(f"credits now used: {sub.get('character_count')} of {sub.get('character_limit')}")
if os.environ.get("GH_TOKEN"):
    subprocess.run(["gh", "release", "create", "voice-samples", "--title", "voice-samples", "--notes", "ElevenLabs voice samples"],
                   capture_output=True)
    subprocess.run(["gh", "release", "upload", "voice-samples", "--clobber", *[f"samples/{f}" for f in os.listdir("samples")]], check=True)
