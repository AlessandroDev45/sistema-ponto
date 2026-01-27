#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Listener do Telegram para GitHub Actions.
Roda periodicamente, verifica comandos e fica ativo por 5 minutos se houver interação.
"""

import os
import sys
import time
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Garante que o root esteja no path
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
sys.path.append(root_dir)

# Tempo máximo de sessão ativa (segundos)
TEMPO_SESSAO = 300  # 5 minutos
INTERVALO_POLLING = 3  # segundos entre verificações


class TelegramListener:
    def __init__(self):
        load_dotenv(override=True)
        self.token = os.environ.get('TELEGRAM_TOKEN')
        self.chat_id = os.environ.get('TELEGRAM_CHAT_ID', '').strip()
        self.ultimo_update_id = 0
        self.db = None
        self.sistema = None
        
        if not self.token or not self.chat_id:
            raise ValueError("TELEGRAM_TOKEN e TELEGRAM_CHAT_ID são obrigatórios")
        
        # Tenta conectar ao banco
        try:
            from src.utils.database import Database
            self.db = Database()
            print("✅ Banco de dados conectado")
        except Exception as e:
            print(f"⚠️ Banco indisponível: {e}")
    
    def enviar_mensagem(self, texto):
        """Envia mensagem para o Telegram"""
        try:
            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            response = requests.post(url, json={
                'chat_id': self.chat_id,
                'text': texto,
                'parse_mode': 'HTML'
            }, timeout=10)
            return response.status_code == 200
        except Exception as e:
            print(f"Erro ao enviar mensagem: {e}")
            return False
    
    def get_updates(self):
        """Busca novas mensagens do Telegram"""
        try:
            url = f"https://api.telegram.org/bot{self.token}/getUpdates"
            params = {'offset': self.ultimo_update_id + 1, 'timeout': 5}
            response = requests.get(url, params=params, timeout=15)
            
            if response.status_code != 200:
                return []
            
            data = response.json()
            if not data.get('ok'):
                return []
            
            updates = data.get('result', [])
            if updates:
                self.ultimo_update_id = updates[-1]['update_id']
            
            return updates
        except Exception as e:
            print(f"Erro ao buscar updates: {e}")
            return []
    
    def processar_comando(self, texto):
        """Processa um comando e retorna a resposta"""
        texto = texto.lower().strip()
        
        # Comandos de controle
        if texto in ['/pausar', 'pausar', '⏸️ pausar sistema']:
            if self.db:
                self.db.registrar_configuracao('sistema_pausado', 'true')
            return "⏸️ Sistema PAUSADO\nO registro automático está desativado."
        
        elif texto in ['/retomar', 'retomar', '▶️ retomar sistema']:
            if self.db:
                self.db.registrar_configuracao('sistema_pausado', 'false')
            return "▶️ Sistema RETOMADO\nO registro automático está ativado."
        
        elif texto in ['/status', 'status', '📊 status']:
            pausado = False
            if self.db:
                estado = self.db.obter_configuracao('sistema_pausado')
                pausado = estado == 'true'
            
            hoje = datetime.now().date()
            registros_hoje = []
            if self.db:
                registros = self.db.obter_registros_dia(hoje)
                for reg in registros:
                    data_hora_str = reg[1]
                    if isinstance(data_hora_str, str):
                        dt = datetime.strptime(data_hora_str.split('.')[0], '%Y-%m-%d %H:%M:%S')
                    else:
                        dt = data_hora_str
                    registros_hoje.append(f"  • {dt.strftime('%H:%M')} - {reg[2]}")
            
            status = "🔴 Pausado" if pausado else "🟢 Ativo"
            msg = f"<b>📊 Status do Sistema</b>\n\nEstado: {status}\n\n"
            msg += f"<b>Registros de Hoje ({hoje.strftime('%d/%m')}):</b>\n"
            if registros_hoje:
                msg += "\n".join(registros_hoje)
            else:
                msg += "Nenhum registro"
            
            return msg
        
        elif texto in ['/registrar', 'registrar', '🕒 registrar ponto']:
            return self.executar_registro()
        
        elif texto in ['/ajuda', 'ajuda', '/help', '❓ ajuda']:
            return (
                "<b>📋 Comandos Disponíveis</b>\n\n"
                "/registrar - Registrar ponto agora\n"
                "/pausar - Pausar registros automáticos\n"
                "/retomar - Retomar registros automáticos\n"
                "/status - Ver status do sistema\n"
                "/ajuda - Mostrar esta ajuda"
            )
        
        return None  # Comando não reconhecido
    
    def executar_registro(self):
        """Executa o registro de ponto"""
        try:
            from main import SistemaPonto
            
            if not self.sistema:
                self.sistema = SistemaPonto()
            
            # Verifica registros existentes no período
            hoje = datetime.now().date()
            hora = datetime.now().hour
            
            if hora < 12:
                periodo = 'manhã'
            elif hora < 18:
                periodo = 'tarde'
            else:
                periodo = 'noite'
            
            resultado = self.sistema.automacao.registrar_ponto(force=True)
            
            if resultado['sucesso']:
                agora = datetime.now()
                msg = f"✅ Ponto registrado às {agora.strftime('%H:%M')}"
                
                # Calcula total se for saída
                if self.db:
                    total = self.db.calcular_total_horas_dia(hoje)
                    if total and total['registros_completos']:
                        msg += f"\n\n📊 Total do dia: {total['total_formatado']}"
                
                return msg
            else:
                return f"❌ Falha: {resultado['mensagem']}"
                
        except Exception as e:
            return f"❌ Erro ao registrar: {str(e)}"
    
    def executar(self):
        """Loop principal - verifica comandos e mantém sessão ativa se necessário"""
        print(f"🤖 Telegram Listener iniciado às {datetime.now().strftime('%H:%M:%S')}")
        print(f"⏱️ Sessão máxima: {TEMPO_SESSAO // 60} minutos")
        
        inicio = time.time()
        sessao_ativa = False
        ultimo_comando = None
        
        # Primeira verificação
        updates = self.get_updates()
        
        for update in updates:
            message = update.get('message', {})
            msg_chat_id = str(message.get('chat', {}).get('id', ''))
            texto = message.get('text', '')
            
            if msg_chat_id != self.chat_id:
                continue
            
            # Verifica se mensagem é recente (últimos 5 minutos)
            msg_time = datetime.fromtimestamp(message.get('date', 0))
            if (datetime.now() - msg_time).total_seconds() > 300:
                continue
            
            print(f"📨 Comando recebido: {texto}")
            resposta = self.processar_comando(texto)
            
            if resposta:
                self.enviar_mensagem(resposta)
                sessao_ativa = True
                ultimo_comando = time.time()
                print(f"✅ Resposta enviada")
        
        # Se houve comando, mantém sessão ativa por 5 minutos
        if sessao_ativa:
            self.enviar_mensagem("🟢 Sessão ativa por 5 minutos. Envie comandos!")
            print("🔄 Sessão ativa - aguardando mais comandos...")
            
            while (time.time() - inicio) < TEMPO_SESSAO:
                time.sleep(INTERVALO_POLLING)
                
                updates = self.get_updates()
                
                for update in updates:
                    message = update.get('message', {})
                    msg_chat_id = str(message.get('chat', {}).get('id', ''))
                    texto = message.get('text', '')
                    
                    if msg_chat_id != self.chat_id:
                        continue
                    
                    print(f"📨 Comando: {texto}")
                    resposta = self.processar_comando(texto)
                    
                    if resposta:
                        self.enviar_mensagem(resposta)
                        ultimo_comando = time.time()
                        print(f"✅ Resposta enviada")
                
                # Mostra tempo restante a cada minuto
                tempo_passado = int(time.time() - inicio)
                if tempo_passado % 60 == 0 and tempo_passado > 0:
                    restante = (TEMPO_SESSAO - tempo_passado) // 60
                    print(f"⏱️ {restante} minutos restantes")
            
            self.enviar_mensagem("🔴 Sessão encerrada. Envie um comando para reativar.")
        else:
            print("💤 Nenhum comando recente - encerrando")
        
        # Cleanup
        if self.sistema:
            try:
                self.sistema.encerrar_sistema()
            except:
                pass
        
        print(f"👋 Listener encerrado às {datetime.now().strftime('%H:%M:%S')}")


def main():
    try:
        listener = TelegramListener()
        listener.executar()
    except Exception as e:
        print(f"❌ Erro fatal: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
