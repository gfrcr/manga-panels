# src/manga_panels/ml.py
"""Panel detector via Magi v2. Every torch/transformers import is LAZY (inside
functions) so the base install stays light."""
from __future__ import annotations

import warnings

import numpy as np
from PIL import Image

from manga_panels.detect import Box
from manga_panels.errors import MissingDependency

_MODEL_NAME = "ragavsachdeva/magiv2"
_MODEL = None  # singleton loaded on demand


def _norm(b) -> list[float]:
    """xyxy with x1<=x2, y1<=y2."""
    x1, y1, x2, y2 = (float(v) for v in b[:4])
    if x2 < x1:
        x1, x2 = x2, x1
    if y2 < y1:
        y1, y2 = y2, y1
    return [x1, y1, x2, y2]


def _inter_area(a, b) -> float:
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
    return max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)


def _edge_gap(a, b) -> float:
    """Distance between two xyxy boxes (0 if they overlap/touch)."""
    gx = max(0.0, a[0] - b[2], b[0] - a[2])
    gy = max(0.0, a[1] - b[3], b[1] - a[3])
    return (gx * gx + gy * gy) ** 0.5


def _panels_to_boxes(panels, texts, page_w: int, page_h: int, *,
                     characters=None, essential=None) -> list[Box]:
    """Panels + Magi's text/character boxes ([x1,y1,x2,y2]) -> (x,y,w,h) crops.
    Each panel is grown to cover (a) the text boxes assigned to it — the one it
    overlaps most, or the nearest panel if it overlaps none (a *floating* text is
    absorbed only if it's essential dialogue, not stray SFX), and (b) characters
    that substantially overlap it — so speech balloons and people that bleed past
    the panel border aren't clipped. Distance-guarded so a stray text/character
    can't balloon a crop across the page. Panel order preserved."""
    pans = [_norm(p) for p in panels]
    if not pans:
        return []
    txts = [_norm(t) for t in texts]
    chars = [_norm(c) for c in (characters or [])]
    ess = list(essential) if essential is not None else [True] * len(txts)
    # ponytail: a floating box farther than this from any panel is ignored
    # (page numbers, margin captions) — else one crop balloons across the page.
    max_gap = 0.05 * max(page_w, page_h)
    grown = [list(p) for p in pans]                # accumulate; assign against pans (fixed)

    def _grow(j, b):
        g = grown[j]
        g[0], g[1] = min(g[0], b[0]), min(g[1], b[1])
        g[2], g[3] = max(g[2], b[2]), max(g[3], b[3])

    for i, t in enumerate(txts):
        overlaps = [_inter_area(t, p) for p in pans]
        j = max(range(len(pans)), key=lambda k: overlaps[k])
        if overlaps[j] <= 0.0:                      # floating text
            if i < len(ess) and not ess[i]:         # stray SFX -> don't chase it
                continue
            j = min(range(len(pans)), key=lambda k: _edge_gap(t, pans[k]))
            if _edge_gap(t, pans[j]) > max_gap:
                continue
        _grow(j, t)

    for c in chars:                                 # keep a bleeding character whole
        area = max(1.0, (c[2] - c[0]) * (c[3] - c[1]))
        overlaps = [_inter_area(c, p) for p in pans]
        j = max(range(len(pans)), key=lambda k: overlaps[k])
        if overlaps[j] / area >= 0.3:               # >=30% of the character is in it
            _grow(j, c)

    boxes: list[Box] = []
    for x1, y1, x2, y2 in grown:
        x1 = max(0.0, min(x1, page_w)); x2 = max(0.0, min(x2, page_w))
        y1 = max(0.0, min(y1, page_h)); y2 = max(0.0, min(y2, page_h))
        w = int(round(x2 - x1)); h = int(round(y2 - y1))
        if w > 0 and h > 0:
            boxes.append((int(round(x1)), int(round(y1)), w, h))
    return boxes


def _pick_device(torch):
    """Best available torch device. cuda covers NVIDIA and AMD ROCm builds
    (ROCm masquerades as cuda); mps is Apple Silicon; xpu is Intel (oneAPI/Arc).
    Falls back to cpu (which is still usable — a volume is a few minutes)."""
    if torch.cuda.is_available():
        return "cuda"
    mps = getattr(torch.backends, "mps", None)
    if mps is not None and mps.is_available():
        import os
        os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")  # unsupported ops -> cpu
        return "mps"
    xpu = getattr(torch, "xpu", None)
    if xpu is not None and xpu.is_available():
        return "xpu"
    return "cpu"


def _load_magi():
    """Load Magi v2 once (singleton). Clear error if the [ml] extra is missing."""
    global _MODEL
    if _MODEL is None:
        try:
            import torch
            from transformers import AutoModel
            from transformers.utils import logging as hf_logging

            hf_logging.set_verbosity_error()
        except ImportError as e:
            raise MissingDependency(
                "failed to import torch/transformers — reinstall the deps "
                "with 'uv sync' (or pip install 'manga-panels')"
            ) from e
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            model = AutoModel.from_pretrained(_MODEL_NAME, trust_remote_code=True)
            model = model.to(_pick_device(torch)).eval()
        _MODEL = model
    return _MODEL


class MagiDetector:
    """ML detector. detect() returns panels in reading order (from Magi itself)."""

    def detect_raw(self, page: Image.Image) -> dict:
        """Full Magi output for a page (panels/texts/characters/tails +
        associations + cluster labels + is_essential_text), boxes in page px.
        Used by the debug overlay; detect() distils it to crop boxes."""
        model = _load_magi()                 # clear MissingDependency if [ml] absent
        import torch
        arr = np.array(page.convert("L").convert("RGB"))
        with torch.no_grad():
            return model.predict_detections_and_associations([arr])[0]

    def detect(self, page: Image.Image) -> list[Box]:
        r = self.detect_raw(page)
        return _panels_to_boxes(r["panels"], r["texts"], page.width, page.height,
                                characters=r["characters"], essential=r["is_essential_text"])

    def warmup(self) -> None:
        _load_magi()                  # load the singleton (spinner in the CLI)
