# 01 — Formato dos eventos

Fase 1. Não cria código: fixa o contrato entre a captura em Scheme (passos 02–05) e a leitura em
Python (passo 07). Os dois lados devem ser escritos contra este documento. Se o contrato mudar,
atualize-o **aqui primeiro** e suba o número de `formato` no cabeçalho.

## Pré-requisitos

- [00 — Convenções](00-convencoes.md).

## Arquivo

- **JSON Lines**: um objeto JSON por linha, em UTF-8, sem vírgula entre as linhas. Extensão
  `.eventos.jsonl`.
- As linhas saem na ordem em que o LilyPond processa: partitura por partitura e, dentro de cada uma,
  passo de tempo por passo de tempo. **O leitor não pode depender da ordem dentro de um mesmo
  instante.** Ele ordena por `(p, t, g)` e agrupa.
- Todo tempo é uma **string com fração exata** na unidade semibreve: `"0"`, `"3/4"`, `"-1/16"`,
  `"13/8"`. É o que `(format #f "~a" racional)` produz no Guile. Nunca número com ponto.

## Campos comuns

Quase toda linha tem:

| Campo | Tipo | Significado |
|---|---|---|
| `tipo` | string | o tipo da linha (tabela abaixo) |
| `p` | int | número da partitura (`\score`), a partir de 1, na ordem em que o LilyPond as processa |
| `t` | fração | `ly:moment-main` do momento atual |
| `g` | fração | `ly:moment-grace`: `"0"` fora de apojatura, negativo dentro (ex.: `"-1/8"`) |
| `c` | int | `currentBarNumber` no momento do evento |
| `pos` | fração | `ly:moment-main` de `measurePosition`; negativo na anacruse (`"-1/4"`) |

Linhas de voz trazem também `voz` (int) e `pauta` (int). As de pauta trazem `pauta`.

## Tipos de linha

### Estrutura

```json
{"tipo":"cabecalho","formato":1,"lilypond":"2.26.0"}
{"tipo":"partitura","p":1,"so_midi":false}
{"tipo":"pauta","p":1,"pauta":1,"id":"up","contexto":"Staff","t":"0"}
{"tipo":"voz","p":1,"voz":3,"id":"1","pauta":2,"t":"1/2"}
{"tipo":"fim-pauta","p":1,"pauta":1,"t":"19/4"}
{"tipo":"fim","p":1,"t":"19/4"}
```

- `cabecalho`: primeira linha do arquivo, uma vez só.
- `partitura`: quando o contexto `Score` é criado. `so_midi` é `true` quando o `\score` original
  **não tinha `\layout`** e a captura acrescentou um (passo 05). O leitor descarta essas partituras
  se existir alguma com `so_midi: false`, porque elas costumam ser a cópia `\unfoldRepeats` feita
  para o MIDI.
- `pauta`: quando um `Staff` é criado. `pauta` é um contador próprio (1, 2...) dentro da
  partitura. `id` é `ly:context-id` (`""` quando anônima). **Não use o `id` para identificar a
  pauta.**
- `voz`: quando um `Voice` é criado. `voz` é um contador próprio dentro da partitura. O `id` do
  LilyPond **não serve** para distinguir vozes: `<< { } \\ { } >>` dá `"1"`, `"2"` em toda pauta,
  e a voz anônima é `""` (ver [Fatos verificados](README.md#fatos-verificados)). `pauta` é a pauta
  onde a voz nasceu.
- `fim-pauta`: quando o `Staff` termina. Se `t` for menor que o `t` do `fim` da partitura, a pauta
  foi temporária (ossia, `\new Staff` no meio). O passo 08 ignora essas pautas e avisa.
- `fim`: no `finalize` do `Score`. O `t` é o comprimento total da partitura.

### Eventos de voz

```json
{"tipo":"nota","p":1,"voz":1,"pauta":1,"t":"7/8","g":"0","c":1,"pos":"5/8",
 "altura":{"oitava":1,"nota":5,"alt":"0"},"midi":69,
 "fig":4,"pontos":0,"escala":"2/3","dur":"1/24","lig":false}
{"tipo":"pausa","p":1,"voz":1,"pauta":1,"t":"2","g":"0","c":3,"pos":"1/4",
 "fig":2,"pontos":0,"escala":"1","dur":"1/4"}
{"tipo":"pausa-compasso","p":1,"voz":1,"pauta":1,"t":"5/2","g":"0","c":4,"pos":"0",
 "fig":1,"pontos":1,"escala":"2","dur":"3/2"}
{"tipo":"quialtera","p":1,"voz":1,"pauta":1,"t":"7/8","g":"0","c":1,"pos":"5/8",
 "dir":"inicio","num":3,"den":2}
```

- `nota`: uma linha por `note-event`. Um acorde `<c e g>` dá **três linhas** com a mesma
  `(voz, t, g)`. O leitor os junta.
  - `altura`: os campos de `ly:pitch` depois de `\relative` e `\transpose`. `oitava` é
    `ly:pitch-octave` (0 = a oitava do `c'`, o dó central), `nota` é `ly:pitch-notename` (0 = dó …
    6 = si) e `alt` é `ly:pitch-alteration` em tons (`"1/2"` = sustenido, `"-1"` = dobrado bemol).
    No music21: `step = "CDEFGAB"[nota]`, `octave = oitava + 4`, `alter = alt × 2`.
  - `midi`: `60 + ly:pitch-semitones`. É redundante. Serve para conferir e para o passo 06.
  - `pauta`: a pauta **no momento da nota** (`ly:context-find voz 'Staff`), que já segue o
    `\change Staff`. Pode ser diferente da pauta da linha `voz`.
  - `fig`: `ly:duration-log` (−1 = breve, 0 = semibreve, 2 = semínima, 4 = semicolcheia).
    `pontos`: `ly:duration-dot-count`. `escala`: `ly:duration-scale` (`"2/3"` numa tercina).
    `dur`: `ly:duration->moment`, ou seja, a duração efetiva, já com a escala.
  - `lig`: `true` se a nota **começa** uma ligadura de prolongamento, seja por `c~`
    (`tie-event` em `articulations` da nota), seja por `<c e>~` (`tie-event` solto na voz, no
    mesmo passo de tempo, que vale para todas as notas do acorde).
  - Só em apojaturas (`g` diferente de `"0"`): `"barra": true` quando a apojatura é cortada
    (`\acciaccatura`, `\slashedGrace`). Fora disso, `"barra"` não aparece.
- `pausa`: `rest-event`, inclusive a pausa com posição (`a4\rest`). A pausa invisível `s`
  (`skip-event`) **não** gera linha.
- `pausa-compasso`: `multi-measure-rest-event` (`R2.*2`). O `rest-event` não aparece para ela.
  `dur` é a duração total (`"3/2"` em `R2.*2`). `escala` traz o multiplicador.
- `quialtera`: `tuplet-span-event`. `dir` é `"inicio"` ou `"fim"`. No início, `num/den` é a razão
  impressa (3/2 numa tercina, que é o inverso de `ly:duration-scale`). No fim, `num` e `den`
  ficam `null`. O fim chega no momento da **próxima** nota da voz, que pode ser uma apojatura.

### Atributos de pauta

Emitidos pelo engraver de pauta **só quando o valor muda**. No primeiro passo de tempo da pauta
saem sempre.

```json
{"tipo":"clave","p":1,"pauta":2,"t":"0","g":"0","c":1,"pos":"-1/4",
 "glifo":"clefs.F","posicao":2,"transp":0}
{"tipo":"armadura","p":1,"pauta":1,"t":"0","g":"0","c":1,"pos":"-1/4",
 "tonica":{"oitava":0,"nota":4,"alt":"0"},"alteracoes":[[3,"1/2"]]}
```

- `clave`: das propriedades `clefGlyph` (`"clefs.G"`, `"clefs.F"`, `"clefs.C"`, `"clefs.percussion"`),
  `clefPosition` e `clefTransposition` (`-7` em `treble_8`, ausente = 0).
- `armadura`: `tonic` e `keyAlterations`. `alteracoes` é a lista `[nota, alt]`. Se o LilyPond
  trouxer uma alteração presa a uma oitava (`((oitava . nota) . alt)`), ela vai como
  `[nota, alt, oitava]`, e o passo 09 avisa.

### Tempo da partitura

Emitidos pelo engraver de `Score`.

```json
{"tipo":"compasso","p":1,"t":"7/4","g":"0","c":3,"pos":"0","tam":"3/4","medindo":true}
{"tipo":"formula","p":1,"t":"0","g":"0","c":1,"pos":"-1/4","num":3,"den":4}
{"tipo":"barra","p":1,"t":"19/4","g":"0","c":7,"pos":"0","glifo":"|."}
{"tipo":"repeticao","p":1,"t":"7/4","g":"0","c":3,"pos":"0","cmds":[["start-repeat"]]}
{"tipo":"volta","p":1,"t":"3/2","g":"0","c":3,"pos":"0","dir":"inicio","numeros":[1,2]}
```

- `compasso`: no primeiro passo de tempo e sempre que `currentBarNumber` muda. `tam` é
  `measureLength` e `medindo` é a propriedade `timing` (`false` dentro de `\cadenzaOn`). Na
  anacruse, o primeiro `compasso` tem `pos` negativo.
- `formula`: `timeSignatureFraction`, quando muda.
- `barra`: `whichBar` quando é uma string não vazia. O LilyPond só preenche `whichBar` nas barras
  explícitas (`\bar "|."`) e nas de repetição.
- `repeticao`: `repeatCommands` quando não é vazio, convertido para listas de strings e números
  (`["start-repeat"]`, `["end-repeat"]`, `["volta","1."]`, `["volta",false]`). Cobre tanto
  `\repeat volta` quanto o `\set Score.repeatCommands` manual dos arquivos antigos.
- `volta`: `volta-span-event` (a casa de `\alternative`). `dir` é `"inicio"`/`"fim"` e
  `numeros` vem de `volta-numbers`. Os eventos `volta-repeat-start-event` e
  `volta-repeat-end-event` saem como `{"tipo":"rep-inicio","vezes":3}` e
  `{"tipo":"rep-fim","volta":2}` (de `repeat-count` e `return-count`).

### Avisos

```json
{"tipo":"aviso","p":1,"t":"2","texto":"RhythmicStaff não é capturado"}
```

A captura pode avisar sem interromper. O passo 07 repassa esses avisos para stderr.

## Exemplo completo

O trecho abaixo, depois da captura, deve dar exatamente estas linhas, a menos da ordem dentro de
cada instante. Ele vira `testes/ly/01-contrato.ly` e o JSON vira
`testes/ly/01-contrato.eventos.jsonl` (usado pelo passo 07 antes de a captura existir):

```lilypond
\version "2.26.0"
\score {
  \new PianoStaff <<
    \new Staff = "up" \relative c'' { \key g \major \time 3/4 \partial 4 d4 | <g, b>2~ q8 r8 | }
    \new Staff = "down" { \clef bass g4 | g,2. | }
  >>
  \layout { }
}
```

```json
{"tipo":"cabecalho","formato":1,"lilypond":"2.26.0"}
{"tipo":"partitura","p":1,"so_midi":false}
{"tipo":"pauta","p":1,"pauta":1,"id":"up","contexto":"Staff","t":"0"}
{"tipo":"pauta","p":1,"pauta":2,"id":"down","contexto":"Staff","t":"0"}
{"tipo":"voz","p":1,"voz":1,"id":"","pauta":1,"t":"0"}
{"tipo":"voz","p":1,"voz":2,"id":"","pauta":2,"t":"0"}
{"tipo":"compasso","p":1,"t":"0","g":"0","c":1,"pos":"-1/4","tam":"3/4","medindo":true}
{"tipo":"formula","p":1,"t":"0","g":"0","c":1,"pos":"-1/4","num":3,"den":4}
{"tipo":"clave","p":1,"pauta":1,"t":"0","g":"0","c":1,"pos":"-1/4","glifo":"clefs.G","posicao":-2,"transp":0}
{"tipo":"armadura","p":1,"pauta":1,"t":"0","g":"0","c":1,"pos":"-1/4","tonica":{"oitava":0,"nota":4,"alt":"0"},"alteracoes":[[3,"1/2"]]}
{"tipo":"clave","p":1,"pauta":2,"t":"0","g":"0","c":1,"pos":"-1/4","glifo":"clefs.F","posicao":2,"transp":0}
{"tipo":"armadura","p":1,"pauta":2,"t":"0","g":"0","c":1,"pos":"-1/4","tonica":{"oitava":0,"nota":0,"alt":"0"},"alteracoes":[]}
{"tipo":"nota","p":1,"voz":1,"pauta":1,"t":"0","g":"0","c":1,"pos":"-1/4","altura":{"oitava":1,"nota":1,"alt":"0"},"midi":74,"fig":2,"pontos":0,"escala":"1","dur":"1/4","lig":false}
{"tipo":"nota","p":1,"voz":2,"pauta":2,"t":"0","g":"0","c":1,"pos":"-1/4","altura":{"oitava":-1,"nota":4,"alt":"0"},"midi":55,"fig":2,"pontos":0,"escala":"1","dur":"1/4","lig":false}
{"tipo":"compasso","p":1,"t":"1/4","g":"0","c":2,"pos":"0","tam":"3/4","medindo":true}
{"tipo":"nota","p":1,"voz":1,"pauta":1,"t":"1/4","g":"0","c":2,"pos":"0","altura":{"oitava":0,"nota":4,"alt":"0"},"midi":67,"fig":1,"pontos":0,"escala":"1","dur":"1/2","lig":true}
{"tipo":"nota","p":1,"voz":1,"pauta":1,"t":"1/4","g":"0","c":2,"pos":"0","altura":{"oitava":0,"nota":6,"alt":"0"},"midi":71,"fig":1,"pontos":0,"escala":"1","dur":"1/2","lig":true}
{"tipo":"nota","p":1,"voz":2,"pauta":2,"t":"1/4","g":"0","c":2,"pos":"0","altura":{"oitava":-2,"nota":4,"alt":"0"},"midi":43,"fig":1,"pontos":1,"escala":"1","dur":"3/4","lig":false}
{"tipo":"nota","p":1,"voz":1,"pauta":1,"t":"3/4","g":"0","c":2,"pos":"1/2","altura":{"oitava":0,"nota":4,"alt":"0"},"midi":67,"fig":3,"pontos":0,"escala":"1","dur":"1/8","lig":false}
{"tipo":"nota","p":1,"voz":1,"pauta":1,"t":"3/4","g":"0","c":2,"pos":"1/2","altura":{"oitava":0,"nota":6,"alt":"0"},"midi":71,"fig":3,"pontos":0,"escala":"1","dur":"1/8","lig":false}
{"tipo":"pausa","p":1,"voz":1,"pauta":1,"t":"7/8","g":"0","c":2,"pos":"5/8","fig":3,"pontos":0,"escala":"1","dur":"1/8"}
{"tipo":"compasso","p":1,"t":"1","g":"0","c":3,"pos":"0","tam":"3/4","medindo":true}
{"tipo":"fim-pauta","p":1,"pauta":1,"t":"1"}
{"tipo":"fim-pauta","p":1,"pauta":2,"t":"1"}
{"tipo":"fim","p":1,"t":"1"}
```

Ao escrever a captura, confira este exemplo campo a campo. Se o LilyPond der outra coisa (por
exemplo, um `compasso` a mais no fim), corrija **o exemplo e este documento**, não o leitor.

## Pegadinhas

- `(format #f "~a" 3/4)` dá `3/4`, mas `(format #f "~a" 1)` dá `1`, e um racional inteiro negativo
  dá `-1`. As duas formas são frações válidas para `Fraction("1")` e `Fraction("-1/16")`.
- O Guile escreve `#t`/`#f` e `()`. A serialização tem de converter para `true`/`false`/`null`.
  Escreva **uma** função `json` em Scheme que trate string, número exato, booleano, lista e
  alist. Não monte JSON com `format` espalhado.
- Strings (`id`, `glifo`, textos) precisam de escape de `"` e `\`.
- Uma nota com `\change Staff` no meio de um acorde não existe: o acorde é de uma voz só e tem uma
  pauta só.

## Pronto quando

- Este documento e `testes/ly/01-contrato.ly` + `testes/ly/01-contrato.eventos.jsonl` existem.
- O JSON de exemplo é válido (`.venv/bin/python -c "import json,sys; [json.loads(l) for l in open(sys.argv[1])]" testes/ly/01-contrato.eventos.jsonl`).
