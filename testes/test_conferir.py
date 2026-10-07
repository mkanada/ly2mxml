"""Passo 17: a página de conferência visual."""
import subprocess
import sys

import pytest

from conftest import RAIZ, TESTES_LY

SCRIPT = RAIZ / "scripts" / "conferir.py"


@pytest.mark.lilypond
def test_gera_o_html_com_as_duas_colunas(tmp_path):
    r = subprocess.run([sys.executable, str(SCRIPT), str(TESTES_LY / "05-scores.ly"), "-o",
                        str(tmp_path)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    html = (tmp_path / "05-scores.html").read_text(encoding="utf-8")
    assert "LilyPond" in html and "Verovio" in html
    # Os quatro \score do arquivo dão quatro páginas de um lado e três MusicXML do outro.
    assert (tmp_path / "05-scores-ly-1.svg").exists()
    assert (tmp_path / "05-scores-1-mxml-1.svg").exists()
    assert "<svg" in (tmp_path / "05-scores-1-mxml-1.svg").read_text(encoding="utf-8")


def test_peca_inexistente(tmp_path):
    r = subprocess.run([sys.executable, str(SCRIPT), "nao-existe", "-o", str(tmp_path)],
                       capture_output=True, text=True)
    assert r.returncode == 2
