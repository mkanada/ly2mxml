# 14 — Repetições e casas

Fase 3. `\repeat volta` vira barras de repetição. `\alternative` vira casas (`<ending>`). As
outras repetições saem desdobradas.

## Pré-requisitos

- [11](11-comparar-midi.md). Independente de 12, 13 e 15.
- A captura já emite `repeticao`, `volta`, `rep-inicio` e `rep-fim` (passo 04).

## Cria

- Amplia `conversor/montagem.py` e, para `\repeat percent`, `ly/captura.ly`.
- `testes/ly/14-repeticoes.ly`.

## O que se sabe (verificado)

Com `\repeat volta 3 { d2 } \alternative { \volta 1,2 { e2 } \volta 3 { f2 } }` começando em
`t = 1`:

| `t` | evento | valores |
|---|---|---|
| 1 | `volta-repeat-start-event` | `repeat-count` 3 |
| 3/2 | `volta-span-event` | início, `volta-numbers` (1 2) |
| 2 | `volta-span-event` | fim, (1 2) |
| 2 | `volta-repeat-end-event` | `return-count` 2 |
| 2 | `volta-span-event` | início, (3) |
| 5/2 | `volta-span-event` | fim, (3) |

`repeatCommands` também aparece no início (`start-repeat`) e no fim (`end-repeat`) da repetição,
mas **sem** as casas. Por isso as casas vêm do `volta-span-event`.

Outras repetições, como chegam à captura:

| Música | O que a captura vê |
|---|---|
| `\repeat unfold 2 { f4 }` | as notas duas vezes. Nada a fazer (28 usos no acervo) |
| `\repeat tremolo 4 { c16 e }` | duas notas `fig = 1` (mínima), `escala = 1/2`, mais um `tremolo-span-event` |
| `c4:16` | uma semínima e um `tremolo-event` com `tremolo-type` 16 |
| `\repeat percent 2 { d8 e }` | **só a primeira vez**. A segunda some (o tempo passa sem notas) |

## O que fazer

### 1. `\repeat percent` na captura

No `captura-preparar` (passo 05), desdobrar só o `percent` antes de entregar o `\score`. A forma
verificada é `\unfoldRepeats percent música`. Como a música de um `\score` pronto não se troca,
criar outro:

```scheme
(let ((novo (ly:make-score #{ \unfoldRepeats percent #(ly:score-music score) #})))
  (if (module? (ly:score-header score)) (ly:score-set-header! novo (ly:score-header score)))
  (for-each (lambda (od) (ly:score-add-output-def! novo od)) (ly:score-output-defs score))
  novo)
```

Verificado que reconstruir assim mantém as definições de saída e o cabeçalho (`ly:score-header`
pode ser `'()`, daí o `module?`). Nenhuma peça do acervo usa `percent` hoje, então isto é barato
e evita uma perda silenciosa. Fazer o mesmo com `tremolo` **não**: o tremolo se escreve como
tremolo.

### 2. Tremolo

Até a fase 5, sem o símbolo de tremolo:

- duas notas com `escala = 1/2` dentro de um tremolo: não usar a figura do LilyPond (mínima), e
  sim `Duration(quarterLength)` da duração efetiva. No exemplo, cada nota vira semínima. Para
  estudo, o que importa é que o tempo feche. Avisar `tremolo escrito como notas simples`.
- `c4:16`: a semínima simples, com aviso.

Na fase 5, isso vira `expressions.TremoloSpanner` e `expressions.Tremolo`.

### 3. Barras de repetição

A partir das linhas da partitura:

- `rep-inicio` em `t`: `leftBarline = bar.Repeat(direction="start")` no compasso que **começa** em
  `t`. Se `t` for o início da peça, o MusicXML não precisa da barra, mas pode tê-la.
- `rep-fim` em `t`: `rightBarline = bar.Repeat(direction="end", times=...)` no compasso que
  **termina** em `t`. `times` só quando o número de vezes passa de 2 (`rep-inicio.vezes`).
- `repeticao` sem `rep-inicio`/`rep-fim` no mesmo `t` (arquivo que use `repeatCommands` à mão):
  `start-repeat` e `end-repeat` valem igual. `(volta "1.")` e `(volta #f)` abrem e fecham uma casa
  com o texto dado.
- Aplicar em **todas** as `PartStaff` (o Hymn_Grabber faz o mesmo).

Repetição no meio do compasso (começa ou termina fora da barra): o MusicXML só aceita repetição na
barra. Avisar e pôr na barra mais próxima.

### 4. Casas

Cada par `volta` início/fim vira `spanner.RepeatBracket(compassos, number=...)`, com os compassos
do intervalo `[início, fim)`. `number` é `"1, 2"` para `(1 2)`, ou o inteiro para uma casa só. Um
`RepeatBracket` por `PartStaff`. Verificado que o music21 exporta `<ending number="1"
type="start" />` e `type="stop"`.

### 5. Saltos (D.C., D.S., Fine, Coda)

`\repeat segno` (2.24+) e marcas de texto. Nenhuma peça do acervo usa `\repeat segno`. Por
enquanto, avisar se aparecer `segno-event`, `coda-mark-event`, `dal-segno-event` ou `fine-event`
(a captura pode emitir uma linha `aviso` ao ouvi-los no `Score`). O texto vai na fase 5.

## Pegadinhas

- Casa que começa no meio do compasso (anacruse antes da casa): `RepeatBracket` só aceita
  compassos inteiros. Pegar os compassos que contêm o intervalo e avisar.
- `\repeat volta` sem `\alternative`, que termina no fim da peça: `rep-fim` cai em `t = fim`. O
  compasso que termina aí é o último.
- A peça com só `\midi` e `\unfoldRepeats` (passo 05): não tem eventos de repetição, porque já
  está desdobrada. Está certo.
- Comparação MIDI: o MusicXML não é desdobrado, nem o MIDI do mesmo `\score`. Os dois tocam cada
  trecho uma vez. A comparação com o `\unfoldRepeats` (passo 11, item 3) passa a valer aqui, com
  `sc.expandRepeats()`.

## Como verificar

`14-repeticoes.ly`: `\repeat volta 2` simples; `volta 3` com casas `1,2` e `3`; repetição que
começa na anacruse; `\repeat unfold`; `\repeat percent`; um tremolo.

Conferir no XML: `<repeat direction="forward"/>` e `backward`, `<ending number="1, 2">`,
`times="3"` onde cabe. No MuseScore: tocar e ouvir que repete.

No acervo: `fur_Elise_WoO59`, `maple`, `gymnopedie_1` e `No03_Albumblatt`. Para cada uma com um
`\score` `\unfoldRepeats` só para MIDI, o `comparar-midi.py` com `expandRepeats` deve bater.

## Pronto quando

- O teste passa.
- As quatro peças mostram as repetições e as casas no MuseScore como no PDF do LilyPond.
- `docs/plano.md` corrigido: `\repeat percent` **não** sai desdobrado sozinho (o plano dizia
  que sim).
