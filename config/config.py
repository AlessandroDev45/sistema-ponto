import datetime
import os
from dotenv import load_dotenv
import logging
from pathlib import Path
import datetime

class ConfigError(Exception):
    pass

class Config:
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not Config._initialized:
            self.logger = logging.getLogger('Config')
            self._load_config()
            Config._initialized = True

    def _load_config(self):
        """Carrega e valida configurações do ambiente"""
        try:
            # Carregar diretórios essenciais
            self.BACKUP_DIR = os.path.abspath(os.getenv('BACKUP_DIR', './backups'))
            self.DB_PATH = os.path.abspath(os.getenv('DB_PATH', './database/ponto.db'))
            
            # Garantir existência de diretórios
            os.makedirs(self.BACKUP_DIR, exist_ok=True)
            os.makedirs(os.path.dirname(self.DB_PATH), exist_ok=True)
            
            # Validar horários
            self.HORARIO_ENTRADA = self._validar_horario('HORARIO_ENTRADA')
            self.HORARIO_SAIDA = self._validar_horario('HORARIO_SAIDA')
            
        except Exception as e:
            self.logger.critical(f"Falha crítica na configuração: {str(e)}")
            raise RuntimeError("Configuração inválida") from e

    def _validar_horario(self, chave):
        """Valida formato HH:MM"""
        valor = os.getenv(chave)
        try:
            # Usar datetime.datetime.strptime
            return datetime.datetime.strptime(valor, '%H:%M').time()
        except ValueError:
            raise ConfigError(f"Formato inválido para {chave}. Use HH:MM")
            
    def _validate_time(self, key):
        try:
            return datetime.strptime(os.getenv(key), '%H:%M').time()
        except ValueError as e:
            raise ConfigError(f"Formato inválido para {key}. Use HH:MM") from e

    def _validate_and_load_configs(self):
        self.SALARIO_BASE = self._get_float('SALARIO_BASE')
        self.URL_SISTEMA = self._get_required('URL_SISTEMA')
        self.LOGIN = self._get_required('LOGIN')
        self.SENHA = self._get_required('SENHA')

        self.HORARIO_ENTRADA = self._get_required('HORARIO_ENTRADA')
        self.HORARIO_SAIDA = self._get_required('HORARIO_SAIDA')
        self.INTERVALO_MINIMO = int(self._get_required('INTERVALO_MINIMO', '270'))
        self.TOLERANCIA_MINUTOS = int(self._get_required('TOLERANCIA_MINUTOS', '5'))
        self.HORARIO_ENTRADA = self._validate_time('HORARIO_ENTRADA')
        self.HORARIO_SAIDA = self._validate_time('HORARIO_SAIDA')
        self.INTERVALO_MINIMO = int(os.getenv('INTERVALO_MINIMO', '270'))
        self.TOLERANCIA_MINUTOS = int(os.getenv('TOLERANCIA_MINUTOS', '5'))

        self.TELEGRAM_TOKEN = self._get_required('TELEGRAM_TOKEN')
        self.TELEGRAM_CHAT_ID = self._get_required('TELEGRAM_CHAT_ID')
        self.TELEGRAM_ADMIN_IDS = self._get_list('TELEGRAM_ADMIN_IDS', [])

        self.DB_PATH = os.getenv('DB_PATH', '/opt/sistema-ponto/database/ponto.db')
        self.LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
        self.LOG_DIR = os.getenv('LOG_DIR', '/opt/sistema-ponto/logs')
        self.BACKUP_DIR = os.getenv('BACKUP_DIR', '/opt/sistema-ponto/backups')
        self.BACKUP_RETENTION_DAYS = int(os.getenv('BACKUP_RETENTION_DAYS', '30'))
        self.PERICULOSIDADE = float(os.getenv('PERICULOSIDADE', '0.30'))
        self.ADICIONAL_NOTURNO = float(os.getenv('ADICIONAL_NOTURNO', '0.30'))
        self.HORAS_EXTRAS = {
            '60': float(os.getenv('HE_60', '0.60')),
            '65': float(os.getenv('HE_65', '0.65')),
            '75': float(os.getenv('HE_75', '0.75')),
            '100': float(os.getenv('HE_100', '1.00')),
            '150': float(os.getenv('HE_150', '1.50'))
        }

    def _get_required(self, key, default=None):
        value = os.getenv(key, default)
        if value is None:
            raise ConfigError(f"Configuração obrigatória não encontrada: {key}")
        return value

    def _get_float(self, key, default=None):
        try:
            value = os.getenv(key, default)
            if value is None:
                raise ConfigError(f"Configuração obrigatória não encontrada: {key}")
            return float(value)
        except ValueError:
            raise ConfigError(f"Valor inválido para {key}: deve ser um número")

    def _get_list(self, key, default=None):
        value = os.getenv(key)
        if value:
            return [item.strip() for item in value.split(',')]
        return default

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = Config()
        return cls._instance