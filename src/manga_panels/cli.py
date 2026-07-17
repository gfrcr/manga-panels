from __future__ import annotations

import argparse
from pathlib import Path

from manga_panels.errors import MangaPanelsError
from manga_panels.pipeline import process_archive
from manga_panels.preview import preview_archive

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
    g_out.add_argument("--preview", action="store_true",
                       help="gera <stem>_preview.cbz com os paineis desenhados, "
                            "sem cortar (pra calibrar)")

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
                n = run(f, out, **kw)
            except (MangaPanelsError, ValueError) as e:
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
        n = run(src, out, **kw)
    except (MangaPanelsError, ValueError) as e:
        print(f"{src.name}: erro -> {e}")
        return 1
    print(f"{src.name}: {n} imagens -> {out}")
    return 0
