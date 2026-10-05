#!/usr/bin/env bash
# Baixa o binário oficial do LilyPond para ferramentas/, sem apt e sem sudo.
# Uso: scripts/instalar-lilypond.sh
# Depois: ferramentas/lilypond/bin/lilypond --version
set -euo pipefail

VERSAO=2.26.0
SHA256=cd8a097a9f52cb2b9f4e7914774786f203f4fc61fcd299afcbb63c23fa5c6b24
ARQUIVO="lilypond-$VERSAO-linux-x86_64.tar.gz"
URL="https://gitlab.com/api/v4/projects/lilypond%2Flilypond/packages/generic/lilypond/$VERSAO/$ARQUIVO"

RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
DESTINO="$RAIZ/ferramentas"
LINK="$DESTINO/lilypond"            # aponta para a versão instalada; os scripts usam este caminho

if [[ -x "$DESTINO/lilypond-$VERSAO/bin/lilypond" ]]; then
    ln -sfn "lilypond-$VERSAO" "$LINK"
    echo "LilyPond $VERSAO já está em $DESTINO/lilypond-$VERSAO"
    exit 0
fi

mkdir -p "$DESTINO"
TEMP="$(mktemp -d)"
trap 'rm -rf "$TEMP"' EXIT

echo "Baixando $ARQUIVO..."
curl -fL --progress-bar -o "$TEMP/$ARQUIVO" "$URL"
echo "$SHA256  $TEMP/$ARQUIVO" | sha256sum -c --quiet -

tar xzf "$TEMP/$ARQUIVO" -C "$DESTINO"
ln -sfn "lilypond-$VERSAO" "$LINK"
"$LINK/bin/lilypond" --version | head -1
