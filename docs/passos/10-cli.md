# 10 — CLI de ponta a ponta

Fase 2. `ly2mxml.py ARQ.ly [-o SAIDA.musicxml]` faz tudo: `convert-ly`, captura, leitura e
montagem. A partir daqui o `ly2json.sh` vira ferramenta de diagnóstico.

## Pré-requisitos

- [05](05-varios-scores.md) (captura completa) e [09](09-atributos-e-ligaduras.md).

## Cria

- `conversor/lilypond.py`: chamar `convert-ly` e `lilypond` a partir do Python.
- `ly2mxml.py` na raiz.
- `testes/test_cli.py`.

## O que fazer

### 1. `conversor/lilypond.py`

Mesma lógica do `ly2json.sh` (passo 02), em Python, para não depender de bash:

```python
@dataclass
class Captura:
    eventos: Path            # .eventos.jsonl
    midis: list[Path]        # na ordem das partituras (vazio se sem_midi)
    log: str                 # stderr do lilypond
    versao_original: str | None   # do \version do arquivo, antes do convert-ly

def capturar(arq: Path, tmp: Path, sem_midi: bool = False) -> Captura: ...
```

- `RAIZ = Path(__file__).resolve().parent.parent`. Binários em `RAIZ / "ferramentas/lilypond/bin"`.
  Se não existirem, erro claro dizendo para rodar `scripts/instalar-lilypond.sh`.
- `subprocess.run([...], capture_output=True, text=True, env={**os.environ, "LY2MXML_EVENTOS": ...,
  "LY2MXML_SEM_MIDI": "1" if sem_midi else ""})`.
- Ler `\version "x.y.z"` do original com regex antes do `convert-ly`. Vai para os avisos e, no
  lote, para o `_resumo.csv`.
- Ler as linhas `MIDI output to` do log (passo 05) para montar `midis`.
- O envelope e o `.ly` convertido ficam em `tmp`, que é de quem chama.
- Exceções próprias: `ErroConvertLy`, `ErroLilypond`, com as linhas `error:` do log na mensagem.

### 2. `ly2mxml.py`

```
uso: ly2mxml.py ARQ.ly [-o SAIDA] [--manter-temp DIR] [--todas]

  -o SAIDA         arquivo .musicxml (padrão: BASE.musicxml no diretório atual)
  --manter-temp D  grava o .ly convertido, o envelope, o JSON, os MIDI e o log em D
  --todas          converte também as partituras so_midi
```

- **Nome da saída**: padrão `./BASE.musicxml` no diretório atual. Nunca escrever ao lado do
  original sem `-o`, porque `dados/` é o acervo.
- **Várias partituras**: com uma só, `BASE.musicxml`. Com mais de uma, `BASE-1.musicxml`,
  `BASE-2.musicxml`..., numeradas em ordem e **depois** de descartar as `so_midi` (passo 07,
  `escolher`). Com `-o X.musicxml` e várias partituras: `X-1.musicxml`...
- Avisos: `aviso: ...` em stderr, um por linha, sem repetir o mesmo texto (contar: `aviso: ... (×12)`).
- Status: 0 com saída gravada (mesmo com avisos); 2 se o `convert-ly` falhou; 3 se o `lilypond`
  falhou; 4 se não sobrou nenhuma partitura com notas; 1 para erro do programa (traceback).
- Na captura, `sem_midi=True`: o CLI não compara, então não precisa do MIDI. A captura precisa
  respeitar `LY2MXML_SEM_MIDI` (no `captura-preparar` do passo 05, não acrescentar o `\midi`
  quando a variável não for vazia).

### 3. Título

Ainda sem metadados: eles são da fase 5. Deixar o padrão do music21, sem título, e só conferir
que a data não sai (passo 08).

## Pegadinhas

- `subprocess` com `text=True`: o log do LilyPond tem acentos em nomes de arquivo e às vezes
  bytes inválidos. Use `errors="replace"`.
- O LilyPond pode demorar em peças grandes. Sem timeout no CLI, mas com timeout (120 s) no lote.
- Rodar a partir de outro diretório: `ly2mxml.py` resolve `ly/captura.ly` pela `RAIZ`, nunca pelo
  diretório atual.
- Windows não é alvo. Não gastar tempo com caminhos de Windows.

## Como verificar

`testes/test_cli.py` (marcado `lilypond`):

- `ly2mxml.py testes/ly/01-contrato.ly -o $tmp/x.musicxml` → status 0, arquivo existe, o
  `music21.converter.parse` lê.
- `testes/ly/05-scores.ly` → `x-1`, `x-2`, `x-3` (a `so_midi` some).
- Arquivo inexistente → status 2 ou mensagem clara, sem traceback.

À mão: `cd /tmp && ~/IdeaProjects/ly2mxml/.venv/bin/python ~/IdeaProjects/ly2mxml/ly2mxml.py
~/IdeaProjects/ly2mxml/dados/bach-invention-01.ly` grava `/tmp/bach-invention-01.musicxml`.

## Pronto quando

- Os testes passam.
- As 5 peças simples saem e abrem no MuseScore.
- `README.md` da raiz tem a seção "Uso" com o comando e o pré-requisito (`instalar-lilypond.sh`,
  `.venv`).
