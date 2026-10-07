#!/usr/bin/env python3
"""Compara as notas capturadas (JSON) com o MIDI que o LilyPond gerou — passo 06.

Uso:
    scripts/json-vs-midi.py ARQ.ly [ARQ.ly ...]    roda scripts/ly2json.sh num temporário
    scripts/json-vs-midi.py DIR [DIR ...]          usa DIR/*.eventos.jsonl, os .midi e o log

Status de saída: 0 se todas as partituras comparadas batem, 1 se alguma não bate, 2 se não deu
para rodar. Não usa conversor/eventos.py: lê o JSON direto, só com o necessário.

Tempo sempre como Fraction na unidade semibreve (1 = semibreve). Nunca float.
"""
import argparse
import json
import re
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path


RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from conversor.comparacao import comparar_partitura, notas_do_midi  # noqa: E402
LY2JSON = RAIZ / "scripts" / "ly2json.sh"

# Quantas diferenças mostrar por partitura.
MAX_DIFERENCAS = 10


# ---------------------------------------------------------------------------
# JSON
# ---------------------------------------------------------------------------

def ler_jsonl(caminho):
    """Linhas do .eventos.jsonl como dicionários."""
    linhas = []
    with open(caminho, encoding="utf-8") as f:
        for linha in f:
            linha = linha.strip()
            if linha:
                linhas.append(json.loads(linha))
    return linhas


def notas_do_json(eventos, p):
    """Separa as notas da partitura `p` em principais e apojaturas.

    Devolve (principais, apojaturas, sem_destino): cada nota é um dicionário com
    `ini`, `midi`, `dur` (Fraction), `c` e `lig`. As ligaduras já vêm juntadas: a nota que
    começa a ligadura absorve a duração das continuações (que somem da lista).
    """
    principais = []
    apojaturas = []
    for e in eventos:
        if e.get("tipo") != "nota" or e["p"] != p:
            continue
        nota = {
            "ini": Fraction(e["t"]),
            "midi": e["midi"],
            "dur": Fraction(e["dur"]),
            "c": e["c"],
            "voz": e["voz"],
            "lig": e["lig"],
            "g": Fraction(e["g"]),
        }
        (apojaturas if nota["g"] != 0 else principais).append(nota)

    # Ligaduras: a continuação é a próxima nota de mesma altura na mesma voz, que começa
    # quando a anterior termina ou depois (um arpejo `c16~ g~ c~ ... <c g c'>4` liga o dó
    # ao acorde final, com outras notas no meio).
    por_voz = defaultdict(list)
    for n in sorted(principais, key=lambda x: x["ini"]):
        por_voz[(n["voz"], n["midi"])].append(n)
    absorvidas = set()
    sem_destino = 0
    for n in principais:
        n["continuacoes"] = []
    for n in principais:
        if id(n) in absorvidas:
            continue
        atual = n
        while atual["lig"]:
            fim = atual["ini"] + atual["dur"]
            seguinte = next((x for x in por_voz[(n["voz"], n["midi"])]
                             if x["ini"] >= fim and id(x) not in absorvidas and x is not n),
                            None)
            if seguinte is None:
                sem_destino += 1
                break
            absorvidas.add(id(seguinte))
            n["continuacoes"].append(seguinte["ini"])
            n["dur"] = seguinte["ini"] + seguinte["dur"] - n["ini"]
            atual = seguinte
    return [n for n in principais if id(n) not in absorvidas], apojaturas, sem_destino


# ---------------------------------------------------------------------------
# MIDI
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Log
# ---------------------------------------------------------------------------

def midis_do_log(caminho_log):
    """Nomes dos MIDI, na ordem em que o LilyPond os escreveu."""
    nomes = []
    with open(caminho_log, encoding="utf-8", errors="replace") as f:
        for linha in f:
            m = re.search(r"MIDI output to `(.+?)'", linha)
            if m:
                nomes.append(m.group(1))
    return nomes


# ---------------------------------------------------------------------------
# Comparação
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Execução
# ---------------------------------------------------------------------------

def rodar_ly2json(arq, saida):
    r = subprocess.run([str(LY2JSON), str(arq), str(saida)], capture_output=True, text=True)
    return r.returncode, r.stderr


def comparar_diretorio(saida, base, avisos_extra=()):
    """Compara todas as partituras de `saida/base.eventos.jsonl`. Devolve (linhas, ok)."""
    jsonl = saida / f"{base}.eventos.jsonl"
    log = saida / f"{base}.lilypond.log"
    if not jsonl.exists():
        return [f"{base}: sem {jsonl.name}"], False
    eventos = ler_jsonl(jsonl)
    partituras = [e["p"] for e in eventos if e.get("tipo") == "partitura"]
    nomes = midis_do_log(log) if log.exists() else []
    linhas = list(avisos_extra)

    if not partituras:
        linhas.append(f"{base}: nenhuma partitura capturada")
        return linhas, False
    if len(nomes) != len(partituras):
        linhas.append(f"{base}: {len(partituras)} partituras e {len(nomes)} MIDI no log; "
                      f"nao comparo")
        return linhas, False
    repetidos = {n for n, q in Counter(nomes).items() if q > 1}

    todas_ok = True
    for p, nome in zip(partituras, nomes):
        if nome in repetidos:
            linhas.append(f"{base} p{p}: MIDI '{nome}' repetido no log; nao comparo")
            continue
        caminho_midi = saida / nome
        if not caminho_midi.exists():
            linhas.append(f"{base} p{p}: MIDI '{nome}' nao existe; nao comparo")
            todas_ok = False
            continue
        principais, apojaturas, sem_destino = notas_do_json(eventos, p)
        r = comparar_partitura(principais, apojaturas, notas_do_midi(caminho_midi))
        extras = []
        if r["encurtadas"]:
            extras.append(f"encurtadas no MIDI {r['encurtadas']}")
        if r["unissonos"]:
            extras.append(f"unissonos {r['unissonos']}")
        if r["nao_fundidas"]:
            extras.append(f"ligaduras nao fundidas no MIDI {r['nao_fundidas']}")
        if r["apoj_ligadas"]:
            extras.append(f"apojaturas ligadas {r['apoj_ligadas']}")
        if sem_destino:
            extras.append(f"ligaduras sem destino {sem_destino}")
        so_midi = " so_midi" if any(e.get("tipo") == "partitura" and e["p"] == p
                                    and e.get("so_midi") for e in eventos) else ""
        linhas.append(
            f"{base} p{p}{so_midi}: notas {r['notas_ok']}/{r['notas_json']}  "
            f"duracoes {r['duracoes_ok']}/{r['duracoes_total']}  "
            f"apojaturas {r['apoj_ok']}/{r['apoj_total']}"
            + ("  " + "  ".join(extras) if extras else "")
            + ("  OK" if r["ok"] else "  FALHA"))
        for d in r["diferencas"][:MAX_DIFERENCAS]:
            linhas.append(f"  {d}")
        if len(r["diferencas"]) > MAX_DIFERENCAS:
            linhas.append(f"  ... mais {len(r['diferencas']) - MAX_DIFERENCAS}")
        todas_ok = todas_ok and r["ok"]
    return linhas, todas_ok


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("entradas", nargs="+", help="arquivos .ly ou diretórios com .eventos.jsonl")
    args = ap.parse_args(argv)

    status = 0
    for entrada in map(Path, args.entradas):
        if entrada.is_dir():
            saidas = [(entrada, j.name[: -len(".eventos.jsonl")], ())
                      for j in sorted(entrada.glob("*.eventos.jsonl"))]
            if not saidas:
                print(f"{entrada}: sem .eventos.jsonl", file=sys.stderr)
                status = max(status, 2)
                continue
            execucoes = [(d, b, a, None) for d, b, a in saidas]
        else:
            execucoes = [(None, entrada.stem, (), entrada)]

        for dir_pronto, base, avisos, arq in execucoes:
            with tempfile.TemporaryDirectory() as tmp:
                if arq is not None:
                    saida = Path(tmp)
                    codigo, erro = rodar_ly2json(arq, saida)
                    if codigo != 0:
                        # Compilar com erro ainda pode ter deixado partituras; só avisa.
                        print(f"{base}: ly2json saiu com status {codigo}", file=sys.stderr)
                        if not (saida / f"{base}.eventos.jsonl").exists():
                            status = max(status, 2)
                            continue
                else:
                    saida = dir_pronto
                linhas, ok = comparar_diretorio(saida, base, avisos)
            print("\n".join(linhas))
            if not ok:
                status = max(status, 1)
    return status


if __name__ == "__main__":
    sys.exit(main())
