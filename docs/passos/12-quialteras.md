# 12 — Quiálteras

Fase 3. Faz as quiálteras saírem com a figura escrita, o `<time-modification>` e o colchete com o
número. Até aqui, a duração vinha só de `quarterLength`, o que dá o tempo certo mas às vezes a
figura errada.

## Pré-requisitos

- [11](11-comparar-midi.md) (para medir).
- Os passos 12 a 15 são independentes entre si.

## Cria

- Amplia `conversor/montagem.py`.
- `testes/ly/12-quialteras.ly` e testes em `testes/test_montagem.py`.

## O que fazer

### 1. Duração a partir da figura

Trocar `Duration(quarterLength)` por uma duração montada da figura do LilyPond:

```python
TIPOS = {-2: "longa", -1: "breve", 0: "whole", 1: "half", 2: "quarter", 3: "eighth",
         4: "16th", 5: "32nd", 6: "64th", 7: "128th"}

def duracao(f: Figura) -> duration.Duration:
    d = duration.Duration(type=TIPOS[f.fig], dots=f.pontos)
    if f.escala != 1:
        d.appendTuplet(duration.Tuplet(numberNotesActual=f.escala.denominator,
                                       numberNotesNormal=f.escala.numerator,
                                       durationActual=..., durationNormal=...))
    assert d.quarterLength == f.dur * 4
    return d
```

- `escala = 2/3` → 3 no lugar de 2 (`actual = 3`, `normal = 2`).
- `durationActual`/`durationNormal`: a figura de referência do colchete. Comece com a própria figura
  da nota e veja no MuseScore se o número sai certo. Para estudo, basta o número.
- O `assert` é a rede de proteção: se falhar, cair para `Duration(Fraction(f.dur * 4))` e avisar.

**Escala sem quiáltera.** `c4*2/3` (duração escalada sem `\tuplet`) e `s1*3/4` têm `escala` mas não
têm linha `quialtera`. Só trate como quiáltera a nota que está **dentro** de um par
`quialtera inicio/fim` da mesma voz. As outras usam `Duration(quarterLength)`: o music21 escolhe a
figura. Pausa de compasso (`R1*4`) nunca é quiáltera.

### 2. Colchetes

Depois de montar as vozes, para cada `stream.Voice` de cada compasso:

```python
stream.makeNotation.makeTupletBrackets(voz, inPlace=True)
```

Necessário porque o music21 só marca os colchetes nas notas soltas no compasso, não nas que estão
em `Voice` (descoberto no Hymn_Grabber, caso 024). Verificado aqui: com isso sai
`<tuplet bracket="yes" ... type="start">` e `type="stop"`.

### 3. Agrupamento

O `makeTupletBrackets` fecha um grupo quando ele completa a duração "normal". Isso cobre
`\tuplet 3/2 4 { c8 d e f g a }` (dois grupos). Use as linhas `quialtera` só para conferir:
o número de grupos do music21 deve ser o número de pares inicio/fim **ou maior** (por causa do
`tupletSpannerDuration`). Se for menor, avisar.

**Aninhadas** (`\tuplet 3/2 { \tuplet 3/2 { } }`): `escala = 4/9`. Monte duas `Tuplet` com a ajuda
dos pares aninhados das linhas `quialtera`: a de fora (3:2) e a de dentro (3:2). Se a escala não se
fatorar pelas razões dos pares, cair para `quarterLength` e avisar. Raro no acervo. Não gastar
tempo antes de achar um caso real.

## Pegadinhas

- Quiáltera que atravessa a barra (LilyPond aceita): o passo 08 corta a nota, e o pedaço perde a
  figura. Avisar e deixar o music21 escolher.
- Apojatura dentro de quiáltera (`\tuplet 3/2 { \grace c16 d8 e f }`): a linha `quialtera fim`
  pode chegar no momento de uma apojatura (verificado no protótipo). Isso não muda nada, porque o
  colchete é calculado pelas durações.
- `\times` (sintaxe antiga) já vira `\tuplet` no `convert-ly`. O evento é o mesmo.
- Uma voz que só tem a quiáltera e espaços (`s`) ao redor: as pausas escondidas do passo 08 entram
  no `makeTupletBrackets`. Se o colchete pegar a pausa escondida, montar os colchetes **antes** de
  preencher os buracos.

## Como verificar

`12-quialteras.ly`: tercina de colcheias, de semínimas (`\tuplet 3/2 { c4 d e }`), sextina
(`\tuplet 6/4`), `\tuplet 3/2 4 { ... }` com 6 colcheias, tercina com pausa no meio, quintina
(`\tuplet 5/4`), e duas vozes com tercinas diferentes ao mesmo tempo.

Conferir no XML: `<actual-notes>`, `<normal-notes>`, `<type>` certo em cada nota e os colchetes. No
MuseScore: o número 3, 6 e 5 sobre os grupos.

No acervo: `Chop-28-1` (152 quiálteras) e `SchubertF-D899-2-Impromptu` (195). O `comparar-midi.py`
deve dar 100% nelas (se não houver outro recurso faltando).

## Pronto quando

- O teste passa e o `comparar-midi.py` continua 100% nas peças simples.
- `Chop-28-1` abre no MuseScore com as quiálteras como no PDF do LilyPond.
