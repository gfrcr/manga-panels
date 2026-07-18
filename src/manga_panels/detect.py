from __future__ import annotations

from typing import Protocol, runtime_checkable

from PIL import Image

Box = tuple[int, int, int, int]  # (x, y, w, h)


@runtime_checkable
class Detector(Protocol):
    def detect(self, page: Image.Image) -> list[Box]: ...
    def warmup(self) -> None: ...
