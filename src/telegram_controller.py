# telegram_controller.py
import requests
import json
import logging
from datetime import datetime, timedelta
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet

from config.config import Config
from src.relatorios.relatorio_anual import RelatorioAnual

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
        self.comandos_disponiveis = {
            '/registrar': self.registrar_ponto_manual,
            '/status': self.mostrar_status_detalhado,
            '/relatorio': self.enviar_relatorio,
            '/falhas': self.mostrar_falhas,
            '/horas': self.mostrar_horas,
            '/ajuda': self.mostrar_ajuda,
            '/menu': self.mostrar_menu,
            '/configuracoes': self.mostrar_configuracoes
        }


    def registrar_ponto_manual(self, args):
        try:
            config = Config()
            agora = datetime.now()
            motivo = ' '.join(args) if args else "Registro manual via Telegram"
            
            if self.db.registrar_ponto(agora, "MANUAL", "SUCESSO", motivo):
                msg = (
                    f"✅ Ponto registrado manualmente\n"
                    f"Data: {agora.strftime('%d/%m/%Y')}\n"
                    f"Hora: {agora.strftime('%H:%M:%S')}\n"
                    f"Motivo: {motivo}"
                )
            else:
                msg = "❌ Erro ao registrar ponto manual"
            
            self.enviar_mensagem(msg)
            self.mostrar_menu() # Retorna ao menu após registro
        except Exception as e:
            self.logger.error(f"Erro ao registrar ponto manual: {e}")
            self.enviar_mensagem(f"❌ Erro: {str(e)}")

    def mostrar_status_detalhado(self, args):
        try:
            config = Config()
            agora = datetime.now()
            hoje = agora.date()
            
            registros_hoje = self.db.obter_registros_periodo(
                datetime.combine(hoje, datetime.min.time()),
                datetime.combine(hoje, datetime.max.time())
            )
            
            horas_hoje = self.db.obter_horas_trabalhadas_periodo(hoje, hoje)
            
            msg = (
                f"📊 *Status do Sistema - {hoje.strftime('%d/%m/%Y')}*\n\n"
                f"*Estado:* {'🟢 Ativo' if self.sistema_ativo else '⏸️ Pausado'}\n\n"
                f"*Horários Configurados:*\n"
                f"• Entrada: {config.HORARIO_ENTRADA}\n"
                f"• Saída: {config.HORARIO_SAIDA}\n\n"
                f"*Registros de Hoje:*\n"
            )
            
            if registros_hoje:
                for reg in registros_hoje:
                    dt = datetime.strptime(reg[1], '%Y-%m-%d %H:%M:%S')
                    msg += f"• {dt.strftime('%H:%M:%S')} - {reg[2]} ({reg[3]})\n"
            else:
                msg += "Nenhum registro hoje\n"
            
            msg += "\n*Horas Trabalhadas Hoje:*\n"
            if horas_hoje:
                h = horas_hoje[0]
                msg += (
                    f"• Normais: {h[4]:.2f}h\n"
                    f"• Extras 60%: {h[5]:.2f}h\n"
                    f"• Extras 65%: {h[6]:.2f}h\n"
                    f"• Extras 75%: {h[7]:.2f}h\n"
                    f"• Extras 100%: {h[8]:.2f}h\n"
                    f"• Extras 150%: {h[9]:.2f}h\n"
                    f"• Noturnas: {h[10]:.2f}h\n"
                )
            else:
                msg += "Nenhuma hora registrada hoje\n"

            msg += "\n*Próximos Horários:*\n"
            hora_atual = agora.strftime('%H:%M')
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

    def mostrar_falhas(self, args):
        try:
            dias = int(args[0]) if args else 7
            
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

    def mostrar_horas(self, args):
        try:
            dias = int(args[0]) if args else 7
            
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
                msg += f"• Normais: {h[4]:.2f}h\n"
                msg += f"• HE 60%: {h[5]:.2f}h\n"
                msg += f"• HE 65%: {h[6]:.2f}h\n"
                msg += f"• HE 75%: {h[7]:.2f}h\n"
                msg += f"• HE 100%: {h[8]:.2f}h\n"
                msg += f"• HE 150%: {h[9]:.2f}h\n"
                msg += f"• Noturnas: {h[10]:.2f}h\n"
                msg += f"{'_'*30}\n\n"
                
                total_horas['normais'] += h[4]
                total_horas['he_60'] += h[5]
                total_horas['he_65'] += h[6]
                total_horas['he_75'] += h[7]
                total_horas['he_100'] += h[8]
                total_horas['he_150'] += h[9]
                total_horas['noturnas'] += h[10]
            
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

    def mostrar_menu(self, args=None):
        keyboard = {
            "keyboard": [
                ["🕒 Registrar Ponto", "📊 Status"],
                ["⏸️ Pausar Sistema", "▶️ Retomar Sistema"],
                ["📄 Relatório Mensal", "📋 Relatório Anual"],
                ["⏰ Horas Trabalhadas", "❌ Falhas"],
                ["⚙️ Configurações", "❓ Ajuda"],
                ["❌ Encerrar"]
            ],
            "resize_keyboard": True,
            "persistent": True
        }
        
        menu_text = (
            "🤖 *Sistema de Registro de Ponto*\n\n"
            "*Comandos Disponíveis:*\n\n"
            "📍 *Registro e Status:*\n"
            "• /registrar - Registrar ponto manual\n"
            "• /status - Ver status detalhado\n\n"
            "📊 *Relatórios:*\n"
            "• /relatorio mes ano - Relatório mensal\n"
            "• /relatorio_anual [ano] - Relatório anual\n\n"
            "⏰ *Consultas:*\n"
            "• /horas [dias] - Ver horas trabalhadas\n"
            "• /falhas [dias] - Ver falhas do sistema\n\n"
            "⚙️ *Sistema:*\n"
            "• /configuracoes - Ver configurações\n"
            "• /ajuda - Ver ajuda detalhada\n"
            "• /menu - Mostrar este menu\n\n"
            "💡 *Dicas:*\n"
            "• Use os botões para acesso rápido\n"
            "• Para relatórios mensais: /relatorio 1 2024\n"
            "• Para consultas: /horas 7 ou /falhas 7"
        )
        
        self.enviar_mensagem(menu_text, keyboard)

    def processar_mensagem(self, mensagem):
        try:
            if 'text' not in mensagem:
                return
                
            texto = mensagem['text']
            comando = texto.split()[0].lower()
            
            if comando in self.comandos_disponiveis:
                args = texto.split()[1:] if len(texto.split()) > 1 else []
                self.comandos_disponiveis[comando](args)
            # Corrigido o mapeamento dos botões para os métodos existentes
            elif texto == "🕒 Registrar Ponto":
                self.registrar_ponto_manual([])
            elif texto == "📊 Status":
                self.mostrar_status_detalhado([])
            elif texto == "⏸️ Pausar Sistema":
                self.processar_botao(texto)
            elif texto == "▶️ Retomar Sistema":
                self.processar_botao(texto)
            elif texto == "📄 Relatório Mensal":
                self.enviar_relatorio([])
            elif texto == "📋 Relatório Anual":
                self.gerar_relatorio_anual([])
            elif texto == "⏰ Horas Trabalhadas":
                self.mostrar_horas([])
            elif texto == "❌ Falhas":
                self.mostrar_falhas([])
            elif texto == "⚙️ Configurações":
                self.mostrar_configuracoes([])
            elif texto == "❓ Ajuda":
                self.mostrar_ajuda()
            elif texto == "❌ Encerrar":
                self.processar_botao(texto)
            else:
                self.enviar_mensagem("Comando não reconhecido. Digite /ajuda para ver os comandos disponíveis.")

        except Exception as e:
            self.logger.error(f"Erro ao processar mensagem: {e}")
            self.enviar_mensagem(f"Erro ao processar comando: {str(e)}")

    def enviar_mensagem(self, mensagem, keyboard=None):
        try:
            data = {
                "chat_id": self.chat_id,
                "text": mensagem,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True
            }
            if keyboard:
                # Converter o keyboard para JSON antes de enviar
                data["reply_markup"] = json.dumps(keyboard)
            response = requests.post(f"{self.api_url}/sendMessage", json=data)
            response.raise_for_status()
            self.logger.info(f"Mensagem enviada: {mensagem[:100]}...")
        except Exception as e:
            self.logger.error(f"Erro ao enviar mensagem: {e}")
            print(f"Erro ao enviar mensagem: {e}")

    def enviar_documento(self, arquivo, caption):
        try:
            with open(arquivo, 'rb') as doc:
                files = {'document': doc}
                data = {
                    'chat_id': self.chat_id,
                    'caption': caption
                }
                response = requests.post(
                    f"{self.api_url}/sendDocument",
                    data=data,
                    files=files
                )
                response.raise_for_status()
                self.logger.info(f"Documento enviado: {arquivo}")
        except Exception as e:
            self.logger.error(f"Erro ao enviar documento: {e}")
            self.enviar_mensagem(f"❌ Erro ao enviar documento: {str(e)}")

    def get_updates(self):
        try:
            response = requests.get(
                f"{self.api_url}/getUpdates",
                params={"offset": self.ultimo_update_id + 1, "timeout": 30}
            )
            updates = response.json()
            if updates.get("result"):
                self.ultimo_update_id = updates["result"][-1]["update_id"]
            return updates.get("result", [])
        except Exception as e:
            self.logger.error(f"Erro ao obter atualizações: {e}")
            return []

    def gerar_relatorio_anual(self, args):
        try:
            if not args:
                ano = datetime.now().year
            else:
                ano = int(args[0])
                
            self.enviar_mensagem(f"🔄 Gerando relatório anual {ano}...")
            
            relatorio = RelatorioAnual(self.db, self.calculadora)
            pdf = relatorio.gerar_relatorio_anual(ano, 'pdf')
            excel = relatorio.gerar_relatorio_anual(ano, 'excel')
            
            if pdf:
                self.enviar_documento(pdf, f"Relatório Anual {ano} (PDF)")
            if excel:
                self.enviar_documento(excel, f"Relatório Anual {ano} (Excel)")
                
        except ValueError:
            self.enviar_mensagem("❌ Ano inválido")
        except Exception as e:
            self.enviar_mensagem(f"❌ Erro ao gerar relatório anual: {e}")

    def mostrar_ajuda(self, args=None):
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
            "• ⏸️ Pausar - Interrompe registros automáticos\n"
            "• ▶️ Retomar - Reinicia registros automáticos\n"
            "• 📊 Status - Mostra situação atual\n"
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

    def mostrar_configuracoes(self, args=None):
        try:
            config = Config()
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

    def processar_botao(self, texto):
        try:
            config = Config()
            if texto == "🕒 Registrar Ponto":
                from .automacao.ponto_controller import AutomacaoPonto
                automacao = AutomacaoPonto(
                    config.URL_SISTEMA,
                    config.LOGIN,
                    config.SENHA,
                    self.db,
                    self
                )
                automacao.registrar_ponto(force=True)
            elif texto == "⏸️ Pausar Sistema":
                self.sistema_ativo = False
                self.enviar_mensagem("⏸️ Sistema pausado")
            elif texto == "▶️ Retomar Sistema":
                self.sistema_ativo = True
                self.enviar_mensagem("▶️ Sistema retomado")
            elif texto == "📊 Status":
                self.mostrar_status_detalhado([])
            elif texto == "❌ Encerrar":
                self.sistema_ativo = False
                self.enviar_mensagem("🔴 Sistema sendo encerrado")
                import sys
                sys.exit(0)
        except Exception as e:
            self.logger.error(f"Erro ao processar botão: {e}")
            self.enviar_mensagem(f"❌ Erro: {str(e)}")

    def _formatar_tempo(self, minutos):
        horas = minutos // 60
        min_rest = minutos % 60
        return f"{horas:02d}:{min_rest:02d}"

    def _formatar_data(self, data):
        return data.strftime("%d/%m/%Y")

    def _formatar_hora(self, hora):
        return hora.strftime("%H:%M:%S")