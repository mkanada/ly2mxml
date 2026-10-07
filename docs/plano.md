# Plano do ly2mxml (LilyPond → MusicXML)

Plano escrito em 04/10/2026, antes de qualquer código.

## Objetivo

Converter partituras de **piano solo** do **Mutopia** e de outros acervos públicos (`.ly` de várias
versões, de 2.0 a 2.26) em MusicXML **para tocar e estudar**. O resultado precisa ter as notas
certas: alturas, ritmo, vozes, compassos, fórmula de compasso, armadura, claves, ligaduras de
prolongamento, quiálteras, apojaturas, repetições e casas. Dinâmica, articulação e texto ficam para
uma fase opcional. O layout (quebras, posições) está fora do escopo.

O MusicXML gerado deve servir às mesmas ferramentas do Hymn_Grabber: MuseScore, o classificador de
dificuldade e as lições de teclado.

## Por que não um parser de `.ly`

LilyPond é uma linguagem de programação, não um formato de dados. Os arquivos do Mutopia usam
variáveis, `\relative`, `\transpose`, `\include`, `\repeat`, `\partial`, `\grace`, funções em Scheme
e sintaxe que mudou entre versões (o `LVB_Sonate_02no1_1.ly` é 2.10.3 e usa `\times` e
`#'transparent`). Um parser próprio, ou o `python-ly` do Frescobaldi, só cobre arquivos simples.

## Arquitetura: o LilyPond interpreta, o Python escreve

```
arquivo.ly ──convert-ly──▶ arquivo-2.26.ly ──lilypond + captura.ly──▶ eventos.json ──python──▶ arquivo.musicxml
                                               └──────────────────────▶ arquivo.midi (gabarito)
```

1. **Atualização**: `convert-ly` leva o arquivo para a sintaxe 2.26. Ele fica numa cópia
   temporária; o original não é alterado.
2. **Captura (Scheme)**: um arquivo-envelope inclui `ly/captura.ly` e depois o `.ly` do usuário. A
   captura acrescenta engravers às pautas e vozes. Em vez de desenhar, eles gravam cada evento já
   resolvido pelo LilyPond:
   - em cada voz: nota (altura absoluta, já depois de `\relative` e `\transpose`), pausa, pausa de
     compasso, duração com fator de quiáltera, início e fim de ligadura de prolongamento, apojatura,
     acorde;
   - em cada pauta: clave, armadura, fórmula de compasso, barra (incluindo repetição e
     `repeatCommands` das casas), `\partial`;
   - o momento de cada evento (tempo principal + tempo da apojatura), o compasso e a posição no
     compasso, e os ids da pauta e da voz (`Staff = "up"`, voz `\\`, etc.).

   O ponto de partida é o `ly/event-listener.ly` que vem com o LilyPond e faz quase isso para os
   testes dele. Roda com `-dbackend=null`, então nada é desenhado e o processo é rápido. A saída é
   uma linha JSON por evento.
3. **Montagem (Python)**: lê o JSON e constrói o MusicXML. Uma parte de piano com 2 pautas, e as
   vozes do LilyPond viram `<voice>` dentro de cada pauta. A montagem usa o music21, como no
   Hymn_Grabber, para dividir notas na barra, calcular feixes e escrever o XML. A saída é
   reprodutível: ids fixos e sem data.
4. **Gabarito**: o mesmo `lilypond` gera o MIDI do arquivo. Converter o MusicXML para MIDI e
   comparar nota por nota (início, altura, duração) dá um teste automático, sem conferir imagem.

## Fases

### Fase 0: ambiente e acervo de teste
- ~~Instalar o LilyPond~~ (feito): `scripts/instalar-lilypond.sh` baixa o binário oficial 2.26.0
  para `ferramentas/` (fora do git), confere o sha256 e cria o link `ferramentas/lilypond`. Sem apt
  e sem sudo. Teste com o `LVB_Sonate_02no1_1.ly` (2.10.3): o `convert-ly` atualizou para 2.26 e o
  `lilypond` compilou em 3 s, gerando PDF e MIDI. O `-dbackend=null` ainda gerou o PDF; a Fase 1
  precisa achar a opção que desliga a saída gráfica.
- Criar `.venv` com `music21`, `verovio` e `mido` (feito): `requirements.txt` fixa
  `music21==10.5.0`, `verovio==6.3.0`, `mido==1.3.3`. Instalar com
  `.venv/bin/pip install -r requirements.txt`.
- Baixar um recorte do Mutopia (feito): `scripts/baixar-acervo.sh` baixa 30 peças de
  piano + o `LVB_Sonate_02no1_1.ly` (31 `.ly` no total, de 2.6.0 a 2.24.3, com
  repetição/quiáltera/apojatura/casas no conjunto) para `dados/` (fora do git),
  do commit fixado `2144afd` (master em 07/11/2024), com `dados/MANIFESTO.txt`.
  `convert-ly` leva a 2.26 tanto o LVB (2.10.3) quanto a mais antiga (2.6.0), e o
  `lilypond` compila o LVB convertido em ~3,5 s, gerando PDF e MIDI.
- `git init` no projeto.

### Fase 1: captura mínima

**Andamento (05/10/2026, passo 01):** contrato entre Scheme e Python fixado em
`docs/passos/01-formato-eventos.md`, com exemplo executável em
`testes/ly/01-contrato.ly` + `testes/ly/01-contrato.eventos.jsonl` (25 linhas,
JSON Lines válido).

**Andamento (05/10/2026, passo 02):** envelope e execução prontos.
`scripts/ly2json.sh ARQ.ly [SAIDA_DIR]` faz `.ly → convert-ly → lilypond +
captura → .eventos.jsonl + .midi + .lilypond.log`, e `ly/captura.ly` tem o
esqueleto (`json`, `objeto`, `fracao`, `emitir`, `campos-tempo`, engraver de
`Score` com `partitura`/`fim`, `cabecalho`). `testes/ly/02-minimo.ly` dá as 3
linhas esperadas e o LVB (2.10.3) sai com status 0 em ~2,5 s. Descobertas:
`-dno-print-pages` desliga o PDF (o `-dbackend=null` não existe); no bash, um
`if ! cmd` zera o `$?` dentro do `then`, então o script testa o exit do
`lilypond` sem `!` (senão a falha passava batida). Das 31 peças, 24 passam e 7
não compilam mesmo sem a captura (causa pré-existente; resolvida depois por `conversor/compat.py`, ver adiante): `Chop-28-2` (o `convert-ly` não converte
`#(ly:set-option 'old-relative)`, status 2); `5.Inquietude`
(`override-auto-beam-setting`), `chopin_nocturne_op9_n2` e
`SchubertF-D899-2-Impromptu` (`set-octavation`), `diabeli.op163.s1-1` e
`maple` (`\unfoldRepeats` com argumentos da sintaxe antiga, sem nem emitir
`partitura`), `25EF-01` (`octave marks must precede duration`); status 3, com
as linhas `error:` na saída. Nenhum erro cita `captura.ly`. O original em
`dados/` segue intacto (o script só escreve em `SAIDA_DIR` e no temporário).

**Andamento (05/10/2026, passo 03):** engraver de `Voice` em `ly/captura.ly`
(`captura-voz` + `emitir-nota/pausa/pausa-compasso/quialtera`, contadores por
partitura zerados no `initialize` do `Score`, tabela `Staff → pauta` ainda
vazia). `testes/ly/03-vozes.ly` cobre acorde, `<g b>2~ q8`, `<c~ e>2`,
`<< {} \\ {} >>` (ids `"1"`/`"2"`), `\new Voice`, `\change Staff`,
`\tuplet 3/2`, `R2.*2` (igual ao exemplo do contrato: `fig` 1, `escala` `"2"`,
`dur` `"3/2"`), `r8`, `s4` (sem linha), `\grace`/`\acciaccatura`/`\appoggiatura`
(`g` `"-1/8"`, `barra` só na cortada). Conferido à mão: 43 notas (29 na pauta
de cima), `lig` true só nas 3 certas, quiáltera `3/2` com `null` no fim e
`num`/`den` direto das propriedades invertidas (sem fallback).
`bach-invention-01` dá 467 notas, como no protótipo. Decisões: `pauta` sai 0
em tudo até o passo 04 preencher a tabela (o `\change Staff` só passa a
aparecer lá); `barra` só aparece como `true` (contrato 01); `02-minimo.ly`
agora traz também `voz` + `nota` (a voz implícita é capturada). Nas 31 peças,
os mesmos 24/7 do passo 02, sem erro novo: nada cita `captura.ly`, e toda
partitura capturada tem notas (só `diabeli`/`maple`, sem partitura, não têm).

**Andamento (07/10/2026, passo 04):** `captura-pauta` (`pauta`, `clave`, `armadura`,
`fim-pauta`, registro na tabela `Staff → pauta` já no `initialize`) e a parte de
tempo de `captura-score` (`compasso`, `formula`, `barra`, `repeticao` e os
ouvintes `volta`, `rep-inicio`, `rep-fim`). `testes/ly/04-pauta.ly` cobre
`\partial`, `\key` g/d/c, `\time` 3/4→6/8, `\clef bass` e `treble_8`,
`\repeat volta` com `\alternative`, `repeatCommands` manual e `\bar "|."`; o aviso
de polimetria foi testado à parte. Achados da 2.26 (corrigidos no passo 01):
`timeSignatureFraction` está deprecada (usar `timeSignature`); `measureLength` é
racional, não `Moment`; **após `\partial` o `currentBarNumber` não incrementa**
(pickup e 1º compasso cheio são ambos 1), então `compasso` sai também quando
`measurePosition` cai ou volta a 0; a tônica de `\key g` vem na oitava −1;
`repeatCommands` de `\repeat volta` traz o número (`["start-repeat",2]`,
`["end-repeat",1]`). O exemplo do contrato (`01-contrato.eventos.jsonl`) agora é
a saída real da captura. Nas 31 peças: os mesmos 24/7, nenhum erro cita
`captura.ly`, nenhuma nota na pauta 0, `fur_Elise` tem repetições e casas,
`SchumannOp15No07` tem 19 notas com pauta diferente da da voz, `bach-invention-01`
segue com 467 notas.

**Andamento (07/10/2026, passo 05):** `captura-preparar` nos três handlers
(`toplevel-`, `book-` e `bookpart-score-handler`): sem definição de saída ganha
`\layout` + `\midi`; só `\midi` ganha `\layout` com `capturaSoMidi = ##t`
(propriedade registrada com `set-object-property!`); só `\layout` ganha `\midi`.
`LY2MXML_SEM_MIDI=1` desliga o `\midi` acrescentado. `05-scores.ly` dá 4
partituras com `so_midi` `false,true,false,false` e 4 MIDI; `05-book.ly` dá o `\book`
primeiro (`so_midi` `true,false,false`) e o `\score` do topo por último, e o log
repete `05-book-1.midi` (nome duplicado, como previsto). Nas 31 peças: os mesmos
24/7; `KV331`, `intermezzo`, `No03_Albumblatt` e `5.Inquietude` têm 2 partituras (a 2ª
`so_midi`), `sonatina-1` tem 3 sem `so_midi`. `Chop-28-2`, `diabeli` e `maple`
seguem sem partitura por causa dos erros pré-existentes (passo 02).

**Andamento (07/10/2026, passo 06):** `scripts/json-vs-midi.py` (aceita `.ly` ou diretório
com os `.eventos.jsonl`). As 5 peças simples batem 100% e, nas 31, as 35 partituras das 28 peças que
geraram partitura batem (status 0); `Chop-28-2`, `diabeli` e `maple` não geram partitura
(erros pré-existentes do passo 02). **Fase 1 concluída.** Ajustes que o protótipo do passo não previa, todos
confirmados contra o MIDI: (1) o MIDI tem ticks inteiros, então o 14/5 de uma quiáltera de 5
vira 4300,8 e o LilyPond arredonda cada início e cada fim: compara-se em ticks, com tolerância
de 2 (início) e 8 (duração); (2) o MIDI **encurta** a nota por staccato e `\afterGrace`;
duração menor no MIDI conta como "encurtada", só maior é erro; (3) a continuação de uma
ligadura é a **próxima nota da mesma altura na voz** a partir do fim, não necessariamente
no `t + dur` (arpejo de quiálteras ligado ao acorde final, `Chop-28-1`); (4) apojatura ligada
à principal de mesma altura (`\appoggiatura a8~ a2`) vira uma nota só no MIDI; (5) uníssonos
entre vozes (mesma altura, mesmo instante, ou sobrepostas) o MIDI funde ou separa, e não dá
para saber qual `note_off` é de qual `note_on`: comparam-se a maior duração de cada lado e
isso é contado como `unissonos`; (6) em `Liszt`, `intermezzo`, `Debussy` e outras, o MIDI do
LilyPond não funde algumas ligaduras sob arpejo; a continuação aparece só no MIDI e é
contada como `ligaduras nao fundidas no MIDI`, sem ser erro. O log tem um nome de MIDI
repetido nos arquivos com `\book` + `\score` no topo: o script avisa e não os compara.

- `ly/captura.ly`: notas, pausas e acordes com momento, pauta e voz.
- Resolver as pegadinhas da injeção:
  - partitura sem `\layout` (só `\midi`): os engravers não rodam. Forçar um `\layout` pelo
    `toplevel-score-handler`;
  - vários `\score` num arquivo (vários movimentos): um MusicXML por `\score`;
  - `\book` e `\bookpart`.
- `scripts/ly2json.sh ARQ.ly` → `ARQ.eventos.json`.
- Critério para avançar: o JSON de 5 peças simples bate com o MIDI do LilyPond.

### Fase 2: MusicXML básico

**Andamento (07/10/2026, passo 07):** `conversor/eventos.py` (`ler`, `escolher`, dataclasses
com `slots`). Acordes agrupados por `(voz, t, g)`; figuras diferentes no mesmo grupo se
separam com aviso. Ligaduras: o destino é o acorde da mesma voz que começa em `fim` com a
mesma altura; **segue por cima de outras notas contíguas da voz** (arpejo ligado ao acorde
final, como o passo 06 mostrou) e para em pausa ou buraco; a apojatura procura a principal
no mesmo `t`. Pauta temporária = começa depois de 0 ou termina antes do `fim`. Nas 31 peças
a leitura roda sem exceção; os únicos avisos são `ligadura sem destino` (31 no total).
`pytest` foi acrescentado ao `requirements.txt` no passo 06.

- `ly2mxml.py ARQ.ly [-o SAIDA.musicxml]` faz tudo de ponta a ponta.
- Compassos, fórmula de compasso, armadura, claves (inclusive a mudança no meio da pauta), anacruse
  (`\partial`), notas, acordes, pausas, `R1*4`, ligaduras de prolongamento e vozes (`<< {} \\ {} >>`
  e `\new Voice`).
- Pautas criadas e encerradas no meio (`\new Staff` temporário, ossia): ignorar a ossia e avisar.
- `scripts/comparar-midi.py`: diferença entre o MIDI do LilyPond e o MIDI do MusicXML.

**Andamento (07/10/2026, passos 08 a 11):** `conversor/montagem.py` (uma `PartStaff` por
pauta, `StaffGroup` com chave; o music21 exporta como **um** `<part>` com `<staves>`),
`conversor/lilypond.py`, `conversor/pipeline.py`, `ly2mxml.py`, `conversor/comparacao.py` e
`scripts/comparar-midi.py`. Decisões e descobertas:

- **`makeNotation=False` na gravação.** Com `makeNotation=True` o music21 renumera as vozes
  (a voz 5 da segunda pauta vira 2). Então a montagem faz o que o music21 faria: `makeBeams` por
  `Measure` (não aceita `Voice`) e `makeAccidentals` por parte. Durações irregulares (corte na
  barra, buracos) são partidas em notas ligadas por `Duration.components`.
- **Compassos entram na parte no offset absoluto** (`t0 × 4`), então uma pauta sem nada num
  compasso não desloca os seguintes. A anacruse é o compasso 0 (`implicit="yes"`), sem
  `paddingLeft`: o MusicXML não precisa dele.
- **Vozes.** O número da voz do MusicXML sai de um coloração de intervalos por pauta: vozes do
  LilyPond que não se sobrepõem compartilham o número (o LVB tem 30 `\new Voice` curtas), a
  que tem mais notas é a 1ª. Passou de 4 vozes simultâneas: aviso, e os números seguintes vão de
  9 em diante (em vez de descartar notas, como o passo previa).
- **Armadura numerada.** O music21 só põe `number` no `<key>` inicial; as mudanças no meio
  valeriam para as duas pautas. O pós-processamento (agora com `ElementTree`, não regex) dá o
  `number` pela pauta da nota seguinte.
- **Pauta temporária** (corrigido no passo 07): só `inicio > 0`. Uma mão que acaba antes da
  outra não é ossia (o teste `03-vozes` mostrou isso).
- **Ligadura sobre outras vozes.** O destino é a próxima nota da mesma voz e altura, mesmo com
  buraco (até 1 semibreve): o arpejo de `Chop-28-1` liga o dó ao acorde final por cima de
  notas de outras vozes.
- `LY2MXML_SEM_MIDI` vazio vale como não definido (em Scheme, `""` é verdadeiro).
- `scripts/comparar-midi.py` lê o MusicXML direto do XML (ElementTree), sem o music21, e usa a
  mesma comparação do passo 06 (`conversor/comparacao.py`).
- Sem apojaturas (passo 13) elas faltam no MusicXML; é a única diferença nas peças simples.

### Fase 3: o que muda o ritmo ou a ordem
- Quiálteras (`\tuplet`/`\times`), com colchete.
- Apojaturas (`\grace`, `\acciaccatura`, `\appoggiatura`) como `<grace/>`, sem consumir tempo.
- Repetições: `\repeat volta` com `\alternative` vira barras de repetição e casas.
  `\repeat unfold` sai desdobrado (o LilyPond já entrega assim). `\repeat percent` e `tremolo` saem
  desdobrados, e dá para avisar.
- Mudança de fórmula e de armadura no meio da peça. Compasso incompleto no meio (`\partial` interno,
  `\set Timing.measurePosition`).
- `\cadenzaOn` (sem barras): um compasso longo, com aviso.

**Andamento (07/10/2026, passos 12 e 13):** quiálteras e apojaturas em `montagem.py`.

- *Quiálteras.* A duração vem da figura do LilyPond (tipo + pontos + `Tuplet`) quando o acorde
  está dentro de um par `quialtera inicio/fim` da voz; fora disso (`c4*2/3`, `s1*3/4`) o music21
  escolhe a figura pelo `quarterLength`. O `(num, den)` impresso vem do evento (`6/4` numa
  sextina): a escala sozinha dá `2/3` para `6/4` e para `3/2`. `makeTupletBrackets` roda por
  `Voice` já com as pausas escondidas dentro, e os colchetes saem. Quiálteras aninhadas (escala
  `4/9`) não foram tratadas à parte, porque o acervo não tem caso.
- *Apojaturas.* `getGrace(appoggiatura=not barra)` dá `<grace slash=...>`; várias apojaturas do
  mesmo grupo mantêm a ordem; a apojatura ligada à principal sai com `tie`. `\afterGrace` entra
  depois do acorde da voz que a contém (`afterGrace aproximada`); se ela está presa a um espaço
  (`\afterGrace s2.*4/5 {...}`, `LiederOhneWorte`), fica no próprio instante, num buraco da voz.
- *Vozes, de novo.* Uma `Voice` do LilyPond pode ter acordes **sobrepostos** (notas de durações
  diferentes tocadas ao mesmo tempo; `debussy_Ste_Bergamesq_Clair`). Cada camada vira uma voz do
  MusicXML à parte (`_camadas`), e o agrupamento de vozes por pauta trabalha com a união dos
  intervalos, não com vizinhos (o teste de vizinhança deixava passar sobreposição).
- *Comparação.* O MIDI do LilyPond atrasa tudo quando a peça **começa** por apojatura
  (`13-apojaturas.ly`): a comparação detecta e desconta o atraso. A janela de uma apojatura
  começa na nota anterior **da mesma voz** (com a de qualquer voz, uma nota da outra mão
  encurtava a janela do `\afterGrace`).
- Nas 31 peças, `comparar-midi.py` dá OK nas 24 que o `lilypond` compila (as outras 7 são as do
  passo 02).

**Andamento (07/10/2026, passos 14 e 15):** repetições, casas e compassos partidos.

- *Repetições.* `rep-inicio`/`rep-fim`/`repeatCommands` (união, sem duplicar o mesmo instante)
  viram `bar.Repeat` em todas as pautas; o `times` vem do `repeat-count` do início que cada fim
  fecha (pilha, como parênteses). As casas vêm dos `volta` do `\alternative` e do
  `(volta "1.")` à mão, e viram `RepeatBracket` por pauta (`<ending number="1,2">`). Os eventos
  de salto (segno, coda, D.S., fine) e o tremolo geram só um aviso na captura.
- *`\repeat percent`.* Confirmado que **não** sai desdobrado sozinho (o plano dizia que sim):
  `captura-preparar` reconstrói o `\score` com `\unfoldRepeats percent` quando acha
  `PercentRepeatedMusic` na música, mantendo cabeçalho e saídas. Verificado com 16 notas em
  vez de 8.
- *Comparação com as repetições.* `notas_do_musicxml(expandir=True)` percorre as repetições e as
  casas na ordem de execução (forward/backward, `times`, passadas das casas) e compara com o MIDI
  da partitura `so_midi` gêmea (a cópia `\unfoldRepeats`): `KV331_1_1_tema`, `intermezzo`,
  `No03_Albumblatt` batem desdobradas, como a `fur_Elise` e a `gymnopedie_1` batem sem desdobrar.
- *Compassos partidos.* O tamanho de um compasso é sempre `próximo.t - t`, então os curtos já
  saem certos; o que foi preciso é a numeração: dois compassos seguidos com o mesmo `c` são um
  compasso partido, e o segundo é `implicit="yes"` com sufixo (`6b`); a anacruse (no começo ou no
  meio) é o que tem `pos < 0`, e leva o número anterior ao `c`. Um `\partial 4` no meio dá um
  compasso com `pos` **positivo** (`1/4`) na 2.26, e não negativo como o passo previa; não muda
  nada porque vale o tamanho real.
- *Cadenza.* O trecho depois de um `\bar` dentro da cadenza vira outro compasso (mesmo `c`,
  `implicit`), com o aviso `cadenza no compasso N (X semínimas)`.

### Fase 4: lote e regressão (o ciclo que funcionou no Hymn_Grabber)
- `scripts/converter-todos.py`: converte o acervo em paralelo e grava:
  - `saida/_resumo.csv`: uma linha por peça (compassos, notas, vozes, quiálteras, apojaturas, se o
    MIDI bate);
  - `saida/_avisos.log`: o que foi ignorado ou aproximado.
  - Ao final, lista as peças que mudaram desde a última rodada.
- Conferência visual quando o MIDI bate mas algo parece errado: renderizar com o verovio ao lado do
  PDF do LilyPond.
- Meta: medir a taxa de sucesso no recorte e depois no Mutopia de piano inteiro (umas 500 peças).
  As peças que não compilam nem depois do `convert-ly` ficam listadas à parte.

**Andamento (07/10/2026, passo 16):** `scripts/converter-todos.py` (+ `conversor/resumo.py`).
`ProcessPoolExecutor`, uma linha de `saida/_resumo.csv` por partitura gravada (versionado: é o
teste de regressão, com `saida/*` e `!saida/_resumo.csv` no `.gitignore`), `saida/_avisos.log`
e a lista do que mudou desde a rodada anterior (todas as colunas menos `segundos`). O lote das
31 peças leva ~26 s com 4 núcleos (meta: < 2 min). **Primeira rodada: 33 partituras de 31
peças, 18 ok, 8 avisos (só `ligadura sem destino`, `afterGrace aproximada` e afins), 0
`midi-difere`, 6 `ERRO-lilypond` e 1 `ERRO-convert`** (as sete peças do passo 02, que não
compilam). Segunda rodada: `0 de 33 partituras mudaram`, ou seja, a saída é reprodutível.

**Andamento (07/10/2026, passo 17):** `scripts/conferir.py PECA [-p N] [-c A-B] [-o DIR]`
grava `saida/conferir/PECA.html` com o SVG do LilyPond (`-dbackend=svg`, sem a captura, cópia
pelo `convert-ly`) à esquerda e o do Verovio (`loadFile` do MusicXML gerado, `select
measureRange` para `-c`) à direita. Funciona com uma e com várias partituras (`sonatina-1`). Foi
usado em `bach-invention-01`, `Chop-28-1`, `LVB_Sonate_02no1_1`, `fur_Elise_WoO59` e nos testes
`12` e `13`, e achou **dois problemas reais**, nenhum visível no MIDI:

1. **Clave de fá perdida quando a peça começa por apojatura** (`13-apojaturas.ly`): a pauta
   emite a clave padrão (sol) em `g = -1/8`, antes da `\clef bass` do mesmo `t`, e a montagem
   usava a primeira. Agora vale a última de cada instante (`g` entrou nas linhas `clave` e
   `armadura` lidas). O MIDI não tem clave, então a comparação nunca acharia isso.
2. **Barra de repetição no início da peça** (`fur_Elise_WoO59`): o `start-repeat` em `t = 0`
   saía como `|:` no primeiro compasso, que o LilyPond não desenha. Agora é omitido (uma
   repetição que começa na primeira nota não precisa da barra para tocar certo).

Como ver a página sem abrir o navegador (snap do Chromium só escreve no `$HOME`):
`chromium --headless --screenshot=$HOME/x.png --window-size=1500,1000 file://.../PECA.html`.

**Andamento (07/10/2026, compatibilidade e as sete peças que não compilavam):**
`conversor/compat.py` corrige o que o `convert-ly` deixa passar, antes (`#(ly:set-option
'old-relative)` **comentado**, que o `convert-ly` lê mesmo assim e aborta) e depois dele
(`#(set-octavation N)` → `\ottava #N`; `#(override-auto-beam-setting ...)` removido;
`\applyMusic #unfold-repeats` → `\unfoldRepeats`; marcas de oitava depois da duração `f8'` →
`f'8`). As regras preservam as linhas e viram `aviso: compatibilidade com sintaxe antiga: ...`.
Resultado: **as 31 peças convertem** (`Chop-28-2`, `25EF-01`, `5.Inquietude`,
`chopin_nocturne_op9_n2`, `diabeli`, `maple` e `SchubertF-D899-2-Impromptu` incluídas), todas
batem com o MIDI do próprio `\score` e o lote dá 24 `ok` e 10 `avisos` em 34 partituras. Outras
descobertas:

- *Repetição ou casa que começa/termina no meio do compasso* (`5.Inquietude`): o compasso é
  partido ali (mesmo `c`, `implicit`), em vez de mover a barra para o fim do compasso, o que
  fazia a repetição tocar notas a mais.
- *A partitura `so_midi` nem sempre é a gêmea desdobrada.* Em `diabeli` ela é o dueto inteiro
  (primo + secondo `\unfoldRepeats`), em `SchubertF-D899-2-Impromptu` é outro arranjo (sem a
  anacruse), em `5.Inquietude` nem desdobra. `comparar_resultado` compara a `so_midi` com as
  gravadas anteriores **juntas**, desdobradas ou não (o que bater), e só como informação
  (coluna `gemea` do resumo: `ok`/`difere`); o que decide o `status` é o MIDI do próprio
  `\score`. `maple` difere por uma ligadura que cruza a volta da repetição (na versão
  desdobrada o MIDI a funde; no MusicXML ela vai para a nota depois da repetição);
  `diabeli`, por um tremolo (o MIDI toca as notas repetidas; a captura avisa).

### Fase 5 (opcional): notação
- Dinâmica e hairpins, articulações (staccato, acento, fermata), ligaduras de expressão, ornamentos
  (trinado, mordente, arpejo), pedal, `\tempo` com metrônomo, textos (`^\markup`), `\ottava`,
  dedilhado e metadados do `\header` (título, compositor, opus).

**Andamento (07/10/2026, passo 18):** feitos os itens 1 a 11 e 14 da tabela: ligadura de
expressão (`(` e `\(`), dinâmica, crescendo/diminuendo, articulações e ornamentos (incluindo
fermata, arpejo e `\portato`), andamento, metadados, dedilhado, pedal, `\ottava`, textos e o
C/₵ da fórmula. Ficaram de fora o 12 (feixes manuais) e o 13 (símbolo de tremolo; a captura
avisa `tremolo escrito como notas simples`). O contrato subiu para `formato` 2 (só acrescenta
linhas; ver `docs/passos/01-formato-eventos.md`). `conversor/notacao.py` aplica tudo depois das
notas, guardando os elementos criados (`Montagem.refs`) para os `Slur`, `Crescendo`,
`PedalMark` e `Ottava`. Verificado no `18-notacao.ly` pelo `conferir.py` (as duas colunas
mostram o mesmo) e nos testes. O `_resumo.csv` ganhou as colunas `dinamicas`, `hairpins`,
`ligaduras_expr`, `articulacoes`, `pedais` e `andamentos`; a comparação com o MIDI não mudou
(as notas são as mesmas). Descobertas: (1) o mesmo evento chega ao engraver de `Voice`, de
`Staff` e de `Score`, então ouvi-lo em mais de um duplica as linhas; (2) `ly:parser-lookup
'$defaultheader` é o `\header` do arquivo (o `'header` volta vazio); (3) `\sustainOn` e
`\sustainOff` chegam como `sustain-event` com `span-direction` -1 e 1; (4) o `Fermata` do music21
sai de ponta-cabeça (`inverted`) se não se pedir `upright`; (5) ligadura de expressão que
começa numa pauta e termina em outra não é desenhada (cada `Slur` fica numa `PartStaff`).

## Riscos e decisões em aberto

| Risco | Plano |
|---|---|
| `convert-ly` falha em arquivos muito antigos (2.0–2.8) | Medir na Fase 0; se forem muitos, manter uma lista de correções manuais à parte, como os `musicxml_special/` do Hymn_Grabber |
| Arquivos que mexem no comportamento de contextos (`\remove`, engravers próprios) | Os engravers da captura são acrescentados por último; avisar quando o arquivo remove `Timing_translator` etc. |
| Vozes que mudam de pauta (`\change Staff`), comum em piano | O evento sai na voz de origem com a pauta do momento; no MusicXML vira `<staff>` por nota, o que o formato permite |
| Feixes manuais `[ ]` contra os automáticos | Para "tocar/estudar", deixar o music21 calcular; os manuais entram na Fase 5 |
| Peças com muitos movimentos ou `\book` | Um MusicXML por `\score`, com o número no nome |
| Versão do LilyPond | Fixada em 2.26.0 no `instalar-lilypond.sh`; registrar no `_resumo.csv` |

## O que reaproveitar do Hymn_Grabber

- A montagem pelo music21 e os contornos já descobertos: ids fixos, sem data, colchete de quiáltera
  e queda para "sem barras automáticas" quando o compasso estoura (`montar_musicxml` em
  `scripts/pdf-para-musicxml.py:1987`).
- O formato do lote: resumo CSV como teste de regressão, log de avisos e lista do que mudou.
- O `classificar-dificuldade.py`, que pode rodar direto sobre a saída.
