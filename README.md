# manga_panels

Corta páginas de manga (CBZ/CBR) em painéis e reempacota como CBZ — um painel
por página, pra ler confortável em tela pequena.

## Instalar

Precisa do [uv](https://docs.astral.sh/uv/). Clone e rode com `uv run` — ele cria
o ambiente e baixa as dependências sozinho:

```bash
git clone https://github.com/gfrcr/manga-panels
cd manga-panels
uv run manga-panels --help
```

Isso já dá o detector `xycut` (default, leve, sem GPU). Pro detector **ML**
(Magi v2, precisa de GPU) e os outros extras, sincronize uma vez:

```bash
uv sync --all-extras                             # torch (ML), rarfile (CBR), pytest
uv run manga-panels --detector ml capitulo.cbz
```

> CBR (`.cbr`) também precisa do binário **`unrar`** instalado no sistema.

Prefere o comando `manga-panels` solto, de qualquer pasta (sem `uv run` na
frente)? Instale como ferramenta do uv:

```bash
uv tool install "git+https://github.com/gfrcr/manga-panels"                    # xycut
uv tool install "manga-panels[ml] @ git+https://github.com/gfrcr/manga-panels" # + ML
```

Os exemplos abaixo mostram `manga-panels` direto — se você foi pelo `uv run`, é
só prefixar: `uv run manga-panels …`.

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

# muda o texto que entra no nome de saida (default _panels) -> capitulo_cortado.cbz
manga-panels capitulo.cbz --suffix _cortado

# sobrescreve o arquivo original no lugar (destrutivo; grava num temp e troca no fim)
manga-panels capitulo.cbz --overwrite
```

## Biblioteca (seleção interativa)

Aponte uma pasta como biblioteca e rode **sem input** pra escolher os arquivos
num menu numerado — navega nas subpastas de série e seleciona os volumes:

```bash
manga-panels --library /mnt/unraid/media/manga -o ./saida
```

```
/mnt/unraid/media/manga
   1) [dir]  Monster
> 1
   0) ..
   1)       Monster Vol.01.cbz
   2)       Monster Vol.02.cbz
> 1,2        # numeros, faixas (1-4), 'a' pra todos, Enter pra cancelar
```

Sem `-o`, a saída vai pra pasta atual. Dá pra fixar a `library` no config
(abaixo) e aí só rodar `manga-panels`.

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

## Config (opcional)

Pra não repetir flags, crie um `manga-panels.toml` (na pasta atual ou em
`~/.config/manga-panels/config.toml`):

```toml
[defaults]
library = "/mnt/unraid/media/manga"   # rodar sem input abre o menu aqui
detector = "ml"
max_width = 1264
quality = 85
page = "before"
suffix = "_paineis"                   # texto no nome de saida (default _panels)
```

As chaves são os nomes das flags (`max_width`, `keep_first`, …). Uma flag na
linha de comando sempre vence o config. Ou aponte um arquivo com `--config`.

Veja **[`manga-panels.example.toml`](manga-panels.example.toml)** com todas as
opções documentadas — copie pra `manga-panels.toml` e ajuste.

## Desenvolvimento

```bash
uv sync --all-extras     # torch + pytest + rarfile no .venv
uv run pytest -q         # testes (os de ML são pulados por default)
```

Rode sempre por `uv run` (sync **inexato**, não remove nada do venv). Um
`uv sync` **parcial** (ex. só `--extra ml`) faz sync exato e **poda** o que
faltar — por isso o `--all-extras`. Pra hackear o `manga-panels` instalado como
ferramenta, use `uv tool install -e . --force` (editable: só `.py` pega ao vivo;
mudança no `pyproject.toml` pede reinstalar).

## Licença

O código do manga-panels é **MIT** (veja [LICENSE](LICENSE)) — use, modifique e
distribua à vontade.

**Atenção ao `--detector ml`:** ele baixa e usa o modelo **Magi v2**
([ragavsachdeva/magiv2](https://huggingface.co/ragavsachdeva/magiv2)), que tem
licença **própria e não-comercial** (uso pessoal, pesquisa e sem fins
lucrativos; comercial exige acordo com o autor). O manga-panels não redistribui
o modelo — baixa em tempo de execução — mas ao usar `ml` você fica sujeito aos
termos do Magi. O detector `xycut` (default) não tem essa restrição.
