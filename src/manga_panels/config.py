"""Carrega defaults de um manga-panels.toml (tabela [defaults]). CLI vence."""
from __future__ import annotations

import tomllib
from pathlib import Path

from manga_panels.errors import MangaPanelsError

# chaves aceitas = dest do argparse
_KNOWN = {"output", "detector", "min_area", "max_ink", "format", "quality",
          "max_width", "preview", "ltr", "page", "keep_first"}

_DISCOVER = [
    Path("manga-panels.toml"),
    Path.home() / ".config" / "manga-panels" / "config.toml",
]


def load_config(explicit_path: str | None = None, *, warn=print) -> dict:
    if explicit_path is not None:
        path = Path(explicit_path)
        if not path.exists():
            raise MangaPanelsError(f"config nao encontrado: {explicit_path}")
    else:
        path = next((p for p in _DISCOVER if p.exists()), None)
        if path is None:
            return {}
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, OSError) as e:
        raise MangaPanelsError(f"config invalido ({path}): {e}") from e
    out: dict = {}
    for k, v in data.get("defaults", {}).items():
        key = k.replace("-", "_")
        if key in _KNOWN:
            out[key] = v
        else:
            warn(f"config: chave desconhecida ignorada: {k}")
    return out
