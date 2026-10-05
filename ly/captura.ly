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

% Contador de partituras (\score), na ordem em que o LilyPond as processa.
% Recomeça a cada execução (variável global zerada ao carregar).
#(define captura-n-partitura 0)

% Engraver de Score: por enquanto só a estrutura (partitura no initialize,
% fim no finalize com o comprimento total). A propriedade capturaSoMidi só
% passa a existir no passo 05; até lá vale #f.
#(define (captura-score ctx)
   (set! captura-n-partitura (1+ captura-n-partitura))
   (let ((p captura-n-partitura))
     (make-engraver
      ((initialize eng)
       (emitir `((tipo . "partitura") (p . ,p)
                 (so_midi . ,(eq? #t (ly:context-property ctx 'capturaSoMidi #f))))))
      ((finalize eng)
       (emitir `((tipo . "fim") (p . ,p)
                 (t . ,(fracao (ly:moment-main (ly:context-current-moment ctx))))))))))

\layout {
  \context { \Score \consists #captura-score }
}
