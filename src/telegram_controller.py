# telegram_controller.py
import requests
import json
import logging
from datetime import datetime, timedelta
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet

class TelegramController:
    def __init__(self, token, chat_id, database, gerador_relatorios):
        self.token = token
        self.chat_id = chat_id
        self.api_url = f"https://api.telegram.org/bot{token}"
        self.ultimo_update_id = 0
        self.logger = logging.getLogger('TelegramController')
        self.db = database
        self.gerador_relatorios = gerador_relatorios
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

    def processar_mensagem(self, mensagem):
        try:
            if 'text' not in mensagem:
                return
            
            texto = mensagem['text']
            comando = texto.split()[0].lower()
            
            if comando in self.comandos_disponiveis:
                args = texto.split()[1:] if len(texto.split()) > 1 else []
                self.comandos_disponiveis[comando](args)
            elif texto in ["🕒 Registrar Ponto", "⏸️ Pausar Sistema", 
                         "▶️ Retomar Sistema", "📊 Status", "❌ Encerrar"]:
                self.processar_botao(texto)
            else:
                self.enviar_mensagem("Comando não reconhecido. Digite /ajuda para ver os comandos disponíveis.")

        except Exception as e:
            self.logger.error(f"Erro ao processar mensagem: {e}")
            self.enviar_mensagem(f"Erro ao processar comando: {str(e)}")

    def registrar_ponto_manual(self, args):
        try:
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
        except Exception as e:
            self.logger.error(f"Erro ao registrar ponto manual: {e}")
            self.enviar_mensagem(f"❌ Erro: {str(e)}")

    def mostrar_status_detalhado(self, args):
        try:
            agora = datetime.now()
            hoje = agora.date()
            
            registros_hoje = self.db.obter_registros_periodo(
                datetime.combine(hoje, datetime.min.time()),
                datetime.combine(hoje, datetime.max.time())
            )
            
            horas_hoje = self.db.obter_horas_trabalhadas_periodo(hoje, hoje)
            
            msg = (
                f"📊 Status Detalhado - {hoje.strftime('%d/%m/%Y')}\n\n"
                f"Registros de Hoje:\n"
            )
            
            if registros_hoje:
                for reg in registros_hoje:
                    dt = datetime.strptime(reg[1], '%Y-%m-%d %H:%M:%S')
                    msg += f"• {dt.strftime('%H:%M:%S')} - {reg[2]} ({reg[3]})\n"
            else:
                msg += "Nenhum registro hoje\n"
            
            msg += "\nHoras Trabalhadas Hoje:\n"
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
            
            self.enviar_mensagem(msg)
        except Exception as e:
            self.logger.error(f"Erro ao mostrar status: {e}")
            self.enviar_mensagem(f"❌ Erro ao obter status: {str(e)}")

    def enviar_relatorio(self, args):
        try:
            if not args or len(args) != 2:
                self.enviar_mensagem("Uso: /relatorio mes ano\nExemplo: /relatorio 1 2024")
                return
            
            mes = int(args[0])
            ano = int(args[1])
            
            if not (1 <= mes <= 12):
                self.enviar_mensagem("Mês inválido. Use um número entre 1 e 12.")
                return
                
            pdf_path = self.gerador_relatorios.gerar_relatorio_mensal(mes, ano, 'pdf')
            if pdf_path:
                self.enviar_documento(pdf_path, f"Relatório {mes}/{ano}")
            else:
                self.enviar_mensagem("❌ Erro ao gerar relatório")
                
        except ValueError:
            self.enviar_mensagem("Formato inválido. Use: /relatorio mes ano")
        except Exception as e:
            self.logger.error(f"Erro ao enviar relatório: {e}")
            self.enviar_mensagem(f"❌ Erro: {str(e)}")

    def mostrar_falhas(self, args):
        try:
            dias = int(args[0]) if args else 7
            
            fim = datetime.now()
            inicio = fim - timedelta(days=dias)
            
            falhas = self.db.obter_falhas_periodo(inicio, fim)
            
            if not falhas:
                self.enviar_mensagem(f"Nenhuma falha nos últimos {dias} dias")
                return
                
            msg = f"📋 Falhas dos últimos {dias} dias:\n\n"
            for f in falhas:
                dt = datetime.strptime(f[1], '%Y-%m-%d %H:%M:%S')
                msg += (
                    f"Data: {dt.strftime('%d/%m/%Y %H:%M:%S')}\n"
                    f"Tipo: {f[2]}\n"
                    f"Erro: {f[3]}\n"
                    f"Detalhes: {f[4] or 'N/A'}\n"
                    f"{'='*30}\n"
                )
            
            self.enviar_mensagem(msg)
        except ValueError:
            self.enviar_mensagem("Uso: /falhas [dias]\nExemplo: /falhas 7")
        except Exception as e:
            self.logger.error(f"Erro ao mostrar falhas: {e}")
            self.enviar_mensagem(f"❌ Erro: {str(e)}")

    def mostrar_horas(self, args):
        try:
            dias = int(args[0]) if args else 7
            
            fim = datetime.now()
            inicio = fim - timedelta(days=dias)
            
            horas = self.db.obter_horas_trabalhadas_periodo(inicio, fim)
            
            if not horas:
                self.enviar_mensagem(f"Nenhuma hora registrada nos últimos {dias} dias")
                return
                
            msg = f"⏰ Horas dos últimos {dias} dias:\n\n"
            total_horas = {
                'normais': 0, 'he_60': 0, 'he_65': 0,
                'he_75': 0, 'he_100': 0, 'he_150': 0,
                'noturnas': 0
            }
            
            for h in horas:
                data = datetime.strptime(h[1], '%Y-%m-%d').strftime('%d/%m/%Y')
                msg += f"📅 {data}:\n"
                msg += f"• Normais: {h[4]:.2f}h\n"
                msg += f"• HE 60%: {h[5]:.2f}h\n"
                msg += f"• HE 65%: {h[6]:.2f}h\n"
                msg += f"• HE 75%: {h[7]:.2f}h\n"
                msg += f"• HE 100%: {h[8]:.2f}h\n"
                msg += f"• HE 150%: {h[9]:.2f}h\n"
                msg += f"• Noturnas: {h[10]:.2f}h\n"
                msg += f"{'='*30}\n"
                
                total_horas['normais'] += h[4]
                total_horas['he_60'] += h[5]
                total_horas['he_65'] += h[6]
                total_horas['he_75'] += h[7]
                total_horas['he_100'] += h[8]
                total_horas['he_150'] += h[9]
                total_horas['noturnas'] += h[10]
            
            msg += "\n📊 Totais do Período:\n"
            for tipo, total in total_horas.items():
                msg += f"• {tipo.replace('_', ' ').title()}: {total:.2f}h\n"
            
            self.enviar_mensagem(msg)
        except ValueError:
            self.enviar_mensagem("Uso: /horas [dias]\nExemplo: /horas 7")
        except Exception as e:
            self.logger.error(f"Erro ao mostrar horas: {e}")
            self.enviar_mensagem(f"❌ Erro: {str(e)}")

    def mostrar_menu(self, args=None):
        keyboard = {
            "keyboard": [
                ["🕒 Registrar Ponto"],
                ["⏸️ Pausar Sistema", "▶️ Retomar Sistema"],
                ["📊 Status", "❌ Encerrar"],
                ["/menu"]
            ],
            "resize_keyboard": True,
            "persistent": True
        }
        
        self.enviar_mensagem(
            "🤖 Sistema de Registro de Ponto\n\n"
            "Comandos disponíveis:\n"
            "/registrar - Registrar ponto manual\n"
            "/status - Ver status detalhado\n"
            "/relatorio mes ano - Gerar relatório mensal\n"
            "/falhas [dias] - Ver falhas recentes\n"
            "/horas [dias] - Ver horas trabalhadas\n"
            "/configuracoes - Ajustar configurações\n"
            "/ajuda - Ver ajuda\n"
            "/menu - Mostrar este menu",
            keyboard
        )

    def enviar_mensagem(self, mensagem, keyboard=None):
        try:
            data = {
                "chat_id": self.chat_id,
                "text": mensagem,
                "parse_mode": "HTML"
            }
            if keyboard:
                data["reply_markup"] = keyboard
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
            self.enviar_mensagem("Ano inválido")
        except Exception as e:
            self.enviar_mensagem(f"❌ Erro ao gerar relatório anual: {e}")