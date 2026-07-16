from __future__ import annotations

from PIL import Image

from manga_panels.archive import pack, unpack
from manga_panels.detect import Box, get_detector


def crop_panels(page: Image.Image, boxes: list[Box]) -> list[Image.Image]:
    return [page.crop((x, y, x + w, y + h)) for (x, y, w, h) in boxes]


def process_archive(in_path, out_path, *, detector: str = "xycut",
                    rtl: bool = True, min_frac: float = 0.02,
                    max_ink: float = 0.08, fmt: str = "jpeg",
                    quality: int = 90, include_page: bool = True,
                    max_width: int | None = None) -> int:
    """Explode cada pagina em paineis num CBZ novo. Retorna o total de imagens
    escritas. Com include_page (default), a pagina inteira vem antes dos seus
    paineis (visao macro, depois os quadros ampliados)."""
    det = get_detector(detector, rtl=rtl, min_frac=min_frac, max_ink=max_ink)
    pages = unpack(in_path)
    out_imgs: list[Image.Image] = []
    for page in pages:
        boxes = det.detect(page)                   # ja vem em ordem de leitura
        if not boxes:                              # sem sarjeta: a pagina ja E o painel
            out_imgs.append(page)                  # (nao duplica)
            continue
        if include_page:                           # macro primeiro, depois os quadros
            out_imgs.append(page)
        out_imgs.extend(crop_panels(page, boxes))
    pack(out_imgs, out_path, fmt=fmt, quality=quality, max_width=max_width)
    return len(out_imgs)
