# IHM — Tração e Flexão (projeto DOPSoft do parceiro)

Projeto **real** das telas da IHM da máquina de Tração e Flexão.

## Arquivo

- `Programa maquina de tração e flexão 02.07.2026 - betin.dpa` — projeto DOPSoft (binário).
  Começa com uma imagem BMP embutida (tela de abertura); o resto é comprimido.

## Como rodar em simulação

1. **DOPSoft** → abrir o `.dpa`. Confirmar a **versão do DOPSoft** que abre esse arquivo
   (`.dpa` é DOPSoft 4.x; se não abrir, testar outra versão) → anotar aqui: `__________`.
2. Apontar o controlador das telas para o **CLP virtual** (Modbus TCP, `localhost:502`).
3. Rodar o **simulador** do DOPSoft → operar o ensaio (iniciar/parar, ver força/deslocamento).

Com o simulador do CLP (COMMGR) + o simulador da IHM (DOPSoft) rodando juntos, você tem a
**máquina inteira funcionando no PC** — a mesma coisa que o operador veria no painel real.

## Por que a IHM importa aqui

Cada display/botão da IHM aponta pra um **endereço de registrador**. Cruzar esses endereços com
a tabela de símbolos do CLP confirma o de/para do
[`../mapa_registradores.md`](../mapa_registradores.md) — é a forma de descobrir "o que cada
registrador significa" mesmo sem ler a ladder.

> **Toolchain: Delta.** Ver [`../../README.md`](../../README.md).
