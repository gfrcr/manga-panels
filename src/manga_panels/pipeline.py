from __future__ import annotations

from PIL import Image

from manga_panels.archive import pack, unpack
from manga_panels.detect import Box, get_detector


def crop_panels(page: Image.Image, boxes: list[Box]) -> list[Image.Image]:
    return [page.crop((x, y, x + w, y + h)) for (x, y, w, h) in boxes]


def process_archive(in_path, out_path, *, detector: str = "xycut",
                    rtl: bool = True, min_frac: float = 0.02,
                    max_ink: float = 0.08, fmt: str = "jpeg",
                    quality: int = 90) -> int:
    det = get_detector(detector, rtl=rtl, min_frac=min_frac, max_ink=max_ink)
    pages = unpack(in_path)
    panels: list[Image.Image] = []
    for page in pages:
        boxes = det.detect(page)                   # ja vem em ordem de leitura
        if not boxes:                              # fallback: pagina inteira
            boxes = [(0, 0, page.width, page.height)]
        panels.extend(crop_panels(page, boxes))
    pack(panels, out_path, fmt=fmt, quality=quality)
    return len(panels)
