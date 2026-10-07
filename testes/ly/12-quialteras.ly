\version "2.26.0"
% Passo 12: tercina de colcheias e de semínimas, sextina, \tuplet 3/2 4 com 6 colcheias, tercina
% com pausa, quintina e duas vozes com tercinas diferentes ao mesmo tempo.
\score {
  \new PianoStaff <<
    \new Staff = "up" \relative c'' {
      \time 4/4
      \tuplet 3/2 { c8 d e } \tuplet 3/2 { f4 g a } r4 |
      \tuplet 6/4 { c16 d e f g a } \tuplet 3/2 4 { c8 b a g f e } r4 |
      \tuplet 3/2 { c8 r e } \tuplet 5/4 { f16 g a b c } r2 |
      << { \tuplet 3/2 { c4 d e } r2 } \\ { \tuplet 5/4 { g,8 a b c d } r2 } >> |
    }
    \new Staff = "down" \relative c {
      \clef bass
      c1 | c1 | c1 | c1 |
    }
  >>
  \layout { }
}
