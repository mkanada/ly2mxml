# 06 — JSON contra o MIDI

Fase 1, o critério para fechar a fase. Compara as notas capturadas com o MIDI que o próprio
LilyPond gerou da mesma partitura. Se batem, a captura está entregando altura e ritmo certos.

## Pré-requisitos

- [05](05-varios-scores.md): toda partitura tem um MIDI, e o log diz qual.

## Cria

- `scripts/json-vs-midi.py ARQ.ly` (ou `DIR` com `ARQ.eventos.jsonl`, os `.midi` e o log).
- `testes/test_json_vs_midi.py`.

Este script **não** usa `conversor/eventos.py` (passo 07). Lê o JSON direto, com o mínimo
necessário, para poder fechar a Fase 1 sem a Fase 2. No passo 07, se valer a pena, ele passa a usar
o leitor.

## O que fazer

### 1. Juntar partitura e MIDI

- Rodar `scripts/ly2json.sh` num diretório temporário (ou receber o diretório pronto).
- Ler do log as linhas `MIDI output to \`NOME'...`, na ordem. A n-ésima é o MIDI da partitura
  `p = n`.
- Se o número de linhas for diferente do número de partituras, ou se um nome se repetir, avisar e
  não comparar aquela peça (ver passo 05).

### 2. Notas do JSON

Para cada partitura, as linhas `nota`:

1. **Ligaduras.** Juntar cada nota com `lig: true` à próxima nota da mesma `midi` na mesma voz que
   começa exatamente em `t + dur` (e `g = "0"`). A duração passa a ser a soma. A continuação some
   da lista. Encadear (`c1~ c1~ c1` vira uma nota de 3 semibreves). Se não achar a continuação,
   manter a nota e contar como `ligadura sem destino`.
2. **Apojaturas** (`g` diferente de `"0"`): separar numa lista própria.
3. Resultado: uma lista de `(início, midi, duração)` em `Fraction`, na unidade semibreve.

### 3. Notas do MIDI

Com o `mido`:

- `ticks_per_beat` é 384 no LilyPond (verificado). `início = Fraction(tick, ticks_per_beat * 4)`.
- Cada `note_on` com `velocity > 0` abre uma nota no canal e na altura. O `note_off` (ou `note_on`
  com `velocity 0`) a fecha. A duração é a diferença.
- Todas as trilhas, todos os canais. O LilyPond põe uma trilha por pauta, mas isso não importa.

### 4. Comparar

- **Notas principais**: multiconjunto de `(início, midi)` dos dois lados. Depois, para os pares
  casados, comparar a duração.
- **Apojaturas**: o LilyPond as toca roubando tempo da nota anterior ou da principal, em instantes
  como `3253/768` (verificado: as 23 apojaturas do `LVB_Sonate_02no1_1` aparecem só no MIDI, em
  tempos fracionários). Compare só a altura e a quantidade: cada apojatura do JSON deve ter, no
  MIDI, uma nota de mesma altura entre o início da nota principal anterior e o início da nota
  principal. As notas do MIDI usadas nisso saem do multiconjunto antes da comparação principal.

Saída, uma linha por partitura:

```
LVB_Sonate_02no1_1 p1: notas 1655/1655  duracoes 1655/1655  apojaturas 23/23  OK
```

e, quando falha, as 10 primeiras diferenças com compasso (`c` do JSON) e tempo:

```
  so no JSON:  c12 t=45/4 G#4 dur=1/8
  so no MIDI:  t=45/4 A4 dur=1/8
```

Status de saída 0 se todas as partituras batem; 1 se não.

### 5. Partituras `so_midi`

Compará-las também: elas foram capturadas e têm o próprio MIDI. É um teste a mais da captura com
`\unfoldRepeats`.

## O que já se sabe (protótipo)

Com uma captura mínima, sem juntar as ligaduras:

| Peça | JSON | MIDI | Só no JSON | Só no MIDI |
|---|---|---|---|---|
| `bach-invention-01` | 467 | 458 | 9 (continuações de ligadura) | 0 |
| `LVB_Sonate_02no1_1` | 1670 + 23 apojaturas | 1678 | 15 (continuações) | 23 (as apojaturas) |

Depois de juntar as ligaduras e tratar as apojaturas como acima, as duas devem bater 100%.

## Pegadinhas

- Notas repetidas iguais e simultâneas (a mesma altura em duas vozes, comum em piano) viram **um**
  `note_on` só no MIDI ou dois `note_on` seguidos com um `note_off` no meio. Se aparecer, contar
  como `uníssono` e não como erro. Registrar quantos.
- Os comandos `\set Staff.midiInstrument`, dinâmicas e `\tempo` não mexem em tempo medido em
  ticks. Ignorar.
- `\articulate` (do `articulate.ly`) muda as durações e põe ornamentos por extenso. Se uma peça usar
  no `\score` do MIDI, a duração vai divergir: comparar só o início.
- Fermata e `\tempo` no meio não mudam ticks. Rallentando também não: o LilyPond não o toca.

## Como verificar

- `testes/test_json_vs_midi.py` (marcado `lilypond`): roda nos trechos `03-vozes.ly`,
  `04-pauta.ly` e `05-scores.ly` e espera status 0.
- As 5 peças simples do [recorte](README.md#recorte-do-acervo-por-recurso): `bach-invention-01`,
  `bach-invention-02`, `wtk1-prelude1`, `gymnopedie_2` e `LiederOhneWorte_-_Op30_No6`.

## Pronto quando

- As 5 peças simples batem 100% (critério da Fase 1 no plano).
- Roda nas 31 peças. Anotar em `docs/plano.md`, Fase 1, quantas batem e por que as outras não
  batem. Isso é diagnóstico, não bloqueio.
- `docs/plano.md` atualizado: Fase 1 concluída, com os fatos novos.
