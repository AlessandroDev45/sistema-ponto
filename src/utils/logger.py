# src/utils/logger.py

import logging
import sys
import os 
from datetime import datetime
from pathlib import Path

def setup_logger(name, level=logging.INFO):
    """Configura o logger com output para arquivo e console"""
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Se já tem handlers, não adiciona novos
    if logger.handlers:
        return logger
        
    # Formato padrão para os logs
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Handler para arquivo
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    file_handler = logging.FileHandler(
        log_dir / f"{name}_{datetime.now().strftime('%Y%m%d')}.log",
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    
    # Handler para console (terminal)
    try:
        reconfigure = getattr(sys.stdout, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    
    # Adiciona os handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    # Garante que erros serão mostrados
    logger.propagate = True
    
    return logger

def log_exception(logger, e, mensagem=""):
    """Registra exceções com detalhes"""
    logger.error(f"{mensagem} Erro: {str(e)}")
    logger.exception("Detalhes do erro:")