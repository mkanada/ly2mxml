# 16 — Lote e regressão

Fase 4. Converte o acervo inteiro em paralelo, compara cada partitura com o MIDI e grava um resumo
que serve de teste de regressão: a cada rodada, o script diz o que mudou desde a anterior. É o
ciclo que funcionou no Hymn_Grabber (`scripts/extrair-todos.py`).

## Pré-requisitos

- [10](10-cli.md) e [11](11-comparar-midi.md). Funciona antes dos passos 12–15: as peças que
  dependem deles aparecem como falha, e o resumo mostra a melhora a cada passo.

## Cria

- `scripts/converter-todos.py`.
- `saida/` no `.gitignore`.

## Uso

```
scripts/converter-todos.py                     # tudo de dados/
scripts/converter-todos.py maple fur_Elise_WoO59   # só algumas (pelo nome, sem .ly)
scripts/converter-todos.py -j 4                # 4 peças por vez (padrão: nº de núcleos)
scripts/converter-todos.py --acervo DIR        # outro diretório de .ly (Mutopia inteiro)
```

## O que fazer

### 1. Uma peça

Função `converter(ly: Path) -> (linhas, avisos, erro)`, chamada num `ProcessPoolExecutor` (o
music21 é lento e usa CPU; `ThreadPoolExecutor` não paraleliza o Python):

1. `capturar(ly, tmp, sem_midi=False)` (passo 10), com timeout de 120 s no `subprocess`.
2. Ler, escolher as partituras e montar cada uma em `saida/BASE.musicxml` ou
   `saida/BASE-N.musicxml`, como o CLI.
3. Comparar cada uma com o MIDI (passo 11).
4. Devolver uma linha do resumo por partitura gravada.

Toda exceção vira `status = ERRO` com a última linha do traceback. Uma peça nunca derruba o lote.

### 2. `saida/_resumo.csv`

Uma linha por partitura, ordenada por `peca, p`. Colunas:

| Coluna | Conteúdo |
|---|---|
| `peca` | nome do `.ly` sem extensão |
| `p` | número da partitura (1 se só uma) |
| `versao` | `\version` original |
| `status` | `ok`, `avisos`, `midi-difere`, `ERRO-convert`, `ERRO-lilypond`, `ERRO` |
| `segundos` | tempo total da peça (só informativo: **fora** do hash e da comparação) |
| `compassos`, `pautas`, `vozes` | do MusicXML |
| `notas`, `pausas`, `acordes`, `ligaduras` | do MusicXML |
| `quialteras`, `apojaturas`, `repeticoes`, `casas` | do MusicXML |
| `formula`, `armadura` | valores distintos, na ordem (como no Hymn_Grabber) |
| `midi` | `n/m` notas que batem, ou `não comparado` |
| `avisos` | quantidade |
| `hash` | sha1 (10 primeiros) de altura, duração, voz, pauta e ligadura de cada nota, na ordem |

O `resumir(musicxml)` do Hymn_Grabber (`scripts/extrair-todos.py:45`) serve de base. Aqui ele
precisa ler as `<staff>` e somar as partes.

### 3. `saida/_avisos.log`

Por peça, os avisos do `ly2mxml` e da comparação:

```
== maple (p1) ==
aviso: afterGrace aproximada (c12)
aviso: ligadura sem destino (c40)
```

### 4. O que mudou

Antes de gravar, ler o `_resumo.csv` anterior. Ao final, imprimir:

```
3 de 31 partituras mudaram em relação ao resumo anterior:
  fur_Elise_WoO59 p1: midi 812/830 → 830/830, hash a1b2c3 → d4e5f6
  maple p1: status avisos → ok
  ...
```

Comparar todas as colunas menos `segundos`. Rodando só algumas peças, as linhas das outras são
mantidas (como no Hymn_Grabber).

### 5. Totais

Última linha impressa: `31 peças, 33 partituras: 28 ok, 3 avisos, 1 midi-difere, 1 ERRO-lilypond
(tempo total 54 s)`.

## Pegadinhas

- Peças que o `lilypond` não compila mesmo depois do `convert-ly` entram com `ERRO-lilypond` e as
  linhas `error:` no `_avisos.log`. O plano pede uma lista à parte: é só filtrar o CSV.
- `ProcessPoolExecutor` e music21: importar o music21 dentro da função do trabalhador, para não
  pagar o custo na hora de criar o processo. O primeiro `import music21` leva alguns segundos.
- Decisão: o `_resumo.csv` **é** versionado, ao contrário do resto de `saida/`, porque ele é o
  teste de regressão. Pôr `saida/*` e `!saida/_resumo.csv` no `.gitignore`.
- `--acervo` com o Mutopia inteiro (umas 500 peças de piano): não baixar tudo agora. Isso fica para
  quando o recorte estiver bom. O `scripts/baixar-acervo.sh` pode ganhar uma opção para isso.

## Como verificar

- Rodar duas vezes seguidas: na segunda, `0 de N partituras mudaram`.
- Estragar algo de propósito (por exemplo, desligar as ligaduras na montagem), rodar, ver as
  mudanças listadas e desfazer.

## Pronto quando

- O lote roda nas 31 peças em menos de 2 minutos com `-j` padrão.
- `saida/_resumo.csv` está no git. `docs/plano.md`, Fase 4, tem a taxa de sucesso do recorte.
