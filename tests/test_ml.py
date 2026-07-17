import sys
import pytest
from PIL import Image
from manga_panels.ml import _panels_to_boxes
from manga_panels.detect import get_detector
import manga_panels.ml as ml


def test_panels_to_boxes_converts_xyxy_to_xywh():
    # Magi devolve [x1,y1,x2,y2] em pixels, ja em ordem de leitura
    panels = [[10.0, 20.0, 110.0, 220.0], [0.0, 0.0, 50.0, 50.0]]
    assert _panels_to_boxes(panels, 200, 300) == [(10, 20, 100, 200), (0, 0, 50, 50)]


def test_panels_to_boxes_preserves_magi_order():
    panels = [[100, 0, 150, 50], [0, 0, 50, 50]]   # nao reordena
    assert _panels_to_boxes(panels, 200, 200) == [(100, 0, 50, 50), (0, 0, 50, 50)]


def test_panels_to_boxes_clamps_and_drops_degenerate():
    panels = [[-5.0, -5.0, 300.0, 400.0], [10.0, 10.0, 10.0, 50.0]]  # 2o tem w=0
    assert _panels_to_boxes(panels, 200, 300) == [(0, 0, 200, 300)]


def test_get_detector_ml_returns_magidetector():
    assert isinstance(get_detector("ml"), ml.MagiDetector)


def test_load_magi_missing_deps_raises_missing_dependency(monkeypatch):
    from manga_panels.errors import MissingDependency
    ml._MODEL = None
    monkeypatch.setitem(sys.modules, "torch", None)   # import torch -> ImportError
    with pytest.raises(MissingDependency, match="uv sync --extra ml"):
        ml._load_magi()


@pytest.mark.ml
def test_magi_detect_returns_boxes_real():
    # gated: so roda com `pytest -m ml` (precisa do extra [ml] + baixa o modelo)
    page = Image.new("RGB", (400, 600), (255, 255, 255))
    boxes = ml.MagiDetector().detect(page)
    assert isinstance(boxes, list)
    for b in boxes:
        assert len(b) == 4 and b[2] > 0 and b[3] > 0
