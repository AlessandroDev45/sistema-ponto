#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
from dotenv import load_dotenv

# Garante que o root esteja no path
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
sys.path.append(root_dir)

from main import SistemaPonto
from src.utils.database import Database


def verificar_sistema_pausado():
    """Verifica no banco de dados se o sistema está pausado"""
    try:
        db = Database()
        estado = db.obter_configuracao('sistema_pausado')
        return estado == 'true'
    except Exception as e:
        print(f"Aviso: Não foi possível verificar estado de pausa no banco: {e}")
        return False


def main():
    load_dotenv(override=True)
    
    # Verifica se o sistema está pausado (no banco de dados)
    if verificar_sistema_pausado():
        print("⏸️ Sistema PAUSADO - registro ignorado")
        print("Para retomar, envie /retomar no Telegram")
        return
    
    sistema = None
    try:
        sistema = SistemaPonto()
        sistema.registrar_ponto_automatico()
    finally:
        if sistema:
            sistema.encerrar_sistema()


if __name__ == "__main__":
    main()
