#!/usr/bin/env python3
"""Converte o acervo em paralelo, compara com o MIDI e grava o resumo de regressão — passo 16.

Uso:
    scripts/converter-todos.py                          tudo de dados/
    scripts/converter-todos.py maple fur_Elise_WoO59    só algumas (nome sem .ly)
    scripts/converter-todos.py -j 4                     4 peças por vez (padrão: nº de núcleos)
    scripts/converter-todos.py --acervo DIR             outro diretório de .ly

Grava em saida/: os .musicxml, `_resumo.csv` (uma linha por partitura; é o teste de regressão e
vai para o git) e `_avisos.log`. No fim imprime o que mudou em relação ao resumo anterior.
Rodando só algumas peças, as linhas das outras são mantidas.
"""
import argparse
import csv
import os
import sys
import tempfile
import time
import traceback
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

COLUNAS = ["peca", "p", "versao", "status", "segundos", "compassos", "pautas", "vozes", "notas",
           "pausas", "acordes", "ligaduras", "quialteras", "apojaturas", "repeticoes", "casas",
           "formula", "armadura", "midi", "avisos", "hash"]
TIMEOUT = 120


def converter(ly: Path, saida: Path):
    """Converte uma peça. Devolve `(linhas, avisos)`: uma linha (dicionário) por partitura
    gravada e os avisos por partitura. Nunca levanta."""
    from conversor import comparacao, lilypond, pipeline, resumo

    ini = time.time()
    base = ly.stem
    versao = ""
    try:
        versao = lilypond.versao_do_arquivo(ly) or ""
    except Exception:
        pass

    def erro(status, texto):
        linha = {c: "" for c in COLUNAS}
        linha.update(peca=base, p=1, versao=versao, status=status,
                     segundos=f"{time.time() - ini:.1f}", avisos=1)
        return [linha], {1: [texto]}

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        try:
            r = pipeline.converter_peca(ly, tmp, saida / f"{base}.musicxml", sem_midi=False,
                                        timeout=TIMEOUT)
        except lilypond.ErroConvertLy as e:
            return erro("ERRO-convert", str(e).splitlines()[-1] if str(e) else "convert-ly")
        except lilypond.ErroLilypond as e:
            return erro("ERRO-lilypond", "; ".join(str(e).splitlines()[1:4]) or str(e))
        except pipeline.ErroSemPartitura as e:
            return erro("ERRO-lilypond", str(e))
        except Exception as e:                       # um erro nunca derruba o lote
            return erro("ERRO", f"{type(e).__name__}: {e} "
                        f"({traceback.format_exc().splitlines()[-3].strip()})")

        linhas, avisos = [], {}
        for n, g in enumerate(r.gravadas, 1):
            lin, ok, comp = comparacao.comparar_gravada(base, r, g)
            texto_avisos = [a for a in g.avisos]
            if len(r.gravadas) > 1:
                # O nome do arquivo já foi dado pelo pipeline (BASE-N); o `p` da linha é o N.
                pass
            dados = resumo.resumir(g.arquivo)
            if comp is None:
                midi = "não comparado"
            else:
                midi = f"{comp['notas_ok']}/{comp['notas_json']}"
            if ok is False:
                status = "midi-difere"
            elif texto_avisos:
                status = "avisos"
            else:
                status = "ok"
            if ok is False:
                texto_avisos = texto_avisos + [l.strip() for l in lin[1:6]]
            linha = {"peca": base, "p": n, "versao": versao, "status": status,
                     "segundos": f"{time.time() - ini:.1f}", "midi": midi,
                     "avisos": len(texto_avisos), **dados}
            linhas.append(linha)
            avisos[n] = texto_avisos
        return linhas, avisos


def trabalhar(args):
    ly, saida = args
    return converter(Path(ly), Path(saida))


def ler_resumo(caminho: Path):
    if not caminho.exists():
        return {}
    with open(caminho, newline="", encoding="utf-8") as f:
        return {(l["peca"], l["p"]): l for l in csv.DictReader(f)}


def diferencas(antigo: dict, novo: dict):
    """Colunas que mudaram (menos `segundos`)."""
    return [c for c in COLUNAS if c != "segundos" and str(antigo.get(c, "")) != str(novo.get(c, ""))]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("pecas", nargs="*", help="nomes (sem .ly); padrão: todas")
    ap.add_argument("-j", "--jobs", type=int, default=os.cpu_count() or 1)
    ap.add_argument("--acervo", type=Path, default=RAIZ / "dados")
    ap.add_argument("--saida", type=Path, default=RAIZ / "saida")
    args = ap.parse_args(argv)

    todos = sorted(args.acervo.glob("*.ly"))
    if args.pecas:
        nomes = set(args.pecas)
        todos = [p for p in todos if p.stem in nomes]
        faltam = nomes - {p.stem for p in todos}
        if faltam:
            print(f"não achei em {args.acervo}: {', '.join(sorted(faltam))}", file=sys.stderr)
    if not todos:
        print("nenhuma peça para converter", file=sys.stderr)
        return 2
    args.saida.mkdir(parents=True, exist_ok=True)
    csv_path = args.saida / "_resumo.csv"
    anterior = ler_resumo(csv_path)

    ini = time.time()
    novas, avisos_por = {}, {}
    with ProcessPoolExecutor(max_workers=args.jobs) as pool:
        for ly, (linhas, avisos) in zip(todos, pool.map(
                trabalhar, [(str(p), str(args.saida)) for p in todos])):
            for lin in linhas:
                novas[(lin["peca"], str(lin["p"]))] = lin
                avisos_por[(lin["peca"], str(lin["p"]))] = avisos.get(lin["p"], [])
            print(f"{ly.stem}: " + ", ".join(f"p{l['p']} {l['status']}" for l in linhas),
                  file=sys.stderr)

    # Mantém as linhas das peças que não foram rodadas.
    rodadas = {p.stem for p in todos}
    resumo = {k: v for k, v in anterior.items() if k[0] not in rodadas}
    resumo.update({k: {c: str(v.get(c, "")) for c in COLUNAS} for k, v in novas.items()})
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, COLUNAS, lineterminator="\n")
        w.writeheader()
        for k in sorted(resumo, key=lambda k: (k[0].lower(), int(k[1]))):
            w.writerow(resumo[k])

    with open(args.saida / "_avisos.log", "w", encoding="utf-8") as f:
        for k in sorted(avisos_por, key=lambda k: (k[0].lower(), int(k[1]))):
            if avisos_por[k]:
                f.write(f"== {k[0]} (p{k[1]}) ==\n")
                for a in avisos_por[k]:
                    f.write(f"aviso: {a}\n")

    mudaram = [(k, diferencas(anterior[k], v)) for k, v in sorted(novas.items())
               if k in anterior and diferencas(anterior[k], v)]
    novas_linhas = [k for k in novas if k not in anterior]
    if anterior:
        total = len(mudaram) + len(novas_linhas)
        print(f"{total} de {len(novas)} partituras mudaram em relação ao resumo anterior:")
        for k, cols in mudaram:
            print(f"  {k[0]} p{k[1]}: " + ", ".join(
                f"{c} {anterior[k].get(c, '')} → {novas[k].get(c, '')}" for c in cols))
        for k in novas_linhas:
            print(f"  {k[0]} p{k[1]}: nova")
    else:
        print("sem resumo anterior")

    status = {}
    for v in novas.values():
        status[v["status"]] = status.get(v["status"], 0) + 1
    partes = ", ".join(f"{n} {s}" for s, n in sorted(status.items()))
    print(f"{len(todos)} peças, {len(novas)} partituras: {partes} "
          f"(tempo total {time.time() - ini:.0f} s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
