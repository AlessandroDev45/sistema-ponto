import os
from dotenv import load_dotenv
import logging
from pathlib import Path

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
        try:
            env_locations = [
                Path.cwd() / '.env',
                Path.home() / '.sistema-ponto/.env',
                Path('/opt/sistema-ponto/.env'),
                Path('/etc/sistema-ponto/.env')
            ]

            env_file = None
            for location in env_locations:
                if location.is_file():
                    env_file = location
                    break

            if not env_file:
                raise ConfigError("Arquivo .env não encontrado")

            load_dotenv(dotenv_path=env_file)
            self.logger.info(f"Configurações carregadas de {env_file}")
            self._validate_and_load_configs()

            self.logger.debug(f"Carregado: HORARIO_ENTRADA={os.getenv('HORARIO_ENTRADA')}, HORARIO_SAIDA={os.getenv('HORARIO_SAIDA')}, SALARIO_BASE={os.getenv('SALARIO_BASE')}")

        except Exception as e:
            self.logger.error(f"Erro ao carregar configurações: {e}")
            raise ConfigError(f"Erro ao carregar configurações: {e}")

    def _validate_and_load_configs(self):
        self.SALARIO_BASE = self._get_float('SALARIO_BASE')
        self.URL_SISTEMA = self._get_required('URL_SISTEMA')
        self.LOGIN = self._get_required('LOGIN')
        self.SENHA = self._get_required('SENHA')

        self.HORARIO_ENTRADA = self._get_required('HORARIO_ENTRADA')
        self.HORARIO_SAIDA = self._get_required('HORARIO_SAIDA')
        self.INTERVALO_MINIMO = int(self._get_required('INTERVALO_MINIMO', '270'))
        self.TOLERANCIA_MINUTOS = int(self._get_required('TOLERANCIA_MINUTOS', '5'))

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