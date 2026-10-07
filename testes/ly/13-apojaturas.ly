\version "2.26.0"
% Passo 13: os seis casos da tabela, mais apojatura em acorde e em duas vozes ao mesmo tempo.
\score {
  \new PianoStaff <<
    \new Staff = "up" \relative c'' {
      \time 4/4
      \grace d8 c4 \acciaccatura e8 d4 \appoggiatura f8 e4 \slashedGrace g8 f4 |
      \grace { a16 b } a4 r2. |
      \afterGrace b2 { c16 d } r2 |
      \grace <c e>8 g'4 << { \acciaccatura a8 b4 } \\ { \acciaccatura d,8 e4 } >> r2 |
      \appoggiatura a8~ a2 r2 |
    }
    \new Staff = "down" \relative c {
      \clef bass
      c1 | c1 | c1 | c1 | c1 |
    }
  >>
  \layout { }
}
