# 15 — Compassos incompletos e cadenza

Fase 3. Trata os compassos que não têm o tamanho da fórmula: `\partial` no meio da peça,
`\set Timing.measurePosition`, `\set Timing.measureLength`, compassos cortados antes de uma
repetição e `\cadenzaOn`. Trata também a numeração dos compassos.

## Pré-requisitos

- [11](11-comparar-midi.md). Independente de 12, 13 e 14, mas fica mais fácil depois do 14
  (compassos curtos aparecem muito em volta de repetições).

## Cria

- Amplia `conversor/montagem.py`.
- `testes/ly/15-compassos.ly`.

## O que se sabe (verificado)

- O tamanho real de cada compasso é a diferença entre duas linhas `compasso` (passo 08). Ele
  cobre todos os casos de compasso curto sem precisar saber como foi escrito.
- Na anacruse, o primeiro `compasso` tem `pos` negativo. Num `\partial` no meio, o `compasso`
  seguinte também começa com `pos` negativo.
- Com `\time 2/4 c'1 \cadenzaOn c'4 d' e' \cadenzaOff \bar "|" f'2`:

  | `t` | `c` | `pos` | `timing` |
  |---|---|---|---|
  | 0 | 1 | 0 | sim |
  | 1/2 | 2 | 0 | sim |
  | 1 | 3 | 0 | **não** |
  | 5/4, 3/2 | 3 | 0 | não |
  | 7/4 | 3 | 0 | sim |
  | 9/4 | 4 | 0 | sim |

  Na cadenza, `currentBarNumber` não muda e `measurePosition` fica parado em 0. O `\bar "|"` em
  `7/4` desenha a barra, mas **não** abre compasso novo. O LilyPond conta o `f'2` como parte do
  compasso 3. Para a captura, o compasso 3 vai de `1` a `9/4` (5/4 de semibreve num 2/4).

## O que fazer

### 1. Compasso curto

Para cada compasso, `real = próximo.t - t` e `tam` vem da linha `compasso`:

- `real == tam`: normal.
- `real < tam` e `pos < 0` no início: falta tempo **no começo** (anacruse, `\partial` no meio).
  `paddingLeft = (tam - real) * 4`.
- `real < tam` e `pos == 0`: falta **no fim** (compasso cortado antes de uma repetição ou de um
  `\partial`). `paddingRight = (tam - real) * 4`.
- `real > tam`: compasso longo (cadenza, `measureLength` mexido). Ver item 3.

O par "compasso cortado no fim + compasso com anacruse" que soma um compasso inteiro (comum em
volta de repetições, `fur_Elise_WoO59`) fica como dois compassos no MusicXML. O segundo recebe
`implicit="yes"` para não contar na numeração. Faça isso no pós-processamento do XML, como já se
faz no compasso 0.

### 2. Numeração

- O número do `<measure>` é o `c` do LilyPond. Ele já trata `\set Score.currentBarNumber`.
- Dois compassos com o mesmo `c` (o caso do item 1, ou a cadenza partida no item 3): o segundo
  leva sufixo (`"12a"`) ou `implicit="yes"`. O MuseScore lida melhor com `implicit`.
- O music21 exige `number` inteiro. Use `numberSuffix` para o sufixo (o Hymn_Grabber usa assim
  nos compassos da introdução).

### 3. Cadenza e compasso longo

- Se o compasso tem algum `compasso` com `medindo: false` dentro, é cadenza.
- Se uma linha `barra` cai **dentro** do compasso (como o `\bar "|"` em `7/4`), partir o compasso
  ali: a cadenza fica num compasso, o resto em outro (com o mesmo `c` e `implicit="yes"`).
- O pedaço da cadenza fica um compasso longo. O MusicXML aceita compasso maior que a fórmula. Se
  o music21 recusar na gravação, o contorno do passo 08 (`makeNotation=False`) entra, com aviso.
- Avisar `cadenza no compasso N (X tempos)`.

### 4. Fórmula e armadura no meio do compasso

O passo 09 já põe clave e armadura no offset do evento. Fórmula de compasso no meio de um compasso
só acontece com `\partial` interno. Nesse caso, o compasso já foi partido pelas linhas `compasso`,
e a fórmula cai no início de um deles. Conferir no teste.

## Pegadinhas

- `\set Timing.measurePosition = #(ly:make-moment -1/4)` (usado no `fur_Elise_WoO59`) tem o mesmo
  efeito de um `\partial`. Não precisa de tratamento especial, porque o passo 08 usa as linhas
  `compasso`.
- `\partial` no meio de um compasso que ainda não terminou: o LilyPond avisa e corta. O JSON
  reflete o que ele fez. Não tente corrigir.
- Cadenza sem `\bar` no fim: o compasso longo vai até a próxima barra que o LilyPond pôr. Está
  certo.
- Compasso longo **fora** de cadenza (`\set Timing.measureLength`): mesmo tratamento do item 3, com
  aviso diferente.

## Como verificar

`15-compassos.ly`: anacruse; `\partial` no meio, antes de uma repetição; `measurePosition`
negativo à mão; uma cadenza com e sem `\bar` no fim; `\set Score.currentBarNumber = #50`.

No XML: os `paddingLeft`/`paddingRight` corretos (as durações somadas de cada `<measure>`),
`implicit="yes"` onde deve, números 50, 51... depois da troca.

No acervo: `chopin_nocturne_op9_n2` (cadenza), `fur_Elise_WoO59` (`measurePosition`),
`SchubertF-D899-2-Impromptu` (7 `\partial`), `intermezzo`, `diabeli.op163.s1-1`.

## Pronto quando

- O teste passa e o `comparar-midi.py` bate nas cinco peças (fora o que depender de passos ainda
  não feitos).
- O MuseScore abre as cinco sem marcar compasso corrompido (o triângulo vermelho de compasso com
  duração errada).
