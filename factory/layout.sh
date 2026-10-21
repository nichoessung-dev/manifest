#!/bin/bash
# Silent layout renders (no voice, no credits used): every line gets 2 s. Writes out-layout/<id>/ and a per-line sheet.
# usage: bash factory/layout.sh id1 id2 ...
cd "$(dirname "$0")/.."
for id in "$@"; do
  ( env -u ELEVENLABS_API_KEY STYLES_FILE=factory/styles_new.json STORIES_FILE=factory/stories_new.json SHORTS_STORY_MUSIC=1Jl7ptfgdvN4FlMiEW0Y3NZpzKhIGDlrx \
      python3 scripts/make_short.py --format "$( [[ $id == vf-* ]] && python3 -c "import json,sys; print('style' if any(s['id']=='$id' for s in json.load(open('factory/styles_new.json'))) else 'story')" || echo story )" --id "$id" --out "out-layout/$id" > "out-layout-$id.log" 2>&1 \
    && python3 factory/qa.py --lines "out-layout/$id" && mv "out-layout-$id.log" "out-layout/$id/render.log" ) &
  while [ "$(jobs -r | wc -l)" -ge 3 ]; do sleep 1; done
done
wait
