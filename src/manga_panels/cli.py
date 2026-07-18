from __future__ import annotations

import argparse
import os
from pathlib import Path

from rich.console import Console
from rich.markup import escape
from rich.progress import (BarColumn, MofNCompleteColumn, Progress, SpinnerColumn,
                           TextColumn, TimeElapsedColumn)
from rich.table import Table
from rich_argparse import RichHelpFormatter

from manga_panels.config import load_config
from manga_panels.errors import MangaPanelsError
from manga_panels.ml import MagiDetector
from manga_panels.pipeline import process_archive
from manga_panels.preview import preview_archive

_EXTS = {".cbz", ".cbr", ".zip", ".rar"}
console = Console()


def _build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="manga-panels",
        description="Split manga pages into panels and repackage as CBZ.",
        formatter_class=RichHelpFormatter,
    )
    ap.add_argument("input", nargs="?",
                    help="a .cbz/.cbr/image file or folder (omit to pick from the library)")
    ap.add_argument("-o", "--output", help="output file or folder")
    ap.add_argument("--config", help="TOML defaults (default: ./manga-panels.toml)")
    ap.add_argument("-L", "--library",
                    help="folder to browse and pick from when no input is given")

    g_out = ap.add_argument_group("output")
    g_out.add_argument("-f", "--format", default="jpeg", choices=["jpeg", "png"],
                       help="image encoding inside the cbz (default jpeg)")
    g_out.add_argument("-q", "--quality", type=int, default=90,
                       help="jpeg quality 1-95 (default 90)")
    g_out.add_argument("-w", "--max-width", type=int, default=None,
                       help="shrink images wider than N px (default: no limit)")
    g_out.add_argument("--preview", action="store_true",
                       help="write <stem>_preview.cbz with the panels drawn, without cropping")
    g_out.add_argument("--suffix", default="_panels",
                       help="text appended to the output name (default _panels)")
    g_out.add_argument("--overwrite", action="store_true",
                       help="write back over the source file (destructive)")

    g_lay = ap.add_argument_group("layout")
    g_lay.add_argument("--page", choices=["before", "after", "off"], default="before",
                       help="position of the macro page (default before)")
    g_lay.add_argument("-k", "--keep-first", type=int, default=0,
                       help="keep the first N pages whole")
    return ap


def _pair(files, out_dir: Path, suffix: str):
    """Map each source file to a unique out_dir/<stem><suffix> (de-dupes stems)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    jobs, used = [], set()
    for f in files:
        out = out_dir / f"{f.stem}{suffix}"
        if out in used:
            out = out_dir / f"{f.stem}_{f.suffix.lstrip('.')}{suffix}"
        used.add(out)
        jobs.append((f, out))
    return jobs


def _jobs(src: Path, output: str | None, suffix: str):
    """Returns (jobs, error): a list of (in_path, out_path) or ([], message)."""
    if src.is_dir():
        files = sorted(p for p in src.iterdir() if p.suffix.lower() in _EXTS)
        if not files:
            return [], f"no .cbz/.cbr files in {src}"
        out_dir = Path(output) if output else src.with_name(src.name + "_panels")
        return _pair(files, out_dir, suffix), None
    if not src.exists():
        return [], f"not found: {src}"
    out = Path(output) if output else src.with_name(f"{src.stem}{suffix}")
    return [(src, out)], None


def _summary(rows) -> Table:
    t = Table(title="summary", title_style="bold")
    t.add_column("File")
    t.add_column("Images", justify="right")
    t.add_column("Size", justify="right")
    t.add_column("Status", justify="center")
    for name, n, size, ok in rows:
        t.add_row(escape(name), str(n) if ok else "-",
                  f"{size / 1e6:.0f} MB" if size else "-",
                  "[green]OK[/]" if ok else "[red]FAILED[/]")
    return t


def main(argv: list[str] | None = None) -> int:
    # pre-parse --config to apply defaults before the final parse
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("--config")
    cfg_arg, _ = pre.parse_known_args(argv)
    ap = _build_parser()
    try:
        cfg = load_config(cfg_arg.config, warn=lambda m: console.print(f"[yellow]{escape(m)}[/]"))
    except MangaPanelsError as e:
        console.print(f"[red]error:[/] {escape(str(e))}")
        return 1
    ap.set_defaults(**cfg)             # config < CLI flag
    args = ap.parse_args(argv)

    common = dict(fmt=args.format, quality=args.quality, max_width=args.max_width)
    if args.preview:
        run, kw, suffix = preview_archive, common, "_preview.cbz"
    else:
        run = process_archive
        kw = {**common, "page_pos": args.page, "keep_first": args.keep_first}
        suffix = f"{args.suffix}.cbz"

    if args.input is None:
        if not args.library:
            console.print("[red]give an input, or set 'library' in the config[/]")
            return 1
        from manga_panels.browse import pick_from_library
        picks = pick_from_library(args.library, console=console)
        if not picks:
            console.print("nothing selected")
            return 0
        out_dir = Path(args.output) if args.output else Path.cwd()
        jobs, err = _pair(picks, out_dir, suffix), None
    else:
        jobs, err = _jobs(Path(args.input), args.output, suffix)
    if err:
        console.print(f"[red]{escape(err)}[/]")
        return 1

    if args.overwrite:
        jobs = [(inp, inp) for inp, _ in jobs]      # replace sources in place
    else:
        clash = next((inp for inp, out in jobs if inp == out), None)
        if clash:
            console.print("[red]output would overwrite the source; "
                          "use --overwrite, a --suffix, or -o[/]")
            return 1

    # load Magi once up front; let HF's own download/loading bars show through
    console.print("[cyan]Preparing Magi model (first use downloads ~1.5GB)…[/]")
    try:
        MagiDetector().warmup()
    except MangaPanelsError as e:
        console.print(f"[red]error:[/] {escape(str(e))}")
        return 1

    rows, failed = [], False
    with Progress(SpinnerColumn(), TextColumn("[bold]{task.description}"), BarColumn(),
                  MofNCompleteColumn(), TimeElapsedColumn(), console=console) as progress:
        overall = progress.add_task("volumes", total=len(jobs)) if len(jobs) > 1 else None
        for in_path, out in jobs:
            task = progress.add_task(escape(in_path.name), total=None)

            def on_page(done, total, _t=task):
                progress.update(_t, completed=done, total=total)

            overwrite_this = in_path == out
            write_path = out.with_name(out.name + ".tmp") if overwrite_this else out
            try:
                n = run(in_path, write_path, on_page=on_page, **kw)
                if overwrite_this:                  # atomic: don't lose the source on failure
                    os.replace(write_path, out)
                rows.append((in_path.name, n, out.stat().st_size, True))
            except (MangaPanelsError, ValueError) as e:
                if overwrite_this:
                    write_path.unlink(missing_ok=True)
                progress.console.print(f"[red]FAILED[/] {escape(in_path.name)}: {escape(str(e))}")
                rows.append((in_path.name, 0, 0, False))
                failed = True
            progress.remove_task(task)
            if overall is not None:
                progress.advance(overall)

    console.print(_summary(rows))
    return 1 if failed else 0
