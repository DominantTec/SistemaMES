FROM mcr.microsoft.com/mssql/server:2019-latest

ENV ACCEPT_EULA=Y \
    MSSQL_SA_PASSWORD=Domin4nt2025@ \
    MSSQL_PID=Developer

# Somente isso já funciona!