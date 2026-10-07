"""Montagem do MusicXML a partir de uma `Partitura` (passos 08 e 09 em diante).

Uma parte de piano com uma `PartStaff` por pauta; as vozes do LilyPond viram `<voice>` dentro de
cada pauta. Tempo em `Fraction` na unidade semibreve; a conversão para `quarterLength` (× 4)
acontece só aqui, e nunca passa por `float`.
"""
import re
import xml.etree.ElementTree as ET
from bisect import bisect_right
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path

from music21 import (bar, clef, duration, key, layout, metadata, meter, note, chord, pitch,
                     spanner, stream, tie)

from . import notacao
from .eventos import Figura

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
    anacruse: bool = False    # compasso de anacruse (o seguinte é o compasso cheio)

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
    primeira_pauta: int = 0
    refs: dict = field(default_factory=dict)         # id(acorde) -> [(elemento, compasso, offset)]
    _avisados: set = field(default_factory=set)

    def avisar(self, texto):
        self.avisos.append(texto)

    def avisar_uma_vez(self, texto):
        if texto not in self._avisados:
            self._avisados.add(texto)
            self.avisos.append(texto)


# ---------------------------------------------------------------------------
# Compassos
# ---------------------------------------------------------------------------

def _compassos(m: Montagem):
    """Os compassos do MusicXML, a partir das linhas `compasso` (e das `barra` na cadenza)."""
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

    # Compasso partido: (1) na cadenza (e em compasso longo) o LilyPond não abre compasso na
    # `\\bar`; o trecho depois da barra vira outro compasso, com o mesmo número. (2) Uma
    # repetição ou uma casa que começa ou termina no meio do compasso (`5.Inquietude`): o
    # MusicXML só tem repetição na barra, então o compasso é partido ali.
    barras = sorted({b.t for b in ps.barras if b.glifo not in ("", "|:", ":|:")})
    cortes_rep = set()
    for r in ps.repeticoes:
        if r.tipo in ("rep-inicio", "rep-fim", "volta") or (
                r.tipo == "repeticao" and any(c[0] in ("start-repeat", "end-repeat", "volta")
                                              for c in r.dados["cmds"])):
            cortes_rep.add(r.t)
    divididas = []
    for md in medidas:
        real = md.t1 - md.t0
        cortes = {t for t in cortes_rep if md.t0 < t < md.t1}
        if real > md.tam:
            cortes |= {t for t in barras if md.t0 < t < md.t1}
        if cortes:
            inicio = md.t0
            for corte in sorted(cortes) + [md.t1]:
                divididas.append(MedidaCompasso(
                    md.c, inicio, corte, md.tam, md.pos if inicio == md.t0 else ZERO,
                    md.medindo if inicio == md.t0 else True))
                inicio = corte
        else:
            divididas.append(md)
    medidas = divididas
    for md in medidas:
        real = md.t1 - md.t0
        if not md.medindo:
            m.avisar(f"cadenza no compasso {md.c} ({real * 4} semínimas)")
        elif real > md.tam:
            m.avisar(f"compasso {md.c} mais longo que a fórmula ({real * 4} semínimas)")
    _numerar(medidas)
    m.implicitos = [md.rotulo for md in medidas if md.implicito]
    return medidas


def _numerar(medidas):
    """Número impresso: o `c` do LilyPond, com a anacruse inicial como 0.

    Dois compassos seguidos com o mesmo `c` são um compasso partido (anacruse no meio, compasso
    cortado antes de uma repetição, cadenza): o que não é o compasso "de verdade" é implícito e
    leva sufixo para o número continuar único.
    """
    for i, md in enumerate(medidas):
        md.numero = md.c
        seguinte_igual = i + 1 < len(medidas) and medidas[i + 1].c == md.c
        if seguinte_igual and md.pos < 0:
            # Anacruse: o compasso seguinte é o compasso cheio. A do começo da peça é o 0.
            md.numero = md.c - 1
            md.implicito = md.anacruse = True
            if i > 0:
                md.sufixo = "b"
        elif i > 0 and md.c == medidas[i - 1].c and not medidas[i - 1].anacruse:
            # Continuação de um compasso partido: "12b", "12c"...
            anterior = medidas[i - 1]
            md.sufixo = chr(ord(anterior.sufixo or "a") + 1)
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

def _camadas(acordes):
    """`{id(acorde): camada}`: uma voz do LilyPond pode ter acordes sobrepostos (notas de
    durações diferentes tocadas ao mesmo tempo na mesma `Voice`). Cada camada é uma voz do
    MusicXML à parte."""
    camadas = {}
    fins = {}                 # voz -> fim do último acorde de cada camada
    for a in sorted((x for x in acordes if x.g == 0), key=lambda x: (x.t, x.fim)):
        lista = fins.setdefault(a.voz, [])
        for k, fim in enumerate(lista):
            if fim <= a.t:
                lista[k] = a.fim
                camadas[id(a)] = k
                break
        else:
            lista.append(a.fim)
            camadas[id(a)] = len(lista) - 1
    return camadas


def _atribuir_vozes(m: Montagem, pautas, por_pauta, camadas):
    """Para cada pauta, `{(voz do LilyPond, camada): número da voz do MusicXML}`.

    Vozes que não se sobrepõem no tempo compartilham o mesmo número (o LilyPond cria muitas
    `\\new Voice` curtas). A que tem mais notas é a 1ª. Passando de 4 vozes simultâneas numa
    pauta, os números seguintes vão a partir de 9 e há um aviso. Apojaturas não ocupam tempo e
    não entram na conta: a voz que só tem apojaturas na pauta cai no número da 1ª.
    """
    resultado = {}
    extra = 9
    for i, pauta in enumerate(pautas):
        por_voz = {}
        so_gracas = set()
        for a in por_pauta[pauta]:
            if a.g == 0:
                por_voz.setdefault((a.voz, camadas[id(a)]), []).append(a)
        for a in por_pauta[pauta]:
            if a.g != 0 and (a.voz, 0) not in por_voz:
                so_gracas.add((a.voz, 0))
        ordem = sorted(por_voz, key=lambda v: (-len(por_voz[v]), v))
        slots = []         # cada slot: intervalos disjuntos (união) ocupados
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
            slots[destino] = _unir(slots[destino] + intervalos)
            mapa[v] = destino
        for v in so_gracas:
            mapa[v] = 0
        if len(slots) > VOZES_POR_PAUTA:
            m.avisar(f"mais de {VOZES_POR_PAUTA} vozes simultâneas na pauta {pauta}: "
                     f"{len(slots)} (as extras saem com número de voz alto)")
        numeros = {}
        for s in range(max(len(slots), 1)):
            if s < VOZES_POR_PAUTA:
                numeros[s] = i * VOZES_POR_PAUTA + s + 1
            else:
                numeros[s] = extra
                extra += 1
        resultado[pauta] = {v: numeros[s] for v, s in mapa.items()}
    return resultado


def _unir(intervalos):
    """União de intervalos (início, fim): lista ordenada de intervalos disjuntos."""
    uniao = []
    for ini, fim in sorted(intervalos):
        if uniao and ini <= uniao[-1][1]:
            uniao[-1] = (uniao[-1][0], max(uniao[-1][1], fim))
        else:
            uniao.append((ini, fim))
    return uniao


def _sobrepoe(ocupado, novos):
    """Algum intervalo de `novos` invade a união `ocupado`? Encostar não é invadir."""
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

    camadas = _camadas([a for lista in por_pauta.values() for a in lista])
    m.primeira_pauta = ativas[0]
    numeros_voz = _atribuir_vozes(m, ativas, por_pauta, camadas)

    partes = {}
    for i, n in enumerate(ativas):
        partes[n] = (stream.PartStaff(id=f"P1-{i + 1}") if len(ativas) > 1
                     else stream.Part(id="P1"))
    inicios = [md.t0 for md in medidas]

    def compasso_de(t):
        return medidas[max(0, bisect_right(inicios, t) - 1)]

    for i, n in enumerate(ativas):
        _montar_pauta(m, ps, partes[n], n, i * VOZES_POR_PAUTA + 1, por_pauta[n], numeros_voz[n],
                      camadas, medidas, compasso_de)

    sc = stream.Score()
    sc.metadata = metadata.Metadata()
    notacao.preencher_metadados(ps, sc.metadata)
    for n in ativas:
        sc.insert(0, partes[n])
    if len(ativas) > 1:
        sc.insert(0, layout.StaffGroup([partes[n] for n in ativas], symbol="brace"))
    partes[ativas[0]].partName = "Piano"
    return sc


def _montar_pauta(m, ps, parte, n_pauta, base_voz, acordes, numeros, camadas, medidas,
                  compasso_de):
    por_medida = [stream.Measure(number=md.numero) for md in medidas]
    for md, obj in zip(medidas, por_medida):
        if md.sufixo:
            obj.numberSuffix = md.sufixo

    # Atributos: claves, armaduras e fórmulas.
    # Duas claves (ou armaduras) no mesmo instante: vale a última. Uma peça que começa por
    # apojatura recebe a clave padrão em g < 0, antes da `\\clef bass` do próprio instante.
    for c in _ultimas_por_instante(ps.claves.get(n_pauta, [])):
        obj = _clave(c)
        if obj is None:
            m.avisar(f"clave {c.glifo} posição {c.posicao} fora da tabela: usada a de sol")
            obj = clef.TrebleClef()
        md = compasso_de(c.t)
        _inserir_atributo(m, por_medida, medidas, md, c.t, obj, "clave")
    for a in _ultimas_por_instante(ps.armaduras.get(n_pauta, [])):
        n = _fifths(a)
        if n is None:
            n = _fifths_mais_proximo(a)
            m.avisar(f"armadura não tradicional na pauta {n_pauta}: usada a de {n} acidentes")
        md = compasso_de(a.t)
        _inserir_atributo(m, por_medida, medidas, md, a.t, key.KeySignature(n), "armadura")
    for f in ps.formulas:
        md = compasso_de(f.t)
        ts = meter.TimeSignature(f"{f.num}/{f.den}")
        # O LilyPond desenha C e ₵ por padrão (estilo `C`); `\numericTimeSignature` desliga.
        estilo = _estilo_da_formula(ps, n_pauta, f.t)
        if estilo == "C" and (f.num, f.den) == (4, 4):
            ts.symbol = "common"
        elif estilo == "C" and (f.num, f.den) == (2, 2):
            ts.symbol = "cut"
        _inserir_atributo(m, por_medida, medidas, md, f.t, ts, "fórmula")

    # Barras: no compasso que termina no instante da linha.
    for b in ps.barras:
        estilo = BARRAS.get(b.glifo)
        if estilo is None:
            continue
        for md, obj in zip(medidas, por_medida):
            if md.t1 == b.t:
                obj.rightBarline = bar.Barline(estilo)

    _repeticoes(m, ps, parte, por_medida, medidas, compasso_de)

    # Apojaturas: o instante e o compasso onde cada uma entra.
    gracas = _posicionar_gracas(m, ps, acordes, medidas, compasso_de)
    qi = _intervalos_quialtera(ps)

    # Notas e pausas, por voz e por compasso.
    for k, (md, obj) in enumerate(zip(medidas, por_medida)):
        vozes = {}
        for a in acordes:
            if a.g != 0:
                continue
            if a.t < md.t1 and a.fim > md.t0:
                pedaco = Peca(a, max(a.t, md.t0), min(a.fim, md.t1),
                              a.t >= md.t0, a.fim <= md.t1)
                vozes.setdefault(numeros[(a.voz, camadas[id(a)])], []).append(pedaco)
        for a, pos in gracas.get(k, []):
            vozes.setdefault(numeros.get((a.voz, 0), base_voz), []).append(
                Peca(a, pos, pos, True, True))
        for numero_voz in sorted(vozes):
            v = stream.Voice(id=numero_voz)
            _preencher_voz(m, v, md, sorted(
                vozes[numero_voz], key=lambda p: (p.ini, p.acorde.g == 0, p.acorde.g)), qi)
            obj.insert(0, v)
        if not vozes:
            v = stream.Voice(id=base_voz)
            _preencher_voz(m, v, md, [], qi)
            obj.insert(0, v)
        parte.insert(md.t0 * QUATRO, obj)
    notacao.aplicar(m, ps, parte, n_pauta, acordes, {id(md): obj for md, obj in zip(medidas, por_medida)},
                    medidas, compasso_de, n_pauta == m.primeira_pauta)


def _estilo_da_formula(ps, n_pauta, t):
    """O `TimeSignature.style` da pauta no instante `t` ("C" por padrão, ou "numbered")."""
    estilo = "C"
    for ti, e in sorted(ps.estilos_formula.get(n_pauta, [])):
        if ti <= t:
            estilo = e
    return estilo


def _ultimas_por_instante(linhas):
    """Das linhas de clave/armadura, a última de cada `t` (ordenadas por `t` e `g`)."""
    por_t = {}
    for x in sorted(linhas, key=lambda x: (x.t, x.g)):
        por_t[x.t] = x
    return list(por_t.values())


def _repeticoes(m, ps, parte, por_medida, medidas, compasso_de):
    """Barras de repetição (`:|` e `|:`) e casas (`<ending>`), em todas as pautas.

    Vêm de `rep-inicio`/`rep-fim` (`\\repeat volta`), de `repeatCommands` à mão
    (`start-repeat`, `end-repeat`, `(volta "1.")`) e dos `volta` do `\\alternative`.
    """
    inicios, fins, casas = {}, [], []     # inicios: t -> vezes
    abertas = []                           # casas abertas: (t, numeros, texto)
    for r in ps.repeticoes:
        if r.tipo == "rep-inicio":
            inicios.setdefault(r.t, r.dados["vezes"])
        elif r.tipo == "rep-fim":
            fins.append(r.t)
        elif r.tipo == "repeticao":
            for cmd in r.dados["cmds"]:
                if cmd[0] == "start-repeat":
                    inicios.setdefault(r.t, cmd[1] if len(cmd) > 1 else 2)
                elif cmd[0] == "end-repeat":
                    fins.append(r.t)
                elif cmd[0] == "volta":
                    if cmd[1] is False:
                        if abertas:
                            ini, numeros, _ = abertas.pop()
                            casas.append((ini, r.t, numeros))
                    else:
                        texto = str(cmd[1])
                        numeros = [int(x) for x in re.findall(r"\d+", texto)]
                        abertas.append((r.t, numeros, texto))
        elif r.tipo == "volta":
            if r.dados["dir"] == "inicio":
                abertas.append((r.t, list(r.dados["numeros"]), None))
            else:
                for k in range(len(abertas) - 1, -1, -1):
                    if abertas[k][1] == list(r.dados["numeros"]):
                        casas.append((abertas.pop(k)[0], r.t, list(r.dados["numeros"])))
                        break
    for ini, numeros, _ in abertas:
        casas.append((ini, ps.fim, numeros))
        m.avisar(f"casa {numeros} sem fim: vai até o fim da peça")
    fins = sorted(set(fins))

    # Quantas vezes cada repetição se toca: o `vezes` do início que ela fecha.
    eventos_ = [(t, 0, None) for t in fins] + [(t, 1, v) for t, v in inicios.items()]
    pilha, vezes_do_fim = [], {}
    for t, tipo, v in sorted(eventos_, key=lambda x: (x[0], x[1])):
        if tipo == 1:
            pilha.append(v)
        else:
            vezes_do_fim[t] = pilha.pop() if pilha else 2

    por_t0 = {md.t0: i for i, md in enumerate(medidas)}
    por_t1 = {md.t1: i for i, md in enumerate(medidas)}
    for t in inicios:
        if t == medidas[0].t0:
            continue      # a repetição que começa na peça não leva barra (o LilyPond não desenha)
        i = por_t0.get(t)
        if i is None:
            i = medidas.index(compasso_de(t))
            m.avisar(f"início de repetição no meio do compasso {medidas[i].rotulo}: "
                     f"movido para o começo dele")
        por_medida[i].leftBarline = bar.Repeat(direction="start")
    for t in fins:
        i = por_t1.get(t)
        if i is None:
            i = medidas.index(compasso_de(t))
            m.avisar(f"fim de repetição no meio do compasso {medidas[i].rotulo}: "
                     f"movido para o fim dele")
        vezes = vezes_do_fim[t]
        por_medida[i].rightBarline = (bar.Repeat(direction="end", times=vezes) if vezes > 2
                                      else bar.Repeat(direction="end"))

    for ini, fim, numeros in sorted(casas):
        dentro = [obj for md, obj in zip(medidas, por_medida)
                  if md.t0 >= ini and md.t1 <= fim]
        if not dentro:
            dentro = [obj for md, obj in zip(medidas, por_medida)
                      if md.t0 < fim and md.t1 > ini]
            m.avisar(f"casa {numeros} começa ou termina no meio de um compasso: "
                     f"tomados os compassos que a contêm")
        if not dentro:
            continue
        numero = ", ".join(str(n) for n in numeros) if numeros else ""
        parte.insert(0, spanner.RepeatBracket(dentro, number=numero or "1"))


def _posicionar_gracas(m, ps, acordes, medidas, compasso_de):
    """`{índice do compasso: [(apojatura, instante)]}`.

    A apojatura entra no instante `t` da nota principal da mesma voz. Sem nota principal ali
    (`\\afterGrace`, que cai dentro da nota anterior), entra depois do acorde da voz que contém
    `t`, que é onde o MusicXML a põe (antes da nota seguinte); com aviso.
    """
    resultado = {}
    principais = {}
    for voz in ps.vozes.values():
        for a in voz.acordes:
            if a.g == 0 and a.alturas:
                principais.setdefault((voz.voz, a.t), a)
    for a in acordes:
        if a.g == 0:
            continue
        if not a.alturas:
            continue
        pos = a.t
        if (a.voz, a.t) not in principais:
            continente = next((x for x in ps.vozes[a.voz].acordes
                               if x.g == 0 and x.t < a.t < x.fim), None)
            if continente is None:
                # Presa a um espaço (`\\afterGrace s2.*4/5 { ... }`): fica onde está, num buraco
                # da voz (a pausa escondida é partida ali).
                m.avisar(f"afterGrace sobre espaço (c={a.c}, t={a.t})")
            else:
                pos = continente.fim
                m.avisar(f"afterGrace aproximada (c={a.c}, t={a.t})")
                if pos >= ps.fim:
                    m.avisar(f"apojatura no fim da peça descartada (c={a.c}, t={a.t})")
                    continue
        md = compasso_de(pos)
        resultado.setdefault(medidas.index(md), []).append((a, pos))
    return resultado


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


def _preencher_voz(m, voz, md, pedacos, quialteras):
    """Notas e pausas de uma voz num compasso, com pausas escondidas nos buracos."""
    cursor = md.t0
    for p in pedacos:
        if p.ini < cursor and p.acorde.g != 0:
            # Apojatura no meio de uma nota sustentada da mesma voz: o MusicXML não tem como
            # pô-la ali, e ela vai para depois da nota.
            m.avisar(f"apojatura deslocada para o fim da nota (c={p.acorde.c}, t={p.ini})")
            p = Peca(p.acorde, cursor, cursor, True, True)
        if p.ini < cursor:
            m.avisar(f"notas sobrepostas na mesma voz no compasso {md.rotulo} (t={p.ini}): "
                     f"descartada")
            continue
        if p.ini > cursor:
            _inserir_pausa_escondida(voz, md, cursor, p.ini)
        _inserir_peca(m, voz, md, p, quialteras)
        cursor = p.fim
    if cursor < md.t1 and pedacos:
        _inserir_pausa_escondida(voz, md, cursor, md.t1)
    elif not pedacos:
        r = note.Rest()
        r.duration = duration.Duration((md.t1 - md.t0) * QUATRO)
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


TIPOS = {-2: "longa", -1: "breve", 0: "whole", 1: "half", 2: "quarter", 3: "eighth",
         4: "16th", 5: "32nd", 6: "64th", 7: "128th", 8: "256th"}


def _duracao_figura(f, razao=None):
    """`Duration` a partir da figura do LilyPond (tipo, pontos e a escala da quiáltera).

    `razao` é o `(num, den)` impresso da quiáltera (6/4 numa sextina), que a escala sozinha
    perde (6/4 e 3/2 dão a mesma escala, 2/3).
    """
    tipo = TIPOS.get(f.fig)
    if tipo is None:
        return None
    d = duration.Duration(type=tipo, dots=f.pontos)
    if f.escala != 1:
        if razao is None or Fraction(razao[1], razao[0]) != f.escala:
            razao = (f.escala.denominator, f.escala.numerator)
        d.appendTuplet(duration.Tuplet(
            numberNotesActual=razao[0], numberNotesNormal=razao[1],
            durationActual=duration.Duration(type=tipo),
            durationNormal=duration.Duration(type=tipo)))
    return d


def _durs_da_peca(p, ql, quialtera):
    """Durações do pedaço: a figura exata quando o pedaço é o acorde inteiro.

    `quialtera` é o `(início, fim, num, den)` da quiáltera que contém o acorde, ou None. Sem ela,
    uma escala (`c4*2/3`) não vira quiáltera: o music21 escolhe a figura.
    """
    a = p.acorde
    if p.primeiro and p.ultimo and not a.compasso_inteiro and (a.figura.escala == 1
                                                               or quialtera is not None):
        d = _duracao_figura(a.figura, quialtera[2:] if quialtera else None)
        if d is not None and d.quarterLength == ql:
            return [d]
    return _duracoes(ql)


def _criar_elemento(a, d, interno_ant, interno_prox, inicio, fim):
    """Nota ou acorde com a duração `d`.

    `interno_ant`/`interno_prox`: o pedaço continua o anterior / tem outro depois dele (corte na
    barra). `inicio`/`fim`: é o primeiro/último pedaço do acorde, onde valem `lig_chega`/`lig`.
    """
    objs = []
    for h, lig, chega in zip(a.alturas, a.lig, a.lig_chega):
        ant = interno_ant or (inicio and chega)
        prox = interno_prox or (fim and lig)
        n = note.Note()
        n.pitch = _pitch(h)
        if ant and prox:
            n.tie = tie.Tie("continue")
        elif prox:
            n.tie = tie.Tie("start")
        elif ant:
            n.tie = tie.Tie("stop")
        objs.append(n)
    elem = objs[0] if len(objs) == 1 else chord.Chord(objs)
    elem.duration = d
    return elem


def _inserir_peca(m, voz, md, p, quialteras):
    a = p.acorde
    off = (p.ini - md.t0) * QUATRO
    if a.g != 0:
        # Apojatura: sem duração no compasso; barra (cortada) quando `a.barra`.
        sem_escala = Figura(a.figura.fig, a.figura.pontos, Fraction(1), a.figura.dur)
        d = _duracao_figura(sem_escala) or duration.Duration(0.25)
        elem = _criar_elemento(a, d, False, False, True, True).getGrace(
            appoggiatura=not a.barra)
        voz.insert(off, elem)
        m.refs.setdefault(id(a), []).append((elem, md, off))
        return
    ql = (p.fim - p.ini) * QUATRO
    durs = _durs_da_peca(p, ql, _quialtera_de(quialteras, a))
    for j, d in enumerate(durs):
        if not a.alturas:
            # Pausa (ou pausa de compasso, um pedaço por compasso).
            elem = note.Rest()
            elem.duration = d
            if a.compasso_inteiro:
                elem.fullMeasure = True
        else:
            elem = _criar_elemento(a, d, (not p.primeiro) or j > 0,
                                   (not p.ultimo) or j < len(durs) - 1,
                                   p.primeiro and j == 0, p.ultimo and j == len(durs) - 1)
        voz.insert(off, elem)
        m.refs.setdefault(id(a), []).append((elem, md, off))
        off += d.quarterLength


def _quialtera_de(intervalos, a):
    """A quiáltera mais interna da voz que contém o acorde (início, fim, num, den), ou None."""
    achou = None
    for q in intervalos.get(a.voz, ()):
        if q[0] <= a.t < q[1] and (achou is None or q[0] >= achou[0]):
            achou = q
    return achou


def _intervalos_quialtera(ps):
    """`{voz: [(início, fim, num, den)]}` dos pares `quialtera inicio`/`fim` de cada voz."""
    resultado = {}
    for voz, linhas in ps.quialteras.items():
        pilha, pares = [], []
        for q in sorted(linhas, key=lambda x: x.t):
            if q.dir == "inicio":
                pilha.append(q)
            elif pilha:
                ini = pilha.pop()
                pares.append((ini.t, q.t, ini.num, ini.den))
        pares += [(ini.t, ps.fim, ini.num, ini.den) for ini in pilha]
        resultado[voz] = pares
    return resultado


# ---------------------------------------------------------------------------
# Gravação
# ---------------------------------------------------------------------------

def _gravar(m, sc, saida: Path):
    for parte in sc.parts:
        for md in parte.getElementsByClass(stream.Measure):
            for v in md.voices:
                stream.makeNotation.makeTupletBrackets(v, inPlace=True)
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
        if titulo.text == "Music21 Fragment":
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
