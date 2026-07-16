# src/manga_panels/ml.py
"""Detector de paineis via Magi v2. Todo import de torch/transformers e LAZY
(dentro das funcoes) pra o base install continuar leve."""
from __future__ import annotations

import numpy as np
from PIL import Image

from manga_panels.detect import Box

_MODEL_NAME = "ragavsachdeva/magiv2"
_MODEL = None  # singleton carregado sob demanda


def _panels_to_boxes(panels, page_w: int, page_h: int) -> list[Box]:
    """[x1,y1,x2,y2] (pixels, ordem de leitura do Magi) -> (x,y,w,h) int,
    clampado na pagina, sem caixas degeneradas. Preserva a ordem."""
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


def _load_magi():
    """Carrega o Magi v2 uma vez (singleton). Erro claro se o extra [ml] falta."""
    global _MODEL
    if _MODEL is None:
        try:
            import torch
            from transformers import AutoModel
        except ImportError as e:
            raise RuntimeError(
                "detector ml precisa do extra [ml]: uv sync --extra ml "
                "(ou pip install 'manga-panels[ml]')"
            ) from e
        model = AutoModel.from_pretrained(_MODEL_NAME, trust_remote_code=True)
        model = model.to("cuda" if torch.cuda.is_available() else "cpu").eval()
        _MODEL = model
    return _MODEL


class MagiDetector:
    """Detector ML. detect() devolve paineis em ordem de leitura (do proprio Magi)."""

    def detect(self, page: Image.Image) -> list[Box]:
        model = _load_magi()                 # RuntimeError claro se [ml] ausente
        import torch
        arr = np.array(page.convert("L").convert("RGB"))
        with torch.no_grad():
            results = model.predict_detections_and_associations([arr])
        return _panels_to_boxes(results[0]["panels"], page.width, page.height)
