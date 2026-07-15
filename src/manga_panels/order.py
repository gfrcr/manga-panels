from __future__ import annotations

from manga_panels.detect import Box


def order_boxes(boxes: list[Box], rtl: bool = True) -> list[Box]:
    if not boxes:
        return []
    # agrupa em linhas: ordena por y (topo), junta caixas que sobrepoem
    # verticalmente com a linha corrente (limiar = metade da altura da 1a caixa)
    by_top = sorted(boxes, key=lambda b: b[1])
    rows: list[list[Box]] = []
    for b in by_top:
        _, y, _, h = b
        cy = y + h / 2
        placed = False
        for row in rows:
            ry, rh = row[0][1], row[0][3]
            if ry <= cy <= ry + rh:            # centro cai dentro da 1a caixa da linha
                row.append(b)
                placed = True
                break
        if not placed:
            rows.append([b])
    ordered: list[Box] = []
    for row in rows:
        row.sort(key=lambda b: b[0], reverse=rtl)   # x decrescente se RTL
        ordered.extend(row)
    return ordered
