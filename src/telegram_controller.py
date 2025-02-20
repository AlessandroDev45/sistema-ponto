import sys
import os
from pathlib import Path
import time

# Adiciona o diretório raiz ao Python Path
current_dir = Path(__file__).resolve().parent
root_dir = current_dir.parent
sys.path.append(str(root_dir))

import requests
import logging
from datetime import datetime, timedelta
import json
from config.config import Config 

# Ensure root path is added to sys.path
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Local imports
from src.relatorios.gerador_relatorios import GeradorRelatorios
from src.utils.database import Database

class TelegramController:
    def __init__(self, token, chat_id, database, gerador_relatorios):
        self.token = token
        self.chat_id = chat_id
        self.api_url = f"https://api.telegram.org/bot{token}"
        self.ultimo_update_id = 0
        self.logger = logging.getLogger('TelegramController')
        self.db = database
        self.gerador_relatorios = gerador_relatorios
        self.sistema_ativo = True
        self.aguardando_confirmacao = False

        self.comandos_disponiveis = {
            '/registrar': self.registrar_ponto_manual,
            '/status': self.mostrar_status_detalhado,
            '/relatorio': self.enviar_relatorio,
            '/relatorio_anual': self.gerar_relatorio_anual,
            '/falhas': self.mostrar_falhas,
            '/horas': self.mostrar_horas,
            '/ajuda': self.mostrar_ajuda,
            '/menu': self.mostrar_menu,
            '/configuracoes': self.mostrar_configuracoes,
            '/pausar': self.pausar_sistema,
            '/retomar': self.retomar_sistema
        }

        try:
            self.logger.info("Verificando credenciais do Telegram...")
            response = requests.get(f"{self.api_url}/getMe")
            response.raise_for_status()
            self.logger.info("Credenciais do Telegram verificadas com sucesso")
        except Exception as e:
            self.logger.error(f"Erro ao verificar credenciais do Telegram: {e}")
            raise

    def solicitar_confirmacao_encerramento(self, args=None):
        """Solicita confirmação antes de encerrar o sistema"""
        self.aguardando_confirmacao = True
        self.enviar_mensagem("⚠️ Tem certeza que deseja encerrar o sistema?\nDigite 'CONFIRMAR' para encerrar ou qualquer outra tecla para cancelar")

    def _escapar_markdown(self, texto):
        """Escapa caracteres especiais para Markdown"""
        caracteres = ['_', '*', '`', '[']
        for c in caracteres:
            texto = texto.replace(c, f'\\{c}')
        return texto

    def enviar_mensagem(self, texto, parse_mode=None):
        """Envia mensagem via Telegram
        Args:
            texto (str): O texto da mensagem
            parse_mode (str, optional): Modo de formatação ('HTML' ou 'MarkdownV2')
        """
        try:
            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            data = {
                'chat_id': self.chat_id,
                'text': texto
            }

            if parse_mode in ['HTML', 'MarkdownV2']:
                data['parse_mode'] = parse_mode

            response = requests.post(url, json=data)
            response.raise_for_status()
            return True
                
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Erro ao enviar mensagem: {e}")
            if hasattr(e, 'response') and hasattr(e.response, 'text'):
                self.logger.error(f"Response: {e.response.text}")
            return False

 

    def enviar_documento(self, arquivo, caption):
        """Envia um documento para o Telegram"""
        try:
            with open(arquivo, 'rb') as doc:
                files = {'document': doc}
                data = {
                    'chat_id': self.chat_id,
                    'caption': caption
                }
                response = requests.post(f"{self.api_url}/sendDocument", data=data, files=files)
                response.raise_for_status()
                self.logger.info(f"Documento enviado: {arquivo}")
        except Exception as e:
            self.logger.error(f"Erro ao enviar documento: {e}")
            self.enviar_mensagem(f"❌ Erro ao enviar documento: {str(e)}")

    def get_updates(self):
        """
        Obtém atualizações do Telegram, ignorando mensagens antigas.
        """
        try:
            response = requests.get(
                f"{self.api_url}/getUpdates",
                params={
                    "offset": self.ultimo_update_id + 1,
                    "timeout": 30,
                    "allowed_updates": ["message"]
                }
            )
            updates = response.json()
            
            if updates.get("result"):
                self.ultimo_update_id = updates["result"][-1]["update_id"]
                current_time = time.time()
                filtered_updates = [
                    update for update in updates["result"]
                    if current_time - update["message"].get("date", current_time) < 30
                ]
                return filtered_updates
                
            return []
        except Exception as e:
            self.logger.error(f"Erro ao obter atualizações: {e}")
            return []

    def processar_mensagem(self, mensagem):
        """
        Processa mensagens recebidas do Telegram.
        """
        try:
            if 'text' not in mensagem:
                return

            texto = mensagem['text']
            msg_time = datetime.fromtimestamp(mensagem.get('date', 0))
            if (datetime.now() - msg_time).total_seconds() > 30:
                return

            if texto == 'CONFIRMAR' and self.aguardando_confirmacao:
                self.sistema_ativo = False
                self.enviar_mensagem("🔴 Sistema sendo encerrado")
                os._exit(0)
                return

            acoes_botoes = {
                "🕒 Registrar Ponto": self.registrar_ponto_manual,
                "📊 Status": self.mostrar_status_detalhado,
                "⏸️ Pausar Sistema": self.pausar_sistema,
                "▶️ Retomar Sistema": self.retomar_sistema,
                "📄 Relatório Mensal": self.enviar_relatorio,
                "📋 Relatório Anual": self.gerar_relatorio_anual,
                "⏰ Horas Trabalhadas": self.mostrar_horas,
                "❌ Falhas": self.mostrar_falhas,
                "⚙️ Configurações": self.mostrar_configuracoes,
                "❓ Ajuda": self.mostrar_ajuda,
                "❌ Encerrar": self.solicitar_confirmacao_encerramento
            }

            if texto in acoes_botoes:
                acoes_botoes[texto](None)  # Passa None como argumento padrão
            elif texto.startswith('/'):
                comando = texto.split()[0].lower()
                args = texto.split()[1:] if len(texto.split()) > 1 else []
                if comando in self.comandos_disponiveis:
                    self.comandos_disponiveis[comando](args if args else None)
                else:
                    self.enviar_mensagem("Comando não reconhecido. Digite /ajuda para ver os comandos disponíveis.")
                    
        except Exception as e:
            self.logger.error(f"Erro ao processar mensagem: {e}")
            self.enviar_mensagem(f"❌ Erro ao processar comando: {str(e)}")

    def pausar_sistema(self, args=None):
        """Pausa o sistema"""
        if self.sistema_ativo:
            self.sistema_ativo = False
            self.enviar_mensagem("⏸️ Sistema pausado")
            self.mostrar_menu()
        else:
            self.enviar_mensagem("O sistema já está pausado.")

    def retomar_sistema(self, args=None):
        """Retoma o sistema pausado"""
        if not self.sistema_ativo:
            self.sistema_ativo = True
            self.enviar_mensagem("▶️ Sistema retomado")
            self.mostrar_menu()
        else:
            self.enviar_mensagem("O sistema já está ativo.")

    def mostrar_menu(self, args=None):
        keyboard = [
            ["🕒 Registrar Ponto", "📊 Status"],
            ["⏸️ Pausar Sistema", "▶️ Retomar Sistema"],
            ["📄 Relatório Mensal", "📋 Relatório Anual"],
            ["⏰ Horas Trabalhadas", "❌ Falhas"],
            ["⚙️ Configurações", "❓ Ajuda"],
            ["❌ Encerrar","🔷 Menu Principal 🔷\n\n"]
        ]

        menu_text = (
            "<b>🤖 Sistema de Registro de Ponto</b>\n\n"
            "<b>Comandos Disponíveis:</b>\n\n"
            "📍 <b>Registro e Status:</b>\n"
            "• /registrar - Registrar ponto manual\n"
            "• /status - Ver status detalhado\n\n"
            "📊 <b>Relatórios:</b>\n"
            "• /relatorio mes ano - Relatório mensal\n"
            "• /relatorio_anual [ano] - Relatório anual\n\n"
            "⏰ <b>Consultas:</b>\n"
            "• /horas [dias] - Ver horas trabalhadas\n"
            "• /falhas [dias] - Ver falhas do sistema\n\n"
            "⚙️ <b>Sistema:</b>\n"
            "• /configuracoes - Ver configurações\n"
            "• /ajuda - Ver ajuda detalhada\n"
            "• /menu - Mostrar este menu\n"
            "• /pausar - Pausar sistema\n"
            "• /retomar - Retomar sistema\n\n"
            "💡 <b>Dicas:</b>\n"
            "• Use os botões para acesso rápido\n"
            "• Para relatórios mensais: /relatorio 1 2024\n"
            "• Para consultas: /horas 7 ou /falhas 7"
        )

        self.enviar_mensagem(menu_text, keyboard)

    def registrar_ponto_manual(self, args=None):
        try:
            if not hasattr(self, 'automacao'):
                self.enviar_mensagem("❌ Sistema não inicializado")
                return
                
            resultado = self.automacao.registrar_ponto(force=True)
            
            if resultado['sucesso']:
                self.enviar_mensagem("✅ Ponto registrado manualmente com sucesso")
            else:
                self.enviar_mensagem(f"❌ Falha no registro: {resultado['mensagem']}")
                
        except Exception as e:
            self.logger.error(f"Erro no registro manual: {e}")
            self.enviar_mensagem(f"❌ Erro: {str(e)}")

    def mostrar_status_detalhado(self, args=None):
        """Mostra status detalhado do sistema e registros"""
        try:
            config = Config.get_instance()
            agora = datetime.now()
            hoje = agora.date()

            inicio_dia = datetime.combine(hoje, datetime.min.time())
            fim_dia = datetime.combine(hoje, datetime.max.time())

            registros_hoje = self.db.obter_registros_periodo(inicio_dia, fim_dia)
            horas_hoje = self.db.obter_horas_trabalhadas_periodo(hoje, hoje)

            msg = (
                "<b>📊 Status do Sistema</b>\n"
                f"Data: {hoje.strftime('%d/%m/%Y')}\n\n"
                f"Estado: {'🟢 Ativo' if self.sistema_ativo else '⏸️ Pausado'}\n\n"
                "<b>Horários Configurados:</b>\n"
                f"• Entrada: {config.HORARIO_ENTRADA}\n"
                f"• Saída: {config.HORARIO_SAIDA}\n\n"
                "<b>Registros de Hoje:</b>\n"
            )

            if registros_hoje:
                for reg in registros_hoje:
                    dt = datetime.strptime(reg[1].split('.')[0], '%Y-%m-%d %H:%M:%S')
                    msg += f"• {dt.strftime('%H:%M')} - {reg[2]} ({reg[3]})\n"
            else:
                msg += "Nenhum registro hoje\n"

            msg += "\n<b>Horas Trabalhadas Hoje:</b>\n"
            if horas_hoje:
                h = horas_hoje[0]
                msg += (
                    f"• Normais: {float(h[4]):.2f}h\n"
                    f"• Extras 60%: {float(h[5]):.2f}h\n"
                    f"• Extras 65%: {float(h[6]):.2f}h\n"
                    f"• Extras 75%: {float(h[7]):.2f}h\n"
                    f"• Extras 100%: {float(h[8]):.2f}h\n"
                    f"• Extras 150%: {float(h[9]):.2f}h\n"
                    f"• Noturnas: {float(h[10]):.2f}h\n"
                )
            else:
                msg += "Nenhuma hora registrada hoje\n"

            hora_atual = agora.strftime('%H:%M')
            msg += "\n<b>Próximos Horários:</b>\n"
            if hora_atual < config.HORARIO_ENTRADA:
                msg += f"• Próximo registro: {config.HORARIO_ENTRADA} (Entrada)\n"
            elif hora_atual < config.HORARIO_SAIDA:
                msg += f"• Próximo registro: {config.HORARIO_SAIDA} (Saída)\n"
            else:
                msg += f"• Próximo registro: {config.HORARIO_ENTRADA} (Entrada amanhã)\n"

            self.enviar_mensagem(msg)

        except Exception as e:
            self.logger.error(f"Erro ao mostrar status: {e}")
            self.enviar_mensagem(f"❌ Erro ao obter status: {str(e)}")

    def enviar_relatorio(self, args):
        """Envia relatório mensal"""
        try:
            if not args or len(args) != 2:
                self.enviar_mensagem(
                    "*Uso do comando /relatorio:*\n\n"
                    "Formato: /relatorio mes ano\n"
                    "Exemplo: /relatorio 1 2024\n\n"
                    "*Observações:*\n"
                    "• Mês deve ser um número entre 1 e 12\n"
                    "• Ano deve ser um número válido\n"
                    "• O relatório será gerado em PDF"
                )
                return

            mes = int(args[0])
            ano = int(args[1])

            if not (1 <= mes <= 12):
                self.enviar_mensagem("❌ Mês inválido. Use um número entre 1 e 12.")
                return

            self.enviar_mensagem(f"🔄 Gerando relatório de {mes}/{ano}...")
            pdf_path = self.gerador_relatorios.gerar_relatorio_mensal(mes, ano, 'pdf')

            if pdf_path:
                self.enviar_documento(pdf_path, f"Relatório {mes}/{ano}")
                self.enviar_mensagem("✅ Relatório gerado com sucesso!")
            else:
                self.enviar_mensagem("❌ Erro ao gerar relatório")

        except ValueError:
            self.enviar_mensagem("❌ Formato inválido. Use: /relatorio mes ano")
        except Exception as e:
            self.logger.error(f"Erro ao enviar relatório: {e}")
            self.enviar_mensagem(f"❌ Erro: {str(e)}")

    def mostrar_falhas(self, args=None):
        """Mostra falhas recentes do sistema"""
        try:
            dias = int(args[0]) if args and args[0].isdigit() else 7

            if dias <= 0 or dias > 90:
                self.enviar_mensagem("❌ Período inválido. Use entre 1 e 90 dias.")
                return

            fim = datetime.now()
            inicio = fim - timedelta(days=dias)

            falhas = self.db.obter_falhas_periodo(inicio, fim)

            if not falhas:
                self.enviar_mensagem(f"✅ Nenhuma falha nos últimos {dias} dias")
                return

            msg = f"📋 *Registro de Falhas - Últimos {dias} dias*\n\n"
            for f in falhas:
                dt = datetime.strptime(f[1], '%Y-%m-%d %H:%M:%S')
                msg += (
                    f"*Data:* {dt.strftime('%d/%m/%Y %H:%M:%S')}\n"
                    f"*Tipo:* {f[2]}\n"
                    f"*Erro:* {f[3]}\n"
                    f"*Detalhes:* {f[4] or 'N/A'}\n"
                    f"{'_'*30}\n\n"
                )

            self.enviar_mensagem(msg)

        except ValueError:
            self.enviar_mensagem(
                "*Uso do comando /falhas:*\n\n"
                "Formato: /falhas [dias]\n"
                "Exemplo: /falhas 7\n\n"
                "*Observações:*\n"
                "• Dias é opcional (padrão: 7)\n"
                "• Máximo: 90 dias"
            )
        except Exception as e:
            self.logger.error(f"Erro ao mostrar falhas: {e}")
            self.enviar_mensagem(f"❌ Erro: {str(e)}")

    def mostrar_configuracoes(self, args=None):
        """Mostra as configurações atuais"""
        try:
            config = Config.get_instance()
            msg = (
                "⚙️ *Configurações Atuais*\n\n"
                "*🕒 Horários:*\n"
                f"• Entrada: {config.HORARIO_ENTRADA}\n"
                f"• Saída: {config.HORARIO_SAIDA}\n"
                f"• Tolerância: {config.TOLERANCIA_MINUTOS} minutos\n"
                f"• Intervalo Mínimo: {config.INTERVALO_MINIMO} minutos\n\n"
                "*💰 Financeiro:*\n"
                f"• Salário Base: R$ {config.SALARIO_BASE:.2f}\n"
                f"• Periculosidade: {config.PERICULOSIDADE*100}%\n"
                f"• Adicional Noturno: {config.ADICIONAL_NOTURNO*100}%\n\n"
                "*🔄 Horas Extras:*\n"
                f"• 60%: {config.HORAS_EXTRAS['60']*100}%\n"
                f"• 65%: {config.HORAS_EXTRAS['65']*100}%\n"
                f"• 75%: {config.HORAS_EXTRAS['75']*100}%\n"
                f"• 100%: {config.HORAS_EXTRAS['100']*100}%\n"
                f"• 150%: {config.HORAS_EXTRAS['150']*100}%"
            )
            self.enviar_mensagem(msg)

        except Exception as e:
            self.logger.error(f"Erro ao mostrar configurações: {e}")
            self.enviar_mensagem("❌ Erro ao obter configurações")

    def mostrar_ajuda(self, args=None):
        """Mostra ajuda detalhada"""
        ajuda = (
            "📚 *Guia Detalhado do Sistema*\n\n"
            "*Registro de Ponto:*\n"
            "• Automático nos horários configurados\n"
            "• Manual via botão ou comando /registrar\n\n"
            "*Relatórios:*\n"
            "• /relatorio mes ano - Relatório mensal detalhado\n"
            "• /horas [dias] - Horas trabalhadas do período\n"
            "• /falhas [dias] - Log de falhas do sistema\n\n"
            "*Controles do Sistema:*\n"
            "• /pausar - Pausa o sistema\n"
            "• /retomar - Retoma o sistema\n"
            "• /status - Mostra situação atual\n"
            "• /configuracoes - Exibe configurações atuais\n\n"
            "*Exemplos:*\n"
            "• /relatorio 1 2024 - Relatório de janeiro/2024\n"
            "• /horas 7 - Horas dos últimos 7 dias\n"
            "• /falhas 30 - Falhas dos últimos 30 dias\n\n"
            "*Observações:*\n"
            "• O sistema registra pontos automaticamente\n"
            "• Mantenha o bot ativo para receber notificações\n"
            "• Use /menu para voltar ao menu principal"
        )
        self.enviar_mensagem(ajuda)

    def _formatar_tempo(self, minutos):
        horas = minutos // 60
        min_rest = minutos % 60
        return f"{horas:02d}:{min_rest:02d}"

    def _formatar_data(self, data):
        return data.strftime("%d/%m/%Y")

    def _formatar_hora(self, hora):
        return hora.strftime("%H:%M:%S")

    def mostrar_horas(self, args=None):
        """Mostra horas trabalhadas em um período"""
        try:
            dias = int(args[0]) if args and args[0].isdigit() else 7

            if dias <= 0 or dias > 90:
                self.enviar_mensagem("❌ Período inválido. Use entre 1 e 90 dias.")
                return

            fim = datetime.now()
            inicio = fim - timedelta(days=dias)

            horas = self.db.obter_horas_trabalhadas_periodo(inicio, fim)

            if not horas:
                self.enviar_mensagem(f"ℹ️ Nenhuma hora registrada nos últimos {dias} dias")
                return

            msg = f"⏰ *Horas Trabalhadas - Últimos {dias} dias*\n\n"
            total_horas = {
                'normais': 0, 'he_60': 0, 'he_65': 0,
                'he_75': 0, 'he_100': 0, 'he_150': 0,
                'noturnas': 0
            }

            for h in horas:
                data = datetime.strptime(h[1], '%Y-%m-%d').strftime('%d/%m/%Y')
                msg += f"📅 *{data}:*\n"
                msg += f"• Normais: {float(h[4]):.2f}h\n"
                msg += f"• HE 60%: {float(h[5]):.2f}h\n"
                msg += f"• HE 65%: {float(h[6]):.2f}h\n"
                msg += f"• HE 75%: {float(h[7]):.2f}h\n"
                msg += f"• HE 100%: {float(h[8]):.2f}h\n"
                msg += f"• HE 150%: {float(h[9]):.2f}h\n"
                msg += f"• Noturnas: {float(h[10]):.2f}h\n"
                msg += f"{'_'*30}\n\n"

                total_horas['normais'] += float(h[4])
                total_horas['he_60'] += float(h[5])
                total_horas['he_65'] += float(h[6])
                total_horas['he_75'] += float(h[7])
                total_horas['he_100'] += float(h[8])
                total_horas['he_150'] += float(h[9])
                total_horas['noturnas'] += float(h[10])

            msg += "*📊 Totais do Período:*\n"
            total_geral = 0
            for tipo, total in total_horas.items():
                msg += f"• {tipo.replace('_', ' ').title()}: {total:.2f}h\n"
                total_geral += total
            msg += f"\n*Total Geral: {total_geral:.2f}h*"

            self.enviar_mensagem(msg)

        except ValueError:
            self.enviar_mensagem(
                "*Uso do comando /horas:*\n\n"
                "Formato: /horas [dias]\n"
                "Exemplo: /horas 7\n\n"
                "*Observações:*\n"
                "• Dias é opcional (padrão: 7)\n"
                "• Máximo: 90 dias"
            )
        except Exception as e:
            self.logger.error(f"Erro ao mostrar horas: {e}")
            self.enviar_mensagem(f"❌ Erro: {str(e)}")

    def gerar_relatorio_anual(self, args=None):
        """Gera e envia relatório anual"""
        try:
            if not args:
                ano = datetime.now().year
            else:
                ano = int(args[0])

            self.enviar_mensagem(f"🔄 Gerando relatório anual {ano}...")

            pdf = self.gerador_relatorios.gerar_relatorio_anual(ano, 'pdf')
            excel = self.gerador_relatorios.gerar_relatorio_anual(ano, 'excel')

            if pdf:
                self.enviar_documento(pdf, f"Relatório Anual {ano} (PDF)")
            if excel:
                self.enviar_documento(excel, f"Relatório Anual {ano} (Excel)")

            self.enviar_mensagem("✅ Relatório anual gerado com sucesso!")

        except ValueError:
            self.enviar_mensagem("❌ Ano inválido")
        except Exception as e:
            self.logger.error(f"Erro ao gerar relatório anual: {e}")
            self.enviar_mensagem(f"❌ Erro ao gerar relatório anual: {str(e)}")

    def confirmar_encerramento(self, mensagem):
        """
        Confirma o encerramento do sistema
        """
        if mensagem.get('text') == 'CONFIRMAR':
            self.sistema_ativo = False
            self.enviar_mensagem("🔴 Sistema sendo encerrado")
            os._exit(0)
            return True
        return False
    def processar_comando_status(self):
        """Processa o comando de status"""
        try:
            if not hasattr(self, 'automacao'):
                self.enviar_mensagem("❌ Sistema não inicializado corretamente")
                return

            status = self.automacao.verificar_status()
            if status and 'mensagem' in status:
                self.enviar_mensagem(status['mensagem'])
            else:
                self.enviar_mensagem("❌ Não foi possível obter o status do sistema")
                
        except Exception as e:
            self.logger.error(f"Erro ao processar comando de status: {e}")
            self.enviar_mensagem("❌ Erro ao obter status do sistema")