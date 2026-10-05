# 11 — Comparar MIDI

Fase 2, o critério para fechar a fase. Compara o MusicXML gerado com o MIDI do LilyPond, nota por
nota. Se batem, a montagem não perdeu nem deslocou nada que a captura entregou.

## Pré-requisitos

- [06](06-json-vs-midi.md) (a lógica de comparação) e [10](10-cli.md).

## Cria

- `scripts/comparar-midi.py ARQ.ly [--musicxml X.musicxml]`.
- Uma função `comparar(notas_a, notas_b) -> Resultado` em `conversor/comparacao.py`, usada por este
  script, pelo `json-vs-midi.py` (refatorado para usá-la) e pelo lote (passo 16).
- `testes/test_comparar_midi.py`.

## O que fazer

### 1. Reaproveitar o passo 06

Mover para `conversor/comparacao.py`:

- `notas_do_midi(caminho) -> list[Nota]` (com `mido`);
- `comparar(esperado, obtido) -> Resultado` (multiconjunto de `(início, midi)`, durações dos pares,
  apojaturas em separado, uníssonos), com `Resultado.ok`, contagens e as primeiras diferenças.

`Nota = (inicio: Fraction, midi: int, dur: Fraction, apojatura: bool, compasso: int | None)`.

### 2. Notas do MusicXML

**Não** converter o MusicXML para MIDI com o music21: ele toca apojaturas e ligaduras do jeito
dele, e a comparação passaria a medir o music21. Ler o MusicXML com o music21 e tirar as notas
direto:

- `sc = converter.parse(x)`; para cada `PartStaff`, `p.flatten().notes` (inclui acordes).
- `inicio = Fraction(n.getOffsetInHierarchy(sc)) / 4` (offset em semínimas → semibreves).
- Notas com `tie.type in ("stop", "continue")` não abrem nota: somam a duração à anterior de mesma
  altura (mesma lógica do passo 06).
- Apojaturas (`n.duration.isGrace`): `apojatura = True`, início = o da nota principal.
- Repetições: o MusicXML **não** é desdobrado. Compare com o MIDI da partitura **sem**
  `\unfoldRepeats`, que é o MIDI que o passo 05 acrescentou ou o `\midi` do mesmo `\score`.

A anacruse desloca tudo: o offset do music21 começa em 0 no compasso 0 com `paddingLeft`. Some o
`pos` negativo do primeiro `compasso` (ou tire o `paddingLeft`) para alinhar com o tick 0 do MIDI.
Confira com o `01-contrato`.

### 3. Qual MIDI

- Para cada partitura que o `ly2mxml.py` gravou, o MIDI de mesma ordem em `Captura.midis`
  (passo 10, agora com `sem_midi=False`).
- Se a partitura gravada tiver uma `so_midi` "gêmea" (o mesmo número de pautas e uma partitura
  `so_midi` logo depois), comparar também com ela, desdobrando as repetições do MusicXML com
  `sc.expandRepeats()`. Isso só vale depois do passo 14. Antes, reportar como `não comparado`.

### 4. Saída

Como no passo 06, uma linha por partitura e as primeiras diferenças com o número do compasso do
MusicXML. Status 0 se todas batem.

## Pegadinhas

- `getOffsetInHierarchy` é lento em peças grandes. Se passar de alguns segundos, iterar compasso a
  compasso somando os offsets.
- O music21 pode juntar pausas ou dividir notas ao gravar (`makeNotation`). A divisão gera
  ligaduras novas, e a lógica do item 2 as junta de volta. É o resultado esperado.
- Voz cruzando pauta: a nota está na `PartStaff` 2 mas veio da voz da pauta 1. Para a
  comparação isso não importa: tudo vira uma lista só.

## Como verificar

- `testes/test_comparar_midi.py` (marcado `lilypond`): `01-contrato`, `03-vozes`, `09-atributos`
  dão status 0.
- Estragar de propósito um XML (trocar uma `<step>`) e ver o script apontar o compasso.

## Pronto quando

- As 5 peças simples batem 100% nas notas principais (critério da Fase 2 no plano). O
  `LiederOhneWorte_-_Op30_No6` tem `\afterGrace`: até o passo 13, as apojaturas dele podem faltar.
- Rodado nas 31 peças, com o resultado anotado em `docs/plano.md` (Fase 2). As que falham por
  quiáltera, apojatura ou repetição são esperadas e apontam para a Fase 3.
