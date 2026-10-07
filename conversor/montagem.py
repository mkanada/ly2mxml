"""Montagem do MusicXML a partir de uma `Partitura` (passos 08 e 09 em diante).

Uma parte de piano com uma `PartStaff` por pauta; as vozes do LilyPond viram `<voice>` dentro de
cada pauta. Tempo em `Fraction` na unidade semibreve; a conversão para `quarterLength` (× 4)
acontece só aqui, e nunca passa por `float`.
"""
import xml.etree.ElementTree as ET
from bisect import bisect_right
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path

from music21 import (bar, clef, duration, key, layout, metadata, meter, note, chord, pitch,
                     stream, tie)

QUATRO = Fraction(4)
ZERO = Fraction(0)

# Voz do MusicXML por pauta: 1 a 4 na primeira, 5 a 8 na segunda (convenção do MuseScore).
VOZES_POR_PAUTA = 4


@dataclass(slots=True)
class MedidaCompasso:
    """Um compasso do MusicXML: de `t0` a `t1`."""
    c: int
    t0: Fraction
    t1: Fraction
    tam: Fraction
    pos: Fraction         # posição no compasso no instante t0 (negativa na anacruse)
    medindo: bool
    numero: int = 0
    sufixo: str = ""
    implicito: bool = False

    @property
    def rotulo(self):
        return f"{self.numero}{self.sufixo}"


@dataclass(slots=True)
class Peca:
    """Um pedaço de acorde dentro de um compasso."""
    acorde: object
    ini: Fraction
    fim: Fraction
    primeiro: bool        # começa onde o acorde começa
    ultimo: bool          # termina onde o acorde termina


@dataclass
class Montagem:
    ps: object
    avisos: list = field(default_factory=list)
    implicitos: list = field(default_factory=list)   # rótulos dos compassos que não contam

    def avisar(self, texto):
        self.avisos.append(texto)


# ---------------------------------------------------------------------------
# Compassos
# ---------------------------------------------------------------------------

def _compassos(m: Montagem):
    """Os compassos do MusicXML, a partir das linhas `compasso`."""
    ps = m.ps
    brutos = []
    for c in sorted(ps.compassos, key=lambda x: x.t):
        if brutos and brutos[-1].t == c.t:
            brutos[-1] = c        # duas linhas no mesmo instante: vale a última
        else:
            brutos.append(c)
    brutos = [c for c in brutos if c.t < ps.fim]
    if not brutos:
        return []
    medidas = []
    for i, c in enumerate(brutos):
        t1 = brutos[i + 1].t if i + 1 < len(brutos) else ps.fim
        medidas.append(MedidaCompasso(c.c, c.t, t1, c.tam, c.pos, c.medindo))
    _numerar(medidas)
    m.implicitos = [md.rotulo for md in medidas if md.implicito]
    return medidas


def _numerar(medidas):
    """Número impresso: o `c` do LilyPond, com a anacruse inicial como 0."""
    for i, md in enumerate(medidas):
        md.numero = md.c
        if i == 0 and md.pos < 0 and len(medidas) > 1 and medidas[1].c == md.c:
            md.numero = md.c - 1
            md.implicito = True
        elif i > 0 and md.c == medidas[i - 1].c and md.numero == medidas[i - 1].numero:
            # O mesmo `c` duas vezes: o segundo é a continuação do primeiro e não conta.
            md.sufixo = "b" if not medidas[i - 1].sufixo else chr(ord(medidas[i - 1].sufixo) + 1)
            md.implicito = True


# ---------------------------------------------------------------------------
# Conversão de objetos
# ---------------------------------------------------------------------------

def _pitch(h):
    p = pitch.Pitch()
    p.step = "CDEFGAB"[h.nota]
    p.octave = h.oitava + 4
    if h.alt != 0:
        p.accidental = pitch.Accidental(float(h.alt * 2))
    assert p.midi == h.midi, f"altura inconsistente: {p} dá {p.midi}, o JSON diz {h.midi}"
    return p


def _clave(c):
    """Classe do music21 para (glifo, posição, transposição); None se fora da tabela."""
    glifo, posicao, transp = c.glifo, c.posicao, c.transp
    if glifo == "clefs.percussion":
        return clef.PercussionClef()
    tabela = {("clefs.G", -2): clef.TrebleClef, ("clefs.G", -4): clef.FrenchViolinClef,
              ("clefs.F", 2): clef.BassClef, ("clefs.F", 0): clef.FBaritoneClef,
              ("clefs.C", 0): clef.AltoClef, ("clefs.C", 2): clef.TenorClef,
              ("clefs.C", -2): clef.MezzoSopranoClef, ("clefs.C", -4): clef.SopranoClef}
    cls = tabela.get((glifo, posicao))
    if cls is None:
        return None
    obj = cls()
    if transp:
        obj.octaveChange = transp // 7
    return obj


SUSTENIDOS = [3, 0, 4, 1, 5, 2, 6]   # fá dó sol ré lá mi si
BEMOIS = [6, 2, 5, 1, 4, 0, 3]       # si mi lá ré sol dó fá


def _fifths(armadura):
    """Número de acidentes da armadura (positivo = sustenidos); None se não for tradicional."""
    alts = {}
    for a in armadura.alteracoes:
        if len(a) > 2:
            return None
        alts[a[0]] = a[1]
    if not alts:
        return 0
    if all(v == Fraction(1, 2) for v in alts.values()):
        n = len(alts)
        if set(alts) == set(SUSTENIDOS[:n]):
            return n
    if all(v == Fraction(-1, 2) for v in alts.values()):
        n = len(alts)
        if set(alts) == set(BEMOIS[:n]):
            return -n
    return None


def _fifths_mais_proximo(armadura):
    """Tradicional mais próxima: pelo número de acidentes, com o sinal da maioria."""
    sus = sum(1 for a in armadura.alteracoes if a[1] > 0)
    bem = sum(1 for a in armadura.alteracoes if a[1] < 0)
    return min(sus, 7) if sus >= bem else -min(bem, 7)


BARRAS = {"|.": "final", "||": "double", ".|": "heavy-light", "..": "light-light",
          "!": "dashed", ".|.": "heavy-heavy", ";": "dotted", "'": "short", "|": "regular"}


# ---------------------------------------------------------------------------
# Duração
# ---------------------------------------------------------------------------

def _duracoes(ql: Fraction):
    """Durações simples (não complexas) que somam `ql`, para cortar um valor irregular.

    Devolve uma lista de `Duration`; mais de uma significa nota ligada.
    """
    d = duration.Duration(ql)
    if d.type != "complex":
        return [d]
    return [duration.Duration(c.quarterLength) for c in d.components]


# ---------------------------------------------------------------------------
# Vozes do MusicXML
# ---------------------------------------------------------------------------

def _atribuir_vozes(m: Montagem, pautas, por_pauta):
    """Para cada pauta, `{voz do LilyPond: número da voz do MusicXML}`.

    Vozes que não se sobrepõem no tempo compartilham o mesmo número (o LilyPond cria muitas
    `\\new Voice` curtas). A que tem mais notas é a 1ª. Passando de 4 vozes simultâneas numa
    pauta, os números seguintes vão a partir de 9 e há um aviso.
    """
    resultado = {}
    extra = 9
    for i, pauta in enumerate(pautas):
        por_voz = {}
        for a in por_pauta[pauta]:
            if a.g == 0:
                por_voz.setdefault(a.voz, []).append(a)
        ordem = sorted(por_voz, key=lambda v: (-len(por_voz[v]), v))
        slots = []         # cada slot: lista de intervalos (ini, fim) ocupados
        mapa = {}
        for v in ordem:
            intervalos = sorted((a.t, a.fim) for a in por_voz[v])
            destino = None
            for s, ocupado in enumerate(slots):
                if not _sobrepoe(ocupado, intervalos):
                    destino = s
                    break
            if destino is None:
                slots.append([])
                destino = len(slots) - 1
            slots[destino] = sorted(slots[destino] + intervalos)
            mapa[v] = destino
        if len(slots) > VOZES_POR_PAUTA:
            m.avisar(f"mais de {VOZES_POR_PAUTA} vozes simultâneas na pauta {pauta}: "
                     f"{len(slots)} (as extras saem com número de voz alto)")
        numeros = {}
        for s in range(len(slots)):
            if s < VOZES_POR_PAUTA:
                numeros[s] = i * VOZES_POR_PAUTA + s + 1
            else:
                numeros[s] = extra
                extra += 1
        resultado[pauta] = {v: numeros[s] for v, s in mapa.items()}
    return resultado


def _sobrepoe(ocupado, novos):
    """Algum intervalo de `novos` invade um de `ocupado`? Os dois estão em ordem."""
    inicios = [o[0] for o in ocupado]
    for ini, fim in novos:
        k = bisect_right(inicios, ini)
        if k > 0 and ocupado[k - 1][1] > ini:
            return True
        if k < len(ocupado) and ocupado[k][0] < fim:
            return True
    return False


# ---------------------------------------------------------------------------
# Montagem
# ---------------------------------------------------------------------------

def montar(partitura, saida: Path) -> list[str]:
    """Grava `saida` e devolve os avisos."""
    m = Montagem(partitura, list(partitura.avisos))
    sc = _construir(m)
    saida = Path(saida)
    _gravar(m, sc, saida)
    return m.avisos


def _construir(m: Montagem):
    ps = m.ps
    medidas = _compassos(m)
    if not medidas:
        raise ValueError("partitura sem compassos")

    # Pautas: só as `Staff` que existem do começo ao fim; a ossia é descartada.
    ativas = []
    for n in sorted(ps.pautas):
        pauta = ps.pautas[n]
        if pauta.temporaria:
            m.avisar(f'pauta temporária "{pauta.id}" ignorada (ossia?)')
        elif pauta.contexto != "Staff":
            m.avisar(f"pauta {pauta.contexto} ignorada")
        else:
            ativas.append(n)
    if not ativas:
        raise ValueError("partitura sem pautas")

    por_pauta = {n: [] for n in ativas}
    perdidos = 0
    for voz in ps.vozes.values():
        for a in voz.acordes:
            if a.pauta in por_pauta:
                por_pauta[a.pauta].append(a)
            else:
                perdidos += 1
    if perdidos:
        m.avisar(f"{perdidos} acordes em pautas ignoradas descartados")

    numeros_voz = _atribuir_vozes(m, ativas, por_pauta)

    partes = {}
    for i, n in enumerate(ativas):
        partes[n] = (stream.PartStaff(id=f"P1-{i + 1}") if len(ativas) > 1
                     else stream.Part(id="P1"))
    inicios = [md.t0 for md in medidas]

    def compasso_de(t):
        return medidas[max(0, bisect_right(inicios, t) - 1)]

    for i, n in enumerate(ativas):
        _montar_pauta(m, ps, partes[n], n, i * VOZES_POR_PAUTA + 1, por_pauta[n], numeros_voz[n],
                      medidas, compasso_de)

    sc = stream.Score()
    sc.metadata = metadata.Metadata()
    for n in ativas:
        sc.insert(0, partes[n])
    if len(ativas) > 1:
        sc.insert(0, layout.StaffGroup([partes[n] for n in ativas], symbol="brace"))
    partes[ativas[0]].partName = "Piano"
    return sc


def _montar_pauta(m, ps, parte, n_pauta, base_voz, acordes, numeros, medidas, compasso_de):
    por_medida = [stream.Measure(number=md.numero) for md in medidas]
    for md, obj in zip(medidas, por_medida):
        if md.sufixo:
            obj.numberSuffix = md.sufixo

    # Atributos: claves, armaduras e fórmulas.
    for c in ps.claves.get(n_pauta, []):
        obj = _clave(c)
        if obj is None:
            m.avisar(f"clave {c.glifo} posição {c.posicao} fora da tabela: usada a de sol")
            obj = clef.TrebleClef()
        md = compasso_de(c.t)
        _inserir_atributo(m, por_medida, medidas, md, c.t, obj, "clave")
    for a in ps.armaduras.get(n_pauta, []):
        n = _fifths(a)
        if n is None:
            n = _fifths_mais_proximo(a)
            m.avisar(f"armadura não tradicional na pauta {n_pauta}: usada a de {n} acidentes")
        md = compasso_de(a.t)
        _inserir_atributo(m, por_medida, medidas, md, a.t, key.KeySignature(n), "armadura")
    for f in ps.formulas:
        md = compasso_de(f.t)
        _inserir_atributo(m, por_medida, medidas, md, f.t,
                          meter.TimeSignature(f"{f.num}/{f.den}"), "fórmula")

    # Barras: no compasso que termina no instante da linha.
    for b in ps.barras:
        estilo = BARRAS.get(b.glifo)
        if estilo is None:
            continue
        for md, obj in zip(medidas, por_medida):
            if md.t1 == b.t:
                obj.rightBarline = bar.Barline(estilo)

    # Notas e pausas, por voz e por compasso.
    for k, (md, obj) in enumerate(zip(medidas, por_medida)):
        vozes = {}
        for a in acordes:
            if a.g != 0:
                continue
            if a.t < md.t1 and a.fim > md.t0:
                pedaco = Peca(a, max(a.t, md.t0), min(a.fim, md.t1),
                              a.t >= md.t0, a.fim <= md.t1)
                vozes.setdefault(numeros[a.voz], []).append(pedaco)
        for numero_voz in sorted(vozes):
            v = stream.Voice(id=numero_voz)
            _preencher_voz(m, v, md, sorted(vozes[numero_voz], key=lambda p: p.ini))
            obj.insert(0, v)
        if not vozes:
            v = stream.Voice(id=base_voz)
            _preencher_voz(m, v, md, [])
            obj.insert(0, v)
        parte.insert(md.t0 * QUATRO, obj)


def _inserir_atributo(m, por_medida, medidas, md, t, obj, nome):
    i = medidas.index(md)
    offset = (t - md.t0) * QUATRO
    if offset != 0 and not isinstance(obj, clef.Clef):
        # Fórmula e armadura no meio do compasso: vale a partir do próximo.
        m.avisar(f"{nome} no meio do compasso {md.rotulo}: movida para o compasso seguinte")
        if i + 1 < len(medidas):
            i += 1
            offset = 0
    por_medida[i].insert(offset, obj)


def _preencher_voz(m, voz, md, pedacos):
    """Notas e pausas de uma voz num compasso, com pausas escondidas nos buracos."""
    cursor = md.t0
    for p in pedacos:
        if p.ini < cursor:
            m.avisar(f"notas sobrepostas na mesma voz no compasso {md.rotulo} (t={p.ini}): "
                     f"descartada")
            continue
        if p.ini > cursor:
            _inserir_pausa_escondida(voz, md, cursor, p.ini)
        _inserir_peca(m, voz, md, p)
        cursor = p.fim
    if cursor < md.t1 and pedacos:
        _inserir_pausa_escondida(voz, md, cursor, md.t1)
    elif not pedacos:
        r = note.Rest()
        r.duration = duration.Duration(md.tam * QUATRO)
        r.fullMeasure = True
        r.style.hideObjectOnPrint = True
        voz.insert(0, r)


def _inserir_pausa_escondida(voz, md, ini, fim):
    off = (ini - md.t0) * QUATRO
    for d in _duracoes((fim - ini) * QUATRO):
        r = note.Rest()
        r.duration = d
        r.style.hideObjectOnPrint = True
        voz.insert(off, r)
        off += d.quarterLength


def _inserir_peca(m, voz, md, p):
    a = p.acorde
    off = (p.ini - md.t0) * QUATRO
    ql = (p.fim - p.ini) * QUATRO
    if not a.alturas:
        # Pausa (ou pausa de compasso, um pedaço por compasso).
        for d in _duracoes(ql):
            r = note.Rest()
            r.duration = d
            if a.compasso_inteiro:
                r.fullMeasure = True
            voz.insert(off, r)
            off += d.quarterLength
        return
    durs = _duracoes(ql)
    for j, d in enumerate(durs):
        tem_anterior = (not p.primeiro) or j > 0
        tem_proximo = (not p.ultimo) or j < len(durs) - 1
        objs = []
        for h, lig, chega in zip(a.alturas, a.lig, a.lig_chega):
            n = note.Note()
            n.pitch = _pitch(h)
            ant = tem_anterior or (p.primeiro and j == 0 and chega)
            prox = tem_proximo or (p.ultimo and j == len(durs) - 1 and lig)
            if ant and prox:
                n.tie = tie.Tie("continue")
            elif prox:
                n.tie = tie.Tie("start")
            elif ant:
                n.tie = tie.Tie("stop")
            objs.append(n)
        if len(objs) == 1:
            elem = objs[0]
        else:
            elem = chord.Chord(objs)
        elem.duration = d
        voz.insert(off, elem)
        off += d.quarterLength


# ---------------------------------------------------------------------------
# Gravação
# ---------------------------------------------------------------------------

def _gravar(m, sc, saida: Path):
    for parte in sc.parts:
        for md in parte.getElementsByClass(stream.Measure):
            try:
                md.makeBeams(inPlace=True, setStemDirections=False)
            except Exception as erro:       # compasso estourado ou fórmula ausente
                m.avisar(f"feixes não calculados no compasso {md.number}: "
                         f"{type(erro).__name__}: {erro}")
        parte.makeAccidentals(inPlace=True)
    sc.write("musicxml", fp=str(saida), makeNotation=False)
    _pos_processar(m, saida)


CABECALHO_XML = (
    '<?xml version="1.0" encoding="utf-8"?>\n'
    '<!DOCTYPE score-partwise  PUBLIC "-//Recordare//DTD MusicXML 4.0 Partwise//EN" '
    '"http://www.musicxml.org/dtds/partwise.dtd">\n')


def _pos_processar(m, saida: Path):
    """Saída reprodutível (ids fixos, sem data nem título genérico) e `<key>` numerado."""
    raiz = ET.fromstring(saida.read_text(encoding="utf-8"))
    ident = raiz.find("identification")
    if ident is not None:
        for creator in ident.findall("creator"):
            if creator.text == "Music21":
                ident.remove(creator)
        encoding = ident.find("encoding")
        if encoding is not None:
            for data in encoding.findall("encoding-date"):
                encoding.remove(data)
    for titulo in raiz.findall("movement-title"):
        raiz.remove(titulo)
    ids = {}
    for n, sp in enumerate(raiz.iter("score-part"), 1):
        ids[sp.get("id")] = f"P{n}"
        sp.set("id", f"P{n}")
    for parte in raiz.findall("part"):
        parte.set("id", ids.get(parte.get("id"), parte.get("id")))
        for compasso in parte.findall("measure"):
            if compasso.get("number") in m.implicitos:
                compasso.set("implicit", "yes")
            _numerar_armaduras(compasso)
    ET.indent(raiz, space="  ")
    saida.write_text(CABECALHO_XML + ET.tostring(raiz, encoding="unicode") + "\n",
                     encoding="utf-8")


def _numerar_armaduras(compasso):
    """Dá `number` à armadura (`<key>`) que o music21 deixa sem, pela pauta da nota seguinte.

    Sem o número, a armadura valeria para todas as pautas da parte.
    """
    filhos = list(compasso)
    for i, el in enumerate(filhos):
        if el.tag != "attributes":
            continue
        chaves = [k for k in el.findall("key") if k.get("number") is None]
        if not chaves or el.find("divisions") is not None:
            continue          # as iniciais o music21 já numera quando as pautas diferem
        staff = None
        for seguinte in filhos[i + 1:]:
            if seguinte.tag == "note":
                staff = seguinte.findtext("staff")
                break
        if staff is None:
            for anterior in reversed(filhos[:i]):
                if anterior.tag == "note":
                    staff = anterior.findtext("staff")
                    break
        if staff is not None:
            for k in chaves:
                k.set("number", staff)
