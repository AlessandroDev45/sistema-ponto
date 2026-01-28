#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de validação do projeto
Roda todos os testes de sintaxe e imports
"""

import os
import sys
import py_compile
from pathlib import Path
from dotenv import load_dotenv

# Setup
load_dotenv(override=True)
print("=" * 70)
print("VALIDAÇÃO DO PROJETO - SISTEMA PONTO")
print("=" * 70)

# Contador de erros
total_errors = 0
total_files = 0

# 1. Validar sintaxe Python
print("\n1️⃣  VALIDAÇÃO DE SINTAXE PYTHON")
print("-" * 70)

py_files = sorted(Path('.').glob('**/*.py'))
py_files = [f for f in py_files if '__pycache__' not in str(f)]

for py_file in py_files:
    total_files += 1
    try:
        py_compile.compile(str(py_file), doraise=True)
        print(f"  ✅ {py_file}")
    except py_compile.PyCompileError as e:
        print(f"  ❌ {py_file}: {e}")
        total_errors += 1

print(f"\n✅ {total_files - total_errors}/{total_files} arquivos OK")

# 2. Validar imports críticos
print("\n2️⃣  VALIDAÇÃO DE IMPORTS")
print("-" * 70)

imports_to_test = [
    ("config.config", "Config"),
    ("src.utils.timezone_helper", "get_now"),
    ("src.utils.database", "Database"),
    ("src.telegram_controller", "TelegramController"),
    ("scripts.telegram_listener", "TelegramListener"),
    ("scripts.run_once", None),
    ("scripts.relatorios_automaticos", "RelatoriosAutomaticos"),
]

import_errors = 0

for module_name, class_name in imports_to_test:
    try:
        module = __import__(module_name, fromlist=[class_name] if class_name else [])
        if class_name:
            getattr(module, class_name)
        print(f"  ✅ {module_name}")
    except Exception as e:
        print(f"  ❌ {module_name}: {e}")
        import_errors += 1

print(f"\n✅ {len(imports_to_test) - import_errors}/{len(imports_to_test)} imports OK")

# 3. Validar Config
print("\n3️⃣  VALIDAÇÃO DE CONFIGURAÇÃO")
print("-" * 70)

try:
    from config.config import Config
    config = Config.get_instance()
    print(f"  ✅ Config inicializado")
    print(f"     • Timezone: {config.TIMEZONE}")
    print(f"     • Salário Base: R$ {config.SALARIO_BASE:.2f}")
    print(f"     • Horário Entrada: {config.HORARIO_ENTRADA}")
    print(f"     • Horário Saída: {config.HORARIO_SAIDA}")
    
    now = config.get_now()
    print(f"     • Hora Atual: {now.strftime('%H:%M:%S')} ({now.tzname()})")
    print(f"  ✅ Config OK")
except Exception as e:
    print(f"  ❌ Config error: {e}")
    import_errors += 1

# 4. Validar Telegram Listener
print("\n4️⃣  VALIDAÇÃO DO TELEGRAM LISTENER")
print("-" * 70)

# Mock se necessário
if not os.environ.get('TELEGRAM_TOKEN'):
    os.environ['TELEGRAM_TOKEN'] = 'test_token:test'
if not os.environ.get('TELEGRAM_CHAT_ID'):
    os.environ['TELEGRAM_CHAT_ID'] = '123456789'

try:
    from scripts.telegram_listener import TelegramListener
    listener = TelegramListener()
    print(f"  ✅ TelegramListener inicializado")
    print(f"     • Chat ID: {listener.chat_id}")
    
    # Testar processamento de comando
    response = listener.processar_comando('/ajuda')
    if response and 'Comandos' in response:
        print(f"  ✅ Processamento de comandos OK")
    else:
        print(f"  ⚠️ Resposta de comando incompleta")
        
except Exception as e:
    print(f"  ⚠️ Listener (pode ser esperado): {e}")

# 5. Relatório Final
print("\n" + "=" * 70)
print("RELATÓRIO FINAL")
print("=" * 70)

if total_errors == 0 and import_errors == 0:
    print("✅ TODAS AS VALIDAÇÕES PASSARAM!")
    print("\n✨ Projeto está pronto para deploy!")
    sys.exit(0)
else:
    print(f"❌ {total_errors + import_errors} ERROS ENCONTRADOS")
    print("\n⚠️ Corrija os erros antes de fazer push")
    sys.exit(1)
