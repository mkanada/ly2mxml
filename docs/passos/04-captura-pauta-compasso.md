# 04 — Captura de pauta e compasso

Fase 1. Acrescenta a `ly/captura.ly` o engraver de `Staff` (linhas `pauta`, `fim-pauta`, `clave`,
`armadura`) e completa o de `Score` (linhas `compasso`, `formula`, `barra`, `repeticao`, `volta`,
`rep-inicio`, `rep-fim`).

## Pré-requisitos

- [03](03-captura-vozes.md).

## Cria

- O engraver `captura-pauta` e o restante de `captura-score` em `ly/captura.ly`.
- `testes/ly/04-pauta.ly`.

## O que fazer

### 1. Pelas propriedades, não pelos eventos

Clave, armadura e fórmula são lidas das **propriedades do contexto** em `process-music` e emitidas
quando mudam. Não use os eventos para isso. No protótipo:

- `key-change-event` e `time-signature-event` chegam para os `\key` e `\time` do meio da peça,
  mas o `\time` do instante 0 **não chegou** ao engraver de `Staff`;
- clave não tem evento: `\clef` é um conjunto de `\set` (`clefGlyph`, `clefPosition`,
  `middleCClefPosition`, `clefTransposition`);
- arquivos antigos mudam tudo com `\set` direto.

Comparar com o último valor emitido cobre todos os casos.

### 2. Engraver de `Staff`

```scheme
#(define (captura-pauta ctx)
   (set! captura-n-pauta (1+ captura-n-pauta))
   (let ((pauta captura-n-pauta) (clave-ant #f) (arm-ant #f))
     (hashq-set! captura-pautas ctx pauta)
     (make-engraver
      ((initialize eng) (emitir ... tipo "pauta" ... contexto (symbol->string (ly:context-name ctx))))
      ((process-music eng)
       (let ((clave (list (ly:context-property ctx 'clefGlyph)
                          (ly:context-property ctx 'clefPosition)
                          (ly:context-property ctx 'clefTransposition 0)))
             (arm (list (ly:context-property ctx 'tonic)
                        (ly:context-property ctx 'keyAlterations))))
         (if (not (equal? clave clave-ant)) (begin (emitir ... "clave" ...) (set! clave-ant clave)))
         (if (not (equal? arm arm-ant)) (begin (emitir ... "armadura" ...) (set! arm-ant arm)))))
      ((finalize eng) (emitir ... "fim-pauta" ...)))))
```

Valores verificados no protótipo: clave de sol `("clefs.G" -2 ())`, de fá `("clefs.F" 2 0)`,
`treble_8` `("clefs.G" -2 -7)`. `clefTransposition` pode vir `()`: trate como 0.

`keyAlterations` vem como `((3 . 1/2))` em sol maior. A forma `((oitava . nota) . alt)` também é
possível. Serialize como diz o [contrato](01-formato-eventos.md#atributos-de-pauta).

O registro no `initialize` é obrigatório: o engraver de voz consulta `captura-pautas` já no primeiro
evento.

### 3. Engraver de `Score`, parte de tempo

Em `process-music`:

- `compasso`: no primeiro passo de tempo, quando `currentBarNumber` muda e quando `measurePosition`
  não avança (depois de uma anacruse o número continua 1; ver passo 01). Leia `measureLength`
  (racional na 2.26, não `Moment`) e `timing`.
- `formula`: `timeSignature` (um par `(3 . 4)`; a `timeSignatureFraction` está deprecada na 2.26 e avisa) quando muda.
- `barra`: `whichBar` quando é string não vazia.
- `repeticao`: `repeatCommands` quando não é `'()`. Cada comando é um símbolo
  (`start-repeat`, `end-repeat`) ou uma lista (`(volta "1.")`, `(volta #f)`). Um markup no lugar
  da string da casa vira o texto `markup->string`.

Ouvintes (verificado que chegam ao `Score` na 2.26):

| Evento | Linha | Propriedades |
|---|---|---|
| `volta-span-event` | `volta` | `span-direction` (−1 início, 1 fim), `volta-numbers` (ex.: `(1 2)`) |
| `volta-repeat-start-event` | `rep-inicio` | `repeat-count` |
| `volta-repeat-end-event` | `rep-fim` | `return-count` |

Os ouvintes rodam antes do `process-music` do mesmo passo. Emita direto no ouvinte.

### 4. Barra a cada compasso?

Não é preciso emitir barra simples. O LilyPond garante um passo de tempo em toda barra, mesmo
quando uma nota longa a atravessa (verificado: `c'1` em 2/4 gera passo de tempo em `1/2`). Então
o `compasso` sempre sai.

## Pegadinhas

- **Polimetria.** Quando o arquivo move o `Timing_translator` para o `Staff`, cada pauta tem sua
  própria fórmula. A captura lê no `Score` e perderia isso. Se `(ly:context-property ctx
  'timeSignature)` no `Staff` diferir do `Score`, emitir `aviso`. Não tratar.
- `\bar ""` (barra invisível, usada para quebra de linha) é uma string vazia: não emitir.
- `\key c \major` no meio da peça, depois de uma armadura com acidentes, emite
  `alteracoes: []`. O passo 09 precisa disso para escrever a armadura de naturais.
- `RhythmicStaff`, `TabStaff`, `DrumStaff`: não registre neles. Uma voz cuja pauta não está em
  `captura-pautas` cai na pauta `0`, e o passo 08 avisa.
- A mesma `\clef` repetida não gera linha (é o mesmo valor). Isso é o desejado.

## Como verificar

`testes/ly/04-pauta.ly`: duas pautas; `\partial 4`; `\key g \major` e, no meio, `\key d \major`
e `\key c \major`; `\time 3/4` e depois `\time 6/8`; `\clef bass` no meio da pauta de cima e
`\clef "treble_8"`; `\repeat volta 2 { } \alternative { { } { } }`; `\bar "|."` no fim; e um
`\set Score.repeatCommands = #'((volta "1.") start-repeat)` manual.

Confira: um `compasso` por compasso, com `pos` negativo no primeiro; as mudanças de clave e
armadura no `t` certo e só na pauta certa; as linhas `repeticao`, `volta`, `rep-inicio` e `rep-fim`.

Com o teste pronto, gere o [exemplo do contrato](01-formato-eventos.md#exemplo-completo) e compare.

## Pronto quando

- `04-pauta.ly` dá as linhas esperadas.
- O exemplo do passo 01 bate com a captura (ou o documento 01 foi corrigido com o motivo).
- Em `dados/fur_Elise_WoO59.ly` aparecem as linhas de repetição e casa; em
  `dados/SchumannOp15No07.ly`, notas com `pauta` diferente da pauta da voz.
