"""Passo 06: o JSON capturado bate com o MIDI do LilyPond."""
import subprocess
import sys

import pytest

from conftest import RAIZ, TESTES_LY

SCRIPT = RAIZ / "scripts" / "json-vs-midi.py"


def rodar(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)],
                          capture_output=True, text=True)


@pytest.mark.lilypond
@pytest.mark.parametrize("nome", ["03-vozes", "04-pauta", "05-scores"])
def test_trechos_batem_com_o_midi(nome):
    r = rodar(TESTES_LY / f"{nome}.ly")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "OK" in r.stdout


@pytest.mark.lilypond
def test_cinco_scores_do_topo():
    r = rodar(TESTES_LY / "05-scores.ly")
    assert r.stdout.count(" OK") == 4, r.stdout
    assert "so_midi" in r.stdout


@pytest.mark.lilypond
def test_book_repete_nome_de_midi_e_nao_compara_esse():
    # Dois MIDI com o mesmo nome no log: o script avisa e não compara aquele arquivo.
    r = rodar(TESTES_LY / "05-book.ly")
    assert "repetido" in r.stdout, r.stdout
