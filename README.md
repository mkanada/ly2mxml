# ly2mxml

Converte partituras do LilyPond (`.ly`) para MusicXML, com foco em piano solo do
[Mutopia](https://www.mutopiaproject.org) e de outros acervos públicos, para tocar e estudar.

O próprio LilyPond interpreta o arquivo e um engraver em Scheme registra cada evento já resolvido
(altura, duração, momento, pauta e voz). Um script Python monta o MusicXML a partir disso. O MIDI
gerado pelo LilyPond serve de gabarito para conferir as notas.

## Documentação

- [Plano](docs/plano.md): objetivo, arquitetura, fases e riscos.
