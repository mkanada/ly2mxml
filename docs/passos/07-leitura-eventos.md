# 07 — Leitura dos eventos em Python

Fase 2. Transforma o `.eventos.jsonl` em objetos Python prontos para a montagem: tempos como
`Fraction`, acordes já agrupados e ligaduras já resolvidas. É a única parte do Python que conhece o
formato do JSON.

## Pré-requisitos

- [01](01-formato-eventos.md). **Não** depende da captura: pode ser feito em paralelo aos passos
  02–06, usando `testes/ly/01-contrato.eventos.jsonl`.

## Cria

- `conversor/__init__.py` (vazio) e `conversor/eventos.py`.
- `testes/test_eventos.py`.
- `pytest` no `requirements.txt`, com a versão fixada e a data.

## Modelo

Tudo com `@dataclass(slots=True)`. Tempo em `Fraction`, na unidade semibreve.

```python
@dataclass
class Altura:
    oitava: int          # LilyPond: 0 = oitava do c'
    nota: int            # 0 = dó ... 6 = si
    alt: Fraction        # em tons: 1/2 = sustenido
    midi: int

@dataclass
class Figura:
    fig: int             # log: 0 semibreve, 2 semínima, -1 breve
    pontos: int
    escala: Fraction     # 2/3 numa tercina
    dur: Fraction        # duração efetiva

@dataclass
class Acorde:            # também para nota solta (uma altura) e pausa (nenhuma)
    voz: int
    pauta: int           # pauta no momento (segue \change Staff)
    t: Fraction
    g: Fraction          # 0 fora de apojatura
    c: int
    pos: Fraction
    figura: Figura
    alturas: list[Altura]          # vazia = pausa
    lig: list[bool]                # por altura: começa ligadura
    lig_chega: list[bool]          # por altura: termina ligadura (preenchido pela leitura)
    barra: bool = False            # apojatura cortada
    compasso_inteiro: bool = False # pausa-compasso (R)

@dataclass
class Partitura:
    p: int
    so_midi: bool
    fim: Fraction
    pautas: dict[int, Pauta]       # número → Pauta (id, contexto, inicio, fim, temporaria)
    vozes: dict[int, Voz]          # número → Voz (id, pauta de origem, acordes ordenados)
    claves: dict[int, list[Clave]]       # por pauta, em ordem de tempo
    armaduras: dict[int, list[Armadura]] # por pauta
    compassos: list[Compasso]      # c, t, pos, tam, medindo
    formulas: list[Formula]
    barras: list[Barra]
    repeticoes: list[...]          # repeticao, volta, rep-inicio, rep-fim, na ordem
    quialteras: dict[int, list[Quialtera]]  # por voz: inicio, fim, num, den (fim pode faltar)
    avisos: list[str]
```

## O que fazer

1. `ler(caminho) -> list[Partitura]`: lê linha a linha com `json.loads`. Confere o `formato` do
   cabeçalho e falha com mensagem clara se for diferente do esperado.
2. Converte `t`, `g`, `pos`, `dur`, `escala`, `alt` com `Fraction(str)`.
3. **Acordes**: agrupa as linhas `nota` por `(p, voz, t, g)`. Todas do grupo têm de ter a mesma
   `figura` e a mesma `pauta`. Se não tiverem (acorde com durações diferentes, que o LilyPond
   permite: `<c4 e2>`), separar em acordes por figura e emitir aviso. Ordenar as alturas pelo
   `midi`.
4. **Ligaduras**: para cada acorde, cada altura com `lig` procura, na **mesma voz**, o próximo
   acorde que começa em `t + dur` com `g = 0` e tem a mesma altura (`midi`). Marca `lig_chega`
   nela. Se não achar, desmarca `lig` e avisa `ligadura sem destino (c=..)`. A ligadura atravessa
   `\change Staff` sem problema: a busca é pela voz.
5. **Vozes**: ordena os acordes de cada voz por `(t, g)`. Descarta a voz que não tem nenhum acorde
   (só `s`).
6. **Pautas temporárias**: `temporaria = fim < partitura.fim or inicio > 0`.
7. `escolher(partituras) -> list[Partitura]`: devolve as que não são `so_midi`; se todas forem,
   devolve todas.
8. Avisos da captura (`tipo: aviso`) vão para `Partitura.avisos`. A leitura não imprime nada. Quem
   chama decide.

## Pegadinhas

- `Fraction("-1/16")` funciona. `Fraction("1/2 ")` não: não aceite espaço no JSON.
- `json.loads` dá `int` para `c`, `voz`, `fig`. Não converta tempos de `int` sem passar por
  `Fraction`.
- A apojatura não participa da busca de ligadura como destino de nota principal, mas pode ter
  ligadura para a nota principal (`\grace c8~ c4`): procure o destino também em `t` com `g = 0`
  quando a origem é apojatura e `t + g + dur ≥ t`. Raro. Se der trabalho, avisar e seguir.
- Linhas de tipo desconhecido: ignorar com um aviso, uma vez por tipo. Assim a captura pode
  ganhar linhas novas (fase 5) sem quebrar a leitura.

## Como verificar

`testes/test_eventos.py`, sem LilyPond:

- `01-contrato.eventos.jsonl` dá 1 partitura, 2 pautas, 2 vozes, 3 `compassos` (o 1 é a
  anacruse; o 3 começa em `t = fim` e fica vazio, e quem o descarta é a montagem), o acorde `<g b>2~` com `lig = [True, True]` e o `q8` seguinte com
  `lig_chega = [True, True]`.
- Um JSON escrito à mão com `so_midi` misturado: `escolher` devolve só as certas.
- Um JSON com ligadura sem destino: aviso, e `lig` falso.
- Um `formato: 2`: erro claro.

## Pronto quando

- `.venv/bin/pytest testes/test_eventos.py` passa.
- `ler` roda nos JSON das 31 peças (gerados pelo `ly2json.sh`) sem exceção.
