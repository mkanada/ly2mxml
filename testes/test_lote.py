"""Passo 16: o lote (scripts/converter-todos.py) e o resumo de regressão."""
import csv
import shutil
import subprocess
import sys

import pytest

from conftest import RAIZ, TESTES_LY

SCRIPT = RAIZ / "scripts" / "converter-todos.py"


def lote(acervo, saida, *args):
    return subprocess.run([sys.executable, str(SCRIPT), "--acervo", str(acervo), "--saida",
                           str(saida), "-j", "2", *args], capture_output=True, text=True)


@pytest.fixture
def acervo(tmp_path):
    pasta = tmp_path / "acervo"
    pasta.mkdir()
    for nome in ("01-contrato", "05-scores", "13-apojaturas"):
        shutil.copy(TESTES_LY / f"{nome}.ly", pasta / f"{nome}.ly")
    (pasta / "quebrada.ly").write_text('\\version "2.26.0"\n\\score { \\foo }\n', encoding="utf-8")
    return pasta


@pytest.mark.lilypond
def test_resumo_e_segunda_rodada_sem_mudancas(acervo, tmp_path):
    saida = tmp_path / "saida"
    r = lote(acervo, saida)
    assert r.returncode == 0, r.stderr
    linhas = list(csv.DictReader(open(saida / "_resumo.csv", encoding="utf-8")))
    por = {(l["peca"], l["p"]): l for l in linhas}
    assert por[("01-contrato", "1")]["status"] == "ok"
    assert por[("01-contrato", "1")]["midi"] == "5/5"
    assert por[("13-apojaturas", "1")]["apojaturas"] == "13"
    assert [k for k in por if k[0] == "05-scores"] == [("05-scores", "1"), ("05-scores", "2"),
                                                       ("05-scores", "3")]
    assert por[("quebrada", "1")]["status"].startswith("ERRO")
    assert "== quebrada" in (saida / "_avisos.log").read_text(encoding="utf-8")
    assert (saida / "01-contrato.musicxml").exists()
    # Segunda rodada: nada mudou.
    r2 = lote(acervo, saida)
    assert "0 de" in r2.stdout, r2.stdout


@pytest.mark.lilypond
def test_mudanca_aparece_e_so_algumas_pecas_mantem_as_outras(acervo, tmp_path):
    saida = tmp_path / "saida"
    lote(acervo, saida)
    # Muda uma peça e roda só ela: as outras linhas continuam no resumo.
    ly = acervo / "01-contrato.ly"
    ly.write_text(ly.read_text(encoding="utf-8").replace("d4 |", "e4 |", 1), encoding="utf-8")
    r = lote(acervo, saida, "01-contrato")
    assert "01-contrato p1" in r.stdout and "hash" in r.stdout, r.stdout
    pecas = {l["peca"] for l in csv.DictReader(open(saida / "_resumo.csv", encoding="utf-8"))}
    assert {"05-scores", "13-apojaturas", "quebrada"} <= pecas
