\version "2.26.0"
% Passo 03: vozes — acorde, ligaduras, << \\ >>, \new Voice, \change Staff,
% quiáltera, pausa de compasso, pausa, skip e apojaturas.
\score {
  \new PianoStaff <<
    \new Staff = "up" {
      <c' e' g'>4
      <g' b'>2~ q8 r8
      <c''~ e''>2 c''2
      << { d''2 d''2 } \\ { b'2 b'2 } >>
      \new Voice { f''2 f''2 }
      \tuplet 3/2 { a'16 b'16 c''16 }
      R2.*2
      r8 s4
      \grace d''8 e''4
      \acciaccatura e''8 f''4
      \appoggiatura f''8 g''4
      a''2 \change Staff = "down" a''2 \change Staff = "up"
    }
    \new Staff = "down" {
      c2 c2 c2 c2 c2 c2 c2 c2 c2 c2 c2 c2 c2 c2 c2 c2
    }
  >>
  \layout { }
}
