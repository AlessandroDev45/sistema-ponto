# src/utils/logger.py
import logging
import os
from datetime import datetime

def setup_logger(name, level=logging.INFO):
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    if not logger.handlers:
        # Configurar formato
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Handler para arquivo
        log_dir = os.getenv('LOG_DIR', 'logs')
        os.makedirs(log_dir, exist_ok=True)
        
        data_atual = datetime.now().strftime('%Y%m%d')
        file_handler = logging.FileHandler(
            os.path.join(log_dir, f'{name}_{data_atual}.log')
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        # Handler para console
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        # Handler para erros críticos
        error_handler = logging.FileHandler(
            os.path.join(log_dir, f'error_{data_atual}.log')
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(formatter)
        logger.addHandler(error_handler)
    
    return logger

def log_exception(logger, e, mensagem=""):
    logger.error(f"{mensagem} Erro: {str(e)}")
    logger.exception("Detalhes do erro:")