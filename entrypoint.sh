#!/bin/bash
set -euo pipefail

/opt/mssql/bin/sqlservr &

echo "Aguardando o SQL Server iniciar..."
# até 10 min (300 tentativas x 2s) – a 1ª inicialização pode demorar
for i in {1..300}; do
  if /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P "${MSSQL_SA_PASSWORD}" -C -Q "SELECT 1" &>/dev/null; then
    echo "SQL Server pronto após $i tentativas."
    ready=1
    break
  fi
  sleep 2
done

if [ "${ready:-0}" -ne 1 ]; then
  echo "Timeout aguardando o SQL Server ficar pronto."
  exit 1
fi

MARKER="/var/opt/mssql/.init-done"
if [ ! -f "${MARKER}" ]; then
  echo "Executando /scripts/init.sql (primeira inicialização)..."
  /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P "${MSSQL_SA_PASSWORD}" -C -i /scripts/init.sql
  touch "${MARKER}"
  echo "Init concluído."
else
  echo "Init já executado anteriormente. Pulando!"
fi

wait
