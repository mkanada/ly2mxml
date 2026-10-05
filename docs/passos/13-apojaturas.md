# 13 — Apojaturas

Fase 3. As notas com `g` diferente de zero viram `<grace/>` no MusicXML, sem ocupar tempo,
antes da nota principal, com barra quando a apojatura é cortada.

## Pré-requisitos

- [11](11-comparar-midi.md). Independente de 12, 14 e 15.

## Cria

- Amplia `conversor/montagem.py`.
- `testes/ly/13-apojaturas.ly`.

## O que se sabe (verificado)

No `testes` do protótipo, com `\relative c''`:

| Música | `t` | `g` | `barra` |
|---|---|---|---|
| `\grace d8 c4` | 0 | −1/8 | não |
| `\acciaccatura e8 d4` | 1/4 | −1/8 | sim |
| `\appoggiatura f8 e4` | 1/2 | −1/8 | não |
| `\slashedGrace g8 f4` | 3/4 | −1/8 | sim |
| `\grace { a16 b } a4` | 1 | −1/8 e −1/16 | não |
| `\afterGrace b2 { c16 d }` | 13/8 | −1/8 e −1/16 | não |

- `t` é o tempo da nota principal. `g` conta para trás a partir dela: a primeira apojatura do grupo
  tem o `g` mais negativo.
- `\afterGrace` cai **dentro** da nota anterior (`13/8` está dentro de `b2`, que vai de `5/4` a
  `7/4`), em `afterGraceFraction` (3/4 por padrão) da duração dela. Não há nota principal em `t`.

## O que fazer

1. Na montagem, separar os acordes com `g != 0`. Agrupar por `(voz, t)`, em ordem de `g`.
2. Para cada grupo, achar a nota principal: o acorde da mesma voz com `t` igual e `g = 0`.
   - Achou: inserir as apojaturas antes dela, no mesmo offset e na mesma `Voice`/pauta.
   - Não achou (`\afterGrace`, ou apojatura no fim da peça): se `t` cai dentro de um acorde da
     voz, as apojaturas vão **depois** desse acorde (`<grace/>` antes da nota seguinte, que é como o
     MusicXML representa `afterGrace`), avisar `afterGrace aproximada`. Se não houver nota
     seguinte, descartar com aviso.
3. Criar cada apojatura com a figura do passo 12 e depois `n = n.getGrace(appoggiatura=not barra)`.
   No music21, `getGrace()` devolve uma cópia com `GraceDuration` e `slash` (verificado: sai
   `<grace slash="yes" />`). Com `appoggiatura=True`, sem barra.
4. Ligaduras de expressão do `\acciaccatura`/`\appoggiatura`: ficam para a fase 5.
5. Ordem: no `Voice`, inserir as apojaturas com o mesmo offset da principal. Verificado: o
   music21 as põe **antes** da principal de mesmo offset, mesmo inseridas depois dela. Num grupo,
   inserir na ordem de `g` (mais negativo primeiro) e conferir no teste que a ordem se mantém.

## Pegadinhas

- Apojatura em acorde (`\grace <c e>8`): várias linhas com o mesmo `(voz, t, g)` → um `chord.Chord`
  grace.
- Apojatura no começo de uma pauta e nada na outra no mesmo instante: o LilyPond sincroniza as
  pautas pelo `g`, e o MusicXML não precisa disso.
- Apojatura em outra pauta (`\change Staff` entre a apojatura e a principal): a apojatura vai na
  pauta dela, com a mesma voz.
- Uma apojatura ligada à principal (`\grace c8~ c4`): a ligadura sai se o passo 07 a encontrar.
  Senão, aviso.
- No `comparar-midi.py`, as apojaturas já são comparadas à parte, por altura e quantidade (passos
  06 e 11).

## Como verificar

`13-apojaturas.ly` com os seis casos da tabela, mais apojatura em acorde e em duas vozes ao mesmo
tempo. No XML: `<grace/>` com e sem `slash`, antes da nota certa. No MuseScore: igual ao PDF.

No acervo: `LVB_Sonate_02no1_1` (23 apojaturas), `No03_Albumblatt`, `chopin_nocturne_op9_n2`,
`K545-1`. Com `\afterGrace`: `LVB_Sonate_02no1_1`, `K545-1` e `LiederOhneWorte_-_Op30_No6`.

## Pronto quando

- O teste passa. O `comparar-midi.py` dá `apojaturas n/n` nas quatro peças.
- Nenhuma apojatura é perdida em silêncio: as descartadas aparecem nos avisos.
