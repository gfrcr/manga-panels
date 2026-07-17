"""Modo preview: anota cada pagina com os paineis desenhados (sem cortar),
pra calibrar antes de processar o volume."""
from __future__ import annotations

from typing import Callable

from PIL import Image, ImageDraw, ImageFont

from manga_panels.archive import pack, unpack
from manga_panels.detect import Box, get_detector


def _font(size: int):
    try:
        return ImageFont.load_default(size=size)   # Pillow >= 10.1
    except TypeError:                              # Pillow antigo
        return ImageFont.load_default()


def annotate_page(page: Image.Image, boxes: list[Box]) -> Image.Image:
    """Copia a pagina e desenha cada painel (retangulo + numero na ordem de
    leitura). Nao altera a original. Cor red->green = progressao da leitura."""
    im = page.convert("RGB").copy()
    d = ImageDraw.Draw(im, "RGBA")
    n = len(boxes)
    f = _font(max(24, im.width // 20))
    line = max(3, im.width // 200)
    r = max(16, im.width // 28)
    for i, (x, y, w, h) in enumerate(boxes):
        t = i / max(1, n - 1)
        col = (int(255 * (1 - t)), int(180 * t), 40)
        d.rectangle([x, y, x + w - 1, y + h - 1], outline=col, width=line)
        cx, cy = x + w // 2, y + h // 2
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(0, 0, 0, 200), outline=col, width=3)
        tb = d.textbbox((0, 0), str(i), font=f)
        d.text((cx - (tb[2] - tb[0]) / 2, cy - (tb[3] - tb[1]) / 2 - tb[1]),
               str(i), fill=(255, 255, 255), font=f)
    return im


def preview_archive(in_path, out_path, *, detector: str = "xycut", rtl: bool = True,
                    min_frac: float = 0.02, max_ink: float = 0.08, fmt: str = "jpeg",
                    quality: int = 90, max_width: int | None = None, on_page: Callable[[int, int], None] | None = None) -> int:
    det = get_detector(detector, rtl=rtl, min_frac=min_frac, max_ink=max_ink)
    pages = unpack(in_path)
    total = len(pages)
    out = []
    for i, p in enumerate(pages):
        out.append(annotate_page(p, det.detect(p)))
        if on_page is not None:
            on_page(i + 1, total)
    pack(out, out_path, fmt=fmt, quality=quality, max_width=max_width)
    return len(out)
