# src/utils/timezone_helper.py
"""
Helper para gerenciar horários com timezone configurado
Fornece funções para substituir datetime.now() em todo o projeto
"""

from datetime import datetime
from config.config import Config


def get_now():
    """Retorna a data/hora atual com timezone configurado"""
    config = Config.get_instance()
    return config.get_now()


def get_now_date():
    """Retorna apenas a data atual com timezone configurado"""
    return get_now().date()


def get_now_time():
    """Retorna apenas a hora atual com timezone configurado"""
    return get_now().time()


def get_now_formatted(fmt='%H:%M:%S'):
    """Retorna o horário atual formatado"""
    return get_now().strftime(fmt)
