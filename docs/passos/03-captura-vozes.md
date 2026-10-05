# 03 — Captura das vozes

Fase 1. Acrescenta a `ly/captura.ly` o engraver de `Voice`, que emite as linhas `voz`, `nota`,
`pausa`, `pausa-compasso` e `quialtera` do [contrato](01-formato-eventos.md).

## Pré-requisitos

- [02](02-envelope-e-execucao.md): `ly2json.sh` roda e `captura.ly` tem `json`, `emitir`,
  `campos-tempo` e o engraver de `Score`.

## Cria

- O engraver `captura-voz` em `ly/captura.ly`.
- `testes/ly/03-vozes.ly`.

## O que fazer

### 1. Contadores por partitura

O número da voz é um contador próprio. O de pauta (passo 04) também. Os dois recomeçam a cada
partitura: guarde-os em variáveis globais zeradas no `initialize` do engraver de `Score`. O
`Score` é criado antes das pautas e das vozes da mesma partitura.

O engraver de voz precisa saber o **número** da pauta onde está, não o `id`. Use uma tabela
`(make-hash-table)` global, zerada junto com os contadores, de contexto `Staff` para número:
`hashq-set!` no engraver de pauta e `hashq-ref` no de voz. Enquanto o passo 04 não existir,
devolva `0` quando a pauta não estiver na tabela.

### 2. O engraver

Forma geral, já testada no protótipo:

```scheme
#(define (captura-voz ctx)
   (set! captura-n-voz (1+ captura-n-voz))
   (let ((voz captura-n-voz)
         (notas '())          ; notas do passo de tempo atual, em ordem inversa
         (lig-acorde #f))     ; houve tie-event solto neste passo de tempo
     (make-engraver
      ((initialize eng) (emitir ... tipo "voz" ...))
      (listeners
       ((note-event eng ev) (set! notas (cons ev notas)))
       ((tie-event eng ev) (set! lig-acorde #t))
       ((rest-event eng ev) (emitir ...))
       ((multi-measure-rest-event eng ev) (emitir ...))
       ((tuplet-span-event eng ev) (emitir ...)))
      ((stop-translation-timestep eng)
       (for-each (lambda (ev) (emitir-nota ev lig-acorde)) (reverse notas))
       (set! notas '())
       (set! lig-acorde #f)))))
```

As notas **ficam guardadas** até o `stop-translation-timestep` porque, num acorde ligado
`<g b>2~`, o `tie-event` do acorde chega **depois** das notas (verificado). Só no fim do passo de
tempo se sabe se a ligadura vale para elas.

`emitir-nota`:

- altura: `(ly:event-property ev 'pitch)`, com `ly:pitch-octave`, `ly:pitch-notename`,
  `ly:pitch-alteration` e `ly:pitch-semitones`. Se não for `ly:pitch?` (percussão, `drum-type`),
  emitir `aviso` e pular a nota.
- duração: `(ly:event-property ev 'duration)`, com `ly:duration-log`, `ly:duration-dot-count`,
  `ly:duration-scale` e `ly:duration->moment` (passar o resultado por `ly:moment-main`).
- `lig`: `lig-acorde` **ou** existe, em `(ly:event-property ev 'articulations)`, um evento cuja
  `(ly:event-property a 'class)` contém `tie-event`. Isso cobre `<c~ e>` (só o dó ligado).
- `pauta`: `(hashq-ref pautas (ly:context-find ctx 'Staff) 0)`, lida **na hora** da nota. Assim
  ela segue o `\change Staff`.
- apojatura: se `(ly:moment-grace momento)` não for zero, acrescentar
  `barra = (equal? "grace" (assoc-get 'stroke-style (ly:context-grob-definition ctx 'Flag) #f))`.
  Verificado: `\acciaccatura` e `\slashedGrace` dão `"grace"`; `\grace` e `\appoggiatura` dão
  `#f`.

`quialtera`: no `tuplet-span-event`, `span-direction` −1 é início e 1 é fim. No início, a razão
impressa vem das propriedades `numerator`/`denominator` do evento, que guardam a **escala**
(2 e 3 para uma tercina). Inverta para `num = 3, den = 2`. Confira no teste e, se não for assim,
use o inverso de `ly:duration-scale` da primeira nota da quiáltera.

### 3. Registrar

```lilypond
\layout {
  \context { \Score \consists #captura-score }
  \context { \Voice \consists #captura-voz }
}
```

Só `\Voice`. `CueVoice` (notas de deixa) e `NullVoice` (alinhamento de letra) **não** devem
entrar: elas não soam. `DrumVoice` também fica de fora.

## Pegadinhas

- Um `\new Voice` por compasso (comum em peças geradas por programa) cria muitas vozes. Isso é
  normal. O passo 08 junta as vozes de mesma pauta que não se sobrepõem.
- Uma voz criada por `<< { } \\ { } >>` tem a vida do bloco `<< >>`. Depois dele, a música volta
  para a voz de antes (que tem o mesmo número de sempre).
- O `skip-event` (`s4`) não deve gerar linha. Mas a voz com só `s` ainda gera a linha `voz`, e o
  passo 08 a descarta se não tiver nenhuma nota nem pausa.
- `\partcombine` (`\partCombine`) cria vozes `one`, `two`, `shared` e `solo`, e as notas de uníssono
  aparecem uma vez só. Se alguma peça do acervo usar, anotar em `docs/plano.md`. Não tratar agora.
- `\tuplet` aninhado: as escalas se multiplicam (`ly:duration-scale` já é o produto). Os eventos
  `quialtera` saem aninhados.

## Como verificar

`testes/ly/03-vozes.ly` deve ter, num `\score` com `\layout { }`:

- acorde `<c e g>4`, acorde ligado `<g b>2~ q8`, ligadura só em uma nota `<c~ e>2 c`;
- `<< { d2 } \\ { b,2 } >>` e um `\new Voice { f2 }`;
- `\change Staff = "down"` no meio da voz de cima;
- `\tuplet 3/2 { a16 b c }`, `R2.*2`, `r8` e `s4`;
- `\grace d8`, `\acciaccatura e8`, `\appoggiatura f8`.

Confira à mão: o número de linhas `nota` é o de cabeças de nota; a `pauta` muda depois do
`\change Staff`; `lig` é `true` só nas notas certas; a `quialtera` abre e fecha; `barra` só na
`\acciaccatura`.

Numa peça real: `dados/bach-invention-01.ly` deve dar 467 linhas `nota` (contagem do protótipo,
sem descontar ligaduras).

## Pronto quando

- O teste acima bate linha por linha com o esperado escrito à mão.
- As 31 peças rodam sem erro de Scheme e todas têm notas em alguma voz.
