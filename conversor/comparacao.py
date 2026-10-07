"""Comparação de notas entre duas fontes (JSON/MusicXML contra o MIDI do LilyPond).

Usada por `scripts/json-vs-midi.py` (passo 06), `scripts/comparar-midi.py` (passo 11) e pelo lote
(passo 16). Uma "nota" é um dicionário com `ini` e `dur` (Fraction, em semibreves), `midi`, `c`
(compasso, só para mensagens), `voz`, `lig` (começa ligadura; só para apojaturas) e `g` (negativo
nas apojaturas). Tempo em ticks só dentro da comparação.
"""
import bisect
import re
from collections import defaultdict
from fractions import Fraction

import mido


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

    # Peça que começa por apojatura: o MIDI do LilyPond atrasa tudo o que vem depois (a
    # apojatura toca em 0 e a primeira nota principal só depois, com todas as outras).
    if principais and apojaturas:
        primeiro = min(n["ini"] for n in principais)
        if any(a["ini"] == primeiro for a in apojaturas):
            alturas = {n["midi"] for n in principais if n["ini"] == primeiro}
            depois = sorted(ini for ini, altura, _ in notas_midi
                            if altura in alturas and ini > ticks(primeiro))
            atraso = depois[0] - ticks(primeiro) if depois else 0
            if 0 < atraso < por_semibreve // 4:
                notas_midi = [(ini - atraso if ini >= atraso else ini, altura, dur)
                              for ini, altura, dur in notas_midi]

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
    inicios_por_voz = defaultdict(set)
    for n in principais:
        inicios_por_voz[n["voz"]].add(ticks(n["ini"]))
    inicios_por_voz = {v: sorted(x) for v, x in inicios_por_voz.items()}
    restantes = list(notas_midi)
    apoj_ok = 0
    apoj_faltam = []
    for a in sorted(apojaturas, key=lambda x: (x["ini"], x["g"])):
        # `a["ini"]` é o tempo da nota principal; num \afterGrace não há nota principal ali,
        # e a janela termina nele mesmo.
        alvo = ticks(a["ini"])
        # A janela começa na nota anterior da mesma voz (a apojatura roubou tempo dela).
        inicios = inicios_por_voz.get(a["voz"], [])
        pos = bisect.bisect_left(inicios, alvo - TOLERANCIA_TICKS)
        janela_ini = inicios[pos - 1] if pos > 0 else -10**9
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
    tremolos = 0
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
        elif any(n["midi"] == altura and ticks(n["ini"]) < ini < ticks(n["ini"] + n["dur"])
                 for n, _ in pares):
            # O MIDI repete a mesma altura dentro de uma nota longa: tremolo, que a montagem
            # escreve como nota simples (a captura avisa).
            tremolos += 1
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
        "tremolos": tremolos,
        "apoj_ligadas": len(ligadas),
        "so_json": len(erros_json),
        "so_midi": len(erros_midi),
        "diferencas": diferencas,
        "ok": not (erros_json or erros_midi or dur_erradas or apoj_faltam),
    }


# ---------------------------------------------------------------------------
# Notas do MusicXML (lidas direto do XML, sem passar pelo music21)
# ---------------------------------------------------------------------------

PASSOS = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def _ler_compassos(caminho):
    """Compassos de cada parte do MusicXML: dicionários com as notas (tempo relativo ao início
    do compasso, em semínimas), o tamanho, a repetição e as casas."""
    import xml.etree.ElementTree as ET

    raiz = ET.parse(str(caminho)).getroot()
    partes = []
    for parte in raiz.findall("part"):
        divisoes = 1
        compassos = []
        casa = None                       # números da casa em que estamos
        for el_compasso in parte.findall("measure"):
            md = {"numero": el_compasso.get("number", "?"), "notas": [], "avanco": 0,
                  "forward": False, "backward": False, "vezes": 2, "casas": None}
            cursor = 0
            maior = 0
            ultimo_inicio = 0
            fecha_casa = False
            for el in el_compasso:
                if el.tag == "attributes":
                    d = el.find("divisions")
                    if d is not None:
                        divisoes = int(d.text)
                elif el.tag == "barline":
                    rep = el.find("repeat")
                    fim = el.get("location", "right") == "right"
                    if rep is not None:
                        if rep.get("direction") == "forward":
                            md["forward"] = True
                        else:
                            md["backward"] = True
                            md["vezes"] = int(rep.get("times", "2"))
                    end = el.find("ending")
                    if end is not None:
                        if end.get("type") == "start":
                            casa = {int(x) for x in re.findall(r"\d+", end.get("number", ""))}
                        else:
                            fecha_casa = True
                elif el.tag == "backup":
                    cursor -= int(el.find("duration").text)
                elif el.tag == "forward":
                    cursor += int(el.find("duration").text)
                elif el.tag == "note":
                    acorde = el.find("chord") is not None
                    graca = el.find("grace") is not None
                    dur = 0 if graca else int(el.find("duration").text)
                    inicio = ultimo_inicio if acorde else cursor
                    if not acorde:
                        ultimo_inicio = cursor
                    if el.find("rest") is None:
                        p = el.find("pitch")
                        midi = (12 * (int(p.find("octave").text) + 1) + PASSOS[p.find("step").text]
                                + int(float(p.findtext("alter", "0"))))
                        md["notas"].append({
                            "ini": Fraction(inicio, divisoes),
                            "dur": Fraction(dur, divisoes), "midi": midi,
                            "voz": el.findtext("voice", "1"),
                            "ligas": {t.get("type") for t in el.findall("tie")},
                            "graca": graca})
                    if not acorde:
                        cursor += dur
                    maior = max(maior, cursor)
            md["avanco"] = Fraction(maior, divisoes)
            md["casas"] = casa
            if fecha_casa:
                casa = None
            compassos.append(md)
        partes.append(compassos)
    return partes


def _ordem_de_execucao(compassos):
    """Índices dos compassos na ordem em que são tocados, com as repetições desdobradas.

    Uma repetição vai do `forward` (ou do começo) ao `backward`; a casa só toca nas passadas
    que ela numera. O `times` do `backward` diz quantas passadas há (2 se omitido).
    """
    ordem = []
    inicio, passada, i, saltou, passos = 0, 1, 0, False, 0
    while i < len(compassos):
        passos += 1
        if passos > 100 * (len(compassos) + 1):
            break                              # estrutura de repetição malformada
        md = compassos[i]
        if md["forward"] and not saltou:
            inicio, passada = i, 1
        saltou = False
        if md["casas"] is not None and passada not in md["casas"]:
            i += 1
            continue
        ordem.append(i)
        if md["backward"] and passada < md["vezes"]:
            passada += 1
            i, saltou = inicio, True
            continue
        if md["backward"]:
            passada, inicio = 1, i + 1
        i += 1
    return ordem


def notas_do_musicxml(caminho, expandir=False):
    """Lê as notas de um MusicXML escrito por `conversor.montagem`.

    Não usa o music21: o music21 tocaria apojaturas e ligaduras do jeito dele, e a comparação
    mediria o music21. Aqui cada nota é lida como está no arquivo. Devolve
    `(principais, apojaturas)` no mesmo formato de `scripts/json-vs-midi.py`: ligaduras já
    juntadas, apojatura com o `ini` da nota principal que a segue. Com `expandir`, as repetições
    e as casas são desdobradas na ordem em que são tocadas (para comparar com o MIDI de um
    `\\score` com `\\unfoldRepeats`); sem ele, cada trecho vale uma vez, como no MIDI do mesmo
    `\\score`.
    """
    principais, apojaturas = [], []
    for compassos in _ler_compassos(caminho):
        ordem = _ordem_de_execucao(compassos) if expandir else range(len(compassos))
        inicio_compasso = Fraction(0)          # em semínimas
        abertas = {}                           # (voz, midi) -> nota aberta por ligadura
        for i in ordem:
            md = compassos[i]
            for n in md["notas"]:
                ini = (inicio_compasso + n["ini"]) / 4
                nota = {"ini": ini, "dur": n["dur"] / 4, "midi": n["midi"],
                        "c": md["numero"], "voz": n["voz"], "lig": "start" in n["ligas"],
                        "g": Fraction(0), "continuacoes": []}
                chave = (n["voz"], n["midi"])
                anterior = abertas.get(chave)
                if n["graca"]:
                    nota["g"] = Fraction(-1)
                    apojaturas.append(nota)
                    if "start" in n["ligas"]:
                        abertas[chave] = nota
                elif "stop" in n["ligas"] and anterior is not None and anterior["g"] == 0:
                    anterior["dur"] = ini + nota["dur"] - anterior["ini"]
                    anterior["continuacoes"].append(ini)
                    if "start" not in n["ligas"]:
                        del abertas[chave]
                else:
                    principais.append(nota)
                    if "start" in n["ligas"]:
                        abertas[chave] = nota
                    else:
                        abertas.pop(chave, None)
            inicio_compasso += md["avanco"]
    return principais, apojaturas


def formatar(base, p, r, so_midi=False):
    """Uma linha de resumo por partitura (a mesma do passo 06) e as primeiras diferenças."""
    extras = []
    if r["encurtadas"]:
        extras.append(f"encurtadas no MIDI {r['encurtadas']}")
    if r["unissonos"]:
        extras.append(f"unissonos {r['unissonos']}")
    if r["nao_fundidas"]:
        extras.append(f"ligaduras nao fundidas no MIDI {r['nao_fundidas']}")
    if r["apoj_ligadas"]:
        extras.append(f"apojaturas ligadas {r['apoj_ligadas']}")
    if r["tremolos"]:
        extras.append(f"repetições de tremolo no MIDI {r['tremolos']}")
    linhas = [f"{base} p{p}{' so_midi' if so_midi else ''}: notas {r['notas_ok']}/{r['notas_json']}"
              f"  duracoes {r['duracoes_ok']}/{r['duracoes_total']}"
              f"  apojaturas {r['apoj_ok']}/{r['apoj_total']}"
              + ("  " + "  ".join(extras) if extras else "")
              + ("  OK" if r["ok"] else "  FALHA")]
    for d in r["diferencas"][:10]:
        linhas.append(f"  {d}")
    if len(r["diferencas"]) > 10:
        linhas.append(f"  ... mais {len(r['diferencas']) - 10}")
    return linhas


def comparar_gravada(base, resultado, g):
    """Compara uma partitura gravada com o MIDI do próprio `\\score` (as repetições valem uma vez,
    nos dois lados). Devolve `(linhas de resumo, bateu?, resumo)`: `bateu` é None se não deu para
    comparar; `resumo` é o dicionário de `comparar_partitura` (ou None)."""
    p = g.partitura.p
    midi = resultado.midi_de(g.partitura)
    nomes = [m.name for m in resultado.captura.midis]
    if midi is None or not midi.exists():
        return [f"{base} p{p}: sem MIDI; não comparado"], None, None
    if nomes.count(midi.name) > 1:
        return [f"{base} p{p}: MIDI '{midi.name}' repetido no log; não comparado"], None, None
    principais, apojaturas = notas_do_musicxml(g.arquivo)
    r = comparar_partitura(principais, apojaturas, notas_do_midi(midi))
    return formatar(base, p, r, g.partitura.so_midi), r["ok"], r


def comparar_resultado(base, resultado):
    """Compara todas as partituras gravadas.

    Devolve, na ordem de `resultado.gravadas`, dicionários com `linhas` (o resumo impresso),
    `ok` (bateu com o MIDI do próprio `\\score`; None se não deu para comparar), `resumo` (o de
    `comparar_partitura`) e `gemea` (True/False/None, abaixo).

    A partitura `so_midi` (a cópia só para o MIDI, quase sempre com `\\unfoldRepeats`) é
    comparada com as gravadas que vêm logo antes dela e têm as mesmas pautas, juntas (num dueto,
    o primo e o secondo), com as repetições desdobradas ou não, o que bater. Isso é só
    informação (`gemea`), e não entra em `ok`: o `\\score` só de MIDI pode ser outro arranjo
    (sem a anacruse, por exemplo, em `SchubertF-D899-2-Impromptu`) e nem por isso a conversão
    está errada.
    """
    saidas = []
    for g in resultado.gravadas:
        linhas, ok, r = comparar_gravada(base, resultado, g)
        saidas.append({"linhas": list(linhas), "ok": ok, "resumo": r, "gemea": None})
    por_gravada = {id(g): s for g, s in zip(resultado.gravadas, saidas)}
    partituras = resultado.partituras
    for i, so in enumerate(partituras):
        if not so.so_midi:
            continue
        irmas = []
        for outra in reversed(partituras[:i]):
            if outra.so_midi or len(outra.pautas) != len(so.pautas):
                break
            irmas.append(outra)
        gravadas = [g for g in resultado.gravadas if g.partitura in irmas]
        midi = resultado.midi_de(so)
        nomes = [m.name for m in resultado.captura.midis]
        if not gravadas or midi is None or not midi.exists() or nomes.count(midi.name) != 1:
            continue
        melhor = None
        for expandir in (True, False):
            principais, apojaturas = [], []
            for g in gravadas:
                pr, ap = notas_do_musicxml(g.arquivo, expandir=expandir)
                principais += pr
                apojaturas += ap
            r = comparar_partitura(principais, apojaturas, notas_do_midi(midi))
            if melhor is None or (r["ok"] and not melhor[1]["ok"]):
                melhor = (expandir, r)
            if r["ok"]:
                break
        expandir, r = melhor
        rotulo = f"{base} ({'desdobrada' if expandir else 'sem desdobrar'}; informativo)"
        ultima = max(gravadas, key=lambda g: resultado.partituras.index(g.partitura))
        por_gravada[id(ultima)]["linhas"] += formatar(rotulo, so.p, r, True)
        for g in gravadas:
            s = por_gravada[id(g)]
            s["gemea"] = r["ok"] if s["gemea"] is None else (s["gemea"] and r["ok"])
    return saidas
