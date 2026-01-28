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
        self.ultimo_update_id = self._carregar_ultimo_update_id()
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
    
    def _carregar_ultimo_update_id(self):
        """Carrega o último update_id processado de um arquivo"""
        try:
            import json
            arquivo = 'temp/.telegram_state.json'
            if os.path.exists(arquivo):
                with open(arquivo, 'r') as f:
                    data = json.load(f)
                    ultimo_id = data.get('ultimo_update_id', 0)
                    print(f"📋 Carregado último update_id: {ultimo_id}")
                    return ultimo_id
        except Exception as e:
            print(f"⚠️ Erro ao carregar estado: {e}")
        
        return 0
    
    def _salvar_ultimo_update_id(self):
        """Salva o último update_id processado"""
        try:
            import json
            os.makedirs('temp', exist_ok=True)
            arquivo = 'temp/.telegram_state.json'
            with open(arquivo, 'w') as f:
                json.dump({'ultimo_update_id': self.ultimo_update_id}, f)
            print(f"💾 Salvo último update_id: {self.ultimo_update_id}")
        except Exception as e:
            print(f"⚠️ Erro ao salvar estado: {e}")
    
    def enviar_mensagem(self, texto):
        """Envia mensagem para o Telegram"""
        try:
            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            payload = {
                'chat_id': self.chat_id,
                'text': texto,
                'parse_mode': 'HTML'
            }
            print(f"📤 POST {url}")
            print(f"   chat_id: {self.chat_id}")
            print(f"   text: {texto[:50]}...")
            
            response = requests.post(url, json=payload, timeout=10)
            print(f"📊 Status: {response.status_code}")
            
            if response.status_code == 200:
                print(f"✅ Mensagem enviada")
                return True
            else:
                print(f"❌ Erro: {response.status_code} - {response.text[:100]}")
                return False
        except Exception as e:
            print(f"❌ Erro ao enviar mensagem: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _limpar_updates_processados(self):
        """Remove updates já processados da fila do Telegram"""
        try:
            if self.ultimo_update_id <= 0:
                return
            
            url = f"https://api.telegram.org/bot{self.token}/deleteMessage"
            # Na verdade, para remover updates usamos offset na próxima chamada
            # Mas também podemos usar a API de getUpdates com offset
            # Vou fazer uma chamada vazia com offset+1 para indicar que processamos
            print(f"🗑️ Limpando updates até ID {self.ultimo_update_id}")
            
        except Exception as e:
            print(f"⚠️ Erro ao limpar: {e}")
    
    def get_updates(self):
        """Busca novas mensagens do Telegram"""
        try:
            url = f"https://api.telegram.org/bot{self.token}/getUpdates"
            # Sempre pega a partir do próximo não processado
            # Se ultimo_update_id = 0, pega do início (toda a fila)
            params = {'offset': self.ultimo_update_id + 1 if self.ultimo_update_id > 0 else 0, 'timeout': 5}
            print(f"🔗 GET {url}")
            print(f"   offset={params['offset']}")
            
            response = requests.get(url, params=params, timeout=15)
            print(f"📊 Status: {response.status_code}")
            
            if response.status_code != 200:
                print(f"❌ HTTP Error: {response.status_code}")
                return []
            
            data = response.json()
            print(f"✅ JSON ok: {data.get('ok')}")
            
            if not data.get('ok'):
                print(f"❌ API Error: {data.get('description', 'desconhecido')}")
                return []
            
            updates = data.get('result', [])
            print(f"📬 {len(updates)} updates")
            
            if updates:
                self.ultimo_update_id = updates[-1]['update_id']
                print(f"   Novo update_id: {self.ultimo_update_id}")
                for u in updates:
                    msg = u.get('message', {})
                    print(f"   - Chat {msg.get('chat', {}).get('id')}: {msg.get('text', 'sem texto')[:50]}")
                # Remove updates processados da fila
                self._limpar_updates_processados()
            
            return updates
        except Exception as e:
            print(f"❌ Erro ao buscar updates: {e}")
            import traceback
            traceback.print_exc()
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
            return self.mostrar_status()
        
        elif texto in ['/registrar', 'registrar', '🕒 registrar ponto']:
            return self.executar_registro()
        
        elif texto in ['/horas', 'horas', '⏰ horas trabalhadas']:
            return self.mostrar_horas()
        
        elif texto in ['/falhas', 'falhas', '❌ falhas']:
            return self.mostrar_falhas()
        
        elif texto in ['/relatorio', 'relatorio', '📄 relatório mensal']:
            return self.gerar_relatorio_mensal()
        
        elif texto in ['/relatorio_anual', 'relatorio_anual', '📅 relatório anual']:
            return self.gerar_relatorio_anual()
            return self.mostrar_menu()
        
        elif texto in ['/horarios', 'horarios', '⏰ horários']:
            return self.mostrar_horarios()
        
        elif texto.startswith('/entrada ') or texto.startswith('entrada '):
            # /entrada 07:30
            horario = texto.split(' ', 1)[1].strip()
            return self.alterar_horario('entrada', horario)
        
        elif texto.startswith('/saida ') or texto.startswith('saida '):
            # /saida 17:18
            horario = texto.split(' ', 1)[1].strip()
            return self.alterar_horario('saida', horario)
        
        elif texto in ['/ajuda', 'ajuda', '/help', '❓ ajuda']:
            return (
                "<b>📋 Comandos Disponíveis</b>\n\n"
                "🕒 /registrar - Registrar ponto agora\n"
                "⏸️ /pausar - Pausar registros automáticos\n"
                "▶️ /retomar - Retomar registros automáticos\n"
                "📊 /status - Ver status do sistema\n"
                "⏰ /horas - Horas trabalhadas hoje\n"
                "❌ /falhas - Ver falhas recentes\n"
                "📄 /relatorio - Relatório do mês\n"
                "📋 /menu - Mostrar menu\n"
                "⏰ /horarios - Ver horários configurados\n"
                "/entrada HH:MM - Alterar horário entrada\n"
                "/saida HH:MM - Alterar horário saída\n"
                "❓ /ajuda - Esta ajuda"
            )
        
        return None  # Comando não reconhecido

    def mostrar_status(self):
        """Mostra status do sistema"""
        try:
            pausado = False
            if self.db:
                try:
                    estado = self.db.obter_configuracao('sistema_pausado')
                    pausado = estado == 'true'
                except Exception as e:
                    print(f"⚠️ Erro ao verificar pausa: {e}")
            
            hoje = datetime.now().date()
            registros_hoje = []
            total_horas = None
            
            if self.db:
                try:
                    registros = self.db.obter_registros_dia(hoje)
                    print(f"📋 {len(registros) if registros else 0} registros encontrados para {hoje}")
                    
                    if registros:
                        for reg in registros:
                            data_hora_str = reg[1]
                            if isinstance(data_hora_str, str):
                                dt = datetime.strptime(data_hora_str.split('.')[0], '%Y-%m-%d %H:%M:%S')
                            else:
                                dt = data_hora_str
                            registros_hoje.append(f"  • {dt.strftime('%H:%M')} - {reg[2]}")
                    
                    total_horas = self.db.calcular_total_horas_dia(hoje)
                except Exception as e:
                    print(f"⚠️ Erro ao buscar registros: {e}")
            else:
                print("⚠️ Banco de dados não disponível para obter registros")
            
            status = "🔴 Pausado" if pausado else "🟢 Ativo"
            msg = f"<b>📊 Status do Sistema</b>\n\nEstado: {status}\n\n"
            msg += f"<b>Registros de Hoje ({hoje.strftime('%d/%m')}):</b>\n"
            
            if registros_hoje:
                msg += "\n".join(registros_hoje)
                if total_horas and total_horas.get('registros_completos'):
                    msg += f"\n\n📊 Total: {total_horas['total_formatado']}"
            else:
                msg += "Nenhum registro"
            
            return msg
        except Exception as e:
            print(f"❌ Erro ao obter status: {e}")
            return f"❌ Erro ao obter status: {e}"

    def mostrar_horarios(self):
        """Mostra os horários configurados para registro automático"""
        try:
            if not self.db:
                return "❌ Banco de dados não disponível"
            
            entrada = self.db.obter_configuracao('horario_entrada') or os.environ.get('HORARIO_ENTRADA', '07:30')
            saida = self.db.obter_configuracao('horario_saida') or os.environ.get('HORARIO_SAIDA', '17:18')
            
            return (
                f"<b>⏰ Horários Configurados</b>\n\n"
                f"🌅 Entrada: <b>{entrada}</b>\n"
                f"🌇 Saída: <b>{saida}</b>\n\n"
                f"<i>Para alterar:</i>\n"
                f"/entrada HH:MM - Altera entrada\n"
                f"/saida HH:MM - Altera saída\n\n"
                f"<i>Exemplo:</i> /entrada 08:00"
            )
        except Exception as e:
            return f"❌ Erro ao obter horários: {e}"

    def alterar_horario(self, tipo, horario):
        """Altera o horário de entrada ou saída e atualiza o cron no GitHub"""
        try:
            if not self.db:
                return "❌ Banco de dados não disponível"
            
            # Valida formato HH:MM
            import re
            if not re.match(r'^([01]?[0-9]|2[0-3]):([0-5][0-9])$', horario):
                return (
                    f"❌ Formato inválido: <b>{horario}</b>\n\n"
                    f"Use o formato HH:MM\n"
                    f"<i>Exemplo:</i> /entrada 08:00"
                )
            
            # Normaliza para HH:MM (com zero à esquerda)
            partes = horario.split(':')
            hora = int(partes[0])
            minuto = int(partes[1])
            horario_normalizado = f"{hora:02d}:{minuto:02d}"
            
            if tipo == 'entrada':
                chave = 'horario_entrada'
                emoji = '🌅'
                nome = 'ENTRADA'
            else:
                chave = 'horario_saida'
                emoji = '🌇'
                nome = 'SAÍDA'
            
            # Salva no banco
            self.db.registrar_configuracao(chave, horario_normalizado)
            
            # Tenta atualizar o cron no GitHub
            cron_atualizado = self._atualizar_cron_github(tipo, hora, minuto)
            
            msg = (
                f"✅ Horário de {nome} alterado!\n\n"
                f"{emoji} Novo horário: <b>{horario_normalizado}</b>\n\n"
            )
            
            if cron_atualizado:
                msg += "✅ Cron do GitHub atualizado automaticamente!"
            else:
                msg += "⚠️ Não foi possível atualizar o cron no GitHub.\nAtualize manualmente se necessário."
            
            return msg
        except Exception as e:
            return f"❌ Erro ao alterar horário: {e}"

    def _atualizar_cron_github(self, tipo, hora_brt, minuto):
        """Atualiza o cron.yml no GitHub via API"""
        try:
            import base64
            
            github_token = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN') or os.environ.get('token-sistema-ponto')
            if not github_token:
                print("Token do GitHub não configurado para atualizar cron")
                return False
            
            repo = "AlessandroDev45/sistema-ponto"
            file_path = ".github/workflows/cron.yml"
            
            # Converte BRT para UTC (BRT = UTC - 3)
            hora_utc = (hora_brt + 3) % 24
            
            # Obtém o arquivo atual
            url = f"https://api.github.com/repos/{repo}/contents/{file_path}"
            headers = {
                "Authorization": f"Bearer {github_token}",
                "Accept": "application/vnd.github+json"
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code != 200:
                print(f"Erro ao obter arquivo: {response.status_code}")
                return False
            
            file_data = response.json()
            sha = file_data['sha']
            content = base64.b64decode(file_data['content']).decode('utf-8')
            
            # Obtém os dois horários atuais do banco
            if self.db is None:
                return False
            entrada = self.db.obter_configuracao('horario_entrada') or '07:30'
            saida = self.db.obter_configuracao('horario_saida') or '17:18'
            
            # Parseia os horários
            ent_h, ent_m = map(int, entrada.split(':'))
            sai_h, sai_m = map(int, saida.split(':'))
            
            # Converte para UTC
            ent_h_utc = (ent_h + 3) % 24
            sai_h_utc = (sai_h + 3) % 24
            
            # Novo conteúdo do cron
            novo_cron = f'''name: Registrar ponto (cron)

on:
  workflow_dispatch:
  schedule:
    # Entrada: {entrada} BRT = {ent_h_utc:02d}:{ent_m:02d} UTC
    - cron: "{ent_m} {ent_h_utc} * * 1-5"
    # Saída: {saida} BRT = {sai_h_utc:02d}:{sai_m:02d} UTC
    - cron: "{sai_m} {sai_h_utc} * * 1-5"
'''
            
            # Obtém o resto do arquivo (a partir de "jobs:")
            jobs_start = content.find('jobs:')
            if jobs_start != -1:
                novo_cron += "\n" + content[jobs_start:]
            
            # Faz o commit
            update_data = {
                "message": f"chore: update cron schedule - {tipo} {hora_brt:02d}:{minuto:02d} BRT",
                "content": base64.b64encode(novo_cron.encode('utf-8')).decode('utf-8'),
                "sha": sha,
                "branch": "main"
            }
            
            response = requests.put(url, headers=headers, json=update_data, timeout=10)
            
            if response.status_code in [200, 201]:
                print(f"Cron atualizado: {tipo} = {hora_brt:02d}:{minuto:02d} BRT")
                return True
            else:
                print(f"Erro ao atualizar cron: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"Erro ao atualizar cron no GitHub: {e}")
            return False

    def mostrar_horas(self):
        """Mostra horas trabalhadas hoje"""
        try:
            if not self.db:
                return "❌ Banco de dados não disponível"
            
            hoje = datetime.now().date()
            total = self.db.calcular_total_horas_dia(hoje)
            
            if not total:
                return "📊 Nenhum registro de horas hoje"
            
            msg = f"<b>⏰ Horas Trabalhadas - {hoje.strftime('%d/%m/%Y')}</b>\n\n"
            
            if total['entradas'] and total['saidas']:
                msg += "<b>Registros:</b>\n"
                for i, (ent, sai) in enumerate(zip(total['entradas'], total['saidas']), 1):
                    delta = sai - ent
                    horas = int(delta.total_seconds() // 3600)
                    minutos = int((delta.total_seconds() % 3600) // 60)
                    msg += f"  {i}º: {ent.strftime('%H:%M')} → {sai.strftime('%H:%M')} ({horas}h{minutos:02d}min)\n"
            
            if total.get('registros_completos'):
                msg += f"\n<b>Total:</b> {total['total_formatado']}"
            else:
                msg += "\n⚠️ Registros incompletos (falta entrada ou saída)"
            
            return msg
        except Exception as e:
            return f"❌ Erro ao calcular horas: {e}"

    def mostrar_falhas(self):
        """Mostra falhas recentes"""
        try:
            if not self.db:
                return "❌ Banco de dados não disponível"
            
            # Busca falhas dos últimos 7 dias
            hoje = datetime.now()
            inicio = hoje - timedelta(days=7)
            falhas = self.db.obter_falhas_periodo(inicio, hoje)
            
            if not falhas:
                return "✅ Nenhuma falha registrada nos últimos 7 dias"
            
            msg = "<b>❌ Últimas Falhas (7 dias)</b>\n\n"
            for f in falhas[-5:]:  # Últimas 5
                data = f[1] if len(f) > 1 else "N/A"
                if isinstance(data, str):
                    try:
                        dt = datetime.strptime(data.split('.')[0], '%Y-%m-%d %H:%M:%S')
                        data = dt.strftime('%d/%m %H:%M')
                    except:
                        pass
                erro = f[3] if len(f) > 3 else "Erro desconhecido"
                msg += f"• {data}: {str(erro)[:40]}...\n"
            
            return msg
        except Exception as e:
            return f"❌ Erro ao buscar falhas: {e}"

    def gerar_relatorio_mensal(self):
        """Gera resumo do mês atual"""
        try:
            if not self.db:
                return "❌ Banco de dados não disponível"
            
            hoje = datetime.now()
            inicio_mes = hoje.replace(day=1)
            
            # Busca registros do mês
            registros = self.db.obter_registros_periodo(inicio_mes, hoje)
            
            if not registros:
                return f"📄 Nenhum registro em {hoje.strftime('%B/%Y')}"
            
            # Conta dias trabalhados
            dias = set()
            for reg in registros:
                data_str = reg[1]
                if isinstance(data_str, str):
                    dt = datetime.strptime(data_str.split('.')[0], '%Y-%m-%d %H:%M:%S')
                else:
                    dt = data_str
                dias.add(dt.date())
            
            msg = f"<b>📄 Relatório - {hoje.strftime('%B/%Y')}</b>\n\n"
            msg += f"📅 Dias trabalhados: {len(dias)}\n"
            msg += f"📝 Total de registros: {len(registros)}\n"
            
            return msg
        except Exception as e:
            return f"❌ Erro ao gerar relatório: {e}"

    def gerar_relatorio_anual(self):
        """Gera resumo do ano atual"""
        try:
            if not self.db:
                return "❌ Banco de dados não disponível"
            
            hoje = datetime.now()
            inicio_ano = hoje.replace(month=1, day=1)
            
            # Busca registros do ano
            registros = self.db.obter_registros_periodo(inicio_ano, hoje)
            
            if not registros:
                return f"📅 Nenhum registro em {hoje.year}"
            
            # Conta dias trabalhados
            dias = set()
            total_horas = 0
            
            for reg in registros:
                data_str = reg[1]
                if isinstance(data_str, str):
                    dt = datetime.strptime(data_str.split('.')[0], '%Y-%m-%d %H:%M:%S')
                else:
                    dt = data_str
                dias.add(dt.date())
            
            # Calcula total de horas (aproximado)
            for dia in dias:
                try:
                    total = self.db.calcular_total_horas_dia(dia)
                    if total and total.get('registros_completos'):
                        # Parse "10h30min" para horas decimais
                        horas_str = total['total_formatado']
                        partes = horas_str.split('h')
                        if len(partes) >= 2:
                            h = int(partes[0])
                            m = int(partes[1].replace('min', ''))
                            total_horas += h + m/60
                except:
                    pass
            
            msg = f"<b>📅 Relatório Anual - {hoje.year}</b>\n\n"
            msg += f"📆 Dias trabalhados: {len(dias)}\n"
            msg += f"📝 Total de registros: {len(registros)}\n"
            msg += f"⏰ Horas aproximadas: {int(total_horas)}h\n"
            
            return msg
        except Exception as e:
            return f"❌ Erro ao gerar relatório anual: {e}"

    def mostrar_menu(self):
        """Mostra menu de comandos"""
        return (
            "<b>🔷 Menu Principal</b>\n\n"
            "🕒 /registrar - Bater ponto\n"
            "📊 /status - Status atual\n"
            "⏰ /horas - Horas de hoje\n"
            "📄 /relatorio - Relatório do mês\n"
            "❌ /falhas - Ver falhas\n"
            "⏸️ /pausar - Pausar sistema\n"
            "▶️ /retomar - Retomar sistema\n"
            "⏰ /horarios - Ver horários\n"
            "/entrada HH:MM - Alterar entrada\n"
            "/saida HH:MM - Alterar saída\n"
            "❓ /ajuda - Ajuda completa"
        )
    
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
    
    def _deduplica_comandos(self, updates):
        """
        Remove comandos repetidos consecutivos.
        Ex: [/status, /status, /status, /menu, /status] → [/status, /menu, /status]
        Mas permite o mesmo comando aparecer novamente após um diferente.
        """
        if not updates:
            return []
        
        deduplic = []
        ultimo_comando = None
        
        for update in updates:
            message = update.get('message', {})
            texto = message.get('text', '').lower().strip()
            
            # Se é um comando diferente do anterior, adiciona
            if texto != ultimo_comando:
                deduplic.append(update)
                ultimo_comando = texto
            else:
                print(f"⏭️ Pulando comando duplicado: {texto}")
        
        return deduplic
    
    def executar(self):
        """Loop principal - verifica comandos e mantém sessão ativa se necessário"""
        print(f"🤖 Telegram Listener iniciado às {datetime.now().strftime('%H:%M:%S')}")
        print(f"⏱️ Sessão máxima: {TEMPO_SESSAO // 60} minutos")
        print(f"📱 Chat ID: {self.chat_id}")
        
        inicio = time.time()
        sessao_ativa = False
        ultimo_comando = None
        
        # Primeira verificação
        print("🔄 Buscando updates do Telegram...")
        updates = self.get_updates()
        print(f"📬 {len(updates)} updates recebidos")
        
        # Deduplica comandos repetidos consecutivos
        comandos_processados = self._deduplica_comandos(updates)
        print(f"🔄 Após deduplicação: {len(comandos_processados)} comandos únicos")
        
        for update in comandos_processados:
            message = update.get('message', {})
            msg_chat_id = str(message.get('chat', {}).get('id', ''))
            texto = message.get('text', '')
            
            print(f"📨 Mensagem de {msg_chat_id}: {texto}")
            
            if msg_chat_id != self.chat_id:
                print(f"⚠️ Chat ID não corresponde. Esperado: {self.chat_id}, Recebido: {msg_chat_id}")
                continue
            
            # REMOVIDO: Filtro de mensagens antigas
            # Não descartamos mais mensagens por idade - melhor processar atrasadas que nunca!
            msg_time = datetime.fromtimestamp(message.get('date', 0))
            idade = (datetime.now() - msg_time).total_seconds()
            print(f"⏰ Idade da mensagem: {int(idade)}s ({int(idade/60)}min atrás)")
            
            print(f"🔍 Processando comando: {texto}")
            resposta = self.processar_comando(texto)
            
            if resposta:
                print(f"📤 Enviando resposta...")
                enviado = self.enviar_mensagem(resposta)
                if enviado:
                    sessao_ativa = True
                    ultimo_comando = time.time()
                    print(f"✅ Resposta enviada com sucesso")
                else:
                    print(f"❌ Falha ao enviar resposta")
            else:
                print(f"⚠️ Nenhuma resposta para este comando")
        
        # Se houve comando, mantém sessão ativa por 5 minutos
        if sessao_ativa:
            print("🟢 Ativando sessão ativa...")
            self.enviar_mensagem("🟢 Sessão ativa por 5 minutos. Envie comandos!")
            print("🔄 Sessão ativa - aguardando mais comandos...")
            
            while (time.time() - inicio) < TEMPO_SESSAO:
                time.sleep(INTERVALO_POLLING)
                
                tempo_passado = int(time.time() - inicio)
                
                # Mostra tempo restante a cada 60 segundos
                if tempo_passado % 60 == 0 and tempo_passado > 0:
                    restante = (TEMPO_SESSAO - tempo_passado) // 60
                    print(f"⏱️ {restante} minuto(s) restantes na sessão")
                
                print(f"🔄 Polling ({tempo_passado}s)...")
                updates = self.get_updates()
                print(f"📬 {len(updates)} updates")
                
                # Deduplica também na sessão ativa
                comandos_processados = self._deduplica_comandos(updates)
                print(f"🔄 Após deduplicação: {len(comandos_processados)} únicos")
                
                for update in comandos_processados:
                    message = update.get('message', {})
                    msg_chat_id = str(message.get('chat', {}).get('id', ''))
                    texto = message.get('text', '')
                    
                    if msg_chat_id != self.chat_id:
                        continue
                    
                    print(f"📨 Comando durante sessão: {texto}")
                    resposta = self.processar_comando(texto)
                    
                    if resposta:
                        enviado = self.enviar_mensagem(resposta)
                        if enviado:
                            ultimo_comando = time.time()
                            print(f"✅ Resposta enviada")
                        else:
                            print(f"❌ Falha ao enviar")
            
            print("⏱️ Sessão expirou")
            self.enviar_mensagem("🔴 Sessão encerrada. Envie um comando para reativar.")
        else:
            print("💤 Nenhum comando recente - encerrando")
        
        # Cleanup
        if self.sistema:
            try:
                self.sistema.encerrar_sistema()
            except:
                pass
        
        # Salva o estado para próxima execução
        self._salvar_ultimo_update_id()
        
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
