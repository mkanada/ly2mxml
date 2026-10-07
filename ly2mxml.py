#!/usr/bin/env python3
"""Converte uma partitura do LilyPond (.ly) em MusicXML.

O LilyPond interpreta o arquivo e a captura em Scheme registra cada evento; o Python monta o
MusicXML. Ver docs/plano.md.

Status: 0 gravou; 1 erro do programa; 2 o convert-ly falhou (ou o arquivo não existe);
3 o lilypond falhou; 4 nenhuma partitura com notas.
"""
import argparse
import shutil
import sys
import tempfile
from collections import Counter
from pathlib import Path

from conversor import lilypond, pipeline


def imprimir_avisos(avisos):
    for texto, n in Counter(avisos).items():
        print(f"aviso: {texto}" + (f" (×{n})" if n > 1 else ""), file=sys.stderr)


def guardar(manter: Path | None, tmp: Path):
    if manter is None:
        return
    manter.mkdir(parents=True, exist_ok=True)
    for f in tmp.iterdir():
        if f.is_file():
            shutil.copy2(f, manter / f.name)


def converter(arq, saida=None, manter=None, todas=False, forcar=False):
    """Devolve (status, [arquivos gravados], avisos)."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        try:
            r = pipeline.converter_peca(arq, tmp, saida, todas, forcar, sem_midi=manter is None)
        except lilypond.ErroLilypondAusente as erro:
            print(f"erro: {erro}", file=sys.stderr)
            return 3, [], []
        except lilypond.ErroConvertLy as erro:
            print(f"erro: {erro}", file=sys.stderr)
            return 2, [], []
        except lilypond.ErroLilypond as erro:
            print(f"erro: {erro}", file=sys.stderr)
            guardar(manter, tmp)
            return 3, [], []
        except pipeline.ErroSemPartitura as erro:
            print(f"erro: {erro}", file=sys.stderr)
            guardar(manter, tmp)
            return 4, [], []
        guardar(manter, tmp)
    avisos = list(r.avisos)
    for g in r.gravadas:
        avisos += g.avisos
    return 0, [g.arquivo for g in r.gravadas], avisos


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("arquivo", type=Path, help="partitura .ly")
    ap.add_argument("-o", "--saida", type=Path, help="arquivo .musicxml (padrão: BASE.musicxml)")
    ap.add_argument("--manter-temp", type=Path, metavar="DIR",
                    help="grava o .ly convertido, o envelope, o JSON, os MIDI e o log em DIR")
    ap.add_argument("--todas", action="store_true", help="converte também as partituras so_midi")
    ap.add_argument("--forcar", action="store_true",
                    help="converte mesmo se o lilypond sair com erro (usa o que foi capturado)")
    args = ap.parse_args(argv)

    if not args.arquivo.is_file():
        print(f"erro: arquivo não encontrado: {args.arquivo}", file=sys.stderr)
        return 2
    try:
        status, gravados, avisos = converter(args.arquivo, args.saida, args.manter_temp,
                                             args.todas, args.forcar)
    except Exception as erro:       # erro do programa
        import traceback
        traceback.print_exc()
        print(f"erro: {type(erro).__name__}: {erro}", file=sys.stderr)
        return 1
    imprimir_avisos(avisos)
    for g in gravados:
        print(g)
    return status


if __name__ == "__main__":
    sys.exit(main())
