from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np
from PIL import Image

Box = tuple[int, int, int, int]  # (x, y, w, h)


@runtime_checkable
class Detector(Protocol):
    def detect(self, page: Image.Image) -> list[Box]: ...


def _content_segments(is_bg: np.ndarray, min_gutter: int) -> list[tuple[int, int]]:
    """Segmentos de conteudo (start, end) separados por sarjetas (runs de fundo
    com comprimento >= min_gutter). Retorna [] se nao ha corte interno real."""
    L = len(is_bg)
    gutters: list[tuple[int, int]] = []
    run_start: int | None = None
    for i, b in enumerate(is_bg):
        if b:
            if run_start is None:
                run_start = i
        elif run_start is not None:
            if i - run_start >= min_gutter:
                gutters.append((run_start, i))
            run_start = None
    if run_start is not None and L - run_start >= min_gutter:
        gutters.append((run_start, L))
    if not gutters:
        return []
    points = [0]
    for s, e in gutters:
        points += [s, e]
    points.append(L)
    segs = [(a, b) for a, b in zip(points[0::2], points[1::2]) if b > a]
    return segs if len(segs) > 1 else []


class XYCutDetector:
    def __init__(self, bg_thresh: int = 200, min_gutter: int = 5,
                 min_frac: float = 0.02, rtl: bool = True,
                 max_ink: float = 0.08) -> None:
        self.bg_thresh = bg_thresh
        self.min_gutter = min_gutter
        self.min_frac = min_frac
        self.rtl = rtl
        # max_ink: fracao maxima de tinta numa linha/coluna pra ela ainda contar
        # como sarjeta (fundo). Scans reais tem screentone/baloes/onomatopeia
        # cruzando a sarjeta; 0.01 (quase-puro-branco) sub-segmenta demais.
        self.max_ink = max_ink

    def detect(self, page: Image.Image) -> list[Box]:
        gray = np.asarray(page.convert("L"))
        h, w = gray.shape
        min_area = self.min_frac * h * w
        out: list[Box] = []
        # axis 0 = corta horizontalmente (linhas empilhadas); axis 1 = colunas
        self._recurse(gray, 0, 0, w, h, axis=0, min_area=min_area, out=out)
        return out

    def _recurse(self, gray, x, y, w, h, axis, min_area, out) -> None:
        region = gray[y:y + h, x:x + w]
        ink = region < self.bg_thresh          # True onde tem traco
        # fracao de tinta por linha ao longo do eixo de corte
        line_ink = ink.mean(axis=1 - axis)     # axis0 -> por linha(y); axis1 -> por coluna(x)
        is_bg = line_ink < self.max_ink
        segs = _content_segments(is_bg, self.min_gutter)
        if not segs:
            other = 1 - axis
            line_ink = ink.mean(axis=1 - other)
            segs = _content_segments(line_ink < self.max_ink, self.min_gutter)
            if not segs:
                if w * h >= min_area and ink.any():
                    out.append((x, y, w, h))
                return
            axis = other
        if axis == 1 and self.rtl:             # colunas: emitir direita->esquerda
            segs = segs[::-1]
        for s, e in segs:
            if axis == 0:
                self._recurse(gray, x, y + s, w, e - s, 1, min_area, out)
            else:
                self._recurse(gray, x + s, y, e - s, h, 0, min_area, out)


def get_detector(name: str, *, rtl: bool = True, min_frac: float = 0.02,
                 max_ink: float = 0.08) -> Detector:
    if name == "xycut":
        return XYCutDetector(rtl=rtl, min_frac=min_frac, max_ink=max_ink)
    if name == "ml":
        from manga_panels.ml import MagiDetector   # import lazy
        return MagiDetector()
    raise ValueError(f"detector desconhecido: {name!r}")
