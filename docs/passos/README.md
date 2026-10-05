# Passos de implementação

O [plano](../plano.md) diz **o quê** e **por quê**. Estes documentos dizem **como**, em passos
pequenos. Cada passo pode ser feito numa sessão, sem ler os outros: ele lista o que precisa já
existir, os arquivos que cria, o que fazer, as pegadinhas conhecidas, como verificar e quando está
pronto.

Escritos em 05/10/2026, depois de testar as premissas da Fase 1 no LilyPond 2.26.0 instalado (ver
[Fatos verificados](#fatos-verificados)).

## Ordem

| # | Passo | Fase | Cria |
|---|---|---|---|
| 00 | [Convenções](00-convencoes.md) | — | (só leitura: layout, nomes, como rodar) |
| 01 | [Formato dos eventos](01-formato-eventos.md) | 1 | (contrato entre Scheme e Python) |
| 02 | [Envelope e execução](02-envelope-e-execucao.md) | 1 | `scripts/ly2json.sh`, `ly/captura.ly` (esqueleto) |
| 03 | [Captura das vozes](03-captura-vozes.md) | 1 | engraver de voz em `ly/captura.ly` |
| 04 | [Captura de pauta e compasso](04-captura-pauta-compasso.md) | 1 | engravers de pauta e de `Score` |
| 05 | [Vários `\score`, `\book` e só `\midi`](05-varios-scores.md) | 1 | handlers em `ly/captura.ly` |
| 06 | [JSON contra o MIDI](06-json-vs-midi.md) | 1 | `scripts/json-vs-midi.py` (critério da Fase 1) |
| 07 | [Leitura dos eventos em Python](07-leitura-eventos.md) | 2 | `conversor/eventos.py` |
| 08 | [Montagem básica](08-montagem-basica.md) | 2 | `conversor/montagem.py` |
| 09 | [Atributos de pauta e ligaduras](09-atributos-e-ligaduras.md) | 2 | (amplia `montagem.py`) |
| 10 | [CLI de ponta a ponta](10-cli.md) | 2 | `ly2mxml.py` |
| 11 | [Comparar MIDI](11-comparar-midi.md) | 2 | `scripts/comparar-midi.py` |
| 12 | [Quiálteras](12-quialteras.md) | 3 | |
| 13 | [Apojaturas](13-apojaturas.md) | 3 | |
| 14 | [Repetições e casas](14-repeticoes.md) | 3 | |
| 15 | [Compassos incompletos e cadenza](15-mudancas-e-cadenza.md) | 3 | |
| 16 | [Lote e regressão](16-lote.md) | 4 | `scripts/converter-todos.py` |
| 17 | [Conferência visual](17-conferencia-visual.md) | 4 | `scripts/conferir.py` |
| 18 | [Notação (opcional)](18-notacao.md) | 5 | |

Dependências: 02 → 03 → 04 → 05 → 06 fecham a Fase 1. 07 só depende do contrato (01), então
pode ser escrito em paralelo usando os JSON de exemplo do 01. 08 → 09 → 10 → 11 fecham a Fase 2.
12 a 15 são independentes entre si. 16 precisa do 10 e do 11.

## Fatos verificados

Testado com `ferramentas/lilypond/bin/lilypond` 2.26.0 em `LVB_Sonate_02no1_1.ly` e
`KV331_1_1_tema.ly`, depois do `convert-ly`:

- **`-dbackend=null` não existe na 2.26.** O LilyPond responde `invalid value; possible values are
  (ps cairo svg)` e ignora a opção. O que desliga o PDF é **`-dno-print-pages`**. O MIDI continua
  saindo.
- Um `\layout { \context { \Voice \consists #engraver } }` no topo, **antes** do `\include` do
  arquivo do usuário, vale para os `\score` que têm `\layout { }` próprio. Não é preciso editar o
  arquivo.
- Um `\score` que tem **só `\midi`** não roda engravers. Por isso a cópia `\unfoldRepeats` que
  muitas peças trazem para o MIDI não duplica eventos. Só é preciso forçar `\layout` quando o
  arquivo **não tem nenhum** `\score` com `\layout` (ver passo 05).
- `ly:context-id` de uma voz criada por `<< { } \\ { } >>` é `"1"`, `"2"`... A voz principal
  anônima tem id `""`. O id **não** distingue as vozes. É preciso um contador próprio, criado
  quando o engraver é instanciado.
- `(ly:context-find voz 'Staff)` no momento do evento devolve a pauta atual, ou seja, já segue o
  `\change Staff`.
- A altura do `note-event` já é absoluta (depois de `\relative` e `\transpose`).
- `ly:duration-scale` devolve `2/3` dentro de `\times 2/3`/`\tuplet 3/2`, e
  `ly:duration->string` dá `"16*2/3"`.
- Na apojatura, `ly:moment-grace` é negativo (`-1/16`) e `ly:moment-main` é o tempo da nota
  principal.
- `measurePosition` e `currentBarNumber` podem ser lidos do contexto de voz (são herdados do
  `Score`).
- Para saber se um `\score` tem `\layout`:
  `(eq? 'layout (module-ref (ly:output-def-scope od) 'output-def-kind #f))` para cada `od` de
  `(ly:score-output-defs score)`.
- Tempo de execução: cerca de 2,5 s por peça, com captura e MIDI.

Verificados depois, ao escrever os passos 01–18 (protótipos descartáveis, fora do repositório):

- O Guile é o 3.0.11. Uma porta aberta com o caminho de `(getenv "LY2MXML_EVENTOS")` e
  `(setvbuf porta 'line)` recebe as linhas na hora (passo 02).
- Num acorde ligado `<g b>2~`, o `tie-event` chega **depois** das notas, solto na voz. Em `<c~ e>`
  ele vem em `articulations` da nota. Os eventos de `articulations` são `Stream_event`: use
  `ly:event-property`, não `ly:music-property` (passo 03).
- `\acciaccatura` e `\slashedGrace` deixam `Flag.stroke-style = "grace"` no contexto. `\grace` e
  `\appoggiatura`, não. `\afterGrace` cai em `afterGraceFraction` da nota anterior, sem nota
  principal no mesmo `t` (passos 03 e 13).
- Clave, armadura e fórmula: ler as propriedades (`clefGlyph`, `clefPosition`, `clefTransposition`,
  `tonic`, `keyAlterations`, `timeSignatureFraction`), não os eventos. O `\time` do instante 0 não
  chegou como evento ao engraver de `Staff` (passo 04).
- `volta-repeat-start-event`, `volta-repeat-end-event` e `volta-span-event` chegam ao `Score`.
  `repeatCommands` mostra o início e o fim da repetição, mas não as casas (passos 04 e 14).
- Há um passo de tempo em toda barra, mesmo quando uma nota longa a atravessa (passo 04).
- Os `\score` passam por `toplevel-score-handler`, `book-score-handler` e
  `bookpart-score-handler`, que a captura pode trocar. `ly:score-add-output-def!` acrescenta
  `\layout`/`\midi`. Acrescentar só `\midi` a um `\score` sem definição de saída faz ele deixar de
  ser desenhado (passo 05).
- Os `\book` são processados antes dos `\score` do topo. O log tem uma linha `MIDI output to` por
  partitura, na ordem de processamento, e os nomes podem se repetir (passo 05).
- Contra o MIDI do LilyPond (`ticks_per_beat` 384), as notas principais batem exatamente. As
  diferenças são as continuações de ligadura (sem `note_on`) e as apojaturas, que o MIDI toca em
  tempos fracionários (passo 06).
- **`\repeat percent` perde a segunda vez na captura.** `\unfoldRepeats percent` resolve (passo 14).
  `\repeat tremolo 4 { c16 e }` chega como duas mínimas com escala 1/2.
- Na `\cadenzaOn`, `currentBarNumber` e `measurePosition` param, e `\bar "|"` não abre compasso
  novo (passo 15).
- music21 10.5: `PartStaff` + `StaffGroup` saem como **um** `<part>` com `<staves>2</staves>`;
  `getGrace()` dá `<grace slash="yes"/>` e as apojaturas saem antes da nota principal;
  `makeTupletBrackets` por `Voice` põe os colchetes; pausa com `hideObjectOnPrint` sai
  `print-object="no"` (passos 08, 12 e 13).
- `lilypond -dbackend=svg` dá uma SVG por página e o Verovio lê o MusicXML do music21 (passo 17).

## Recorte do acervo, por recurso

Útil para escolher a peça de teste de cada passo (contagem por `grep` no `.ly` original):

| Recurso | Peças boas para testar |
|---|---|
| simples (2 pautas, sem truques) | `bach-invention-01`, `bach-invention-02`, `wtk1-prelude1`, `gymnopedie_2`, `LiederOhneWorte_-_Op30_No6` |
| vários `\score` (layout + midi separado) | `KV331_1_1_tema`, `maple`, `intermezzo`, `No03_Albumblatt`, `5.Inquietude` |
| vários `\score` com `\layout` | `diabeli.op163.s1-1` (2 com layout + 1 só midi) |
| `\book` | `Chop-28-2` (`theScore = \score` dentro de `\book`), `sonatina-1` (3 movimentos) |
| `\include` de idioma | `25EF-01`, `Chop-28-4`, `chopin_nocturne_op9_n2`, `debussy_*`, `SchubertF-D899-2-Impromptu` |
| quiálteras | `Chop-28-1` (152), `SchubertF-D899-2-Impromptu` (195), `LVB_Sonate_02no1_1`, `debussy_*` |
| apojaturas | `LVB_Sonate_02no1_1`, `No03_Albumblatt`, `chopin_nocturne_op9_n2`, `K545-1` |
| `\repeat volta` + `\alternative` | `fur_Elise_WoO59`, `maple`, `gymnopedie_1`, `No03_Albumblatt` |
| `\afterGrace` | `LVB_Sonate_02no1_1`, `K545-1`, `LiederOhneWorte_-_Op30_No6` |
| `\cadenzaOn` | `chopin_nocturne_op9_n2` |
| outras repetições | `\repeat tremolo`: 1 uso; `\repeat unfold`: 28; `\repeat percent` e `repeatCommands` à mão: nenhum |
| `\change Staff` | `SchumannOp15No07` (8), `maple`, `5.Inquietude` |
| `\partial` | `SchubertF-D899-2-Impromptu`, `diabeli.op163.s1-1`, `intermezzo` |
| mais antigas (2.6.0) | `KV331_1_1_tema`, `SchumannOp15No07` |
