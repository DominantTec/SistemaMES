# IHM virtual (telas do operador)

Projeto da **interface homem-máquina** virtual da Tração e Flexão.

Responsabilidade: reproduzir as telas que o operador veria no painel físico — login de
operador, iniciar/parar ensaio, definir meta, leitura ao vivo de força/deslocamento — lendo
e escrevendo nos mesmos registradores do [`../mapa_registradores.md`](../mapa_registradores.md).

Quando a IHM física chegar (ROADMAP Fase 7), este mesmo projeto de telas é carregado no painel real.

> **Toolchain: Delta.** Projeto do **DOPSoft** (série DOP). Use o simulador do DOPSoft
> apontando pro CLP virtual do COMMGR via Modbus TCP. Ver `../README.md`.
