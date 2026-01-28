# config/config.py
import datetime
import os
import logging
from pathlib import Path
import time
from dotenv import load_dotenv
from datetime import datetime, time, timezone, timedelta
import pytz

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
            try:
                self.logger = logging.getLogger('Config')
                if not self.logger.handlers:
                    # Configura logger básico se não houver handlers
                    handler = logging.StreamHandler()
                    handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
                    self.logger.addHandler(handler)
                    self.logger.setLevel(logging.INFO)
            except Exception as e:
                print(f"Erro ao configurar logger: {e}")
                self.logger = logging.getLogger('Config')
            
            self._load_config()
            Config._initialized = True

    def _load_config(self):
        """Carrega e valida todas as configurações"""
        try:
            # Carregar variáveis de ambiente
            load_dotenv(override=True)
            
            # Carregar e validar configurações
            self._validate_and_load_configs()
            
            # Criar diretórios necessários
            self._criar_diretorios()
            
        except Exception as e:
            self.logger.critical(f"Falha crítica na configuração: {str(e)}")
            raise RuntimeError("Configuração inválida") from e

    def _validate_and_load_configs(self):
        """Valida e carrega todas as variáveis"""
        try:
            # Configurações de fuso horário
            self.TIMEZONE = os.getenv('TIMEZONE', 'America/Sao_Paulo')
            try:
                self.TZ_OBJ = pytz.timezone(self.TIMEZONE)
            except pytz.exceptions.UnknownTimeZoneError:
                self.logger.warning(f"Fuso horário '{self.TIMEZONE}' desconhecido, usando America/Sao_Paulo")
                self.TIMEZONE = 'America/Sao_Paulo'
                self.TZ_OBJ = pytz.timezone(self.TIMEZONE)
            
            # Configurações financeiras
            self.SALARIO_BASE = self._get_float('SALARIO_BASE')
            
            # Configurações de horário
            self.HORARIO_ENTRADA = self._validar_horario('HORARIO_ENTRADA')
            self.HORARIO_SAIDA = self._validar_horario('HORARIO_SAIDA')
            self.INTERVALO_MINIMO = int(os.getenv('INTERVALO_MINIMO', '270'))
            self.TOLERANCIA_MINUTOS = int(os.getenv('TOLERANCIA_MINUTOS', '5'))
            
            # Configurações do sistema
            self.URL_SISTEMA = self._get_required('URL_SISTEMA')
            self.LOGIN = self._get_required('LOGIN')
            self.SENHA = self._get_required('SENHA')
            
            # Configurações do Telegram
            self.TELEGRAM_TOKEN = self._get_required('TELEGRAM_TOKEN')
            self.TELEGRAM_CHAT_ID = self._get_required('TELEGRAM_CHAT_ID')
            self.TELEGRAM_ADMIN_IDS = self._get_list('TELEGRAM_ADMIN_IDS')
            
            # Configurações de banco de dados
            self.DB_PATH = os.path.abspath(os.getenv('DB_PATH', './database/ponto.db'))
            
            # Configurações de log
            self.LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
            self.LOG_DIR = os.path.abspath(os.getenv('LOG_DIR', './logs'))
            
            # Configurações de backup
            self.BACKUP_DIR = os.path.abspath(os.getenv('BACKUP_DIR', './backups'))
            self.BACKUP_RETENTION_DAYS = int(os.getenv('BACKUP_RETENTION_DAYS', '30'))
            
            # Configurações de cálculos
            self.PERICULOSIDADE = float(os.getenv('PERICULOSIDADE', '0.30'))
            self.ADICIONAL_NOTURNO = float(os.getenv('ADICIONAL_NOTURNO', '0.30'))
            self.HORAS_EXTRAS = {
                '60': float(os.getenv('HE_60', '0.60')),
                '65': float(os.getenv('HE_65', '0.65')),
                '75': float(os.getenv('HE_75', '0.75')),
                '100': float(os.getenv('HE_100', '1.00')),
                '150': float(os.getenv('HE_150', '1.50'))
            }
            
        except Exception as e:
            self.logger.error(f"Erro ao carregar configurações: {str(e)}")
            raise

    def _validar_horario(self, chave):
        """Valida formato HH:MM:SS"""
        valor = os.getenv(chave)
        if not valor:
            raise ConfigError(f"Variável {chave} não definida")
        try:
            # Adiciona segundos se não fornecidos
            if len(valor.split(':')) == 2:
                valor = f"{valor}:00"
                
            h, m, s = map(int, valor.split(':'))
            return time(h, m, s)  # Retorna objeto time
            
        except (ValueError, TypeError) as e:
            raise ConfigError(f"Formato inválido para {chave}. Use HH:MM ou HH:MM:SS: {str(e)}")
        
    def _criar_diretorios(self):
        """Garante a existência dos diretórios necessários"""
        diretorios = [
            self.LOG_DIR,
            self.BACKUP_DIR,
            os.path.dirname(self.DB_PATH)
        ]
        
        for diretorio in diretorios:
            os.makedirs(diretorio, exist_ok=True)
            self.logger.debug(f"Diretório verificado/criado: {diretorio}")

    def _get_required(self, key):
        """Obtém variável obrigatória"""
        value = os.getenv(key)
        if not value:
            raise ConfigError(f"Variável obrigatória faltando: {key}")
        return value

    def _get_float(self, key):
        """Obtém e converte para float"""
        value = self._get_required(key)
        try:
            return float(value)
        except ValueError:
            raise ConfigError(f"Valor inválido para {key}. Deve ser numérico")

    def _get_list(self, key):
        """Obtém lista de valores"""
        value = os.getenv(key, '')
        return [item.strip() for item in value.split(',') if item.strip()]

    @classmethod
    def get_instance(cls):
        """Retorna a instância singleton"""
        if cls._instance is None:
            cls._instance = Config()
        return cls._instance
    
    def get_now(self):
        """Retorna o horário atual com timezone configurado"""
        return datetime.now(self.TZ_OBJ)