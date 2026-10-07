\version "2.26.0"
% Passo 05: um \score no topo e um \book com 3 \score (só midi; layout+midi; sem definição).
\score { \new Staff { c'1 } \layout { } }
\book {
  \score { \new Staff { d'1 } \midi { } }
  \score { \new Staff { e'1 } \layout { } \midi { } }
  \score { \new Staff { f'1 } }
}
