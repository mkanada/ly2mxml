# 00 — Convenções

Vale para todos os passos. Não cria nada.

## Layout do repositório

```
ly2mxml.py                 CLI: .ly → .musicxml (passo 10)
conversor/                 pacote Python (não se chama ly2mxml/ para não colidir com ly2mxml.py)
  __init__.py
  eventos.py               leitura do JSON de eventos (passo 07)
  montagem.py              eventos → music21 → MusicXML (passos 08–09, 12–15)
  lilypond.py              chamar convert-ly e lilypond a partir do Python (passo 10)
ly/
  captura.ly               engravers e handlers em Scheme (passos 02–05)
scripts/
  instalar-lilypond.sh     (já existe)
  baixar-acervo.sh         (já existe)
  ly2json.sh               .ly → eventos (passo 02)
  json-vs-midi.py          critério da Fase 1 (passo 06)
  comparar-midi.py         MusicXML contra o MIDI do LilyPond (passo 11)
  converter-todos.py       lote (passo 16)
testes/
  ly/                      trechos .ly mínimos, escritos à mão, um por recurso
  test_*.py                pytest
docs/plano.md, docs/passos/
dados/                     acervo do Mutopia (fora do git)
ferramentas/lilypond/      LilyPond 2.26.0 (fora do git)
saida/                     resultados do lote (fora do git; incluir no .gitignore no passo 16)
```

## Como rodar

- LilyPond: sempre `ferramentas/lilypond/bin/lilypond` e `ferramentas/lilypond/bin/convert-ly`,
  nunca o do sistema. A versão é fixada em 2.26.0.
- Python: sempre `.venv/bin/python`. Ao acrescentar uma dependência (por exemplo `pytest`), fixar
  a versão no `requirements.txt` com a data.
- Opções do `lilypond` na captura: `-dno-print-pages` (sem PDF). **Não usar `-dbackend=null`**:
  ela não existe na 2.26 e é ignorada com aviso.
- Saída intermediária em diretório temporário (`mktemp -d` no shell, `tempfile.TemporaryDirectory`
  no Python). O `.ly` original nunca é alterado.

## Testes

- Cada passo traz um ou mais trechos mínimos em `testes/ly/NN-nome.ly`, com `\version "2.26.0"`,
  de poucos compassos. Eles rodam em menos de 1 s e mostram exatamente o recurso. As peças do
  `dados/` servem para a verificação final de cada passo, não para teste unitário.
- `pytest` em `testes/`. Os testes que chamam o LilyPond são marcados com
  `@pytest.mark.lilypond` e pulados se `ferramentas/lilypond` não existir.

## Estilo

- Código, nomes, mensagens e documentação em português, como o resto do repositório.
- Tempo musical sempre como fração exata: `fractions.Fraction` no Python e racional no Scheme.
  **Nunca float.** No JSON o tempo vai como string `"13/8"` (ver passo 01).
- Unidade de tempo: a **semibreve** (1 = semibreve, `1/4` = semínima), que é a do LilyPond. A
  conversão para `quarterLength` do music21 (× 4) acontece só dentro de `montagem.py`.
- Saída reprodutível: sem data no MusicXML e ids fixos. Rodar duas vezes deve dar arquivos
  idênticos byte a byte.
- Avisos (o que foi ignorado ou aproximado) vão para stderr com o prefixo `aviso:` e, no lote,
  para `saida/_avisos.log`. Não interrompem a conversão.

## Depois de cada passo

- Atualizar a seção da fase em `docs/plano.md` (o que foi feito, o que se descobriu).
- `graft build` para atualizar o grafo do repositório.
