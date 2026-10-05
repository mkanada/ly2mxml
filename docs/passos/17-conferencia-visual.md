# 17 — Conferência visual

Fase 4. Para quando o MIDI bate mas algo parece errado (figura, voz, pauta, clave, colchete):
uma página HTML com o desenho do LilyPond à esquerda e o do MusicXML (Verovio) à direita.

## Pré-requisitos

- [10](10-cli.md). Útil a partir do passo 12.
- `verovio` já está no `requirements.txt`.

## Cria

- `scripts/conferir.py PECA [-p N] [-c A-B] [-o DIR]`.

## O que fazer

Diferente do Hymn_Grabber, aqui não é preciso recortar PDF nem tirar screenshot com o chromium:
os dois lados saem em **SVG**, e uma página HTML os põe lado a lado.

1. **Lado do LilyPond.** Compilar a cópia convertida pelo `convert-ly` (não o envelope) com
   `-dbackend=svg -o DIR/BASE`. Verificado na 2.26: sai `BASE-1.svg`, `BASE-2.svg`... (uma por
   página) e um aviso inofensivo, `ignoring unsupported formats (pdf)`. Com vários `\score`, eles
   estão todos nessas páginas, em ordem.
2. **Lado do MusicXML.** `verovio.toolkit()`, `loadFile(saida.musicxml)`. Opções de partida:
   `{"pageWidth": 2100, "pageHeight": 2970, "scale": 40, "footer": "none", "header": "none"}`.
   Uma `renderToSVG(n)` por página (`getPageCount()`). Verificado que o Verovio do `.venv` lê o
   MusicXML do music21.
3. **Página.** `DIR/BASE.html`, com duas colunas (`display: grid; grid-template-columns: 1fr 1fr`),
   uma linha por página, e as SVG incluídas por `<img src="BASE-1.svg">` (não inline: as do
   LilyPond são grandes).
4. `-p N`: só a página N de cada lado.
5. `-c A-B`: no Verovio, `tk.select({"measureRange": "A-B"})` e `redoLayout()` (como no
   Hymn_Grabber). O lado do LilyPond continua por página. Os dois desenham o número do compasso
   no início de cada sistema, e isso basta para achar o trecho.
6. Imprimir o caminho do HTML. Abrir no navegador é com o usuário.

Saída padrão: `saida/conferir/`, fora do git.

## Pegadinhas

- As quebras de linha e de página não batem entre os dois lados, porque o MusicXML não leva o
  layout (fora do escopo). Compare compasso a compasso pelos números, não página com página.
- O Verovio às vezes desenha diferente do MuseScore (por exemplo, vozes cruzando pauta). Na
  dúvida, abrir no MuseScore, que é o alvo.
- Fontes: no SVG do LilyPond (verificado), os glifos musicais são caminhos (`<path>`), e só os
  textos (título, letra, dinâmica por extenso) são `<text font-family="serif">`. A música aparece
  certa em qualquer máquina, e os textos usam a fonte serifada que houver.

## Como verificar

`scripts/conferir.py bach-invention-01` gera o HTML. Abrir e ver as duas colunas com a mesma
música.

## Pronto quando

- Funciona com uma peça de uma partitura e com uma de várias (`sonatina-1`).
- Foi usado pelo menos uma vez para achar um problema real, anotado em `docs/plano.md`.
