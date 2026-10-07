\version "2.26.0"
% ly/captura.ly — captura de eventos para o ly2mxml (passo 02: esqueleto).
% O envelope gerado por scripts/ly2json.sh inclui este arquivo antes do .ly
% do usuário. Os engravers de verdade entram nos passos 03 a 05; por enquanto
% só sai o cabeçalho, uma linha por partitura (\score) e o fim.

% Porta onde as linhas JSONL são escritas. O caminho vem da variável de
% ambiente LY2MXML_EVENTOS (ver scripts/ly2json.sh). Sem a variável, escreve
% em stderr, para testar à mão. Cada linha sai na hora (buffer de linha),
% mesmo se o LilyPond morrer no meio.
#(define captura-porta
   (let ((caminho (getenv "LY2MXML_EVENTOS")))
     (if caminho
         (let ((p (open-output-file caminho)))
           (setvbuf p 'line)
           p)
         (current-error-port))))

% Escapa uma string para JSON (aspas, barra e controles).
#(define (json-escape s)
   (let ((n (string-length s)))
     (let loop ((i 0) (partes '()))
       (if (>= i n)
           (apply string-append (reverse partes))
           (let ((ch (string-ref s i)))
             (cond ((char=? ch #\") (loop (1+ i) (cons "\\\"" partes)))
                   ((char=? ch #\\) (loop (1+ i) (cons "\\\\" partes)))
                   ((char=? ch #\newline) (loop (1+ i) (cons "\\n" partes)))
                   ((char=? ch #\return) (loop (1+ i) (cons "\\r" partes)))
                   ((char=? ch #\tab) (loop (1+ i) (cons "\\t" partes)))
                   ((char<? ch #\space)
                    (loop (1+ i) (cons (format #f "\\u~4,'0x" (char->integer ch)) partes)))
                   (else (loop (1+ i) (cons (string ch) partes)))))))))

% Junta strings com um separador (evita depender de módulo extra).
#(define (json-juntar partes sep)
   (if (null? partes)
       ""
       (let loop ((resto (cdr partes)) (acc (car partes)))
         (if (null? resto)
             acc
             (loop (cdr resto) (string-append acc sep (car resto)))))))

% Marca uma alist como objeto JSON. Sem o marcador não dá para distinguir
% lista (array) de alist (objeto): (objeto '((tipo . "nota") ...)).
#(define (objeto alist) (cons '@objeto alist))

#(define (json-objeto alist)
   (string-append
    "{"
    (json-juntar
     (map (lambda (par)
            (string-append (json (symbol->string (car par))) ":" (json (cdr par))))
          alist)
     ",")
    "}"))

% Serializa um valor para JSON. Racional exato vira string entre aspas, mas
% só quem decide isso é (fracao x): aqui o racional já chega como string.
% Inteiros (c, fig, voz, etc.) ficam números. '() vira [].
#(define (json x)
   (cond ((string? x) (string-append "\"" (json-escape x) "\""))
         ((boolean? x) (if x "true" "false"))
         ((integer? x) (number->string x))
         ((rational? x) (string-append "\"" (format #f "~a" x) "\""))
         ((null? x) "[]")
         ((and (pair? x) (eq? (car x) '@objeto)) (json-objeto (cdr x)))
         ((list? x) (string-append "[" (json-juntar (map json x) ",") "]"))
         ((pair? x) (string-append "[" (json (car x)) "," (json (cdr x)) "]"))
         ((symbol? x) (if (eq? x 'null) "null" (string-append "\"" (symbol->string x) "\"")))
         (else (error "json: tipo nao suportado" x))))

% Formata um tempo exato (racional na unidade semibreve) como string de
% fração: "0", "3/4", "-1/16". É o que vai no JSON (ver passo 01).
#(define (fracao x) (format #f "~a" x))

% Escreve uma linha JSONL na porta da captura.
#(define (emitir campos)
   (display (json (objeto campos)) captura-porta)
   (display "\n" captura-porta))

% Campos de tempo de um contexto: t (momento principal), g (apojatura),
% c (número do compasso) e pos (posição no compasso). Usado pelos engravers
% dos passos 03 e 04; já fica pronto aqui.
#(define (campos-tempo ctx)
   (let* ((mom (ly:context-current-moment ctx))
          (t (ly:moment-main mom))
          (g (ly:moment-grace mom))
          (c (ly:context-property ctx 'currentBarNumber 1))
          (pos-obj (ly:context-property ctx 'measurePosition (ly:make-moment 0)))
          (pos (if (ly:moment? pos-obj) (ly:moment-main pos-obj) pos-obj)))
     `((t . ,(fracao t)) (g . ,(fracao g)) (c . ,c) (pos . ,(fracao pos)))))

% Primeira linha do arquivo, uma vez só, quando este arquivo é carregado
% (antes do .ly do usuário, que vem depois no envelope).
#(emitir `((tipo . "cabecalho") (formato . 1) (lilypond . ,(lilypond-version))))

% Contadores por partitura (passo 03): voz e pauta recomeçam a cada `\score`.
% São zerados no `initialize` do engraver de `Score`, criado antes das pautas
% e das vozes da mesma partitura.
#(define captura-n-partitura 0)
#(define captura-n-voz 0)
#(define captura-n-pauta 0)
% De contexto `Staff` para número da pauta. O engraver de pauta (passo 04)
% registra aqui; a voz consulta na hora do evento (segue o `\change Staff`).
% Pautas que não são `Staff` (RhythmicStaff, TabStaff...) não entram: a voz
% delas cai na pauta 0 (o passo 08 avisa).
#(define captura-pautas (make-hash-table))

% Número da pauta onde a voz está agora (0 se a pauta não foi registrada).
#(define (captura-pauta-de ctx)
   (let ((st (ly:context-find ctx 'Staff)))
     (if st (hashq-ref captura-pautas st 0) 0)))

% Campos comuns de um evento de voz: p, voz, pauta + t, g, c, pos.
#(define (campos-voz ctx voz)
   (append `((p . ,captura-n-partitura) (voz . ,voz)
             (pauta . ,(captura-pauta-de ctx)))
           (campos-tempo ctx)))

% Os campos de duração de uma nota, pausa ou pausa de compasso.
#(define (captura-duracao-campos dur)
   `((fig . ,(ly:duration-log dur))
     (pontos . ,(ly:duration-dot-count dur))
     (escala . ,(fracao (ly:duration-scale dur)))
     (dur . ,(fracao (ly:moment-main (ly:duration->moment dur))))))

% Verdade se alguma articulação da nota é ligadura de prolongamento.
% Cobre `<c~ e>`: só o dó tem o `tie-event` nas articulações.
#(define (captura-tem-ligadura? ev)
   (let ((arts (ly:event-property ev 'articulations)))
     (if (and (pair? arts)
              (any (lambda (a)
                     (let ((c (ly:event-property a 'class)))
                       (and (list? c) (member 'tie-event c))))
                   arts))
         #t
         #f)))

#(define (emitir-nota ctx voz ev lig-acorde)
   (let ((pitch (ly:event-property ev 'pitch)))
     (if (not (ly:pitch? pitch))
         ;; Percussão (`drum-type`): sem altura, não entra no MusicXML.
         (emitir `((tipo . "aviso") (p . ,captura-n-partitura)
                   (t . ,(fracao (ly:moment-main (ly:context-current-moment ctx))))
                   (texto . "nota sem altura (percussao?) ignorada")))
         (let* ((dur (ly:event-property ev 'duration))
                (mom (ly:context-current-moment ctx))
                (em-graca (not (zero? (ly:moment-grace mom))))
                (def-flag (ly:context-grob-definition ctx 'Flag))
                (cortada (equal? "grace"
                                 (assoc-get 'stroke-style (if (pair? def-flag) def-flag '()) #f)))
                (base (append `((tipo . "nota"))
                              (campos-voz ctx voz)
                              `((altura . ,(objeto `((oitava . ,(ly:pitch-octave pitch))
                                                    (nota . ,(ly:pitch-notename pitch))
                                                    (alt . ,(fracao (ly:pitch-alteration pitch))))))
                                (midi . ,(+ 60 (ly:pitch-semitones pitch))))
                              (captura-duracao-campos dur)
                              `((lig . ,(if (or lig-acorde (captura-tem-ligadura? ev)) #t #f))))))
           ;; `barra` só aparece como true, na apojatura cortada
           ;; (`\acciaccatura`, `\slashedGrace`); ver passo 01.
           (emitir (if (and em-graca cortada)
                       (append base `((barra . #t)))
                       base))))))

#(define (emitir-pausa ctx voz ev)
   (emitir (append `((tipo . "pausa"))
                   (campos-voz ctx voz)
                   (captura-duracao-campos (ly:event-property ev 'duration)))))

#(define (emitir-pausa-compasso ctx voz ev)
   (emitir (append `((tipo . "pausa-compasso"))
                   (campos-voz ctx voz)
                   (captura-duracao-campos (ly:event-property ev 'duration)))))

#(define (emitir-quialtera ctx voz ev)
   (if (= (ly:event-property ev 'span-direction) -1)
       ;; No início, o evento guarda a escala (2 e 3 numa tercina);
       ;; a razão impressa é o inverso: 3/2.
       (emitir (append `((tipo . "quialtera"))
                       (campos-voz ctx voz)
                       `((dir . "inicio")
                         (num . ,(ly:event-property ev 'denominator))
                         (den . ,(ly:event-property ev 'numerator)))))
       (emitir (append `((tipo . "quialtera"))
                       (campos-voz ctx voz)
                       `((dir . "fim") (num . null) (den . null))))))

% Engraver de `Voice` (passo 03): linhas `voz`, `nota`, `pausa`,
% `pausa-compasso` e `quialtera`. As notas esperam até o
% `stop-translation-timestep` porque, num acorde ligado `<g b>2~`, o
% `tie-event` do acorde chega depois das notas, solto na voz.
#(define (captura-voz ctx)
   (set! captura-n-voz (1+ captura-n-voz))
   (let ((voz captura-n-voz)
         (notas '())
         (lig-acorde #f))
     (make-engraver
      ((initialize eng)
       (emitir `((tipo . "voz") (p . ,captura-n-partitura) (voz . ,voz)
                (id . ,(ly:context-id ctx))
                (pauta . ,(captura-pauta-de ctx))
                (t . ,(fracao (ly:moment-main (ly:context-current-moment ctx)))))))
      (listeners
       ((note-event eng ev) (set! notas (cons ev notas)))
       ((tie-event eng ev) (set! lig-acorde #t))
       ((rest-event eng ev) (emitir-pausa ctx voz ev))
       ((multi-measure-rest-event eng ev) (emitir-pausa-compasso ctx voz ev))
       ((tuplet-span-event eng ev) (emitir-quialtera ctx voz ev)))
      ((stop-translation-timestep eng)
       (for-each (lambda (ev) (emitir-nota ctx voz ev lig-acorde)) (reverse notas))
       (set! notas '())
       (set! lig-acorde #f)))))

% Campos de tempo de um contexto de pauta: p + t, g, c, pos.
#(define (campos-pauta ctx pauta)
   (append `((p . ,captura-n-partitura) (pauta . ,pauta))
           (campos-tempo ctx)))

% Altura de `tonic` como objeto JSON. Sem `tonic` válido, vale dó.
#(define (captura-tonica pitch)
   (if (ly:pitch? pitch)
       (objeto `((oitava . ,(ly:pitch-octave pitch))
                 (nota . ,(ly:pitch-notename pitch))
                 (alt . ,(fracao (ly:pitch-alteration pitch)))))
       (objeto `((oitava . 0) (nota . 0) (alt . "0")))))

% `keyAlterations` como lista de [nota, alt] ou, se a alteração vem presa a
% uma oitava (`((oitava . nota) . alt)`), [nota, alt, oitava].
#(define (captura-alteracoes alts)
   (map (lambda (a)
          (let ((chave (car a)) (alt (fracao (cdr a))))
            (if (pair? chave)
                (list (cdr chave) alt (car chave))
                (list chave alt))))
        (if (list? alts) alts '())))

% Engraver de `Staff` (passo 04): linhas `pauta`, `clave`, `armadura` e
% `fim-pauta`. Clave e armadura saem das propriedades do contexto, e só
% quando mudam (cobre `\clef`, `\key` e os `\set` diretos de arquivos antigos).
#(define (captura-pauta ctx)
   (set! captura-n-pauta (1+ captura-n-pauta))
   (let ((pauta captura-n-pauta)
         (clave-ant #f)
         (arm-ant #f)
         (avisou-formula #f))
     ;; O registro tem de vir já no initialize: a voz consulta a tabela no
     ;; primeiro evento.
     (hashq-set! captura-pautas ctx pauta)
     (make-engraver
      ((initialize eng)
       (emitir `((tipo . "pauta") (p . ,captura-n-partitura) (pauta . ,pauta)
                 (id . ,(ly:context-id ctx))
                 (contexto . ,(symbol->string (ly:context-name ctx)))
                 (t . ,(fracao (ly:moment-main (ly:context-current-moment ctx)))))))
      ((process-music eng)
       (let* ((glifo (ly:context-property ctx 'clefGlyph))
              (posicao (ly:context-property ctx 'clefPosition))
              (transp (ly:context-property ctx 'clefTransposition 0))
              (transp (if (integer? transp) transp 0))
              (clave (list glifo posicao transp))
              (tonic (ly:context-property ctx 'tonic))
              (alts (ly:context-property ctx 'keyAlterations))
              (arm (list tonic alts))
              (score (ly:context-find ctx 'Score))
              (formula-pauta (ly:context-property ctx 'timeSignature))
              (formula-score (and score (ly:context-property score 'timeSignature))))
         (if (and (string? glifo) (not (equal? clave clave-ant)))
             (begin
               (set! clave-ant clave)
               (emitir (append `((tipo . "clave"))
                               (campos-pauta ctx pauta)
                               `((glifo . ,glifo) (posicao . ,posicao)
                                 (transp . ,transp))))))
         (if (not (equal? arm arm-ant))
             (begin
               (set! arm-ant arm)
               (emitir (append `((tipo . "armadura"))
                               (campos-pauta ctx pauta)
                               `((tonica . ,(captura-tonica tonic))
                                 (alteracoes . ,(captura-alteracoes alts)))))))
         ;; Polimetria: a captura lê a fórmula no Score e perderia a da pauta.
         (if (and (not avisou-formula)
                  (pair? formula-pauta) (pair? formula-score)
                  (not (equal? formula-pauta formula-score)))
             (begin
               (set! avisou-formula #t)
               (emitir `((tipo . "aviso") (p . ,captura-n-partitura)
                         (t . ,(fracao (ly:moment-main (ly:context-current-moment ctx))))
                         (texto . "formula de compasso diferente por pauta (polimetria) nao tratada")))))))
      ((finalize eng)
       (emitir `((tipo . "fim-pauta") (p . ,captura-n-partitura) (pauta . ,pauta)
                 (t . ,(fracao (ly:moment-main (ly:context-current-moment ctx))))))))))

% Um comando de `repeatCommands` para JSON: símbolo vira ["start-repeat"],
% `(volta "1.")` vira ["volta","1."] e `(volta #f)` vira ["volta",false].
% Um markup no lugar do texto da casa vira texto puro.
#(define (captura-comando-repeticao cmd)
   (cond ((symbol? cmd) (list (symbol->string cmd)))
         ((pair? cmd)
          (map (lambda (x)
                 (cond ((symbol? x) (symbol->string x))
                       ((or (string? x) (boolean? x) (number? x)) x)
                       ((markup? x) (markup->string x))
                       (else (format #f "~a" x))))
               cmd))
         (else (list (format #f "~a" cmd)))))

% Engraver de Score: partitura/fim (passo 02), zeramento dos contadores
% (passo 03) e a parte de tempo (passo 04): `compasso`, `formula`, `barra`,
% `repeticao` e os ouvintes de `volta`, `rep-inicio` e `rep-fim`.
% A propriedade capturaSoMidi só passa a existir no passo 05; até lá vale #f.
#(define (captura-score ctx)
   (set! captura-n-partitura (1+ captura-n-partitura))
   (let ((p captura-n-partitura)
         (compasso-ant #f)
         (pos-ant #f)
         (formula-ant #f))
     (make-engraver
      ((initialize eng)
       (set! captura-n-voz 0)
       (set! captura-n-pauta 0)
       (set! captura-pautas (make-hash-table))
       (emitir `((tipo . "partitura") (p . ,p)
                 (so_midi . ,(eq? #t (ly:context-property ctx 'capturaSoMidi #f))))))
      (listeners
       ((volta-span-event eng ev)
        (emitir (append `((tipo . "volta") (p . ,p))
                        (campos-tempo ctx)
                        `((dir . ,(if (= (ly:event-property ev 'span-direction) -1)
                                      "inicio" "fim"))
                          (numeros . ,(let ((n (ly:event-property ev 'volta-numbers '())))
                                        (if (list? n) n '())))))))
       ((volta-repeat-start-event eng ev)
        (emitir (append `((tipo . "rep-inicio") (p . ,p))
                        (campos-tempo ctx)
                        `((vezes . ,(ly:event-property ev 'repeat-count 2))))))
       ((volta-repeat-end-event eng ev)
        (emitir (append `((tipo . "rep-fim") (p . ,p))
                        (campos-tempo ctx)
                        `((volta . ,(ly:event-property ev 'return-count 1)))))))
      ((process-music eng)
       (let* ((c (ly:context-property ctx 'currentBarNumber 1))
             (pos-obj (ly:context-property ctx 'measurePosition (ly:make-moment 0)))
             (pos (if (ly:moment? pos-obj) (ly:moment-main pos-obj) pos-obj))
             (formula (ly:context-property ctx 'timeSignature))
             (barra (ly:context-property ctx 'whichBar))
             (cmds (ly:context-property ctx 'repeatCommands '())))
         ;; Compasso novo: no primeiro passo, quando `currentBarNumber` muda e
         ;; quando `measurePosition` não avança (volta a 0 ou cai, como no
         ;; `\partial`). Só o número não basta: depois de uma anacruse ele
         ;; continua 1 no primeiro compasso cheio.
         (if (or (not (equal? c compasso-ant))
                 (and pos-ant (< pos pos-ant))
                 (and pos-ant (< pos-ant 0) (>= pos 0)))
             (let* ((ml (ly:context-property ctx 'measureLength 1))
                    ;; Na 2.26 é racional; em versões antigas era Moment.
                    (tam (if (ly:moment? ml) (ly:moment-main ml) ml)))
               (emitir (append `((tipo . "compasso") (p . ,p))
                               (campos-tempo ctx)
                               `((tam . ,(fracao tam))
                                 (medindo . ,(if (ly:context-property ctx 'timing #t) #t #f)))))))
         (set! compasso-ant c)
         (set! pos-ant pos)
         (if (and (pair? formula) (not (equal? formula formula-ant)))
             (begin
               (set! formula-ant formula)
               (emitir (append `((tipo . "formula") (p . ,p))
                               (campos-tempo ctx)
                               `((num . ,(car formula)) (den . ,(cdr formula)))))))
         ;; `\bar ""` (barra invisível) é string vazia: não vale.
         (if (and (string? barra) (not (string-null? barra)))
             (emitir (append `((tipo . "barra") (p . ,p))
                             (campos-tempo ctx)
                             `((glifo . ,barra)))))
         (if (and (pair? cmds) (list? cmds))
             (emitir (append `((tipo . "repeticao") (p . ,p))
                             (campos-tempo ctx)
                             `((cmds . ,(map captura-comando-repeticao cmds))))))))
      ((finalize eng)
       (emitir `((tipo . "fim") (p . ,p)
                 (t . ,(fracao (ly:moment-main (ly:context-current-moment ctx))))))))))

\layout {
  \context { \Score \consists #captura-score }
  \context { \Staff \consists #captura-pauta }
  \context { \Voice \consists #captura-voz }
}
