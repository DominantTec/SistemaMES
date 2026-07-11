# CLP virtual (soft-PLC)

Projeto do **controlador lógico programável** virtual da Tração e Flexão.

Responsabilidade: rodar a lógica do ensaio (Ladder/ST) e **expor os holding registers**
do [`../mapa_registradores.md`](../mapa_registradores.md) via **servidor Modbus TCP**, para
o `src/monitoramento` ler como se fosse a máquina real.

Comportamento a implementar (ROADMAP Fase 1):
- Rampa de força ao longo do deslocamento
- Curva até o ponto de ruptura
- Ruído plausível na leitura
- Estados de máquina (parada, ensaiando, manutenção)

> **Toolchain: Delta.** Projeto do **ISPSoft** (série AS recomendada). O CLP virtual sobe
> pelo **COMMGR** (driver Simulator), que expõe o servidor Modbus TCP. Ver `../README.md`.
