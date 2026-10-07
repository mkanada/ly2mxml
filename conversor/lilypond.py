"""Chamar o `convert-ly` e o `lilypond` a partir do Python (passo 10).

Mesma lógica do `scripts/ly2json.sh`, sem depender de bash. O envelope e o `.ly` convertido ficam
em `tmp`, que é de quem chama; o original nunca é alterado.
"""
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from . import compat

RAIZ = Path(__file__).resolve().parent.parent
BIN = RAIZ / "ferramentas" / "lilypond" / "bin"
CAPTURA = RAIZ / "ly" / "captura.ly"


class ErroLilypondAusente(Exception):
    """O LilyPond fixado em ferramentas/ não está instalado."""


class ErroConvertLy(Exception):
    """O `convert-ly` falhou."""


class ErroLilypond(Exception):
    """O `lilypond` falhou (há linhas `error:` na mensagem)."""

    def __init__(self, mensagem, captura=None):
        super().__init__(mensagem)
        self.captura = captura


@dataclass
class Captura:
    eventos: Path                 # .eventos.jsonl
    midis: list[Path]             # na ordem das partituras (vazio se sem_midi)
    log: str                      # stderr do lilypond
    versao_original: str | None   # do \version do arquivo, antes do convert-ly
    base: str = ""
    compat: list = None           # regras de conversor/compat.py que dispararam


def versao_do_arquivo(arq: Path) -> str | None:
    texto = arq.read_text(encoding="utf-8", errors="replace")
    m = re.search(r'\\version\s*"([^"]+)"', texto)
    return m.group(1) if m else None


def midis_do_log(log: str) -> list[str]:
    """Nomes dos MIDI, na ordem em que o LilyPond os escreveu."""
    return re.findall(r"MIDI output to `(.+?)'", log)


def linhas_de_erro(log: str) -> str:
    erros = [l for l in log.splitlines() if "error:" in l.lower()]
    return "\n".join(erros) if erros else log.strip()[-2000:]


def _atualizar(arq: Path, tmp: Path, base: str):
    """Escreve em `tmp` a cópia de `arq` na sintaxe 2.26 (`convert-ly` e `compat`).

    Devolve `(caminho da cópia, regras de compat aplicadas)`.
    """
    texto, antes = compat.antes_do_convert(arq.read_text(encoding="utf-8", errors="replace"))
    original = tmp / f"{base}-original.ly"
    original.write_text(texto, encoding="utf-8")
    r = subprocess.run([str(BIN / "convert-ly"), str(original)], capture_output=True, text=True,
                       errors="replace")
    if r.returncode != 0:
        raise ErroConvertLy(f"convert-ly falhou para {arq.name}:\n{r.stderr.strip()}")
    texto, depois = compat.depois_do_convert(r.stdout)
    convertido = tmp / f"{base}-2.26.ly"
    convertido.write_text(texto, encoding="utf-8")
    return convertido, antes + depois


def capturar(arq: Path, tmp: Path, sem_midi: bool = False, timeout: int | None = None,
             forcar: bool = False) -> Captura:
    """Roda `convert-ly` e o `lilypond` com a captura.

    Levanta `ErroConvertLy` ou `ErroLilypond`. Com `forcar`, um `lilypond` que falha mas deixou
    eventos não levanta (o chamador decide o que fazer com o `log`).
    """
    arq = Path(arq).resolve()
    tmp = Path(tmp)
    lilypond, convert = BIN / "lilypond", BIN / "convert-ly"
    for exe in (lilypond, convert):
        if not exe.exists():
            raise ErroLilypondAusente(
                f"{exe} não encontrado: rode scripts/instalar-lilypond.sh")
    base = arq.stem
    versao = versao_do_arquivo(arq)

    convertido, aplicadas = _atualizar(arq, tmp, base)

    # A captura antes do arquivo do usuário: o \layout com os engravers precisa existir antes.
    envelope = tmp / "envelope.ly"
    envelope.write_text(f'\\version "2.26.0"\n\\include "{CAPTURA}"\n'
                        f'\\include "{convertido}"\n', encoding="utf-8")
    eventos = tmp / f"{base}.eventos.jsonl"
    env = {**os.environ, "LY2MXML_EVENTOS": str(eventos),
           "LY2MXML_SEM_MIDI": "1" if sem_midi else ""}
    r = subprocess.run(
        [str(lilypond), "-dno-print-pages", "-I", str(arq.parent), "-o", str(tmp / base),
         str(envelope)],
        capture_output=True, text=True, errors="replace", env=env, timeout=timeout)
    captura = Captura(eventos, [tmp / n for n in midis_do_log(r.stderr)], r.stderr, versao,
                      base, aplicadas)
    if r.returncode != 0 and not forcar:
        raise ErroLilypond(f"lilypond falhou para {arq.name}:\n{linhas_de_erro(r.stderr)}",
                           captura)
    if not eventos.exists():
        raise ErroLilypond(f"lilypond não gerou eventos para {arq.name}:\n"
                           f"{linhas_de_erro(r.stderr)}", captura)
    return captura


def renderizar_svg(arq: Path, destino: Path, base: str | None = None) -> list[Path]:
    """Compila o `.ly` (já atualizado pelo `convert-ly`) em SVG, uma por página.

    Sem a captura: é o desenho do próprio LilyPond, para comparar com o do MusicXML (passo 17).
    Copia as páginas, em ordem, para `destino/BASE-ly-N.svg` e devolve os caminhos. O
    `-dbackend=svg` escreve `lily-1.svg`, `lily-2.svg`... (ou `lily.svg` se for uma só) e avisa
    `ignoring unsupported formats (pdf)`, que é inofensivo.
    """
    import re
    import shutil
    import tempfile

    arq = Path(arq).resolve()
    base = base or arq.stem
    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        convertido, _ = _atualizar(arq, tmp, base)
        r = subprocess.run([str(BIN / "lilypond"), "-dbackend=svg", "-I", str(arq.parent),
                            "-o", str(tmp / "lily"), str(convertido)],
                           capture_output=True, text=True, errors="replace")
        numeradas = sorted((int(m.group(1)), p) for p in tmp.glob("lily-*.svg")
                           if (m := re.fullmatch(r"lily-(\d+)\.svg", p.name)))
        paginas = [p for _, p in numeradas] or ([tmp / "lily.svg"] if (tmp / "lily.svg").exists()
                                                else [])
        if not paginas:
            raise ErroLilypond(f"lilypond não gerou SVG para {arq.name}:\n"
                               f"{linhas_de_erro(r.stderr)}")
        copias = []
        for n, p in enumerate(paginas, 1):
            copia = destino / f"{base}-ly-{n}.svg"
            shutil.copy2(p, copia)
            copias.append(copia)
    return copias
