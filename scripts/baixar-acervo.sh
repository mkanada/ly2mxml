#!/usr/bin/env bash
# Baixa o recorte de teste do Mutopia para dados/ (fora do git).
# Uso: scripts/baixar-acervo.sh
# 30 peças de piano solo + LVB_Sonate_02no1_1.ly (referência do plano),
# de épocas e versões variadas (2.6.0 a 2.24.3). Commit fixado para reprodutibilidade.
set -euo pipefail

RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
DESTINO="$RAIZ/dados"
PIN="2144afd6f52d56c5b6995b8b589ef1268b3139f0"  # master em 07/11/2024
BASE="https://raw.githubusercontent.com/MutopiaProject/MutopiaProject/$PIN/ftp"

ARQUIVOS=(
"BeethovenLv/O2/LVB_Sonate_02no1_1/LVB_Sonate_02no1_1.ly"
"BeethovenLv/O49/LVB_Sonate_49no1_1/LVB_Sonate_49no1_1.ly"
"BeethovenLv/WoO59/fur_Elise_WoO59/fur_Elise_WoO59.ly"
"BachJS/BWV772/bach-invention-01/bach-invention-01.ly"
"BachJS/BWV773/bach-invention-02/bach-invention-02.ly"
"BachJS/BWV846/wtk1-prelude1/wtk1-prelude1.ly"
"MozartWA/KV545/K545-1/K545-1.ly"
"MozartWA/KV331/KV331_1_1_tema/KV331_1_1_tema.ly"
"ScarlattiD/K11/sonatensatz/sonatensatz.ly"
"ClementiM/O36/sonatina-1/sonatina-1.ly"
"DiabelliA/O163/diabeli.op163.s1-1/diabeli.op163.s1-1.ly"
"ChopinFF/O28/Chop-28-1/Chop-28-1.ly"
"ChopinFF/O28/Chop-28-2/Chop-28-2.ly"
"ChopinFF/O28/Chop-28-4/Chop-28-4.ly"
"ChopinFF/O9/chopin_nocturne_op9_n2/chopin_nocturne_op9_n2.ly"
"FieldJ/H37/Field_Nocturne_5/Field_Nocturne_5.ly"
"SchumannR/O15/SchumannOp15No07/SchumannOp15No07.ly"
"SchubertF/D899/SchubertF-D899-2-Impromptu/SchubertF-D899-2-Impromptu.ly"
"BrahmsJ/O39/waltz-op39-15/waltz-op39-15.ly"
"BrahmsJ/O118/intermezzo/intermezzo.ly"
"LisztF/S.172/liszt-consolation-no3/liszt-consolation-no3.ly"
"Mendelssohn-BartholdyF/O19/5.Inquietude/5.Inquietude.ly"
"Mendelssohn-BartholdyF/O30/LiederOhneWorte_-_Op30_No6/LiederOhneWorte_-_Op30_No6.ly"
"GriegE/O12/No03_Albumblatt/No03_Albumblatt.ly"
"BurgmullerJFF/O100/25EF-01/25EF-01.ly"
"DebussyC/L66/debussy_Arabesque_1/debussy_Arabesque_1.ly"
"DebussyC/L75/debussy_Ste_Bergamesq_Clair/debussy_Ste_Bergamesq_Clair.ly"
"SatieE/gymnopedie_1/gymnopedie_1.ly"
"SatieE/gymnopedie_2/gymnopedie_2.ly"
"JoplinS/maple/maple.ly"
"BartokB/rom_folk_dance_1_bartok/rom_folk_dance_1_bartok.ly"
)

mkdir -p "$DESTINO"
: > "$DESTINO/MANIFESTO.txt"
echo "# acervo ly2mxml — Mutopia @$PIN" >> "$DESTINO/MANIFESTO.txt"
echo "# baixado em $(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$DESTINO/MANIFESTO.txt"

for rel in "${ARQUIVOS[@]}"; do
  nome="$(basename "$rel")"
  if [[ ! -f "$DESTINO/$nome" ]]; then
    echo "Baixando $nome..."
    curl -fL --progress-bar -o "$DESTINO/$nome" "$BASE/$rel"
  fi
  echo "$rel" >> "$DESTINO/MANIFESTO.txt"
done

echo "OK: $(ls "$DESTINO"/*.ly | wc -l) peças em $DESTINO"
