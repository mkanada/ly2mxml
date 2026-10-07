\version "2.26.0"
% Passo 04: pauta e compasso — duas pautas, \partial, \key (g, d, c), \time 3/4 e 6/8,
% \clef bass e treble_8 no meio, repetição com casas, barra final e repeatCommands manual.
\score {
  \new PianoStaff <<
    \new Staff = "up" {
      \key g \major \time 3/4 \partial 4
      g'4 |
      b'2 d''4 |
      \key d \major
      fis''2 a''4 |
      \key c \major
      \clef bass
      c2 e4 |
      \clef "treble_8"
      \time 6/8
      g4. g4. |
      \repeat volta 2 { c'4. c'4. | }
      \alternative { { d'4. d'4. | } { e'4. e'4. | } }
      \set Score.repeatCommands = #'((volta "1.") start-repeat)
      f'4. f'4. |
      \set Score.repeatCommands = #'((volta #f) end-repeat)
      g'4. g'4. |
      \bar "|."
    }
    \new Staff = "down" {
      \clef bass
      g,4 | g,2. | g,2. | g,2. | g,2. |
      c,2. | c,2. | c,2. | c,2. | c,2. | c,2. | c,2. |
    }
  >>
  \layout { }
}
