import pytest
from rich.console import Console
from manga_panels.browse import pick_from_library, _parse_nums


def _quiet():
    return Console(quiet=True)


def test_parse_nums_ranges_and_bounds():
    assert _parse_nums("1,3-5", 5) == [1, 3, 4, 5]
    assert _parse_nums("2", 3) == [2]
    with pytest.raises(ValueError):
        _parse_nums("6", 5)          # out of range
    with pytest.raises(ValueError):
        _parse_nums("x", 5)          # junk


def test_pick_navigates_into_folder_and_selects(tmp_path):
    (tmp_path / "Monster").mkdir()
    for n in (1, 2, 3):
        (tmp_path / "Monster" / f"Vol.{n:02d}.cbz").write_bytes(b"x")
    inputs = iter(["1", "1,2"])      # enter Monster, then pick vol 1 & 2
    picks = pick_from_library(tmp_path, console=_quiet(), ask=lambda _p: next(inputs))
    assert sorted(p.name for p in picks) == ["Vol.01.cbz", "Vol.02.cbz"]


def test_pick_go_up_then_cancel(tmp_path):
    (tmp_path / "S").mkdir()
    (tmp_path / "S" / "a.cbz").write_bytes(b"x")
    inputs = iter(["1", "0", ""])    # into S, back up (0), cancel (Enter)
    picks = pick_from_library(tmp_path, console=_quiet(), ask=lambda _p: next(inputs))
    assert picks == []


def test_pick_all_files(tmp_path):
    (tmp_path / "a.cbz").write_bytes(b"x")
    (tmp_path / "b.cbz").write_bytes(b"x")
    picks = pick_from_library(tmp_path, console=_quiet(), ask=lambda _p: "a")
    assert sorted(p.name for p in picks) == ["a.cbz", "b.cbz"]


def test_pick_non_tty_returns_empty(tmp_path):
    def _eof(_p):
        raise EOFError
    assert pick_from_library(tmp_path, console=_quiet(), ask=_eof) == []
