"""Passo 11: o MusicXML gerado bate com o MIDI do LilyPond."""
import subprocess
import sys

import pytest

from conftest import RAIZ, TESTES_LY

SCRIPT = RAIZ / "scripts" / "comparar-midi.py"


def rodar(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True,
                          text=True)


@pytest.mark.lilypond
@pytest.mark.parametrize("nome", ["01-contrato", "04-pauta", "09-atributos"])
def test_trechos_batem(nome):
    r = rodar(TESTES_LY / f"{nome}.ly")
    assert r.returncode == 0, r.stdout + r.stderr
    assert " OK" in r.stdout


@pytest.mark.lilypond
def test_xml_estragado_aponta_o_compasso(tmp_path):
    # Troca um <step> e o comparador acha a diferença, com o número do compasso.
    from conversor import comparacao, pipeline
    r = pipeline.converter_peca(TESTES_LY / "01-contrato.ly", tmp_path,
                                tmp_path / "x.musicxml", sem_midi=False)
    g = r.gravadas[0]
    texto = g.arquivo.read_text(encoding="utf-8")
    g.arquivo.write_text(texto.replace("<step>B</step>", "<step>C</step>", 1), encoding="utf-8")
    principais, apojaturas = comparacao.notas_do_musicxml(g.arquivo)
    res = comparacao.comparar_partitura(principais, apojaturas,
                                        comparacao.notas_do_midi(r.midi_de(g.partitura)))
    assert not res["ok"]
    assert any("c1" in d for d in res["diferencas"]), res["diferencas"]
