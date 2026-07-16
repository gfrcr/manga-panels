import zipfile
import numpy as np
from pathlib import Path
from PIL import Image
from manga_panels.pipeline import crop_panels, process_archive
from manga_panels.archive import pack, unpack


def _grid_page():
    arr = np.full((200, 200), 255, np.uint8)
    for (y, x) in [(20, 20), (20, 120), (120, 20), (120, 120)]:
        arr[y:y + 60, x:x + 60] = 0
    return Image.fromarray(arr, "L").convert("RGB")


def test_crop_returns_subimages():
    page = _grid_page()
    panels = crop_panels(page, [(20, 20, 60, 60), (120, 20, 60, 60)])
    assert [p.size for p in panels] == [(60, 60), (60, 60)]


def test_process_archive_explodes_panels(tmp_path):
    src = tmp_path / "ch.cbz"
    pack([_grid_page()], src)                     # 1 pagina, 4 paineis
    out = tmp_path / "ch_panels.cbz"
    n = process_archive(src, out, include_page=False)
    assert n == 4
    with zipfile.ZipFile(out) as z:
        assert len(z.namelist()) == 4


def test_process_archive_prepends_full_page(tmp_path):
    src = tmp_path / "ch.cbz"
    pack([_grid_page()], src)                     # 1 pagina 200x200, 4 paineis
    out = tmp_path / "ch_panels.cbz"
    n = process_archive(src, out)                 # include_page default = True
    assert n == 5                                 # pagina cheia + 4 paineis
    imgs = unpack(out)
    assert imgs[0].size == (200, 200)             # macro primeiro
    assert all(im.size != (200, 200) for im in imgs[1:])  # depois os quadros menores


def test_include_page_not_duplicated_when_whole_page(tmp_path):
    # pagina sem sarjeta: fallback = pagina inteira; nao pode duplicar
    src = tmp_path / "blank.cbz"
    pack([Image.new("RGB", (100, 100), (255, 255, 255))], src)
    out = tmp_path / "out.cbz"
    assert process_archive(src, out, include_page=True) == 1


def test_blank_page_falls_back_to_whole_page(tmp_path):
    src = tmp_path / "blank.cbz"
    pack([Image.new("RGB", (100, 100), (255, 255, 255))], src)
    out = tmp_path / "blank_panels.cbz"
    n = process_archive(src, out)
    assert n == 1                                  # nunca perde a pagina


def test_cli_processes_folder(tmp_path):
    from manga_panels.cli import main
    from manga_panels.archive import pack
    src_dir = tmp_path / "chapters"
    src_dir.mkdir()
    pack([_grid_page()], src_dir / "c1.cbz")
    out_dir = tmp_path / "out"
    rc = main([str(src_dir), "-o", str(out_dir)])
    assert rc == 0
    assert (out_dir / "c1_panels.cbz").exists()


def test_cli_empty_folder_does_not_create_output_dir(tmp_path):
    from manga_panels.cli import main
    empty_dir = tmp_path / "chapters"
    empty_dir.mkdir()
    out = tmp_path / "out"
    rc = main([str(empty_dir), "-o", str(out)])
    assert rc != 0
    assert not out.exists()


def test_cli_same_stem_different_ext_no_overwrite(tmp_path):
    from manga_panels.cli import main
    from manga_panels.archive import pack
    src_dir = tmp_path / "chapters"
    src_dir.mkdir()
    pack([_grid_page()], src_dir / "c1.cbz")
    pack([_grid_page()], src_dir / "c1.zip")
    out_dir = tmp_path / "out"
    rc = main([str(src_dir), "-o", str(out_dir)])
    assert rc == 0
    outputs = sorted(out_dir.iterdir())
    assert len(outputs) == 2
    for f in outputs:
        assert f.stat().st_size > 0
        with zipfile.ZipFile(f) as z:
            assert len(z.namelist()) == 5   # pagina cheia + 4 paineis (--page default)


def test_cli_ml_detector_reports_error_without_raising(tmp_path, monkeypatch):
    from manga_panels.cli import main
    import manga_panels.ml as ml

    def _boom():
        raise RuntimeError("detector ml precisa do extra [ml]: uv sync --extra ml")

    monkeypatch.setattr(ml, "_load_magi", _boom)
    src = tmp_path / "ch.cbz"
    pack([_grid_page()], src)
    rc = main([str(src), "--detector", "ml"])
    assert rc != 0
