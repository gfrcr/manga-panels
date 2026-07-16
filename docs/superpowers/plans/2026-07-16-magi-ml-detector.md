# Magi v2 ML Detector — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar `--detector ml` de verdade com o Magi v2 (detecção de painéis treinada em Manga109), rodando na GPU, devolvendo caixas já em ordem de leitura.

**Architecture:** `MagiDetector` (novo, em `ml.py`) implementa o mesmo protocolo `Detector`. Todo código torch/transformers fica isolado em `ml.py` com imports lazy, então o base install (só xycut) continua leve. O pipeline já confia na ordem do detector, e o Magi já ordena os painéis internamente — nada de `order_boxes` no caminho ML. `xycut` continua o default; ML é opt-in via extra `[ml]` gerenciado por uv.

**Tech Stack:** Python 3.14, torch (cp314, CUDA), transformers (`trust_remote_code`), Magi v2 (`ragavsachdeva/magiv2`), uv pra deps.

## Global Constraints

- Detector protocolo: `detect(page: PIL.Image) -> list[Box]`, `Box = (x, y, w, h)` int pixels, em ordem de leitura.
- `xycut` é o default; ML nunca é obrigatório pro base install.
- Todo import de torch/transformers é LAZY (dentro de função/método), nunca no topo de `ml.py`.
- Modelo: `ragavsachdeva/magiv2`, `AutoModel.from_pretrained(..., trust_remote_code=True)`.
- API de inferência: `model.predict_detections_and_associations([np_rgb_array])` → `list[dict]`; `dict["panels"]` = lista de `[x1, y1, x2, y2]` em pixels absolutos, JÁ em ordem de leitura.
- Entrada do modelo: `np.array(page.convert("L").convert("RGB"))` (grayscale→RGB, como no treino).
- pytest, plain assert. Testes que baixam o modelo ficam atrás do marker `ml` e NÃO rodam no `pytest` normal.
- Deps do extra `[ml]`: `torch, transformers, einops, matplotlib, networkx, pulp, scipy, shapely`.

---

## File Structure

- `pyproject.toml` — extra `[ml]`, marker pytest `ml`, `addopts` excluindo `ml` por default.
- `src/manga_panels/ml.py` (novo) — `MagiDetector`, `_load_magi()` (singleton), `_panels_to_boxes()`. Único arquivo com torch/transformers.
- `src/manga_panels/detect.py` (modificar) — remove `MLDetector` stub; `get_detector("ml")` importa `ml.MagiDetector` lazy.
- `src/manga_panels/__init__.py` (modificar) — remove export de `MLDetector`.
- `tests/test_ml.py` (novo) — unit (mock, sem torch) + gated integração.
- `tests/test_detect.py` (modificar) — remove `test_ml_detector_not_implemented`.
- `README.md` (modificar) — `--detector ml` + `uv sync --extra ml`.

---

## Task 1: Extra `[ml]` + pytest marker + instalação via uv

**Files:**
- Modify: `pyproject.toml`

**Interfaces:**
- Consumes: nada.
- Produces: extra instalável `manga-panels[ml]`; marker pytest `ml` registrado e excluído por default.

- [ ] **Step 1: Add the `[ml]` extra and pytest config to `pyproject.toml`**

Adicione o extra em `[project.optional-dependencies]` (já existe a seção com `cbr` e `dev`):

```toml
[project.optional-dependencies]
cbr = ["rarfile>=4"]
dev = ["pytest>=8"]
ml = [
    "torch>=2.3",
    "transformers>=4.40",
    "einops",
    "matplotlib",
    "networkx",
    "pulp",
    "scipy",
    "shapely",
]
```

E adicione no fim do arquivo:

```toml
[tool.pytest.ini_options]
markers = [
    "ml: integracao que precisa do extra [ml] e baixa o modelo Magi (~1.5GB); nao roda por default",
]
addopts = "-m 'not ml'"
```

- [ ] **Step 2: Sync the ml extra with uv**

Run: `uv sync --extra ml --extra dev`
Expected: resolve e instala torch (wheel cp314 CUDA), transformers, etc.; atualiza `uv.lock`. Sem compilar nada.

- [ ] **Step 3: Verify torch sees the GPU**

Run: `.venv/bin/python -c "import torch, transformers; print('cuda:', torch.cuda.is_available())"`
Expected: imprime `cuda: True`. Se `False`: o wheel default não trouxe CUDA — adicione o índice CUDA e re-sync:

```toml
[[tool.uv.index]]
name = "pytorch-cu124"
url = "https://download.pytorch.org/whl/cu124"
explicit = true

[tool.uv.sources]
torch = { index = "pytorch-cu124" }
```
Então `uv sync --extra ml --extra dev` de novo e repita a verificação até `cuda: True`.

- [ ] **Step 4: Confirm the default test run still excludes ml**

Run: `.venv/bin/pytest -q`
Expected: os 23 testes atuais passam; nenhum teste `ml` roda (addopts exclui). Nenhum download de modelo.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore: add optional [ml] extra (torch+transformers+magi deps)"
```

---

## Task 2: `MagiDetector` + conversão + wiring

**Files:**
- Create: `src/manga_panels/ml.py`
- Modify: `src/manga_panels/detect.py`
- Modify: `src/manga_panels/__init__.py`
- Create: `tests/test_ml.py`
- Modify: `tests/test_detect.py`

**Interfaces:**
- Consumes: `Box` de `manga_panels.detect`; extra `[ml]` (Task 1) em runtime.
- Produces:
  - `_panels_to_boxes(panels, page_w: int, page_h: int) -> list[Box]` — converte a saída `[x1,y1,x2,y2]` do Magi (ordem preservada) pra `(x,y,w,h)` int, clampada na página, descartando degenerados.
  - `_load_magi()` — singleton do modelo; lazy import de torch/transformers; `RuntimeError` acionável se ausentes.
  - `MagiDetector.detect(page: PIL.Image) -> list[Box]` — roda o Magi e devolve caixas em ordem de leitura.
  - `get_detector("ml")` retorna `MagiDetector()` (não precisa de torch pra construir).

- [ ] **Step 1: Write the failing unit tests (no torch needed)**

```python
# tests/test_ml.py
import sys
import pytest
from PIL import Image
from manga_panels.ml import _panels_to_boxes
from manga_panels.detect import get_detector
import manga_panels.ml as ml


def test_panels_to_boxes_converts_xyxy_to_xywh():
    # Magi devolve [x1,y1,x2,y2] em pixels, ja em ordem de leitura
    panels = [[10.0, 20.0, 110.0, 220.0], [0.0, 0.0, 50.0, 50.0]]
    assert _panels_to_boxes(panels, 200, 300) == [(10, 20, 100, 200), (0, 0, 50, 50)]


def test_panels_to_boxes_preserves_magi_order():
    panels = [[100, 0, 150, 50], [0, 0, 50, 50]]   # nao reordena
    assert _panels_to_boxes(panels, 200, 200) == [(100, 0, 50, 50), (0, 0, 50, 50)]


def test_panels_to_boxes_clamps_and_drops_degenerate():
    panels = [[-5.0, -5.0, 300.0, 400.0], [10.0, 10.0, 10.0, 50.0]]  # 2o tem w=0
    assert _panels_to_boxes(panels, 200, 300) == [(0, 0, 200, 300)]


def test_get_detector_ml_returns_magidetector():
    assert isinstance(get_detector("ml"), ml.MagiDetector)


def test_load_magi_missing_deps_raises_runtimeerror(monkeypatch):
    ml._MODEL = None
    monkeypatch.setitem(sys.modules, "torch", None)   # import torch -> ImportError
    with pytest.raises(RuntimeError, match="uv sync --extra ml"):
        ml._load_magi()


@pytest.mark.ml
def test_magi_detect_returns_boxes_real():
    # gated: so roda com `pytest -m ml` (precisa do extra [ml] + baixa o modelo)
    page = Image.new("RGB", (400, 600), (255, 255, 255))
    boxes = ml.MagiDetector().detect(page)
    assert isinstance(boxes, list)
    for b in boxes:
        assert len(b) == 4 and b[2] > 0 and b[3] > 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_ml.py -q`
Expected: FAIL com `ModuleNotFoundError: manga_panels.ml` (o módulo ainda não existe).

- [ ] **Step 3: Create `src/manga_panels/ml.py`**

```python
# src/manga_panels/ml.py
"""Detector de paineis via Magi v2. Todo import de torch/transformers e LAZY
(dentro das funcoes) pra o base install continuar leve."""
from __future__ import annotations

import numpy as np
from PIL import Image

from manga_panels.detect import Box

_MODEL_NAME = "ragavsachdeva/magiv2"
_MODEL = None  # singleton carregado sob demanda


def _panels_to_boxes(panels, page_w: int, page_h: int) -> list[Box]:
    """[x1,y1,x2,y2] (pixels, ordem de leitura do Magi) -> (x,y,w,h) int,
    clampado na pagina, sem caixas degeneradas. Preserva a ordem."""
    boxes: list[Box] = []
    for p in panels:
        x1, y1, x2, y2 = (float(v) for v in p[:4])
        if x2 < x1:
            x1, x2 = x2, x1
        if y2 < y1:
            y1, y2 = y2, y1
        x1 = max(0.0, min(x1, page_w)); x2 = max(0.0, min(x2, page_w))
        y1 = max(0.0, min(y1, page_h)); y2 = max(0.0, min(y2, page_h))
        w = int(round(x2 - x1)); h = int(round(y2 - y1))
        if w > 0 and h > 0:
            boxes.append((int(round(x1)), int(round(y1)), w, h))
    return boxes


def _load_magi():
    """Carrega o Magi v2 uma vez (singleton). Erro claro se o extra [ml] falta."""
    global _MODEL
    if _MODEL is None:
        try:
            import torch
            from transformers import AutoModel
        except ImportError as e:
            raise RuntimeError(
                "detector ml precisa do extra [ml]: uv sync --extra ml "
                "(ou pip install 'manga-panels[ml]')"
            ) from e
        model = AutoModel.from_pretrained(_MODEL_NAME, trust_remote_code=True)
        model = model.to("cuda" if torch.cuda.is_available() else "cpu").eval()
        _MODEL = model
    return _MODEL


class MagiDetector:
    """Detector ML. detect() devolve paineis em ordem de leitura (do proprio Magi)."""

    def detect(self, page: Image.Image) -> list[Box]:
        model = _load_magi()                 # RuntimeError claro se [ml] ausente
        import torch
        arr = np.array(page.convert("L").convert("RGB"))
        with torch.no_grad():
            results = model.predict_detections_and_associations([arr])
        return _panels_to_boxes(results[0]["panels"], page.width, page.height)
```

- [ ] **Step 4: Wire `get_detector` and remove the stub in `detect.py`**

Remova a classe `MLDetector` inteira de `src/manga_panels/detect.py` e troque o ramo `"ml"` de `get_detector`:

```python
def get_detector(name: str, *, rtl: bool = True, min_frac: float = 0.02,
                 max_ink: float = 0.08) -> Detector:
    if name == "xycut":
        return XYCutDetector(rtl=rtl, min_frac=min_frac, max_ink=max_ink)
    if name == "ml":
        from manga_panels.ml import MagiDetector   # import lazy
        return MagiDetector()
    raise ValueError(f"detector desconhecido: {name!r}")
```

- [ ] **Step 5: Remove `MLDetector` from `__init__.py`**

Em `src/manga_panels/__init__.py`, tire `MLDetector` do import e do `__all__`:

```python
from manga_panels.detect import Box, Detector, XYCutDetector, get_detector
from manga_panels.pipeline import process_archive

__all__ = [
    "Box", "Detector", "XYCutDetector", "get_detector",
    "process_archive",
]
```

- [ ] **Step 6: Remove the obsolete stub test in `test_detect.py`**

Apague a função `test_ml_detector_not_implemented` inteira de `tests/test_detect.py` (o `MLDetector` não existe mais; o comportamento do "ml" agora é coberto por `tests/test_ml.py`). Remova também o import de `MLDetector` na linha 3 desse arquivo, deixando:

```python
from manga_panels.detect import XYCutDetector, get_detector
```

- [ ] **Step 7: Run the default suite (no torch/model needed)**

Run: `.venv/bin/pytest -q`
Expected: PASS. Os 5 unit tests novos de `test_ml.py` passam sem baixar modelo; o teste `@pytest.mark.ml` é excluído pelo `addopts`. `test_detect.py` sem o stub. Total sobe pra ~27 passando.

- [ ] **Step 8: Run the gated integration test once, manually**

Run: `.venv/bin/pytest -m ml tests/test_ml.py -q`
Expected: baixa o modelo no 1º uso e PASSA (retorna uma lista de caixas válidas). Se falhar por dep faltando do custom code, adicione ao extra `[ml]` no pyproject e re-sync. (Este passo é verificação manual; não bloqueia o commit se o download falhar por rede — reporte.)

- [ ] **Step 9: Commit**

```bash
git add src/manga_panels/ml.py src/manga_panels/detect.py src/manga_panels/__init__.py tests/test_ml.py tests/test_detect.py
git commit -m "feat: Magi v2 ML panel detector (--detector ml)"
```

---

## Task 3: Docs + calibração manual xycut vs ml

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: tudo.
- Produces: doc de uso do ML. Sem código novo.

- [ ] **Step 1: Update `README.md`**

Na seção de instalação, adicione o extra ml:

```markdown
# detector ML (Magi v2, precisa de GPU pra ser rapido)
uv sync --extra ml        # ou: pip install "manga-panels[ml]"
```

Na seção de uso, adicione:

```markdown
# detector ML — muito melhor em paginas de acao/nao-grid (baixa ~1.5GB no 1o uso)
manga-panels capitulo.cbz --detector ml
```

E na calibração, troque a linha do detector por:

```markdown
- Detector: `--detector xycut` (default, leve, bom em grid limpo P&B).
  `--detector ml` usa o Magi v2 (Manga109) — resolve paginas de acao, sangradas
  e nao-retangulares que o xycut mescla ou falha. Precisa do extra `[ml]` e de
  GPU pra rodar rapido; baixa o modelo (~1.5GB) no primeiro uso.
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: document --detector ml (Magi v2)"
```

- [ ] **Step 3: Manual calibration comparison (não bloqueia; gera evidência)**

Com `[ml]` instalado, rode a comparação nas páginas que o xycut errou e anote as caixas dos dois detectores lado a lado (mesma técnica de visualização já usada no projeto). Alvo: as ~12% de páginas que o xycut devolvia como 1 painel caem drasticamente com o ML. Reporte o antes/depois.

---

## Self-Review (feita ao escrever)

- **Spec coverage:** MagiDetector+protocolo → Task 2; imports lazy → Task 2 (ml.py); singleton+device → `_load_magi` Task 2; extra [ml] via uv → Task 1; erro claro → Task 2 (`_load_magi`); ordem de leitura (Magi já ordena) → confirmado, `_panels_to_boxes` preserva; testes 2 camadas (unit mock + gated) → Task 2; remove stub → Task 2; docs+calibração → Task 3. Coberto.
- **Placeholders:** nenhum — todo passo tem código/comando real.
- **Type consistency:** `Box=(x,y,w,h)` idêntico em ml.py/detect.py; `_panels_to_boxes(panels, page_w, page_h)`, `MagiDetector.detect(page)->list[Box]`, `get_detector(...,max_ink=0.08)` batem com detect.py atual.
- **Nota de contingência:** se o custom code do magiv2 pedir dep não listada, Task 2 Step 8 manda adicioná-la ao extra `[ml]`. Se `torch.cuda.is_available()` for False, Task 1 Step 3 tem o índice CUDA.
