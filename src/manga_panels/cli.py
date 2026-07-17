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
