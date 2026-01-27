#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import requests
from datetime import datetime, timedelta
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
        return estado == 'true', db
    except Exception as e:
        print(f"Aviso: Não foi possível verificar estado de pausa no banco: {e}")
        return False, None


def verificar_comandos_telegram():
    """
    Verifica comandos recentes no Telegram e atualiza o estado no banco.
    Retorna: 'pausar', 'retomar', 'registrar' ou None
    """
    try:
        token = os.environ.get('TELEGRAM_TOKEN')
        chat_id = os.environ.get('TELEGRAM_CHAT_ID', '').strip()
        
        if not token or not chat_id:
            print("Aviso: Token ou Chat ID do Telegram não configurados")
            return None, None
        
        # Busca últimas mensagens do Telegram
        url = f"https://api.telegram.org/bot{token}/getUpdates"
        response = requests.get(url, timeout=10)
        
        if response.status_code != 200:
            print(f"Aviso: Erro ao buscar mensagens do Telegram: {response.status_code}")
            return None, None
        
        data = response.json()
        if not data.get('ok') or not data.get('result'):
            return None, None
        
        # Processa mensagens das últimas 2 horas (janela de tempo para comandos)
        agora = datetime.now()
        limite = agora - timedelta(hours=2)
        
        ultimo_comando = None
        ultimo_comando_time = None
        
        for update in data['result']:
            message = update.get('message', {})
            msg_chat_id = str(message.get('chat', {}).get('id', ''))
            texto = message.get('text', '').lower().strip()
            msg_timestamp = message.get('date', 0)
            msg_time = datetime.fromtimestamp(msg_timestamp)
            
            # Só processa mensagens do chat correto e dentro da janela de tempo
            if msg_chat_id != chat_id:
                continue
            if msg_time < limite:
                continue
            
            # Verifica comandos
            if texto in ['/pausar', 'pausar', '⏸️ pausar sistema']:
                if ultimo_comando_time is None or msg_time > ultimo_comando_time:
                    ultimo_comando = 'pausar'
                    ultimo_comando_time = msg_time
            elif texto in ['/retomar', 'retomar', '▶️ retomar sistema']:
                if ultimo_comando_time is None or msg_time > ultimo_comando_time:
                    ultimo_comando = 'retomar'
                    ultimo_comando_time = msg_time
            elif texto in ['/registrar', 'registrar', '🕒 registrar ponto']:
                if ultimo_comando_time is None or msg_time > ultimo_comando_time:
                    ultimo_comando = 'registrar'
                    ultimo_comando_time = msg_time
        
        return ultimo_comando, ultimo_comando_time
        
    except Exception as e:
        print(f"Aviso: Erro ao verificar Telegram: {e}")
        return None, None


def enviar_mensagem_telegram(texto):
    """Envia mensagem para o Telegram"""
    try:
        token = os.environ.get('TELEGRAM_TOKEN')
        chat_id = os.environ.get('TELEGRAM_CHAT_ID', '').strip()
        
        if not token or not chat_id:
            return
        
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        requests.post(url, json={'chat_id': chat_id, 'text': texto}, timeout=10)
    except:
        pass


def main():
    load_dotenv(override=True)
    
    print("🔍 Verificando comandos do Telegram...")
    
    # Verifica comandos recentes no Telegram
    comando_telegram, comando_time = verificar_comandos_telegram()
    
    if comando_telegram:
        print(f"📱 Comando encontrado: /{comando_telegram} às {comando_time.strftime('%H:%M') if comando_time else 'N/A'}")
    
    # Atualiza o estado no banco conforme comando do Telegram
    pausado_no_banco, db = verificar_sistema_pausado()
    
    if comando_telegram == 'pausar':
        # Salva no banco e não registra
        if db:
            db.registrar_configuracao('sistema_pausado', 'true')
        print("⏸️ Sistema PAUSADO via Telegram - registro ignorado")
        enviar_mensagem_telegram("⏸️ Sistema pausado - registro automático cancelado")
        return
    
    elif comando_telegram == 'retomar':
        # Salva no banco e continua para registrar
        if db:
            db.registrar_configuracao('sistema_pausado', 'false')
        print("▶️ Sistema RETOMADO via Telegram")
        enviar_mensagem_telegram("▶️ Sistema retomado - prosseguindo com registro")
        pausado_no_banco = False
    
    elif comando_telegram == 'registrar':
        # Força o registro mesmo se pausado
        print("🕒 Registro FORÇADO via Telegram")
        pausado_no_banco = False
    
    # Verifica se o sistema está pausado (no banco de dados)
    if pausado_no_banco:
        print("⏸️ Sistema PAUSADO no banco - registro ignorado")
        print("Para retomar, envie /retomar no Telegram antes do próximo horário")
        enviar_mensagem_telegram("⏸️ Registro ignorado - sistema pausado\nEnvie /retomar para reativar")
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
