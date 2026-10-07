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

Conferir contra o MIDI do próprio LilyPond: `.venv/bin/python scripts/comparar-midi.py ARQ.ly`.
Testes: `.venv/bin/python -m pytest`.

## Documentação

- [Plano](docs/plano.md): objetivo, arquitetura, fases e riscos.
