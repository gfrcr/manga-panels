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
    ap.add_argument("--max-ink", type=float, default=0.08,
                    help="tolerancia de tinta na sarjeta: maior corta mais paineis, "
                         "menor e mais conservador (default 0.08)")
    ap.add_argument("--format", default="jpeg", choices=["jpeg", "png"],
                    help="encoding dos paineis no cbz (default jpeg)")
    ap.add_argument("--quality", type=int, default=90,
                    help="qualidade jpeg 1-95, maior=maior arquivo (default 90)")
    args = ap.parse_args(argv)

    rtl = not args.ltr
    src = Path(args.input)
    kw = dict(detector=args.detector, rtl=rtl, min_frac=args.min_area,
              max_ink=args.max_ink, fmt=args.format, quality=args.quality)

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
            out = out_dir / f"{f.stem}_panels.cbz"
            if out in used:
                out = out_dir / f"{f.stem}_{f.suffix.lstrip('.')}_panels.cbz"
            used.add(out)
            try:
                n = process_archive(f, out, **kw)
            except (NotImplementedError, RuntimeError, ValueError) as e:
                print(f"{f.name}: erro -> {e}")
                failed = True
                continue
            print(f"{f.name}: {n} paineis -> {out.name}")
        return 1 if failed else 0

    if not src.exists():
        print(f"nao encontrado: {src}")
        return 1
    out = Path(args.output) if args.output else src.with_name(f"{src.stem}_panels.cbz")
    try:
        n = process_archive(src, out, **kw)
    except (NotImplementedError, RuntimeError, ValueError) as e:
        print(f"{src.name}: erro -> {e}")
        return 1
    print(f"{src.name}: {n} paineis -> {out}")
    return 0
