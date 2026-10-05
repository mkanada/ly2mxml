# 18 — Notação (opcional)

Fase 5. Tudo o que não muda as notas tocadas, mas ajuda a estudar: dinâmica, articulação,
ligadura de expressão, ornamentos, pedal, andamento, textos, `\ottava`, dedilhado e metadados.
Cada item é independente. Faça na ordem da tabela, que vai do mais útil ao menos útil para quem
estuda, e pare quando quiser.

## Pré-requisitos

- Fases 1 a 4 fechadas: o lote (passo 16) mostra que as notas estão certas. Notação em cima de
  nota errada é trabalho perdido.

## Como acrescentar um item

Sempre os mesmos quatro passos:

1. **Contrato** ([01](01-formato-eventos.md)): uma linha nova (ou um campo novo na `nota`). Subir
   o `formato` do cabeçalho.
2. **Captura**: um ouvinte a mais no engraver certo. A maioria é `Voice`. Para ver as
   propriedades de um evento, imprima `(ly:event-property ev 'xxx)` num teste mínimo, como foi
   feito nos passos 03 a 05.
3. **Leitura** ([07](07-leitura-eventos.md)): o tipo novo vira um campo do `Acorde` ou uma lista
   da `Partitura`. Linhas de tipo desconhecido já são ignoradas com aviso, então a ordem
   captura → leitura não quebra nada.
4. **Montagem**: o objeto do music21 no lugar certo. Conferir no MuseScore e no passo 17.

O `_resumo.csv` (passo 16) ganha uma coluna por item (contagem). A comparação MIDI não muda.

## Itens

| # | Item | Evento no LilyPond (`Voice`, salvo indicação) | music21 |
|---|---|---|---|
| 1 | Ligadura de expressão | `slur-event` (`span-direction`) e `phrasing-slur-event` | `spanner.Slur(n1, n2)` |
| 2 | Dinâmica | `absolute-dynamic-event` (`text`: `"p"`, `"ff"`...) | `dynamics.Dynamic("p")` |
| 3 | Crescendo/diminuendo | `crescendo-event`, `decrescendo-event` (`span-direction`) | `dynamics.Crescendo(n1, n2)` |
| 4 | Articulações | `articulation-event` (`articulation-type`: `"staccato"`, `"accent"`, `"tenuto"`, `"fermata"`, `"marcato"`...) dentro de `articulations` da nota | `articulations.Staccato()`... e `expressions.Fermata()` |
| 5 | Andamento | `tempo-change-event` (`metronome-count`, `tempo-unit`, `text`), no `Score` | `tempo.MetronomeMark` |
| 6 | Metadados | `\header` do arquivo e do `\score`: `title`, `composer`, `opus`, `piece`, `mutopiatitle`... | `metadata.Metadata` |
| 7 | Dedilhado | `fingering-event` (`digit`) em `articulations` | `articulations.Fingering(n)` |
| 8 | Ornamentos | `articulation-event` com `"trill"`, `"mordent"`, `"prall"`, `"turn"`; `arpeggio-event` | `expressions.Trill()`, `Mordent()`, `Turn()`, `ArpeggioMark()` |
| 9 | Pedal | `sustain-event` (`span-direction`), no `Staff` | `expressions.PedalMark` (music21 ≥ 9) |
| 10 | `\ottava` | propriedade `ottavation` do `Staff`, quando muda | `spanner.Ottava` (as alturas já são reais, então `transposing=False`) |
| 11 | Textos | `text-script-event` (`text`, um markup) | `expressions.TextExpression(markup->string)` |
| 12 | Feixes manuais | `beam-event` (`span-direction`) | `beam.Beams` e gravar sem recalcular os feixes daquela nota |
| 13 | Tremolo | `tremolo-event`, `tremolo-span-event` (passo 14) | `expressions.Tremolo`, `TremoloSpanner` |
| 14 | Símbolo C/₵ | `TimeSignature.style` do `Staff` | `TimeSignature.symbol` |

Os nomes dos eventos vêm do `event-listener.ly` do próprio LilyPond
(`ferramentas/lilypond/share/lilypond/2.26.0/ly/event-listener.ly`) e da lista de classes de
evento em `ferramentas/lilypond/share/lilypond/2.26.0/scm/lily/define-event-classes.scm` (todos os
da tabela existem lá, verificado). As classes do music21 da tabela também existem na 10.5
(verificado). **Confirme cada um num teste mínimo
antes de escrever o código**: alguns mudaram de nome entre versões (por exemplo, `dynamic-event`
no `event-listener.ly` de exemplo é a classe genérica; a dinâmica absoluta chega como
`absolute-dynamic-event`).

## Pegadinhas

- **Spanners entre vozes e pautas.** Uma ligadura de expressão pode começar numa pauta e terminar
  na outra (voz com `\change Staff`). No music21, o `Slur` vai na `PartStaff` da primeira nota. O
  MusicXML aceita.
- **Eventos sem nota.** Dinâmica numa pausa ou num `s` (comum em `\new Dynamics`): o
  `Dynamics` é um contexto à parte, sem `Voice`. Registrar o engraver também em `\Dynamics` e
  pôr a dinâmica no offset certo da pauta mais próxima (a de cima, no piano).
- **Markup.** Textos podem ser markups complexos. `markup->string` dá o texto puro, que basta.
- **Metadados.** Os arquivos do Mutopia têm `\header` com campos próprios (`mutopiatitle`,
  `mutopiacomposer`, `source`, `license`). Preferir `title`/`composer` e cair para os do Mutopia.
  Pôr a licença em `metadata.copyright`, porque o Mutopia pede atribuição.
- **`\ottava`**: o LilyPond já entrega as alturas reais. O `Ottava` do music21 tem de ser criado
  sem transpor as notas.

## Como verificar

Para cada item, um `testes/ly/18-ITEM.ly` com poucos compassos e o teste do XML, como nos passos
anteriores. No lote, a coluna nova não pode baixar a taxa de `ok`.

## Pronto quando

Não há fim obrigatório. Cada item está pronto quando o teste dele passa, o MuseScore mostra como
no PDF do LilyPond e o `docs/plano.md` (Fase 5) diz o que já foi feito.
