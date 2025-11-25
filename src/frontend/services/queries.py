from services.db import run_query
from typing import List, Dict, Any
import streamlit as st


@st.cache_data(ttl=10)
def get_active_lines() -> List[Dict[str, Any]]:
    return run_query("""
        SELECT id_linha_producao, nome
        FROM linhas_producao
        ORDER BY id_linha_producao
    """)


@st.cache_data(ttl=10)
def get_active_machines(line_id: int) -> List[Dict[str, Any]]:
    return run_query("""
        SELECT id_ihm, nome_maquina
        FROM ihms
        WHERE id_linha_producao = :id
        ORDER BY id_ihm
    """, {"id": line_id})


@st.cache_data(ttl=2)
def get_machine_timeline(machine_id: int, data_inicio=None, data_fim=None) -> Dict[str, Any]:
    if not data_inicio or not data_fim:
        df_registradores = run_query("""
            SELECT * FROM logs_registradores
            WHERE id_ihm = :id
        """, {'id': machine_id})
    else:
        print("data_inicio")
        print(data_inicio)
        print("data_fim")
        print(data_fim)
        df_registradores = run_query("""
            SELECT * FROM logs_registradores
            WHERE id_ihm = :id 
            AND datahora >= :data_inicio 
            AND datahora <= :data_fim
        """, {'id': machine_id, 'data_inicio': data_inicio, 'data_fim': data_fim})
    df_ihms = run_query("""
        SELECT
            id_ihm,
            nome_maquina
        FROM ihms
    """)
    df_depara_registradores = run_query("""
        SELECT
            id_registrador,
            descricao 
        FROM registradores
    """)
    if len(df_registradores) > 2:
        df_registradores = df_registradores.merge(
            df_ihms, how='left', on='id_ihm')
        df_registradores = df_registradores.merge(
            df_depara_registradores, how='left', on='id_registrador')
        df_registradores = df_registradores[[
            'nome_maquina', 'descricao', 'datahora', 'valor_bruto']]
        del df_ihms, df_depara_registradores
        df_registradores = df_registradores.pivot_table(
            index=['nome_maquina', 'datahora'], columns='descricao', values='valor_bruto', aggfunc='first').reset_index()
        df_registradores = df_registradores.sort_values('datahora')
        df_registradores.reset_index(drop=True, inplace=True)
        depara_status_maquina = {
            '0': 'Parada',
            '1': 'Passar Padrão',
            '49': 'Produzindo',
            '4': 'Limpeza',
            '51': 'Aguardando Manutentor',
            '52': 'Máquina em manutenção',
            '50': 'Maquina Liberada',
            '53': 'Alteração de Parâmetros',
        }
        df_registradores['status_maquina'] = df_registradores['status_maquina'].map(
            depara_status_maquina)

    return df_registradores


@st.cache_data(ttl=2)
def get_metrics_machine(machine_id: int) -> Dict[str, Any]:
    try:
        df_registradores = get_machine_timeline(machine_id)

        first_register = df_registradores[df_registradores['datahora']
                                          == df_registradores['datahora'].min()]
        last_register = df_registradores[df_registradores['datahora']
                                         == df_registradores['datahora'].max()]
        status = last_register['status_maquina'].to_list()[0]
        operador = last_register['operador'].to_list()[0]
        manutentor = last_register['manutentor'].to_list()[0]
        produzido = last_register['produzido'].to_list()[0]
        reprovado = last_register['reprovado'].to_list()[0]
        total = last_register['total_produzido'].to_list()[0]

        # OEE = Disponibilidade * Performance * Qualidade

        # Disponibilidade = Tempo produzido / Tempo programado para produzir
        lista_produzido = []
        status_antigo = ""
        inicio = None
        fim = None
        for i, row in df_registradores.iterrows():
            if status_antigo != 'Produzindo' and row['status_maquina'] == 'Produzindo':
                inicio = row['datahora']
            elif (status_antigo == 'Produzindo' and row['status_maquina'] != 'Produzindo') or (status_antigo == 'Produzindo' and row['status_maquina'] == 'Produzindo' and row['datahora'] == last_register['datahora'].to_list()[0]):
                fim = row['datahora']
            if inicio and fim:
                lista_produzido.append((inicio, fim))
                inicio = None
                fim = None
            status_antigo = row['status_maquina']
        tempo_produzido = sum([y.total_seconds()
                               for y in [x[1] - x[0] for x in lista_produzido]])
        tempo_programado = (last_register['datahora'].to_list()[
                            0] - first_register['datahora'].to_list()[0]).total_seconds()
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
            'eficiencia': round(100 * performance, 2),
            'qualidade': round(100 * qualidade, 2),
            'meta': meta,
            'produzido': produzido,
            'reprovado': reprovado,
            'total_produzido': total,
            'operador': operador,
            'manutentor': manutentor
        }
    except Exception:
        return {
            'status_maquina': "-",
            'oee': "-",
            'eficiencia': "-",
            'qualidade': "-",
            'meta': "-",
            'produzido': "-",
            'reprovado': "-",
            'total_produzido': "-",
            'operador': "-",
            'manutentor': "-"
        }
