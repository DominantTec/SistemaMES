"""
Simulador de produção para as IHMs fantasma (Linha 2 – LINHA_SIMULADA).

Simula inserções em tb_log_registrador exatamente como o monitoramento real,
mas sem conexão Modbus: os valores são gerados por lógica probabilística
que reproduz situações reais de chão de fábrica.

IHMs simuladas: 3, 4, 5, 6, 7 (SIM_01 a SIM_05)

Ciclo padrão: 30 segundos
Só insere no banco quando os valores mudam (mesmo comportamento do data_processor.py)
"""

import time
import random
import os
from logger import logger
from database import get_connection_db

# ─── Configurações ────────────────────────────────────────────────────────────

GHOST_IHM_IDS = [3, 4, 5, 6, 7]
CYCLE_SECONDS  = 5

# Códigos de status_maquina (espelham os valores reais da IHM)
STATUS_PRODUZINDO = 49
STATUS_PARADA     = 0
STATUS_LIMPEZA    = 4
STATUS_MANUTENCAO = 52

# Probabilidades de transição por ciclo (enquanto PRODUZINDO)
PROB_IR_PARADA     = 0.015   # ~1 parada a cada ~33 min
PROB_IR_MANUTENCAO = 0.005   # ~1 manutenção a cada ~1.5 h
PROB_IR_LIMPEZA    = 0.003   # ~1 limpeza a cada ~2.5 h

# Probabilidades de retorno (por ciclo, após tempo mínimo)
PROB_VOLTA_DE_PARADA     = 0.10  # parada dura em média ~5 min (3 ciclos mín.)
PROB_VOLTA_DE_MANUTENCAO = 0.04  # manutenção dura em média ~12 min (6 ciclos mín.)
PROB_VOLTA_DE_LIMPEZA    = 0.20  # limpeza dura em média ~3 min (2 ciclos mín.)

# Ciclos mínimos antes de poder sair do estado de parada
MIN_CICLOS_PARADA     = 3
MIN_CICLOS_MANUTENCAO = 6
MIN_CICLOS_LIMPEZA    = 2

# Produção
PECAS_POR_CICLO_MIN  = 1
PECAS_POR_CICLO_MAX  = 4
TAXA_REPROVADO       = 0.03   # 3% de rejeição por peça
PROB_TROCA_OPERADOR  = 0.15   # chance de trocar operador ao voltar a produzir


# ─── Estado de cada máquina ───────────────────────────────────────────────────

class MachineState:
    def __init__(self, id_ihm, reg_ids, operadores, motivos, manutentores, engenheiros, modelos):
        self.id_ihm       = id_ihm
        self.reg_ids      = reg_ids       # [id_registrador] ordenado por id ASC
        self.operadores   = operadores    # [nu_cod_operador]
        self.motivos      = motivos       # [nu_cod_motivo_parada]
        self.manutentores = manutentores  # [nu_cod_manutentor]
        self.engenheiros  = engenheiros   # [nu_cod_engenheiro]
        self.modelos      = modelos       # [nu_cod_peca]

        # Valores correntes (ordem idêntica à dos registradores no banco)
        self.operador        = operadores[0] if operadores else 1
        self.status          = STATUS_PRODUZINDO
        self.motivo_parada   = 0
        self.produzido       = 0
        self.reprovado       = 0
        self.total_produzido = 0
        self.manutentor      = 0
        self.engenheiro      = 0
        self.meta            = 1000
        self.modelo          = modelos[0] if modelos else 1

        self.parada_duracao = 0   # contagem de ciclos no estado atual de parada
        self.prev_values    = None

    def load_from_db(self, conn_db):
        """Restaura o último estado gravado no banco para continuar de onde parou."""
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
                logger.info(f"IHM {self.id_ihm}: sem histórico no banco, iniciando do zero.")
                return

            cursor.execute(f"""
                SELECT nu_valor_bruto
                FROM tb_log_registrador
                WHERE id_ihm = {self.id_ihm} AND dt_created_at = '{row[0]}'
                ORDER BY id_log_registrador ASC
            """)
            vals = [int(r[0]) for r in cursor.fetchall()]

            if len(vals) != 10:
                logger.warning(f"IHM {self.id_ihm}: snapshot com {len(vals)} registradores (esperado 10), ignorando.")
                return

            self.operador, self.status, self.motivo_parada, \
            self.produzido, self.reprovado, self.total_produzido, \
            self.manutentor, self.engenheiro, _, _ = vals
            # meta e modelo não são restaurados do banco — sempre usam o valor
            # configurado no simulador para evitar herdar valores antigos ou reais

            self.prev_values = vals[:]
            logger.info(f"IHM {self.id_ihm}: estado restaurado — status={self.status}, prod={self.produzido}")

        except Exception as e:
            logger.warning(f"IHM {self.id_ihm}: falha ao restaurar estado do banco: {e}")

    # ── Lógica de simulação ──────────────────────────────────────────────────

    def tick(self):
        """Avança um ciclo de simulação."""
        if self.status == STATUS_PRODUZINDO:
            self._tick_produzindo()
        elif self.status == STATUS_PARADA:
            self._tick_parada()
        elif self.status == STATUS_MANUTENCAO:
            self._tick_manutencao()
        elif self.status == STATUS_LIMPEZA:
            self._tick_limpeza()

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
        n = random.randint(PECAS_POR_CICLO_MIN, PECAS_POR_CICLO_MAX)
        reprov = sum(1 for _ in range(n) if random.random() < TAXA_REPROVADO)
        self.produzido       += n - reprov
        self.reprovado       += reprov
        self.total_produzido += n

    def _transicao_parada(self):
        self.status        = STATUS_PARADA
        self.motivo_parada = random.choice(self.motivos) if self.motivos else 1
        self.parada_duracao = 0
        logger.info(f"IHM {self.id_ihm}: → PARADA (motivo={self.motivo_parada})")

    def _transicao_manutencao(self):
        self.status        = STATUS_MANUTENCAO
        self.motivo_parada = 3  # Manutenção Preventiva
        self.manutentor    = random.choice(self.manutentores) if self.manutentores else 1
        self.engenheiro    = random.choice(self.engenheiros)  if self.engenheiros  else 0
        self.parada_duracao = 0
        logger.info(f"IHM {self.id_ihm}: → MANUTENÇÃO (manut={self.manutentor})")

    def _transicao_limpeza(self):
        self.status        = STATUS_LIMPEZA
        self.motivo_parada = 4  # Limpeza programada
        self.parada_duracao = 0
        logger.info(f"IHM {self.id_ihm}: → LIMPEZA")

    def _transicao_produzindo(self):
        self.status        = STATUS_PRODUZINDO
        self.motivo_parada = 0
        self.manutentor    = 0
        self.engenheiro    = 0
        self.parada_duracao = 0
        # Rodízio de operador ao retornar
        if self.operadores and random.random() < PROB_TROCA_OPERADOR:
            self.operador = random.choice(self.operadores)
        logger.info(f"IHM {self.id_ihm}: → PRODUZINDO (op={self.operador})")

    # ── Serialização para o banco ────────────────────────────────────────────

    def current_values(self):
        """Retorna lista de valores na mesma ordem dos registradores (por id ASC)."""
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
        """Monta o trecho VALUES do INSERT (mesmo formato do data_processor.py)."""
        vals  = self.current_values()
        parts = [f"({self.id_ihm}, {reg_id}, {val})"
                 for reg_id, val in zip(self.reg_ids, vals)]
        return ", ".join(parts)


# ─── Carregamento e persistência ──────────────────────────────────────────────

def load_machine(id_ihm, conn_db):
    """Cria um MachineState carregando metadados e último estado do banco."""
    cursor = conn_db.cursor()

    cursor.execute(f"""
        SELECT id_registrador
        FROM tb_registrador
        WHERE id_ihm = {id_ihm}
        ORDER BY id_registrador ASC
    """)
    reg_ids = [r[0] for r in cursor.fetchall()]

    cursor.execute(f"SELECT nu_cod_operador       FROM tb_depara_operador       WHERE id_ihm = {id_ihm}")
    operadores = [r[0] for r in cursor.fetchall()]

    cursor.execute(f"SELECT nu_cod_motivo_parada  FROM tb_depara_motivo_parada  WHERE id_ihm = {id_ihm}")
    motivos = [r[0] for r in cursor.fetchall()]

    cursor.execute(f"SELECT nu_cod_manutentor     FROM tb_depara_manutentor     WHERE id_ihm = {id_ihm}")
    manutentores = [r[0] for r in cursor.fetchall()]

    cursor.execute(f"SELECT nu_cod_engenheiro     FROM tb_depara_engenheiro     WHERE id_ihm = {id_ihm}")
    engenheiros = [r[0] for r in cursor.fetchall()]

    cursor.execute(f"SELECT nu_cod_peca           FROM tb_depara_peca           WHERE id_ihm = {id_ihm}")
    modelos = [r[0] for r in cursor.fetchall()]

    machine = MachineState(id_ihm, reg_ids, operadores, motivos, manutentores, engenheiros, modelos)
    machine.load_from_db(conn_db)

    # Sempre inicia produzindo; as aleatoriedades começam a partir do primeiro ciclo
    machine.status        = STATUS_PRODUZINDO
    machine.motivo_parada = 0
    machine.manutentor    = 0
    machine.engenheiro    = 0
    machine.parada_duracao = 0

    return machine


def insert_if_changed(machine, conn_db):
    """Insere snapshot no banco somente se os valores mudaram desde o último insert."""
    curr = machine.current_values()

    if curr == machine.prev_values:
        logger.info(f"IHM {machine.id_ihm}: sem alteração — registro ignorado.")
        return

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
            f"IHM {machine.id_ihm}: inserido — "
            f"status={machine.status} prod={machine.produzido} "
            f"reprov={machine.reprovado} total={machine.total_produzido}"
        )
    except Exception as e:
        logger.error(f"IHM {machine.id_ihm}: erro ao inserir no banco: {e}")


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
            logger.info(f"IHM {id_ihm} carregada: {len(m.reg_ids)} registradores, "
                        f"status inicial={m.status}")

        logger.info(
            f"Simulador iniciado — {len(machines)} máquinas fantasma, "
            f"ciclo de {CYCLE_SECONDS}s."
        )

        while True:
            logger.info("=" * 60)
            for machine in machines:
                machine.tick()
                insert_if_changed(machine, conn_db)
            time.sleep(CYCLE_SECONDS)

    except Exception as e:
        logger.error(f"SIMULADOR INTERROMPIDO: {e}")
    finally:
        if conn_db:
            conn_db.close()


if __name__ == "__main__":
    main()
