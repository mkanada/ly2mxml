#!/usr/bin/env python3
"""Compara o MusicXML gerado com o MIDI do LilyPond, nota por nota — passo 11.

Uso:
    scripts/comparar-midi.py ARQ.ly [ARQ.ly ...]
    scripts/comparar-midi.py ARQ.ly --musicxml X.musicxml   (compara um MusicXML já gerado)

Converte o `.ly` com a captura (com o MIDI ligado), grava o MusicXML num temporário e compara cada
partitura gravada com o MIDI correspondente (pela ordem do log do LilyPond). O MusicXML é lido
direto do XML, sem o music21. Repetições não são desdobradas no MusicXML; o MIDI do mesmo score
também não é.

Status: 0 se todas batem, 1 se alguma não bate, 2 se não deu para converter. A comparação com a
partitura `so_midi` (cópia só para o MIDI) é informativa e não muda o status.
"""
import argparse
import sys
import tempfile
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from conversor import comparacao, lilypond, pipeline  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("arquivos", nargs="+", type=Path)
    args = ap.parse_args(argv)

    status = 0
    for arq in args.arquivos:
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            try:
                resultado = pipeline.converter_peca(arq, tmp, tmp / f"{arq.stem}.musicxml",
                                                    sem_midi=False)
            except (lilypond.ErroConvertLy, lilypond.ErroLilypond, pipeline.ErroSemPartitura,
                    lilypond.ErroLilypondAusente) as erro:
                print(f"{arq.stem}: {str(erro).splitlines()[0]}", file=sys.stderr)
                status = max(status, 2)
                continue
            for saida in comparacao.comparar_resultado(arq.stem, resultado):
                print("\n".join(saida["linhas"]))
                if saida["ok"] is False:
                    status = max(status, 1)
    return status


if __name__ == "__main__":
    sys.exit(main())
