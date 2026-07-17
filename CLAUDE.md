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

Flags: `manga-panels --help` (agrupadas detecção/saída/layout). Deps com **uv**,
`uv.lock` versionado.

## Arquitetura (pipeline de 5 estágios)

```
CBZ/CBR  →  unpack  →  detect  →  crop  →  pack  →  CBZ novo
```

Um arquivo por responsabilidade em `src/manga_panels/`:

| Arquivo | Responsabilidade |
|---|---|
| `archive.py` | `unpack()`/`pack()` (CBZ zip, CBR opcional; jpeg/png, quality, max_width; sort natural). Levanta `Empty/BadArchive`. |
| `detect.py` | Protocolo `Detector` (`detect`, `warmup`), `Box`, `XYCutDetector`, `get_detector(name)`. |
| `ml.py` | `MagiDetector` (Magi v2). **Único arquivo com torch/transformers, sempre import lazy.** |
| `pipeline.py` | `crop_panels()`, `process_archive()` (com `on_page` de progresso). |
| `preview.py` | `annotate_page()`/`preview_archive()` — desenha os painéis sem cortar (`--preview`). |
| `config.py` | `load_config()` — lê `manga-panels.toml [defaults]`. |
| `errors.py` | `MangaPanelsError` + `EmptyArchive`/`BadArchive`/`MissingDependency`. |
| `cli.py` | `main()` / argparse + Rich (progresso, tabela). Console script `manga-panels`. |
| `order.py` | `order_boxes()` — prep pra detectores futuros; **não usado hoje** (ambos já saem ordenados). |

**Fluxo por página:** `detect()` devolve painéis em ordem de leitura → página com
≤1 painel (capa/splash/vazio) sai inteira uma vez (sem duplicar) → senão, `--page`
(default `before`) põe a página-macro antes dos painéis.

## Detectores (`--detector`)

- **`xycut`** (default) — projeção recursiva em numpy, corta nas sarjetas brancas.
  Leve, sem GPU, bom em grid P&B limpo; mescla/erra ~30% das páginas de ação
  (linhas cruzando sarjeta, bordas rasgadas, diagonais). Knob: `--max-ink`.
- **`ml`** — Magi v2 (`ragavsachdeva/magiv2`, HuggingFace, `trust_remote_code`),
  na GPU. Resolve páginas complexas. Extra `[ml]`, baixa ~1.5GB no 1º uso.

## Convenções (importantes ao editar)

- **`Box = (x, y, w, h)`** em pixels, em todo lugar.
- **RTL por padrão** (`rtl=True`); o pipeline **confia na ordem do detector** — não re-ordena.
- **torch/transformers SEMPRE lazy** (dentro de função), só em `ml.py`. Base install
  (só xycut) nunca precisa de torch; se `[ml]` faltar, `--detector ml` levanta
  `MissingDependency` claro.
- Falhas conhecidas → `MangaPanelsError` (nunca traceback cru); o CLI captura e no
  batch segue pros próximos. Strings não-confiáveis (nomes de arquivo) vão com
  `rich.markup.escape` antes do Rich.
- Sem OpenCV (não tem wheel pra Python 3.14). Python 3.14 — toda dep precisa de wheel cp314.
- Pin `transformers>=4.40,<5` (5.x quebra o load do magiv2). `sentencepiece`/`timm`
  são puxados pelo custom code do Magi.

## Testes

```bash
.venv/bin/pytest -q      # offline; testes ML deselecionados por default (addopts -m 'not ml')
.venv/bin/pytest -m ml   # integração real (baixa/carrega o Magi)
```

TDD, `assert` puro. O teste de inferência real é `@pytest.mark.ml` (nunca roda num
`pytest` normal). A lógica pura (`_panels_to_boxes`) é testada com Magi **mockado**.

## Limitações conhecidas

- **Spreads de página dupla** (Vagabond, Monster Kanzenban, ~3200px+): corta os
  painéis dentro da spread mas **não separa em 2 páginas**. Se precisar, é um estágio
  pré-detecção (sarjeta central → corta em 2 → detecta por metade). Não construído.
- `order.py`: heurística de linha usa a 1ª caixa como banda, erra alturas irregulares
  — irrelevante hoje (sem caller).

## Docs & Kindle

Specs/planos em `docs/superpowers/`. Kindle (one-off, não é feature): reprocessar no
`ml --max-width 1264`, extrair a capa (metade frontal ~0.47 da spread da pág 0) como
página 1, montar PDF com `img2pdf`, transferir por USB (`documents/`) — Send to
Kindle wireless limita a 50MB.
