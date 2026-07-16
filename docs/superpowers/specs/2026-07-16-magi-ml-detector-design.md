# manga_panels — Detector ML (Magi v2)

**Data:** 2026-07-16
**Status:** aprovado, pré-implementação
**Contexto:** substitui o stub `MLDetector`. XY-cut (default) erra ~30% das
páginas de ação (linhas cruzando sarjetas, bordas rasgadas, painéis
não-retangulares). O Magi é treinado em manga real (Manga109) e resolve isso.

## Objetivo

Implementar `--detector ml` de verdade: detecção de painéis via **Magi v2**
(`ragavsachdeva/magiv2`, HuggingFace), rodando na GPU local (RTX 3070 Ti),
devolvendo caixas já em ordem de leitura. `xycut` continua o default.

## Escopo

- Entra: `PIL.Image` de uma página (mesma interface do detector atual).
- Sai: `list[Box]` = `[(x, y, w, h), ...]` em ordem de leitura, pixels inteiros.
- Fora: OCR, detecção de personagem/texto, tradução (Magi faz, mas não usamos).

## Por que Magi (e por que não Ollama)

Ollama roda GGUF (LLM/VLM via llama.cpp); Magi é um transformer de detecção
PyTorch — runtimes incompatíveis, sem caminho de conversão. VLM genérico via
Ollama foi descartado: detecção de bounding box precisa é tarefa errada pra
VLM (alucina coordenadas, imprevisível). Magi é purpose-built e preciso.

## Arquitetura

Encaixa no que já existe — o pipeline **confia na ordem do detector**, então
o `MagiDetector` só precisa devolver caixas ordenadas.

```
get_detector("ml")  ->  MagiDetector()
MagiDetector.detect(page: PIL.Image) -> list[Box]   # ordem de leitura
```

- `MagiDetector` implementa o protocolo `Detector` (mesmo de `XYCutDetector`).
- **Imports lazy:** `torch`/`transformers` importados DENTRO do
  `__init__`/`detect`, nunca no topo do módulo. Base install (só xycut) não
  precisa deles.
- **Modelo singleton:** carrega `magiv2` uma vez (cacheado em nível de módulo),
  reusa em todas as páginas da execução. `torch.no_grad()` na inferência.
- **Device:** auto — `cuda` se disponível (half precision `.half()` pra caber
  em 8GB e acelerar), senão `cpu` (float32).
- **Download:** `transformers`/`huggingface_hub` baixam e cacheiam o modelo no
  1º uso (`~/.cache/huggingface`). Sem passo manual.

### Ordem de leitura

Preferência: usar a ordem que o **Magi prevê** (é feature dele). Se a API do
magiv2 não expuser ordem utilizável, ordenar via `order_boxes` — e nesse caso
**endurecer `order_boxes`** (hoje a banda de linha usa a 1ª caixa, erra linhas
de altura irregular; trocar por união/expansão da banda). Decisão final na
implementação, ao inspecionar a saída real do modelo.

## Componentes

- `src/manga_panels/ml.py` (novo) — `MagiDetector` + helpers de carga do modelo
  e conversão de saída pra `Box`. Isola todo o código torch/transformers num
  arquivo só (o resto do projeto continua sem deps pesadas).
  - `_load_model()` — singleton, device/precisão, retorna (model, processor).
  - `_panels_to_boxes(raw) -> list[Box]` — converte a saída do Magi (dicts/
    tensores de painel, coords possivelmente float/normalizadas) pra
    `(x, y, w, h)` int em ordem de leitura. **Testável sem torch.**
  - `MagiDetector.detect(page)` — orquestra: garante RGB, roda modelo, chama
    `_panels_to_boxes`.
- `src/manga_panels/detect.py` — **remove** o `MLDetector` stub;
  `get_detector("ml")` passa a fazer import lazy de `manga_panels.ml` e
  retornar `MagiDetector()`. Se o import falhar (extra `[ml]` ausente),
  levanta `RuntimeError` acionável. O teste atual
  `test_ml_detector_not_implemented` é substituído pelo teste de erro-claro
  (camada 1 abaixo).

## Dependências (uv)

`pyproject.toml`:
```toml
[project.optional-dependencies]
ml = ["torch>=2.3", "transformers>=4.40", "huggingface-hub>=0.23", "einops"]
```
Gerência com **uv**: `uv sync --extra ml` (travado no `uv.lock`). torch cp314
tem wheel na PyPI (confirmado v2.13). Se o wheel default não for CUDA, fixar o
índice CUDA via `[tool.uv.sources]`/`[tool.uv.index]` — verificar na
implementação que a GPU é usada de fato (`torch.cuda.is_available()`).

Import lazy garante que sem `[ml]` o `--detector ml` falha com mensagem
acionável, e `xycut` roda normalmente.

## Erros

- `[ml]` ausente + `--detector ml` → `RuntimeError` claro: "detector ml precisa
  do extra: uv sync --extra ml (ou pip install 'manga-panels[ml]')".
- Falha de download do modelo → propaga com contexto.
- Página sem painéis detectados → devolve `[]`; o pipeline aplica o fallback de
  página inteira (comportamento atual, inalterado).

## Testes

Não dá pra baixar ~1.5GB de modelo no fluxo normal de teste. Duas camadas:

1. **Unit, sem torch (roda sempre):** testa `_panels_to_boxes` com saída do
   Magi **mockada** — confere conversão pra `(x,y,w,h)` int e a ordem. Testa
   também que `get_detector("ml")` sem o extra `[ml]` levanta erro claro
   (simulando `ImportError`).
2. **Integração real, gated (skip por padrão):** marcado
   `@pytest.mark.ml`, roda só se `[ml]` instalado + modelo disponível (checa
   import; senão `pytest.skip`). Roda `MagiDetector().detect()` numa página e
   afirma que volta ≥1 `Box` válida.

## Verificação manual (calibração)

Depois de pronto: rodar `--detector ml` no FMA Vol.01 e comparar com xycut nas
páginas de ação que o xycut mesclou (0013 etc.), anotando as caixas — mesma
ferramenta de visualização já usada. Alvo: as páginas com 1 painel (12% no
xycut) caírem drasticamente.

## Fora de escopo (YAGNI)

- `--detector auto` (híbrido xycut+ml) — o usuário optou por ML direto.
- Batch multi-página na GPU (uma página por vez basta; modelo carrega 1x).
- VLM via Ollama.
