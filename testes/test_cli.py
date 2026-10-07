"""Passo 10: o CLI ly2mxml.py de ponta a ponta."""
import subprocess
import sys

import pytest

from conftest import RAIZ, TESTES_LY

CLI = RAIZ / "ly2mxml.py"


def rodar(*args, cwd=None):
    return subprocess.run([sys.executable, str(CLI), *map(str, args)], capture_output=True,
                          text=True, cwd=cwd)


@pytest.mark.lilypond
def test_contrato(tmp_path):
    saida = tmp_path / "x.musicxml"
    r = rodar(TESTES_LY / "01-contrato.ly", "-o", saida)
    assert r.returncode == 0, r.stderr
    assert saida.exists()
    from music21 import converter
    assert converter.parse(str(saida)) is not None


@pytest.mark.lilypond
def test_varias_partituras_descarta_so_midi(tmp_path):
    saida = tmp_path / "x.musicxml"
    r = rodar(TESTES_LY / "05-scores.ly", "-o", saida)
    assert r.returncode == 0, r.stderr
    assert sorted(p.name for p in tmp_path.iterdir()) == ["x-1.musicxml", "x-2.musicxml",
                                                          "x-3.musicxml"]


@pytest.mark.lilypond
def test_nome_padrao_no_diretorio_atual(tmp_path):
    r = rodar(TESTES_LY / "02-minimo.ly", cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    assert (tmp_path / "02-minimo.musicxml").exists()


def test_arquivo_inexistente(tmp_path):
    r = rodar(tmp_path / "nao-existe.ly")
    assert r.returncode == 2
    assert "Traceback" not in r.stderr and "não encontrado" in r.stderr


@pytest.mark.lilypond
def test_lilypond_com_erro_da_status_3(tmp_path):
    ruim = tmp_path / "ruim.ly"
    ruim.write_text('\\version "2.26.0"\n\\score { \\new Staff { c\' d\'  } \\layout { } }\n'
                    '\\foo\n', encoding="utf-8")
    r = rodar(ruim, "-o", tmp_path / "x.musicxml")
    assert r.returncode == 3
    assert "Traceback" not in r.stderr
