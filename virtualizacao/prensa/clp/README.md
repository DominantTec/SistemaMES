# CLP virtual — Prensa (soft-PLC)

Projeto do **controlador lógico programável** virtual da prensa protótipo.

Responsabilidade: rodar a lógica do ciclo e **expor os holding registers** do
[`../mapa_registradores.md`](../mapa_registradores.md) via **servidor Modbus TCP**, para o
`src/monitoramento` ler como se fosse a máquina real.

## Dois blocos (não misturar)

- **Controlador** — a lógica real: liga/desliga por `comando`, timer de `intervalo_s`,
  dispara o curso, incrementa `contador`, escreve `status`. **Vai pro hardware físico igual.**
- **Planta simulada** — finge os sensores que não existem no virtual: faz `posicao` subir
  0→100→0 a cada curso. **Some na Fase 7**, quando entra o I/O real.

## Como sobe

1. **ISPSoft** (série AS recomendada) → escrever os dois blocos, mapear as grandezas do
   contrato em registradores D acessíveis por Modbus.
2. **COMMGR** → driver **Simulator** → Start → CLP virtual vira servidor Modbus TCP (`localhost:502`).
3. **Teste rápido** com `pymodbus` lendo `status/posicao/contador` antes de tocar no MES.

> **Toolchain: Delta.** Ver `../../README.md` para o loop completo de virtualização.
