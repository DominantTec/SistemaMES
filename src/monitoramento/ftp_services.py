from ftplib import FTP
import pandas as pd
from pathlib import Path
from logger import logger


def connect_ftp(host, user, pwd) -> FTP:
    """
    Conecta ao servidor FTP da IHM e retorna o objeto FTP.
    """
    try:
        ftp = FTP()
        ftp.connect(host, 21, timeout=10)
        ftp.login(user, pwd)
        logger.info("Conexão FTP feita com sucesso!")
        return ftp
    except Exception as e:
        logger.error("Erro ao estabelecer a conexão FTP: %s", e)
        return None


def list_files(ftp: FTP, directory: str, show_info: bool = False) -> list:
    """
    Lista arquivos em um diretório da IHM.
    """
    try:
        logger.info(f"\nListando arquivos em: {directory}")
        ftp.cwd(directory)
        files = ftp.nlst()
        if show_info:
            for f in files:
                logger.info(f" - {f}")
        return files
    except Exception as e:
        logger.error("Erro ao listar arquivos: %s", e)
        return []


def download_file(ftp: FTP,
                  remote_dir: str,
                  remote_filename: str,
                  local_path: Path) -> bool:
    """
    Baixa um arquivo do FTP (IHM) para o PC.
    """
    try:
        logger.info(
            f"Baixando '{remote_filename}' de '{remote_dir}' para '{local_path}' ...")
        ftp.cwd(remote_dir)
        with open(local_path, "wb") as f:
            ftp.retrbinary(f"RETR {remote_filename}", f.write)
        logger.info(f"Download concluído!")
        return True
    except Exception as e:
        logger.error("Erro fazer download do arquivo: %s", e)
        return False


def read_ftp_file(file_path):
    tables = dict()
    data = []
    current_table = None
    with open(file_path, encoding="utf-8") as f:
        for linha in f:
            linha = linha.strip()
            if not linha:   # linha vazia → terminou tabela
                if current_table and data:
                    tables[current_table] = pd.DataFrame(
                        data, columns=["ID", "Codigo", "Nome"])
                    data = []
                continue

            partes = [x.strip() for x in linha.split(",") if x.strip()]

            # Detecta nome da tabela (ex: Matriculas, Manutentor)
            if len(partes) == 3 and partes[1].isdigit() and partes[2].isdigit():
                current_table = partes[0]
                continue

            # Pulamos linhas metadata (ex: "2,1,0,0,Código")
            if len(partes) >= 4:
                continue

            # Linhas de data válidas (ID, Código, Nome)
            if len(partes) >= 3:
                data.append(partes[:3])

    return tables
