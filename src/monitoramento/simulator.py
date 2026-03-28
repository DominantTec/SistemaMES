"""
Simulador de produção para as IHMs fantasma (Linha Pintura).

Execute manualmente (fora do Docker):
    cd src/monitoramento
    python simulator.py

Fluxo de linha:
  Estágio 1 (paralelo): IHM 3 | IHM 4  — alimentados pela matéria-prima
  Estágio 2 (paralelo): IHM 5 | IHM 6  — alimentados pelo aprovado do estágio 1
  Estágio 3 (série):    IHM 7           — alimentado pelo aprovado do estágio 2

  Se uma peça for reprovada no estágio 1, ela não chega ao estágio 2.
  O WIP (estoque entre estágios) limita o quanto cada estágio pode produzir.

Taxa de produção:
  - Cada máquina tem sua própria taxa teórica (pç/h) definida em MACHINE_RATES.
  - Um acumulador fracional garante que a produção média respeite a taxa configurada.
  - Variação aleatória de ±20% simula irregularidade real.
  - Paradas aleatórias podem ocorrer e reduzir a produção efetiva.

Ciclo: CYCLE_SECONDS segundos.
"""

import time
import random
import os
from logger import logger
from database import get_connection_db

# ─── Configuração ─────────────────────────────────────────────────────────────

CYCLE_SECONDS = 5

# Taxas teóricas de produção por IHM (peças/hora).
# Estágio 0 (IHM 3+4) produz em torno de 1100 pç/h combinado — suficiente para
# alimentar o estágio 1 (IHM 5+6 ~960 pç/h de demanda) e ainda manter WIP.
MACHINE_RATES = {
    3: 620,   # TRATAMENTO 1
    4: 500,   # PRIMER 1
    5: 480,   # PINTURA 1
    6: 480,   # PINTURA 2
    7: 400,   # ESTUFA 1
}

GHOST_IHM_IDS = list(MACHINE_RATES.keys())

# Fluxo da linha: lista de estágios, cada estágio é uma lista de IHM IDs (paralelas).
STAGES = [
    [3, 4],   # Estágio 1: TRATAMENTO 1 | PRIMER 1  (paralelas, matéria-prima ilimitada)
    [5, 6],   # Estágio 2: PINTURA 1 | PINTURA 2    (paralelas, alimentadas pelo estágio 1)
    [7],      # Estágio 3: ESTUFA 1                 (série, alimentada pelo estágio 2)
]

# WIP: peças aprovadas disponíveis para cada estágio.
# wip[0] = peças aprovadas do estágio 0 disponíveis para o estágio 1.
# wip[1] = peças aprovadas do estágio 1 disponíveis para o estágio 2.
_wip: dict[int, int] = {i: 0 for i in range(len(STAGES))}

# Limite superior do WIP para evitar crescimento ilimitado
WIP_MAX = 500

STATUS_PRODUZINDO = 49
STATUS_PARADA     = 0
STATUS_LIMPEZA    = 4
STATUS_MANUTENCAO = 52

# Probabilidades de interrupção (por ciclo, apenas quando PRODUZINDO com OP ativa)
PROB_IR_PARADA     = 0.010   # ~1 parada a cada ~50 min
PROB_IR_MANUTENCAO = 0.003   # ~1 manutenção a cada ~2.5 h
PROB_IR_LIMPEZA    = 0.002   # ~1 limpeza a cada ~4 h

# Probabilidades de retorno
PROB_VOLTA_DE_PARADA     = 0.18   # retorno mais rápido (~28s em média após min)
PROB_VOLTA_DE_MANUTENCAO = 0.07
PROB_VOLTA_DE_LIMPEZA    = 0.30

# Ciclos mínimos em cada estado de interrupção antes de poder voltar
MIN_CICLOS_PARADA     = 2
MIN_CICLOS_MANUTENCAO = 4
MIN_CICLOS_LIMPEZA    = 2

# Taxa de reprovação por peça (gera refugo e reduz qualidade)
TAXA_REPROVADO      = 0.09   # 9% de reprovação → rendimento ~91% por estágio

PROB_TROCA_OPERADOR = 0.15

# Peças semeadas no WIP[0] quando nova OP é detectada pelas máquinas do estágio 0,
# para evitar starvation inicial nos estágios downstream.
WIP_SEED_NOVA_OP = 30


# ─── Estado de cada máquina ───────────────────────────────────────────────────

class MachineState:
    def __init__(self, id_ihm, pecas_por_hora, reg_ids,
                 operadores, motivos, manutentores, engenheiros, modelos,
                 stage_idx: int = 0):
        self.id_ihm          = id_ihm
        self.pecas_por_hora  = pecas_por_hora
        self.reg_ids         = reg_ids
        self.operadores      = operadores
        self.motivos         = motivos
        self.manutentores    = manutentores
        self.engenheiros     = engenheiros
        self.modelos         = modelos
        self.stage_idx       = stage_idx

        self.operador        = operadores[0] if operadores else 1
        self.status          = STATUS_PARADA
        self.motivo_parada   = 0
        self.produzido       = 0
        self.reprovado       = 0
        self.total_produzido = 0
        self.manutentor      = 0
        self.engenheiro      = 0
        self.meta            = 0
        self.modelo          = modelos[0] if modelos else 1

        self.parada_duracao  = 0
        self.prev_values     = None

        # Controle interno de produção por OP ativa
        self._produzido_na_op = 0
        self._meta_anterior   = 0
        self._parada_por_meta = False

        # Acumulador fracional: garante taxa média correta mesmo com ciclos grossos
        self._acum = 0.0

    # ── Carregamento do banco ─────────────────────────────────────────────────

    def load_from_db(self, conn_db):
        """Restaura o último estado gravado no banco."""
        try:
            cursor = conn_db.cursor()
            cursor.execute(f"""
                SELECT TOP 1 dt_created_at
                FROM tb_log_registrador
                WHERE id_ihm = {self.id_ihm}
                ORDER BY dt_created_at DESC
            """)
            row = cursor.fetchone()
            if not row:
                logger.info(f"IHM {self.id_ihm}: sem histórico, iniciando do zero.")
                return

            cursor.execute(f"""
                SELECT nu_valor_bruto
                FROM tb_log_registrador
                WHERE id_ihm = {self.id_ihm} AND dt_created_at = '{row[0]}'
                ORDER BY id_log_registrador ASC
            """)
            vals = [int(r[0]) for r in cursor.fetchall()]
            if len(vals) != 10:
                logger.warning(f"IHM {self.id_ihm}: snapshot incompleto ({len(vals)} regs), ignorando.")
                return

            self.operador, _, self.motivo_parada, \
            self.produzido, self.reprovado, self.total_produzido, \
            self.manutentor, self.engenheiro, _, self.modelo = vals

            self.prev_values = vals[:]
            logger.info(f"IHM {self.id_ihm}: estado restaurado — prod={self.produzido}")

        except Exception as e:
            logger.warning(f"IHM {self.id_ihm}: falha ao restaurar: {e}")

    def refresh_meta(self, conn_db):
        """Lê a meta mais recente do banco (definida pela OP ativa via API)."""
        try:
            cursor = conn_db.cursor()
            cursor.execute(f"""
                SELECT TOP 1 nu_valor_bruto
                FROM tb_log_registrador
                WHERE id_registrador = (
                    SELECT id_registrador FROM tb_registrador
                    WHERE id_ihm = {self.id_ihm} AND tx_descricao = 'meta'
                )
                ORDER BY dt_created_at DESC
            """)
            row = cursor.fetchone()
            self.meta = int(row[0]) if row else 0
        except Exception as e:
            logger.warning(f"IHM {self.id_ihm}: falha ao ler meta: {e}")

    # ── Lógica principal de tick ──────────────────────────────────────────────

    def tick(self):
        """Avança um ciclo de simulação respeitando a lógica de OP."""
        nova_meta = self.meta

        # ── Transições de OP ─────────────────────────────────────────────────

        # Caso 1: nova OP (meta foi de 0 para > 0)
        if nova_meta > 0 and self._meta_anterior == 0:
            self._iniciar_nova_op(nova_meta)

        # Caso 2: meta mudou enquanto estava em parada por meta (nova OP sem passar por 0)
        # Isso ocorre quando a API finaliza a OP e ativa a próxima quase simultaneamente.
        elif self._parada_por_meta and nova_meta != self._meta_anterior and nova_meta > 0:
            logger.info(
                f"IHM {self.id_ihm}: meta mudou {self._meta_anterior} -> {nova_meta} "
                f"(nova OP sem transição por 0), retomando producao."
            )
            self._iniciar_nova_op(nova_meta)

        # Caso 3: meta aumentou (OP paralela / ajuste de meta)
        elif nova_meta > self._meta_anterior and self._meta_anterior > 0:
            logger.info(f"IHM {self.id_ihm}: meta aumentou {self._meta_anterior} -> {nova_meta}.")
            if self._parada_por_meta:
                self._parada_por_meta = False

        # ── Sem OP ativa ─────────────────────────────────────────────────────
        if nova_meta == 0:
            if self._meta_anterior > 0:
                logger.info(f"IHM {self.id_ihm}: meta zerada, OP encerrada. Parando.")
                self._produzido_na_op = 0
                self._parada_por_meta = False
                self._acum = 0.0
            self._forcar_parada()
            self._meta_anterior = 0
            return

        # ── Meta atingida ─────────────────────────────────────────────────────
        if self._produzido_na_op >= nova_meta and not self._parada_por_meta:
            logger.info(f"IHM {self.id_ihm}: meta atingida ({self._produzido_na_op}/{nova_meta}). Parando.")
            self._parada_por_meta = True

        if self._parada_por_meta:
            self._forcar_parada()
            self._meta_anterior = nova_meta
            return

        # ── Produção normal com interrupções probabilísticas ──────────────────
        if self.status == STATUS_PRODUZINDO:
            self._tick_produzindo()
        elif self.status == STATUS_PARADA:
            self._tick_parada()
        elif self.status == STATUS_MANUTENCAO:
            self._tick_manutencao()
        elif self.status == STATUS_LIMPEZA:
            self._tick_limpeza()

        self._meta_anterior = nova_meta

    def _iniciar_nova_op(self, nova_meta: int):
        """Reseta o estado interno para uma nova OP."""
        self._produzido_na_op = 0
        self._parada_por_meta = False
        self._acum = 0.0
        # Semeia WIP para evitar starvation nos estágios downstream
        if self.stage_idx == 0:
            _wip[0] = max(_wip[0], WIP_SEED_NOVA_OP)
        else:
            # Limpa WIP do estágio anterior para este estágio (fresh start)
            _wip[self.stage_idx - 1] = max(_wip[self.stage_idx - 1], 0)
        logger.info(f"IHM {self.id_ihm}: nova OP detectada, meta={nova_meta}. Iniciando producao.")

    def _forcar_parada(self):
        if self.status != STATUS_PARADA:
            self.status         = STATUS_PARADA
            self.motivo_parada  = 0
            self.manutentor     = 0
            self.engenheiro     = 0
            self.parada_duracao = 0

    # ── Transições de estado (com OP ativa) ──────────────────────────────────

    def _tick_produzindo(self):
        r = random.random()
        if r < PROB_IR_PARADA:
            self._transicao_parada()
        elif r < PROB_IR_PARADA + PROB_IR_MANUTENCAO:
            self._transicao_manutencao()
        elif r < PROB_IR_PARADA + PROB_IR_MANUTENCAO + PROB_IR_LIMPEZA:
            self._transicao_limpeza()
        else:
            self._produzir()

    def _tick_parada(self):
        self.parada_duracao += 1
        if self.parada_duracao >= MIN_CICLOS_PARADA and random.random() < PROB_VOLTA_DE_PARADA:
            self._transicao_produzindo()

    def _tick_manutencao(self):
        self.parada_duracao += 1
        if self.parada_duracao >= MIN_CICLOS_MANUTENCAO and random.random() < PROB_VOLTA_DE_MANUTENCAO:
            self._transicao_produzindo()

    def _tick_limpeza(self):
        self.parada_duracao += 1
        if self.parada_duracao >= MIN_CICLOS_LIMPEZA and random.random() < PROB_VOLTA_DE_LIMPEZA:
            self._transicao_produzindo()

    def _produzir(self):
        """
        Produz peças respeitando a taxa teórica e o WIP disponível do estágio anterior.

        - Estágio 0: alimentado por matéria-prima ilimitada.
        - Demais estágios: só processa o que o estágio anterior aprovou (WIP).
        - Peças aprovadas são somadas ao WIP do próximo estágio (capped em WIP_MAX).
        - Peças reprovadas são descartadas.
        """
        pct_ciclo = self.pecas_por_hora * CYCLE_SECONDS / 3600.0
        self._acum += pct_ciclo * random.uniform(0.8, 1.2)

        n = int(self._acum)
        if n <= 0:
            return
        self._acum -= n

        # Limita ao restante da meta
        restante = self.meta - self._produzido_na_op
        n = min(n, max(restante, 0))
        if n <= 0:
            return

        # Estágios 1+ precisam de WIP do estágio anterior
        if self.stage_idx > 0:
            wip_disponivel = _wip[self.stage_idx - 1]
            n = min(n, wip_disponivel)
            if n <= 0:
                return  # sem insumos, aguarda
            _wip[self.stage_idx - 1] -= n

        reprov = sum(1 for _ in range(n) if random.random() < TAXA_REPROVADO)
        boas   = n - reprov
        self.produzido        += boas
        self.reprovado        += reprov
        self.total_produzido  += n
        self._produzido_na_op += boas

        # Peças aprovadas alimentam o WIP do próximo estágio (com limite superior)
        if boas > 0 and self.stage_idx < len(STAGES) - 1:
            _wip[self.stage_idx] = min(_wip[self.stage_idx] + boas, WIP_MAX)

    def _transicao_parada(self):
        self.status         = STATUS_PARADA
        self.motivo_parada  = random.choice(self.motivos) if self.motivos else 1
        self.parada_duracao = 0
        logger.info(f"IHM {self.id_ihm}: -> PARADA (motivo={self.motivo_parada})")

    def _transicao_manutencao(self):
        self.status         = STATUS_MANUTENCAO
        self.motivo_parada  = 3
        self.manutentor     = random.choice(self.manutentores) if self.manutentores else 1
        self.engenheiro     = random.choice(self.engenheiros)  if self.engenheiros  else 0
        self.parada_duracao = 0
        logger.info(f"IHM {self.id_ihm}: -> MANUTENCAO")

    def _transicao_limpeza(self):
        self.status         = STATUS_LIMPEZA
        self.motivo_parada  = 4
        self.parada_duracao = 0
        logger.info(f"IHM {self.id_ihm}: -> LIMPEZA")

    def _transicao_produzindo(self):
        self.status         = STATUS_PRODUZINDO
        self.motivo_parada  = 0
        self.manutentor     = 0
        self.engenheiro     = 0
        self.parada_duracao = 0
        if self.operadores and random.random() < PROB_TROCA_OPERADOR:
            self.operador = random.choice(self.operadores)
        logger.info(f"IHM {self.id_ihm}: -> PRODUZINDO (op={self.operador})")

    # ── Serialização ─────────────────────────────────────────────────────────

    def current_values(self):
        return [
            self.operador,
            self.status,
            self.motivo_parada,
            self.produzido,
            self.reprovado,
            self.total_produzido,
            self.manutentor,
            self.engenheiro,
            self.meta,
            self.modelo,
        ]

    def build_insert_str(self):
        vals  = self.current_values()
        parts = [f"({self.id_ihm}, {reg_id}, {val})"
                 for reg_id, val in zip(self.reg_ids, vals)]
        return ", ".join(parts)


# ─── Carregamento ─────────────────────────────────────────────────────────────

def _stage_of(id_ihm: int) -> int:
    for idx, stage in enumerate(STAGES):
        if id_ihm in stage:
            return idx
    return 0


def load_machine(id_ihm, conn_db):
    pecas_por_hora = MACHINE_RATES.get(id_ihm, 60)
    stage_idx      = _stage_of(id_ihm)

    cursor = conn_db.cursor()
    cursor.execute(f"SELECT id_registrador FROM tb_registrador WHERE id_ihm = {id_ihm} ORDER BY id_registrador ASC")
    reg_ids = [r[0] for r in cursor.fetchall()]

    cursor.execute(f"SELECT nu_cod_operador      FROM tb_depara_operador      WHERE id_ihm = {id_ihm}")
    operadores = [r[0] for r in cursor.fetchall()]

    cursor.execute(f"SELECT nu_cod_motivo_parada FROM tb_depara_motivo_parada WHERE id_ihm = {id_ihm}")
    motivos = [r[0] for r in cursor.fetchall()]

    cursor.execute(f"SELECT nu_cod_manutentor    FROM tb_depara_manutentor    WHERE id_ihm = {id_ihm}")
    manutentores = [r[0] for r in cursor.fetchall()]

    cursor.execute(f"SELECT nu_cod_engenheiro    FROM tb_depara_engenheiro    WHERE id_ihm = {id_ihm}")
    engenheiros = [r[0] for r in cursor.fetchall()]

    cursor.execute(f"SELECT nu_cod_peca          FROM tb_depara_peca          WHERE id_ihm = {id_ihm}")
    modelos = [r[0] for r in cursor.fetchall()]

    machine = MachineState(id_ihm, pecas_por_hora, reg_ids,
                           operadores, motivos, manutentores, engenheiros, modelos,
                           stage_idx=stage_idx)
    machine.load_from_db(conn_db)
    machine.refresh_meta(conn_db)

    machine.status         = STATUS_PARADA
    machine.motivo_parada  = 0
    machine.manutentor     = 0
    machine.engenheiro     = 0
    machine.parada_duracao = 0

    return machine


# ─── Persistência ─────────────────────────────────────────────────────────────

def insert_if_changed(machine, conn_db):
    curr = machine.current_values()
    if curr == machine.prev_values:
        return conn_db

    insert_sql = f"""
        INSERT INTO tb_log_registrador (id_ihm, id_registrador, nu_valor_bruto)
        VALUES {machine.build_insert_str()}
    """
    try:
        cursor = conn_db.cursor()
        cursor.execute(insert_sql)
        conn_db.commit()
        machine.prev_values = curr[:]
        logger.info(
            f"IHM {machine.id_ihm} ({machine.pecas_por_hora}pç/h): "
            f"status={machine.status} prod={machine.produzido} reprov={machine.reprovado} "
            f"op={machine._produzido_na_op}/{machine.meta}"
        )
    except Exception as e:
        logger.error(f"IHM {machine.id_ihm}: erro ao inserir: {e}")
        try:
            conn_db.rollback()
        except Exception:
            pass
        try:
            conn_db.close()
        except Exception:
            pass
        conn_db = _reconectar()

    return conn_db


def _reconectar(max_tentativas: int = 10) -> object:
    """Tenta reconectar ao banco com backoff, retorna a conexão ou None."""
    for tentativa in range(1, max_tentativas + 1):
        try:
            conn = get_connection_db()
            logger.info(f"Reconectado ao banco (tentativa {tentativa}).")
            return conn
        except Exception as e:
            espera = min(5 * tentativa, 60)
            logger.warning(f"Falha ao reconectar (tentativa {tentativa}): {e}. Aguardando {espera}s...")
            time.sleep(espera)
    logger.error("Não foi possível reconectar ao banco após várias tentativas.")
    return None


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    """Loop principal com reconexão automática em caso de falha."""
    while True:
        conn_db = None
        try:
            conn_db = get_connection_db()

            machines = []
            for id_ihm in GHOST_IHM_IDS:
                m = load_machine(id_ihm, conn_db)
                machines.append(m)
                logger.info(
                    f"IHM {id_ihm} carregada: {m.pecas_por_hora} pç/h, "
                    f"meta={m.meta}, status=PARADA (aguardando OP)"
                )

            logger.info(f"Simulador iniciado — {len(machines)} máquinas, ciclo de {CYCLE_SECONDS}s.")
            logger.info("Taxas configuradas: " + ", ".join(
                f"IHM {iid}={MACHINE_RATES[iid]}pç/h" for iid in GHOST_IHM_IDS
            ))

            while True:
                logger.info("=" * 60)
                wip_log = " | ".join(
                    f"S{i+1}->{i+2}: {_wip[i]}pç" for i in range(len(STAGES) - 1)
                )
                if wip_log:
                    logger.info(f"WIP: {wip_log}")

                for machine in machines:
                    try:
                        machine.refresh_meta(conn_db)
                    except Exception as e:
                        logger.warning(f"IHM {machine.id_ihm}: erro ao ler meta: {e}")
                        conn_db = _reconectar()
                        if conn_db is None:
                            raise RuntimeError("Sem conexão com o banco.")
                        try:
                            machine.refresh_meta(conn_db)
                        except Exception:
                            pass

                    try:
                        machine.tick()
                    except Exception as e:
                        logger.error(f"IHM {machine.id_ihm}: erro no tick: {e}")

                    conn_db = insert_if_changed(machine, conn_db)
                    if conn_db is None:
                        raise RuntimeError("Sem conexão com o banco após insert.")

                time.sleep(CYCLE_SECONDS)

        except KeyboardInterrupt:
            logger.info("Simulador encerrado pelo usuário.")
            break
        except Exception as e:
            logger.error(f"SIMULADOR INTERROMPIDO: {e}. Reiniciando em 10s...")
            time.sleep(10)
        finally:
            if conn_db:
                try:
                    conn_db.close()
                except Exception:
                    pass


if __name__ == "__main__":
    main()
