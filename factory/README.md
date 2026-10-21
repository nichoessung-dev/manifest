# Video factory

Scripts, clip map, sources and tools for mass-producing vertical "style" videos (voice + footage + captions) and short news
"story" videos for puroclassico.com. Everything here lives on the `video-factory` branch. Nothing is posted from here:
finished videos go to orphan branches `videos-batch-NN` (same layout as `previews-batch`), and the owner posts them with
the Post videos workflow (ref = that branch).

## Files

| File | What it is |
|---|---|
| `styles_new.json` | New style scripts (ids `vf-...`), same schema as `scripts/styles.json`, plus `sources` (shop prices) and `totals` / `thresholds` (sums and game lines the voice says) that the renderer ignores |
| `stories_new.json` | New and updated news stories, same schema as `scripts/stories.json` (4 beats are spoken), plus `source_notes` (publisher, date, checked). Always `"approved": false` |
| `clips.json` | The 55 Drive clips the owner's videos already use (what each shows, length, good start times, creator credit) and the Pexels clips the existing stories use |
| `sources.md` | Every shop price ("around $X in the shop") with the page it was read on and the date |
| `finds.py` | Eligible finds: in products.json, QC photos (qc >= 1), not DEAD or SOLD_OUT. USD = round(cny * 0.14) |
| `grid.py` | A contact grid of find photos, to pick finds by eye |
| `check.py` | The rule check (run it before every render) |
| `render.py` | Renders ids with the voice, QA's each, logs credits used, stops when the credits run out |
| `qa.py` | Contact sheet (8 frames), length, audio level, silence, black frames, still stretches |
| `publish_batch.py` | Builds and force-pushes `videos-batch-NN` with `<id>.mp4`, `<id>.json` and `INDEX.md` |
| `scores.json` | Score per finished video (hook, clarity, look, mean), filled in after looking at each sheet |

## Run (a session with the voice)

```bash
pip install pillow imageio-ffmpeg
export ELEVENLABS_API_KEY=...            # or "proxy" when the cloud environment adds the key (header xi-api-key) itself
python factory/check.py                  # must print OK for every id
python scripts/make_short.py --credits   # characters used / limit
python factory/render.py --all-new       # or a list of ids; stops when the credits run out
# look at every out/<id>/*.sheet.jpg, score it in factory/scores.json, fix and re-render anything under 7
python factory/publish_batch.py --nn 01 --ids id1,id2,...   # every 20 good videos
```

The renderer reads `STYLES_FILE` / `STORIES_FILE` (set by render.py), `SHORTS_STORY_MUSIC` (news videos reuse the owner's
Drive track instead of generating music) and `SHORTS_HASHTAGS` (the owner's fixed hashtag line). Without those variables it
behaves exactly as before.

## Rules (from the owner)

- No em dashes anywhere. Never say or show: fake, replica, counterfeit, 1:1, "same as real", "dupe". Use "the same look",
  "on the spreadsheet", "for $X".
- Every product is a real eligible find; the price on screen and in the voice is round(cny * 0.14).
- A shop price is said as "around $X", rounded down, only with a source in `sources.md`.
- Coupon wording, only if used: "up to $500 in MyCNBox new-user coupons".
- Hashtags: #grisch #oldmoney #taobao #mycnbox #cnfans, nothing else.
- Footage: only the 55 Drive clips (credits kept), music: only the track already used.
- News: primary sources, dated, re-checked on the day; "check your country's customs site" instead of advice; never advice to
  under-declare, split parcels, mislabel or hide anything from customs.
- Brand names are not said or printed on finds (`"brand": false` on every product shot).
