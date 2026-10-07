"""Passo 18: notação (articulações, dinâmica, ligaduras de expressão, pedal, andamento...)."""
import xml.etree.ElementTree as ET

import pytest

from conftest import TESTES_LY


@pytest.fixture(scope="module")
def raiz(tmp_path_factory):
    from conversor import pipeline
    tmp = tmp_path_factory.mktemp("n18")
    r = pipeline.converter_peca(TESTES_LY / "18-notacao.ly", tmp, tmp / "x.musicxml",
                                sem_midi=False)
    return ET.parse(r.gravadas[0].arquivo).getroot(), r


def contar(raiz_, caminho, **atributos):
    return sum(1 for e in raiz_.iter(caminho.split("/")[-1])
               if all(e.get(k) == v for k, v in atributos.items()))


@pytest.mark.lilypond
def test_metadados(raiz):
    r, _ = raiz
    assert r.findtext("work/work-title") == "Notação"
    assert r.find("identification/creator").text == "Teste"
    assert r.find("identification/miscellaneous/miscellaneous-field").get("name") == "opus"


@pytest.mark.lilypond
def test_dinamicas_e_hairpins(raiz):
    r, _ = raiz
    nomes = [d[0].tag for d in r.iter("dynamics")]
    assert nomes == ["p", "sf"]
    assert contar(r, "wedge", type="crescendo") == 1 and contar(r, "wedge", type="diminuendo") == 1
    assert contar(r, "wedge", type="stop") == 2


@pytest.mark.lilypond
def test_articulacoes_e_ornamentos(raiz):
    r, _ = raiz
    arts = {x.tag for a in r.iter("articulations") for x in a}
    assert {"staccato", "accent", "tenuto"} <= arts
    orn = {x.tag for o in r.iter("ornaments") for x in o}
    assert {"trill-mark", "turn", "mordent", "inverted-mordent"} <= orn
    assert contar(r, "fermata", type="upright") == 1
    assert contar(r, "arpeggiate") >= 1
    assert [f.text for f in r.iter("fingering")] == ["1"]


@pytest.mark.lilypond
def test_ligaduras_de_expressao_e_pedal(raiz):
    r, _ = raiz
    assert contar(r, "slur", type="start") == 2 and contar(r, "slur", type="stop") == 2
    assert contar(r, "pedal", type="start") == 1 and contar(r, "pedal", type="stop") == 1


@pytest.mark.lilypond
def test_andamento_ottava_texto_e_simbolo(raiz):
    r, _ = raiz
    assert [p.text for p in r.iter("per-minute")] == ["120"]
    assert contar(r, "octave-shift", type="down", size="8") == 1
    assert contar(r, "octave-shift", type="stop") == 1
    assert "cresc." in [w.text for w in r.iter("words")]
    # \numericTimeSignature: sem o C.
    assert all(t.get("symbol") is None for t in r.iter("time"))


@pytest.mark.lilypond
def test_c_e_cortado_por_padrao(tmp_path):
    from conversor import pipeline
    ly = tmp_path / "x.ly"
    ly.write_text('\\version "2.26.0"\n\\score { \\new Staff { \\time 4/4 c\'1 \\time 2/2 d\'1 '
                  '\\time 3/4 e\'2. } \\layout { } }\n', encoding="utf-8")
    r = pipeline.converter_peca(ly, tmp_path, tmp_path / "y.musicxml")
    raiz_ = ET.parse(r.gravadas[0].arquivo).getroot()
    assert [t.get("symbol") for t in raiz_.iter("time")] == ["common", "cut", None]


@pytest.mark.lilypond
def test_as_notas_continuam_batendo_com_o_midi(raiz):
    import subprocess, sys
    from conftest import RAIZ
    r = subprocess.run([sys.executable, str(RAIZ / "scripts" / "comparar-midi.py"),
                        str(TESTES_LY / "18-notacao.ly")], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout


def test_leitura_das_linhas_de_notacao(tmp_path):
    import json
    from conversor import eventos
    base = {"p": 1, "voz": 1, "pauta": 1, "t": "0", "g": "0", "c": 1, "pos": "0"}
    linhas = [
        {"tipo": "cabecalho", "formato": 2, "lilypond": "2.26.0"},
        {"tipo": "partitura", "p": 1, "so_midi": False},
        {"tipo": "nota", **base, "altura": {"oitava": 0, "nota": 0, "alt": "0"}, "midi": 60,
         "fig": 2, "pontos": 0, "escala": "1", "dur": "1/4", "lig": False},
        {"tipo": "articulacao", **base, "nome": "staccato"},
        {"tipo": "dedo", **base, "digito": 3},
        {"tipo": "texto", **base, "texto": "dolce"},
        {"tipo": "dinamica", **base, "texto": "mf"},
        {"tipo": "andamento", "p": 1, "t": "0", "texto": "", "bpm": 90,
         "unidade": {"fig": 2, "pontos": 0}},
        {"tipo": "metadados", "p": 1, "campos": {"title": "T"}},
        {"tipo": "fim", "p": 1, "t": "1/4"},
    ]
    caminho = tmp_path / "x.eventos.jsonl"
    caminho.write_text("\n".join(json.dumps(l) for l in linhas), encoding="utf-8")
    p = eventos.ler(caminho)[0]
    a = p.vozes[1].acordes[0]
    assert (a.art, a.dedo, a.textos) == (["staccato"], 3, ["dolce"])
    assert p.marcas[0].tipo == "dinamica" and p.marcas[0].dados["texto"] == "mf"
    assert p.andamentos[0]["bpm"] == 90 and p.metadados == {"title": "T"}
