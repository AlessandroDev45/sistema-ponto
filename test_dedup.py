#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Teste de deduplicação de comandos
"""

from scripts.telegram_listener import TelegramListener

listener = TelegramListener()

# Simula updates duplicados
updates_teste = [
    {'message': {'chat': {'id': 5899118807}, 'text': '/relatorio_anual', 'date': 1704000000}},
    {'message': {'chat': {'id': 5899118807}, 'text': '/status', 'date': 1704000001}},
    {'message': {'chat': {'id': 5899118807}, 'text': '/status', 'date': 1704000002}},
    {'message': {'chat': {'id': 5899118807}, 'text': '/status', 'date': 1704000003}},
    {'message': {'chat': {'id': 5899118807}, 'text': '/status', 'date': 1704000004}},
    {'message': {'chat': {'id': 5899118807}, 'text': '/menu', 'date': 1704000005}},
    {'message': {'chat': {'id': 5899118807}, 'text': '/status', 'date': 1704000006}},
    {'message': {'chat': {'id': 5899118807}, 'text': '/relatorio_anual', 'date': 1704000007}},
]

print('📨 TESTE DE DEDUPLICAÇÃO')
print('=' * 50)
print('\n🔴 ANTES (8 mensagens):')
for i, u in enumerate(updates_teste, 1):
    texto = u['message']['text']
    print(f'  {i}. {texto}')

deduplic = listener._deduplica_comandos(updates_teste)

print('\n🟢 DEPOIS (após deduplicação):')
for i, u in enumerate(deduplic, 1):
    texto = u['message']['text']
    print(f'  {i}. {texto}')

print(f'\n✅ Redução: {len(updates_teste)} → {len(deduplic)} mensagens')
print(f'💰 Economia: {len(updates_teste) - len(deduplic)} respostas evitadas')
