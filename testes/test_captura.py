"""A captura (ly/captura.ly) contra o exemplo do contrato (docs/passos/01-formato-eventos.md)."""
import json
import subprocess

import pytest

from conftest import RAIZ, TESTES_LY


@pytest.mark.lilypond
def test_captura_do_exemplo_do_contrato(tmp_path):
    r = subprocess.run([str(RAIZ / "scripts" / "ly2json.sh"), str(TESTES_LY / "01-contrato.ly"),
                        str(tmp_path)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    obtido = [json.loads(l) for l in open(tmp_path / "01-contrato.eventos.jsonl")]
    esperado = [json.loads(l) for l in open(TESTES_LY / "01-contrato.eventos.jsonl")]
    # A ordem dentro de um instante não é garantida (docs/passos/01): compara como conjuntos.
    chave = lambda d: json.dumps(d, sort_keys=True)
    assert sorted(map(chave, obtido)) == sorted(map(chave, esperado))


@pytest.mark.lilypond
def test_cada_linha_e_um_json_valido_nas_tres_primeiras_pecas_de_teste(tmp_path):
    for nome in ("03-vozes", "04-pauta", "05-scores", "18-notacao"):
        r = subprocess.run([str(RAIZ / "scripts" / "ly2json.sh"), str(TESTES_LY / f"{nome}.ly"),
                            str(tmp_path)], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        linhas = [json.loads(l) for l in open(tmp_path / f"{nome}.eventos.jsonl")]
        assert linhas[0] == {"tipo": "cabecalho", "formato": 2, "lilypond": "2.26.0"}
