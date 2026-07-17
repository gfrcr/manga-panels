# CLAUDE.md — manga_panels

CLI que pega páginas de manga (CBZ/CBR), corta em painéis e reempacota como CBZ
— um painel por "página" — pra ler confortável em tela pequena.

## Quickstart

```bash
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"   # base (só xycut)
uv sync --extra ml --extra dev                               # + detector ML (torch/Magi)

manga-panels capitulo.cbz                    # -> capitulo_panels.cbz
manga-panels ./pasta -o ./saida              # batch de uma pasta
manga-panels capitulo.cbz --detector ml      # detector ML (precisa do extra [ml] + GPU)
```

Deps gerenciadas com **uv**; `uv.lock` é versionado (controle de dependências).

## Arquitetura (pipeline de 5 estágios)

```
CBZ/CBR  →  unpack  →  detect  →  crop  →  pack  →  CBZ novo
```

Um arquivo por responsabilidade em `src/manga_panels/`:

| Arquivo | Responsabilidade |
|---|---|
| `archive.py` | `unpack()` (CBZ zip / CBR opcional) e `pack()` (escreve o CBZ; jpeg/png, quality, max_width). Sort natural de nomes de página. |
| `detect.py` | Protocolo `Detector`, `Box`, `XYCutDetector` (numpy), `get_detector(name)`. |
| `ml.py` | `MagiDetector` (Magi v2). **Único arquivo com torch/transformers, sempre import lazy.** |
| `order.py` | `order_boxes()` — normaliza saída não-ordenada em ordem de leitura. Prep pra detectores futuros; **não usado hoje** (ambos os detectores já saem ordenados). |
| `pipeline.py` | `crop_panels()` e `process_archive()` — orquestra tudo. |
| `cli.py` | `main()` / argparse. Console script `manga-panels`. |

**Fluxo por página:** `detect()` devolve painéis já em ordem de leitura → se vazio,
fallback pra página inteira (nunca perde conteúdo) → com `--page` (default), a
página inteira vem antes dos painéis (visão macro). Página com ≤1 painel (capa/splash) é
emitida uma vez só (sem duplicar a macro).

## Detectores (`--detector`)

- **`xycut`** (default) — XY-cut recursivo em numpy: projeta linhas/colunas, corta
  nas sarjetas brancas. Leve, sem GPU, bom em grid P&B limpo. **Não** lida com
  linhas de ação cruzando sarjetas, bordas rasgadas, painéis diagonais (mescla ou
  cai no fallback ~30% das páginas de ação).
- **`ml`** — Magi v2 (`ragavsachdeva/magiv2`, HuggingFace, `trust_remote_code`).
  Treinado em Manga109, resolve páginas complexas. Roda na GPU (auto-detecta CUDA).
  Extra `[ml]` opcional. Baixa ~1.5GB no 1º uso, cacheia em `~/.cache/huggingface`.
  Já devolve painéis em ordem de leitura (não usa `order_boxes`).

## Flags

| Flag | Default | O que faz |
|---|---|---|
| `-o, --output` | `<stem>_panels.cbz` | arquivo ou pasta de saída |
| `--config PATH` | `./manga-panels.toml` | TOML `[defaults]` (flag da CLI vence) |
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

## Saída e erros

- CLI usa **Rich**: barra de progresso (volume + página), spinner no load do
  modelo ML, tabela-resumo no fim. `rich`/`rich-argparse` são deps base.
- Falhas conhecidas levantam `MangaPanelsError` (`errors.py`): `EmptyArchive`,
  `BadArchive`, `MissingDependency`. O CLI captura, imprime a mensagem, e no
  batch segue pros próximos (exit ≠0 se algum falhou).
- Config: `config.py::load_config` lê `manga-panels.toml [defaults]` (chaves =
  dest do argparse); aplicado via `ap.set_defaults` antes do parse.

## Convenções (importantes ao editar)

- **`Box = tuple[int, int, int, int]` = `(x, y, w, h)`** em pixels, em todo lugar.
- **Ordem de leitura RTL por padrão** (`rtl=True`). O pipeline **confia na ordem do
  detector** — não re-ordena.
- **Imports de torch/transformers são SEMPRE lazy** (dentro de função), só em `ml.py`.
  O base install (só xycut) nunca precisa de torch. Se `[ml]` faltar, `--detector ml`
  levanta `MissingDependency` claro ("uv sync --extra ml").
- Sem OpenCV (não tem wheel pra Python 3.14; o XY-cut é numpy puro).
- Python 3.14; toda dependência precisa de wheel cp314.
- Extra `[ml]` pin: `transformers>=4.40,<5` (o 5.x tem regressão no tokenizer TrOCR
  que quebra o load do magiv2). `sentencepiece`/`timm` são puxados pelo custom code.

## Testes

```bash
.venv/bin/pytest -q          # roda offline; testes ML são deselecionados por default
.venv/bin/pytest -m ml       # roda a integração real (baixa/carrega o modelo Magi)
```

- TDD (test-first) para toda lógica não-trivial. `assert` puro, sem frameworks extras.
- O teste de inferência real é marcado `@pytest.mark.ml` e **excluído por default**
  via `addopts = "-m 'not ml' --strict-markers"` — um `pytest` normal nunca baixa o
  modelo. A lógica pura (`_panels_to_boxes`) é testada com saída do Magi **mockada**.

## Limitações conhecidas

- **Spreads de página dupla** (ex. Vagabond, Monster Kanzenban ~3200px+ de largura):
  o detector corta os painéis dentro da spread, mas **não separa a spread em 2
  páginas**. Se precisar, é um estágio pré-detecção (achar a sarjeta central, cortar
  em 2, detectar por metade). Não construído.
- `order.py` tem heurística de linha (usa a 1ª caixa como banda) que erra linhas de
  altura irregular — irrelevante hoje (sem caller), revisitar se um detector precisar.

## Docs

Specs e planos em `docs/superpowers/specs/` e `docs/superpowers/plans/`.

## Nota: conversão pra Kindle (referência)

Painéis → PDF pro Kindle não é feature do CLI; foi um one-off. Receita usada no
Monster (Paperwhite 12ª, tela 1264px): reprocessar no `ml` com `--max-width 1264`,
extrair a capa (metade frontal ~0.47 da largura da spread da página 0) como
página 1, e montar o PDF com `img2pdf` (embute os JPEGs, memória leve). Transferir
por USB (drive `documents/`) — o Send to Kindle wireless limita a 50MB/arquivo.
