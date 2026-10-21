# -*- coding: utf-8 -*-
"""A contact grid of find photos, to pick finds by eye (clean photo, plain background, no loud logo).

  python factory/grid.py out.jpg 891428294916 7294857785 ...
  python factory/grid.py out.jpg --search cable knit       # the top 24 eligible matches
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image, ImageDraw
import finds as F

def main():
    out = sys.argv[1]; args = sys.argv[2:]; fl, _, _, products = F.load()
    if args and args[0] == "--search": ids = [f["id"] for f in F.search(args[1:], fl, 24)]
    else: ids = args
    import make_short as M
    T = 300; cols = 6; rows = (len(ids) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * T, rows * (T + 64)), (255, 255, 255)); d = ImageDraw.Draw(sheet)
    for k, pid in enumerate(ids):
        p = products.get(pid) or {}; f = fl.get(pid); x, y = (k % cols) * T, (k // cols) * (T + 64)
        im = M.load_img(M.img_url(p)) if p else None
        cut = "cut" if (im is not None and M.cutout(im) is not None) else "card"
        if im: im.thumbnail((T - 10, T - 10)); sheet.paste(im, (x + (T - im.width) // 2, y + (T - im.height) // 2))
        lab = "%s  $%s qc%s %s %s" % (pid, f["usd"] if f else "?", f["qc"] if f else "-", "" if f else "NOT ELIGIBLE", cut)
        d.text((x + 6, y + T + 4), lab, fill=(0, 0, 0)); d.text((x + 6, y + T + 22), (p.get("title") or "")[:46], fill=(80, 80, 80))
    sheet.save(out, quality=85); print("wrote", out, len(ids))

if __name__ == "__main__": main()
