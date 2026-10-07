\version "2.26.0"
% Passo 15: anacruse; \partial no meio, antes de uma repetição; measurePosition à mão; cadenza com
% \bar no fim e sem; \set Score.currentBarNumber.
\score {
  \new PianoStaff <<
    \new Staff = "up" \relative c'' {
      \time 2/4
      \partial 4 c4 |
      d4 e | f g |
      \partial 4 a4 |
      b4 c |
      \set Timing.measurePosition = #(ly:make-moment -1/4)
      d4 |
      e4 f |
      \cadenzaOn c4 d e f g \cadenzaOff \bar "|" a2 |
      b4 c |
      \cadenzaOn d4 e f \bar "|" \cadenzaOff
      g4 a |
      \set Score.currentBarNumber = #50
      b4 c |
      d2 |
    }
    \new Staff = "down" \relative c {
      \clef bass
      \time 2/4
      \partial 4 c4 |
      d4 e | f g |
      \partial 4 a4 |
      b4 c |
      \set Timing.measurePosition = #(ly:make-moment -1/4)
      d4 |
      e4 f |
      \cadenzaOn c4 d e f g \cadenzaOff \bar "|" a2 |
      b4 c |
      \cadenzaOn d4 e f \bar "|" \cadenzaOff
      g4 a |
      \set Score.currentBarNumber = #50
      b4 c |
      d2 |
    }
  >>
  \layout { }
  \midi { }
}
