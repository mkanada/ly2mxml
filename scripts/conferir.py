#!/usr/bin/env python3
"""Conferência visual — passo 17: o desenho do LilyPond ao lado do desenho do MusicXML.

Uso:
    scripts/conferir.py PECA [-p N] [-c A-B] [-o DIR]

PECA é o nome (sem .ly) de uma peça de dados/ ou o caminho de um .ly. Escreve em DIR (padrão
`saida/conferir/`) uma página `PECA.html` com duas colunas, uma linha por página: à esquerda o SVG
que o próprio LilyPond desenha, à direita o SVG que o Verovio desenha do MusicXML gerado.

  -p N     só a página N de cada lado
  -c A-B   no Verovio, só os compassos A a B (o LilyPond continua por página)

As quebras de linha e de página não batem entre os dois lados (o MusicXML não leva o layout):
compare compasso a compasso, pelos números. Imprime o caminho do HTML; abrir é com o usuário.
"""
import argparse
import html
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from conversor import lilypond, pipeline  # noqa: E402


def paginas_verovio(musicxml: Path, destino: Path, rotulo: str, compassos: str | None):
    """SVG do Verovio, uma por página. Devolve os caminhos em ordem."""
    import verovio

    tk = verovio.toolkit()
    tk.setOptions({"pageWidth": 2100, "pageHeight": 2970, "scale": 40, "footer": "none",
                   "header": "none"})
    if not tk.loadFile(str(musicxml)):
        raise RuntimeError(f"o Verovio não leu {musicxml.name}")
    if compassos:
        tk.select({"measureRange": compassos})
        tk.redoLayout()
    caminhos = []
    for n in range(1, tk.getPageCount() + 1):
        caminho = destino / f"{rotulo}-mxml-{n}.svg"
        caminho.write_text(tk.renderToSVG(n), encoding="utf-8")
        caminhos.append(caminho)
    return caminhos


def montar_html(base, esquerda, direita, pagina, destino: Path) -> Path:
    n = max(len(esquerda), len(direita))
    linhas = []
    for i in range(n):
        if pagina is not None and i + 1 != pagina:
            continue
        lado = lambda lista: (f'<img src="{html.escape(lista[i].name)}" alt="página {i + 1}">'
                              if i < len(lista) else "<em>(sem página)</em>")
        linhas.append(f'<section><h2>página {i + 1}</h2><div class="par">'
                      f'<div><h3>LilyPond</h3>{lado(esquerda)}</div>'
                      f'<div><h3>MusicXML (Verovio)</h3>{lado(direita)}</div></div></section>')
    pagina_html = f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><title>{html.escape(base)}</title>
<style>
body {{ font-family: sans-serif; margin: 1rem; }}
.par {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }}
img {{ width: 100%; border: 1px solid #ccc; background: white; }}
h2, h3 {{ margin: .4rem 0; }}
</style></head><body><h1>{html.escape(base)}</h1>
{chr(10).join(linhas)}
</body></html>
"""
    saida = destino / f"{base}.html"
    saida.write_text(pagina_html, encoding="utf-8")
    return saida


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("peca", help="nome em dados/ (sem .ly) ou caminho de um .ly")
    ap.add_argument("-p", type=int, metavar="N", help="só a página N")
    ap.add_argument("-c", metavar="A-B", help="só os compassos A a B no Verovio")
    ap.add_argument("-o", type=Path, default=RAIZ / "saida" / "conferir", metavar="DIR")
    args = ap.parse_args(argv)

    arq = Path(args.peca)
    if not arq.is_file():
        arq = RAIZ / "dados" / f"{args.peca}.ly"
    if not arq.is_file():
        print(f"erro: não achei {args.peca}", file=sys.stderr)
        return 2
    destino = args.o
    destino.mkdir(parents=True, exist_ok=True)
    base = arq.stem
    try:
        esquerda = lilypond.renderizar_svg(arq, destino, base)
        with tempfile.TemporaryDirectory() as tmp:
            r = pipeline.converter_peca(arq, Path(tmp), destino / f"{base}.musicxml",
                                        sem_midi=True)
            direita = []
            for g in r.gravadas:
                direita += paginas_verovio(g.arquivo, destino, g.arquivo.stem, args.c)
    except (lilypond.ErroConvertLy, lilypond.ErroLilypond, pipeline.ErroSemPartitura) as erro:
        print(f"erro: {erro}", file=sys.stderr)
        return 3
    print(montar_html(base, esquerda, direita, args.p, destino))
    return 0


if __name__ == "__main__":
    sys.exit(main())
