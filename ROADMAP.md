# Roadmap — Evolução do PCP para Plataforma de Máquinas Configuráveis

> Documento vivo. Última atualização: **2026-07-10**.
> Objetivo deste arquivo: manter a memória do que estamos construindo, mesmo que
> o chat/assistente seja reiniciado. Trabalhe em cima dele e vá marcando os `[ ]`.

---

## 🎯 Visão

Transformar o PCP de um sistema fixo em uma **plataforma configurável** onde cada
**tipo de máquina** (ex.: Tração e Flexão, ACM, injetora…) pode ser cadastrado,
adicionado a uma **linha de produção customizável**, e ao abrir uma máquina específica
o usuário vê **tudo** sobre ela: funcionamento em tempo real, configurações,
**digital twin** e **simulação digital**.

A ideia é vender/entregar a plataforma adaptada a cada cliente: se o cliente produz ACM,
ele ganha o tipo "ACM"; se faz ensaios mecânicos, ganha "Tração e Flexão"; etc.

---

## 🧭 Princípios norteadores (as regras que não vamos quebrar)

1. **Digital-first.** Construímos o software inteiro de forma digital, usando
   **simulação**, sem depender do hardware físico. Depois é só "plugar" a parte física.
2. **A simulação e o hardware real compartilham a MESMA interface.** O resto do sistema
   (API, frontend, twin) não sabe nem se importa se o dado veio de um simulador ou de uma
   IHM real. Trocar a fonte não deve exigir reescrever o software.
3. **Construir UM tipo concreto de ponta a ponta antes de generalizar.** Primeiro fazemos a
   máquina de **Tração e Flexão** funcionar 100%. Só depois abstraímos para "tipos de máquina"
   genéricos. Abstrair antes de ter 2–3 exemplos reais é a forma mais comum de errar.
4. **Uma grande mudança de cada vez.** Não misturar a evolução do software com a migração de banco.
5. **Reaproveitar o que já existe:** o sistema de módulos (`MODULES` / `is_enabled()`),
   o `simulator.py`, `@dnd-kit`, `recharts`, o padrão `_ensure_schema()`.

---

## 🔬 Máquina piloto: Tração e Flexão

Primeira máquina do projeto (já existe um sistema desenvolvido para ela). Será a
**cobaia** para desenvolver e validar toda a plataforma de forma digital.

Grandezas típicas a modelar (a detalhar): força (N), deslocamento (mm), curva
força × deslocamento, ponto de ruptura, tensão/deformação, etc.

---

## 🗺️ Ordem de prioridade (resumo)

| Ordem | Bloco | Prioridade |
|------:|-------|------------|
| 1º | **Módulo de Simulação** (máquina digital de Tração e Flexão) | 🔴 Primeiro |
| 2º | Tração e Flexão de ponta a ponta no software (config + telas + KPIs) | 🟠 |
| 3º | "Tipo de Máquina" vira entidade genérica | 🟡 |
| 4º | Config dirigida por esquema + telas genéricas | 🟡 |
| 5º | Construtor de linha de produção configurável | 🟢 |
| 6º | Digital Twin (2D → depois 3D) | 🟢 |
| 7º | Plugar o hardware físico (troca de fonte, sem reescrever) | 🔵 |
| — | **Migração para TimescaleDB** | ⚫ Segundo plano / por último |

---

## 📋 Fases detalhadas

### Fase 1 — Módulo de Simulação (PRIMEIRO) 🔴
Uma camada de simulação que **emula a máquina física** e alimenta o sistema como se fosse real.

- [ ] Definir o "contrato" de dados da máquina de Tração e Flexão (quais grandezas/registros)
- [ ] Criar módulo de simulação ligável via `MODULES` (ex.: `sim`), evoluindo o `simulator.py` existente
- [ ] O simulador grava **nas mesmas tabelas** que a IHM real gravaria → a máquina "existe" sem hardware
- [ ] Simulação com comportamento plausível (ex.: rampa de força, curva até ruptura, ruído)
- [ ] Garantir que a fonte (simulação ↔ real) seja **intercambiável** por configuração

**Resultado:** dá pra desenvolver todo o resto sem ter a máquina em mãos.

### Fase 2 — Tração e Flexão de ponta a ponta 🟠
- [ ] Tela de configuração da máquina
- [ ] Tela de detalhe em tempo real alimentada pela simulação (via WebSocket, como hoje a cada ~2s)
- [ ] KPIs específicos do ensaio (curva força × deslocamento, limite de ruptura, etc.)
- [ ] Validar o ciclo completo: simulação → banco → API → tela

### Fase 3 — "Tipo de Máquina" vira entidade 🟡
Hoje `tipo_maquina` é só um texto (`tx_tipo_maquina NVARCHAR(120)` em `tb_ihm`). Endurecer:

- [ ] `tb_tipo_maquina` (catálogo: id, nome, descrição, ícone)
- [ ] `tb_tipo_maquina_parametro` (parâmetros do tipo: nome, unidade, endereço, min/max, config vs telemetria)
- [ ] `tb_ihm.id_tipo_maquina` (máquina = instância de um tipo; migrar do texto atual)
- [ ] Tela de admin para criar/editar tipos e seus parâmetros
- [ ] Usar o padrão `_ensure_schema()` para as novas colunas/tabelas

### Fase 4 — Config e telas dirigidas por esquema 🟡
- [ ] Tela de configuração da máquina se monta sozinha a partir dos parâmetros do tipo (form dinâmico)
- [ ] `MaquinaDetalhe` renderiza telemetria/KPIs a partir do esquema do tipo
- [ ] Widgets específicos de um tipo entram como componentes "plugáveis"

### Fase 5 — Construtor de linha configurável 🟢
- [ ] Editor visual para montar linhas arrastando instâncias de máquina e ligando o fluxo
- [ ] Evoluir o "mapa de produção / fluxograma" atual de visualização para **edição** (reusa `@dnd-kit`)

### Fase 6 — Digital Twin 🟢
- [ ] Começar em **2D**: esquema/SVG da máquina com pontos animando via telemetria ao vivo
- [ ] Curva/indicadores em tempo real (reusa `recharts`)
- [ ] Só depois avaliar 3D (`react-three-fiber` / `three.js`)
- [ ] O twin funciona igual com dado simulado OU real (por causa do Princípio 2)

### Fase 7 — Plugar o hardware físico 🔵
- [ ] Conectar a IHM/CLP real da máquina de Tração e Flexão (Modbus, via `monitoramento`)
- [ ] Trocar a fonte de dados de "simulação" para "real" — sem reescrever o software
- [ ] Validar paridade simulação × real

---

## ⚫ Segundo plano — Migração para TimescaleDB (POR ÚLTIMO)

Decisão adiada de propósito para não misturar com a evolução do software. Contexto guardado
para o futuro:

- Telemetria (leituras dos sensores) é série temporal clássica → TimescaleDB (PostgreSQL +
  extensão) encaixa: hypertables, compressão (10–20x), continuous aggregates, retention policies.
- Custo real: portar ~125+ construções T-SQL do `_core.py` (`OUTPUT INSERTED` → `RETURNING`,
  `GETDATE()` → `now()`, `ISNULL` → `COALESCE`…), trocar driver (FreeTDS/pyodbc → `psycopg`),
  reescrever `init.sql`.
- Caminho recomendado quando chegar a hora: **telemetria-primeiro (híbrido)** — Timescale só
  para o dado quente, resto no SQL Server, plugando a 2ª conexão na camada `db.py` (SQLAlchemy).

---

## 🔮 Evolução futura — Aposentar a IHM física (DEPOIS DE TUDO, ATÉ DEPOIS DO BANCO)

Ideia guardada para o futuro distante, **só depois** de todo o ecossistema estar rodando e
maduro (simulação → MES → twin → hardware plugado) **e inclusive depois da migração de banco**.

**O quê:** remover a IHM física (DOPSoft) e fazer o **CLP conversar direto com o software**,
que passa a ser o frontend e "vira" a IHM. O contrato continua sendo **Modbus TCP** — o CLP
não sabe se quem lê/escreve os registradores é a IHM Delta ou o nosso software, então a troca
não mexe na ladder.

**Por que vale:** liberdade total de UI (web, multi-tela, gráficos), integração nativa com o
MES/PCP, acesso remoto, log de tudo. Vários cálculos hoje presos na ladder (regressão,
correlação, somatórias) poderiam migrar para o software, mais fácil de evoluir.

**Cuidados inegociáveis (por isso é a última etapa):**
- **Segurança nunca depende do software.** A máquina de Tração e Flexão é uma prensa/ensaio
  → NR-12. Emergência, intertravamento, parada por ruptura: **hardwired ou na lógica do CLP**,
  jamais no frontend. Software = camada **supervisória/operacional**, não de segurança.
- **Tempo real mora no CLP.** O software dá comandos e observa; não entra no loop de timing
  crítico (Modbus TCP tem latência de polling).
- **Disponibilidade:** um PC/rede é ponto de falha novo; se o software cair, a máquina para segura.

---

## 📍 Estado atual & próximo passo

**Onde estamos (2026-07-09):**
- Sistema MES funcionando: FastAPI + React 19 + SQL Server 2022, coletor Modbus (`monitoramento`).
- Sistema de módulos iniciado (`MODULES=base,op,os,alertas`, `is_enabled()`).
- `tipo_maquina` ainda é texto livre em `tb_ihm`.
- Já existe um `simulator.py` (~649 linhas) no `monitoramento` — base para a Fase 1.
- Já existe um sistema desenvolvido para a máquina de Tração e Flexão (a piloto).

**Próximo passo:** iniciar a **Fase 1** — desenhar o contrato de dados da máquina de
Tração e Flexão e montar o módulo de simulação que a emula.

---

## 🧠 Decisões registradas
- Simulação = **primeira** prioridade. Banco = **última**.
- Máquina piloto = **Tração e Flexão**.
- Módulos de simulação servem tanto como **ferramenta de desenvolvimento** (dev sem hardware)
  quanto como **recurso de produto** (demonstrar/vender uma linha antes do hardware existir).
