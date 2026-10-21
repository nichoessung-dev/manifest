# Video factory report (prep session, 21 October 2026)

## Outcome

- **Voiced videos made: 0. ElevenLabs characters used: 0.** The cloud environment of this session adds its own
  `Authorization` header to every request to api.elevenlabs.io, so ElevenLabs rejects every call ("only one of xi-api-key and
  authorization headers"), even with the key. The owner chose a prep-only session. To render: fix or remove the ElevenLabs network
  secret in the environment settings (header name `xi-api-key`), or set `ELEVENLABS_API_KEY` as a plain environment variable, then run
  `python factory/render.py --queue` in a new session.
- **Ready to render: 39 style scripts and 22 news stories (61 videos)**, all passing `factory/check.py`, every style script checked in a
  silent layout render (one frame per line) and fixed where a shot, price tag or hook did not work.
- About 32,000 characters of speech in total (style about 450 per video, news about 650), so a 100,000-character month covers all 61.

## What is in factory/

- `clips.json`: all 55 Drive clips described from 4 frames each (garments, colours, season, setting, shot type, good start times, issues,
  creator credit from the Drive file name) and the 107 Pexels clips the existing stories use.
- `styles_new.json` (39), `stories_new.json` (22, all `"approved": false`), `queue.json` (render order: 3 style, 1 news, best first).
- `sources.md`: 22 shop prices confirmed on 21 October 2026 on the brand's site or a big retailer, with the page and the exact price.
- Tools: `check.py`, `finds.py`, `grid.py`, `layout.sh`, `qa.py`, `render.py`, `publish_batch.py`, `build_stories.py`, `make_sources.py`.
- `scripts/make_short.py` (on this branch only): `STORIES_FILE`, `SHORTS_STORY_MUSIC`, `SHORTS_HASHTAGS`, `--credits`, and no em dash in
  the story caption. Without the new variables it renders exactly as before.

## Strongest scripts (predicted, before voice)

1. `vf-splatter-sneakers-980-or-31`: "$980 sneakers. Or $31?" Exact match (same paint-splatter design), Nordstrom price, the find has the most QC listings in the catalogue.
2. `vf-crewneck-1900-or-48`: "$1,900 sweater or $48?" Biggest price gap with a plain, logo-free photo.
3. `vf-padded-jacket-1000-or-73`: "$1,000 jacket or $73?" Matching footage of padded knit jackets from three creators.
4. `vf-under-over-50-knits`: $48 vs $51 vs $40 vs $62: close calls make people guess and comment.
5. `vf-old-money-4-under-100`: running total on screen, ends on the best old money clip (@floriansoutfits).
6. `vf-scuffed-sneakers-630-or-55`: curiosity hook ("why pay $630 for scuffed sneakers?").
7. `vf-knit-looks-cheap-fit`: a rule people can check on themselves right away.
8. `vf-grisch-starter-pack`: names the audience's own style.
9. `vf-copycat-perfume-methanol-lab-test` (news): Korea Consumer Agency test, 14 August 2026, methanol up to 484 times the limit.
10. `eu-three-euro-parcel-duty` (news, updated): the EU's own T-shirt and watch example, every date from the Council regulation.

## Families to make more of

- **Price contrast** with an exact-match find and a confirmed price: the strongest hooks. Limited by which brand pages can be read
  (Loro Piana and Brunello Cucinelli block every bot, so no suede-loafer, cap, trousers or scarf prices could be confirmed).
- **Games** (higher or lower, which one costs $X, pick the shoes): cheap to make, built for comments.
- **Outfit formulas with a running total**: clear payoff on screen.
- **News: safety and EU/Nordic customs**: the most useful to the audience and fully sourced.

## Ideas left out, and why

- $900 suede loafers, $250 cap, waxed jacket, wedding guest, ski trip, rank the winter boots, Stockholm winter, big logos (already made
  as `logo-vs-16`), 3 colour rule (already `three-colours-parrot`), cable knit or quarter zip (already `quarter-zip-bank`): no confirmed
  shop price, no matching finds or footage, or a repeat of an existing video.
- $1,500 bag: the closest confirmed bag (Jacquemus Le Cabas, $1,182 at FWRD) does not match the find's shape.
- QC photo count claims ("129 QC photos"): the catalogue's qc number may not be a photo count, so it is never said.
- News: Christmas cut-off dates (no agent had published 2026 dates on 21 October: retry around 10 and 24 November); the agent that shut
  down (no police, court or company statement on the parcels); "shipping got more expensive" (the only sourced answer is the EU charges,
  already covered). Details: `news_dropped.md`.

## Rules applied beyond the brief (owner, please confirm)

- No brand name is said or printed on a find (`"brand": false` everywhere); shop prices are said as "around $X in the shop" and the brand
  is only named in `sources.md`.
- `scripts/site.png` (the end screen with the phone) shows "The only replica spreadsheet" on the phone. No factory video uses it, because
  that word may never be shown. The owner's existing video `autumn-sneakers` does use it: worth a new screenshot.
- Creator footage where a brand name is clearly readable (a branded rug, a shoe tongue) is avoided next to our finds.
- The QC checklist story talks about print and stitching quality, not about matching a brand's logo.
