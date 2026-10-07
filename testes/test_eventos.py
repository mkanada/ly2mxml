"""Passo 07: leitura do .eventos.jsonl (sem LilyPond)."""
import json
from fractions import Fraction

import pytest

from conftest import TESTES_LY
from conversor import eventos

CONTRATO = TESTES_LY / "01-contrato.eventos.jsonl"


def jsonl(tmp_path, *linhas):
    caminho = tmp_path / "x.eventos.jsonl"
    caminho.write_text("\n".join(json.dumps(l) for l in linhas) + "\n", encoding="utf-8")
    return caminho


CAB = {"tipo": "cabecalho", "formato": 2, "lilypond": "2.26.0"}


def nota(p=1, voz=1, t="0", midi=60, dur="1/4", lig=False, g="0", pauta=1, c=1, **extra):
    return {"tipo": "nota", "p": p, "voz": voz, "pauta": pauta, "t": t, "g": g, "c": c,
            "pos": "0", "altura": {"oitava": 0, "nota": 0, "alt": "0"}, "midi": midi,
            "fig": 2, "pontos": 0, "escala": "1", "dur": dur, "lig": lig, **extra}


def partitura(p=1, so_midi=False):
    return {"tipo": "partitura", "p": p, "so_midi": so_midi}


def fim(p=1, t="1"):
    return {"tipo": "fim", "p": p, "t": t}


def test_contrato():
    ps = eventos.ler(CONTRATO)
    assert len(ps) == 1
    p = ps[0]
    assert len(p.pautas) == 2 and len(p.vozes) == 2
    # O 1º compasso é a anacruse e o 3º começa em t = fim.
    assert [c.c for c in p.compassos] == [1, 1, 2]  # após o \partial o número não incrementa
    assert p.compassos[0].pos == Fraction(-1, 4)
    assert p.compassos[2].t == p.fim == 1
    acordes = p.vozes[1].acordes
    gb = acordes[1]
    assert [x.midi for x in gb.alturas] == [67, 71]
    assert gb.lig == [True, True] and gb.lig_chega == [False, False]
    q = acordes[2]
    assert q.lig_chega == [True, True] and q.lig == [False, False]
    assert acordes[3].alturas == []          # a pausa
    assert p.avisos == []
    assert not any(pt.temporaria for pt in p.pautas.values())


def test_tempos_sao_fracoes():
    p = eventos.ler(CONTRATO)[0]
    a = p.vozes[1].acordes[0]
    assert isinstance(a.t, Fraction) and isinstance(a.figura.dur, Fraction)
    assert p.claves[1][0].glifo == "clefs.G" and p.armaduras[1][0].alteracoes == [(3, Fraction(1, 2))]
    assert (p.formulas[0].num, p.formulas[0].den) == (3, 4)


def test_escolher_descarta_so_midi(tmp_path):
    c = jsonl(tmp_path, CAB, partitura(1), nota(p=1), fim(1),
              partitura(2, so_midi=True), nota(p=2), fim(2))
    ps = eventos.ler(c)
    assert [p.p for p in eventos.escolher(ps)] == [1]
    c = jsonl(tmp_path, CAB, partitura(1, so_midi=True), nota(p=1), fim(1))
    assert [p.p for p in eventos.escolher(eventos.ler(c))] == [1]


def test_ligadura_sem_destino(tmp_path):
    c = jsonl(tmp_path, CAB, partitura(), nota(t="0", lig=True),
              nota(t="1/4", midi=62), fim())
    p = eventos.ler(c)[0]
    a = p.vozes[1].acordes[0]
    assert a.lig == [False]
    assert any("ligadura sem destino" in x for x in p.avisos)


def test_ligadura_por_cima_de_outras_notas_da_voz(tmp_path):
    # Arpejo: o dó tem a ligadura, as notas seguintes são outras, e o acorde final tem o dó.
    c = jsonl(tmp_path, CAB, partitura(),
              nota(t="0", midi=60, dur="1/8", lig=True),
              nota(t="1/8", midi=64, dur="1/8", lig=True),
              nota(t="1/4", midi=60, dur="1/4"),
              nota(t="1/4", midi=64, dur="1/4"), fim())
    p = eventos.ler(c)[0]
    a = p.vozes[1].acordes
    assert a[2].lig_chega == [True, True]
    assert p.avisos == []


def test_ligadura_nao_atravessa_pausa(tmp_path):
    pausa = {"tipo": "pausa", "p": 1, "voz": 1, "pauta": 1, "t": "1/4", "g": "0", "c": 1,
             "pos": "1/4", "fig": 2, "pontos": 0, "escala": "1", "dur": "1/4"}
    c = jsonl(tmp_path, CAB, partitura(), nota(t="0", lig=True), pausa,
              nota(t="1/2"), fim())
    p = eventos.ler(c)[0]
    assert p.vozes[1].acordes[0].lig == [False]


def test_apojatura_ligada_a_principal(tmp_path):
    c = jsonl(tmp_path, CAB, partitura(),
              nota(t="1/4", g="-1/8", dur="1/8", lig=True),
              nota(t="1/4", g="0"), fim())
    p = eventos.ler(c)[0]
    graca, principal = p.vozes[1].acordes
    assert graca.g == Fraction(-1, 8) and principal.lig_chega == [True]


def test_acorde_com_duracoes_diferentes_separa_e_avisa(tmp_path):
    c = jsonl(tmp_path, CAB, partitura(), nota(midi=60, dur="1/4"),
              nota(midi=64, dur="1/2"), fim())
    p = eventos.ler(c)[0]
    assert len(p.vozes[1].acordes) == 2
    assert any("figuras diferentes" in x for x in p.avisos)


def test_formato_diferente(tmp_path):
    c = jsonl(tmp_path, {"tipo": "cabecalho", "formato": 3, "lilypond": "x"})
    with pytest.raises(eventos.ErroFormato, match="formato 3"):
        eventos.ler(c)


def test_tipo_desconhecido_avisa_uma_vez(tmp_path):
    c = jsonl(tmp_path, CAB, partitura(), {"tipo": "futuro", "p": 1, "t": "0"},
              {"tipo": "futuro", "p": 1, "t": "1/4"}, nota(), fim())
    p = eventos.ler(c)[0]
    assert sum("futuro" in x for x in p.avisos) == 1


def test_pauta_temporaria(tmp_path):
    c = jsonl(tmp_path, CAB, partitura(),
              {"tipo": "pauta", "p": 1, "pauta": 1, "id": "", "contexto": "Staff", "t": "0"},
              {"tipo": "pauta", "p": 1, "pauta": 2, "id": "o", "contexto": "Staff", "t": "1/4"},
              {"tipo": "fim-pauta", "p": 1, "pauta": 2, "t": "1/2"},
              {"tipo": "fim-pauta", "p": 1, "pauta": 1, "t": "1"},
              nota(), fim())
    p = eventos.ler(c)[0]
    assert not p.pautas[1].temporaria and p.pautas[2].temporaria
