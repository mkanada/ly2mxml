\version "2.26.0"
% Passo 18: slur, frase, dinâmica, hairpin, articulações, dedilhado, ornamentos, pedal, andamento,
% \ottava, texto, \numericTimeSignature.
\header { title = "Notação" composer = "Teste" opus = "Op. 1" }
\score {
  \new PianoStaff <<
    \new Staff = "up" \relative c'' {
      \time 4/4 \numericTimeSignature
      \tempo "Allegro" 4 = 120
      c4-.(\p d-> e--\< f-\fermata\!) |
      g4\prall-1^"cresc." a\mordent b\turn c\trill |
      \ottava #1 c4\( d e f\) \ottava #0 |
      <c e g>4\arpeggio r r2 |
      c1\sf \sustainOn |
      d1 \sustainOff |
      e4 \> f g a\! |
    }
    \new Staff = "down" \relative c {
      \clef bass
      c1 | c | c | c | c | c | c |
    }
  >>
  \layout { }
  \midi { }
}
