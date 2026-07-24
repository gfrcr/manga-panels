from __future__ import annotations

from typing import Callable

from PIL import Image

from manga_panels.archive import load_image, pack, unpack
from manga_panels.detect import Box
from manga_panels.ml import MagiDetector


def crop_panels(page: Image.Image, boxes: list[Box]) -> list[Image.Image]:
    return [page.crop((x, y, x + w, y + h)) for (x, y, w, h) in boxes]


def process_archive(in_path, out_path, *, fmt: str = "jpeg", quality: int = 90,
                    page_pos: str = "before", max_width: int | None = None,
                    keep_first: int = 0, grayscale: bool = False, gamma: float = 1.0,
                    cover=None,
                    on_page: Callable[[int, int], None] | None = None) -> int:
    """Explode each page into panels in a new CBZ. Returns the total number of
    images written.
    - keep_first: the first N pages are kept whole (cover/front matter).
    - A page with <=1 panel (cover/splash) is emitted only once.
    - page_pos: 'before' (macro page before the panels), 'after', or 'off'.
    - on_page(done, total): called after each processed page (progress)."""
    if page_pos not in ("before", "after", "off"):
        raise ValueError(f"invalid page_pos: {page_pos!r} (use before/after/off)")
    det = MagiDetector()
    pages = unpack(in_path)
    total = len(pages)
    out_imgs: list[Image.Image] = []
    if cover is not None:                          # a fixed cover -> PDF page 1 / thumbnail
        out_imgs.append(load_image(cover))
    for i, page in enumerate(pages):
        if i < keep_first:                         # keep front matter whole
            out_imgs.append(page)
        else:
            boxes = det.detect(page)               # already in reading order
            if len(boxes) <= 1:                    # cover/splash/fallback -> once
                out_imgs.append(page)
            else:
                if page_pos == "before":
                    out_imgs.append(page)
                out_imgs.extend(crop_panels(page, boxes))
                if page_pos == "after":
                    out_imgs.append(page)
        if on_page is not None:
            on_page(i + 1, total)
    pack(out_imgs, out_path, fmt=fmt, quality=quality, max_width=max_width,
         grayscale=grayscale, gamma=gamma)
    return len(out_imgs)
