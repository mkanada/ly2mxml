# 02 — Envelope e execução

Fase 1. Monta o caminho `.ly → convert-ly → lilypond + captura → .eventos.jsonl + .midi`, com uma
captura ainda vazia: só o cabeçalho, as partituras e o fim. Os engravers de verdade entram nos
passos 03 a 05.

## Pré-requisitos

- [00](00-convencoes.md) e [01](01-formato-eventos.md).
- `ferramentas/lilypond` instalado (`scripts/instalar-lilypond.sh`).

## Cria

- `ly/captura.ly`: o esqueleto da captura.
- `scripts/ly2json.sh`: `ly2json.sh ARQ.ly [SAIDA_DIR]`.
- `testes/ly/02-minimo.ly`.

## O que fazer

### 1. O envelope

O arquivo que o `lilypond` compila não é o do usuário, e sim um envelope gerado no diretório
temporário:

```lilypond
\version "2.26.0"
\include "/caminho/absoluto/ly/captura.ly"
\include "/tmp/xxx/arquivo-2.26.ly"
```

A ordem importa: tudo o que a captura define (o `\layout { \context { ... \consists ... } }` e os
handlers) precisa existir **antes** de o arquivo do usuário ser lido. Já se verificou que um
`\layout` no topo, antes do `\include`, vale para os `\score` que têm `\layout { }` próprio.

### 2. `scripts/ly2json.sh`

Passos, com `set -euo pipefail`:

1. `RAIZ` = diretório do repositório (a partir de `$0`), `LY=$RAIZ/ferramentas/lilypond/bin`.
2. `TMP=$(mktemp -d)` e `trap 'rm -rf "$TMP"' EXIT`.
3. `"$LY/convert-ly" "$ARQ" > "$TMP/$BASE-2.26.ly" 2> "$TMP/convert.log"`. O `convert-ly` sem `-e`
   escreve o resultado em stdout e não toca no original. Se ele falhar, mostrar o log e sair com
   status 2.
4. Gerar `$TMP/envelope.ly` como acima.
5. Rodar:

   ```bash
   LY2MXML_EVENTOS="$SAIDA/$BASE.eventos.jsonl" \
     "$LY/lilypond" -dno-print-pages -I "$(dirname "$ARQ")" \
     -o "$TMP/$BASE" "$TMP/envelope.ly" 2> "$TMP/lilypond.log"
   ```

   - `-dno-print-pages`: sem PDF. **Não** `-dbackend=null`.
   - `-I` com o diretório do original: alguns arquivos fazem `\include "outro.ly"` relativo, e a
     cópia convertida está em outro lugar.
   - `-o "$TMP/$BASE"`: os MIDI saem como `$BASE.midi`, `$BASE-1.midi`...
   - O caminho do JSON vai pela **variável de ambiente** `LY2MXML_EVENTOS`, lida em Scheme com
     `(getenv "LY2MXML_EVENTOS")`. É mais simples que `-e` e não depende do nome do envelope.
6. Copiar os `.midi` de `$TMP` para `$SAIDA` e o `lilypond.log` para `$SAIDA/$BASE.lilypond.log`
   (o passo 06 lê dele a ordem dos MIDI).
7. Status: 0 se o `lilypond` terminou bem; senão, mostrar as linhas `error:` do log e sair com
   status 3. Um `warning:` não é falha.

`SAIDA_DIR` padrão: o diretório atual. Nada é escrito ao lado do original.

### 3. Esqueleto de `ly/captura.ly`

```scheme
\version "2.26.0"

#(define captura-porta
   (let ((caminho (getenv "LY2MXML_EVENTOS")))
     (if caminho
         (let ((p (open-output-file caminho)))
           (setvbuf p 'line)
           p)
         (current-error-port))))
```

- Sem a variável, escrever em stderr. Ajuda a testar à mão.
- `setvbuf ... 'line` garante que cada linha chegue ao arquivo mesmo se o LilyPond morrer no meio.
  Não confie em fechar a porta no fim.

Funções básicas, todas neste arquivo:

- `(json x)`: serializa string (com escape), inteiro, racional exato (como string, ver 01),
  booleano, `'()` como `[]`, lista como array e alist com chaves símbolo como objeto. Para
  distinguir lista de alist, use um marcador explícito: `(objeto '((tipo . "nota") ...))` devolve
  um registro que `json` sabe tratar como objeto. Um racional vira string **só** quando passado
  por `(fracao x)`. Inteiros que são contagens (`c`, `fig`, `voz`) ficam números.
- `(emitir campos)`: escreve `(json (objeto campos))` + `"\n"` em `captura-porta`.
- `(campos-tempo ctx)`: devolve a alist de `t`, `g`, `c`, `pos` a partir de
  `(ly:context-current-moment ctx)`, `currentBarNumber` e `measurePosition`.

Engraver de `Score`, por enquanto só com a estrutura:

```scheme
#(define captura-n-partitura 0)

#(define (captura-score ctx)
   (set! captura-n-partitura (1+ captura-n-partitura))
   (let ((p captura-n-partitura))
     (make-engraver
      ((initialize eng)
       (emitir `((tipo . "partitura") (p . ,p)
                 (so_midi . ,(eq? #t (ly:context-property ctx 'capturaSoMidi #f))))))
      ((finalize eng)
       (emitir `((tipo . "fim") (p . ,p)
                 (t . ,(fracao (ly:moment-main (ly:context-current-moment ctx)))))))))))

\layout {
  \context { \Score \consists #captura-score }
}
```

A propriedade `capturaSoMidi` só passa a existir no passo 05. Até lá, `#f`.

A linha `cabecalho` sai quando o arquivo é carregado, num `#(emitir ...)` no topo de
`captura.ly`. A versão vem de `(lilypond-version)`.

## Pegadinhas

- O `lilypond` escreve o progresso em **stderr**. O que a captura escreve com `format #t` vai
  para stdout, fora de ordem com o stderr. Use sempre a porta da captura.
- A captura é um `\include`: um erro de Scheme nela aparece no log como erro no `init.ly`
  (`Guile signaled an error for the expression beginning here`). Leia a linha
  `In procedure ...` logo abaixo.
- Eventos dentro de `articulations` são `Stream_event`, não `Music`: use `ly:event-property`, não
  `ly:music-property` (já deu erro no protótipo).
- O Guile é o 3.0.11. `assoc-get`, `filter`, `any` e quasiquote estão disponíveis.
- Arquivos do Mutopia às vezes têm `\paper { }` com fontes ou tamanhos estranhos. Com
  `-dno-print-pages` a paginação ainda roda, mas não é escrita. Se uma peça demorar muito, veja se
  é a paginação, e não a captura.

## Como verificar

```bash
scripts/ly2json.sh testes/ly/02-minimo.ly /tmp/t && cat /tmp/t/02-minimo.eventos.jsonl
```

`02-minimo.ly`: um `\score` com `{ c'1 }` e `\layout { }`. Deve sair:

```json
{"tipo":"cabecalho","formato":1,"lilypond":"2.26.0"}
{"tipo":"partitura","p":1,"so_midi":false}
{"tipo":"fim","p":1,"t":"1"}
```

Depois, com `dados/LVB_Sonate_02no1_1.ly` (2.10.3, passa pelo `convert-ly`): status 0, uma
partitura e um `.midi` no diretório de saída. O tempo deve ficar em torno de 2,5 s.

## Pronto quando

- `ly2json.sh` roda nas duas entradas acima e nas 31 peças de `dados/` sem erro de Scheme. As
  peças que o `lilypond` não compila mesmo depois do `convert-ly` são anotadas em `docs/plano.md`
  (Fase 1).
- O original em `dados/` continua intacto (`git status` não vale porque está fora do git:
  confira com `sha256sum` antes e depois em uma peça).
