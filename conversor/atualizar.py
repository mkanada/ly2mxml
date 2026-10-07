"""`python -m conversor.atualizar ARQ.ly SAIDA.ly`: atualiza o .ly para a sintaxe 2.26.

Faz o que a captura faz antes de rodar o LilyPond (`compat` antes e depois do `convert-ly`), para
o `scripts/ly2json.sh` ver o mesmo arquivo que o `ly2mxml.py`. Escreve as regras aplicadas em
stderr.
"""
import sys
import tempfile
from pathlib import Path

from . import lilypond


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        print("uso: python -m conversor.atualizar ARQ.ly SAIDA.ly", file=sys.stderr)
        return 1
    arq, saida = Path(argv[0]), Path(argv[1])
    with tempfile.TemporaryDirectory() as tmp:
        try:
            convertido, regras = lilypond._atualizar(arq.resolve(), Path(tmp), arq.stem)
        except lilypond.ErroConvertLy as erro:
            print(erro, file=sys.stderr)
            return 2
        saida.write_text(convertido.read_text(encoding="utf-8"), encoding="utf-8")
    for regra in regras:
        print(f"compatibilidade com sintaxe antiga: {regra}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
