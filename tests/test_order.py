from manga_panels.order import order_boxes


def test_rtl_two_by_two():
    # out-of-order boxes: (x, y, w, h)
    tl = (0, 0, 40, 40)      # top-left
    tr = (60, 0, 40, 40)     # top-right
    bl = (0, 60, 40, 40)     # bottom-left
    br = (60, 60, 40, 40)    # bottom-right
    boxes = [bl, tr, br, tl]
    assert order_boxes(boxes, rtl=True) == [tr, tl, br, bl]


def test_ltr_two_by_two():
    tl = (0, 0, 40, 40)
    tr = (60, 0, 40, 40)
    boxes = [tr, tl]
    assert order_boxes(boxes, rtl=False) == [tl, tr]
