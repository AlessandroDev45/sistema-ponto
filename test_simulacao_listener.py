#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simulação COMPLETA do que vai acontecer quando o listener rodar
Testa com a FILA REAL do Telegram
"""

import os
import sys
import requests
from datetime import datetime
from dotenv import load_dotenv

# Garante que o root esteja no path
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = current_dir
sys.path.append(root_dir)

load_dotenv(override=True)
token = os.environ.get('TELEGRAM_TOKEN')
chat_id = os.environ.get('TELEGRAM_CHAT_ID', '').strip()

print("=" * 70)
print("🧪 SIMULAÇÃO COMPLETA DO TELEGRAM LISTENER")
print("=" * 70)

# Busca updates REAIS da fila
print("\n📡 Buscando fila REAL do Telegram...")
url = f'https://api.telegram.org/bot{token}/getUpdates'
response = requests.get(url, timeout=10)
data = response.json()
updates = data.get('result', [])

print(f"✅ {len(updates)} mensagens encontradas na fila\n")

if not updates:
    print("❌ Nenhuma mensagem na fila!")
    sys.exit(1)

# Mostra antes
print("🔴 FILA ATUAL (antes de processar):")
print("-" * 70)
for i, u in enumerate(updates, 1):
    msg = u.get('message', {})
    texto = msg.get('text', 'N/A')
    timestamp = msg.get('date', 0)
    data_fmt = datetime.fromtimestamp(timestamp).strftime('%d/%m %H:%M:%S')
    print(f"  {i}. [{data_fmt}] {texto}")

# Simula o listener
print("\n" + "=" * 70)
print("🤖 INICIANDO SIMULAÇÃO DO LISTENER")
print("=" * 70)

try:
    from scripts.telegram_listener import TelegramListener
    
    listener = TelegramListener()
    print("\n✅ TelegramListener criado")
    
    # Deduplica
    print("\n🔄 Aplicando deduplicação...")
    deduplic = listener._deduplica_comandos(updates)
    
    print(f"📊 {len(updates)} → {len(deduplic)} mensagens (economia de {len(updates) - len(deduplic)})")
    
    # Processa cada uma
    print("\n🟢 PROCESSANDO MENSAGENS:")
    print("-" * 70)
    
    respostas_enviadas = 0
    
    for i, update in enumerate(deduplic, 1):
        message = update.get('message', {})
        msg_chat_id = str(message.get('chat', {}).get('id', ''))
        texto = message.get('text', '')
        timestamp = message.get('date', 0)
        data_fmt = datetime.fromtimestamp(timestamp).strftime('%d/%m %H:%M:%S')
        
        if msg_chat_id != chat_id:
            print(f"  {i}. ❌ Chat ID errado (ignorado)")
            continue
        
        print(f"\n  {i}. 📨 COMANDO: {texto}")
        print(f"      Hora: {data_fmt}")
        
        # Processa
        resposta = listener.processar_comando(texto)
        
        if resposta:
            # Mostra resposta
            resposta_preview = resposta.replace('<b>', '').replace('</b>', '').replace('<i>', '').replace('</i>', '')[:60]
            print(f"      ✅ RESPOSTA: {resposta_preview}...")
            respostas_enviadas += 1
        else:
            print(f"      ⚠️ Sem resposta")
    
    print("\n" + "=" * 70)
    print(f"✅ SIMULAÇÃO COMPLETA")
    print("=" * 70)
    print(f"\n📊 Resumo:")
    print(f"   • Mensagens na fila: {len(updates)}")
    print(f"   • Após deduplicação: {len(deduplic)}")
    print(f"   • Respostas que serão enviadas: {respostas_enviadas}")
    print(f"\n💚 PRONTO PRA RODAR NO GITHUB ACTIONS!")
    
except Exception as e:
    print(f"\n❌ ERRO NA SIMULAÇÃO: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
