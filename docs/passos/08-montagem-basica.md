# 08 — Montagem básica

Fase 2. Primeira versão de `conversor/montagem.py`: uma `Partitura` (passo 07) vira um MusicXML
com uma parte de piano, compassos, notas, acordes, pausas e vozes. Clave, armadura e fórmula só
**iniciais**. As mudanças no meio e as ligaduras ficam para o passo 09.

## Pré-requisitos

- [07](07-leitura-eventos.md).
- JSON de teste: os de `testes/ly/` e os das peças simples, gerados pelo `ly2json.sh`.

## Cria

- `conversor/montagem.py` com `montar(partitura, saida: Path) -> list[str]` (devolve os avisos).
- `testes/test_montagem.py`.

## Decisões

- **Uma parte, várias pautas.** Uma `stream.PartStaff` por pauta não temporária, todas numa
  `layout.StaffGroup(..., symbol="brace")`. Verificado: o music21 10.5 exporta isso como **um**
  `<part>` com `<staves>2</staves>` e `<staff>` em cada nota. Não use duas `stream.Part`, como no
  Hymn_Grabber: lá eram duas partes de propósito.
- **A nota fica na pauta onde soa.** Um acorde com `pauta = 2`, vindo de uma voz que nasceu na
  pauta 1 (`\change Staff`), vai para a `PartStaff` 2. A voz continua a mesma no MusicXML. O formato
  permite isso, e o MuseScore desenha a voz cruzando.
- **Números de voz do MusicXML.** Por pauta: 1 a 4 na pauta 1, 5 a 8 na pauta 2 (a convenção do
  MuseScore). Em cada pauta, a voz do LilyPond com mais notas nela é a 1ª. As outras seguem por
  ordem de primeira nota. Mais de 4 vozes simultâneas na mesma pauta e no mesmo compasso: aviso, e
  as excedentes se juntam à 4ª se não se sobrepuserem a ela; senão são descartadas, com aviso.
- **Compassos pelas linhas `compasso`.** O compasso `c` vai de `compassos[i].t` até
  `compassos[i+1].t` (o último, até `fim`). Um compasso que começa em `fim` não existe. O número
  impresso é `c`, e a anacruse é o `0` (ver abaixo).
- **Tempo do music21**: sempre `Fraction(dur * 4)`, nunca `float`. O music21 aceita `Fraction` e
  assim não perde a tercina (`1/3` de semínima não tem representação exata em `float`).

## O que fazer

1. `partes = {n: stream.PartStaff(id=f"P1-{n}") for n in pautas não temporárias}`. Avisar as
   temporárias (`ossia na pauta "id" ignorada`) e descartar os acordes que caem nelas.
2. Para cada compasso e cada pauta, criar `stream.Measure(number=c)`.
   - No 1º compasso: `clef`, `KeySignature` e `TimeSignature` iniciais (as primeiras linhas
     `clave`, `armadura` e `formula`). A conversão dos valores está no passo 09. Aqui só sol/fá e
     armadura pelo número de acidentes.
   - **Anacruse**: se o 1º `compasso` tem `pos < 0`, ele é o compasso 0. Duração real = `-pos`.
     `m.paddingLeft = tam*4 - (-pos)*4`. No XML final, trocar `implicit="no"` por
     `implicit="yes"` no compasso 0 (o Hymn_Grabber faz isso por texto).
3. Para cada voz e cada acorde, achar o compasso pelo `t` (busca binária nos inícios). Criar
   `note.Note`, `chord.Chord` ou `note.Rest`:
   - altura: `pitch.Pitch()` com `step = "CDEFGAB"[nota]`, `octave = oitava + 4`,
     `accidental = pitch.Accidental(float(alt * 2))` se `alt != 0`. Confira: o `midi` do music21
     tem de dar o `midi` do JSON. Se não der, é erro do programa: `assert`.
   - duração: `duration.Duration(Fraction(dur * 4))`. A notação exata (figura + pontos +
     quiáltera) entra no passo 12.
   - offset no compasso: `Fraction((t - inicio_do_compasso) * 4)`; na anacruse, somar o
     `paddingLeft`.
4. **Nota que atravessa a barra**: cortar em pedaços, um por compasso, ligados entre si
   (`tie.Tie("start"/"continue"/"stop")` em cada altura). Fazer isso aqui, e não deixar para o
   music21: ele não sabe em que compasso a nota começa.
5. **Pausa de compasso** (`compasso_inteiro`): uma `note.Rest` por compasso coberto, com
   `fullMeasure = True` e a duração do compasso.
6. **Buracos**: dentro de cada voz, em cada compasso, preencher os intervalos sem acorde com
   `note.Rest` escondida (`r.style.hideObjectOnPrint = True`, verificado: sai
   `print-object="no"`). Isso acontece com `s` e com `\change Staff`. Uma voz que não aparece num
   compasso daquela pauta não entra nele.
7. Inserir cada voz como `stream.Voice(id=str(numero_musicxml))` no compasso.
8. `sc = stream.Score()`, inserir as `PartStaff` e o `StaffGroup`. Gravar com
   `sc.write("musicxml", fp=saida)`. Se o music21 levantar exceção (compasso estourado), gravar de
   novo com `makeNotation=False` e avisar (o contorno do Hymn_Grabber).
9. Pós-processar o texto do XML (copiar de `montar_musicxml`, em
   `~/IdeaProjects/Hymn_Grabber/scripts/pdf-para-musicxml.py:2309`):
   - ids das partes fixos (`P1`);
   - remover `<encoding-date>`;
   - `implicit="yes"` no compasso 0.

## Pegadinhas

- **Compasso estourado**: a soma das durações de uma voz passa do compasso. Na captura isso não
  deveria acontecer, porque cada nota já tem o `t` certo. Se acontecer, o erro está na escolha do
  compasso (`t` exatamente na barra cai no compasso **seguinte**).
- `measureLength` de um compasso pode mudar sem mudar a fórmula (`\set Timing.measureLength`).
  O tamanho real é sempre a diferença entre dois `compasso`, não a fórmula.
- Uma voz que, num compasso, tem notas só em outra pauta deixa buraco na pauta de origem. Não
  preencher a pauta de origem com pausa visível: é o que o passo 6 faz com pausa escondida.
- O music21 reordena elementos com o mesmo offset. Para conferir, compare a saída pelo MIDI
  (passo 11), não pelo texto do XML.
- `chord.Chord` com alturas repetidas (`<c c'>` é diferente de `<c c>`): o LilyPond aceita
  `<c c>`. Remova a repetida, com aviso.

## Como verificar

`testes/test_montagem.py`, a partir dos JSON de `testes/ly/` (sem LilyPond, com os JSON
versionados):

- `01-contrato`: compasso 0 com `implicit="yes"`, 2 pautas, `<staves>2</staves>`, o acorde
  sol–si no compasso 1.
- `03-vozes`: as notas depois do `\change Staff` com `<staff>2</staff>` e a mesma `<voice>` de
  antes.
- Rodar duas vezes e comparar os arquivos: idênticos byte a byte.
- Abrir no MuseScore o resultado de `bach-invention-01` e conferir à vista as primeiras linhas.

## Pronto quando

- Os testes passam e o XML é válido para o music21 (`converter.parse(saida)` não falha).
- `bach-invention-01`, `bach-invention-02` e `wtk1-prelude1` abrem no MuseScore sem aviso de
  arquivo corrompido.
