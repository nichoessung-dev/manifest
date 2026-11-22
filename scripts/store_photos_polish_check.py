# -*- coding: utf-8 -*-
"""Regression check of the polished store photos (22 Nov 2026), before the site uses them.

The polish step (scripts/store_photos_polish.py) makes a clean 1600 px white cut-out of every live store photo. On white
and very light items the new matte can lose parts that the old cut-out kept as a light grey ghost: a white football shirt's
body, a white sole. The item then looks cut in half on the white page (Portugal shirt 7737220505: only the teal top
was left). This script compares each polished copy with the live file and marks the ones the site must not use:

  ghost   share of semi-transparent pixels (alpha 10..200) per opaque pixel in the live cut-out: over 0.15 the old
          cut-out drew part of the item as a ghost, which the polish removes (pilot sheet: every such case lost parts)
  ar      log of the aspect-ratio change of the visible item (pixels darker than 250, specks ignored): over 0.08 a part
          was lost or added
  corr    grey correlation of the two visible items (each cropped to itself, 96 x 96): under 0.6 the photo changed

Writes data/store_photos_polish_check.json {name: {"ok": bool, "ghost", "ar", "corr"}}; scripts/apply_store_photos.py
keeps the live products/store/ file wherever "ok" is false. Model shots are not checked (never re-cut).

  python scripts/store_photos_polish_check.py [--redo]
"""
import argparse, io, json, os, re, sys, urllib.request
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from catalog_common import ROOT, load_json, save_json  # noqa: E402
import store_photos_polish as sp  # noqa: E402

OUT = os.path.join(ROOT, "data", "store_photos_polish_check.json")
GHOST_MAX, AR_MAX, CORR_MIN = 0.15, 0.08, 0.6


def load(u):
    for _ in range(3):
        try:
            im = Image.open(io.BytesIO(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": sp.UA}), timeout=60).read()))
            im.load(); return im
        except Exception:
            pass
    return None


def visible(im, thr=250):
    g = np.asarray(im.convert("L"), dtype=np.int16) < thr
    rows, cols = np.where(g.mean(1) > 0.003)[0], np.where(g.mean(0) > 0.003)[0]
    if not len(rows) or not len(cols): return None
    return int(cols[0]), int(rows[0]), int(cols[-1]) + 1, int(rows[-1]) + 1


def check(name):
    a, b = load(sp.STORE + name), load(sp.STORE2 + name)
    if a is None or b is None: return name, None
    rgba = np.asarray(a.convert("RGBA"))
    al = rgba[..., 3]
    ghost = float(((al > 10) & (al < 200)).sum() / max(1, (al >= 200).sum()))
    wa, wb = sp.on_white(a), sp.on_white(b)
    ea, eb = visible(wa), visible(wb)
    if not ea or not eb: return name, {"ok": False, "ghost": round(ghost, 3), "why": "no visible item"}
    ar = float(np.log(((eb[2] - eb[0]) / max(1, eb[3] - eb[1])) / ((ea[2] - ea[0]) / max(1, ea[3] - ea[1]))))
    x = np.asarray(wa.crop(ea).convert("L").resize((96, 96)), dtype=np.float32).ravel()
    y = np.asarray(wb.crop(eb).convert("L").resize((96, 96)), dtype=np.float32).ravel()
    x, y = x - x.mean(), y - y.mean()
    corr = float(np.dot(x, y) / (np.linalg.norm(x) * np.linalg.norm(y) + 1e-6))
    ok = ghost <= GHOST_MAX and abs(ar) <= AR_MAX and corr >= CORR_MIN
    return name, {"ok": ok, "ghost": round(ghost, 3), "ar": round(ar, 3), "corr": round(corr, 3)}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--redo", action="store_true")
    a = ap.parse_args(argv)
    out = {} if a.redo else load_json(OUT, {})
    names = [n for d in sp.load_done().values() for n, x in (d.get("photos") or {}).items()
             if x.get("url") and not re.search(r"-[a-z]?m\d+\.webp$", n) and n not in out]
    print(f"{len(names)} polished photos to check", flush=True)
    with ThreadPoolExecutor(16) as ex:
        for k, (n, r) in enumerate(ex.map(check, names), 1):
            if r is not None: out[n] = r
            if k % 250 == 0: print(k, flush=True)
    save_json(OUT, dict(sorted(out.items())))
    bad = [n for n, r in out.items() if not r.get("ok")]
    print(f"{len(out)} checked, {len(bad)} kept on the live file (ghost > {GHOST_MAX}, |ar| > {AR_MAX} or corr < {CORR_MIN})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
