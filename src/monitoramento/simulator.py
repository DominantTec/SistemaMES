"""
Simulador de produção para as IHMs fantasma (Linha Pintura).

Execute manualmente (fora do Docker):
    cd src/monitoramento
    python simulator.py

Fluxo real da linha (sequencial/paralelo):
  IHM 3 (TRATAMENTO) → IHM 4 (PRIMER) → IHM 5 | IHM 6 (PINTURA, paralelas) → IHM 7 (ESTUFA)

  Cada peça passa obrigatoriamente por TRATAMENTO → PRIMER → uma PINTURA → ESTUFA.
  Se reprovada em qualquer estágio, não avança.

  O rastreamento é feito na tabela tb_op_peca_producao: cada linha é uma peça
  com nu_etapa_atual (estágio atual) e nu_etapa_erro (estágio onde falhou, ou NULL).

Ciclo: CYCLE_SECONDS segundos.
"""

import time
import random
import os
from logger import logger
from database import get_connection_db

# ─── Configuração ─────────────────────────────────────────────────────────────

CYCLE_SECONDS = 5

MACHINE_RATES = {
    3: 620,   # TRATAMENTO 1
    4: 520,   # PRIMER 1
    5: 230,   # PINTURA 1
    6: 230,   # PINTURA 2
    7: 380,   # ESTUFA 1  (terminal)
}

GHOST_IHM_IDS = list(MACHINE_RATES.keys())

# Estágios: cada lista contém as IHMs que processam em paralelo naquele estágio.
# A ORDER dos estágios define o caminho obrigatório de cada peça.
STAGES = [
    [3],     # Estágio 1: TRATAMENTO
    [4],     # Estágio 2: PRIMER
    [5, 6],  # Estágio 3: PINTURA (paralelas)
    [7],     # Estágio 4: ESTUFA (terminal)
]

TERMINAL_STAGE_IDX = len(STAGES) - 1   # índice 0-based do último estágio
N_ETAPAS           = len(STAGES)       # número total de estágios

STATUS_PRODUZINDO = 49
STATUS_PARADA     = 0
STATUS_LIMPEZA    = 4
STATUS_MANUTENCAO = 52

PROB_IR_PARADA     = 0.010
PROB_IR_MANUTENCAO = 0.003
PROB_IR_LIMPEZA    = 0.002

PROB_VOLTA_DE_PARADA     = 0.18
PROB_VOLTA_DE_MANUTENCAO = 0.07
PROB_VOLTA_DE_LIMPEZA    = 0.30

MIN_CICLOS_PARADA     = 2
MIN_CICLOS_MANUTENCAO = 4
MIN_CICLOS_LIMPEZA    = 2

TAXA_REPROVADO      = 0.09
PROB_TROCA_OPERADOR = 0.15


# ─── Acesso à tabela de rastreamento de peças ─────────────────────────────────

def _process_pieces(conn_db, op_id: int, stage_num: int, n_max: int) -> tuple[int, int]:
    """
    Processa até n_max peças na etapa stage_num (1-indexed).
    Retorna (aprovadas, reprovadas).
    """
    cursor = conn_db.cursor()
    cursor.execute(f"""
        SELECT TOP {n_max} id_peca_producao
        FROM dbo.tb_op_peca_producao
        WHERE id_ordem = {op_id}
          AND nu_etapa_atual = {stage_num}
          AND nu_etapa_erro IS NULL
        ORDER BY nu_peca
    """)
    piece_ids = [r[0] for r in cursor.fetchall()]
    if not piece_ids:
        return 0, 0

    approved = []
    rejected = []
    for pid in piece_ids:
        if random.random() < TAXA_REPROVADO:
            rejected.append(pid)
        else:
            approved.append(pid)

    next_stage = stage_num + 1   # stage_num + 1 > N_ETAPAS significa concluída

    if approved:
        ids = ','.join(str(x) for x in approved)
        cursor.execute(f"""
            UPDATE dbo.tb_op_peca_producao
            SET nu_etapa_atual = {next_stage}
            WHERE id_peca_producao IN ({ids})
        """)

    if rejected:
        ids = ','.join(str(x) for x in rejected)
        cursor.execute(f"""
            UPDATE dbo.tb_op_peca_producao
            SET nu_etapa_erro = {stage_num}
            WHERE id_peca_producao IN ({ids})
        """)

    conn_db.commit()
    return len(approved), len(rejected)


def _init_pieces_if_needed(conn_db, op_id: int, quantidade: int) -> bool:
    """
    Garante que as peças da OP existem em tb_op_peca_producao.
    Retorna True se as peças existem (ou foram criadas agora).
    """
    cursor = conn_db.cursor()
    cursor.execute(f"SELECT COUNT(*) FROM dbo.tb_op_peca_producao WHERE id_ordem = {op_id}")
    count = cursor.fetchone()[0]
    if count > 0:
        return True

    logger.info(f"OP {op_id}: inicializando {quantidade} peças no simulador ({N_ETAPAS} etapas)…")
    BATCH = 1000
    for start in range(1, quantidade + 1, BATCH):
        end = min(start + BATCH - 1, quantidade)
        rows = [(op_id, i, N_ETAPAS, 1) for i in range(start, end + 1)]
        cursor.executemany(
            "INSERT INTO dbo.tb_op_peca_producao "
            "(id_ordem, nu_peca, nu_etapas_total, nu_etapa_atual, nu_etapa_erro) "
            "VALUES (?, ?, ?, ?, NULL)",
            rows,
        )
    conn_db.commit()
    logger.info(f"OP {op_id}: {quantidade} peças inicializadas.")
    return True


def _get_n_etapas_op(conn_db, op_id: int) -> int:
    """Lê nu_etapas_total das peças da OP (inserido pela API via rota). Fallback: N_ETAPAS."""
    try:
        cursor = conn_db.cursor()
        cursor.execute(f"""
            SELECT TOP 1 nu_etapas_total
            FROM dbo.tb_op_peca_producao
            WHERE id_ordem = {op_id}
        """)
        row = cursor.fetchone()
        return int(row[0]) if row else N_ETAPAS
    except Exception:
        return N_ETAPAS


def _compute_effective_meta(conn_db, op_id: int, stage_num: int, total_qty: int) -> int:
    """
    Meta efetiva da máquina = peças que chegam nesta etapa.
    = total_qty − peças rejeitadas em etapas ANTERIORES a esta.
    Stage 1 sempre recebe todas as peças.
    """
    if stage_num <= 1:
        return total_qty
    cursor = conn_db.cursor()
    cursor.execute(f"""
        SELECT COUNT(*) FROM dbo.tb_op_peca_producao
        WHERE id_ordem = {op_id}
          AND nu_etapa_erro IS NOT NULL
          AND nu_etapa_erro < {stage_num}
    """)
    rejected_before = cursor.fetchone()[0]
    return max(0, total_qty - rejected_before)


def _pieces_remaining_in_pipeline(conn_db, op_id: int, stage_num: int) -> int:
    """
    Conta peças que ainda podem chegar a esta etapa (sem erro, etapa_atual <= stage_num).
    Quando retorna 0, nenhuma peça nova chegará a este estágio.
    """
    cursor = conn_db.cursor()
    cursor.execute(f"""
        SELECT COUNT(*) FROM dbo.tb_op_peca_producao
        WHERE id_ordem = {op_id}
          AND nu_etapa_atual <= {stage_num}
          AND nu_etapa_erro IS NULL
    """)
    return cursor.fetchone()[0]


def _get_active_op(conn_db) -> tuple[int | None, int]:
    """Retorna (op_id, quantidade) da OP ativa na linha, ou (None, 0)."""
    cursor = conn_db.cursor()
    cursor.execute(f"""
        SELECT TOP 1 o.id_ordem, o.nu_quantidade
        FROM dbo.tb_ordem_producao o
        JOIN dbo.tb_ihm i ON i.id_linha_producao = o.id_linha_producao
        WHERE i.id_ihm = {GHOST_IHM_IDS[0]}
          AND o.tx_status = 'em_producao'
        ORDER BY o.dt_inicio DESC
    """)
    row = cursor.fetchone()
    if row:
        return int(row[0]), int(row[1])
    return None, 0


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
        self.stage_num       = stage_idx + 1   # 1-indexed, igual ao nu_etapa_atual na tabela

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

        self.op_id            = None   # OP ativa conhecida por esta máquina
        self.n_etapas         = N_ETAPAS  # atualizado a cada ciclo com o valor real da rota
        self._produzido_na_op = 0
        self._meta_anterior   = 0
        self._parada_por_meta = False
        self._acum            = 0.0

    @property
    def is_terminal(self) -> bool:
        """Terminal = última etapa da rota ativa (dinâmico, não fixo no STAGES)."""
        return self.n_etapas > 0 and self.stage_num == self.n_etapas

    # ── Carregamento do banco ─────────────────────────────────────────────────

    def load_from_db(self, conn_db):
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
                return

            cursor.execute(f"""
                SELECT nu_valor_bruto
                FROM tb_log_registrador
                WHERE id_ihm = {self.id_ihm} AND dt_created_at = '{row[0]}'
                ORDER BY id_log_registrador ASC
            """)
            vals = [int(r[0]) for r in cursor.fetchall()]
            if len(vals) != 10:
                return

            self.operador, _, self.motivo_parada, \
            self.produzido, self.reprovado, self.total_produzido, \
            self.manutentor, self.engenheiro, _, self.modelo = vals

            self.prev_values = vals[:]
        except Exception as e:
            logger.warning(f"IHM {self.id_ihm}: falha ao restaurar: {e}")

    def refresh_meta(self, conn_db):
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

    def tick(self, conn_db):
        # Máquina além da rota ativa: fica parada sem processar peças
        if self.n_etapas > 0 and self.stage_num > self.n_etapas:
            self._forcar_parada()
            return

        nova_meta = self.meta

        if nova_meta > 0 and self._meta_anterior == 0:
            self._iniciar_nova_op(nova_meta)

        elif self._parada_por_meta and nova_meta != self._meta_anterior and nova_meta > 0:
            logger.info(
                f"IHM {self.id_ihm}: meta mudou {self._meta_anterior} -> {nova_meta} (nova OP), retomando."
            )
            self._iniciar_nova_op(nova_meta)

        elif nova_meta > self._meta_anterior and self._meta_anterior > 0:
            logger.info(f"IHM {self.id_ihm}: meta aumentou {self._meta_anterior} -> {nova_meta}.")
            if self._parada_por_meta:
                self._parada_por_meta = False

        if nova_meta == 0:
            if self._meta_anterior > 0:
                logger.info(f"IHM {self.id_ihm}: meta zerada, OP encerrada.")
                self._produzido_na_op = 0
                self._parada_por_meta = False
                self._acum = 0.0
                self.op_id = None
            self._forcar_parada()
            self._meta_anterior = 0
            return

        if self.is_terminal and not self._parada_por_meta:
            meta_atingida    = self._produzido_na_op >= nova_meta
            pipeline_esgotado = (
                self._produzido_na_op > 0
                and self.op_id is not None
                and _pieces_remaining_in_pipeline(conn_db, self.op_id, self.stage_num) == 0
            )
            if meta_atingida or pipeline_esgotado:
                motivo = "meta atingida" if meta_atingida else "pipeline esgotado (refugos upstream)"
                logger.info(
                    f"IHM {self.id_ihm}: parando — {motivo} "
                    f"({self._produzido_na_op}/{nova_meta})."
                )
                self._parada_por_meta = True

        if self._parada_por_meta:
            self._forcar_parada()
            self._meta_anterior = nova_meta
            return

        if self.status == STATUS_PRODUZINDO:
            self._tick_produzindo(conn_db)
        elif self.status == STATUS_PARADA:
            self._tick_parada()
        elif self.status == STATUS_MANUTENCAO:
            self._tick_manutencao()
        elif self.status == STATUS_LIMPEZA:
            self._tick_limpeza()

        self._meta_anterior = nova_meta

    def _iniciar_nova_op(self, nova_meta: int):
        self._produzido_na_op = 0
        self._parada_por_meta = False
        self._acum = 0.0
        logger.info(f"IHM {self.id_ihm}: nova OP detectada, meta={nova_meta}.")

    def _forcar_parada(self):
        if self.status != STATUS_PARADA:
            self.status         = STATUS_PARADA
            self.motivo_parada  = 0
            self.manutentor     = 0
            self.engenheiro     = 0
            self.parada_duracao = 0

    # ── Transições de estado ──────────────────────────────────────────────────

    def _tick_produzindo(self, conn_db):
        r = random.random()
        if r < PROB_IR_PARADA:
            self._transicao_parada()
        elif r < PROB_IR_PARADA + PROB_IR_MANUTENCAO:
            self._transicao_manutencao()
        elif r < PROB_IR_PARADA + PROB_IR_MANUTENCAO + PROB_IR_LIMPEZA:
            self._transicao_limpeza()
        else:
            self._produzir(conn_db)

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

    def _produzir(self, conn_db):
        if not self.op_id:
            # Sem OP rastreável: apenas avança status, sem registrar peças
            self._transicao_produzindo()
            return

        pct_ciclo = self.pecas_por_hora * CYCLE_SECONDS / 3600.0
        self._acum += pct_ciclo * random.uniform(0.8, 1.2)

        n = int(self._acum)
        if n <= 0:
            return
        self._acum -= n

        if self.is_terminal:
            restante = self.meta - self._produzido_na_op
            n = min(n, max(restante, 0))
            if n <= 0:
                return

        approved, rejected = _process_pieces(conn_db, self.op_id, self.stage_num, n)
        total = approved + rejected
        if total == 0:
            return   # nenhuma peça disponível neste estágio ainda

        self.produzido        += approved
        self.reprovado        += rejected
        self.total_produzido  += total
        self._produzido_na_op += total

    def _transicao_parada(self):
        self.status         = STATUS_PARADA
        self.motivo_parada  = random.choice(self.motivos) if self.motivos else 1
        self.parada_duracao = 0

    def _transicao_manutencao(self):
        self.status         = STATUS_MANUTENCAO
        self.motivo_parada  = 3
        self.manutentor     = random.choice(self.manutentores) if self.manutentores else 1
        self.engenheiro     = random.choice(self.engenheiros)  if self.engenheiros  else 0
        self.parada_duracao = 0

    def _transicao_limpeza(self):
        self.status         = STATUS_LIMPEZA
        self.motivo_parada  = 4
        self.parada_duracao = 0

    def _transicao_produzindo(self):
        self.status         = STATUS_PRODUZINDO
        self.motivo_parada  = 0
        self.manutentor     = 0
        self.engenheiro     = 0
        self.parada_duracao = 0
        if self.operadores and random.random() < PROB_TROCA_OPERADOR:
            self.operador = random.choice(self.operadores)

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


# ─── Persistência de contadores (para OEE) ───────────────────────────────────

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
            f"IHM {machine.id_ihm} (etapa {machine.stage_num}): "
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
    for tentativa in range(1, max_tentativas + 1):
        try:
            conn = get_connection_db()
            logger.info(f"Reconectado ao banco (tentativa {tentativa}).")
            return conn
        except Exception as e:
            espera = min(5 * tentativa, 60)
            logger.warning(f"Falha ao reconectar ({tentativa}): {e}. Aguardando {espera}s…")
            time.sleep(espera)
    logger.error("Não foi possível reconectar.")
    return None


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    while True:
        conn_db = None
        try:
            conn_db = get_connection_db()

            machines = []
            for id_ihm in GHOST_IHM_IDS:
                m = load_machine(id_ihm, conn_db)
                machines.append(m)
                logger.info(f"IHM {id_ihm} carregada: etapa {m.stage_num}, meta={m.meta}")

            logger.info(f"Simulador iniciado — {len(machines)} máquinas, ciclo {CYCLE_SECONDS}s.")

            while True:
                logger.info("=" * 60)

                # Obtém OP ativa e garante que as peças estão inicializadas
                try:
                    op_id, quantidade = _get_active_op(conn_db)
                except Exception as e:
                    logger.warning(f"Erro ao obter OP ativa: {e}")
                    op_id, quantidade = None, 0

                n_etapas = 0
                if op_id:
                    try:
                        _init_pieces_if_needed(conn_db, op_id, quantidade)
                        n_etapas = _get_n_etapas_op(conn_db, op_id)
                    except Exception as e:
                        logger.warning(f"Erro ao inicializar peças da OP {op_id}: {e}")

                if n_etapas > 0:
                    logger.info(f"OP {op_id}: {n_etapas} etapas, {quantidade} peças.")

                # Propaga op_id e n_etapas para todas as máquinas
                for machine in machines:
                    machine.op_id    = op_id
                    machine.n_etapas = n_etapas if n_etapas > 0 else N_ETAPAS

                # Tick em ordem INVERSA de estágio (terminal primeiro).
                # Isso evita que uma peça avançada por um estágio seja imediatamente
                # processada pelo próximo estágio no mesmo ciclo ("cascata").
                machines_rev = sorted(machines, key=lambda m: m.stage_num, reverse=True)
                for machine in machines_rev:
                    # 1. Lê meta base do banco
                    try:
                        machine.refresh_meta(conn_db)
                    except Exception as e:
                        logger.warning(f"IHM {machine.id_ihm}: erro ao ler meta: {e}")
                        conn_db = _reconectar()
                        if conn_db is None:
                            raise RuntimeError("Sem conexão.")
                        try:
                            machine.refresh_meta(conn_db)
                        except Exception:
                            pass

                    # 2. Sobrescreve com meta efetiva (cascata de refugos):
                    #    meta_efetiva[etapa K] = total_qty − refugos_antes_da_etapa_K
                    if (op_id and n_etapas > 0
                            and machine.stage_num <= n_etapas
                            and machine._meta_anterior > 0):
                        try:
                            eff = _compute_effective_meta(
                                conn_db, op_id, machine.stage_num, quantidade
                            )
                            if eff != machine.meta:
                                machine.meta = eff
                        except Exception:
                            pass

                    # 3. Tick (usa machine.meta já corrigido)
                    try:
                        machine.tick(conn_db)
                    except Exception as e:
                        logger.error(f"IHM {machine.id_ihm}: erro no tick: {e}")

                    conn_db = insert_if_changed(machine, conn_db)
                    if conn_db is None:
                        raise RuntimeError("Sem conexão após insert.")

                time.sleep(CYCLE_SECONDS)

        except KeyboardInterrupt:
            logger.info("Simulador encerrado.")
            break
        except Exception as e:
            logger.error(f"SIMULADOR INTERROMPIDO: {e}. Reiniciando em 10s…")
            time.sleep(10)
        finally:
            if conn_db:
                try:
                    conn_db.close()
                except Exception:
                    pass


if __name__ == "__main__":
    main()
