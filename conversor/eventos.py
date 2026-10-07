"""Leitura do .eventos.jsonl (passo 07): do JSON da captura para objetos Python.

É a única parte do Python que conhece o formato do JSON (docs/passos/01-formato-eventos.md).
Tempo sempre em `Fraction`, na unidade semibreve. A leitura não imprime nada: os avisos ficam em
`Partitura.avisos`, e quem chama decide o que fazer com eles.
"""
import json
from collections import defaultdict
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path

FORMATO = 1

ZERO = Fraction(0)


class ErroFormato(Exception):
    """O arquivo não é um .eventos.jsonl que esta leitura entende."""


@dataclass(slots=True)
class Altura:
    oitava: int          # LilyPond: 0 = oitava do c'
    nota: int            # 0 = dó ... 6 = si
    alt: Fraction        # em tons: 1/2 = sustenido
    midi: int


@dataclass(slots=True)
class Figura:
    fig: int             # log: 0 semibreve, 2 semínima, -1 breve
    pontos: int
    escala: Fraction     # 2/3 numa tercina
    dur: Fraction        # duração efetiva


@dataclass(slots=True)
class Acorde:
    """Também para nota solta (uma altura) e pausa (nenhuma altura)."""
    voz: int
    pauta: int           # pauta no momento (segue \change Staff)
    t: Fraction
    g: Fraction          # 0 fora de apojatura
    c: int
    pos: Fraction
    figura: Figura
    alturas: list[Altura] = field(default_factory=list)   # vazia = pausa
    lig: list[bool] = field(default_factory=list)         # por altura: começa ligadura
    lig_chega: list[bool] = field(default_factory=list)   # por altura: termina ligadura
    barra: bool = False              # apojatura cortada
    compasso_inteiro: bool = False   # pausa de compasso (R)

    @property
    def fim(self):
        return self.t + self.figura.dur


@dataclass(slots=True)
class Pauta:
    pauta: int
    id: str
    contexto: str
    inicio: Fraction
    fim: Fraction | None = None
    temporaria: bool = False


@dataclass(slots=True)
class Voz:
    voz: int
    id: str
    pauta: int           # pauta onde a voz nasceu
    acordes: list[Acorde] = field(default_factory=list)


@dataclass(slots=True)
class Clave:
    pauta: int
    t: Fraction
    pos: Fraction
    glifo: str
    posicao: int
    transp: int


@dataclass(slots=True)
class Armadura:
    pauta: int
    t: Fraction
    pos: Fraction
    tonica: Altura
    alteracoes: list[tuple]    # (nota, alt) ou (nota, alt, oitava)


@dataclass(slots=True)
class Compasso:
    c: int
    t: Fraction
    pos: Fraction
    tam: Fraction
    medindo: bool


@dataclass(slots=True)
class Formula:
    t: Fraction
    c: int
    pos: Fraction
    num: int
    den: int


@dataclass(slots=True)
class Barra:
    t: Fraction
    c: int
    pos: Fraction
    glifo: str


@dataclass(slots=True)
class Repeticao:
    """`repeticao` (repeatCommands), `volta`, `rep-inicio` ou `rep-fim`, na ordem do arquivo."""
    tipo: str
    t: Fraction
    c: int
    pos: Fraction
    dados: dict


@dataclass(slots=True)
class Quialtera:
    t: Fraction
    dir: str             # "inicio" ou "fim"
    num: int | None
    den: int | None


@dataclass(slots=True)
class Partitura:
    p: int
    so_midi: bool = False
    fim: Fraction = ZERO
    pautas: dict[int, Pauta] = field(default_factory=dict)
    vozes: dict[int, Voz] = field(default_factory=dict)
    claves: dict[int, list[Clave]] = field(default_factory=dict)
    armaduras: dict[int, list[Armadura]] = field(default_factory=dict)
    compassos: list[Compasso] = field(default_factory=list)
    formulas: list[Formula] = field(default_factory=list)
    barras: list[Barra] = field(default_factory=list)
    repeticoes: list[Repeticao] = field(default_factory=list)
    quialteras: dict[int, list[Quialtera]] = field(default_factory=dict)
    avisos: list[str] = field(default_factory=list)


def _fr(x):
    return Fraction(x)


def _altura(d, midi=None):
    nota, oitava, alt = d["nota"], d["oitava"], _fr(d["alt"])
    if midi is None:
        midi = 60 + 12 * oitava + (0, 2, 4, 5, 7, 9, 11)[nota] + int(alt * 2)
    return Altura(oitava, nota, alt, midi)


def _figura(e):
    return Figura(e["fig"], e["pontos"], _fr(e["escala"]), _fr(e["dur"]))


# ---------------------------------------------------------------------------
# Leitura
# ---------------------------------------------------------------------------

def ler(caminho) -> list[Partitura]:
    """Lê um .eventos.jsonl. Devolve as partituras, na ordem em que a captura as emitiu."""
    linhas = []
    with open(caminho, encoding="utf-8") as f:
        for n, texto in enumerate(f, 1):
            texto = texto.strip()
            if not texto:
                continue
            try:
                linhas.append(json.loads(texto))
            except json.JSONDecodeError as erro:
                raise ErroFormato(f"{caminho}:{n}: JSON inválido: {erro}") from erro
    return ler_linhas(linhas)


def ler_linhas(linhas) -> list[Partitura]:
    if not linhas or linhas[0].get("tipo") != "cabecalho":
        raise ErroFormato("a primeira linha não é o cabeçalho da captura")
    if linhas[0].get("formato") != FORMATO:
        raise ErroFormato(f"formato {linhas[0].get('formato')} não suportado "
                          f"(esta leitura entende o formato {FORMATO})")

    partituras: dict[int, Partitura] = {}
    notas = defaultdict(list)    # p -> linhas `nota`/`pausa`/`pausa-compasso` de voz
    desconhecidos = set()

    def da(p):
        if p not in partituras:
            partituras[p] = Partitura(p)
        return partituras[p]

    for e in linhas[1:]:
        tipo = e.get("tipo")
        p = e.get("p")
        if tipo == "partitura":
            da(p).so_midi = bool(e["so_midi"])
        elif tipo == "pauta":
            da(p).pautas[e["pauta"]] = Pauta(e["pauta"], e["id"], e["contexto"], _fr(e["t"]))
        elif tipo == "fim-pauta":
            da(p).pautas[e["pauta"]].fim = _fr(e["t"])
        elif tipo == "voz":
            da(p).vozes[e["voz"]] = Voz(e["voz"], e["id"], e["pauta"])
        elif tipo in ("nota", "pausa", "pausa-compasso"):
            notas[p].append(e)
        elif tipo == "quialtera":
            da(p).quialteras.setdefault(e["voz"], []).append(
                Quialtera(_fr(e["t"]), e["dir"], e["num"], e["den"]))
        elif tipo == "clave":
            da(p).claves.setdefault(e["pauta"], []).append(
                Clave(e["pauta"], _fr(e["t"]), _fr(e["pos"]), e["glifo"], e["posicao"],
                      e["transp"]))
        elif tipo == "armadura":
            alts = [(a[0], _fr(a[1])) + tuple(a[2:]) for a in e["alteracoes"]]
            da(p).armaduras.setdefault(e["pauta"], []).append(
                Armadura(e["pauta"], _fr(e["t"]), _fr(e["pos"]), _altura(e["tonica"], 0), alts))
        elif tipo == "compasso":
            da(p).compassos.append(
                Compasso(e["c"], _fr(e["t"]), _fr(e["pos"]), _fr(e["tam"]), e["medindo"]))
        elif tipo == "formula":
            da(p).formulas.append(
                Formula(_fr(e["t"]), e["c"], _fr(e["pos"]), e["num"], e["den"]))
        elif tipo == "barra":
            da(p).barras.append(Barra(_fr(e["t"]), e["c"], _fr(e["pos"]), e["glifo"]))
        elif tipo in ("repeticao", "volta", "rep-inicio", "rep-fim"):
            dados = {k: v for k, v in e.items() if k not in ("tipo", "p", "t", "g", "c", "pos")}
            da(p).repeticoes.append(
                Repeticao(tipo, _fr(e["t"]), e["c"], _fr(e["pos"]), dados))
        elif tipo == "fim":
            da(p).fim = _fr(e["t"])
        elif tipo == "aviso":
            da(p).avisos.append(e["texto"])
        elif tipo == "cabecalho":
            pass
        else:
            if tipo not in desconhecidos:
                desconhecidos.add(tipo)
                alvo = da(p) if p is not None else (next(iter(partituras.values()), None))
                if alvo is not None:
                    alvo.avisos.append(f"linha de tipo desconhecido ignorada: {tipo}")

    for p, ps in partituras.items():
        _montar_acordes(ps, notas.get(p, []))
        _ligaduras(ps)
        for voz in ps.vozes.values():
            voz.acordes.sort(key=lambda a: (a.t, a.g))
        # Voz sem nenhum acorde (só `s`) não existe para a montagem.
        for n in [n for n, v in ps.vozes.items() if not v.acordes]:
            del ps.vozes[n]
        for pauta in ps.pautas.values():
            pauta.temporaria = (pauta.fim is not None and pauta.fim < ps.fim) or pauta.inicio > 0
        # Compassos e fórmulas na ordem do tempo (a captura não garante a ordem).
        ps.compassos.sort(key=lambda x: x.t)
        ps.formulas.sort(key=lambda x: x.t)
        ps.barras.sort(key=lambda x: x.t)
    return [partituras[p] for p in sorted(partituras)]


def _montar_acordes(ps, linhas):
    """Agrupa as linhas de voz em acordes: por (voz, t, g, figura, pauta)."""
    grupos = defaultdict(list)
    for e in linhas:
        if e["tipo"] == "nota":
            chave = (e["voz"], _fr(e["t"]), _fr(e["g"]))
            grupos[chave].append(e)
        else:
            figura = _figura(e)
            if e["voz"] not in ps.vozes:
                ps.vozes[e["voz"]] = Voz(e["voz"], "", e["pauta"])
            ps.vozes[e["voz"]].acordes.append(Acorde(
                e["voz"], e["pauta"], _fr(e["t"]), _fr(e["g"]), e["c"], _fr(e["pos"]), figura,
                compasso_inteiro=(e["tipo"] == "pausa-compasso")))
    for (voz, t, g), es in grupos.items():
        por_figura = defaultdict(list)
        for e in es:
            fig = _figura(e)
            por_figura[(fig.fig, fig.pontos, fig.escala, fig.dur, e["pauta"])].append(e)
        if len(por_figura) > 1:
            ps.avisos.append(f"acorde com figuras diferentes separado (c={es[0]['c']}, t={t})")
        for grupo in por_figura.values():
            grupo.sort(key=lambda e: e["midi"])
            vistos = set()
            alturas, ligs = [], []
            for e in grupo:
                if e["midi"] in vistos:
                    ps.avisos.append(f"altura repetida no acorde removida (c={e['c']}, t={t})")
                    continue
                vistos.add(e["midi"])
                alturas.append(_altura(e["altura"], e["midi"]))
                ligs.append(bool(e["lig"]))
            primeiro = grupo[0]
            if voz not in ps.vozes:
                ps.vozes[voz] = Voz(voz, "", primeiro["pauta"])
            ps.vozes[voz].acordes.append(Acorde(
                voz, primeiro["pauta"], t, g, primeiro["c"], _fr(primeiro["pos"]),
                _figura(primeiro), alturas, ligs, [False] * len(alturas),
                barra=bool(primeiro.get("barra", False))))


def _ligaduras(ps):
    """Resolve o destino de cada ligadura, na mesma voz.

    O destino é o acorde que começa em `fim` e tem a mesma altura. Num arpejo
    (`c16~ g~ c~ ... <c g c'>4`) o dó liga ao acorde final por cima de outras notas da voz: então
    segue-se a voz enquanto os acordes forem contíguos (sem pausa nem buraco). A apojatura ligada
    à principal (`\\grace c8~ c4`) procura a principal no mesmo `t`.
    """
    for voz in ps.vozes.values():
        acordes = sorted(voz.acordes, key=lambda a: (a.t, a.g))
        voz.acordes = acordes
        for i, a in enumerate(acordes):
            for k, (altura, lig) in enumerate(zip(a.alturas, a.lig)):
                if not lig:
                    continue
                destino = _destino(acordes, i, altura.midi)
                if destino is None:
                    a.lig[k] = False
                    ps.avisos.append(f"ligadura sem destino (c={a.c}, t={a.t})")
                else:
                    destino.lig_chega[[x.midi for x in destino.alturas].index(altura.midi)] = True


def _destino(acordes, i, midi):
    a = acordes[i]
    if a.g != 0:
        # Apojatura: o destino é a próxima nota (outra apojatura ou a principal).
        for b in acordes[i + 1:]:
            if b.t != a.t:
                break
            if not b.alturas:
                return None
            if any(x.midi == midi for x in b.alturas):
                return b
        return None
    fim = a.fim
    for b in acordes[i + 1:]:
        if b.g != 0:
            continue
        if b.t < fim:
            continue          # outra voz do mesmo instante não está aqui; só a mesma voz
        if b.t > fim or not b.alturas:
            return None       # buraco ou pausa: a ligadura não tem destino
        if any(x.midi == midi for x in b.alturas):
            return b
        fim = b.fim
    return None


def escolher(partituras):
    """As partituras que viram MusicXML: as que não são `so_midi`; se todas forem, todas."""
    boas = [p for p in partituras if not p.so_midi]
    return boas if boas else list(partituras)
