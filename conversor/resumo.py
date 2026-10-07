"""Resumo estatístico de um MusicXML (passo 16): contagens e um hash do conteúdo musical."""
import hashlib
import xml.etree.ElementTree as ET


def resumir(caminho) -> dict:
    """Contagens do MusicXML e o hash (sha1, 10 primeiros) de altura, duração, voz, pauta e
    ligadura de cada nota, na ordem. As contagens são da primeira parte, que é onde a montagem
    põe todas as pautas."""
    raiz = ET.parse(str(caminho)).getroot()
    r = dict(compassos=0, pautas=1, vozes=0, notas=0, pausas=0, acordes=0, ligaduras=0,
             quialteras=0, apojaturas=0, repeticoes=0, casas=0, dinamicas=0, hairpins=0,
             ligaduras_expr=0, articulacoes=0, pedais=0, andamentos=0)
    formulas, armaduras = [], []
    vozes = set()
    h = hashlib.sha1()
    parte = raiz.find("part")
    if parte is None:
        return {**r, "formula": "", "armadura": "", "hash": ""}
    for compasso in parte.findall("measure"):
        r["compassos"] += 1
        filhos = list(compasso)
        for i, el in enumerate(filhos):
            if el.tag == "attributes":
                if el.findtext("staves"):
                    r["pautas"] = int(el.findtext("staves"))
                for t in el.findall("time"):
                    f = f"{t.findtext('beats')}/{t.findtext('beat-type')}"
                    if not formulas or formulas[-1] != f:
                        formulas.append(f)
                for k in el.findall("key"):
                    f = k.findtext("fifths")
                    if f is not None and (not armaduras or armaduras[-1] != f):
                        armaduras.append(f)
            elif el.tag == "direction":
                r["dinamicas"] += len(el.findall("direction-type/dynamics"))
                r["hairpins"] += sum(1 for w in el.findall("direction-type/wedge")
                                     if w.get("type") in ("crescendo", "diminuendo"))
                r["pedais"] += sum(1 for w in el.findall("direction-type/pedal")
                                   if w.get("type") == "start")
                r["andamentos"] += len(el.findall("direction-type/metronome"))
            elif el.tag == "barline":
                for rep in el.findall("repeat"):
                    r["repeticoes"] += 1
                for end in el.findall("ending"):
                    if end.get("type") == "start":
                        r["casas"] += 1
            elif el.tag == "note":
                proximo = filhos[i + 1] if i + 1 < len(filhos) else None
                if proximo is not None and proximo.tag == "note" \
                        and proximo.find("chord") is not None and el.find("chord") is None:
                    r["acordes"] += 1
                voz, pauta = el.findtext("voice", "1"), el.findtext("staff", "1")
                tipo = "r" if el.find("rest") is not None else (
                    f"{el.findtext('pitch/step')}{el.findtext('pitch/alter', '0')}"
                    f"{el.findtext('pitch/octave')}")
                ligas = ",".join(sorted(t.get("type") for t in el.findall("tie")))
                graca = "g" if el.find("grace") is not None else ""
                h.update(f"{tipo}|{el.findtext('duration', '0')}|{voz}|{pauta}|{ligas}|{graca}"
                         f"|{'c' if el.find('chord') is not None else ''};".encode())
                if el.find("rest") is not None:
                    if el.get("print-object") != "no":
                        r["pausas"] += 1
                else:
                    r["notas"] += 1
                    vozes.add((pauta, voz))
                    for t in el.findall("tie"):
                        if t.get("type") == "start":
                            r["ligaduras"] += 1
                    if el.find("grace") is not None:
                        r["apojaturas"] += 1
                    for t in el.findall("notations/tuplet"):
                        if t.get("type") == "start":
                            r["quialteras"] += 1
                for sl in el.findall("notations/slur"):
                    if sl.get("type") == "start":
                        r["ligaduras_expr"] += 1
                r["articulacoes"] += sum(len(x) for x in el.findall("notations/articulations"))
                r["articulacoes"] += sum(len(x) for x in el.findall("notations/ornaments"))
                r["articulacoes"] += len(el.findall("notations/fermata"))
                r["articulacoes"] += len(el.findall("notations/arpeggiate"))
    r["vozes"] = len(vozes)
    return {**r, "formula": " ".join(formulas), "armadura": " ".join(armaduras),
            "hash": h.hexdigest()[:10]}
