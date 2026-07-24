from __future__ import annotations

import io
import os
import re
import zipfile
import zlib
from contextlib import contextmanager
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from manga_panels.errors import BadArchive, EmptyArchive, MissingDependency

_IMG_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}


def _is_image(name: str) -> bool:
    return Path(name).suffix.lower() in _IMG_EXT


def _natkey(name: str):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", name)]


def unpack(path: str | Path) -> list[Image.Image]:
    path = Path(path)
    ext = path.suffix.lower()
    if ext == ".cbz" or ext == ".zip":
        return _unpack_zip(path)
    if ext == ".cbr" or ext == ".rar":
        return _unpack_rar(path)
    if ext in _IMG_EXT:                       # a bare image -> single page
        try:
            data = path.read_bytes()
        except OSError as e:
            raise BadArchive(f"cannot read {path.name}: {e}") from e
        return [_load(data)]
    raise ValueError(f"unsupported format: {path.suffix}")


def _load(data: bytes) -> Image.Image:
    try:
        return Image.open(io.BytesIO(data)).convert("RGB")
    except (UnidentifiedImageError, OSError) as e:
        raise BadArchive(f"invalid image in archive: {e}") from e


def _unpack_zip(path: Path) -> list[Image.Image]:
    try:
        with zipfile.ZipFile(path) as z:
            names = sorted((n for n in z.namelist() if _is_image(n)), key=_natkey)
            imgs = [_load(z.read(n)) for n in names]
    except (zipfile.BadZipFile, zlib.error, RuntimeError, OSError, EOFError) as e:
        raise BadArchive(f"corrupt cbz/zip: {path.name}") from e
    if not imgs:
        raise EmptyArchive(f"no images in {path.name}")
    return imgs


def _unpack_rar(path: Path) -> list[Image.Image]:
    try:
        import rarfile
    except ImportError as e:
        raise MissingDependency(
            "CBR needs the 'cbr' extra: pip install 'manga-panels[cbr]' "
            "and the 'unrar' binary on the system"
        ) from e
    try:
        with rarfile.RarFile(path) as r:
            names = sorted((n for n in r.namelist() if _is_image(n)), key=_natkey)
            imgs = [_load(r.read(n)) for n in names]
    except (rarfile.Error, zlib.error, RuntimeError, OSError, EOFError) as e:
        raise BadArchive(f"corrupt cbr/rar: {path.name}") from e
    if not imgs:
        raise EmptyArchive(f"no images in {path.name}")
    return imgs


def _fit(img: Image.Image, max_width: int | None) -> Image.Image:
    if max_width and img.width > max_width:       # only shrink, never upscale
        h = round(img.height * max_width / img.width)
        return img.resize((max_width, h), Image.LANCZOS)
    return img


def _eink(img: Image.Image, *, grayscale: bool, gamma: float) -> Image.Image:
    """e-ink tweaks: grayscale (smaller + native to e-paper) and gamma (>1 darkens
    midtones for punchier contrast; 1.0 = off)."""
    if grayscale and img.mode != "L":
        img = img.convert("L")
    if gamma and gamma != 1.0:
        lut = [round(255 * (i / 255) ** gamma) for i in range(256)]
        img = img.point(lut * len(img.getbands()))
    return img


@contextmanager
def _atomic(out_path: Path):
    """Yield a temp path; on success swap it onto out_path atomically, on any
    failure (incl. KeyboardInterrupt) delete it. So a crash/kill/error mid-write
    never leaves a half-written, corrupt file — you get the complete file or none."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_name(out_path.name + ".tmp")   # same dir -> os.replace is atomic
    try:
        yield tmp
        os.replace(tmp, out_path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def pack(images: list[Image.Image], out_path: str | Path, *,
         fmt: str = "jpeg", quality: int = 90, max_width: int | None = None,
         grayscale: bool = False, gamma: float = 1.0) -> None:
    out_path = Path(out_path)
    fmt = fmt.lower()
    if fmt == "pdf":                              # a PDF file, one panel per page
        _pack_pdf(images, out_path, quality=quality, max_width=max_width,
                  grayscale=grayscale, gamma=gamma)
        return
    if fmt in ("jpg", "jpeg"):
        # jpeg is already compressed: STORED avoids pointless zip recompression
        ext, pil_fmt, save_kw, compression = (
            "jpg", "JPEG", {"quality": quality}, zipfile.ZIP_STORED)
    elif fmt == "png":
        ext, pil_fmt, save_kw, compression = (
            "png", "PNG", {}, zipfile.ZIP_DEFLATED)
    else:
        raise ValueError(f"unknown image format: {fmt!r}")
    with _atomic(out_path) as tmp:
        with zipfile.ZipFile(tmp, "w", compression) as z:
            for i, img in enumerate(images, start=1):
                buf = io.BytesIO()
                im = _eink(_fit(img, max_width), grayscale=grayscale, gamma=gamma)
                im.save(buf, pil_fmt, **save_kw)
                z.writestr(f"{i:04d}.{ext}", buf.getvalue())


def _pack_pdf(images: list[Image.Image], out_path: Path, *, quality: int,
              max_width: int | None, grayscale: bool, gamma: float) -> None:
    """Embed each panel as a PDF page. img2pdf stores the JPEG bytes as-is (no
    re-encode), so no extra quality loss. For Kindle & other PDF-only readers."""
    try:
        import img2pdf
    except ImportError as e:
        raise MissingDependency(
            "PDF output needs the [pdf] extra: uv sync --extra pdf "
            "(or pip install 'manga-panels[pdf]')"
        ) from e
    jpegs = []
    for img in images:
        im = _eink(_fit(img, max_width), grayscale=grayscale, gamma=gamma)
        if im.mode not in ("L", "RGB"):
            im = im.convert("RGB")
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=quality)
        jpegs.append(buf.getvalue())
    with _atomic(out_path) as tmp:
        tmp.write_bytes(img2pdf.convert(jpegs))
