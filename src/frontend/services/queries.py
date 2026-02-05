from services.db import run_query, run_query_update
from typing import List, Dict, Any
import streamlit as st


@st.cache_data(ttl=10)
def get_active_lines() -> List[Dict[str, Any]]:
    '''Retorna todas as linhas de produção.'''
    return run_query("""
        SELECT id_linha_producao, tx_name
        FROM tb_linha_producao
        ORDER BY id_linha_producao
    """)


@st.cache_data(ttl=10)
def get_active_machines(line_id: int) -> List[Dict[str, Any]]:
    '''Retorna todas as IHMs de uma determinada linha.'''
    return run_query("""
        SELECT id_ihm, tx_name
        FROM tb_ihm
        WHERE id_linha_producao = :id
        ORDER BY id_ihm
    """, {"id": line_id})


@st.cache_data(ttl=2)
def get_machine_timeline(machine_id: int, data_inicio=None, data_fim=None) -> Dict[str, Any]:
    '''Retorna a linha do tempo de uma IHM filtrada no tempo ou não.'''
    if not data_inicio or not data_fim:
        df_registradores = run_query("""
            SELECT * FROM tb_log_registrador
            WHERE id_ihm = :id
        """, {'id': machine_id})
    else:
        df_registradores = run_query("""
            SELECT * FROM tb_log_registrador
            WHERE id_ihm = :id 
            AND dt_created_at >= :data_inicio 
            AND dt_created_at <= :data_fim
        """, {'id': machine_id, 'data_inicio': data_inicio, 'data_fim': data_fim})
    df_ihms = run_query("""
        SELECT
            id_ihm,
            tx_name
        FROM tb_ihm
    """)
    df_depara_registradores = run_query("""
        SELECT
            id_registrador,
            tx_descricao 
        FROM tb_registrador
    """)
    if len(df_registradores) > 2:
        df_registradores = df_registradores.merge(
            df_ihms, how='left', on='id_ihm')
        df_registradores = df_registradores.merge(
            df_depara_registradores, how='left', on='id_registrador')
        df_registradores = df_registradores[[
            'tx_name', 'tx_descricao', 'dt_created_at', 'nu_valor_bruto']]
        del df_ihms, df_depara_registradores
        df_registradores = df_registradores.pivot_table(
            index=['tx_name', 'dt_created_at'], columns='tx_descricao', values='nu_valor_bruto', aggfunc='first').reset_index()
        df_registradores = df_registradores.sort_values('dt_created_at')
        df_registradores.reset_index(drop=True, inplace=True)
        depara_status_maquina = {
            0: 'Parada',
            1: 'Passar Padrão',
            49: 'Produzindo',
            4: 'Limpeza',
            51: 'Aguardando Manutentor',
            52: 'Máquina em manutenção',
            50: 'Maquina Liberada',
            53: 'Alteração de Parâmetros',
        }
        df_registradores['status_maquina'] = df_registradores['status_maquina'].map(
            depara_status_maquina)

    return df_registradores


@st.cache_data(ttl=2)
def get_machine_shifts(machine_id: int, data_inicio=None, data_fim=None) -> Dict[str, Any]:
    '''Usando o id de uma IHM, retorna os turnos de uma linha de produção filtrado por data ou não.'''
    if not data_inicio or not data_fim:
        df_funcionamento = run_query("""
            SELECT * FROM tb_turnos
            WHERE id_linha_producao = (SELECT id_linha_producao FROM tb_ihm WHERE id_ihm = :id)
        """, {'id': machine_id})
    else:
        df_funcionamento = run_query("""
            SELECT * FROM tb_turnos
            WHERE id_linha_producao = (SELECT id_linha_producao FROM tb_ihm WHERE id_ihm = :id)
            AND dt_inicio >= :data_inicio 
            AND dt_fim <= :data_fim
        """, {'id': machine_id, 'data_inicio': data_inicio, 'data_fim': data_fim})
    df_ihms = run_query("""
        SELECT
            id_ihm,
            tx_name,
            id_linha_producao
        FROM tb_ihm
    """)
    df_funcionamento = df_funcionamento.merge(
        df_ihms, how='left', on='id_linha_producao')
    return df_funcionamento


def get_possible_pieces(machine_id: int) -> list:
    '''Retorna as peças possiveis em uma determinada IHM.'''
    try:
        resultado = run_query("""
            SELECT tx_peca
            FROM tb_depara_peca
            WHERE id_ihm = :id
        """, {"id": machine_id})
        if resultado['tx_peca'].to_list() == []:
            return ['PEÇA TEMP', 'PEÇA 1', 'SEM PEÇAS PARA DEPARA']
        else:
            return resultado['tx_peca'].to_list()
    except:
        return ['PEÇA TEMP', 'PEÇA 1']


def get_selected_piece(machine_id: int, data_ref: Any | None = None) -> str:
    '''Retorna a peça seleciona antes da data informada.'''
    try:
        if not data_ref:
            cod_peca = run_query("""
                SELECT *
                FROM tb_log_registrador
                WHERE id_registrador = (SELECT id_registrador
                                        FROM tb_registrador
                                        WHERE id_ihm = :id AND tx_descricao='modelo_peça')
                ORDER BY dt_created_at DESC
            """, {"id": machine_id})['nu_valor_bruto'].tolist()[0]
            resultado = run_query("""
                SELECT tx_peca
                FROM tb_depara_peca
                WHERE id_ihm = :id AND nu_cod_peca=:nu_cod_peca
            """, {"id": machine_id, "nu_cod_peca": cod_peca})['tx_peca'].tolist()
        else:
            cod_peca = run_query("""
                SELECT *
                FROM tb_log_registrador
                WHERE id_registrador = (SELECT id_registrador
                                        FROM tb_registrador
                                        WHERE id_ihm = :id AND tx_descricao='modelo_peça')
                    AND dt_created_at <= :data
                ORDER BY dt_created_at DESC
            """, {"id": machine_id, "data": data_ref})['nu_valor_bruto'].tolist()[0]
            resultado = run_query("""
                SELECT tx_peca
                FROM tb_depara_peca
                WHERE id_ihm = :id AND nu_cod_peca=:nu_cod_peca
            """, {"id": machine_id, "nu_cod_peca": cod_peca})['tx_peca'].tolist()
        if resultado == []:
            return 'PEÇA TEMP'
        else:
            return resultado[0]
    except:
        return 'PEÇA TEMP'


def get_meta(machine_id: int, data_ref: Any | None = None) -> int:
    '''Retorna a meta antes da data informada.'''
    try:
        if not data_ref:
            resultado = run_query("""
                SELECT *
                FROM tb_log_registrador
                WHERE id_registrador = (SELECT id_registrador
                                        FROM tb_registrador
                                        WHERE id_ihm = :id AND tx_descricao='meta')
                ORDER BY dt_created_at DESC
            """, {"id": machine_id})
        else:
            resultado = run_query("""
                SELECT *
                FROM tb_log_registrador
                WHERE id_registrador = (SELECT id_registrador
                                        FROM tb_registrador
                                        WHERE id_ihm = :id AND tx_descricao='meta')
                    AND dt_created_at <= :data
                ORDER BY dt_created_at DESC
            """, {"id": machine_id, "data": data_ref})
        resultado = int(resultado['nu_valor_bruto'].tolist()[0])
        return resultado
    except:
        return 1


def get_meta_register(machine_id: int) -> int:
    '''Retorna o registro referente a meta naquela IHM.'''
    try:
        resultado = run_query("""
            SELECT nu_endereco
            FROM tb_registrador
            WHERE id_ihm = :id AND tx_descricao='meta'
        """, {"id": machine_id})
        resultado = resultado['nu_endereco'].tolist()[0]
        return resultado
    except:
        return -1


@st.cache_data(ttl=2)
def get_metrics_machine(machine_id: int, data_inicio: Any | None = None, data_fim: Any | None = None) -> Dict[str, Any]:
    '''Retorna as principais informações de uma IHM para um dado periodo de tempo.'''
    try:
        df_registradores = get_machine_timeline(
            machine_id, data_inicio=data_inicio, data_fim=data_fim)
        df_shifts = get_machine_shifts(
            machine_id, data_inicio=data_inicio, data_fim=data_fim)

        first_register = df_registradores[df_registradores['dt_created_at']
                                          == df_registradores['dt_created_at'].min()]
        last_register = df_registradores[df_registradores['dt_created_at']
                                         == df_registradores['dt_created_at'].max()]
        status = last_register['status_maquina'].to_list()[0]
        operador = last_register['operador'].to_list()[0]
        manutentor = last_register['manutentor'].to_list()[0]
        engenheiro = last_register['engenheiro'].to_list()[0]

        # OEE = Disponibilidade * Performance * Qualidade

        # Disponibilidade = Tempo produzido / Tempo programado para produzir
        lista_qtd_aprovado = []
        lista_qtd_reprovado = []
        lista_qtd_total = []
        lista_produzido = []
        lista_esperado = []
        status_antigo = ""
        inicio = None
        inicio_qtd_aprovado = None
        inicio_qtd_reprovado = None
        inicio_qtd_total = None
        inicio_teorico = None
        fim = None
        fim_qtd_aprovado = None
        fim_qtd_reprovado = None
        fim_qtd_total = None
        fim_teorico = None
        for i, row in df_registradores.iterrows():
            # Apenas o turno que inicio na data.
            working_day = df_shifts[(df_shifts['dt_inicio'].dt.date == row['dt_created_at'].date()) & (
                df_shifts['id_ihm'] == machine_id)]
            # Se não era Produzindo e agora é, então estava parada e agora ta produzindo
            if status_antigo != 'Produzindo' and row['status_maquina'] == 'Produzindo':
                # Data do registrador precisa ser anterior ao fim do turno
                if row['dt_created_at'] < working_day['dt_fim'].to_list()[0]:
                    if row['dt_created_at'] < working_day['dt_inicio'].to_list()[0]:
                        inicio = working_day['dt_inicio'].to_list()[0]
                    else:
                        inicio = row['dt_created_at']
                    inicio_qtd_aprovado = row['produzido']
                    inicio_qtd_reprovado = row['reprovado']
                    inicio_qtd_total = row['total_produzido']
                    inicio_teorico = working_day['dt_inicio'].to_list()[0]
            # Se estava parada e agora está produzindo ou é o ultimo registro
            elif (status_antigo == 'Produzindo' and row['status_maquina'] != 'Produzindo') or (status_antigo == 'Produzindo' and row['status_maquina'] == 'Produzindo' and row['dt_created_at'] == last_register['dt_created_at'].to_list()[0]):
                # Data do registrador precisa ser depois do inicio do turno
                if row['dt_created_at'] > working_day['dt_inicio'].to_list()[0]:
                    if row['dt_created_at'] > working_day['dt_fim'].to_list()[0]:
                        fim = working_day['dt_fim'].to_list()[0]
                    else:
                        fim = row['dt_created_at']
                    fim_qtd_aprovado = row['produzido']
                    fim_qtd_reprovado = row['reprovado']
                    fim_qtd_total = row['total_produzido']
                    fim_teorico = working_day['dt_fim'].to_list()[0]
            # Se tiver inicio e fim
            if inicio and fim:
                # Mesmo dia
                if inicio.day == fim.day:
                    # Já não foi adicionado
                    if (inicio, fim) not in lista_produzido:
                        lista_produzido.append((inicio, fim))
                    if (inicio_teorico, fim_teorico) not in lista_esperado:
                        lista_esperado.append((inicio_teorico, fim_teorico))
                    # Qtd de peças sempre adiciona
                    lista_qtd_aprovado.append(
                        (inicio_qtd_aprovado, fim_qtd_aprovado))
                    lista_qtd_reprovado.append(
                        (inicio_qtd_reprovado, fim_qtd_reprovado))
                    lista_qtd_total.append((inicio_qtd_total, fim_qtd_total))

                inicio_qtd_aprovado = None
                inicio_qtd_reprovado = None
                inicio_qtd_total = None
                fim_qtd_aprovado = None
                fim_qtd_reprovado = None
                fim_qtd_total = None
                inicio = None
                inicio_teorico = None
                fim = None
                fim_teorico = None
            status_antigo = row['status_maquina']
        tempo_produzido = sum([y.total_seconds()
                               for y in [x[1] - x[0] for x in lista_produzido]])
        tempo_programado = sum([y.total_seconds()
                                for y in [x[1] - x[0] for x in lista_esperado]])
        produzido = sum([y for y in [x[1] - x[0] for x in lista_qtd_aprovado]])
        reprovado = sum([y for y in [x[1] - x[0]
                        for x in lista_qtd_reprovado]])
        total = sum([y for y in [x[1] - x[0] for x in lista_qtd_total]])
        disponibilidade = tempo_produzido / tempo_programado

        # Performance = Produção Real / Produção Teórica
        # Considerando que a cada 1 s é feito uma peça
        meta = (tempo_programado // 1)
        performance = int(total) / meta

        # Qualidade = Peça Boas / Total de peças
        qualidade = int(produzido) / int(total)

        oee = disponibilidade * performance * qualidade
        # OEE, Qualidade, Eficiencia, Meta, Acumulado, Operador, Manutentor, Status

        return {
            'status_maquina': status,
            'oee': round(100 * oee, 2),
            'disponibilidade': round(100 * disponibilidade, 2),
            'performance': round(100 * performance, 2),
            'qualidade': round(100 * qualidade, 2),
            'meta': meta,
            'produzido': produzido,
            'reprovado': reprovado,
            'total_produzido': total,
            'operador': operador,
            'manutentor': manutentor,
            'engenheiro': engenheiro,
            # MTBF - TEMPO MÉDIO ENTRE FALHAS
            # MTTR - TEMPO MÉDIO PARA REPARO
            # MTTA - TEMPO MÉDIO PARA ATENDIMENTO
            # PEÇA_ATUAL
            # REGISTRO DE PARADAS
        }
    except Exception:
        return {
            'status_maquina': "-",
            'oee': "-",
            'disponibilidade': "-",
            'performance': "-",
            'qualidade': "-",
            'meta': "-",
            'produzido': "-",
            'reprovado': "-",
            'total_produzido': "-",
            'operador': "-",
            'manutentor': "-",
            'engenheiro': '-'
        }
