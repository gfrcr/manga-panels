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
```

## Calibração

Scans reais têm ruído, sarjetas acinzentadas e JPEG artifacts. Se o corte
sair errado, ajuste:

- `--min-area 0.02` — sobe pra descartar painéis-fantasma pequenos; desce se
  painéis legítimos sumirem.
- Detector: `--detector xycut` (padrão, P&B com sarjeta limpa). `--detector ml`
  é um stub — layouts sangrados/coloridos ainda não são suportados.

Se um capítulo sai como uma página inteira só, ele não tinha sarjetas
detectáveis: caso pro futuro detector ML.
