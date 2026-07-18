"""Debug mode: draw *everything* Magi sees on each page — panels, characters
(colored by identity cluster), speech-bubble tails, and texts colored by the
character they're attributed to (SFX/non-essential marked). For inspecting the
model, not for reading. `--preview` shows only the panel cuts; this shows all."""
from __future__ import annotations

from typing import Callable

from PIL import Image, ImageDraw, ImageFont

from manga_panels.archive import pack, unpack
from manga_panels.ml import MagiDetector

_PALETTE = [(220, 30, 30), (30, 120, 230), (30, 170, 60), (200, 120, 0),
            (150, 40, 200), (0, 160, 160), (230, 90, 160), (110, 110, 40)]
_GRAY = (130, 130, 130)
_TAIL = (255, 0, 255)


def _font(size: int):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _center(b):
    return ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)


def annotate_debug(page: Image.Image, r: dict) -> Image.Image:
    """Draw Magi's full understanding of `page` from its raw result `r`.
    Does not modify the original."""
    im = page.convert("RGB").copy()
    d = ImageDraw.Draw(im)
    f = _font(max(14, im.width // 45))
    line = max(2, im.width // 500)
    clusters = r.get("character_cluster_labels", [])
    chars = r.get("characters", [])
    essential = r.get("is_essential_text", [])
    t2c = {a[0]: a[1] for a in r.get("text_character_associations", [])}

    for p in r.get("panels", []):                        # panels: thin gray
        d.rectangle([p[0], p[1], p[2], p[3]], outline=_GRAY, width=line)
    for t in r.get("tails", []):                         # tails: magenta
        d.rectangle([t[0], t[1], t[2], t[3]], outline=_TAIL, width=line)
    for i, c in enumerate(chars):                        # characters: color = identity
        col = _PALETTE[clusters[i] % len(_PALETTE)] if i < len(clusters) else _GRAY
        d.rectangle([c[0], c[1], c[2], c[3]], outline=col, width=line + 1)
        if i < len(clusters):
            d.text((c[0] + 3, c[1] + 2), f"C{clusters[i]}", fill=col, font=f)
    for i, t in enumerate(r.get("texts", [])):           # texts: color = speaker
        cid = t2c.get(i)
        if cid is not None and cid < len(chars):
            col = _PALETTE[clusters[cid] % len(_PALETTE)] if cid < len(clusters) else _GRAY
            d.line([_center(t), _center(chars[cid])], fill=col, width=line)
        else:
            col = _GRAY
        d.rectangle([t[0], t[1], t[2], t[3]], outline=col, width=line)
        if i < len(essential) and not essential[i]:
            d.text((t[0] + 2, max(0, t[1] - im.width // 45)), "SFX", fill=_GRAY, font=f)
    return im


def debug_archive(in_path, out_path, *, fmt: str = "jpeg", quality: int = 90,
                  max_width: int | None = None,
                  on_page: Callable[[int, int], None] | None = None) -> int:
    det = MagiDetector()
    pages = unpack(in_path)
    total = len(pages)
    out = []
    for i, p in enumerate(pages):
        out.append(annotate_debug(p, det.detect_raw(p)))
        if on_page is not None:
            on_page(i + 1, total)
    pack(out, out_path, fmt=fmt, quality=quality, max_width=max_width)
    return len(out)
