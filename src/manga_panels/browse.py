"""Interactive library picker: browse a configured folder, descend into series
subfolders, and select the archives to process."""
from __future__ import annotations

from pathlib import Path

from rich.markup import escape

from manga_panels.archive import _natkey

_EXTS = {".cbz", ".cbr", ".zip", ".rar"}


def _visible(d: Path):
    for p in sorted(d.iterdir(), key=lambda p: _natkey(p.name)):
        if not p.name.startswith("."):        # skip dotfiles / OS junk
            yield p


def _entries(d: Path):
    """(kind, path) list for a folder: subdirs first, then archives, natural order.
    ponytail: subdirs aren't pre-filtered for content; an empty one just lists
    nothing and the user goes back up."""
    items = list(_visible(d))
    dirs = [p for p in items if p.is_dir()]
    files = [p for p in items if p.is_file() and p.suffix.lower() in _EXTS]
    return [("dir", p) for p in dirs] + [("file", p) for p in files]


def _parse_nums(raw: str, n: int) -> list[int]:
    """'1,3-5' -> [1,3,4,5]. Raises ValueError on junk or out-of-range."""
    out: set[int] = set()
    for tok in raw.replace(",", " ").split():
        if "-" in tok:
            a, b = tok.split("-", 1)
            out.update(range(int(a), int(b) + 1))
        else:
            out.add(int(tok))
    if not out or any(v < 1 or v > n for v in out):
        raise ValueError("out of range")
    return sorted(out)


def pick_from_library(root, *, console, ask=None) -> list[Path]:
    """Navigate `root`, letting the user descend into folders and pick archives.
    Returns the selected file paths ([] if cancelled). `ask(prompt)->str` is
    injectable for testing; defaults to console.input."""
    root = Path(root)
    ask = ask or console.input
    cur = root
    while True:
        entries = _entries(cur)
        console.print(f"[bold]{escape(str(cur))}[/]")
        up = cur != root
        if up:
            console.print("   0) ..")
        for i, (kind, p) in enumerate(entries, start=1):
            tag = "[cyan][dir][/]" if kind == "dir" else "     "
            console.print(f"  {i:>2}) {tag} {escape(p.name)}")
        console.print("[dim]numbers / ranges (1,3-5), 'a' for all files, Enter to cancel[/]")
        try:
            raw = ask("> ").strip()
        except EOFError:
            return []
        if not raw or raw.lower() == "q":
            return []
        if raw == "0" and up:
            cur = cur.parent
            continue
        if raw.lower() == "a":
            files = [p for k, p in entries if k == "file"]
            if files:
                return files
            console.print("[yellow]no files here[/]")
            continue
        try:
            nums = _parse_nums(raw, len(entries))
        except ValueError:
            console.print("[red]invalid selection[/]")
            continue
        picked = [entries[i - 1] for i in nums]
        if len(picked) == 1 and picked[0][0] == "dir":
            cur = picked[0][1]
            continue
        if any(k == "dir" for k, _ in picked):
            console.print("[yellow]pick ONE folder to enter, or only files[/]")
            continue
        return [p for _, p in picked]
