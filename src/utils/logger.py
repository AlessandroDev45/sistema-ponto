# src/utils/logger.py
import logging
import os
from datetime import datetime

def setup_logger(name, level=logging.INFO):
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    if not logger.handlers:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        log_dir = os.getenv('LOG_DIR', 'logs')
        os.makedirs(log_dir, exist_ok=True)
        
        data_atual = datetime.now().strftime('%Y%m%d')
        file_handler = logging.FileHandler(
            os.path.join(log_dir, f'{name}_{data_atual}.log'),
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        error_handler = logging.FileHandler(
            os.path.join(log_dir, f'error_{data_atual}.log'),
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(formatter)
        logger.addHandler(error_handler)
    
    return logger

def log_exception(logger, e, mensagem=""):
    logger.error(f"{mensagem} Erro: {str(e)}")
    logger.exception("Detalhes do erro:")