# 09 — Atributos de pauta e ligaduras

Fase 2. Amplia `conversor/montagem.py` com claves (todas, inclusive no meio do compasso),
armaduras, fórmulas de compasso, barras e ligaduras de prolongamento.

## Pré-requisitos

- [08](08-montagem-basica.md).

## Cria

- Nada novo: amplia `montagem.py` e `testes/test_montagem.py`.
- `testes/ly/09-atributos.ly` (pode reaproveitar o `04-pauta.ly`).

## O que fazer

### 1. Clave

Tabela `(glifo, posicao) → classe do music21`:

| `glifo` | `posicao` | music21 |
|---|---|---|
| `clefs.G` | −2 | `clef.TrebleClef()` |
| `clefs.G` | −4 | `clef.FrenchViolinClef()` |
| `clefs.F` | 2 | `clef.BassClef()` |
| `clefs.F` | 0 | `clef.FBaritoneClef()` (barítono em fá) |
| `clefs.C` | 0 | `clef.AltoClef()` |
| `clefs.C` | 2 | `clef.TenorClef()` |
| `clefs.C` | −2, −4 | `clef.MezzoSopranoClef()`, `clef.SopranoClef()` |
| `clefs.percussion` | qualquer | `clef.PercussionClef()` |

`transp` (−7, 7, −14...) vira `octaveChange = transp // 7` na clave criada (verificado que o
atributo existe), ou as classes prontas `Treble8vbClef`, `Treble8vaClef`, `Bass8vbClef`. Combinação fora da tabela: aviso e clave de sol.

Mudança no meio do compasso: inserir a clave **na `Measure` da pauta**, no offset do evento, e não
dentro de uma voz. A primeira de cada pauta vai no offset 0 do 1º compasso.

### 2. Armadura

`alteracoes` → número de acidentes:

- só sustenidos, na ordem fá dó sol ré lá mi si (`nota` 3, 0, 4, 1, 5, 2, 6), sem buraco: `n`;
- só bemóis, na ordem si mi lá ré sol dó fá (6, 2, 5, 1, 4, 0, 3), sem buraco: `-n`;
- vazio: 0.

Qualquer outra coisa (armadura não tradicional, alteração presa a oitava): aviso, e usar a
armadura tradicional mais próxima pelo número de acidentes. As notas não são afetadas, porque as
alturas do JSON já são absolutas.

`key.KeySignature(n)`. O modo (maior/menor) não vem confiável do LilyPond só pela tônica. Use
`KeySignature`, e não `Key`, para não inventar modo.

Mudança: nova `KeySignature` no compasso (offset do evento). `\key c \major` depois de uma
armadura com acidentes é `KeySignature(0)`, e o music21 escreve os naturais.

### 3. Fórmula de compasso

`meter.TimeSignature(f"{num}/{den}")` no compasso em que a linha `formula` cai. Ela vai em todas
as `PartStaff`. Fórmula no meio do compasso (raro, só com `\partial` interno): pôr no início do
compasso seguinte e avisar.

`\time 4/4` e `\time 2/2`: o music21 escreve `<time>` com números (verificado: sem
`symbol="common"`). O LilyPond desenha C e ₵ por padrão. Para estudo, tanto faz. O símbolo fica
para a fase 5 (`TimeSignature.symbol = "common"`/`"cut"`).

### 4. Barras

`barra.glifo` → `bar.Barline`:

| LilyPond | music21 |
|---|---|
| `"|."` | `"final"` |
| `"||"` | `"double"` |
| `".|"`, `".."` | `"heavy-light"`, `"light-light"` |
| `"!"` | `"dashed"` |
| `":|."`, `".|:"`, `":..:"`, `":|.|:"` | ignorar aqui: repetições são do passo 14 |

A barra vai em `rightBarline` do compasso que **termina** no `t` da linha. Se o `t` for o início
de um compasso, é o fim do anterior.

### 5. Ligaduras de prolongamento

Já resolvidas na leitura (`lig` e `lig_chega` por altura). Para cada altura do music21:

- `lig` e não `lig_chega`: `tie.Tie("start")`
- `lig` e `lig_chega`: `"continue"`
- só `lig_chega`: `"stop"`

Juntar com as ligaduras que o passo 08 criou ao cortar uma nota na barra: se o pedaço já tem
`stop` e a nota original tinha `lig`, o último pedaço vira `continue`.

## Pegadinhas

- Armadura diferente nas duas pautas (raro, mas existe em peças bitonais): uma `KeySignature` por
  `PartStaff`, cada uma com a sua. O music21 aceita.
- Clave que muda no mesmo instante em que a voz troca de pauta: a ordem dentro do instante não é
  garantida. Clave sempre antes das notas do mesmo offset.
- `clefTransposition` 7 (`treble^8`): as notas já vêm na altura real. A clave só informa a leitura.
- Ligaduras entre vozes diferentes (`\voiceOne c2~ \voiceTwo c2` em `\\`) não existem no
  LilyPond como ligadura de verdade. Ignorar.

## Como verificar

- `09-atributos.ly`, convertido e comparado por partes no XML: as claves no lugar certo (inclusive
  no meio do compasso), `<fifths>` 1, 2 e 0 com `<cancel>` ou naturais, `<beats>6</beats>` no
  compasso da mudança, `<bar-style>light-heavy</bar-style>` no fim, ligaduras `start`/`stop`.
- `fur_Elise_WoO59` e `LiederOhneWorte_-_Op30_No6` no MuseScore: claves e armaduras corretas.

## Pronto quando

- Os testes passam.
- Nas 5 peças simples, o MuseScore mostra claves, armaduras e fórmulas iguais ao PDF do LilyPond
  (gerar com `ferramentas/lilypond/bin/lilypond` à parte, sem `-dno-print-pages`).
