# Plano do ly2mxml (LilyPond → MusicXML)

Plano escrito em 04/10/2026, antes de qualquer código.

## Objetivo

Converter partituras de **piano solo** do **Mutopia** e de outros acervos públicos (`.ly` de várias
versões, de 2.0 a 2.24) em MusicXML **para tocar e estudar**. O resultado precisa ter as notas
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
arquivo.ly ──convert-ly──▶ arquivo-2.24.ly ──lilypond + captura.ly──▶ eventos.json ──python──▶ arquivo.musicxml
                                               └──────────────────────▶ arquivo.midi (gabarito)
```

1. **Atualização**: `convert-ly` leva o arquivo para a sintaxe 2.24. Ele fica numa cópia
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
- Instalar o LilyPond 2.24 (o binário oficial do lilypond.org num diretório local não precisa de
  sudo; o `apt` também tem o 2.24.3).
- Criar `.venv` com `music21`, `verovio` e `mido`.
- Baixar um recorte do Mutopia (o repositório `MutopiaProject/MutopiaProject` no GitHub tem os
  `.ly`): umas 30 peças de piano de épocas e versões variadas, além do `LVB_Sonate_02no1_1.ly`.
- `git init` no projeto.

### Fase 1: captura mínima
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
| Versão do LilyPond | Fixar a 2.24.x e registrar no `_resumo.csv` |

## O que reaproveitar do Hymn_Grabber

- A montagem pelo music21 e os contornos já descobertos: ids fixos, sem data, colchete de quiáltera
  e queda para "sem barras automáticas" quando o compasso estoura (`montar_musicxml` em
  `scripts/pdf-para-musicxml.py:1987`).
- O formato do lote: resumo CSV como teste de regressão, log de avisos e lista do que mudou.
- O `classificar-dificuldade.py`, que pode rodar direto sobre a saída.
