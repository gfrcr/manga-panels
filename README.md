# manga_panels

Corta páginas de manga (CBZ/CBR) em painéis e reempacota como CBZ — um painel
por página, pra ler confortável em tela pequena.

## Instalar

```bash
python3 -m venv .venv && .venv/bin/pip install -e .
# CBR (opcional): precisa do binario 'unrar' no sistema
.venv/bin/pip install -e ".[cbr]"
```

## Usar

```bash
# um arquivo
manga-panels capitulo.cbz                 # gera capitulo_panels.cbz
manga-panels capitulo.cbz -o saida.cbz

# uma pasta inteira (batch)
manga-panels ./capitulos -o ./saida

# manga ocidental (esquerda->direita)
manga-panels capitulo.cbz --ltr

# saida sem perda (arquivos ~3x maiores)
manga-panels capitulo.cbz --format png
```

A saida e sempre um CBZ (zip de imagens); `--format` so muda o encoding das
imagens dentro dele. Default e JPEG q90 (~1x o tamanho da fonte); PNG e
sem perda mas ~3x maior. Ajuste com `--quality 1..95`.

## Calibração

Scans reais têm ruído, sarjetas acinzentadas e JPEG artifacts. Se o corte
sair errado, ajuste:

- `--max-ink 0.08` — o knob mais importante. É quanta tinta uma linha/coluna
  pode ter e ainda contar como sarjeta. **Sobe** (ex. `0.12`) se páginas
  ficarem como um painel só ou não separarem painéis lado a lado (screentone
  ou onomatopeia cruzando a sarjeta). **Desce** (ex. `0.04`) se um painel
  estiver sendo picado em pedaços.
- `--min-area 0.02` — sobe pra descartar painéis-fantasma pequenos; desce se
  painéis legítimos sumirem.
- Detector: `--detector xycut` (padrão, P&B com sarjeta limpa). `--detector ml`
  é um stub — layouts sangrados/coloridos ainda não são suportados.

Se um capítulo sai como uma página inteira só mesmo subindo `--max-ink`, ele
não tinha sarjetas detectáveis: caso pro futuro detector ML.

Calibração medida em FMA Vol.01 (176 páginas): default antigo (0.01) dava
2.3 painéis/página e deixava várias páginas inteiras sem cortar; o default
atual (0.08) dá 3.6/página — densidade realista de mangá.
