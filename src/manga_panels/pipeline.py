from __future__ import annotations

from typing import Callable

from PIL import Image

from manga_panels.archive import pack, unpack
from manga_panels.detect import Box, get_detector


def crop_panels(page: Image.Image, boxes: list[Box]) -> list[Image.Image]:
    return [page.crop((x, y, x + w, y + h)) for (x, y, w, h) in boxes]


def process_archive(in_path, out_path, *, detector: str = "xycut",
                    rtl: bool = True, min_frac: float = 0.02,
                    max_ink: float = 0.08, fmt: str = "jpeg",
                    quality: int = 90, page_pos: str = "before",
                    max_width: int | None = None, keep_first: int = 0,
                    on_page: Callable[[int, int], None] | None = None) -> int:
    """Explode cada pagina em paineis num CBZ novo. Retorna o total de imagens
    escritas.
    - keep_first: as primeiras N paginas ficam inteiras (capa/miolo inicial).
    - Pagina com <=1 painel (capa/splash/sem sarjeta) e emitida uma vez so.
    - page_pos: 'before' (macro antes dos paineis), 'after', ou 'off'.
    - on_page(feitas, total): chamado apos cada pagina processada (progresso)."""
    if page_pos not in ("before", "after", "off"):
        raise ValueError(f"page_pos invalido: {page_pos!r} (use before/after/off)")
    det = get_detector(detector, rtl=rtl, min_frac=min_frac, max_ink=max_ink)
    pages = unpack(in_path)
    total = len(pages)
    out_imgs: list[Image.Image] = []
    for i, page in enumerate(pages):
        if i < keep_first:                         # front-matter inteiro
            out_imgs.append(page)
        else:
            boxes = det.detect(page)               # ja vem em ordem de leitura
            if len(boxes) <= 1:                    # capa/splash/fallback -> uma vez
                out_imgs.append(page)
            else:
                if page_pos == "before":
                    out_imgs.append(page)
                out_imgs.extend(crop_panels(page, boxes))
                if page_pos == "after":
                    out_imgs.append(page)
        if on_page is not None:
            on_page(i + 1, total)
    pack(out_imgs, out_path, fmt=fmt, quality=quality, max_width=max_width)
    return len(out_imgs)
