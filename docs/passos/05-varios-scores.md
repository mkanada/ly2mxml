# 05 — Vários `\score`, `\book` e só `\midi`

Fase 1. Faz a captura funcionar com qualquer arranjo de `\score` no arquivo:

- `\score` com só `\midi` (os engravers não rodam);
- vários `\score` (movimentos, ou a cópia `\unfoldRepeats` para o MIDI);
- `\score` dentro de `\book` e `\bookpart`.

Também garante que **toda** partitura capturada tenha um MIDI correspondente, para o passo 06.

## Pré-requisitos

- [02](02-envelope-e-execucao.md) a [04](04-captura-pauta-compasso.md).

## Cria

- Os handlers em `ly/captura.ly`.
- `testes/ly/05-scores.ly` e `testes/ly/05-book.ly`.

## Como o LilyPond trata os `\score`

Na 2.26 (`ly/declarations-init.ly`):

- um `\score` no topo do arquivo passa por `toplevel-score-handler`;
- um `\score` dentro de `\book` passa por `book-score-handler`;
- um `\score` dentro de `\bookpart` passa por `bookpart-score-handler`.

O envelope inclui a captura **antes** do arquivo do usuário. Então basta trocar essas três
variáveis por versões que preparam o `\score` e chamam a original.

## O que fazer

### 1. Propriedades novas de contexto

```scheme
#(for-each
  (lambda (s)
    (set-object-property! s 'translation-type? boolean?)
    (set-object-property! s 'translation-doc "ly2mxml: marcado pela captura"))
  '(capturaSoMidi))
```

Sem isso, o LilyPond recusa `capturaSoMidi = ##t` num `\context`.

### 2. Preparar cada `\score`

Regras:

| O `\score` tem | O que fazer |
|---|---|
| nenhuma definição de saída | acrescentar `\layout { }` **e** `\midi { }` (ver abaixo) |
| `\layout` e `\midi` | nada |
| só `\layout` | acrescentar `\midi { }` |
| só `\midi` | acrescentar `\layout { \context { \Score capturaSoMidi = ##t } }` |

O `\midi` acrescentado faz com que **toda** partitura capturada gere exatamente um arquivo MIDI.
Assim, a n-ésima partitura do JSON corresponde ao n-ésimo `MIDI output to` do log (passo 06).
Isso vale para o envelope. O `ly2mxml.py` (passo 10) pode desligar esse acréscimo com
`LY2MXML_SEM_MIDI=1` quando não for comparar.

Código verificado (com a linha do `\midi` a acrescentar):

```scheme
#(define (captura-tipo od)
   (module-ref (ly:output-def-scope od) 'output-def-kind #f))

#(define (captura-preparar score)
   (let* ((ods (ly:score-output-defs score))
          (tem-layout (any (lambda (od) (eq? (captura-tipo od) 'layout)) ods))
          (tem-midi (any (lambda (od) (eq? (captura-tipo od) 'midi)) ods)))
     (if (and (pair? ods) (not tem-layout))
         (ly:score-add-output-def!
          score #{ \layout { \context { \Score capturaSoMidi = ##t } } #}))
     (if (null? ods)
         (ly:score-add-output-def! score #{ \layout { } #}))
     (if (not tem-midi)
         (ly:score-add-output-def! score #{ \midi { } #}))
     score))

#(set! toplevel-score-handler
   (let ((h toplevel-score-handler)) (lambda (score) (h (captura-preparar score)))))
#(set! book-score-handler
   (let ((h book-score-handler)) (lambda (b score) (h b (captura-preparar score)))))
#(set! bookpart-score-handler
   (let ((h bookpart-score-handler)) (lambda (b score) (h b (captura-preparar score)))))
```

Um `\score` sem nenhuma definição de saída é desenhado com o `\layout` padrão, mas **só enquanto
a lista estiver vazia**. Verificado: acrescentar só o `\midi` nesse caso faz a partitura deixar de
ser desenhada, e os engravers não rodam. Por isso o `(null? ods)` acrescenta também um
`\layout { }`, e o `(pair? ods)` impede que essa partitura seja marcada `so_midi`.

O `\layout { ... }` criado dentro de `#{ #}` parte de `$defaultlayout`, que já tem os `\consists`
da captura. Não é preciso repeti-los.

### 3. Ordem e nomes dos MIDI

Verificado com `-o base`: o log tem uma linha `MIDI output to \`NOME'...` por partitura, **na
mesma ordem** em que as linhas `partitura` saem no JSON. Essa ordem é a de processamento, não a do
arquivo: um `\book` é processado quando termina de ser lido, e os `\score` do topo só no fim do
arquivo. Num arquivo com quatro `\score` no topo seguidos de um `\book`, a partitura `p = 1` é a do
`\book`.

Os nomes não seguem um padrão simples (`base.midi`, `base-1.midi`, `base-1-1.midi`...). Leia-os do
log, não os deduza.

Com `\book` **e** `\score` no topo, o LilyPond pode dar o mesmo nome a dois MIDI (verificado: o
`base-1.midi` foi escrito duas vezes). Quando o log tiver um nome repetido, o passo 06 não
compara aquele arquivo e avisa. Não tente consertar os nomes.

## Pegadinhas

- **O `\unfoldRepeats` do MIDI.** Muitas peças têm um `\score` com `\layout` e outro igual com
  `\unfoldRepeats` e só `\midi`. O segundo agora também é capturado, com `so_midi: true`. O
  leitor (passo 07) descarta as partituras `so_midi` quando há pelo menos uma sem. Elas não se
  perdem: no passo 11 servem de gabarito para a música com as repetições desdobradas.
- Peça **só** com `\midi`: a partitura `so_midi` é a única e vira o MusicXML. Se tiver
  `\unfoldRepeats`, as repetições saem desdobradas. É o melhor possível sem reescrever o arquivo.
- O cabeçalho (`\header`) do `\score` fica no objeto. A fase 5 vai lê-lo daí.
- `\book` com `\bookOutputSuffix` muda o nome do MIDI. Raro no acervo. Tratar só se aparecer.

## Como verificar

`testes/ly/05-scores.ly` (no topo, sem `\book`):

```lilypond
\score { \new Staff { c'1 } \layout { } }
\score { \new Staff { d'1 } \midi { } }
\score { \new Staff { e'1 } \layout { } \midi { } }
\score { \new Staff { f'1 } }
```

Esperado: 4 linhas `partitura`, com `so_midi` `false, true, false, false`; 4 MIDI; 4 linhas
`MIDI output to` no log. A quarta partitura (sem definição de saída) tem de ter notas.

`testes/ly/05-book.ly`: um `\score` no topo e, depois, um `\book` com 3 `\score` (só `\midi`;
`\layout` + `\midi`; nenhuma definição). Esperado: 4 partituras e 4 MIDI. As do `\book` vêm
primeiro (`p` = 1 a 3, a 1ª `so_midi`) e a do topo por último.

No acervo:

| Peça | Esperado |
|---|---|
| `KV331_1_1_tema` | 2 partituras, a 2ª `so_midi` |
| `diabeli.op163.s1-1` | 3 partituras: 2 com `\layout`, 1 `so_midi` |
| `Chop-28-2` | `theScore = \score` dentro de `\book`: 1 partitura (ou 2, se houver um `\midi` separado) |
| `sonatina-1` | 3 movimentos: 3 partituras sem `so_midi` |

## Pronto quando

- Os dois testes e as quatro peças dão o esperado.
- As 31 peças têm pelo menos uma partitura com notas.
