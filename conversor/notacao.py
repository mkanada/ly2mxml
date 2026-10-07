"""Notação que não muda as notas tocadas (passo 18): articulações, ornamentos, dinâmica,
ligaduras de expressão, pedal, andamento, `\\ottava`, dedilhado, textos e metadados.

Chamado por `montagem._montar_pauta` depois que as notas de uma pauta estão nos compassos. As
notas criadas ficam em `Montagem.refs`: `id(acorde)` → lista de `(elemento, compasso, offset)`,
um por pedaço do acorde (um acorde que atravessa a barra tem mais de um).
"""
from fractions import Fraction

from music21 import (articulations, duration, dynamics, expressions, metadata, spanner, tempo)

QUATRO = Fraction(4)

# Articulações do LilyPond (`articulation-type`) → classes do music21.
ARTICULACOES = {
    "staccato": articulations.Staccato,
    "staccatissimo": articulations.Staccatissimo,
    "accent": articulations.Accent,
    "tenuto": articulations.Tenuto,
    "marcato": articulations.StrongAccent,
    "stopped": articulations.Stopped,
    "snappizzicato": articulations.SnapPizzicato,
    "upbow": articulations.UpBow,
    "downbow": articulations.DownBow,
    "open": articulations.OpenString,
}
# Ornamentos: vão em `expressions` da nota.
ORNAMENTOS = {
    "fermata": expressions.Fermata,
    "trill": expressions.Trill,
    "mordent": expressions.Mordent,
    "prall": expressions.InvertedMordent,
    "upprall": expressions.InvertedMordent,
    "downprall": expressions.InvertedMordent,
    "prallup": expressions.InvertedMordent,
    "pralldown": expressions.InvertedMordent,
    "lineprall": expressions.InvertedMordent,
    "prallprall": expressions.InvertedMordent,
    "upmordent": expressions.Mordent,
    "downmordent": expressions.Mordent,
    "prallmordent": expressions.Mordent,
    "turn": expressions.Turn,
    "reverseturn": expressions.InvertedTurn,
    "arpeggio": expressions.ArpeggioMark,
}
# `\portato` é um tenuto com staccato.
COMPOSTAS = {"portato": (articulations.Tenuto, articulations.Staccato)}

DINAMICAS = {"pppppp", "ppppp", "pppp", "ppp", "pp", "p", "mp", "mf", "f", "ff", "fff", "ffff",
             "fffff", "ffffff", "fp", "sf", "sfp", "sfpp", "sfz", "sffz", "rfz", "rf", "fz", "sp",
             "spp", "pf", "n"}

OTTAVAS = {1: "8va", -1: "8vb", 2: "15ma", -2: "15mb"}


def aplicar(m, ps, parte, n_pauta, acordes, obj_de, medidas, compasso_de, primeira):
    """Aplica a notação desta pauta. `obj_de`: `id(compasso)` → `Measure` desta pauta."""
    por_voz = {}
    for a in acordes:
        if a.alturas:
            por_voz.setdefault(a.voz, []).append(a)
    for lista in por_voz.values():
        lista.sort(key=lambda a: (a.t, a.g))

    _decoracoes(m, acordes, obj_de)
    _dinamicas(m, ps, parte, n_pauta, por_voz, obj_de, medidas, compasso_de)
    _hairpins(m, ps, parte, n_pauta, por_voz)
    _expressoes(m, ps, parte, n_pauta, por_voz)
    _pedais(m, ps, parte, n_pauta, por_voz)
    _ottavas(m, ps, parte, n_pauta, acordes)
    if primeira:
        _andamentos(m, ps, obj_de, medidas, compasso_de)


# ---------------------------------------------------------------------------
# Em cada acorde: articulações, ornamentos, dedilhado e textos
# ---------------------------------------------------------------------------

def _decoracoes(m, acordes, obj_de):
    for a in acordes:
        if not (a.art or a.dedo or a.textos):
            continue
        refs = m.refs.get(id(a))
        if not refs:
            continue
        elem, md, off = refs[0]
        for nome in a.art:
            if nome in ARTICULACOES:
                elem.articulations.append(ARTICULACOES[nome]())
            elif nome in COMPOSTAS:
                for cls in COMPOSTAS[nome]:
                    elem.articulations.append(cls())
            elif nome in ORNAMENTOS:
                orn = ORNAMENTOS[nome]()
                if nome == "fermata":
                    orn.type = "upright"       # o padrão do music21 é a fermata de ponta-cabeça
                elem.expressions.append(orn)
            else:
                m.avisar_uma_vez(f"articulação {nome} ignorada")
        if a.dedo is not None:
            elem.articulations.append(articulations.Fingering(a.dedo))
        for texto in a.textos:
            obj_de[id(md)].insert(off, expressions.TextExpression(texto))


# ---------------------------------------------------------------------------
# Marcas com início e fim
# ---------------------------------------------------------------------------

def _acorde_em(por_voz, voz, t, g):
    """O acorde de notas da voz em `(t, g)` ou, na falta, o primeiro depois."""
    return next((a for a in por_voz.get(voz, []) if (a.t, a.g) >= (t, g)), None)


def _marcas(ps, n_pauta, tipos):
    return [x for x in ps.marcas if x.tipo in tipos and x.pauta == n_pauta]


def _dinamicas(m, ps, parte, n_pauta, por_voz, obj_de, medidas, compasso_de):
    for x in _marcas(ps, n_pauta, {"dinamica"}):
        texto = x.dados["texto"]
        if texto not in DINAMICAS:
            m.avisar_uma_vez(f"dinâmica {texto} ignorada")
            continue
        a = _acorde_em(por_voz, x.voz, x.t, x.g)
        refs = m.refs.get(id(a)) if a is not None and a.t == x.t else None
        if refs:
            _, md, off = refs[0]
        else:
            md = compasso_de(x.t)
            off = (x.t - md.t0) * QUATRO
        obj_de[id(md)].insert(off, dynamics.Dynamic(texto))


def _pares(marcas, chave=lambda x: x.voz):
    """Emparelha início e fim, por chave (a voz, em geral), na ordem do tempo."""
    abertas, pares = {}, []
    for x in sorted(marcas, key=lambda x: (x.t, x.g)):
        k = chave(x)
        if x.dados["dir"] == "inicio":
            abertas.setdefault(k, []).append(x)
        elif abertas.get(k):
            pares.append((abertas[k].pop(), x))
    return pares


def _hairpins(m, ps, parte, n_pauta, por_voz):
    for ini, fim in _pares(_marcas(ps, n_pauta, {"hairpin"})):
        a, b = _acorde_em(por_voz, ini.voz, ini.t, ini.g), _acorde_em(por_voz, fim.voz, fim.t, fim.g)
        if a is None or b is None or a is b or not m.refs.get(id(a)) or not m.refs.get(id(b)):
            continue
        cls = dynamics.Crescendo if ini.dados["forma"] == "cresc" else dynamics.Diminuendo
        parte.insert(0, cls(m.refs[id(a)][0][0], m.refs[id(b)][0][0]))


def _expressoes(m, ps, parte, n_pauta, por_voz):
    """Ligaduras de expressão (`(` `)`) e de frase (`\\(` `\\)`): ambas viram `Slur`."""
    marcas = _marcas(ps, n_pauta, {"expressao"})
    for nome in ("slur", "frase"):
        for ini, fim in _pares([x for x in marcas if x.dados["nome"] == nome]):
            a, b = (_acorde_em(por_voz, ini.voz, ini.t, ini.g),
                    _acorde_em(por_voz, fim.voz, fim.t, fim.g))
            if a is None or b is None or not m.refs.get(id(a)) or not m.refs.get(id(b)):
                continue
            ini_elem, fim_elem = m.refs[id(a)][0][0], m.refs[id(b)][-1][0]
            if ini_elem is fim_elem:
                continue
            parte.insert(0, spanner.Slur(ini_elem, fim_elem))


def _pedais(m, ps, parte, n_pauta, por_voz):
    tipos = {"sustain": "sustain", "sostenuto": "sostenuto", "unacorda": "una-corda"}
    marcas = _marcas(ps, n_pauta, {"pedal"})
    for nome, tipo in tipos.items():
        for ini, fim in _pares([x for x in marcas if x.dados["nome"] == nome]):
            a = _acorde_em(por_voz, ini.voz, ini.t, ini.g)
            b = _acorde_em(por_voz, fim.voz, fim.t, fim.g)
            if a is None or b is None or not m.refs.get(id(a)) or not m.refs.get(id(b)):
                continue
            ini_elem, fim_elem = m.refs[id(a)][0][0], m.refs[id(b)][0][0]
            if ini_elem is fim_elem:
                continue
            marca = expressions.PedalMark(ini_elem, fim_elem)
            marca.pedalType = expressions.PedalType.Sustain if tipo == "sustain" else (
                expressions.PedalType.Sostenuto if tipo == "sostenuto"
                else expressions.PedalType.SoftPedal)
            marca.pedalForm = expressions.PedalForm.Line
            parte.insert(0, marca)


def _ottavas(m, ps, parte, n_pauta, acordes):
    eventos = sorted(ps.ottavas.get(n_pauta, []))
    for i, (t, n) in enumerate(eventos):
        if n == 0:
            continue
        fim = eventos[i + 1][0] if i + 1 < len(eventos) else ps.fim
        tipo = OTTAVAS.get(n)
        if tipo is None:
            m.avisar_uma_vez(f"\\ottava #{n} fora da tabela: ignorada")
            continue
        notas = [a for a in acordes if a.alturas and a.g == 0 and t <= a.t < fim]
        notas = [r for a in notas for r in m.refs.get(id(a), [])]
        if len(notas) < 2:
            continue
        parte.insert(0, spanner.Ottava(notas[0][0], notas[-1][0], type=tipo, transposing=False))


# ---------------------------------------------------------------------------
# Andamento e metadados
# ---------------------------------------------------------------------------

def _andamentos(m, ps, obj_de, medidas, compasso_de):
    for x in ps.andamentos:
        md = compasso_de(x["t"])
        off = (x["t"] - md.t0) * QUATRO
        bpm, unidade = x["bpm"], x["unidade"]
        texto = x["texto"] or None
        if isinstance(bpm, list):
            bpm = bpm[0]
        if bpm is None or bpm == "null":
            marca = tempo.TempoText(texto) if texto else None
        else:
            referente = None
            if unidade is not None:
                from .montagem import TIPOS
                tipo = TIPOS.get(unidade["fig"])
                if tipo:
                    referente = duration.Duration(type=tipo, dots=unidade["pontos"])
            marca = tempo.MetronomeMark(text=texto, number=bpm, referent=referente)
        if marca is not None:
            obj_de[id(md)].insert(off, marca)


def preencher_metadados(ps, md: metadata.Metadata):
    """Título, compositor e afins a partir do `\\header` (com os campos do Mutopia como
    reserva). A licença do Mutopia vai em `copyright`: o acervo pede atribuição."""
    campos = ps.metadados
    if not campos:
        return

    def primeiro(*nomes):
        return next((campos[n] for n in nomes if campos.get(n)), None)

    titulo = primeiro("title", "mutopiatitle")
    if titulo:
        md.title = titulo
    compositor = primeiro("composer", "mutopiacomposer")
    if compositor:
        md.composer = compositor
    opus = primeiro("opus", "mutopiaopus")
    if opus:
        md.addCustom("opus", opus)
    peca = primeiro("piece", "subtitle")
    if peca:
        md.movementName = peca
    direitos = primeiro("copyright", "license", "mutopialicense")
    if direitos:
        md.copyright = direitos
