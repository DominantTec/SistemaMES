"""
Simulador de produção para as IHMs fantasma (Linha 2 – LINHA PINTURA).

Comportamento orientado a OP:
  - Máquina só produz quando há uma OP ativa (em_producao) na linha.
  - Para quando a meta do turno é atingida (produzido_na_op >= meta).
  - Retoma automaticamente se a meta aumentar (OP paralela adicionada).
  - Se não houver OP ativa: fica PARADA.

Ciclo: CYCLE_SECONDS segundos.
"""

import time
import random
import os
from logger import logger
from database import get_connection_db

# ─── Configuração ─────────────────────────────────────────────────────────────

GHOST_IHM_IDS  = [3, 4, 5, 6, 7]
CYCLE_SECONDS  = 5

STATUS_PRODUZINDO = 49
STATUS_PARADA     = 0
STATUS_LIMPEZA    = 4
STATUS_MANUTENCAO = 52

# Probabilidades de interrupção (apenas quando PRODUZINDO e com OP ativa)
PROB_IR_PARADA     = 0.012   # ~1 parada a cada ~40 min
PROB_IR_MANUTENCAO = 0.004   # ~1 manutenção a cada ~2 h
PROB_IR_LIMPEZA    = 0.002   # ~1 limpeza a cada ~4 h

# Probabilidades de retorno
PROB_VOLTA_DE_PARADA     = 0.12
PROB_VOLTA_DE_MANUTENCAO = 0.05
PROB_VOLTA_DE_LIMPEZA    = 0.25

# Ciclos mínimos em cada estado de interrupção
MIN_CICLOS_PARADA     = 3
MIN_CICLOS_MANUTENCAO = 6
MIN_CICLOS_LIMPEZA    = 2

# Produção por ciclo (em peças aprovadas)
PECAS_POR_CICLO_MIN = 1
PECAS_POR_CICLO_MAX = 4
TAXA_REPROVADO      = 0.03

PROB_TROCA_OPERADOR = 0.15


# ─── Estado de cada máquina ───────────────────────────────────────────────────

class MachineState:
    def __init__(self, id_ihm, reg_ids, operadores, motivos, manutentores, engenheiros, modelos):
        self.id_ihm       = id_ihm
        self.reg_ids      = reg_ids
        self.operadores   = operadores
        self.motivos      = motivos
        self.manutentores = manutentores
        self.engenheiros  = engenheiros
        self.modelos      = modelos

        self.operador        = operadores[0] if operadores else 1
        self.status          = STATUS_PARADA   # inicia parada até ter OP
        self.motivo_parada   = 0
        self.produzido       = 0               # acumulado total (persiste entre ciclos)
        self.reprovado       = 0
        self.total_produzido = 0
        self.manutentor      = 0
        self.engenheiro      = 0
        self.meta            = 0               # meta do turno atual (0 = sem OP)
        self.modelo          = modelos[0] if modelos else 1

        self.parada_duracao  = 0
        self.prev_values     = None

        # Controle interno de produção por período de meta
        self._produzido_na_op   = 0    # produzido desde que a meta atual foi definida
        self._meta_anterior     = 0    # meta na iteração anterior (detecta mudanças)
        self._parada_por_meta   = False  # parou porque atingiu a meta

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

        # Detecta início de novo período de meta (meta foi de 0 para > 0)
        if nova_meta > 0 and self._meta_anterior == 0:
            self._produzido_na_op = 0
            self._parada_por_meta = False
            logger.info(f"IHM {self.id_ihm}: nova OP detectada, meta={nova_meta}. Iniciando produção.")

        # Detecta aumento de meta (OP paralela adicionada)
        elif nova_meta > self._meta_anterior and self._meta_anterior > 0:
            logger.info(f"IHM {self.id_ihm}: meta aumentou {self._meta_anterior} → {nova_meta} (OP paralela).")
            if self._parada_por_meta:
                self._parada_por_meta = False  # retoma produção

        # Meta zerada: OP encerrada/pausada
        if nova_meta == 0:
            if self._meta_anterior > 0:
                logger.info(f"IHM {self.id_ihm}: meta zerada, OP encerrada. Parando.")
                self._produzido_na_op = 0
                self._parada_por_meta = False
            self._forcar_parada()
            self._meta_anterior = 0
            return

        # Meta atingida: fica parada
        if self._produzido_na_op >= nova_meta and not self._parada_por_meta:
            logger.info(f"IHM {self.id_ihm}: meta atingida ({self._produzido_na_op}/{nova_meta}). Parando.")
            self._parada_por_meta = True

        if self._parada_por_meta:
            self._forcar_parada()
            self._meta_anterior = nova_meta
            return

        # Produção normal com interrupções probabilísticas
        if self.status == STATUS_PRODUZINDO:
            self._tick_produzindo()
        elif self.status == STATUS_PARADA:
            self._tick_parada()
        elif self.status == STATUS_MANUTENCAO:
            self._tick_manutencao()
        elif self.status == STATUS_LIMPEZA:
            self._tick_limpeza()

        self._meta_anterior = nova_meta

    def _forcar_parada(self):
        if self.status != STATUS_PARADA:
            self.status        = STATUS_PARADA
            self.motivo_parada = 0
            self.manutentor    = 0
            self.engenheiro    = 0
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
        restante = self.meta - self._produzido_na_op
        n = min(random.randint(PECAS_POR_CICLO_MIN, PECAS_POR_CICLO_MAX), restante)
        if n <= 0:
            return
        reprov = sum(1 for _ in range(n) if random.random() < TAXA_REPROVADO)
        boas   = n - reprov
        self.produzido          += boas
        self.reprovado          += reprov
        self.total_produzido    += n
        self._produzido_na_op   += boas

    def _transicao_parada(self):
        self.status        = STATUS_PARADA
        self.motivo_parada = random.choice(self.motivos) if self.motivos else 1
        self.parada_duracao = 0
        logger.info(f"IHM {self.id_ihm}: → PARADA (motivo={self.motivo_parada})")

    def _transicao_manutencao(self):
        self.status        = STATUS_MANUTENCAO
        self.motivo_parada = 3
        self.manutentor    = random.choice(self.manutentores) if self.manutentores else 1
        self.engenheiro    = random.choice(self.engenheiros)  if self.engenheiros  else 0
        self.parada_duracao = 0
        logger.info(f"IHM {self.id_ihm}: → MANUTENÇÃO")

    def _transicao_limpeza(self):
        self.status        = STATUS_LIMPEZA
        self.motivo_parada = 4
        self.parada_duracao = 0
        logger.info(f"IHM {self.id_ihm}: → LIMPEZA")

    def _transicao_produzindo(self):
        self.status        = STATUS_PRODUZINDO
        self.motivo_parada = 0
        self.manutentor    = 0
        self.engenheiro    = 0
        self.parada_duracao = 0
        if self.operadores and random.random() < PROB_TROCA_OPERADOR:
            self.operador = random.choice(self.operadores)
        logger.info(f"IHM {self.id_ihm}: → PRODUZINDO (op={self.operador})")

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

def load_machine(id_ihm, conn_db):
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

    machine = MachineState(id_ihm, reg_ids, operadores, motivos, manutentores, engenheiros, modelos)
    machine.load_from_db(conn_db)
    machine.refresh_meta(conn_db)

    # Inicia parada — começa a produzir apenas quando houver OP ativa
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
            f"IHM {machine.id_ihm}: status={machine.status} "
            f"prod={machine.produzido} op={machine._produzido_na_op}/{machine.meta}"
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
        try:
            conn_db = get_connection_db()
            logger.info("Reconectado ao banco.")
        except Exception as re:
            logger.error(f"Falha ao reconectar: {re}")

    return conn_db


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    if os.getenv('SIMULADOR_ENABLED', 'true').lower() != 'true':
        logger.info("Simulador desativado (SIMULADOR_ENABLED=false). Encerrando.")
        return

    conn_db = None
    try:
        conn_db = get_connection_db()

        machines = []
        for id_ihm in GHOST_IHM_IDS:
            m = load_machine(id_ihm, conn_db)
            machines.append(m)
            logger.info(f"IHM {id_ihm} carregada: meta={m.meta}, status=PARADA (aguardando OP)")

        logger.info(f"Simulador iniciado — {len(machines)} máquinas, ciclo de {CYCLE_SECONDS}s.")

        while True:
            logger.info("=" * 60)
            for machine in machines:
                machine.refresh_meta(conn_db)
                try:
                    machine.tick()
                except Exception as e:
                    logger.error(f"IHM {machine.id_ihm}: erro no tick: {e}")
                conn_db = insert_if_changed(machine, conn_db)
            time.sleep(CYCLE_SECONDS)

    except Exception as e:
        logger.error(f"SIMULADOR INTERROMPIDO: {e}")
    finally:
        if conn_db:
            conn_db.close()


if __name__ == "__main__":
    main()
