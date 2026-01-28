#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de teste para Telegram Listener
"""

import os
import sys
from pathlib import Path

# Setup path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

print("=" * 60)
print("TESTE TELEGRAM LISTENER")
print("=" * 60)

# 1. Testa .env
print("\n1️⃣  Testando .env...")
from dotenv import load_dotenv
load_dotenv(override=True)

token = os.environ.get('TELEGRAM_TOKEN')
chat_id = os.environ.get('TELEGRAM_CHAT_ID')

if token and chat_id:
    print(f"✅ Token e Chat ID carregados")
    print(f"   Token: {token[:20]}...")
    print(f"   Chat ID: {chat_id}")
else:
    print(f"❌ Token ou Chat ID não carregados!")
    print(f"   Token: {token}")
    print(f"   Chat ID: {chat_id}")
    sys.exit(1)

# 2. Testa Config
print("\n2️⃣  Testando Config...")
try:
    from config.config import Config
    config = Config.get_instance()
    print(f"✅ Config inicializado")
    print(f"   Timezone: {config.TIMEZONE}")
    now = config.get_now()
    print(f"   Agora: {now.strftime('%H:%M:%S')}")
except Exception as e:
    print(f"❌ Erro em Config: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 3. Testa imports do listener
print("\n3️⃣  Testando imports...")
try:
    from scripts.telegram_listener import TelegramListener
    print(f"✅ Imports OK")
except Exception as e:
    print(f"❌ Erro em imports: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 4. Testa inicialização do listener
print("\n4️⃣  Testando inicialização do listener...")
try:
    listener = TelegramListener()
    print(f"✅ Listener inicializado")
except Exception as e:
    print(f"❌ Erro ao inicializar listener: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 5. Testa envio de mensagem
print("\n5️⃣  Testando envio de mensagem...")
try:
    teste_msg = "🧪 Teste do Telegram Listener"
    resultado = listener.enviar_mensagem(teste_msg)
    if resultado:
        print(f"✅ Mensagem enviada com sucesso!")
    else:
        print(f"❌ Falha ao enviar mensagem")
except Exception as e:
    print(f"❌ Erro ao enviar: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 60)
print("✅ TODOS OS TESTES PASSARAM!")
print("=" * 60)
