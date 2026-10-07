"""Correções de sintaxe antiga que o convert-ly não faz (conversor/compat.py)."""
import pytest

from conftest import RAIZ
from conversor import compat


def depois(texto):
    return compat.depois_do_convert(texto)


def test_set_octavation_vira_ottava():
    texto, regras = depois("OCTAVEEND = #(set-octavation 0)\nB = { #(set-octavation -1) c'4 }")
    assert "\\ottava #0" in texto and "\\ottava #-1" in texto and "set-octavation" not in texto
    assert regras == ["set-octavation (×2)"]


def test_override_auto_beam_setting_sai():
    texto, regras = depois("  #(override-auto-beam-setting '(end * * * *) 6 8 'Score)\n  c4")
    assert "override-auto-beam" not in texto and texto.count("\n") == 1
    assert regras == ["override-auto-beam-setting"]


def test_apply_music_unfold_repeats():
    texto, _ = depois("\\applyMusic #unfold-repeats \\primoUp")
    assert texto == "\\unfoldRepeats \\primoUp"


@pytest.mark.parametrize("antigo,novo", [
    ("f8'-5_\\p ( d", "f'8-5_\\p ( d"),
    ("cis16,, d", "cis,,16 d"),
    ("a4.' b", "a'4. b"),
])
def test_marcas_de_oitava_antes_da_duracao(antigo, novo):
    texto, regras = depois(antigo)
    assert texto == novo and regras


@pytest.mark.parametrize("intacto", [
    "c'8 d'", "\\relative c' { c4 }", "c4 \"nota8'\"", "\\key c \\major",
    "fis'8 gis'", "r8 s4",
])
def test_nao_mexe_no_que_esta_certo(intacto):
    texto, regras = depois(intacto)
    assert texto == intacto and regras == []


def test_old_relative_comentado_sai_antes_do_convert():
    texto, regras = compat.antes_do_convert("%% #(ly:set-option 'old-relative)\n\\version \"2.16.1\"")
    assert "old-relative" not in texto and regras == ["old-relative comentado"]
    # Sem comentário, a opção muda o significado das notas: fica como está (o convert-ly falha).
    texto, regras = compat.antes_do_convert("#(ly:set-option 'old-relative)")
    assert "old-relative" in texto and regras == []


def test_preserva_as_linhas():
    original = "a\n#(set-octavation 1)\n#(override-auto-beam-setting 'x)\nb\n"
    texto, _ = depois(original)
    assert texto.count("\n") == original.count("\n")
