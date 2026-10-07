"""Correções de sintaxe que o `convert-ly` não faz, em arquivos antigos do acervo.

Só mexem no que não muda as notas: chamadas de Scheme que a 2.26 removeu (oitava, feixes) e
a ordem das marcas de oitava. Cada regra preserva as linhas do arquivo (a numeração das
mensagens do LilyPond continua valendo) e devolve o nome dela quando dispara, para virar aviso.
"""
import re

# Antes do convert-ly: ele para com "Not smart enough" mesmo diante de um comentário.
ANTES = [
    ("old-relative comentado",
     re.compile(r"^(\s*%+\s*)#\(ly:set-option\s+'old-relative\)", re.M),
     lambda m: m.group(1)),
]

# Depois do convert-ly.
NOTA = r"[a-g](?:is|es|s|f|x|ih|eh|isih|eseh)*"
DEPOIS = [
    # `#(set-octavation 1)` (2.8) virou `\ottava #1`; as alturas dos eventos não mudam.
    ("set-octavation",
     re.compile(r"#\(set-octavation\s+(-?\d+)\)"),
     lambda m: f"\\ottava #{m.group(1)}"),
    # `#(override-auto-beam-setting ...)` (2.8) foi removido; só mudava os feixes.
    ("override-auto-beam-setting",
     re.compile(r"#\(override-auto-beam-setting[^\n]*\)"),
     lambda m: ""),
    # `\applyMusic #unfold-repeats \x` (2.8) virou `\unfoldRepeats \x`.
    ("applyMusic unfold-repeats",
     re.compile(r"\\applyMusic\s+#unfold-repeats"),
     lambda m: "\\unfoldRepeats"),
    # `f8'` (marcas de oitava depois da duração, 2.8) virou `f'8`.
    ("marcas de oitava depois da duração",
     re.compile(rf"(?<![\\\w\"-])({NOTA})(\d+\.*)([',]+)(?![\w])"),
     lambda m: f"{m.group(1)}{m.group(3)}{m.group(2)}"),
]


def _aplicar(texto, regras):
    aplicadas = []
    for nome, padrao, troca in regras:
        texto, n = padrao.subn(troca, texto)
        if n:
            aplicadas.append(f"{nome} (×{n})" if n > 1 else nome)
    return texto, aplicadas


def antes_do_convert(texto):
    """Devolve `(texto, regras aplicadas)`."""
    return _aplicar(texto, ANTES)


def depois_do_convert(texto):
    """Devolve `(texto, regras aplicadas)`."""
    return _aplicar(texto, DEPOIS)
