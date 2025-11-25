FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    unixodbc \
    unixodbc-dev \
    freetds-dev \
    freetds-bin \
    tdsodbc \
    && rm -rf /var/lib/apt/lists/*

RUN echo "[FreeTDS]\n\
    Description=FreeTDS Driver\n\
    Driver=/usr/lib/x86_64-linux-gnu/odbc/libtdsodbc.so\n\
    UsageCount=1\n" >> /etc/odbcinst.ini

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .
