# ly2mxml

Converte partituras do LilyPond (`.ly`) para MusicXML, com foco em piano solo do
[Mutopia](https://www.mutopiaproject.org) e de outros acervos públicos, para tocar e estudar.

O próprio LilyPond interpreta o arquivo e um engraver em Scheme registra cada evento já resolvido
(altura, duração, momento, pauta e voz). Um script Python monta o MusicXML a partir disso. O MIDI
gerado pelo LilyPond serve de gabarito para conferir as notas.

## Uso

Pré-requisitos: `scripts/instalar-lilypond.sh` (baixa o LilyPond 2.26.0 para `ferramentas/`, fora
do git) e o ambiente Python: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`.

```
.venv/bin/python ly2mxml.py ARQ.ly [-o SAIDA.musicxml] [--manter-temp DIR] [--todas] [--forcar]
```

Grava `ARQ.musicxml` no diretório atual (nunca ao lado do original). Com várias partituras
(`\score`), grava `ARQ-1.musicxml`, `ARQ-2.musicxml`... (as que só têm `\midi` e repetem outra
são descartadas, salvo com `--todas`). Avisos vão para stderr. Status: 0 gravou, 2 `convert-ly`
falhou, 3 `lilypond` falhou, 4 sem partitura com notas.

Outras ferramentas (todas em `scripts/`, rodadas com `.venv/bin/python`):

- `comparar-midi.py ARQ.ly`: confere o MusicXML gerado contra o MIDI do próprio LilyPond, nota por
  nota (início, altura, duração, apojaturas), com as repetições desdobradas quando a peça traz a
  cópia `\unfoldRepeats` só para o MIDI.
- `converter-todos.py [PECA...] [-j N]`: converte o acervo em paralelo e grava `saida/_resumo.csv`
  (o teste de regressão, versionado) e `saida/_avisos.log`; no fim diz o que mudou desde a rodada
  anterior.
- `conferir.py PECA [-p N] [-c A-B]`: página HTML com o desenho do LilyPond ao lado do desenho do
  MusicXML (Verovio), para quando o MIDI bate mas algo parece errado.
- `ly2json.sh`, `json-vs-midi.py`: diagnóstico da captura (eventos JSON e a comparação deles com o
  MIDI).

Testes: `.venv/bin/python -m pytest` (os que chamam o LilyPond são pulados se `ferramentas/lilypond`
não existir).

## Documentação

- [Plano](docs/plano.md): objetivo, arquitetura, fases e riscos.
