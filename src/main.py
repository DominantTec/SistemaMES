from src.logger import logger
from src.config import load_config, get_args
from src.database import get_connection_db
from src.ihm_client import get_connection_ihm

def main():
    args = get_args()
    logger.info("Iniciando monitoramento da IHM...")

    config = load_config(args.config_path)

    conn_db = get_connection_db(config['banco']['conn_driver'], config['banco']['conn_server'], config['banco']['conn_database'])
    conn_ihm = get_connection_ihm(f"{config['ihm']['ip']}", config['ihm']['port'])

if __name__ == "__main__":
    main()