# src/utils/backup.py
import sys
import os
from pathlib import Path

# Adiciona o diretório raiz ao Python Path
current_dir = Path(__file__).resolve().parent
root_dir = current_dir.parent.parent
sys.path.append(str(root_dir))

import shutil
from datetime import datetime, timedelta
import logging
import json

from src.utils.logger import setup_logger

class BackupManager:
    def __init__(self, config):
        self.config = config  # Já está correto, assume que é Config.get_instance()
        self.logger = setup_logger('BackupManager')

    def criar_backup(self, tipo='diario'):
        try:
            data_atual = datetime.now()
            backup_name = f"backup_{tipo}_{data_atual.strftime('%Y%m%d_%H%M%S')}"
            
            # Garantir existência do diretório
            backup_dir = os.path.join(self.config.BACKUP_DIR, tipo)
            os.makedirs(backup_dir, exist_ok=True)  # Cria diretórios recursivamente
            
            # Backup do banco
            db_backup = os.path.join(backup_dir, f"{backup_name}.db")
            shutil.copy2(self.config.DB_PATH, db_backup)
            
            # Backup da configuração
            config_backup = os.path.join(backup_dir, f"{backup_name}_config.json")
            self._backup_config(config_backup)
            
            self.logger.info(f"Backup {tipo} criado em: {db_backup}")
            return True
            
        except Exception as e:
            self.logger.error(f"Erro ao criar backup {tipo}: {e}")
            return False

    def limpar_backups_antigos(self):
        try:
            data_limite = datetime.now() - timedelta(days=self.config.BACKUP_RETENTION_DAYS)
            
            for tipo in ['diario', 'semanal', 'mensal']:
                backup_dir = os.path.join(self.config.BACKUP_DIR, tipo)
                if not os.path.exists(backup_dir):
                    continue
                    
                for arquivo in os.listdir(backup_dir):
                    caminho_arquivo = os.path.join(backup_dir, arquivo)
                    data_arquivo = datetime.fromtimestamp(os.path.getctime(caminho_arquivo))
                    
                    if data_arquivo < data_limite:
                        os.remove(caminho_arquivo)
                        self.logger.info(f"Backup antigo removido: {arquivo}")
                        
            return True
            
        except Exception as e:
            self.logger.error(f"Erro ao limpar backups antigos: {e}")
            return False

    def _backup_config(self, destino):
        config_data = {
            attr: getattr(self.config, attr)
            for attr in dir(self.config)
            if not attr.startswith('_') and attr.isupper()
        }
        
        with open(destino, 'w') as f:
            json.dump(config_data, f, indent=4)