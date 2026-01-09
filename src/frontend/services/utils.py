from datetime import datetime, date, timedelta, time
from services.db import run_query_update


def to_time(v):
    if isinstance(v, time):
        return v
    return time(v.hour, v.minute)


def get_weekday_start(reference_day=datetime.now()):
    year = reference_day.year
    month = reference_day.month
    return datetime(year, month, 1).weekday()


def get_last_day_month(reference_day=datetime.now()):
    if reference_day.month == 12:
        first_day_next_month = date(reference_day.year + 1, 1, 1)
    else:
        first_day_next_month = date(
            reference_day.year, reference_day.month + 1, 1)

    last_day = first_day_next_month - timedelta(days=1)

    return int(last_day.day)


def fill_month_database(reference_day=datetime.now(), ids_ihm=[1, 2], start_hour=7, end_hour=20):
    query = """
        INSERT INTO tb_funcionamento (id_ihm, dia, mes, ano, horario_inicio, horario_fim)
        VALUES (:id_ihm, :dia, :mes, :ano, :horario_inicio, :horario_fim)
    """
    for id_ihm in ids_ihm:
        for day in range(1, get_last_day_month(reference_day)+1):
            params = {"id_ihm": id_ihm,
                      "dia": day,
                      "mes": reference_day.month,
                      "ano": reference_day.year,
                      "horario_inicio": datetime(reference_day.year, reference_day.month, day, start_hour),
                      "horario_fim": datetime(reference_day.year, reference_day.month, day, end_hour)}
            run_query_update(query, params)


def post_working_hours(reference_day, id_ihm, start_hour, end_hour):
    query = """
        UPDATE tb_funcionamento
        SET horario_inicio = :horario_inicio,
            horario_fim = :horario_fim
        WHERE id_ihm = :id_ihm
          AND dia = :dia
          AND mes = :mes
          AND ano = :ano
    """
    params = {
        "id_ihm": id_ihm,
        "dia": reference_day.day,
        "mes": reference_day.month,
        "ano": reference_day.year,
        "horario_inicio": start_hour,
        "horario_fim": end_hour
    }
    run_query_update(query, params)
