# -*- coding: utf-8 -*-
"""Shards for the store-photo pipeline (owner, 20 Nov 2026: all partner finds, fast). Several GitHub runs work in
parallel, each on its own share of the finds: a find belongs to shard k of n when int(sha1(id)) % n == k. Each shard
writes only its own files, so parallel runs never conflict when they push:
    data/store_photos/<k>-of-<n>/store_photo_names.json, store_photo_candidates.json, store_photos.json
Shard 0/1 (the default) is the whole set and writes the top-level files data/store_photo_*.json as before. Readers merge
the top-level files and every shard file (a find is done when it is done in any of them); scripts/store_photos_merge.py
writes the merged data/store_photos.json for the apply step and the review sheets.
"""
import glob, hashlib, json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOP = {"names": "store_photo_names.json", "cands": "store_photo_candidates.json", "log": "store_photos.json"}
SHARD_DIR = os.path.join(ROOT, "data", "store_photos")


def parse(s):
    """'k/n' -> (k, n)."""
    k, n = (s or "0/1").split("/")
    k, n = int(k), int(n)
    if not (n >= 1 and 0 <= k < n): raise SystemExit(f"bad shard {s!r}: use k/n with 0 <= k < n")
    return k, n


def of(pid, n):
    return int(hashlib.sha1(str(pid).encode()).hexdigest(), 16) % n


def mine(pid, shard):
    k, n = shard
    return n == 1 or of(pid, n) == k


def path(kind, shard):
    k, n = shard
    if n == 1: return os.path.join(ROOT, "data", TOP[kind])
    return os.path.join(SHARD_DIR, f"{k}-of-{n}", TOP[kind])


def _load(p):
    try:
        with open(p, encoding="utf-8") as f: return json.load(f)
    except Exception:
        return {}


def files(kind):
    """The top-level file first, then every shard's file (later ones win for a find present twice)."""
    return [os.path.join(ROOT, "data", TOP[kind])] + sorted(glob.glob(os.path.join(SHARD_DIR, "*", TOP[kind])))


def merged(kind):
    """{"items": {...all files...}, "spent_usd": sum of all files}."""
    items, spent = {}, 0.0
    for p in files(kind):
        d = _load(p)
        items.update(d.get("items") or {})
        spent += float(d.get("spent_usd") or 0)
    return {"items": items, "spent_usd": round(spent, 4)}


def spent_all():
    """AI spend of every run so far (naming + picking, all shards): the global budget."""
    return merged("names")["spent_usd"] + merged("log")["spent_usd"]


def spent_shard(shard):
    return float(_load(path("names", shard)).get("spent_usd") or 0) + float(_load(path("log", shard)).get("spent_usd") or 0)
