# manga_panels — Polimento do CLI pra distribuição

**Data:** 2026-07-17
**Status:** aprovado, pré-implementação
**Contexto:** preparar o tool pra outras pessoas — feedback de progresso (Rich),
erros claros, config de defaults, e fluxo uv/console. Um spec, 5 componentes.

## Escopo (5 componentes, nesta ordem de build)

### 1) Erros (`src/manga_panels/errors.py`)
Taxonomia mínima; cada falha conhecida vira mensagem clara (não stack trace).

```python
class MangaPanelsError(Exception): ...        # base
class EmptyArchive(MangaPanelsError): ...      # 0 imagens no arquivo
class BadArchive(MangaPanelsError): ...        # zip/rar corrompido ou imagem invalida
class MissingDependency(MangaPanelsError): ... # extra [ml] ou unrar ausente
```

- `archive.unpack`: `EmptyArchive` se 0 imagens; `BadArchive` em `zipfile.BadZipFile`,
  erro de rarfile, ou `PIL.UnidentifiedImageError` numa página.
- `archive._unpack_rar`: o `RuntimeError` de rarfile ausente vira `MissingDependency`.
- `ml._load_magi`: o `RuntimeError` de `[ml]` ausente vira `MissingDependency`
  (mesma mensagem "uv sync --extra ml").
- CLI captura `MangaPanelsError` → imprime `✗ <nome>: <msg>` (vermelho). No batch,
  segue pros próximos; exit code ≠0 se algum falhou.
- Atualizar os testes existentes que esperam `RuntimeError` → `MissingDependency`.

### 2) Callback de progresso (pipeline + detector)
- `process_archive(..., on_page: Callable[[int, int], None] | None = None)` e
  `preview_archive(..., on_page=...)`: chamam `on_page(feitas, total)` após cada
  página. Sem callback → comportamento atual (nada muda).
- `warmup(self) -> None` adicionado ao protocolo `Detector` e implementado em
  cada detector: `XYCutDetector.warmup` = no-op; `MagiDetector.warmup` dispara
  `_load_magi()` (carrega o singleton). (Protocol não dá impl herdada — cada
  classe implementa.) Deixa o CLI mostrar spinner de "carregando modelo" antes do
  loop.

### 3) Rich (no `cli.py`)
- **Progresso:** `rich.progress.Progress` (spinner + descrição + `pagina N/total` +
  %). Arquivo único: 1 tarefa (total=páginas), avança pelo `on_page`. Batch: linha
  por volume + a barra de páginas.
- **Warmup:** quando `--detector ml`, `console.status("carregando Magi…")` em volta
  de `detector.warmup()` antes de processar.
- **Resumo:** `rich.table.Table` no fim — colunas `Arquivo · Imagens · Tamanho ·
  Status` (✓ verde / ✗ vermelho).
- **Help:** `rich_argparse.RichHelpFormatter` como `formatter_class`.
- Rich degrada sozinho fora de tty (testes/pipe) — não quebra.

### 4) Config (`src/manga_panels/config.py`)
```python
def load_config(explicit_path: str | None = None) -> dict: ...
```
- Lê a tabela `[defaults]` de um TOML (`tomllib`, stdlib). Retorna `{dest: valor}`.
- Descoberta: se `--config PATH` dado, usa ele; senão `./manga-panels.toml`; senão
  `~/.config/manga-panels/config.toml`. Primeiro que existir vence.
- Chaves = `dest` do argparse (`detector`, `max_width`, `quality`, `format`,
  `page`, `keep_first`, `min_area`, `max_ink`, `ltr`, `output`). Chave desconhecida
  → aviso (`console.print`) e ignora.
- CLI: pre-parse do `--config` (via `parse_known_args`), `load_config`,
  `ap.set_defaults(**cfg)`, depois `parse_args`. **Flag na CLI sempre vence** o
  config (defaults do argparse < config < flag explícita). Adiciona `--config PATH`.

### 5) uv / deps / docs
- `rich` e `rich-argparse` entram em `[project.dependencies]` (base; pure-python,
  wheel cp314). `tomllib` é stdlib.
- Verificar `uv tool install .` e `uvx --from . manga-panels`.
- README + CLAUDE.md: documentar Rich (nada a fazer, é automático), o
  `manga-panels.toml`, e o fluxo uv (`uv tool install`). PyPI fica pra depois.

## Componentes (arquivos)

- `src/manga_panels/errors.py` (novo) — exceções.
- `src/manga_panels/config.py` (novo) — `load_config`.
- `src/manga_panels/archive.py` (modificar) — raise `EmptyArchive`/`BadArchive`/`MissingDependency`.
- `src/manga_panels/ml.py` (modificar) — `_load_magi` raise `MissingDependency`; `MagiDetector.warmup`.
- `src/manga_panels/detect.py` (modificar) — `warmup` no protocolo + `XYCutDetector` no-op.
- `src/manga_panels/pipeline.py` (modificar) — `on_page` em `process_archive`.
- `src/manga_panels/preview.py` (modificar) — `on_page` em `preview_archive`.
- `src/manga_panels/cli.py` (modificar) — Rich (progress/status/table/help), config, catch `MangaPanelsError`.
- `pyproject.toml` (modificar) — `rich`, `rich-argparse` nas deps base.

## Erros / bordas

- Config: TOML inválido → `MangaPanelsError` com mensagem "config invalido:
  <erro>". Arquivo de config ausente na descoberta → sem config, segue com
  defaults. `--config PATH` explícito inexistente → `MangaPanelsError` claro.
- Rich em `pytest` (sem tty): `Progress`/`status` funcionam degradados; os testes
  de CLI existentes (rc + arquivo) continuam válidos.
- `warmup` no `xycut` é no-op — nenhum custo.

## Testes

- `test_errors.py` / `test_archive.py`: `unpack` levanta `EmptyArchive` (zip sem
  imagem) e `BadArchive` (zip corrompido). CBR sem rarfile → `MissingDependency`.
- `test_config.py`: `load_config` lê `[defaults]`; chave desconhecida é ignorada;
  precedência via CLI (`--config` seta `detector=ml`, `--detector xycut` na linha
  vence). TOML inválido → `MangaPanelsError`.
- `test_pipeline.py`: `on_page` chamado `len(pages)` vezes com `(feitas, total)`
  corretos (acumula numa lista no teste).
- `test_ml.py`: atualizar o teste de deps ausentes pra `MissingDependency`.
- CLI: `--config` aplica defaults e a flag vence; batch com 1 arquivo ruim →
  `✗` + segue + rc≠0. Rich não é testado no visual — só que `main` roda e gera a
  saída.

## Fora de escopo (YAGNI)

- Perfis nomeados no config (só `[defaults]`).
- Publicar no PyPI (precisa de conta; fica documentado o caminho).
- Rich degradado custom / tema — usa o default do Rich.
- Taxonomia grande de exceções (só as 3 + base).
