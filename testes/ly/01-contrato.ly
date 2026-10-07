\version "2.26.0"
\score {
  \new PianoStaff <<
    \new Staff = "up" \relative c'' { \key g \major \time 3/4 \partial 4 d4 | <g, b>2~ q8 r8 | }
    \new Staff = "down" { \clef bass g4 | g,2. | }
  >>
  \layout { }
}
