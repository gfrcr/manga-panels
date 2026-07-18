# manga-panels

Corta páginas de manga (CBZ/CBR) em **painéis** e reempacota como um CBZ novo —
um painel por página — pra ler confortável em tela pequena (celular, Kindle).

- Detecção com **Magi v2**, um modelo transformer treinado em mangá: resolve
  páginas de ação, sangradas e não-retangulares, não só grid limpo.
- Ordem de leitura **direita→esquerda** (mangá), vinda do próprio modelo.
- Configura uma vez, depois é só escolher os volumes num menu.

Escolhe sozinho o melhor device do torch: **CUDA** (NVIDIA), **ROCm** (AMD),
**XPU** (Intel), **MPS** (Apple) ou **CPU** (uns poucos minutos por volume).

## Instalar

Precisa do [uv](https://docs.astral.sh/uv/). Clone e rode com `uv run` — ele cria
o ambiente e baixa as dependências (inclui o **torch**, ~2GB) sozinho:

```bash
git clone https://github.com/gfrcr/manga-panels
cd manga-panels
uv run manga-panels --help
```

No primeiro processamento, o modelo Magi (~1.5GB) é baixado automaticamente.

> Pra GPU **AMD/Intel/Apple**, instale o build do torch correspondente
> (ROCm/XPU/MPS) — o padrão é o build NVIDIA/CUDA. O código usa o que estiver
> disponível; sem GPU, roda na CPU.
>
> CBR (`.cbr`) precisa do binário **`unrar`** no sistema e do extra:
> `uv sync --extra cbr`.

Prefere o comando `manga-panels` solto, de qualquer pasta (sem `uv run` na
frente)? Instale como ferramenta do uv:

```bash
uv tool install "git+https://github.com/gfrcr/manga-panels"
```

Os exemplos abaixo mostram `manga-panels` direto — se você foi pelo `uv run`, é
só prefixar: `uv run manga-panels …`.

## Configurar (o jeito recomendado)

Em vez de repetir flags, guarde seus padrões num **`manga-panels.toml`** — na
pasta de onde você roda o comando, ou em `~/.config/manga-panels/config.toml`:

```toml
[defaults]
library   = "/caminho/para/seus/mangas"   # pasta que o menu abre quando roda sem input
max_width = 1264                          # largura do seu leitor (1264 = Kindle Paperwhite)
quality   = 85
page      = "before"                      # a página inteira antes dos painéis
```

Com isso, rode **sem argumentos** e escolha o que processar num menu — ele navega
nas subpastas de série e você seleciona os volumes:

```bash
manga-panels -o ~/saida
```

```
/caminho/para/seus/mangas
   1) [dir]  Monster
> 1
   0) ..
   1)       Monster Vol.01.cbz
   2)       Monster Vol.02.cbz
> 1,2        # números, faixas (1-4), 'a' pra todos, Enter pra cancelar
```

Pronto — cada volume vira um CBZ com um painel por página.

As chaves do config são os nomes das flags (`max_width`, `keep_first`, …). Uma
flag na linha de comando **sempre vence** o config. Veja
**[`manga-panels.example.toml`](manga-panels.example.toml)** com todas as opções
comentadas — copie e ajuste.

## Rodar num arquivo ou pasta (sem menu)

Passe o caminho direto — pra um volume só, batch de uma pasta, ou quando não quer
usar a `library`:

```bash
manga-panels capitulo.cbz               # um arquivo -> capitulo_panels.cbz
manga-panels capitulo.cbz -o saida.cbz  # nome de saída específico
manga-panels ./capitulos -o ./saida     # pasta inteira (batch)
```

Antes de processar um volume todo, **confira os cortes** com `--preview`: gera um
CBZ com os painéis desenhados e numerados na ordem de leitura, sem cortar.

```bash
manga-panels capitulo.cbz --preview
```

Outras flags (todas em `manga-panels --help`; qualquer uma vence o config):

| flag | o que faz |
|---|---|
| `--page before\|after\|off` | onde entra a página inteira (macro) — default `before` |
| `--keep-first N` | mantém as N primeiras páginas inteiras (capa/miolo) |
| `--suffix _cortado` | muda o texto no nome de saída (default `_panels`) |
| `--overwrite` | sobrescreve o arquivo original no lugar (destrutivo) |

## Saída: formato e tamanho

A saída é sempre um CBZ (zip de imagens). Default: **JPEG q90** (~1x o tamanho da
fonte). `--format png` é sem perda mas ~3x maior; ajuste com `--quality 1..95`.

Scans grandes (edições deluxe a 1600px+) geram arquivos pesados. Pra celular ou
Kindle, reduza com `--max-width`:

```bash
manga-panels capitulo.cbz --max-width 1264
```

`--max-width N` reduz qualquer imagem mais larga que N px (mantém proporção, nunca
amplia). Sem ele, mantém a resolução original.

Capa e splash saem inteiras sozinhas (o Magi devolve ≤1 painel), sem duplicar.

## Desenvolvimento

```bash
uv sync --all-extras     # + pytest e rarfile (cbr) no .venv
uv run pytest -q         # os testes reais de ML são pulados por default (-m 'not ml')
```

Rode por `uv run`. Pra hackear o `manga-panels` instalado como ferramenta, use
`uv tool install -e . --force` (editable: só `.py` pega ao vivo; mudança no
`pyproject.toml` pede reinstalar).

## Licença

O código do manga-panels é **MIT** (veja [LICENSE](LICENSE)) — use, modifique e
distribua à vontade.

**Atenção:** a detecção usa o modelo **Magi v2**
([ragavsachdeva/magiv2](https://huggingface.co/ragavsachdeva/magiv2)), que tem
licença **própria e não-comercial** (uso pessoal, pesquisa e sem fins
lucrativos; comercial exige acordo com o autor). O manga-panels não redistribui
o modelo — baixa em tempo de execução — mas ao usá-lo você fica sujeito aos
termos do Magi.
