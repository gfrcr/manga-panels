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


def _panels_to_boxes(panels, page_w: int, page_h: int) -> list[Box]:
    """[x1,y1,x2,y2] (pixels, Magi reading order) -> (x,y,w,h) int, clamped to
    the page, without degenerate boxes. Preserves order."""
    boxes: list[Box] = []
    for p in panels:
        x1, y1, x2, y2 = (float(v) for v in p[:4])
        if x2 < x1:
            x1, x2 = x2, x1
        if y2 < y1:
            y1, y2 = y2, y1
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
                "ml detector needs the [ml] extra: uv sync --extra ml "
                "(or pip install 'manga-panels[ml]')"
            ) from e
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            model = AutoModel.from_pretrained(_MODEL_NAME, trust_remote_code=True)
            model = model.to(_pick_device(torch)).eval()
        _MODEL = model
    return _MODEL


class MagiDetector:
    """ML detector. detect() returns panels in reading order (from Magi itself)."""

    def detect(self, page: Image.Image) -> list[Box]:
        model = _load_magi()                 # clear MissingDependency if [ml] absent
        import torch
        arr = np.array(page.convert("L").convert("RGB"))
        with torch.no_grad():
            results = model.predict_detections_and_associations([arr])
        return _panels_to_boxes(results[0]["panels"], page.width, page.height)

    def warmup(self) -> None:
        _load_magi()                  # load the singleton (spinner in the CLI)
