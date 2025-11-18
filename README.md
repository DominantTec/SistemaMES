# Monitoramento de IHM

Projeto para realizar o monitoramento dos dados de IHM's em fábricas.

Para funcionamento do projeto siga as instruções a seguir:

# 1. Gere o Ambiente Virtual

Instale o virtualenv:

```bash
pip3 install virtualenv
```

Crie um ambiente virtual de python 3.12:

```bash
virtualenv .\venv -p python312
```

Ative o ambiente:

```bash
venv\Scripts\activate
```

Atualize a versão do pip:

```bash
python -m pip install --upgrade pip
```

Instale os requirements:

```bash
pip install -r requirements.txt
```

# 2. Suba a base de dados

No repositório `/src`, faça uma cópia do arquivo `.env.example` e troque o nome da cópia para `.env`.
Nesse arquivo insira uma senha para seu usuário administrador, lembre-se que a senha tem que seguir os critérios do SQL Server.
Exemplo de senha `Str0ng!Passw0rd2025`.

Entre na pasta `/src` e rode o seguinte comando para subir a base de dados com o docker:

```bash
docker compose up --build
```

# 3. Abrir o tunelamento para IHM's

Para abrir o tunelamento para IHM's:

1. Abra o DIAcom.
2. Faça o login.
3. Mude para opção `Static`.
4. Insira o range de IP das máquinas.
5. Clique no botão `Create Tunel`.

Na lista de conexões, verifique se os `Status` estão `Online`.

# 4. Rodando o monitoramento

Para rodar o monitoramento, garanta que você está com o `venv` ativo e na raiz do projeto execute o seguinte comando:

```bash
python -m src.monitoramento.main
```
