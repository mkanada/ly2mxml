"""De um .ly aos MusicXML: captura, leitura e montagem (usado pelo CLI, pelo comparar-midi e pelo
lote)."""
from dataclasses import dataclass, field
from pathlib import Path

from . import eventos, lilypond, montagem


class ErroSemPartitura(Exception):
    """A captura não achou nenhuma partitura com notas."""


@dataclass
class Gravada:
    partitura: object        # conversor.eventos.Partitura
    arquivo: Path
    avisos: list[str] = field(default_factory=list)


@dataclass
class Resultado:
    captura: lilypond.Captura
    partituras: list         # todas as lidas, na ordem da captura
    gravadas: list[Gravada] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)   # da captura, não de uma partitura

    def midi_de(self, partitura):
        """O MIDI do LilyPond da partitura (por ordem), ou None."""
        i = self.partituras.index(partitura)
        return self.captura.midis[i] if i < len(self.captura.midis) else None


def nomes_de_saida(base: str, saida: Path | None, quantas: int) -> list[Path]:
    if saida is None:
        saida = Path(f"{base}.musicxml")
    if quantas == 1:
        return [saida]
    return [saida.with_name(f"{saida.stem}-{n}{saida.suffix}") for n in range(1, quantas + 1)]


def converter_peca(arq: Path, tmp: Path, saida: Path | None = None, todas: bool = False,
                   forcar: bool = False, sem_midi: bool = True,
                   timeout: int | None = None) -> Resultado:
    """Converte `arq`. `tmp` guarda os intermediários e é de quem chama.

    Levanta `lilypond.ErroConvertLy`, `lilypond.ErroLilypond` ou `ErroSemPartitura`.
    """
    arq = Path(arq)
    captura = lilypond.capturar(arq, tmp, sem_midi=sem_midi, forcar=forcar, timeout=timeout)
    partituras = eventos.ler(captura.eventos)
    resultado = Resultado(captura, partituras)
    if captura.versao_original:
        resultado.avisos.append(f"versão original {captura.versao_original}")
    escolhidas = partituras if todas else eventos.escolher(partituras)
    escolhidas = [p for p in escolhidas if p.vozes]
    if not escolhidas:
        raise ErroSemPartitura(f"nenhuma partitura com notas em {arq.name}")
    for p, destino in zip(escolhidas, nomes_de_saida(arq.stem, saida, len(escolhidas))):
        destino.parent.mkdir(parents=True, exist_ok=True)
        avisos = montagem.montar(p, destino)
        resultado.gravadas.append(Gravada(p, destino, avisos))
    return resultado
