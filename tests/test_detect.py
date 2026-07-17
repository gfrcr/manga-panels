import numpy as np
from PIL import Image
from manga_panels.detect import XYCutDetector, get_detector


def _page_with_grid():
    # white 200x200 page with 4 black squares (2x2), 20px gutter
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
    # RTL: expected order = top-right, top-left, bottom-right, bottom-left
    boxes = XYCutDetector(rtl=True).detect(_page_with_grid())
    centers = [(x + w / 2, y + h / 2) for (x, y, w, h) in boxes]
    # panel 0 is in the top half (small y) and on the right (large x)
    assert centers[0][1] < 100 and centers[0][0] > 100
    # panel 1 is on top and on the left
    assert centers[1][1] < 100 and centers[1][0] < 100
    # panel 2 is bottom-right; panel 3 is bottom-left
    assert centers[2][1] > 100 and centers[2][0] > 100
    assert centers[3][1] > 100 and centers[3][0] < 100


def test_blank_page_returns_empty():
    blank = Image.new("RGB", (100, 100), (255, 255, 255))
    assert XYCutDetector().detect(blank) == []


def _page_with_noisy_gutter():
    # 2 panels side by side with a "dirty" vertical gutter: ~3% ink
    # crossing it (simulates screentone/onomatopoeia). 200x100, gutter x[90..110].
    arr = np.full((100, 200), 255, np.uint8)
    arr[10:90, 10:90] = 0          # left panel
    arr[10:90, 110:190] = 0        # right panel
    arr[45:48, 90:110] = 0         # 3 ink rows in the gutter -> ~3%/column
    return Image.fromarray(arr, "L").convert("RGB")


def test_max_ink_knob_splits_noisy_gutter():
    page = _page_with_noisy_gutter()
    # too conservative (old default): the dirty gutter slips through -> 1 panel
    assert len(XYCutDetector(max_ink=0.01).detect(page)) == 1
    # calibrated default: tolerates the intrusion and splits the 2 panels
    assert len(XYCutDetector(max_ink=0.08).detect(page)) == 2


def test_get_detector_returns_xycut():
    assert isinstance(get_detector("xycut"), XYCutDetector)
