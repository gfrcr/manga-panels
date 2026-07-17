# manga_panels — Flags, preview e layout

**Data:** 2026-07-16
**Status:** aprovado, pré-implementação
**Contexto:** preparar o tool pra outras pessoas usarem — reduzir a fricção de
calibração (preview) e arrumar/expandir as flags. Sem TUI nem web (over-eng);
o valor está no preview + publicar o repo bem (publicação fica pra depois).

## Escopo (5 mudanças)

### A) Auto capa/splash — dedup de página de 1 painel
Hoje uma página com 1 painel detectado (capa, splash, folha de rosto — o Magi
devolve 1 painel nelas) sai **duplicada** com `--page before` (a macro + o painel
que é ~a página toda). Correção: **se `detect()` devolve ≤1 painel, emite a página
inteira uma vez só** (sem macro, sem crop). Unifica com o fallback de página vazia.
Vale pros dois detectores. Resolve capa/front-matter automaticamente.

### B) `--keep-first N` / `-k` (default 0)
As primeiras N páginas são emitidas **inteiras** (sem detecção nem corte); o corte
começa na página N+1. Controle explícito de front-matter (capa, folha de rosto,
créditos). Unifica "não cortar a capa" + "cortar a partir da página X".

### C) `--page {before,after,off}` (default `before`)
Onde a página-macro entra em relação aos seus painéis. Substitui o par
`--page`/`--no-page`:
- `before` — página inteira, depois os painéis (default, visão macro→detalhe)
- `after` — painéis, depois a página inteira (recap)
- `off` — só os painéis

Só se aplica a páginas com ≥2 painéis (as de ≤1 painel já saem uma vez, ver A).

### D) `--preview`
Em vez de cortar, gera `<stem>_preview.cbz`: cada página com os painéis
**desenhados (retângulo) e numerados na ordem de leitura**. Abre no leitor de CBZ
pra conferir os cortes/ordem antes de processar o volume. Mostra a detecção crua
de cada página (não aplica `--keep-first` nem `--page`). Respeita
`--format/--quality/--max-width`. Custo de detecção = igual a processar.

### E) Arrumar flags
- Aliases curtos: `-o` (existe), `-d --detector`, `-f --format`, `-q --quality`,
  `-w --max-width`, `-k --keep-first`.
- `--help` agrupado com argparse: **detecção** (`--detector`, `--min-area`,
  `--max-ink`), **saída** (`-o`, `--format`, `--quality`, `--max-width`,
  `--preview`), **layout** (`--ltr`, `--page`, `--keep-first`).
- Sem alias curto pras menos usadas/crípticas (`--ltr`, `--min-area`,
  `--max-ink`, `--page`, `--preview`).

## Componentes

- `src/manga_panels/pipeline.py` (modificar) — `process_archive`: trocar o param
  `include_page: bool` por `page_pos: str = "before"`; adicionar `keep_first: int
  = 0`; aplicar o dedup ≤1 painel.
- `src/manga_panels/preview.py` (novo) — isola o desenho/anotação:
  - `annotate_page(page: Image, boxes: list[Box], rtl: bool = True) -> Image` —
    desenha os retângulos + número (ordem de leitura) numa cópia da página.
  - `preview_archive(in_path, out_path, *, detector, rtl, min_frac, max_ink,
    fmt, quality, max_width) -> int` — detecta cada página, anota, e escreve o
    CBZ via `pack`. Retorna nº de páginas.
- `src/manga_panels/cli.py` (modificar) — aliases, grupos, `--page` enum,
  `--keep-first`, `--preview`; roteia pra `preview_archive` quando `--preview`.

## Fluxo `process_archive` (novo)

```
for i, page in enumerate(pages):
    if i < keep_first:                 # B: front-matter inteiro
        out.append(page); continue
    boxes = detect(page)               # ja em ordem de leitura
    if len(boxes) <= 1:                # A: capa/splash/fallback -> uma vez
        out.append(page); continue
    if page_pos == "before": out.append(page)
    out.extend(crop_panels(page, boxes))
    if page_pos == "after":  out.append(page)
pack(out, out_path, fmt=fmt, quality=quality, max_width=max_width)
```

## Erros / bordas

- `--keep-first N` maior que o nº de páginas → todas emitidas inteiras (sem erro).
- `--page` inválido → argparse rejeita (choices).
- `--preview` + `--detector ml` sem o extra `[ml]` → mesmo `RuntimeError` claro do
  fluxo normal (surge no 1º `detect`).
- `annotate_page`: fonte via `ImageFont.load_default(size=...)` (Pillow ≥10.1);
  se não suportar tamanho, cai pra `load_default()`. Sem dependência de fonte no
  sistema.

## Testes

- `test_pipeline.py`:
  - dedup: página que detecta 1 painel (grid 1x1 sintético) → 1 imagem na saída
    (não 2), com `--page before`.
  - `keep_first=1`: primeira página emitida inteira, resto cortado.
  - `page_pos`: `before` → [page, p0, p1...]; `after` → [p0, p1..., page]; `off`
    → só painéis. Assert por ordem/contagem no grid sintético.
- `test_preview.py` (novo):
  - `annotate_page` desenha e retorna imagem do mesmo tamanho, sem alterar a
    original (identidade preservada; a saída difere da entrada).
  - `preview_archive` num CBZ de 1 página → CBZ de 1 página anotada; nº = nº de
    páginas de entrada.
- CLI: `--preview` gera `<stem>_preview.cbz`; aliases (`-d -f -q -w -k`) mapeiam
  pros mesmos destinos das flags longas.

## Fora de escopo (YAGNI)

- Classificador de capa por ML (o A resolve).
- TUI / web.
- Preview de amostra parcial (aponta pra um capítulo se quiser rápido).
