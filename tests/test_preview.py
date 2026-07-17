import zipfile
import numpy as np
from PIL import Image
from manga_panels.preview import annotate_page, preview_archive
from manga_panels.detect import XYCutDetector
from manga_panels.archive import pack, unpack


def _grid_page():
    arr = np.full((200, 200), 255, np.uint8)
    for (y, x) in [(20, 20), (20, 120), (120, 20), (120, 120)]:
        arr[y:y + 60, x:x + 60] = 0
    return Image.fromarray(arr, "L").convert("RGB")


def test_annotate_page_same_size_and_original_untouched():
    page = _grid_page()
    before = page.tobytes()
    boxes = XYCutDetector().detect(page)
    out = annotate_page(page, boxes)
    assert out.size == page.size
    assert page.tobytes() == before                # original untouched
    assert out.tobytes() != before                 # annotated something (drew boxes)


def test_annotate_page_no_boxes_returns_same_size():
    page = Image.new("RGB", (80, 80), (255, 255, 255))
    out = annotate_page(page, [])
    assert out.size == (80, 80)


def test_preview_archive_page_count(tmp_path):
    src = tmp_path / "ch.cbz"
    pack([_grid_page(), _grid_page()], src)         # 2 pages
    out = tmp_path / "ch_preview.cbz"
    n = preview_archive(src, out)
    assert n == 2                                    # 1 annotated image per page
    with zipfile.ZipFile(out) as z:
        assert len(z.namelist()) == 2
