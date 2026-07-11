# IHM virtual — Prensa (telas do operador)

Projeto da **interface homem-máquina** virtual da prensa protótipo.

Responsabilidade: reproduzir as telas que o operador veria no painel físico — **iniciar/parar**
(escreve `comando`), **definir o intervalo** (escreve `intervalo_s`) e **leitura ao vivo** de
`status`, `posicao` e `contador` — lendo/escrevendo nos mesmos registradores do
[`../mapa_registradores.md`](../mapa_registradores.md).

Permite operar a prensa para testes **sem ter a IHM física**. Quando o painel real chegar
(Fase 7), este mesmo projeto de telas é carregado nele.

## Como rodar

- **DOPSoft** (série DOP) → desenhar as telas, apontar o controlador para o CLP via Modbus TCP.
- Usar o **simulador** do DOPSoft apontando pro CLP virtual do COMMGR (`localhost:502`).

> **Toolchain: Delta.** Ver `../../README.md`.
