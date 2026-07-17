# manga_panels

Corta páginas de manga (CBZ/CBR) em painéis e reempacota como CBZ — um painel
por página, pra ler confortável em tela pequena.

## Instalar

```bash
python3 -m venv .venv && .venv/bin/pip install -e .
# CBR (opcional): precisa do binario 'unrar' no sistema
.venv/bin/pip install -e ".[cbr]"
# detector ML (Magi v2, precisa de GPU pra ser rapido)
uv sync --extra ml        # ou: pip install "manga-panels[ml]"
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

# detector ML — muito melhor em paginas de acao/nao-grid (baixa ~1.5GB no 1o uso)
manga-panels capitulo.cbz --detector ml

# preview: confere os cortes antes de processar (gera capitulo_preview.cbz)
manga-panels capitulo.cbz --detector ml --preview

# mantem as 2 primeiras paginas inteiras (capa/folha de rosto) e macro depois dos paineis
manga-panels capitulo.cbz -k 2 --page after
```

A saida e sempre um CBZ (zip de imagens); `--format` so muda o encoding das
imagens dentro dele. Default e JPEG q90 (~1x o tamanho da fonte); PNG e
sem perda mas ~3x maior. Ajuste com `--quality 1..95`.

Scans de alta resolucao (ex. edicoes deluxe a 1600px+) geram arquivos grandes.
Pra ler no celular, reduza com `--max-width`:

```bash
manga-panels capitulo.cbz --detector ml --max-width 1200
```

`--max-width N` reduz qualquer imagem mais larga que N px (mantendo proporcao,
nunca amplia) — corta bastante o tamanho sem perda de leitura numa tela de
celular. Sem `--max-width`, mantem a resolucao original.

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
- Detector: `--detector xycut` (default, leve, bom em grid limpo P&B).
  `--detector ml` usa o Magi v2 (Manga109) — resolve paginas de acao, sangradas
  e nao-retangulares que o xycut mescla ou falha. Precisa do extra `[ml]` e de
  GPU pra rodar rapido; baixa o modelo (~1.5GB) no primeiro uso.
- `--preview` gera um CBZ com os paineis desenhados e numerados (ordem de
  leitura) em vez de cortar — abra no leitor pra conferir antes do volume todo.
- `--keep-first N` mantem as primeiras N paginas inteiras (capa/miolo). Capas e
  splashes ja saem inteiras sozinhas (detector devolve <=1 painel).
- `--page before|after|off` controla onde a pagina-macro entra.

Se um capítulo sai como uma página inteira só mesmo subindo `--max-ink`, ele
não tinha sarjetas detectáveis — tente `--detector ml`.

Calibração medida em FMA Vol.01 (176 páginas): default antigo (0.01) dava
2.3 painéis/página e deixava várias páginas inteiras sem cortar; o default
atual (0.08) dá 3.6/página — densidade realista de mangá.
