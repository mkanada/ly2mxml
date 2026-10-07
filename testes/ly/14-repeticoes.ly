\version "2.26.0"
% Passo 14: \repeat volta 2 simples; volta 3 com casas 1,2 e 3; \repeat unfold; \repeat percent;
% um tremolo (c4:16) e \repeat tremolo.
\score {
  \new PianoStaff <<
    \new Staff = "up" \relative c'' {
      \time 4/4
      \repeat volta 2 { c4 d e f | }
      \repeat volta 3 { g4 a b c | }
      \alternative { \volta 1,2 { d1 | } \volta 3 { e1 | } }
      \repeat unfold 2 { f4 e d c | }
      \repeat percent 2 { d8 e f g a g f e | }
      c4:16 r2. |
      \repeat tremolo 4 { c16 e } r2 |
    }
    \new Staff = "down" \relative c {
      \clef bass
      c1 | c1 | c1 | c1 | c1 | c1 | c1 | c1 | c1 |
    }
  >>
  \layout { }
  \midi { }
}
