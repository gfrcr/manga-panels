# CLI Flags + Preview — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Arrumar/expandir as flags do CLI (aliases, grupos, `--page` enum, `--keep-first`), consertar o bug da capa duplicada, e adicionar `--preview`.

**Architecture:** Muda `process_archive` (dedup ≤1 painel, `page_pos`, `keep_first`); adiciona `preview.py` (anota páginas sem cortar); reescreve o argparse do `cli.py` com grupos/aliases e roteia `--preview` pro `preview_archive`.

**Tech Stack:** Python 3.14, Pillow, argparse. Sem deps novas.

## Global Constraints

- `Box = tuple[int,int,int,int]` = (x,y,w,h). Detectores já devolvem em ordem de leitura; o pipeline não re-ordena.
- Página com **≤1 painel detectado → emite a página inteira uma vez** (sem macro/crop).
- `--page {before,after,off}` default `before`. `--keep-first N` default `0`. RTL default.
- Aliases: `-o`, `-d --detector`, `-f --format`, `-q --quality`, `-w --max-width`, `-k --keep-first`. Sem alias curto pra `--ltr/--min-area/--max-ink/--page/--preview`.
- `--preview` → `<stem>_preview.cbz`, respeita `--format/--quality/--max-width`, mostra detecção crua (ignora `--page`/`--keep-first`).
- pytest, plain assert, testes ML gated (não afetados aqui). Cada task termina com commit.

---

## File Structure

- `src/manga_panels/pipeline.py` (modificar) — `process_archive`: `include_page:bool` → `page_pos:str`, +`keep_first:int`, dedup ≤1 painel.
- `src/manga_panels/preview.py` (novo) — `annotate_page`, `preview_archive`.
- `src/manga_panels/cli.py` (modificar) — grupos, aliases, `--page` enum, `-k`, `--preview` roteamento.
- `tests/test_pipeline.py` (modificar), `tests/test_preview.py` (novo), `tests/test_cli.py` (novo, se necessário — senão dentro de test_pipeline).

---

## Task 1: Pipeline (dedup + page_pos + keep_first) + CLI flags

**Files:**
- Modify: `src/manga_panels/pipeline.py`
- Modify: `src/manga_panels/cli.py`
- Modify: `tests/test_pipeline.py`

**Interfaces:**
- Consumes: `unpack`, `pack` (archive), `Box`, `get_detector` (detect).
- Produces:
  - `process_archive(in_path, out_path, *, detector="xycut", rtl=True, min_frac=0.02, max_ink=0.08, fmt="jpeg", quality=90, page_pos="before", max_width=None, keep_first=0) -> int`
  - `cli.main(argv=None) -> int` com as flags novas (grupos, aliases, `--page` enum, `-k/--keep-first`).

- [ ] **Step 1: Update the pipeline tests (write the new expectations first)**

Em `tests/test_pipeline.py`, TROQUE as chamadas antigas que usam `include_page` e ADICIONE os testes novos. Substitua as 3 funções existentes abaixo e adicione as 4 novas:

```python
def test_process_archive_explodes_panels(tmp_path):
    src = tmp_path / "ch.cbz"
    pack([_grid_page()], src)                     # 1 pagina, 4 paineis
    out = tmp_path / "ch_panels.cbz"
    n = process_archive(src, out, page_pos="off")
    assert n == 4
    with zipfile.ZipFile(out) as z:
        assert len(z.namelist()) == 4


def test_process_archive_prepends_full_page(tmp_path):
    src = tmp_path / "ch.cbz"
    pack([_grid_page()], src)                     # 1 pagina 200x200, 4 paineis
    out = tmp_path / "ch_panels.cbz"
    n = process_archive(src, out)                 # page_pos default = before
    assert n == 5                                 # pagina cheia + 4 paineis
    imgs = unpack(out)
    assert imgs[0].size == (200, 200)             # macro primeiro
    assert all(im.size != (200, 200) for im in imgs[1:])


def test_include_page_not_duplicated_when_whole_page(tmp_path):
    src = tmp_path / "blank.cbz"
    pack([Image.new("RGB", (100, 100), (255, 255, 255))], src)
    out = tmp_path / "out.cbz"
    assert process_archive(src, out) == 1         # 0 paineis -> pagina uma vez


def _single_panel_page():
    # pagina branca com UM retangulo preto sem sarjeta interna -> 1 painel
    arr = np.full((200, 200), 255, np.uint8)
    arr[40:160, 40:160] = 0
    return Image.fromarray(arr, "L").convert("RGB")


def test_single_panel_page_emitted_once(tmp_path):
    src = tmp_path / "sp.cbz"
    pack([_single_panel_page()], src)
    out = tmp_path / "out.cbz"
    assert process_archive(src, out) == 1         # 1 painel ~ pagina -> nao duplica


def test_page_pos_after_puts_macro_last(tmp_path):
    src = tmp_path / "ch.cbz"
    pack([_grid_page()], src)
    out = tmp_path / "out.cbz"
    n = process_archive(src, out, page_pos="after")
    assert n == 5
    imgs = unpack(out)
    assert imgs[-1].size == (200, 200)            # macro por ultimo
    assert imgs[0].size != (200, 200)             # painel primeiro


def test_keep_first_keeps_pages_whole(tmp_path):
    src = tmp_path / "ch.cbz"
    pack([_grid_page(), _grid_page()], src)       # 2 paginas de 4 paineis
    out = tmp_path / "out.cbz"
    n = process_archive(src, out, keep_first=1)   # 1a inteira, 2a cortada
    assert n == 6                                 # 1 (inteira) + 5 (macro+4)
    imgs = unpack(out)
    assert imgs[0].size == (200, 200)             # 1a pagina inteira, sem cortar
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/pytest tests/test_pipeline.py -q`
Expected: FAIL (process_archive ainda tem `include_page`, sem `page_pos`/`keep_first`; `TypeError`/`AssertionError`).

- [ ] **Step 3: Rewrite `process_archive` in `pipeline.py`**

Substitua a função inteira (mantendo `crop_panels` e os imports):

```python
def process_archive(in_path, out_path, *, detector: str = "xycut",
                    rtl: bool = True, min_frac: float = 0.02,
                    max_ink: float = 0.08, fmt: str = "jpeg",
                    quality: int = 90, page_pos: str = "before",
                    max_width: int | None = None, keep_first: int = 0) -> int:
    """Explode cada pagina em paineis num CBZ novo. Retorna o total de imagens
    escritas.
    - keep_first: as primeiras N paginas ficam inteiras (capa/miolo inicial).
    - Pagina com <=1 painel (capa/splash/sem sarjeta) e emitida uma vez so.
    - page_pos: 'before' (macro antes dos paineis), 'after', ou 'off'."""
    det = get_detector(detector, rtl=rtl, min_frac=min_frac, max_ink=max_ink)
    pages = unpack(in_path)
    out_imgs: list[Image.Image] = []
    for i, page in enumerate(pages):
        if i < keep_first:                         # front-matter inteiro
            out_imgs.append(page)
            continue
        boxes = det.detect(page)                   # ja vem em ordem de leitura
        if len(boxes) <= 1:                        # capa/splash/fallback -> uma vez
            out_imgs.append(page)
            continue
        if page_pos == "before":
            out_imgs.append(page)
        out_imgs.extend(crop_panels(page, boxes))
        if page_pos == "after":
            out_imgs.append(page)
    pack(out_imgs, out_path, fmt=fmt, quality=quality, max_width=max_width)
    return len(out_imgs)
```

- [ ] **Step 4: Rewrite `cli.py` with groups, aliases, `--page` enum, `-k`**

Substitua o arquivo `src/manga_panels/cli.py` inteiro por:

```python
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

    g_det = ap.add_argument_group("deteccao")
    g_det.add_argument("-d", "--detector", default="xycut", choices=["xycut", "ml"],
                       help="detector de painel (default xycut)")
    g_det.add_argument("--min-area", type=float, default=0.02,
                       help="fracao minima da area da pagina por painel (default 0.02)")
    g_det.add_argument("--max-ink", type=float, default=0.08,
                       help="(xycut) tolerancia de tinta na sarjeta: maior corta mais "
                            "paineis, menor e mais conservador (default 0.08)")

    g_out = ap.add_argument_group("saida")
    g_out.add_argument("-f", "--format", default="jpeg", choices=["jpeg", "png"],
                       help="encoding das imagens no cbz (default jpeg)")
    g_out.add_argument("-q", "--quality", type=int, default=90,
                       help="qualidade jpeg 1-95, maior=maior arquivo (default 90)")
    g_out.add_argument("-w", "--max-width", type=int, default=None,
                       help="reduz imagens mais largas que N px (mantem proporcao, "
                            "nunca amplia); ex. 1264. Default: sem limite")

    g_lay = ap.add_argument_group("layout")
    g_lay.add_argument("--ltr", action="store_true", help="leitura esquerda->direita")
    g_lay.add_argument("--page", choices=["before", "after", "off"], default="before",
                       help="onde a pagina inteira (macro) entra: antes/depois dos "
                            "paineis, ou off (default before)")
    g_lay.add_argument("-k", "--keep-first", type=int, default=0,
                       help="mantem as primeiras N paginas inteiras (capa/miolo inicial)")

    args = ap.parse_args(argv)

    rtl = not args.ltr
    src = Path(args.input)
    kw = dict(detector=args.detector, rtl=rtl, min_frac=args.min_area,
              max_ink=args.max_ink, fmt=args.format, quality=args.quality,
              max_width=args.max_width, page_pos=args.page, keep_first=args.keep_first)
    suffix = "_panels.cbz"

    if src.is_dir():
        out_dir = Path(args.output) if args.output else src.with_name(src.name + "_panels")
        files = sorted(p for p in src.iterdir() if p.suffix.lower() in _EXTS)
        if not files:
            print(f"nenhum arquivo .cbz/.cbr em {src}")
            return 1
        out_dir.mkdir(parents=True, exist_ok=True)
        used: set[Path] = set()
        failed = False
        for f in files:
            out = out_dir / f"{f.stem}{suffix}"
            if out in used:
                out = out_dir / f"{f.stem}_{f.suffix.lstrip('.')}{suffix}"
            used.add(out)
            try:
                n = process_archive(f, out, **kw)
            except (NotImplementedError, RuntimeError, ValueError) as e:
                print(f"{f.name}: erro -> {e}")
                failed = True
                continue
            print(f"{f.name}: {n} imagens -> {out.name}")
        return 1 if failed else 0

    if not src.exists():
        print(f"nao encontrado: {src}")
        return 1
    out = Path(args.output) if args.output else src.with_name(f"{src.stem}{suffix}")
    try:
        n = process_archive(src, out, **kw)
    except (NotImplementedError, RuntimeError, ValueError) as e:
        print(f"{src.name}: erro -> {e}")
        return 1
    print(f"{src.name}: {n} imagens -> {out}")
    return 0
```

- [ ] **Step 5: Run the full suite**

Run: `.venv/bin/pytest -q`
Expected: PASS. Os testes de pipeline atualizados passam; `test_cli_same_stem_different_ext_no_overwrite` continua verde (grid=4 paineis, page_pos before → 5 imagens; ele afirma `len(z.namelist()) == 5`). `manga-panels --help` mostra os grupos.

- [ ] **Step 6: Smoke-test the CLI aliases**

Run: `.venv/bin/manga-panels --help`
Expected: aparece `-d`, `-f`, `-q`, `-w`, `-k`, `--page {before,after,off}`, e os grupos `deteccao`/`saida`/`layout`.

- [ ] **Step 7: Commit**

```bash
git add src/manga_panels/pipeline.py src/manga_panels/cli.py tests/test_pipeline.py
git commit -m "feat: page_pos/keep-first/single-panel dedup + CLI flag cleanup"
```

---

## Task 2: Preview mode

**Files:**
- Create: `src/manga_panels/preview.py`
- Create: `tests/test_preview.py`
- Modify: `src/manga_panels/cli.py`

**Interfaces:**
- Consumes: `unpack`, `pack` (archive); `Box`, `get_detector` (detect).
- Produces:
  - `annotate_page(page: Image.Image, boxes: list[Box]) -> Image.Image` — cópia da página com os painéis desenhados (retângulo + número na ordem de leitura). Não altera a original.
  - `preview_archive(in_path, out_path, *, detector="xycut", rtl=True, min_frac=0.02, max_ink=0.08, fmt="jpeg", quality=90, max_width=None) -> int` — anota cada página, escreve o CBZ, retorna nº de páginas.
  - CLI: `--preview` → roteia pra `preview_archive`, sufixo `_preview.cbz`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_preview.py
import zipfile
import numpy as np
from PIL import Image
from manga_panels.preview import annotate_page, preview_archive
from manga_panels.detect import XYCutDetector
from manga_panels.archive import pack, unpack


def _grid_page():
    arr = np.full((200, 200), 255, np.uint8)
    for (y, x) in [(20, 20), (20, 120), (120, 20), (120, 120)]:
        arr[y:y + 60, x:x + 60] = 0
    return Image.fromarray(arr, "L").convert("RGB")


def test_annotate_page_same_size_and_original_untouched():
    page = _grid_page()
    before = list(page.getdata())
    boxes = XYCutDetector().detect(page)
    out = annotate_page(page, boxes)
    assert out.size == page.size
    assert list(page.getdata()) == before          # original intacta
    assert list(out.getdata()) != before           # anotou algo (desenhou caixas)


def test_annotate_page_no_boxes_returns_same_size():
    page = Image.new("RGB", (80, 80), (255, 255, 255))
    out = annotate_page(page, [])
    assert out.size == (80, 80)


def test_preview_archive_page_count(tmp_path):
    src = tmp_path / "ch.cbz"
    pack([_grid_page(), _grid_page()], src)         # 2 paginas
    out = tmp_path / "ch_preview.cbz"
    n = preview_archive(src, out)
    assert n == 2                                    # 1 imagem anotada por pagina
    with zipfile.ZipFile(out) as z:
        assert len(z.namelist()) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_preview.py -q`
Expected: FAIL com `ModuleNotFoundError: manga_panels.preview`.

- [ ] **Step 3: Create `src/manga_panels/preview.py`**

```python
"""Modo preview: anota cada pagina com os paineis desenhados (sem cortar),
pra calibrar antes de processar o volume."""
from __future__ import annotations

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
                    quality: int = 90, max_width: int | None = None) -> int:
    det = get_detector(detector, rtl=rtl, min_frac=min_frac, max_ink=max_ink)
    pages = unpack(in_path)
    out = [annotate_page(p, det.detect(p)) for p in pages]
    pack(out, out_path, fmt=fmt, quality=quality, max_width=max_width)
    return len(out)
```

- [ ] **Step 4: Run preview tests to verify they pass**

Run: `.venv/bin/pytest tests/test_preview.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Wire `--preview` into `cli.py`**

Faça 3 edições em `src/manga_panels/cli.py`:

(a) Import — troque a linha de import por:
```python
from manga_panels.pipeline import process_archive
from manga_panels.preview import preview_archive
```

(b) No grupo `g_out`, adicione a flag `--preview` (depois de `--max-width`):
```python
    g_out.add_argument("--preview", action="store_true",
                       help="gera <stem>_preview.cbz com os paineis desenhados, "
                            "sem cortar (pra calibrar)")
```

(c) Troque o bloco que monta `kw`/`suffix` (as linhas de `rtl = not args.ltr` até `suffix = "_panels.cbz"`) por:
```python
    rtl = not args.ltr
    src = Path(args.input)
    common = dict(detector=args.detector, rtl=rtl, min_frac=args.min_area,
                  max_ink=args.max_ink, fmt=args.format, quality=args.quality,
                  max_width=args.max_width)
    if args.preview:
        run = preview_archive
        kw = common
        suffix = "_preview.cbz"
    else:
        run = process_archive
        kw = {**common, "page_pos": args.page, "keep_first": args.keep_first}
        suffix = "_panels.cbz"
```

(d) Nas DUAS chamadas `process_archive(f, out, **kw)` e `process_archive(src, out, **kw)`, troque `process_archive` por `run`.

- [ ] **Step 6: Add a CLI preview test to `tests/test_pipeline.py`**

```python
def test_cli_preview_writes_preview_cbz(tmp_path):
    from manga_panels.cli import main
    src = tmp_path / "ch.cbz"
    pack([_grid_page()], src)
    rc = main([str(src), "--preview"])
    assert rc == 0
    assert (tmp_path / "ch_preview.cbz").exists()
    assert not (tmp_path / "ch_panels.cbz").exists()
```

- [ ] **Step 7: Run the full suite + smoke test**

Run: `.venv/bin/pytest -q && .venv/bin/manga-panels --help`
Expected: tudo passa; `--preview` aparece no grupo `saida` do help.

- [ ] **Step 8: Commit**

```bash
git add src/manga_panels/preview.py tests/test_preview.py src/manga_panels/cli.py tests/test_pipeline.py
git commit -m "feat: --preview mode (annotated CBZ for calibration)"
```

---

## Task 3: Docs

**Files:**
- Modify: `README.md`
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: tudo. Sem código novo.

- [ ] **Step 1: Update `README.md`**

Na seção de uso, adicione exemplos das flags novas (depois do exemplo `--detector ml`):
```markdown
# preview: confere os cortes antes de processar (gera capitulo_preview.cbz)
manga-panels capitulo.cbz --detector ml --preview

# mantem as 2 primeiras paginas inteiras (capa/folha de rosto) e macro depois dos paineis
manga-panels capitulo.cbz -k 2 --page after
```

E na Calibração, adicione um bullet:
```markdown
- `--preview` gera um CBZ com os paineis desenhados e numerados (ordem de
  leitura) em vez de cortar — abra no leitor pra conferir antes do volume todo.
- `--keep-first N` mantem as primeiras N paginas inteiras (capa/miolo). Capas e
  splashes ja saem inteiras sozinhas (detector devolve <=1 painel).
- `--page before|after|off` controla onde a pagina-macro entra.
```

- [ ] **Step 2: Update `CLAUDE.md`**

Na tabela de flags, troque a linha do `--page` e adicione `--keep-first`/`--preview`, e acrescente os aliases curtos (`-d -f -q -w -k`) nas linhas correspondentes. Substitua a tabela de flags inteira por:

```markdown
| Flag | Default | O que faz |
|---|---|---|
| `-o, --output` | `<stem>_panels.cbz` | arquivo ou pasta de saída |
| `--ltr` | off (RTL) | leitura esquerda→direita |
| `-d, --detector {xycut,ml}` | `xycut` | detector de painel |
| `--min-area FLOAT` | `0.02` | fração mínima da área por painel |
| `--max-ink FLOAT` | `0.08` | (xycut) tolerância de sarjeta |
| `-f, --format {jpeg,png}` | `jpeg` | encoding no CBZ |
| `-q, --quality INT` | `90` | qualidade JPEG |
| `-w, --max-width INT` | sem limite | reduz largura (ex. 1264) |
| `--page {before,after,off}` | `before` | posição da página-macro |
| `-k, --keep-first INT` | `0` | mantém as primeiras N páginas inteiras |
| `--preview` | off | gera `<stem>_preview.cbz` anotado, sem cortar |
```

E adicione uma linha na seção de fluxo: "Página com ≤1 painel (capa/splash) é
emitida uma vez só (sem duplicar a macro)."

- [ ] **Step 3: Commit**

```bash
git add README.md CLAUDE.md
git commit -m "docs: document preview, keep-first, page position, flag aliases"
```

---

## Self-Review (feita ao escrever)

- **Spec coverage:** A (dedup ≤1) → Task 1 pipeline + teste `test_single_panel_page_emitted_once`; B (keep-first) → Task 1 + `-k` flag + teste; C (page_pos) → Task 1 + `--page` enum + testes after/off; D (preview) → Task 2 (preview.py + `--preview`); E (aliases/grupos) → Task 1 cli.py. Docs → Task 3. Coberto.
- **Placeholders:** nenhum — código completo em cada passo.
- **Type consistency:** `process_archive(..., page_pos, keep_first)` idêntico entre pipeline, cli e testes; `annotate_page(page, boxes)`, `preview_archive(...)` batem entre preview.py, cli e testes; `_grid_page()` reusado; `unpack`/`pack` já existem.
- **Ordem:** Task 1 muda a assinatura de `process_archive` E o cli.py juntos (acoplados) — nenhum estado intermediário quebrado. Task 2 adiciona `--preview` por cima do cli.py da Task 1.
