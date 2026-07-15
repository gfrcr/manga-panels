# manga_panels — Pipeline de recorte de painéis

**Data:** 2026-07-15
**Status:** aprovado, pré-implementação

## Objetivo

Pegar capítulos de manga em CBZ/CBR e repaginar cada painel como uma "página"
própria, gerando um CBZ que abre em qualquer leitor (Tachiyomi, Panels,
KOReader) — facilitando a leitura em telas pequenas.

## Escopo

Entra: arquivos CBZ/CBR (zip/rar de imagens).
Sai: CBZ com 1 painel = 1 página.
Leitura assumida: RTL (manga), com flag `--ltr` pra inverter.

## Fluxo

```
chapter.cbz
  └─ 1. unpack   descompacta → páginas ordenadas (Pillow)
  └─ 2. detect   por página → lista de painéis [x,y,w,h]
        ├─ xycut (numpy, projeção recursiva)  ← padrão, construído agora
        └─ ml (Magi/YOLO)                     ← só interface/stub por enquanto
  └─ 3. order    RTL, linha-a-linha (top→bottom, right→left)
  └─ 4. crop     recorta cada painel (Pillow)
  └─ 5. pack     reempacota como <nome>_panels.cbz
```

## Interface (CLI)

```
manga-panels INPUT -o OUTPUT [--ltr] [--detector kumiko|ml] [--min-area FLOAT]
```

- `INPUT`: um `.cbz`/`.cbr` ou uma pasta (batch de vários).
- `--detector`: `xycut` (padrão). `ml` existe como flag mas retorna
  "não implementado" por enquanto.
- `--min-area`: fração mínima da área da página pra um painel contar
  (filtro de over-segmentação). Knob calibrável.

## Componentes (unidades isoladas e testáveis)

- `unpack(path) -> list[PIL.Image]` — abre CBZ/CBR na ordem correta.
- `Detector` (protocolo): `detect(page: PIL.Image) -> list[Box]`.
  - `XYCutDetector` — projeção recursiva (numpy). Detecta sarjetas
    (bandas de fundo claro) e corta; sai em ordem de leitura.
  - `MLDetector` — stub que levanta `NotImplementedError`.
- `order(boxes, rtl) -> list[Box]` — ordena por linhas.
- `crop(page, boxes) -> list[PIL.Image]`.
- `pack(images, out_path)` — escreve o CBZ (zip de PNGs numerados).

Box = `(x, y, w, h)`.

## Bordas tratadas

- **Nenhum painel / spread de página inteira** → página vira 1 painel único.
  Nunca perde conteúdo.
- **Over-segmentação** → filtro `--min-area`. Painéis abaixo do limite são
  descartados. `# ponytail: descarta simples; funde vizinhos se descartar
  demais, sobe pra ML se errar muito`.
- **Painel muito alto** → nada; o leitor faz fit-to-width. YAGNI.

## Fora de escopo (adiciona quando precisar)

- Detector ML de verdade (só interface/flag agora).
- Saída EPUB (CBZ é só um zip; EPUB vira flag depois).
- OCR / tradução / qualquer processamento de texto.

## Stack

Python 3.14 + Pillow + numpy (ambos com wheel pra 3.14). Detector clássico é
XY-cut caseiro em numpy — sem OpenCV (não tem wheel pra 3.14) e sem vendorizar
Kumiko (GPL, não pip-installable). CBZ via `zipfile` (stdlib). CBR é opcional:
usa `rarfile` + `unrar` do sistema se disponível, senão só CBZ. Sem framework,
sem app.

## Verificação

Um self-check com `assert`: uma página sintética com painéis conhecidos
(retângulos brancos separados por sarjeta) deve produzir a contagem e a
ordem RTL esperadas. Roda o pipeline ponta-a-ponta num CBZ de 1 página.
