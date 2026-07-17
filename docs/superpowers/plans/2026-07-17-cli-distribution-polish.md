# CLI Distribution Polish — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Polir o CLI pra distribuição: erros claros, callback de progresso, saída Rich (barra + spinner + tabela), arquivo de config TOML, e deps/uv.

**Architecture:** `errors.py` (exceções tipadas) alimenta `archive`/`ml`; `pipeline`/`preview` ganham `on_page`; detectores ganham `warmup`; `config.py` lê `manga-panels.toml`; `cli.py` é reescrito com Rich + config + captura de `MangaPanelsError`.

**Tech Stack:** Python 3.14, Pillow, numpy, **rich**, **rich-argparse** (pure-python), `tomllib` (stdlib).

## Global Constraints

- Falhas conhecidas levantam `MangaPanelsError` (subclasse): `EmptyArchive`, `BadArchive`, `MissingDependency`. Mensagem acionável, não stack trace.
- No batch, um arquivo ruim imprime a falha e **segue**; exit code ≠0 se algum falhou.
- `on_page(feitas: int, total: int)` opcional em `process_archive`/`preview_archive`; sem callback → comportamento atual.
- `warmup()` em todo `Detector`: `XYCutDetector` no-op, `MagiDetector` carrega o singleton.
- Config: TOML `[defaults]` com chaves = `dest` do argparse; **flag na CLI sempre vence** (default argparse < config < flag). tomllib stdlib, zero dep.
- `rich`+`rich-argparse` nas deps base. Rich degrada sozinho fora de tty (testes não quebram).
- pytest, plain assert, testes ML gated (`-m ml`) inalterados. Cada task termina com commit.

---

## File Structure

- `src/manga_panels/errors.py` (novo) — `MangaPanelsError` + 3 subclasses.
- `src/manga_panels/config.py` (novo) — `load_config`.
- `src/manga_panels/archive.py` (mod) — raise `EmptyArchive`/`BadArchive`/`MissingDependency`.
- `src/manga_panels/ml.py` (mod) — `_load_magi` raise `MissingDependency`; `MagiDetector.warmup`.
- `src/manga_panels/detect.py` (mod) — `warmup` no protocolo + `XYCutDetector.warmup`.
- `src/manga_panels/pipeline.py` (mod) — `on_page` em `process_archive`.
- `src/manga_panels/preview.py` (mod) — `on_page` em `preview_archive`.
- `src/manga_panels/cli.py` (mod) — Rich + config + captura de erro.
- `pyproject.toml` (mod) — `rich`, `rich-argparse`.

---

## Task 1: Erros tipados (errors.py + archive + ml)

**Files:**
- Create: `src/manga_panels/errors.py`
- Modify: `src/manga_panels/archive.py`, `src/manga_panels/ml.py`, `src/manga_panels/cli.py`
- Modify tests: `tests/test_archive.py`, `tests/test_ml.py`, `tests/test_pipeline.py`

**Interfaces:**
- Produces: `MangaPanelsError`, `EmptyArchive`, `BadArchive`, `MissingDependency` (todas em `manga_panels.errors`). `unpack` levanta `EmptyArchive`/`BadArchive`; `_unpack_rar`/`_load_magi` levantam `MissingDependency`.

- [ ] **Step 1: Write the failing tests**

Adicione a `tests/test_archive.py`:
```python
def test_unpack_empty_archive_raises(tmp_path):
    import pytest, zipfile
    from manga_panels.errors import EmptyArchive
    cbz = tmp_path / "empty.cbz"
    with zipfile.ZipFile(cbz, "w") as z:
        z.writestr("leiame.txt", "sem imagens")
    with pytest.raises(EmptyArchive):
        unpack(cbz)


def test_unpack_corrupt_archive_raises(tmp_path):
    import pytest
    from manga_panels.errors import BadArchive
    cbz = tmp_path / "bad.cbz"
    cbz.write_bytes(b"nao sou um zip")
    with pytest.raises(BadArchive):
        unpack(cbz)
```

Em `tests/test_ml.py`, TROQUE `test_load_magi_missing_deps_raises_runtimeerror` por:
```python
def test_load_magi_missing_deps_raises_missing_dependency(monkeypatch):
    from manga_panels.errors import MissingDependency
    ml._MODEL = None
    monkeypatch.setitem(sys.modules, "torch", None)   # import torch -> ImportError
    with pytest.raises(MissingDependency, match="uv sync --extra ml"):
        ml._load_magi()
```

Em `tests/test_pipeline.py`, no `test_cli_ml_detector_reports_error_without_raising`, TROQUE o corpo de `_boom` por:
```python
    def _boom():
        from manga_panels.errors import MissingDependency
        raise MissingDependency("detector ml precisa do extra [ml]: uv sync --extra ml")
```

- [ ] **Step 2: Run to verify the new tests fail**

Run: `.venv/bin/pytest tests/test_archive.py -k "empty or corrupt" tests/test_ml.py -k missing -q`
Expected: FAIL (`ModuleNotFoundError: manga_panels.errors` / erro atual é `RuntimeError`).

- [ ] **Step 3: Create `src/manga_panels/errors.py`**

```python
"""Erros conhecidos do manga_panels — mensagem acionavel, nao stack trace."""
from __future__ import annotations


class MangaPanelsError(Exception):
    """Base pra falhas esperadas (o CLI captura e imprime a mensagem)."""


class EmptyArchive(MangaPanelsError):
    """Arquivo sem nenhuma imagem."""


class BadArchive(MangaPanelsError):
    """Arquivo corrompido ou imagem invalida dentro dele."""


class MissingDependency(MangaPanelsError):
    """Extra opcional ([ml]/cbr) ou binario do sistema ausente."""
```

- [ ] **Step 4: Update `archive.py` to raise the typed errors**

Troque os imports do topo e as funções `_load`, `_unpack_zip`, `_unpack_rar`:
```python
from PIL import Image, UnidentifiedImageError

from manga_panels.errors import BadArchive, EmptyArchive, MissingDependency
```
```python
def _load(data: bytes) -> Image.Image:
    try:
        return Image.open(io.BytesIO(data)).convert("RGB")
    except UnidentifiedImageError as e:
        raise BadArchive(f"imagem invalida no arquivo: {e}") from e


def _unpack_zip(path: Path) -> list[Image.Image]:
    try:
        with zipfile.ZipFile(path) as z:
            names = sorted((n for n in z.namelist() if _is_image(n)), key=_natkey)
            imgs = [_load(z.read(n)) for n in names]
    except zipfile.BadZipFile as e:
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
    except rarfile.Error as e:
        raise BadArchive(f"cbr/rar corrompido: {path.name}") from e
    if not imgs:
        raise EmptyArchive(f"nenhuma imagem em {path.name}")
    return imgs
```

- [ ] **Step 5: Update `ml._load_magi` to raise `MissingDependency`**

Em `src/manga_panels/ml.py`, adicione o import e troque o `raise RuntimeError(...)` do `except ImportError`:
```python
from manga_panels.errors import MissingDependency
```
```python
        except ImportError as e:
            raise MissingDependency(
                "detector ml precisa do extra [ml]: uv sync --extra ml "
                "(ou pip install 'manga-panels[ml]')"
            ) from e
```

- [ ] **Step 6: Update the CLI's except clauses**

Em `src/manga_panels/cli.py`, adicione `from manga_panels.errors import MangaPanelsError` e troque as DUAS ocorrências de `except (NotImplementedError, RuntimeError, ValueError) as e:` por:
```python
    except (MangaPanelsError, ValueError) as e:
```

- [ ] **Step 7: Run the full suite**

Run: `.venv/bin/pytest -q`
Expected: PASS (os testes novos + os atualizados; nada quebrado).

- [ ] **Step 8: Commit**

```bash
git add src/manga_panels/errors.py src/manga_panels/archive.py src/manga_panels/ml.py src/manga_panels/cli.py tests/
git commit -m "feat: typed errors (MangaPanelsError + Empty/Bad/MissingDependency)"
```

---

## Task 2: Callback de progresso + warmup

**Files:**
- Modify: `src/manga_panels/pipeline.py`, `src/manga_panels/preview.py`, `src/manga_panels/detect.py`, `src/manga_panels/ml.py`
- Modify test: `tests/test_pipeline.py`; Create: `tests/test_warmup.py`

**Interfaces:**
- Consumes: nada novo.
- Produces:
  - `process_archive(..., on_page: Callable[[int, int], None] | None = None) -> int` — chama `on_page(feitas, total)` após cada página.
  - `preview_archive(..., on_page=...) -> int` — idem.
  - `Detector.warmup(self) -> None`; `XYCutDetector.warmup` (no-op); `MagiDetector.warmup` (carrega singleton).

- [ ] **Step 1: Write the failing tests**

Adicione a `tests/test_pipeline.py`:
```python
def test_process_archive_on_page_called_per_page(tmp_path):
    calls = []
    src = tmp_path / "ch.cbz"
    pack([_grid_page(), _grid_page()], src)
    process_archive(src, tmp_path / "o.cbz",
                    on_page=lambda done, total: calls.append((done, total)))
    assert calls == [(1, 2), (2, 2)]
```

Crie `tests/test_warmup.py`:
```python
from manga_panels.detect import XYCutDetector, get_detector
import manga_panels.ml as ml


def test_xycut_warmup_is_noop():
    XYCutDetector().warmup()          # nao levanta, nao carrega nada


def test_magi_warmup_calls_load(monkeypatch):
    called = []
    monkeypatch.setattr(ml, "_load_magi", lambda: called.append(True))
    get_detector("ml").warmup()
    assert called == [True]
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/bin/pytest tests/test_pipeline.py -k on_page tests/test_warmup.py -q`
Expected: FAIL (`process_archive` sem `on_page`; `warmup` inexistente).

- [ ] **Step 3: Add `on_page` to `process_archive` (pipeline.py)**

Troque a assinatura e o loop de `process_archive` (mantém a validação de `page_pos`):
```python
def process_archive(in_path, out_path, *, detector: str = "xycut",
                    rtl: bool = True, min_frac: float = 0.02,
                    max_ink: float = 0.08, fmt: str = "jpeg",
                    quality: int = 90, page_pos: str = "before",
                    max_width: int | None = None, keep_first: int = 0,
                    on_page=None) -> int:
    """... (docstring atual) ..."""
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
```

- [ ] **Step 4: Add `on_page` to `preview_archive` (preview.py)**

Troque `preview_archive`:
```python
def preview_archive(in_path, out_path, *, detector: str = "xycut", rtl: bool = True,
                    min_frac: float = 0.02, max_ink: float = 0.08, fmt: str = "jpeg",
                    quality: int = 90, max_width: int | None = None, on_page=None) -> int:
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
```

- [ ] **Step 5: Add `warmup` to the detectors**

Em `src/manga_panels/detect.py`, adicione `warmup` ao protocolo e ao `XYCutDetector`:
```python
@runtime_checkable
class Detector(Protocol):
    def detect(self, page: Image.Image) -> list[Box]: ...
    def warmup(self) -> None: ...
```
No fim da classe `XYCutDetector` (depois de `_recurse`):
```python
    def warmup(self) -> None:
        pass                          # xycut nao carrega nada
```

Em `src/manga_panels/ml.py`, adicione ao `MagiDetector` (depois de `detect`):
```python
    def warmup(self) -> None:
        _load_magi()                  # carrega o singleton (spinner no CLI)
```

- [ ] **Step 6: Run the tests**

Run: `.venv/bin/pytest tests/test_pipeline.py tests/test_warmup.py tests/test_preview.py -q`
Expected: PASS.

- [ ] **Step 7: Run full suite + commit**

Run: `.venv/bin/pytest -q` → PASS.
```bash
git add src/manga_panels/pipeline.py src/manga_panels/preview.py src/manga_panels/detect.py src/manga_panels/ml.py tests/test_pipeline.py tests/test_warmup.py
git commit -m "feat: on_page progress callback + Detector.warmup"
```

---

## Task 3: Config TOML

**Files:**
- Create: `src/manga_panels/config.py`, `tests/test_config.py`

**Interfaces:**
- Consumes: `MangaPanelsError` (errors).
- Produces: `load_config(explicit_path: str | None = None, *, warn=print) -> dict` — lê `[defaults]` de um TOML, retorna `{dest: valor}`. Descoberta: `explicit_path`, senão `./manga-panels.toml`, senão `~/.config/manga-panels/config.toml`. Chave desconhecida → `warn(msg)` e ignora. TOML inválido ou `explicit_path` inexistente → `MangaPanelsError`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_config.py
import pytest
from manga_panels.config import load_config
from manga_panels.errors import MangaPanelsError
import manga_panels.config as config


def test_reads_defaults(tmp_path):
    cfg = tmp_path / "c.toml"
    cfg.write_text('[defaults]\ndetector = "ml"\nmax_width = 1264\n')
    assert load_config(str(cfg)) == {"detector": "ml", "max_width": 1264}


def test_unknown_key_ignored_with_warning(tmp_path):
    cfg = tmp_path / "c.toml"
    cfg.write_text('[defaults]\ndetector = "ml"\nbogus = 1\n')
    warned = []
    assert load_config(str(cfg), warn=warned.append) == {"detector": "ml"}
    assert warned                      # avisou sobre a chave desconhecida


def test_hyphen_key_normalized(tmp_path):
    cfg = tmp_path / "c.toml"
    cfg.write_text('[defaults]\nkeep-first = 2\n')
    assert load_config(str(cfg)) == {"keep_first": 2}


def test_missing_explicit_raises(tmp_path):
    with pytest.raises(MangaPanelsError):
        load_config(str(tmp_path / "nope.toml"))


def test_bad_toml_raises(tmp_path):
    cfg = tmp_path / "c.toml"
    cfg.write_text("isto = = nao e toml")
    with pytest.raises(MangaPanelsError):
        load_config(str(cfg))


def test_no_file_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "_DISCOVER", [tmp_path / "manga-panels.toml"])
    assert load_config(None) == {}     # nenhum arquivo -> sem defaults
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/bin/pytest tests/test_config.py -q`
Expected: FAIL com `ModuleNotFoundError: manga_panels.config`.

- [ ] **Step 3: Create `src/manga_panels/config.py`**

```python
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
```

- [ ] **Step 4: Run tests + commit**

Run: `.venv/bin/pytest tests/test_config.py -q` → PASS (6 passed).
```bash
git add src/manga_panels/config.py tests/test_config.py
git commit -m "feat: manga-panels.toml config (load_config)"
```

---

## Task 4: Rich CLI + deps + config wiring

**Files:**
- Modify: `pyproject.toml`, `src/manga_panels/cli.py`
- Modify test: `tests/test_pipeline.py` (adiciona teste de config)

**Interfaces:**
- Consumes: `process_archive`/`preview_archive` (com `on_page`), `get_detector().warmup()`, `load_config`, `MangaPanelsError`.
- Produces: `cli.main` com Rich (progress/status/tabela/help), `--config`, captura de `MangaPanelsError`.

- [ ] **Step 1: Add deps to `pyproject.toml`**

Troque a linha `dependencies`:
```toml
dependencies = ["pillow>=10", "numpy>=1.24", "rich>=13", "rich-argparse>=1.5"]
```
Run: `uv sync --extra dev` (instala rich/rich-argparse). Expected: instala sem compilar (pure-python).

- [ ] **Step 2: Write the failing config test**

Adicione a `tests/test_pipeline.py`:
```python
def test_cli_config_defaults_applied_and_cli_wins(tmp_path):
    from manga_panels.cli import main
    src = tmp_path / "ch.cbz"
    pack([_grid_page()], src)
    cfg = tmp_path / "manga-panels.toml"
    cfg.write_text('[defaults]\nformat = "png"\n')
    # config seta png; sem flag -> saida png
    out1 = tmp_path / "a.cbz"
    assert main([str(src), "-o", str(out1), "--config", str(cfg)]) == 0
    import zipfile
    with zipfile.ZipFile(out1) as z:
        assert z.namelist()[0].endswith(".png")
    # flag na CLI vence o config
    out2 = tmp_path / "b.cbz"
    assert main([str(src), "-o", str(out2), "--config", str(cfg), "-f", "jpeg"]) == 0
    with zipfile.ZipFile(out2) as z:
        assert z.namelist()[0].endswith(".jpg")
```

- [ ] **Step 3: Run to verify it fails**

Run: `.venv/bin/pytest tests/test_pipeline.py -k config_defaults -q`
Expected: FAIL (`--config` não existe ainda / import de rich falha se não instalado — rode o Step 1 antes).

- [ ] **Step 4: Rewrite `src/manga_panels/cli.py`**

Substitua o arquivo inteiro por:
```python
from __future__ import annotations

import argparse
from pathlib import Path

from rich.console import Console
from rich.progress import (BarColumn, MofNCompleteColumn, Progress, SpinnerColumn,
                           TextColumn, TimeElapsedColumn)
from rich.table import Table
from rich_argparse import RichHelpFormatter

from manga_panels.config import load_config
from manga_panels.detect import get_detector
from manga_panels.errors import MangaPanelsError
from manga_panels.pipeline import process_archive
from manga_panels.preview import preview_archive

_EXTS = {".cbz", ".cbr", ".zip", ".rar"}
console = Console()


def _build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="manga-panels",
        description="Corta paginas de manga em paineis e reempacota como CBZ.",
        formatter_class=RichHelpFormatter,
    )
    ap.add_argument("input", help="arquivo .cbz/.cbr ou pasta com varios")
    ap.add_argument("-o", "--output", help="arquivo ou pasta de saida")
    ap.add_argument("--config", help="TOML de defaults (default: ./manga-panels.toml)")

    g_det = ap.add_argument_group("deteccao")
    g_det.add_argument("-d", "--detector", default="xycut", choices=["xycut", "ml"],
                       help="detector de painel (default xycut)")
    g_det.add_argument("--min-area", type=float, default=0.02,
                       help="fracao minima da area da pagina por painel (default 0.02)")
    g_det.add_argument("--max-ink", type=float, default=0.08,
                       help="(xycut) tolerancia de tinta na sarjeta (default 0.08)")

    g_out = ap.add_argument_group("saida")
    g_out.add_argument("-f", "--format", default="jpeg", choices=["jpeg", "png"],
                       help="encoding das imagens no cbz (default jpeg)")
    g_out.add_argument("-q", "--quality", type=int, default=90,
                       help="qualidade jpeg 1-95 (default 90)")
    g_out.add_argument("-w", "--max-width", type=int, default=None,
                       help="reduz imagens mais largas que N px (default: sem limite)")
    g_out.add_argument("--preview", action="store_true",
                       help="gera <stem>_preview.cbz com os paineis desenhados, sem cortar")

    g_lay = ap.add_argument_group("layout")
    g_lay.add_argument("--ltr", action="store_true", help="leitura esquerda->direita")
    g_lay.add_argument("--page", choices=["before", "after", "off"], default="before",
                       help="posicao da pagina-macro (default before)")
    g_lay.add_argument("-k", "--keep-first", type=int, default=0,
                       help="mantem as primeiras N paginas inteiras")
    return ap


def _jobs(src: Path, output: str | None, suffix: str):
    """Retorna (jobs, erro): lista de (in_path, out_path) ou ([], mensagem)."""
    if src.is_dir():
        out_dir = Path(output) if output else src.with_name(src.name + "_panels")
        files = sorted(p for p in src.iterdir() if p.suffix.lower() in _EXTS)
        if not files:
            return [], f"nenhum arquivo .cbz/.cbr em {src}"
        out_dir.mkdir(parents=True, exist_ok=True)
        jobs, used = [], set()
        for f in files:
            out = out_dir / f"{f.stem}{suffix}"
            if out in used:
                out = out_dir / f"{f.stem}_{f.suffix.lstrip('.')}{suffix}"
            used.add(out)
            jobs.append((f, out))
        return jobs, None
    if not src.exists():
        return [], f"nao encontrado: {src}"
    out = Path(output) if output else src.with_name(f"{src.stem}{suffix}")
    return [(src, out)], None


def _summary(rows) -> Table:
    t = Table(title="resumo", title_style="bold")
    t.add_column("Arquivo")
    t.add_column("Imagens", justify="right")
    t.add_column("Tamanho", justify="right")
    t.add_column("Status", justify="center")
    for name, n, size, ok in rows:
        t.add_row(name, str(n) if ok else "-",
                  f"{size / 1e6:.0f} MB" if size else "-",
                  "[green]OK[/]" if ok else "[red]FALHA[/]")
    return t


def main(argv: list[str] | None = None) -> int:
    # pre-parse do --config pra aplicar defaults antes do parse final
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("--config")
    cfg_arg, _ = pre.parse_known_args(argv)
    ap = _build_parser()
    try:
        cfg = load_config(cfg_arg.config, warn=lambda m: console.print(f"[yellow]{m}[/]"))
    except MangaPanelsError as e:
        console.print(f"[red]erro:[/] {e}")
        return 1
    ap.set_defaults(**cfg)             # config < flag da CLI
    args = ap.parse_args(argv)

    common = dict(detector=args.detector, rtl=not args.ltr, min_frac=args.min_area,
                  max_ink=args.max_ink, fmt=args.format, quality=args.quality,
                  max_width=args.max_width)
    if args.preview:
        run, kw, suffix = preview_archive, common, "_preview.cbz"
    else:
        run = process_archive
        kw = {**common, "page_pos": args.page, "keep_first": args.keep_first}
        suffix = "_panels.cbz"

    jobs, err = _jobs(Path(args.input), args.output, suffix)
    if err:
        console.print(f"[red]{err}[/]")
        return 1

    if args.detector == "ml":          # spinner enquanto carrega o modelo
        try:
            with console.status("[cyan]carregando modelo Magi (1o uso baixa ~1.5GB)..."):
                get_detector("ml").warmup()
        except MangaPanelsError as e:
            console.print(f"[red]erro:[/] {e}")
            return 1

    rows, failed = [], False
    with Progress(SpinnerColumn(), TextColumn("[bold]{task.description}"), BarColumn(),
                  MofNCompleteColumn(), TimeElapsedColumn(), console=console) as progress:
        overall = progress.add_task("volumes", total=len(jobs)) if len(jobs) > 1 else None
        for in_path, out in jobs:
            task = progress.add_task(in_path.name, total=None)

            def on_page(done, total, _t=task):
                progress.update(_t, completed=done, total=total)

            try:
                n = run(in_path, out, on_page=on_page, **kw)
                rows.append((in_path.name, n, out.stat().st_size, True))
            except (MangaPanelsError, ValueError) as e:
                progress.console.print(f"[red]FALHA[/] {in_path.name}: {e}")
                rows.append((in_path.name, 0, 0, False))
                failed = True
            progress.remove_task(task)
            if overall is not None:
                progress.advance(overall)

    console.print(_summary(rows))
    return 1 if failed else 0
```

- [ ] **Step 5: Run the full suite + smoke test**

Run: `.venv/bin/pytest -q && .venv/bin/manga-panels --help`
Expected: todos passam (incluindo `test_cli_config_defaults_applied_and_cli_wins` e os testes de CLI existentes); `--help` sai colorido (rich-argparse) com `--config` e os grupos.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock src/manga_panels/cli.py tests/test_pipeline.py
git commit -m "feat: Rich CLI (progress/spinner/summary/help) + config wiring"
```

---

## Task 5: Docs + uv

**Files:**
- Modify: `README.md`, `CLAUDE.md`

- [ ] **Step 1: Update `README.md`**

Na seção de instalação, adicione o fluxo uv:
```markdown
# rodar como ferramenta sem sujar o ambiente (uv)
uv tool install .            # instala o comando `manga-panels`
uvx --from . manga-panels --help   # ou rodar sem instalar
```
Adicione uma seção **Config**:
```markdown
## Config (opcional)

Pra não repetir flags, crie um `manga-panels.toml` (na pasta atual ou em
`~/.config/manga-panels/config.toml`):

```toml
[defaults]
detector = "ml"
max_width = 1264
quality = 85
page = "before"
```

As chaves são os nomes das flags (`max_width`, `keep_first`, …). Uma flag na
linha de comando sempre vence o config. Ou aponte um arquivo com `--config`.
```

- [ ] **Step 2: Update `CLAUDE.md`**

Adicione `--config` na tabela de flags (após `-o, --output`):
```markdown
| `--config PATH` | `./manga-panels.toml` | TOML `[defaults]` (flag da CLI vence) |
```
E adicione uma seção curta após "Flags":
```markdown
## Saída e erros

- CLI usa **Rich**: barra de progresso (volume + página), spinner no load do
  modelo ML, tabela-resumo no fim. `rich`/`rich-argparse` são deps base.
- Falhas conhecidas levantam `MangaPanelsError` (`errors.py`): `EmptyArchive`,
  `BadArchive`, `MissingDependency`. O CLI captura, imprime a mensagem, e no
  batch segue pros próximos (exit ≠0 se algum falhou).
- Config: `config.py::load_config` lê `manga-panels.toml [defaults]` (chaves =
  dest do argparse); aplicado via `ap.set_defaults` antes do parse.
```

- [ ] **Step 3: Commit**

```bash
git add README.md CLAUDE.md
git commit -m "docs: rich, config, typed errors, uv tool workflow"
```

---

## Self-Review (feita ao escrever)

- **Spec coverage:** erros → Task 1 (errors.py + archive + ml + CLI catch); progresso+warmup → Task 2; config → Task 3; Rich+config-wiring+deps → Task 4; uv+docs → Task 5. Coberto.
- **Placeholders:** nenhum — código completo em cada passo.
- **Type consistency:** `MangaPanelsError`/`EmptyArchive`/`BadArchive`/`MissingDependency` idênticos entre errors/archive/ml/cli/testes; `on_page(feitas,total)` e `warmup()` batem entre pipeline/preview/detect/ml/cli/testes; `load_config(explicit_path, *, warn)` batem entre config/cli/testes; `_jobs`/`_summary` internos ao cli.
- **Acoplamento tratado:** Task 1 muda a exceção do ml E atualiza a captura do CLI E os testes (`test_ml`, `_boom`) juntos — nenhum estado quebrado. Task 4 reescreve o CLI usando o que Tasks 1-3 produziram (errors, on_page/warmup, load_config).
- **Testes Rich:** o CLI usa `console`/`Progress` que degradam fora de tty; os testes de CLI checam rc + arquivo, não o visual — continuam válidos.
