# manga_panels — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Um CLI que pega CBZ/CBR de manga e reempacota cada painel como uma página própria num novo CBZ, pra leitura confortável em telas pequenas.

**Architecture:** Pipeline de 5 estágios (unpack → detect → order → crop → pack). Detecção via protocolo `Detector`: o padrão `XYCutDetector` faz projeção recursiva em numpy (corta nas sarjetas brancas, já em ordem de leitura); `MLDetector` é um stub pluggável pra layouts complexos. Se nenhum painel é detectado, a página inteira vira um painel — nunca perde conteúdo.

**Tech Stack:** Python 3.14, Pillow, numpy, stdlib `zipfile`/`argparse`. `rarfile` opcional pra CBR. Sem OpenCV (sem wheel pra 3.14), sem framework.

## Global Constraints

- Python 3.14; toda dependência precisa de wheel pra cp314 (Pillow, numpy têm; OpenCV não — proibido).
- Trabalhar sempre em imagens `PIL.Image`, nunca caminhos de arquivo, dentro do pipeline.
- `Box = tuple[int, int, int, int]` significando `(x, y, w, h)` em pixels, em TODOS os módulos.
- Leitura padrão RTL (manga); `rtl=True` é o default em toda assinatura que ordena.
- Testes com pytest, `assert` puro, sem fixtures pesadas. Cada task termina com commit.
- CBR degrada com elegância: sem `rarfile`/`unrar`, levanta erro claro só quando o input é `.cbr` — nunca quebra o fluxo CBZ.

---

## File Structure

- `pyproject.toml` — metadata, deps, console_script `manga-panels`.
- `src/manga_panels/__init__.py` — exports públicos.
- `src/manga_panels/archive.py` — `unpack()`, `pack()` (CBZ stdlib, CBR opcional).
- `src/manga_panels/detect.py` — `Box`, `Detector` protocol, `XYCutDetector`, `MLDetector`, `get_detector()`.
- `src/manga_panels/order.py` — `order_boxes()` (agrupa em linhas, ordena RTL/LTR).
- `src/manga_panels/pipeline.py` — `process_archive()` (crop + orquestração).
- `src/manga_panels/cli.py` — `main()` (argparse).
- `tests/test_detect.py`, `tests/test_order.py`, `tests/test_archive.py`, `tests/test_pipeline.py`.

---

## Task 1: Project scaffold + packaging

**Files:**
- Create: `pyproject.toml`
- Create: `src/manga_panels/__init__.py`

**Interfaces:**
- Consumes: nada.
- Produces: pacote instalável `manga_panels`; console_script `manga-panels` apontando pra `manga_panels.cli:main` (implementado na Task 6).

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "manga-panels"
version = "0.1.0"
description = "Corta paginas de manga em paineis e reempacota como CBZ"
requires-python = ">=3.11"
dependencies = ["pillow>=10", "numpy>=1.24"]

[project.optional-dependencies]
cbr = ["rarfile>=4"]
dev = ["pytest>=8"]

[project.scripts]
manga-panels = "manga_panels.cli:main"

[tool.hatch.build.targets.wheel]
packages = ["src/manga_panels"]
```

- [ ] **Step 2: Write `src/manga_panels/__init__.py`**

```python
from manga_panels.detect import Box, Detector, XYCutDetector, MLDetector, get_detector
from manga_panels.pipeline import process_archive

__all__ = [
    "Box", "Detector", "XYCutDetector", "MLDetector", "get_detector",
    "process_archive",
]
```

(Nota: os imports só resolvem depois das Tasks 2–5. Não rode nada ainda; só o arquivo existe.)

- [ ] **Step 3: Create venv and install editable**

Run: `python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"`
Expected: instala sem compilar nada (wheels de pillow/numpy pra cp314). Falha aqui = wheel faltando, pare e reporte.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml src/manga_panels/__init__.py
git commit -m "chore: scaffold manga-panels package"
```

---

## Task 2: Archive unpack/pack (CBZ + CBR opcional)

**Files:**
- Create: `src/manga_panels/archive.py`
- Test: `tests/test_archive.py`

**Interfaces:**
- Consumes: nada.
- Produces:
  - `unpack(path: str | Path) -> list[Image.Image]` — abre `.cbz` (zip) ou `.cbr` (rar), retorna as páginas como imagens PIL RGB, ordenadas por nome de arquivo (natural-ish: zero-padded já ordena bem lexicograficamente). Ignora entradas não-imagem.
  - `pack(images: list[Image.Image], out_path: str | Path) -> None` — escreve um `.cbz` (zip) com PNGs nomeados `0001.png`, `0002.png`, … na ordem da lista.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_archive.py
import zipfile
from pathlib import Path
from PIL import Image
from manga_panels.archive import unpack, pack


def _make_cbz(path: Path, n: int) -> None:
    with zipfile.ZipFile(path, "w") as z:
        for i in range(n):
            img = Image.new("RGB", (10, 10), (i * 10, 0, 0))
            p = path.parent / f"tmp_{i}.png"
            img.save(p)
            z.write(p, f"{i:03d}.png")
            p.unlink()


def test_unpack_reads_pages_in_order(tmp_path):
    cbz = tmp_path / "ch.cbz"
    _make_cbz(cbz, 3)
    pages = unpack(cbz)
    assert len(pages) == 3
    assert pages[0].size == (10, 10)
    assert pages[0].mode == "RGB"


def test_pack_roundtrip(tmp_path):
    imgs = [Image.new("RGB", (8, 8), (0, i * 5, 0)) for i in range(4)]
    out = tmp_path / "out.cbz"
    pack(imgs, out)
    with zipfile.ZipFile(out) as z:
        names = sorted(z.namelist())
    assert names == ["0001.png", "0002.png", "0003.png", "0004.png"]
    assert len(unpack(out)) == 4
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_archive.py -v`
Expected: FAIL com `ModuleNotFoundError: manga_panels.archive`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/manga_panels/archive.py
from __future__ import annotations

import io
import zipfile
from pathlib import Path

from PIL import Image

_IMG_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}


def _is_image(name: str) -> bool:
    return Path(name).suffix.lower() in _IMG_EXT


def unpack(path: str | Path) -> list[Image.Image]:
    path = Path(path)
    ext = path.suffix.lower()
    if ext == ".cbz" or ext == ".zip":
        return _unpack_zip(path)
    if ext == ".cbr" or ext == ".rar":
        return _unpack_rar(path)
    raise ValueError(f"formato nao suportado: {path.suffix}")


def _load(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data)).convert("RGB")


def _unpack_zip(path: Path) -> list[Image.Image]:
    with zipfile.ZipFile(path) as z:
        names = sorted(n for n in z.namelist() if _is_image(n))
        return [_load(z.read(n)) for n in names]


def _unpack_rar(path: Path) -> list[Image.Image]:
    try:
        import rarfile
    except ImportError as e:
        raise RuntimeError(
            "CBR precisa do extra 'cbr': pip install 'manga-panels[cbr]' "
            "e do binario 'unrar' no sistema"
        ) from e
    with rarfile.RarFile(path) as r:
        names = sorted(n for n in r.namelist() if _is_image(n))
        return [_load(r.read(n)) for n in names]


def pack(images: list[Image.Image], out_path: str | Path) -> None:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        for i, img in enumerate(images, start=1):
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            z.writestr(f"{i:04d}.png", buf.getvalue())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_archive.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add src/manga_panels/archive.py tests/test_archive.py
git commit -m "feat: CBZ unpack/pack with optional CBR support"
```

---

## Task 3: XY-cut panel detector

**Files:**
- Create: `src/manga_panels/detect.py`
- Test: `tests/test_detect.py`

**Interfaces:**
- Consumes: nada.
- Produces:
  - `Box = tuple[int, int, int, int]` — `(x, y, w, h)`.
  - `class Detector(Protocol): def detect(self, page: Image.Image) -> list[Box]: ...`
  - `class XYCutDetector` com `__init__(self, bg_thresh: int = 200, min_gutter: int = 8, min_frac: float = 0.02, rtl: bool = True)` e `detect(page) -> list[Box]`. Retorna painéis já em ordem de leitura. Retorna `[]` se não achar nenhum corte (chamador decide o fallback de página inteira).
  - `class MLDetector` com `detect()` que levanta `NotImplementedError`.
  - `get_detector(name: str, *, rtl: bool = True, min_frac: float = 0.02) -> Detector` — `"xycut"` ou `"ml"`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_detect.py
import numpy as np
from PIL import Image
from manga_panels.detect import XYCutDetector, MLDetector, get_detector


def _page_with_grid():
    # pagina branca 200x200 com 4 quadrados pretos (2x2), sarjeta de 20px
    arr = np.full((200, 200), 255, np.uint8)
    for (y, x) in [(20, 20), (20, 120), (120, 20), (120, 120)]:
        arr[y:y + 60, x:x + 60] = 0
    return Image.fromarray(arr, "L").convert("RGB")


def test_detects_four_panels(tmp_path):
    boxes = XYCutDetector().detect(_page_with_grid())
    assert len(boxes) == 4
    for (x, y, w, h) in boxes:
        assert w > 0 and h > 0


def test_reading_order_rtl_top_row_first_and_right_first():
    # RTL: ordem esperada = topo-direita, topo-esquerda, base-direita, base-esquerda
    boxes = XYCutDetector(rtl=True).detect(_page_with_grid())
    centers = [(x + w / 2, y + h / 2) for (x, y, w, h) in boxes]
    # painel 0 fica na metade de cima (y pequeno) e na direita (x grande)
    assert centers[0][1] < 100 and centers[0][0] > 100
    # painel 1 fica em cima e na esquerda
    assert centers[1][1] < 100 and centers[1][0] < 100


def test_blank_page_returns_empty():
    blank = Image.new("RGB", (100, 100), (255, 255, 255))
    assert XYCutDetector().detect(blank) == []


def test_ml_detector_not_implemented():
    import pytest
    with pytest.raises(NotImplementedError):
        MLDetector().detect(Image.new("RGB", (10, 10)))


def test_get_detector_returns_xycut():
    assert isinstance(get_detector("xycut"), XYCutDetector)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_detect.py -v`
Expected: FAIL com `ModuleNotFoundError: manga_panels.detect`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/manga_panels/detect.py
from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np
from PIL import Image

Box = tuple[int, int, int, int]  # (x, y, w, h)


@runtime_checkable
class Detector(Protocol):
    def detect(self, page: Image.Image) -> list[Box]: ...


def _content_segments(is_bg: np.ndarray, min_gutter: int) -> list[tuple[int, int]]:
    """Segmentos de conteudo (start, end) separados por sarjetas (runs de fundo
    com comprimento >= min_gutter). Retorna [] se nao ha corte interno real."""
    L = len(is_bg)
    gutters: list[tuple[int, int]] = []
    run_start: int | None = None
    for i, b in enumerate(is_bg):
        if b:
            if run_start is None:
                run_start = i
        elif run_start is not None:
            if i - run_start >= min_gutter:
                gutters.append((run_start, i))
            run_start = None
    if run_start is not None and L - run_start >= min_gutter:
        gutters.append((run_start, L))
    if not gutters:
        return []
    points = [0]
    for s, e in gutters:
        points += [s, e]
    points.append(L)
    segs = [(a, b) for a, b in zip(points[0::2], points[1::2]) if b > a]
    return segs if len(segs) > 1 else []


class XYCutDetector:
    def __init__(self, bg_thresh: int = 200, min_gutter: int = 8,
                 min_frac: float = 0.02, rtl: bool = True) -> None:
        self.bg_thresh = bg_thresh
        self.min_gutter = min_gutter
        self.min_frac = min_frac
        self.rtl = rtl

    def detect(self, page: Image.Image) -> list[Box]:
        gray = np.asarray(page.convert("L"))
        h, w = gray.shape
        min_area = self.min_frac * h * w
        out: list[Box] = []
        # axis 0 = corta horizontalmente (linhas empilhadas); axis 1 = colunas
        self._recurse(gray, 0, 0, w, h, axis=0, min_area=min_area, out=out)
        return out

    def _recurse(self, gray, x, y, w, h, axis, min_area, out) -> None:
        region = gray[y:y + h, x:x + w]
        ink = region < self.bg_thresh          # True onde tem traco
        # fracao de tinta por linha ao longo do eixo de corte
        line_ink = ink.mean(axis=1 - axis)     # axis0 -> por linha(y); axis1 -> por coluna(x)
        is_bg = line_ink < 0.01
        segs = _content_segments(is_bg, self.min_gutter)
        if not segs:
            other = 1 - axis
            line_ink = ink.mean(axis=1 - other)
            segs = _content_segments(line_ink < 0.01, self.min_gutter)
            if not segs:
                if w * h >= min_area and ink.any():
                    out.append((x, y, w, h))
                return
            axis = other
        if axis == 1 and self.rtl:             # colunas: emitir direita->esquerda
            segs = segs[::-1]
        for s, e in segs:
            if axis == 0:
                self._recurse(gray, x, y + s, w, e - s, 1, min_area, out)
            else:
                self._recurse(gray, x + s, y, e - s, h, 0, min_area, out)


class MLDetector:
    def detect(self, page: Image.Image) -> list[Box]:
        raise NotImplementedError(
            "detector ML ainda nao implementado; use --detector xycut"
        )


def get_detector(name: str, *, rtl: bool = True, min_frac: float = 0.02) -> Detector:
    if name == "xycut":
        return XYCutDetector(rtl=rtl, min_frac=min_frac)
    if name == "ml":
        return MLDetector()
    raise ValueError(f"detector desconhecido: {name!r}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_detect.py -v`
Expected: PASS (5 passed). Se `test_reading_order` falhar, cheque o `segs[::-1]` no eixo 1.

- [ ] **Step 5: Commit**

```bash
git add src/manga_panels/detect.py tests/test_detect.py
git commit -m "feat: XY-cut panel detector with reading-order output"
```

---

## Task 4: Reading-order sort (pro caminho ML)

**Files:**
- Create: `src/manga_panels/order.py`
- Test: `tests/test_order.py`

**Interfaces:**
- Consumes: `Box` de `manga_panels.detect`.
- Produces: `order_boxes(boxes: list[Box], rtl: bool = True) -> list[Box]` — agrupa caixas em linhas por sobreposição vertical, ordena as linhas de cima pra baixo e, dentro da linha, por x (RTL = x decrescente, LTR = crescente). O `XYCutDetector` já sai ordenado; isto existe pra normalizar saídas de detectores que não garantem ordem (o ML futuro).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_order.py
from manga_panels.order import order_boxes


def test_rtl_two_by_two():
    # caixas fora de ordem: (x, y, w, h)
    tl = (0, 0, 40, 40)      # topo-esquerda
    tr = (60, 0, 40, 40)     # topo-direita
    bl = (0, 60, 40, 40)     # base-esquerda
    br = (60, 60, 40, 40)    # base-direita
    boxes = [bl, tr, br, tl]
    assert order_boxes(boxes, rtl=True) == [tr, tl, br, bl]


def test_ltr_two_by_two():
    tl = (0, 0, 40, 40)
    tr = (60, 0, 40, 40)
    boxes = [tr, tl]
    assert order_boxes(boxes, rtl=False) == [tl, tr]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_order.py -v`
Expected: FAIL com `ModuleNotFoundError: manga_panels.order`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/manga_panels/order.py
from __future__ import annotations

from manga_panels.detect import Box


def order_boxes(boxes: list[Box], rtl: bool = True) -> list[Box]:
    if not boxes:
        return []
    # agrupa em linhas: ordena por y (topo), junta caixas que sobrepoem
    # verticalmente com a linha corrente (limiar = metade da altura da 1a caixa)
    by_top = sorted(boxes, key=lambda b: b[1])
    rows: list[list[Box]] = []
    for b in by_top:
        _, y, _, h = b
        cy = y + h / 2
        placed = False
        for row in rows:
            ry, rh = row[0][1], row[0][3]
            if ry <= cy <= ry + rh:            # centro cai dentro da 1a caixa da linha
                row.append(b)
                placed = True
                break
        if not placed:
            rows.append([b])
    ordered: list[Box] = []
    for row in rows:
        row.sort(key=lambda b: b[0], reverse=rtl)   # x decrescente se RTL
        ordered.extend(row)
    return ordered
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_order.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add src/manga_panels/order.py tests/test_order.py
git commit -m "feat: reading-order sort for unordered detectors"
```

---

## Task 5: Pipeline (crop + orquestração ponta-a-ponta)

**Files:**
- Create: `src/manga_panels/pipeline.py`
- Test: `tests/test_pipeline.py`

**Interfaces:**
- Consumes: `unpack`, `pack` (Task 2); `Box`, `Detector`, `get_detector` (Task 3); `order_boxes` (Task 4).
- Produces:
  - `crop_panels(page: Image.Image, boxes: list[Box]) -> list[Image.Image]`.
  - `process_archive(in_path, out_path, *, detector: str = "xycut", rtl: bool = True, min_frac: float = 0.02) -> int` — roda o pipeline inteiro e retorna o número de painéis escritos. Fallback: página sem painéis detectados vira um painel único (a página toda).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pipeline.py
import zipfile
import numpy as np
from pathlib import Path
from PIL import Image
from manga_panels.pipeline import crop_panels, process_archive
from manga_panels.archive import pack


def _grid_page():
    arr = np.full((200, 200), 255, np.uint8)
    for (y, x) in [(20, 20), (20, 120), (120, 20), (120, 120)]:
        arr[y:y + 60, x:x + 60] = 0
    return Image.fromarray(arr, "L").convert("RGB")


def test_crop_returns_subimages():
    page = _grid_page()
    panels = crop_panels(page, [(20, 20, 60, 60), (120, 20, 60, 60)])
    assert [p.size for p in panels] == [(60, 60), (60, 60)]


def test_process_archive_explodes_panels(tmp_path):
    src = tmp_path / "ch.cbz"
    pack([_grid_page()], src)                     # 1 pagina, 4 paineis
    out = tmp_path / "ch_panels.cbz"
    n = process_archive(src, out)
    assert n == 4
    with zipfile.ZipFile(out) as z:
        assert len(z.namelist()) == 4


def test_blank_page_falls_back_to_whole_page(tmp_path):
    src = tmp_path / "blank.cbz"
    pack([Image.new("RGB", (100, 100), (255, 255, 255))], src)
    out = tmp_path / "blank_panels.cbz"
    n = process_archive(src, out)
    assert n == 1                                  # nunca perde a pagina
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_pipeline.py -v`
Expected: FAIL com `ModuleNotFoundError: manga_panels.pipeline`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/manga_panels/pipeline.py
from __future__ import annotations

from pathlib import Path

from PIL import Image

from manga_panels.archive import pack, unpack
from manga_panels.detect import Box, get_detector
from manga_panels.order import order_boxes


def crop_panels(page: Image.Image, boxes: list[Box]) -> list[Image.Image]:
    return [page.crop((x, y, x + w, y + h)) for (x, y, w, h) in boxes]


def process_archive(in_path, out_path, *, detector: str = "xycut",
                    rtl: bool = True, min_frac: float = 0.02) -> int:
    det = get_detector(detector, rtl=rtl, min_frac=min_frac)
    pages = unpack(in_path)
    panels: list[Image.Image] = []
    for page in pages:
        boxes = det.detect(page)
        if not boxes:                              # fallback: pagina inteira
            boxes = [(0, 0, page.width, page.height)]
        else:
            boxes = order_boxes(boxes, rtl=rtl)
        panels.extend(crop_panels(page, boxes))
    pack(panels, out_path)
    return len(panels)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_pipeline.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add src/manga_panels/pipeline.py tests/test_pipeline.py
git commit -m "feat: end-to-end pipeline with whole-page fallback"
```

---

## Task 6: CLI

**Files:**
- Create: `src/manga_panels/cli.py`

**Interfaces:**
- Consumes: `process_archive` (Task 5).
- Produces: `main(argv: list[str] | None = None) -> int` — parse de args, roda um arquivo ou batch de uma pasta, imprime progresso. Console_script `manga-panels` (já registrado na Task 1).
  - Uso: `manga-panels INPUT [-o OUTPUT] [--ltr] [--detector xycut|ml] [--min-area FLOAT]`
  - `INPUT` arquivo → gera `OUTPUT` (default `<stem>_panels.cbz` ao lado).
  - `INPUT` pasta → processa todo `.cbz`/`.cbr` dentro; `-o` é a pasta de saída (default `<pasta>_panels/`).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pipeline.py  (append)
def test_cli_processes_folder(tmp_path):
    from manga_panels.cli import main
    from manga_panels.archive import pack
    src_dir = tmp_path / "chapters"
    src_dir.mkdir()
    pack([_grid_page()], src_dir / "c1.cbz")
    out_dir = tmp_path / "out"
    rc = main([str(src_dir), "-o", str(out_dir)])
    assert rc == 0
    assert (out_dir / "c1_panels.cbz").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_pipeline.py::test_cli_processes_folder -v`
Expected: FAIL com `ModuleNotFoundError: manga_panels.cli`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/manga_panels/cli.py
from __future__ import annotations

import argparse
from pathlib import Path

from manga_panels.pipeline import process_archive

_EXTS = {".cbz", ".cbr", ".zip", ".rar"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="manga-panels",
        description="Corta paginas de manga em paineis e reempacota como CBZ.",
    )
    ap.add_argument("input", help="arquivo .cbz/.cbr ou pasta com varios")
    ap.add_argument("-o", "--output", help="arquivo ou pasta de saida")
    ap.add_argument("--ltr", action="store_true", help="leitura esquerda->direita")
    ap.add_argument("--detector", default="xycut", choices=["xycut", "ml"])
    ap.add_argument("--min-area", type=float, default=0.02,
                    help="fracao minima da area da pagina por painel (default 0.02)")
    args = ap.parse_args(argv)

    rtl = not args.ltr
    src = Path(args.input)
    kw = dict(detector=args.detector, rtl=rtl, min_frac=args.min_area)

    if src.is_dir():
        out_dir = Path(args.output) if args.output else src.with_name(src.name + "_panels")
        out_dir.mkdir(parents=True, exist_ok=True)
        files = sorted(p for p in src.iterdir() if p.suffix.lower() in _EXTS)
        if not files:
            print(f"nenhum arquivo .cbz/.cbr em {src}")
            return 1
        for f in files:
            out = out_dir / f"{f.stem}_panels.cbz"
            n = process_archive(f, out, **kw)
            print(f"{f.name}: {n} paineis -> {out.name}")
        return 0

    if not src.exists():
        print(f"nao encontrado: {src}")
        return 1
    out = Path(args.output) if args.output else src.with_name(f"{src.stem}_panels.cbz")
    n = process_archive(src, out, **kw)
    print(f"{src.name}: {n} paineis -> {out}")
    return 0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_pipeline.py::test_cli_processes_folder -v`
Expected: PASS.

- [ ] **Step 5: Full suite + smoke test the console script**

Run: `.venv/bin/pytest -q && .venv/bin/manga-panels --help`
Expected: todos os testes passam; `--help` imprime o uso.

- [ ] **Step 6: Commit**

```bash
git add src/manga_panels/cli.py tests/test_pipeline.py
git commit -m "feat: CLI for single-file and batch folder processing"
```

---

## Task 7: README + calibração

**Files:**
- Create: `README.md`

**Interfaces:**
- Consumes: tudo.
- Produces: doc de uso. Nada de código novo.

- [ ] **Step 1: Write `README.md`**

````markdown
# manga_panels

Corta páginas de manga (CBZ/CBR) em painéis e reempacota como CBZ — um painel
por página, pra ler confortável em tela pequena.

## Instalar

```bash
python3 -m venv .venv && .venv/bin/pip install -e .
# CBR (opcional): precisa do binario 'unrar' no sistema
.venv/bin/pip install -e ".[cbr]"
```

## Usar

```bash
# um arquivo
manga-panels capitulo.cbz                 # gera capitulo_panels.cbz
manga-panels capitulo.cbz -o saida.cbz

# uma pasta inteira (batch)
manga-panels ./capitulos -o ./saida

# manga ocidental (esquerda->direita)
manga-panels capitulo.cbz --ltr
```

## Calibração

Scans reais têm ruído, sarjetas acinzentadas e JPEG artifacts. Se o corte
sair errado, ajuste:

- `--min-area 0.02` — sobe pra descartar painéis-fantasma pequenos; desce se
  painéis legítimos sumirem.
- Detector: `--detector xycut` (padrão, P&B com sarjeta limpa). `--detector ml`
  é um stub — layouts sangrados/coloridos ainda não são suportados.

Se um capítulo sai como uma página inteira só, ele não tinha sarjetas
detectáveis: caso pro futuro detector ML.
````

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: usage and calibration guide"
```

---

## Self-Review (feita ao escrever)

- **Spec coverage:** unpack/detect/order/crop/pack → Tasks 2–5; CLI + flags (`--ltr`, `--detector`, `--min-area`) → Task 6; bordas (página inteira no fallback, min-area) → Tasks 3/5; CBR opcional → Task 2; verificação (página sintética + CBZ de 1 página ponta-a-ponta) → Tasks 3/5. Coberto.
- **Placeholders:** nenhum — todo passo tem código/comando real.
- **Type consistency:** `Box=(x,y,w,h)` e `detect(page)->list[Box]` idênticos em detect/order/pipeline; `process_archive(...)->int`; `get_detector(name,*,rtl,min_frac)` chamado com os mesmos kwargs no pipeline. OK.
- **Desvio do spec (registrado):** detector clássico é XY-cut em numpy, não Kumiko/OpenCV — OpenCV não tem wheel pra cp314 e Kumiko é GPL/não-pip. Mesmo método (projeção/sarjeta), mesma interface, mesmo resultado.
