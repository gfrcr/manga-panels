import numpy as np
from PIL import Image
from manga_panels.detect import XYCutDetector, MLDetector, get_detector


def _page_with_grid():
    # pagina branca 200x200 com 4 quadrados pretos (2x2), sarjeta de 20px
    arr = np.full((200, 200), 255, np.uint8)
    for (y, x) in [(20, 20), (20, 120), (120, 20), (120, 120)]:
        arr[y:y + 60, x:x + 60] = 0
    return Image.fromarray(arr, "L").convert("RGB")


def test_detects_four_panels(tmp_path):
    boxes = XYCutDetector().detect(_page_with_grid())
    assert len(boxes) == 4
    for (x, y, w, h) in boxes:
        assert w > 0 and h > 0


def test_reading_order_rtl_top_row_first_and_right_first():
    # RTL: ordem esperada = topo-direita, topo-esquerda, base-direita, base-esquerda
    boxes = XYCutDetector(rtl=True).detect(_page_with_grid())
    centers = [(x + w / 2, y + h / 2) for (x, y, w, h) in boxes]
    # painel 0 fica na metade de cima (y pequeno) e na direita (x grande)
    assert centers[0][1] < 100 and centers[0][0] > 100
    # painel 1 fica em cima e na esquerda
    assert centers[1][1] < 100 and centers[1][0] < 100
    # painel 2 fica embaixo e na direita; painel 3 embaixo e na esquerda
    assert centers[2][1] > 100 and centers[2][0] > 100
    assert centers[3][1] > 100 and centers[3][0] < 100


def test_blank_page_returns_empty():
    blank = Image.new("RGB", (100, 100), (255, 255, 255))
    assert XYCutDetector().detect(blank) == []


def test_ml_detector_not_implemented():
    import pytest
    with pytest.raises(NotImplementedError):
        MLDetector().detect(Image.new("RGB", (10, 10)))


def test_get_detector_returns_xycut():
    assert isinstance(get_detector("xycut"), XYCutDetector)
