"""Passos 08 e 09: montagem do MusicXML a partir dos eventos (sem LilyPond)."""
import xml.etree.ElementTree as ET

import pytest

from conftest import TESTES_LY
from conversor import eventos, montagem

CONTRATO = TESTES_LY / "01-contrato.eventos.jsonl"


def montar(tmp_path, jsonl=CONTRATO, nome="x.musicxml"):
    ps = eventos.escolher(eventos.ler(jsonl))
    saida = tmp_path / nome
    avisos = montagem.montar(ps[0], saida)
    return saida, avisos


def raiz(caminho):
    return ET.parse(caminho).getroot()


def test_contrato_estrutura(tmp_path):
    saida, avisos = montar(tmp_path)
    r = raiz(saida)
    partes = r.findall("part")
    assert len(partes) == 1
    assert partes[0].get("id") == "P1"
    assert partes[0].findtext("measure/attributes/staves") == "2"
    compassos = partes[0].findall("measure")
    assert [(c.get("number"), c.get("implicit")) for c in compassos] == [("0", "yes"), ("1", "no")]
    # O acorde sol–si do compasso 1, ligado, na pauta 1.
    notas = [n for n in compassos[1].findall("note") if n.find("rest") is None
             and n.findtext("staff") == "1"]
    assert [n.findtext("pitch/step") for n in notas[:2]] == ["G", "B"]
    assert notas[0].find("tie").get("type") == "start"
    assert notas[2].find("tie").get("type") == "stop"
    assert avisos == []


def test_sem_data_nem_titulo(tmp_path):
    saida, _ = montar(tmp_path)
    texto = saida.read_text(encoding="utf-8")
    assert "encoding-date" not in texto and "movement-title" not in texto
    assert 'id="P1"' in texto


def test_reproduzivel(tmp_path):
    a, _ = montar(tmp_path, nome="a.musicxml")
    b, _ = montar(tmp_path, nome="b.musicxml")
    assert a.read_bytes() == b.read_bytes()


def test_music21_le_a_saida(tmp_path):
    from music21 import converter
    saida, _ = montar(tmp_path)
    assert len(list(converter.parse(str(saida)).flatten().notes)) > 0


@pytest.mark.lilypond
def test_atributos_do_passo_09(tmp_path):
    from conversor import pipeline
    r = pipeline.converter_peca(TESTES_LY / "09-atributos.ly", tmp_path, tmp_path / "x.musicxml")
    raiz_ = raiz(r.gravadas[0].arquivo)
    compassos = raiz_.findall("part/measure")
    fifths = [(c.get("number"), k.findtext("fifths"), k.get("number"))
              for c in compassos for k in c.findall("attributes/key")]
    assert ("2", "2", "1") in fifths and ("3", "0", "1") in fifths
    # Fórmula 6/8 no compasso 4, clave de fá no 3, sol oitava abaixo no 4.
    assert compassos[4].findtext("attributes/time/beats") == "6"
    claves = [(c.get("number"), cl.findtext("sign"), cl.findtext("clef-octave-change"))
              for c in compassos for cl in c.findall("attributes/clef")]
    assert ("3", "F", None) in claves and ("4", "G", "-1") in claves
    # Barra final.
    assert compassos[-1].findtext("barline/bar-style") == "light-heavy" or any(
        b.findtext("bar-style") == "light-heavy" for b in raiz_.iter("barline"))


def converter(tmp_path, nome):
    from conversor import pipeline
    r = pipeline.converter_peca(TESTES_LY / f"{nome}.ly", tmp_path, tmp_path / "x.musicxml",
                                sem_midi=False)
    return r, raiz(r.gravadas[0].arquivo)


@pytest.mark.lilypond
def test_quialteras_12(tmp_path):
    r, raiz_ = converter(tmp_path, "12-quialteras")
    notas = [n for n in raiz_.iter("note") if n.findtext("staff") == "1"]
    razoes = {(tm.findtext("actual-notes"), tm.findtext("normal-notes"))
              for n in notas for tm in n.findall("time-modification")}
    assert razoes == {("3", "2"), ("6", "4"), ("5", "4")}
    # Todo colchete que abre fecha, em cada voz.
    for voz in {n.findtext("voice") for n in notas}:
        marcas = [t.get("type") for n in notas if n.findtext("voice") == voz
                  for t in n.findall("notations/tuplet")]
        assert marcas.count("start") == marcas.count("stop") > 0 or not marcas
    assert r.gravadas[0].avisos == []


@pytest.mark.lilypond
def test_apojaturas_13(tmp_path):
    r, raiz_ = converter(tmp_path, "13-apojaturas")
    graca = [n for n in raiz_.iter("note") if n.find("grace") is not None]
    assert len(graca) == 13
    # \acciaccatura e \slashedGrace têm barra; \grace e \appoggiatura não.
    barras = [g.find("grace").get("slash") for g in graca[:4]]
    assert barras == ["no", "yes", "no", "yes"]
    # A apojatura vem antes da nota principal no mesmo compasso.
    primeiro = list(raiz_.find("part/measure"))
    nomes = [n.findtext("pitch/step") for n in primeiro if n.tag == "note"
             and n.findtext("staff") == "1"]
    assert nomes[:2] == ["D", "C"]


@pytest.mark.lilypond
@pytest.mark.parametrize("nome", ["12-quialteras", "13-apojaturas", "03-vozes"])
def test_bate_com_o_midi(nome):
    import subprocess, sys
    from conftest import RAIZ
    r = subprocess.run([sys.executable, str(RAIZ / "scripts" / "comparar-midi.py"),
                        str(TESTES_LY / f"{nome}.ly")], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


@pytest.mark.lilypond
def test_repeticoes_14(tmp_path):
    r, raiz_ = converter(tmp_path, "14-repeticoes")
    compassos = raiz_.findall("part/measure")
    barras = [(c.get("number"), b.get("location"), b.find("repeat").get("direction"),
               b.find("repeat").get("times")) for c in compassos for b in c.findall("barline")
              if b.find("repeat") is not None]
    # A repetição que começa na primeira nota da peça não leva barra (o LilyPond não a desenha).
    assert not any(n == "1" and d == "forward" for n, _, d, _ in barras)
    assert any(n == "2" and d == "forward" for n, _, d, _ in barras)
    assert any(d == "backward" and t == "3" for _, _, d, t in barras)
    casas = [(e.get("number"), e.get("type")) for e in raiz_.iter("ending")]
    assert ("1,2", "start") in casas and ("1,2", "stop") in casas
    assert ("3", "start") in casas and ("3", "stop") in casas
    avisos = r.gravadas[0].avisos
    assert any("tremolo" in a for a in avisos)


@pytest.mark.lilypond
def test_percent_sai_desdobrado(tmp_path):
    # \repeat percent 2 { 8 colcheias } dá 16 notas, não 8.
    r, _ = converter(tmp_path, "14-repeticoes")
    notas = [a for v in r.gravadas[0].partitura.vozes.values() for a in v.acordes
             if a.pauta == 1 and a.alturas and a.figura.dur == 1 / 8]
    assert len(notas) >= 16


@pytest.mark.lilypond
def test_compassos_15(tmp_path):
    r, raiz_ = converter(tmp_path, "15-compassos")
    numeros = [(c.get("number"), c.get("implicit")) for c in raiz_.findall("part/measure")]
    assert numeros[0] == ("0", "yes")
    assert ("6b", "yes") in numeros and ("8b", "yes") in numeros     # depois das cadenzas
    assert numeros[-2:] == [("50", "no"), ("51", "no")]
    avisos = r.gravadas[0].avisos
    assert any("cadenza no compasso 6" in a for a in avisos)
    assert any("cadenza no compasso 8" in a for a in avisos)


@pytest.mark.lilypond
@pytest.mark.parametrize("nome", ["14-repeticoes", "15-compassos"])
def test_14_15_batem_com_o_midi(nome):
    import subprocess, sys
    from conftest import RAIZ
    r = subprocess.run([sys.executable, str(RAIZ / "scripts" / "comparar-midi.py"),
                        str(TESTES_LY / f"{nome}.ly")], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


@pytest.mark.lilypond
def test_clave_de_fa_depois_de_apojatura_no_inicio(tmp_path):
    # A peça começa por apojatura: a clave padrão chega em g < 0 e a `\clef bass` no mesmo `t`.
    _, raiz_ = converter(tmp_path, "13-apojaturas")
    claves = {c.get("number"): c.findtext("sign") for c in raiz_.iter("clef")}
    assert claves == {"1": "G", "2": "F"}
