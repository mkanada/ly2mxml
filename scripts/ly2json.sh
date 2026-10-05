#!/usr/bin/env bash
# Converte um .ly em eventos JSONL (+ MIDI de gabarito) — passo 02.
# Uso: scripts/ly2json.sh ARQ.ly [SAIDA_DIR]
# Saída em SAIDA_DIR (padrão: diretório atual):
#   <base>.eventos.jsonl  — uma linha JSON por evento (ver docs/passos/01-*.md)
#   <base>*.midi          — os MIDI gerados pelo LilyPond, se houver \midi
#   <base>.lilypond.log   — stderr do lilypond (o passo 06 lê dele a ordem dos MIDI)
# O .ly original nunca é alterado: o convert-ly roda sobre uma cópia temporária.
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "uso: $0 ARQ.ly [SAIDA_DIR]" >&2
  exit 1
fi

ARQ="$1"
SAIDA="${2:-.}"

if [[ ! -f "$ARQ" ]]; then
  echo "ly2json: arquivo não encontrado: $ARQ" >&2
  exit 1
fi

RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
LY="$RAIZ/ferramentas/lilypond/bin"
CAPTURA="$RAIZ/ly/captura.ly"

if [[ ! -x "$LY/lilypond" ]]; then
  echo "ly2json: lilypond não encontrado em $LY (rode scripts/instalar-lilypond.sh)" >&2
  exit 1
fi

mkdir -p "$SAIDA"
SAIDA="$(cd "$SAIDA" && pwd)"

BASE="$(basename "$ARQ" .ly)"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# 1. Atualiza a sintaxe para 2.26 numa cópia temporária, sem tocar no original.
# O convert-ly sem -e escreve em stdout.
if ! "$LY/convert-ly" "$ARQ" > "$TMP/$BASE-2.26.ly" 2> "$TMP/convert.log"; then
  echo "ly2json: convert-ly falhou para $ARQ:" >&2
  cat "$TMP/convert.log" >&2
  exit 2
fi

# 2. Envelope: a captura antes do arquivo do usuário. A ordem importa, pois o
# \layout com os engravers precisa existir antes de o .ly ser lido.
cat > "$TMP/envelope.ly" <<EOF
\\version "2.26.0"
\\include "$CAPTURA"
\\include "$TMP/$BASE-2.26.ly"
EOF

# 3. Roda o lilypond sem PDF (-dno-print-pages; -dbackend=null não existe).
# -I com o diretório do original resolve \include relativos, pois a cópia
# convertida está em outro lugar. -o joga os MIDI no temporário.
# Sem "!" no if: com "!" o $? dentro do then seria o da condição negada (0),
# e a falha do lilypond passaria batida. Aqui o $? do else é o do lilypond.
LILY_OK=0
if LY2MXML_EVENTOS="$SAIDA/$BASE.eventos.jsonl" \
  "$LY/lilypond" -dno-print-pages -I "$(dirname "$ARQ")" \
  -o "$TMP/$BASE" "$TMP/envelope.ly" > /dev/null 2> "$TMP/lilypond.log"; then
  LILY_OK=0
else
  LILY_OK=$?
fi

# 4. Copia os MIDI (se houver) e o log para a saída.
for midi in "$TMP/$BASE"*.midi; do
  [[ -e "$midi" ]] || continue
  cp "$midi" "$SAIDA/"
done
cp "$TMP/lilypond.log" "$SAIDA/$BASE.lilypond.log"

# 5. Status: warning não é falha; error é (status 3).
if [[ $LILY_OK -ne 0 ]]; then
  grep -i "error:" "$TMP/lilypond.log" >&2 || cat "$TMP/lilypond.log" >&2
  exit 3
fi
