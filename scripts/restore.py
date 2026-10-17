# -*- coding: utf-8 -*-
"""Cleans up soft, re-compressed QC photos before they go on a slide.

Uses Real-ESRGAN's small general model (realesr-general-x4v3 and its denoise twin realesr-general-wdn-x4v3, mixed half and
half, from xinntao/Real-ESRGAN, BSD-3): it removes JPEG blocks and blur and redraws the edges that are there; it does not
add things that are not in the photo. The photo is shrunk to three quarters of its size on the slide, enlarged 4x by the
model, then scaled down to fit. A stronger shrink or the plain model draws fake stripes into knits (tested 17 Oct 2026).

Needs torch and the two model files in scripts/models/ (the workflow downloads them). Without them, restore() returns the
photo unchanged, so the posts still go out.
"""
import os
from PIL import Image

MODELS = os.environ.get("RESTORE_MODELS", os.path.join(os.path.dirname(os.path.abspath(__file__)), "models"))
DENOISE = 0.5                                                  # share of the plain model; the rest is the denoise model
_net = None


def _load():
    global _net
    if _net is not None: return _net or None
    try:
        import torch, torch.nn as nn, torch.nn.functional as F

        class SRVGGNetCompact(nn.Module):
            def __init__(self, feat=64, convs=32, scale=4):
                super().__init__(); self.scale = scale
                body = [nn.Conv2d(3, feat, 3, 1, 1), nn.PReLU(num_parameters=feat)]
                for _ in range(convs): body += [nn.Conv2d(feat, feat, 3, 1, 1), nn.PReLU(num_parameters=feat)]
                body += [nn.Conv2d(feat, 3 * scale * scale, 3, 1, 1)]
                self.body = nn.ModuleList(body); self.upsampler = nn.PixelShuffle(scale)

            def forward(self, x):
                out = x
                for m in self.body: out = m(out)
                return self.upsampler(out) + F.interpolate(x, scale_factor=self.scale, mode="nearest")

        ld = lambda f: torch.load(os.path.join(MODELS, f), map_location="cpu", weights_only=True)["params"]
        a, b = ld("realesr-general-x4v3.pth"), ld("realesr-general-wdn-x4v3.pth")
        net = SRVGGNetCompact(); net.load_state_dict({k: DENOISE * a[k] + (1 - DENOISE) * b[k] for k in a}); net.eval()
        torch.set_num_threads(max(1, os.cpu_count() or 1)); _net = net
    except Exception as e:
        print("  photo clean-up is off:", str(e)[:100]); _net = False
    return _net or None


def restore(im, w, h):
    """The photo cleaned up, at least w x h in size (the caller crops it to fit)."""
    net = _load()
    if net is None: return im
    import numpy as np, torch
    r = max(w / im.width, h / im.height) * 0.75                # the model enlarges 4x: three times the slide size
    small = im.convert("RGB").resize((max(8, round(im.width * r)), max(8, round(im.height * r))), Image.LANCZOS)
    x = torch.from_numpy(np.asarray(small, dtype=np.float32) / 255.0).permute(2, 0, 1).unsqueeze(0)
    with torch.no_grad(): y = net(x).clamp_(0, 1)
    return Image.fromarray((y[0].permute(1, 2, 0).numpy() * 255.0).round().astype("uint8"))
