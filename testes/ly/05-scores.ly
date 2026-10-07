\version "2.26.0"
% Passo 05: quatro \score no topo — layout, só midi, layout+midi e sem definição de saída.
\score { \new Staff { c'1 } \layout { } }
\score { \new Staff { d'1 } \midi { } }
\score { \new Staff { e'1 } \layout { } \midi { } }
\score { \new Staff { f'1 } }
