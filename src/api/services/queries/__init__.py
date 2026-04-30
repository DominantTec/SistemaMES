# ─── queries/__init__.py ────────────────────────────────────────────────────
#
# Pacote de queries do PCP. Módulos:
#   _core.py   — lógica principal (domínios a separar gradualmente)
#
# Re-exporta tudo de _core para manter compatibilidade com os routers
# que importam de `api.services.queries`.

from api.services.queries._core import (  # noqa: F401
    # ── Schema ────────────────────────────────────────────────────────────
    ensure_ordens_table,
    # ── Linhas ────────────────────────────────────────────────────────────
    get_lines_df,
    get_line_detail,
    get_line_shifts,
    update_line_shifts,
    get_machines_by_line_df,
    # ── Máquinas ──────────────────────────────────────────────────────────
    get_all_machines,
    update_machine_tipo,
    get_machine_timeline,
    get_machine_detail,
    get_machine_config_data,
    update_machine_config,
    get_possible_pieces,
    get_meta,
    get_historico_turnos,
    get_proximos_turnos,
    abrir_turno_manual,
    fechar_turno_manual,
    link_modelo_to_linhas,
    # ── Produção Teórica ──────────────────────────────────────────────────
    get_producao_teorica,
    update_producao_teorica,
    get_producao_teorica_linha,
    # ── Peças / Roteiros ──────────────────────────────────────────────────
    get_pecas_by_linha,
    create_peca,
    delete_peca,
    get_rota_peca,
    update_rota_peca,
    # ── OPs ───────────────────────────────────────────────────────────────
    get_all_ordens,
    proximo_numero_op,
    create_ordem,
    update_ordem_status,
    delete_ordem,
    calcular_metas_op,
    recalcular_turno_ordens_ativas,
    get_op_fluxo,
    save_op_distribuicao,
    ConflictError,
    STATUSES_VALIDOS,
    # ── Overview ──────────────────────────────────────────────────────────
    get_overview_data,
    get_overview_turno,
    # ── Histórico ─────────────────────────────────────────────────────────
    get_historico_data,
    get_producao_hora_maquina,
    get_pareto_paradas,
    get_ordens_funil,
    get_historico_linha_detalhe,
    get_historico_maquina_detalhe,
    # ── Setup ─────────────────────────────────────────────────────────────
    setup_ghost_data,
    # ── Alertas ───────────────────────────────────────────────────────────
    get_alertas,
    get_alertas_stats,
    reconhecer_alerta,
    resolver_alerta,
    get_alertas_config,
    save_alerta_config,
    delete_alerta_config,
    toggle_alerta_config,
    detectar_alertas_throttled,
)
