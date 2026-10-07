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
import bisect
import json
import re
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path

import mido

RAIZ = Path(__file__).resolve().parent.parent
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

def notas_do_midi(caminho):
    """Devolve (notas, ticks_por_semibreve); cada nota é (início, midi, duração) em ticks."""
    arq = mido.MidiFile(str(caminho))
    por_semibreve = arq.ticks_per_beat * 4
    notas = []
    for trilha in arq.tracks:
        tick = 0
        abertas = defaultdict(list)  # (canal, nota) -> ticks de início, em ordem
        for msg in trilha:
            tick += msg.time
            if msg.type == "note_on" and msg.velocity > 0:
                abertas[(msg.channel, msg.note)].append(tick)
            elif msg.type in ("note_off", "note_on"):
                pilha = abertas.get((msg.channel, msg.note))
                if pilha:
                    ini = pilha.pop(0)
                    notas.append((ini, msg.note, tick - ini))
    return notas, por_semibreve


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

NOMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def nome_nota(midi):
    return f"{NOMES[midi % 12]}{midi // 12 - 1}"


# O MIDI tem resolução de ticks inteiros (384 por semínima), e o LilyPond arredonda cada
# início e cada fim: o 14/5 de uma quiáltera de 5 vira 4300,8 ticks. Compara-se em ticks,
# aceitando esta diferença.
TOLERANCIA_TICKS = 2
# Nas durações, o MIDI soma mais arredondamentos (e as apojaturas roubam alguns ticks).
TOLERANCIA_DURACAO = 8


def comparar_partitura(principais, apojaturas, midi):
    """Compara uma partitura. `midi` é (notas, ticks por semibreve) de notas_do_midi."""
    notas_midi, por_semibreve = midi

    def ticks(fr):
        return int(round(fr * por_semibreve))

    # Apojaturas: pegam, no MIDI, uma nota de mesma altura entre o início da nota principal
    # anterior e o início da nota principal em que a apojatura cai. Essas notas saem do
    # multiconjunto antes da comparação principal.
    # Apojatura ligada à nota principal de mesma altura (`\appoggiatura a8~ a2`): o MIDI toca
    # uma nota só, que começa na apojatura. A principal não tem nota própria no MIDI.
    ligadas = set()
    for a in apojaturas:
        if a["lig"]:
            for n in principais:
                if n["midi"] == a["midi"] and n["ini"] == a["ini"] and id(n) not in ligadas:
                    ligadas.add(id(n))
                    break
    principais_midi = [n for n in principais if id(n) not in ligadas]
    inicios = sorted({ticks(n["ini"]) for n in principais})
    restantes = list(notas_midi)
    apoj_ok = 0
    apoj_faltam = []
    for a in sorted(apojaturas, key=lambda x: (x["ini"], x["g"])):
        # `a["ini"]` é o tempo da nota principal; num \afterGrace não há nota principal ali,
        # e a janela termina nele mesmo.
        alvo = ticks(a["ini"])
        pos = bisect.bisect_left(inicios, alvo - TOLERANCIA_TICKS)
        janela_ini = inicios[pos - 1] if pos > 0 else -1
        achou = None
        for i, (ini, midi_n, dur) in enumerate(restantes):
            if (midi_n == a["midi"] and janela_ini + TOLERANCIA_TICKS < ini
                    <= alvo + TOLERANCIA_TICKS):
                achou = i
                break
        if achou is None:
            apoj_faltam.append(a)
        else:
            restantes.pop(achou)
            apoj_ok += 1

    # Notas de mesma altura que se sobrepõem no JSON (duas vozes com o mesmo som): o MIDI não
    # consegue representar as duas, então elas não são comparadas nota a nota.
    sobrepostas = set()
    por_altura = defaultdict(list)
    for n in principais_midi:
        por_altura[n["midi"]].append(n)
    for lista in por_altura.values():
        lista.sort(key=lambda x: x["ini"])
        for i, a in enumerate(lista):
            for b in lista[i + 1:]:
                if b["ini"] >= a["ini"] + a["dur"]:
                    break
                sobrepostas.add(id(a))
                sobrepostas.add(id(b))

    # Casamento por altura: cada nota do JSON pega a nota do MIDI mais próxima no início,
    # dentro da tolerância.
    midi_por_altura = defaultdict(list)
    for ini, altura, dur in restantes:
        midi_por_altura[altura].append([ini, dur, False])
    for lista in midi_por_altura.values():
        lista.sort()

    pares = []       # (nota do JSON, [ini, dur, usada] do MIDI)
    so_json = []
    for n in sorted(principais_midi, key=lambda x: (x["ini"], x["midi"])):
        ini = ticks(n["ini"])
        melhor = None
        for m in midi_por_altura.get(n["midi"], []):
            if m[2]:
                continue
            d = abs(m[0] - ini)
            if d <= TOLERANCIA_TICKS and (melhor is None or d < abs(melhor[0] - ini)):
                melhor = m
        if melhor is None:
            so_json.append(n)
        else:
            melhor[2] = True
            pares.append((n, melhor))
    so_midi = [(m[0], altura) for altura, lista in midi_por_altura.items()
               for m in lista if not m[2]]

    # Uníssono: a mesma altura no mesmo instante em duas vozes. O MIDI funde ou separa as
    # duas; não é erro, só fica registrado.
    casados_json = [(ticks(n["ini"]), n["midi"]) for n, _ in pares]
    casados_midi = [(m[0], n["midi"]) for n, m in pares]

    def perto(lista, ini, altura):
        return any(a == altura and abs(i - ini) <= TOLERANCIA_TICKS for i, a in lista)

    unissonos = 0
    erros_json = []
    for n in so_json:
        if id(n) in sobrepostas or perto(casados_json, ticks(n["ini"]), n["midi"]):
            unissonos += 1
        else:
            erros_json.append(n)
    # Ligadura que o JSON juntou mas o MIDI tocou em duas notas (o MIDI do LilyPond nem sempre
    # funde a ligadura, por exemplo sob um arpejo): a continuação aparece só no MIDI.
    continuacoes = [(ticks(c), n["midi"]) for n in principais for c in n["continuacoes"]]
    nao_fundidas = 0
    erros_midi = []
    for ini, altura in so_midi:
        if perto(continuacoes, ini, altura):
            nao_fundidas += 1
            continue
        if perto(casados_midi, ini, altura) or any(
                id(n) in sobrepostas and n["midi"] == altura
                for n in por_altura.get(altura, [])
                if ticks(n["ini"]) - TOLERANCIA_TICKS <= ini
                <= ticks(n["ini"] + n["dur"]) + TOLERANCIA_TICKS):
            unissonos += 1
        else:
            erros_midi.append((ini, altura))

    # Durações dos pares casados. O MIDI encurta a nota por staccato, \\afterGrace e outras
    # articulações; duração menor no MIDI não é erro (articulação está fora do escopo).
    # Num uníssono (a mesma altura no mesmo instante em duas vozes) o MIDI não separa qual
    # note_off é de qual note_on: compara-se a maior duração de cada lado, uma vez só.
    grupos = defaultdict(lambda: {"json": [], "midi": [], "sobreposta": False})
    for n, m in pares:
        g = grupos[(n["midi"], ticks(n["ini"]))]
        g["json"].append(ticks(n["ini"] + n["dur"]) - ticks(n["ini"]))
        g["midi"].append(m[1])
        g["sobreposta"] = g["sobreposta"] or id(n) in sobrepostas
    for n in so_json:
        chave = (n["midi"], ticks(n["ini"]))
        if chave in grupos:
            grupos[chave]["json"].append(ticks(n["ini"] + n["dur"]) - ticks(n["ini"]))
    dur_ok = 0
    dur_encurtadas = 0
    dur_erradas = []
    comp_de = {(n["midi"], ticks(n["ini"])): n for n, _ in pares}
    for chave, g in grupos.items():
        if g["sobreposta"]:
            continue
        esperado, obtido = max(g["json"]), max(g["midi"])
        if abs(obtido - esperado) <= TOLERANCIA_DURACAO:
            dur_ok += 1
        elif obtido < esperado:
            dur_ok += 1
            dur_encurtadas += 1
        else:
            dur_erradas.append((comp_de[chave], esperado, obtido))

    diferencas = []
    for n in erros_json:
        diferencas.append(f"so no JSON:  c{n['c']} t={n['ini']} {nome_nota(n['midi'])} "
                          f"dur={n['dur']}")
    for ini, altura in sorted(erros_midi):
        diferencas.append(f"so no MIDI:  t={Fraction(ini, por_semibreve)} {nome_nota(altura)}")
    for n, esperado, obtido in dur_erradas:
        diferencas.append(f"duracao: c{n['c']} t={n['ini']} {nome_nota(n['midi'])} "
                          f"JSON={n['dur']} ({esperado} ticks) MIDI={obtido} ticks")
    for a in apoj_faltam:
        diferencas.append(f"apojatura sem nota no MIDI: c{a['c']} t={a['ini']} g={a['g']} "
                          f"{nome_nota(a['midi'])}")

    return {
        "notas_json": len(principais),
        "notas_ok": len(principais) - len(erros_json),
        "duracoes_ok": dur_ok,
        "duracoes_total": sum(1 for g in grupos.values() if not g["sobreposta"]),
        "encurtadas": dur_encurtadas,
        "apoj_ok": apoj_ok,
        "apoj_total": len(apojaturas),
        "unissonos": unissonos,
        "nao_fundidas": nao_fundidas,
        "apoj_ligadas": len(ligadas),
        "so_json": len(erros_json),
        "so_midi": len(erros_midi),
        "diferencas": diferencas,
        "ok": not (erros_json or erros_midi or dur_erradas or apoj_faltam),
    }


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
