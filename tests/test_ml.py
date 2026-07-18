import sys
import pytest
from PIL import Image
from manga_panels.ml import _panels_to_boxes
import manga_panels.ml as ml


def test_panels_to_boxes_converts_xyxy_to_xywh():
    # Magi returns [x1,y1,x2,y2] in pixels, already in reading order
    panels = [[10.0, 20.0, 110.0, 220.0], [0.0, 0.0, 50.0, 50.0]]
    assert _panels_to_boxes(panels, [], 200, 300) == [(10, 20, 100, 200), (0, 0, 50, 50)]


def test_panels_to_boxes_preserves_magi_order():
    panels = [[100, 0, 150, 50], [0, 0, 50, 50]]   # does not reorder
    assert _panels_to_boxes(panels, [], 200, 200) == [(100, 0, 50, 50), (0, 0, 50, 50)]


def test_panels_to_boxes_clamps_and_drops_degenerate():
    panels = [[-5.0, -5.0, 300.0, 400.0], [10.0, 10.0, 10.0, 50.0]]  # 2nd has w=0
    assert _panels_to_boxes(panels, [], 200, 300) == [(0, 0, 200, 300)]


def test_panels_to_boxes_expands_for_overflowing_balloon():
    panels = [[10, 10, 100, 100]]
    texts = [[90, 90, 130, 130]]                   # balloon overflows bottom-right
    assert _panels_to_boxes(panels, texts, 200, 200) == [(10, 10, 120, 120)]


def test_panels_to_boxes_gutter_text_goes_to_nearest_panel():
    panels = [[0, 0, 80, 100], [120, 0, 200, 100]]  # gutter x[80..120]
    texts = [[85, 40, 110, 60]]                      # floating balloon, overlaps neither
    out = _panels_to_boxes(panels, texts, 200, 100)
    assert out[0] == (0, 0, 110, 100)                # nearest (left) panel grew right
    assert out[1] == (120, 0, 80, 100)               # right panel unchanged


def test_panels_to_boxes_keeps_bleeding_character_whole():
    panels = [[0, 0, 100, 100]]
    chars = [[60, 60, 120, 120]]                     # ~44% inside -> include fully
    assert _panels_to_boxes(panels, [], 200, 200, characters=chars) == [(0, 0, 120, 120)]


def test_panels_to_boxes_ignores_floating_sfx():
    panels = [[0, 0, 80, 100]]
    sfx = [[85, 40, 120, 60]]                        # floating text near the panel
    assert _panels_to_boxes(panels, sfx, 200, 100, essential=[False]) == [(0, 0, 80, 100)]
    assert _panels_to_boxes(panels, sfx, 200, 100, essential=[True]) == [(0, 0, 120, 100)]


def test_pick_device_priority():
    import types
    def fake(cuda, mps, xpu):
        return types.SimpleNamespace(
            cuda=types.SimpleNamespace(is_available=lambda: cuda),
            backends=types.SimpleNamespace(mps=types.SimpleNamespace(is_available=lambda: mps)),
            xpu=types.SimpleNamespace(is_available=lambda: xpu))
    assert ml._pick_device(fake(True, True, True)) == "cuda"
    assert ml._pick_device(fake(False, True, True)) == "mps"
    assert ml._pick_device(fake(False, False, True)) == "xpu"
    assert ml._pick_device(fake(False, False, False)) == "cpu"


def test_load_magi_missing_deps_raises_missing_dependency(monkeypatch):
    from manga_panels.errors import MissingDependency
    ml._MODEL = None
    monkeypatch.setitem(sys.modules, "torch", None)   # import torch -> ImportError
    with pytest.raises(MissingDependency, match="uv sync"):
        ml._load_magi()


@pytest.mark.ml
def test_magi_detect_returns_boxes_real():
    # gated: only runs with `pytest -m ml` (needs the [ml] extra + downloads the model)
    page = Image.new("RGB", (400, 600), (255, 255, 255))
    boxes = ml.MagiDetector().detect(page)
    assert isinstance(boxes, list)
    for b in boxes:
        assert len(b) == 4 and b[2] > 0 and b[3] > 0
