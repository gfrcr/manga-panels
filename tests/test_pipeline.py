import zipfile
import numpy as np
from pathlib import Path
from PIL import Image
from manga_panels.pipeline import crop_panels, process_archive
from manga_panels.archive import pack


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
    n = process_archive(src, out)
    assert n == 4
    with zipfile.ZipFile(out) as z:
        assert len(z.namelist()) == 4


def test_blank_page_falls_back_to_whole_page(tmp_path):
    src = tmp_path / "blank.cbz"
    pack([Image.new("RGB", (100, 100), (255, 255, 255))], src)
    out = tmp_path / "blank_panels.cbz"
    n = process_archive(src, out)
    assert n == 1                                  # nunca perde a pagina
