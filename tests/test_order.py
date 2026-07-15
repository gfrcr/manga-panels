from manga_panels.order import order_boxes


def test_rtl_two_by_two():
    # caixas fora de ordem: (x, y, w, h)
    tl = (0, 0, 40, 40)      # topo-esquerda
    tr = (60, 0, 40, 40)     # topo-direita
    bl = (0, 60, 40, 40)     # base-esquerda
    br = (60, 60, 40, 40)    # base-direita
    boxes = [bl, tr, br, tl]
    assert order_boxes(boxes, rtl=True) == [tr, tl, br, bl]


def test_ltr_two_by_two():
    tl = (0, 0, 40, 40)
    tr = (60, 0, 40, 40)
    boxes = [tr, tl]
    assert order_boxes(boxes, rtl=False) == [tl, tr]
