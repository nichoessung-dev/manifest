# -*- coding: utf-8 -*-
"""Merge this run's copy of a JSON state file into the newest one on main, so two jobs that save at once both keep their records.

  python scripts/merge_state.py <this run's copy> <file in the checkout of the newest main>

Dicts merge key by key (numbers keep the larger value, nested dicts merge), lists keep every item of both (newest main first),
anything else takes this run's value. Writes the result over the second file.
"""
import json, sys


def merge(mine, theirs):
    if isinstance(mine, dict) and isinstance(theirs, dict):
        out = dict(theirs)
        for k, v in mine.items(): out[k] = merge(v, theirs[k]) if k in theirs else v
        return out
    if isinstance(mine, list) and isinstance(theirs, list):
        seen = {json.dumps(x, sort_keys=True) for x in theirs}
        return theirs + [x for x in mine if json.dumps(x, sort_keys=True) not in seen]
    if isinstance(mine, (int, float)) and isinstance(theirs, (int, float)) and not isinstance(mine, bool): return max(mine, theirs)
    return mine


if __name__ == "__main__":
    mine = json.load(open(sys.argv[1], encoding="utf-8"))
    try: theirs = json.load(open(sys.argv[2], encoding="utf-8"))
    except Exception: theirs = None
    json.dump(merge(mine, theirs) if theirs is not None else mine, open(sys.argv[2], "w", encoding="utf-8"), indent=0, ensure_ascii=False)
