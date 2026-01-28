#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para testar o Telegram Listener localmente
Simula um comando /status e verifica se a resposta é enviada
"""

import os
import sys
import time
from dotenv import load_dotenv

# Garante que o root esteja no path
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = current_dir
sys.path.append(root_dir)

def test_telegram():
    """Testa a conexão com o Telegram e o banco de dados"""
    load_dotenv(override=True)
    
    token = os.environ.get('TELEGRAM_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID', '').strip()
    
    print("=" * 60)
    print("🧪 TESTE DO TELEGRAM LISTENER")
    print("=" * 60)
    
    print(f"\n📋 Configuração:")
    print(f"   Token: {token[:20]}..." if token else "   Token: ❌ NÃO CONFIGURADO")
    print(f"   Chat ID: {chat_id}" if chat_id else "   Chat ID: ❌ NÃO CONFIGURADO")
    
    if not token or not chat_id:
        print("\n❌ Credenciais incompletas!")
        return False
    
    print("\n📱 Testando API do Telegram...")
    import requests
    
    # Teste 1: Verificar token
    print("\n1️⃣ Testando token...")
    try:
        url = f"https://api.telegram.org/bot{token}/getMe"
        response = requests.get(url, timeout=10)
        data = response.json()
        
        if data.get('ok'):
            bot_info = data.get('result', {})
            print(f"   ✅ Token válido!")
            print(f"   Bot: {bot_info.get('first_name')} (@{bot_info.get('username')})")
        else:
            print(f"   ❌ Token inválido: {data.get('description')}")
            return False
    except Exception as e:
        print(f"   ❌ Erro: {e}")
        return False
    
    # Teste 2: Buscar updates
    print("\n2️⃣ Buscando updates...")
    try:
        url = f"https://api.telegram.org/bot{token}/getUpdates"
        response = requests.get(url, timeout=10)
        data = response.json()
        
        if data.get('ok'):
            updates = data.get('result', [])
            print(f"   ✅ {len(updates)} updates encontrados")
            
            if updates:
                print("\n   📨 Últimas mensagens:")
                for u in updates[-5:]:  # Últimas 5
                    msg = u.get('message', {})
                    msg_chat_id = msg.get('chat', {}).get('id')
                    texto = msg.get('text', 'sem texto')
                    timestamp = msg.get('date', 0)
                    from datetime import datetime
                    data_fmt = datetime.fromtimestamp(timestamp).strftime('%d/%m %H:%M:%S')
                    
                    marca = "✅" if str(msg_chat_id) == str(chat_id) else "⚠️"
                    print(f"      {marca} [{data_fmt}] Chat {msg_chat_id}: {texto[:50]}")
        else:
            print(f"   ❌ Erro: {data.get('description')}")
            return False
    except Exception as e:
        print(f"   ❌ Erro: {e}")
        return False
    
    # Teste 3: Enviar mensagem de teste
    print("\n3️⃣ Enviando mensagem de teste...")
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            'chat_id': chat_id,
            'text': "✅ <b>Teste do Telegram Listener</b>\n\nSe você vê isso, a API está funcionando!",
            'parse_mode': 'HTML'
        }
        response = requests.post(url, json=payload, timeout=10)
        data = response.json()
        
        if data.get('ok'):
            print(f"   ✅ Mensagem enviada com sucesso!")
            msg_id = data.get('result', {}).get('message_id')
            print(f"   Message ID: {msg_id}")
        else:
            print(f"   ❌ Erro: {data.get('description')}")
            return False
    except Exception as e:
        print(f"   ❌ Erro: {e}")
        return False
    
    # Teste 4: Verificar banco de dados
    print("\n4️⃣ Testando banco de dados...")
    try:
        from src.utils.database import Database
        db = Database()
        print(f"   ✅ Banco conectado!")
        
        # Tenta obter uma configuração
        config = db.obter_configuracao('sistema_pausado')
        print(f"   Sistema pausado: {config if config else 'não configurado'}")
        
    except Exception as e:
        print(f"   ⚠️ Erro ao conectar banco: {e}")
    
    # Teste 5: Testar listener
    print("\n5️⃣ Testando Telegram Listener...")
    try:
        from scripts.telegram_listener import TelegramListener
        
        listener = TelegramListener()
        print(f"   ✅ TelegramListener instanciado!")
        
        # Testa processar comando
        resposta = listener.processar_comando('/status')
        if resposta:
            print(f"   ✅ Comando /status respondeu:")
            print(f"\n{resposta}\n")
        else:
            print(f"   ⚠️ /status retornou None")
        
    except Exception as e:
        print(f"   ❌ Erro: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n" + "=" * 60)
    print("✅ TODOS OS TESTES PASSARAM!")
    print("=" * 60)
    return True

if __name__ == "__main__":
    success = test_telegram()
    sys.exit(0 if success else 1)
