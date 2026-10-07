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
não compilam mesmo sem a captura (causa pré-existente, à parte como os
`musicxml_special/` do Hymn_Grabber): `Chop-28-2` (o `convert-ly` não converte
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

- `ly/captura.ly`: notas, pausas e acordes com momento, pauta e voz.
- Resolver as pegadinhas da injeção:
  - partitura sem `\layout` (só `\midi`): os engravers não rodam. Forçar um `\layout` pelo
    `toplevel-score-handler`;
  - vários `\score` num arquivo (vários movimentos): um MusicXML por `\score`;
  - `\book` e `\bookpart`.
- `scripts/ly2json.sh ARQ.ly` → `ARQ.eventos.json`.
- Critério para avançar: o JSON de 5 peças simples bate com o MIDI do LilyPond.

### Fase 2: MusicXML básico
- `ly2mxml.py ARQ.ly [-o SAIDA.musicxml]` faz tudo de ponta a ponta.
- Compassos, fórmula de compasso, armadura, claves (inclusive a mudança no meio da pauta), anacruse
  (`\partial`), notas, acordes, pausas, `R1*4`, ligaduras de prolongamento e vozes (`<< {} \\ {} >>`
  e `\new Voice`).
- Pautas criadas e encerradas no meio (`\new Staff` temporário, ossia): ignorar a ossia e avisar.
- `scripts/comparar-midi.py`: diferença entre o MIDI do LilyPond e o MIDI do MusicXML.

### Fase 3: o que muda o ritmo ou a ordem
- Quiálteras (`\tuplet`/`\times`), com colchete.
- Apojaturas (`\grace`, `\acciaccatura`, `\appoggiatura`) como `<grace/>`, sem consumir tempo.
- Repetições: `\repeat volta` com `\alternative` vira barras de repetição e casas.
  `\repeat unfold` sai desdobrado (o LilyPond já entrega assim). `\repeat percent` e `tremolo` saem
  desdobrados, e dá para avisar.
- Mudança de fórmula e de armadura no meio da peça. Compasso incompleto no meio (`\partial` interno,
  `\set Timing.measurePosition`).
- `\cadenzaOn` (sem barras): um compasso longo, com aviso.

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

### Fase 5 (opcional): notação
- Dinâmica e hairpins, articulações (staccato, acento, fermata), ligaduras de expressão, ornamentos
  (trinado, mordente, arpejo), pedal, `\tempo` com metrônomo, textos (`^\markup`), `\ottava`,
  dedilhado e metadados do `\header` (título, compositor, opus).

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
