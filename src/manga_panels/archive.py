from __future__ import annotations

import io
import re
import zipfile
import zlib
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
    raise ValueError(f"formato nao suportado: {path.suffix}")


def _load(data: bytes) -> Image.Image:
    try:
        return Image.open(io.BytesIO(data)).convert("RGB")
    except (UnidentifiedImageError, OSError) as e:
        raise BadArchive(f"imagem invalida no arquivo: {e}") from e


def _unpack_zip(path: Path) -> list[Image.Image]:
    try:
        with zipfile.ZipFile(path) as z:
            names = sorted((n for n in z.namelist() if _is_image(n)), key=_natkey)
            imgs = [_load(z.read(n)) for n in names]
    except (zipfile.BadZipFile, zlib.error, RuntimeError, OSError, EOFError) as e:
        raise BadArchive(f"cbz/zip corrompido: {path.name}") from e
    if not imgs:
        raise EmptyArchive(f"nenhuma imagem em {path.name}")
    return imgs


def _unpack_rar(path: Path) -> list[Image.Image]:
    try:
        import rarfile
    except ImportError as e:
        raise MissingDependency(
            "CBR precisa do extra 'cbr': pip install 'manga-panels[cbr]' "
            "e do binario 'unrar' no sistema"
        ) from e
    try:
        with rarfile.RarFile(path) as r:
            names = sorted((n for n in r.namelist() if _is_image(n)), key=_natkey)
            imgs = [_load(r.read(n)) for n in names]
    except (rarfile.Error, zlib.error, RuntimeError, OSError, EOFError) as e:
        raise BadArchive(f"cbr/rar corrompido: {path.name}") from e
    if not imgs:
        raise EmptyArchive(f"nenhuma imagem em {path.name}")
    return imgs


def pack(images: list[Image.Image], out_path: str | Path, *,
         fmt: str = "jpeg", quality: int = 90, max_width: int | None = None) -> None:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fmt = fmt.lower()
    if fmt in ("jpg", "jpeg"):
        # jpeg ja e comprimido: STORED evita recompressao inutil no zip
        ext, pil_fmt, save_kw, compression = (
            "jpg", "JPEG", {"quality": quality}, zipfile.ZIP_STORED)
    elif fmt == "png":
        ext, pil_fmt, save_kw, compression = (
            "png", "PNG", {}, zipfile.ZIP_DEFLATED)
    else:
        raise ValueError(f"formato de imagem desconhecido: {fmt!r}")
    with zipfile.ZipFile(out_path, "w", compression) as z:
        for i, img in enumerate(images, start=1):
            if max_width and img.width > max_width:   # so reduz, nunca amplia
                h = round(img.height * max_width / img.width)
                img = img.resize((max_width, h), Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, pil_fmt, **save_kw)
            z.writestr(f"{i:04d}.{ext}", buf.getvalue())
