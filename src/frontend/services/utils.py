from datetime import datetime


def get_weekday_start(reference_day=datetime.now()):
    year = reference_day.year
    month = reference_day.month
    return datetime(year, month, 1).weekday()
