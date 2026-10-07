"""Configuração comum dos testes: caminhos e o pulo dos testes que chamam o LilyPond."""
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
TESTES_LY = RAIZ / "testes" / "ly"
LILYPOND = RAIZ / "ferramentas" / "lilypond" / "bin" / "lilypond"

# Permite `import conversor...` sem instalar o pacote.
sys.path.insert(0, str(RAIZ))


def pytest_collection_modifyitems(config, items):
    if LILYPOND.exists():
        return
    pular = pytest.mark.skip(reason="ferramentas/lilypond não existe")
    for item in items:
        if "lilypond" in item.keywords:
            item.add_marker(pular)
