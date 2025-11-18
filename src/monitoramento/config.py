import json
import argparse
from src.logger import logger

def load_config(file):
    try:
        with open(file, 'r', encoding='utf-8') as file:
            config = json.load(file)
        logger.info(f"Configuração carregada com sucesso: {file}")
        return config
    except Exception as e:
        logger.error(f"Erro ao carregar o arquivo de configuração {file}: {e}")
        exit(1)

def get_args():
    parser = argparse.ArgumentParser(description="Monitoramento de IHM via Modbus")
    parser.add_argument("config_path", type=str, help="Caminho do JSON de configuração da IHM.")
    return parser.parse_args()