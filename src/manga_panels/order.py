from __future__ import annotations

from manga_panels.detect import Box


def order_boxes(boxes: list[Box], rtl: bool = True) -> list[Box]:
    if not boxes:
        return []
    # group into rows: sort by y (top), merge boxes that overlap vertically
    # with the current row (threshold = half the height of the first box)
    by_top = sorted(boxes, key=lambda b: b[1])
    rows: list[list[Box]] = []
    for b in by_top:
        _, y, _, h = b
        cy = y + h / 2
        placed = False
        for row in rows:
            ry, rh = row[0][1], row[0][3]
            if ry <= cy <= ry + rh:            # center falls within the row's first box
                row.append(b)
                placed = True
                break
        if not placed:
            rows.append([b])
    ordered: list[Box] = []
    for row in rows:
        row.sort(key=lambda b: b[0], reverse=rtl)   # descending x if RTL
        ordered.extend(row)
    return ordered
