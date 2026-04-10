"""
Simulador de operadores para as IHMs fantasma (Linha Pintura).

Representa um operador por máquina. Cada operador produz peças, pode reprovar
peças defeituosas, e tem paradas aleatórias (parada, manutenção, limpeza).

Regra de linha: toda peça percorre as etapas em ordem sequencial.
Uma peça só chega à etapa N se foi aprovada em todas as anteriores.

IMPORTANTE: o simulador NÃO gerencia metas. Metas são responsabilidade exclusiva
da API/MES via _recalcular_metas_linha. Ao desligar o simulador, o MES continua
funcionando normalmente — apenas sem atualização de produção em tempo real.

Execute:
    cd src/monitoramento
    python simulator.py
"""

import time
import random
from logger import logger
from database import get_connection_db

# ─── Configuração da linha ─────────────────────────────────────────────────────

CYCLE_SECONDS = 5

# Sequência de etapas. Cada sublista tem as IHMs paralelas no mesmo estágio.
STAGES = [
    [3],     # Etapa 1 — TRATAMENTO
    [4],     # Etapa 2 — PRIMER
    [5, 6],  # Etapa 3 — PINTURA (paralelas)
    [7],     # Etapa 4 — ESTUFA
]

N_ETAPAS      = len(STAGES)
GHOST_IHM_IDS = [ihm for stage in STAGES for ihm in stage]

# Peças produzidas por hora por máquina
MACHINE_RATES = {3: 620, 4: 520, 5: 230, 6: 230, 7: 380}

# Um operador fixo por máquina — código numérico + nome exibido no MES
OPERATORS = {
    3: {"cod": 1, "nome": "Carlos Silva"},
    4: {"cod": 2, "nome": "Ana Souza"},
    5: {"cod": 3, "nome": "João Pereira"},
    6: {"cod": 4, "nome": "Marcos Oliveira"},
    7: {"cod": 5, "nome": "Fernanda Costa"},
}

# ─── Status de máquina ─────────────────────────────────────────────────────────

STATUS_PRODUZINDO    = 49
STATUS_PARADA        = 0
STATUS_LIMPEZA       = 4
STATUS_AG_MANUTENCAO = 51   # Aguardando Manutentor (permanente)
STATUS_MANUTENCAO    = 52   # Em Manutenção (transitório — aguarda motivo)

PROB_IR_PARADA           = 0.010
PROB_IR_MANUTENCAO       = 0.003
PROB_IR_LIMPEZA          = 0.002
PROB_VOLTA_DE_PARADA     = 0.18
PROB_VOLTA_DE_MANUTENCAO = 0.07
PROB_VOLTA_DE_LIMPEZA    = 0.30
MIN_CICLOS_PARADA        = 2
MIN_CICLOS_MANUTENCAO    = 4   # min ciclos em STATUS_MANUTENCAO antes de liberar
MIN_CICLOS_LIMPEZA       = 2

# Delay para o operador informar o motivo de parada (fluxo real assíncrono):
# 49 → 0 (sem motivo) → [delay] → motivo (1-32) → 49
MIN_CICLOS_MOTIVO_DELAY  = 1   # 1 ciclo  ≈  5 segundos
MAX_CICLOS_MOTIVO_DELAY  = 6   # 6 ciclos ≈ 30 segundos

# Delay para o manutentor chegar (fluxo manutenção):
# 49 → 51 (Ag. Manutentor) → [delay] → 52 (Em Manutenção) → [delay] → motivo → 49
MIN_CICLOS_AG_MANUTENCAO    = 2   # ciclos aguardando manutentor chegar
MAX_CICLOS_AG_MANUTENCAO    = 8
MAX_CICLOS_MANUTENCAO_DELAY = 4   # ciclos após 52 para registrar o motivo

TAXA_REPROVADO = 0.09


# ─── Acesso ao rastreamento de peças ──────────────────────────────────────────

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

    next_stage = stage_num + 1   # > N_ETAPAS significa concluída

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


def _init_pieces_if_needed(conn_db, op_id: int, quantidade: int) -> None:
    """Garante que as peças da OP existem em tb_op_peca_producao."""
    cursor = conn_db.cursor()
    cursor.execute(f"SELECT COUNT(*) FROM dbo.tb_op_peca_producao WHERE id_ordem = {op_id}")
    if cursor.fetchone()[0] > 0:
        return

    logger.info(f"OP {op_id}: inicializando {quantidade} peças ({N_ETAPAS} etapas)…")
    BATCH = 1000
    for start in range(1, quantidade + 1, BATCH):
        end  = min(start + BATCH - 1, quantidade)
        rows = [(op_id, i, N_ETAPAS, 1) for i in range(start, end + 1)]
        cursor.executemany(
            "INSERT INTO dbo.tb_op_peca_producao "
            "(id_ordem, nu_peca, nu_etapas_total, nu_etapa_atual, nu_etapa_erro) "
            "VALUES (?, ?, ?, ?, NULL)",
            rows,
        )
    conn_db.commit()
    logger.info(f"OP {op_id}: {quantidade} peças inicializadas.")


def _get_n_etapas_op(conn_db, op_id: int) -> int:
    """Lê nu_etapas_total das peças da OP. Fallback: N_ETAPAS."""
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


def _get_active_op(conn_db) -> tuple[int | None, int]:
    """Retorna (op_id, quantidade) da OP em_producao da linha, ou (None, 0)."""
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
    return (int(row[0]), int(row[1])) if row else (None, 0)


# ─── Estado de cada operador/máquina ──────────────────────────────────────────

class MachineState:
    """Estado de um operador em sua máquina na linha de produção."""

    def __init__(self, id_ihm: int, stage_idx: int, pecas_por_hora: int,
                 reg_ids: list, operador_cod: int,
                 motivos: list, manutentores: list, engenheiros: list, modelos: list):
        self.id_ihm          = id_ihm
        self.stage_num       = stage_idx + 1   # 1-indexed (= nu_etapa_atual no banco)
        self.pecas_por_hora  = pecas_por_hora
        self.reg_ids         = reg_ids

        self.operador        = operador_cod    # código fixo por máquina
        self.motivos         = motivos
        self.manutentores    = manutentores
        self.engenheiros     = engenheiros
        self.modelos         = modelos

        self.status          = STATUS_PARADA
        self.motivo_parada   = 0
        self.produzido       = 0
        self.reprovado       = 0
        self.total_produzido = 0
        self.manutentor      = 0
        self.engenheiro      = 0
        self.modelo          = modelos[0] if modelos else 1

        self.parada_duracao  = 0
        self.prev_values     = None

        self._acum                       = 0.0  # acumulador fracionário de peças por ciclo
        self._motivo_pendente            = 0    # motivo operacional, aguardando ser revelado
        self._ciclos_motivo_delay        = 0    # ciclos restantes até revelar motivo operacional
        self._ciclos_ag_manutencao       = 0    # ciclos restantes aguardando manutentor chegar
        self._motivo_manutencao_pendente = 0    # motivo de manutenção, revelado após delay
        self._ciclos_manutencao_delay    = 0    # ciclos restantes até revelar motivo de manutenção
        self._op_id_atual                = None  # detecta troca de OP

    def load_from_db(self, conn_db):
        """Restaura contadores de produção do último registro gravado."""
        try:
            cursor = conn_db.cursor()
            cursor.execute(f"""
                SELECT TOP 1 dt_created_at FROM tb_log_registrador
                WHERE id_ihm = {self.id_ihm} ORDER BY dt_created_at DESC
            """)
            row = cursor.fetchone()
            if not row:
                return
            cursor.execute(f"""
                SELECT nu_valor_bruto FROM tb_log_registrador
                WHERE id_ihm = {self.id_ihm} AND dt_created_at = '{row[0]}'
                ORDER BY id_log_registrador ASC
            """)
            vals = [int(r[0]) for r in cursor.fetchall()]
            if len(vals) != 10:
                return
            # posições: 0=operador, 1=status(ignorado), 2=motivo, 3=produzido,
            #           4=reprovado, 5=total, 6=manutentor, 7=engenheiro,
            #           8=meta(ignorado), 9=modelo
            self.operador, _, self.motivo_parada, \
            self.produzido, self.reprovado, self.total_produzido, \
            self.manutentor, self.engenheiro, _, self.modelo = vals
            self.prev_values = vals[:]
        except Exception as e:
            logger.warning(f"IHM {self.id_ihm}: falha ao restaurar estado: {e}")

    def current_values(self) -> list:
        return [
            self.operador,
            self.status,
            self.motivo_parada,
            self.produzido,
            self.reprovado,
            self.total_produzido,
            self.manutentor,
            self.engenheiro,
            0,              # meta: sempre 0 — gerenciada exclusivamente pela API
            self.modelo,
        ]

    def build_insert_str(self) -> str:
        parts = [
            f"({self.id_ihm}, {reg_id}, {val})"
            for reg_id, val in zip(self.reg_ids, self.current_values())
        ]
        return ", ".join(parts)

    # ── Tick principal ─────────────────────────────────────────────────────────

    def tick(self, conn_db, op_id: int | None, n_etapas: int):
        """Avança um ciclo de simulação."""
        # Sem OP ativa ou etapa além da rota: fica parada
        if op_id is None or (n_etapas > 0 and self.stage_num > n_etapas):
            self._forcar_parada()
            return

        # Nova OP detectada: reinicia acumulador
        if op_id != self._op_id_atual:
            logger.info(f"IHM {self.id_ihm}: nova OP {op_id} (etapa {self.stage_num}).")
            self._acum = 0.0
            self._op_id_atual = op_id

        if self.status == STATUS_PRODUZINDO:
            self._tick_produzindo(conn_db, op_id)
        elif self.status == STATUS_PARADA:
            self._tick_parada()
        elif self.status == STATUS_AG_MANUTENCAO:
            self._tick_ag_manutencao()
        elif self.status == STATUS_MANUTENCAO:
            self._tick_manutencao()
        elif self.status == STATUS_LIMPEZA:
            self._tick_limpeza()

    def _tick_produzindo(self, conn_db, op_id: int):
        r = random.random()
        if r < PROB_IR_PARADA:
            self._transicao_parada()
        elif r < PROB_IR_PARADA + PROB_IR_MANUTENCAO:
            self._transicao_manutencao()
        elif r < PROB_IR_PARADA + PROB_IR_MANUTENCAO + PROB_IR_LIMPEZA:
            self._transicao_limpeza()
        else:
            self._produzir(conn_db, op_id)

    def _produzir(self, conn_db, op_id: int):
        pct_ciclo = self.pecas_por_hora * CYCLE_SECONDS / 3600.0
        self._acum += pct_ciclo * random.uniform(0.8, 1.2)
        n = int(self._acum)
        if n <= 0:
            return
        self._acum -= n

        approved, rejected = _process_pieces(conn_db, op_id, self.stage_num, n)
        total = approved + rejected
        if total == 0:
            return   # nenhuma peça disponível nesta etapa ainda

        self.produzido       += approved
        self.reprovado       += rejected
        self.total_produzido += total

    def _tick_parada(self):
        self.parada_duracao += 1

        # Operador informa o motivo após um delay (fluxo real assíncrono).
        if self._ciclos_motivo_delay > 0:
            self._ciclos_motivo_delay -= 1
            if self._ciclos_motivo_delay == 0 and self._motivo_pendente != 0:
                self.motivo_parada = self._motivo_pendente
                self._motivo_pendente = 0
                # Retorno antecipado: garante que este ciclo só grave o motivo.
                # O insert_if_changed verá (status=0, motivo=X) separadamente de
                # (status=49, motivo=0), preservando o registro assíncrono no log.
                return

        # A máquina pode retomar produção quando:
        #   (a) o motivo foi registrado pelo operador — fluxo normal de parada, OU
        #   (b) não há motivo pendente nem delay em andamento — significa que a parada
        #       foi forçada por ausência de OP (_forcar_parada) e a OP acaba de chegar.
        #       Nesse caso não faz sentido bloquear a retomada esperando um motivo que
        #       nunca será setado.
        motivo_ok = (self.motivo_parada != 0) or (
            self._motivo_pendente == 0 and self._ciclos_motivo_delay == 0
        )
        if (motivo_ok
                and self.parada_duracao >= MIN_CICLOS_PARADA
                and random.random() < PROB_VOLTA_DE_PARADA):
            self._transicao_produzindo()

    def _tick_ag_manutencao(self):
        """Status 51 — Aguardando Manutentor (permanente). Aguarda o manutentor chegar."""
        self.parada_duracao += 1
        if self._ciclos_ag_manutencao > 0:
            self._ciclos_ag_manutencao -= 1
            if self._ciclos_ag_manutencao == 0:
                # Manutentor chegou → transiciona para STATUS_MANUTENCAO (52, transitório).
                # O motivo só será revelado após _ciclos_manutencao_delay ciclos.
                self.status                   = STATUS_MANUTENCAO
                self.motivo_parada            = 0   # ainda sem motivo
                self._ciclos_manutencao_delay = random.randint(1, MAX_CICLOS_MANUTENCAO_DELAY)
                self.parada_duracao           = 0

    def _tick_manutencao(self):
        """Status 52 — Em Manutenção (transitório). Aguarda motivo e depois libera."""
        self.parada_duracao += 1

        # Manutentor registra o motivo após um delay (fluxo real assíncrono).
        if self._ciclos_manutencao_delay > 0:
            self._ciclos_manutencao_delay -= 1
            if self._ciclos_manutencao_delay == 0 and self._motivo_manutencao_pendente != 0:
                self.motivo_parada                = self._motivo_manutencao_pendente
                self._motivo_manutencao_pendente  = 0
                # Retorno antecipado: garante que (status=52, motivo=X) seja gravado
                # separadamente de (status=49, motivo=0) na próxima retomada.
                return

        # Pode retomar quando motivo já foi registrado (ou não havia motivo pendente).
        motivo_ok = (self.motivo_parada != 0) or (
            self._motivo_manutencao_pendente == 0 and self._ciclos_manutencao_delay == 0
        )
        if (motivo_ok
                and self.parada_duracao >= MIN_CICLOS_MANUTENCAO
                and random.random() < PROB_VOLTA_DE_MANUTENCAO):
            self._transicao_produzindo()

    def _tick_limpeza(self):
        self.parada_duracao += 1
        if self.parada_duracao >= MIN_CICLOS_LIMPEZA and random.random() < PROB_VOLTA_DE_LIMPEZA:
            self._transicao_produzindo()

    def _forcar_parada(self):
        if self.status != STATUS_PARADA:
            self.status                      = STATUS_PARADA
            self.motivo_parada               = 0
            self.manutentor                  = 0
            self.engenheiro                  = 0
            self.parada_duracao              = 0
            self._ciclos_ag_manutencao       = 0
            self._motivo_manutencao_pendente = 0
            self._ciclos_manutencao_delay    = 0

    def _transicao_parada(self):
        # Fluxo real: máquina para (status=0, sem motivo ainda).
        # O operador informa o motivo depois — simulado via delay assíncrono.
        self.status              = STATUS_PARADA
        self.motivo_parada       = 0   # ainda sem motivo
        self._motivo_pendente    = random.choice(self.motivos) if self.motivos else 1
        self._ciclos_motivo_delay = random.randint(MIN_CICLOS_MOTIVO_DELAY, MAX_CICLOS_MOTIVO_DELAY)
        self.parada_duracao      = 0

    def _transicao_manutencao(self):
        # Fluxo real: operador chama manutenção → STATUS 51 (Ag. Manutentor).
        # Manutentor chega depois → STATUS 52 (Em Manutenção).
        # Manutentor registra o motivo → código de motivo assíncrono.
        self.status                      = STATUS_AG_MANUTENCAO  # 51
        self.motivo_parada               = 0
        self.manutentor                  = random.choice(self.manutentores) if self.manutentores else 1
        self.engenheiro                  = random.choice(self.engenheiros)  if self.engenheiros  else 0
        self.parada_duracao              = 0
        self._ciclos_ag_manutencao       = random.randint(MIN_CICLOS_AG_MANUTENCAO, MAX_CICLOS_AG_MANUTENCAO)
        self._motivo_manutencao_pendente = random.choice(self.motivos) if self.motivos else 3
        self._ciclos_manutencao_delay    = 0

    def _transicao_limpeza(self):
        self.status         = STATUS_LIMPEZA
        self.motivo_parada  = 4
        self.parada_duracao = 0

    def _transicao_produzindo(self):
        self.status               = STATUS_PRODUZINDO
        self.motivo_parada        = 0
        self.manutentor           = 0
        self.engenheiro           = 0
        self.parada_duracao       = 0
        self._motivo_pendente            = 0
        self._ciclos_motivo_delay        = 0
        self._ciclos_ag_manutencao       = 0
        self._motivo_manutencao_pendente = 0
        self._ciclos_manutencao_delay    = 0


# ─── Carregamento ──────────────────────────────────────────────────────────────

def _stage_of(id_ihm: int) -> int:
    for idx, stage in enumerate(STAGES):
        if id_ihm in stage:
            return idx
    return 0


def load_machine(id_ihm: int, conn_db) -> MachineState:
    cursor = conn_db.cursor()

    cursor.execute(f"SELECT id_registrador FROM tb_registrador WHERE id_ihm = {id_ihm} ORDER BY id_registrador ASC")
    reg_ids = [r[0] for r in cursor.fetchall()]

    cursor.execute(f"SELECT nu_cod_motivo_parada FROM tb_depara_motivo_parada WHERE id_ihm = {id_ihm}")
    motivos = [r[0] for r in cursor.fetchall()]

    cursor.execute(f"SELECT nu_cod_manutentor FROM tb_depara_manutentor WHERE id_ihm = {id_ihm}")
    manutentores = [r[0] for r in cursor.fetchall()]

    cursor.execute(f"SELECT nu_cod_engenheiro FROM tb_depara_engenheiro WHERE id_ihm = {id_ihm}")
    engenheiros = [r[0] for r in cursor.fetchall()]

    cursor.execute(f"SELECT nu_cod_peca FROM tb_depara_peca WHERE id_ihm = {id_ihm}")
    modelos = [r[0] for r in cursor.fetchall()]

    op = OPERATORS.get(id_ihm, {"cod": 1, "nome": "Operador"})

    machine = MachineState(
        id_ihm         = id_ihm,
        stage_idx      = _stage_of(id_ihm),
        pecas_por_hora = MACHINE_RATES.get(id_ihm, 60),
        reg_ids        = reg_ids,
        operador_cod   = op["cod"],
        motivos        = motivos,
        manutentores   = manutentores,
        engenheiros    = engenheiros,
        modelos        = modelos,
    )
    machine.load_from_db(conn_db)
    logger.info(f"IHM {id_ihm} carregada: etapa {machine.stage_num}, operador={op['nome']}")
    return machine


# ─── Persistência ──────────────────────────────────────────────────────────────

def insert_if_changed(machine: MachineState, conn_db):
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
            f"status={machine.status} prod={machine.produzido} reprov={machine.reprovado}"
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


def _reconectar(max_tentativas: int = 10):
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


# ─── Entry point ───────────────────────────────────────────────────────────────

def main():
    while True:
        conn_db = None
        try:
            conn_db = get_connection_db()

            machines = [load_machine(id_ihm, conn_db) for id_ihm in GHOST_IHM_IDS]
            logger.info(f"Simulador iniciado — {len(machines)} operadores, ciclo {CYCLE_SECONDS}s.")

            while True:
                logger.info("=" * 60)

                # Obtém OP ativa e inicializa rastreamento de peças
                try:
                    op_id, quantidade = _get_active_op(conn_db)
                except Exception as e:
                    logger.warning(f"Erro ao obter OP ativa: {e}")
                    op_id, quantidade = None, 0

                n_etapas = N_ETAPAS
                if op_id:
                    try:
                        _init_pieces_if_needed(conn_db, op_id, quantidade)
                        n_etapas = _get_n_etapas_op(conn_db, op_id)
                    except Exception as e:
                        logger.warning(f"Erro ao inicializar peças OP {op_id}: {e}")

                # Tick em ordem INVERSA de etapa — evita que uma peça avançada num
                # estágio seja imediatamente processada pelo próximo no mesmo ciclo.
                machines_rev = sorted(machines, key=lambda m: m.stage_num, reverse=True)
                for machine in machines_rev:
                    try:
                        machine.tick(conn_db, op_id, n_etapas)
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
