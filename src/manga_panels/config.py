"""Load defaults from a manga-panels.toml ([defaults] table). The CLI wins."""
from __future__ import annotations

import tomllib
from pathlib import Path

from manga_panels.errors import MangaPanelsError

# accepted keys = argparse dests
_KNOWN = {"output", "library", "format", "quality", "max_width", "preview",
          "page", "keep_first", "suffix", "overwrite"}

_DISCOVER = [
    Path("manga-panels.toml"),
    Path.home() / ".config" / "manga-panels" / "config.toml",
]


def load_config(explicit_path: str | None = None, *, warn=print) -> dict:
    if explicit_path is not None:
        path = Path(explicit_path)
        if not path.exists():
            raise MangaPanelsError(f"config not found: {explicit_path}")
    else:
        path = next((p for p in _DISCOVER if p.exists()), None)
        if path is None:
            return {}
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, OSError) as e:
        raise MangaPanelsError(f"invalid config ({path}): {e}") from e
    out: dict = {}
    for k, v in data.get("defaults", {}).items():
        key = k.replace("-", "_")
        if key in _KNOWN:
            out[key] = v
        else:
            warn(f"config: unknown key ignored: {k}")
    return out
