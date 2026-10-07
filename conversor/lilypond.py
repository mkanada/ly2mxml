"""Chamar o `convert-ly` e o `lilypond` a partir do Python (passo 10).

Mesma lógica do `scripts/ly2json.sh`, sem depender de bash. O envelope e o `.ly` convertido ficam
em `tmp`, que é de quem chama; o original nunca é alterado.
"""
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

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

    convertido = tmp / f"{base}-2.26.ly"
    r = subprocess.run([str(convert), str(arq)], capture_output=True, text=True,
                       errors="replace")
    if r.returncode != 0:
        raise ErroConvertLy(f"convert-ly falhou para {arq.name}:\n{r.stderr.strip()}")
    convertido.write_text(r.stdout, encoding="utf-8")

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
                      base)
    if r.returncode != 0 and not forcar:
        raise ErroLilypond(f"lilypond falhou para {arq.name}:\n{linhas_de_erro(r.stderr)}",
                           captura)
    if not eventos.exists():
        raise ErroLilypond(f"lilypond não gerou eventos para {arq.name}:\n"
                           f"{linhas_de_erro(r.stderr)}", captura)
    return captura
