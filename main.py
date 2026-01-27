#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
from pathlib import Path

# Adiciona o diretório raiz ao Python Path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)  # Adiciona o diretório atual
sys.path.append(os.path.dirname(current_dir))  # Adiciona o diretório pai

import time as time_module
import signal
import logging
import holidays
import schedule
import threading
import queue
import psutil
import platform
from datetime import datetime, timedelta, time as datetime_time
from dotenv import load_dotenv
from typing import Optional, Dict, Any

# Imports locais
from src.utils.logger import setup_logger
from config.config import Config
from src.telegram_controller import TelegramController
from src.utils.database import Database
from src.calculos.processor import ProcessadorDados
from src.calculos.trabalhista import CalculosTrabalhistas, ProcessadorFolha
from src.relatorios.gerador_relatorios import GeradorRelatorios
from src.automacao.ponto_controller import AutomacaoPonto
from src.utils.backup import BackupManager

class SystemMonitor:
    def __init__(self, logger):
        self.logger = logger
        self.start_time = datetime.now()

    def get_system_info(self) -> Dict[str, Any]:
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            uptime = datetime.now() - self.start_time
            
            return {
                'cpu_percent': cpu_percent,
                'memory_percent': memory.percent,
                'disk_percent': disk.percent,
                'uptime': str(uptime).split('.')[0],
                'platform': platform.platform(),
                'python_version': sys.version.split()[0]
            }
        except Exception as e:
            self.logger.error(f"Erro ao obter informações do sistema: {e}")
            return {
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }

class SistemaPonto:
    def __init__(self):
        try:
            # Configuração inicial
            self.logger = setup_logger('SistemaPonto')
            self.logger.info("Iniciando Sistema de Ponto")
            self.startup_time = datetime.now()
            self.ultimo_heartbeat = datetime.now()
            self.last_health_check = datetime.now()
            
            # Inicialização dos componentes
            self.config = Config.get_instance()
            self.logger.debug(f"Config instance: SALARIO_BASE={self.config.SALARIO_BASE}")
            
            # Banco de dados é opcional - continua sem persistência se falhar
            try:
                self.db = Database()
                self.logger.info("Banco de dados conectado com sucesso")
            except Exception as db_error:
                self.logger.warning(f"Banco de dados indisponível, continuando sem persistência: {db_error}")
                self.db = None
            
            self.calculadora = CalculosTrabalhistas(self.config.SALARIO_BASE)
            self.processador_folha = ProcessadorFolha(self.db, self.calculadora) if self.db else None
            self.gerador_relatorios = GeradorRelatorios(self.db, self.calculadora) if self.db else None
            self.backup_manager = BackupManager(self.config)
            
            # Inicializa Telegram e Automação
            self.telegram = TelegramController(
                self.config.TELEGRAM_TOKEN,
                self.config.TELEGRAM_CHAT_ID,
                self.db,
                self.gerador_relatorios
            )
            
            self.telegram.get_updates()
            
            self.automacao = AutomacaoPonto(
                self.config.URL_SISTEMA,
                self.config.LOGIN,
                self.config.SENHA,
                self.db,
                self.telegram,
                incognito=True
            )
            
            # Configurações adicionais
            self.feriados_br = holidays.country_holidays("BR")
            self.sistema_ativo = True
            self.modo_manutencao = False
            self.command_queue = queue.Queue()
            self.monitor = SystemMonitor(self.logger)
            
            # Configuração de sinais
            signal.signal(signal.SIGINT, self.handle_shutdown)
            signal.signal(signal.SIGTERM, self.handle_shutdown)
            
            # Criação de diretórios
            self._setup_directories()
            
        except Exception as e:
            self.logger.critical(f"Erro fatal na inicialização: {e}")
            raise

    def _setup_directories(self):
        """Cria estrutura de diretórios necessária"""
        try:
            directories = ['logs', 'backups', 'relatorios', 'temp', 'database']
            for dir_name in directories:
                path = Path(dir_name)
                path.mkdir(exist_ok=True)
                self.logger.debug(f"Diretório verificado/criado: {path}")
        except Exception as e:
            self.logger.error(f"Erro ao criar diretórios: {e}")
            raise

    def verificar_dia_util(self) -> tuple[bool, str]:
        """Verifica se é dia útil"""
        hoje = datetime.now().date()
        
        if hoje.weekday() >= 5:
            return False, "Hoje é fim de semana"
        
        if hoje in self.feriados_br:
            return False, f"Hoje é feriado: {self.feriados_br[hoje]}"
            
        return True, "Dia útil"

    def _obter_periodo_atual(self):
        """Retorna o período atual: manha, tarde ou noite"""
        hora = datetime.now().hour
        if hora < 12:
            return 'manha', 'manhã'
        elif hora < 18:
            return 'tarde', 'tarde'
        else:
            return 'noite', 'noite'

    def _verificar_registro_existente(self):
        """Verifica se já existe registro no período atual"""
        if not self.db:
            return False, []
        
        hoje = datetime.now().date()
        periodo_key, _ = self._obter_periodo_atual()
        registros = self.db.verificar_registro_periodo(hoje, periodo_key)
        return len(registros) > 0, registros

    def registrar_ponto_automatico(self):
        """Registra ponto automaticamente"""
        try:
            if not self.sistema_ativo:
                self.logger.info("Sistema pausado, registro automático ignorado")
                return

            eh_dia_util, motivo = self.verificar_dia_util()
            if not eh_dia_util:
                self.logger.info(f"Registro ignorado: {motivo}")
                self.telegram.enviar_mensagem(f"ℹ️ {motivo}")
                return

            # Verifica se já existe registro no período atual (batido manualmente)
            ja_registrado, registros = self._verificar_registro_existente()
            if ja_registrado:
                periodo_key, periodo_nome = self._obter_periodo_atual()
                registros_info = []
                for reg in registros:
                    data_hora_str = reg[1]
                    if isinstance(data_hora_str, str):
                        dt = datetime.strptime(data_hora_str.split('.')[0], '%Y-%m-%d %H:%M:%S')
                    else:
                        dt = data_hora_str
                    registros_info.append(dt.strftime('%H:%M'))
                
                self.logger.info(f"Registro automático ignorado - já existe registro no período: {', '.join(registros_info)}")
                self.telegram.enviar_mensagem(
                    f"ℹ️ Registro automático ignorado\n"
                    f"Já existe registro de {periodo_nome}: {', '.join(registros_info)}"
                )
                return

            if not self.automacao.verificar_disponibilidade():
                self.logger.error("Sistema indisponível para registro")
                return

            resultado = self.automacao.registrar_ponto()
            
            if resultado['sucesso']:
                self.logger.info("Ponto registrado com sucesso")
                self.telegram.enviar_mensagem(resultado['mensagem'])
            else:
                self.logger.error(f"Falha no registro: {resultado['mensagem']}")
                self.telegram.enviar_mensagem(f"❌ {resultado['mensagem']}")
            
        except Exception as e:
            self.logger.error(f"Erro no registro automático: {e}")
            self.telegram.enviar_mensagem(f"❌ Erro no registro automático: {e}")

    def verificar_status(self):
        """Verifica status do sistema e envia heartbeat"""
        try:
            agora = datetime.now()
            horario_atual = agora.strftime('%H:%M')
            system_info = self.monitor.get_system_info()
            
            status_msg = (
                f"🕒 Status do Sistema\n\n"
                f"Horário Atual: {horario_atual}\n"
                f"Próximo Registro: {self._calcular_proximo_horario()}\n"
                f"Sistema: {'🟢 Ativo' if self.sistema_ativo else '🔴 Pausado'}\n\n"
                f"Recursos do Sistema:\n"
                f"CPU: {system_info['cpu_percent']}%\n"
                f"Memória: {system_info['memory_percent']}%\n"
                f"Disco: {system_info['disk_percent']}%\n"
                f"Uptime: {system_info['uptime']}\n"
            )

            # Envia heartbeat a cada 30 minutos
            if (agora - self.ultimo_heartbeat).total_seconds() > 1800:
                self.telegram.enviar_mensagem(status_msg)
                self.ultimo_heartbeat = agora
                
            return status_msg
                
        except Exception as e:
            self.logger.error(f"Erro na verificação do sistema: {e}")
            return f"❌ Erro ao verificar status: {e}"

    def _calcular_proximo_horario(self):
        """Calcula próximo horário de registro"""
        try:
            agora = datetime.now().time()
            entrada = self.config.HORARIO_ENTRADA
            saida = self.config.HORARIO_SAIDA

            # Converter strings para time se necessário
            if isinstance(entrada, str):
                h, m, s = map(int, entrada.split(':'))
                entrada = datetime_time(h, m, s)
            if isinstance(saida, str):
                h, m, s = map(int, saida.split(':'))
                saida = datetime_time(h, m, s)

            if agora < entrada:
                return entrada.strftime('%H:%M')
            elif agora < saida:
                return saida.strftime('%H:%M')
            else:
                return f"{entrada.strftime('%H:%M')} (amanhã)"

        except Exception as e:
            self.logger.error(f"Erro ao calcular próximo horário: {e}")
            return "Erro ao calcular próximo horário"

    def health_check(self) -> bool:
        """Verifica saúde do sistema"""
        try:
            system_info = self.monitor.get_system_info()
            
            # Verifica recursos do sistema
            if (system_info['cpu_percent'] > 90 or 
                system_info['memory_percent'] > 90 or 
                system_info['disk_percent'] > 90):
                
                self.telegram.enviar_mensagem(
                    "⚠️ Alerta de recursos do sistema:\n" +
                    f"CPU: {system_info['cpu_percent']}%\n" +
                    f"Memória: {system_info['memory_percent']}%\n" +
                    f"Disco: {system_info['disk_percent']}%"
                )
                return False
                
            # Verifica conexão com sistema de ponto
            if not self.automacao.verificar_conexao():
                self.telegram.enviar_mensagem("⚠️ Sistema de ponto inacessível")
                return False
                
            # Verifica banco de dados (se disponível)
            if self.db and not self.db.verificar_conexao():
                self.telegram.enviar_mensagem("⚠️ Problema com banco de dados")
                return False
                
            self.last_health_check = datetime.now()
            return True
            
        except Exception as e:
            self.logger.error(f"Erro no health check: {e}")
            return False

    def verificar_sistema(self):
        """Verifica saúde e status geral do sistema"""
        try:
            self.health_check()
            return self.verificar_status()
        except Exception as e:
            self.logger.error(f"Erro ao verificar sistema: {e}")
            return f"❌ Erro ao verificar sistema: {e}"

    def processar_comando_async(self, comando: str, *args):
        """Processa comandos de forma assíncrona"""
        try:
            self.command_queue.put((comando, args))
            self.logger.debug(f"Comando enfileirado: {comando}")
        except Exception as e:
            self.logger.error(f"Erro ao enfileirar comando: {e}")
            
    def worker_thread(self):
        """Thread worker para processar comandos"""
        while self.sistema_ativo:
            try:
                comando, args = self.command_queue.get(timeout=1)
                self.logger.debug(f"Processando comando: {comando}")
                
                if hasattr(self, comando):
                    method = getattr(self, comando)
                    method(*args)
                else:
                    self.logger.warning(f"Comando não encontrado: {comando}")
                    
                self.command_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"Erro no worker thread: {e}")
                
                
    def processar_comandos_telegram(self):
        """Processa comandos recebidos via Telegram"""
        try:
            updates = self.telegram.get_updates()
            for update in updates:
                try:
                    if "message" in update:
                        mensagem = update["message"]
                        comando = mensagem.get("text", "")
                        chat_id = mensagem["chat"]["id"]
                        
                        self.logger.info(f"Comando recebido: {comando}")
                        
                        # Verifica se é um chat autorizado
                        if str(chat_id) != self.config.TELEGRAM_CHAT_ID:
                            self.logger.warning(f"Tentativa de acesso não autorizado: {chat_id}")
                            continue
                        
                        # Processa comando
                        if comando == "📊 Status":
                            status = self.verificar_status()
                            self.telegram.enviar_mensagem(status)
                            
                        elif comando == "🕒 Registrar Ponto":
                            self.registrar_ponto_automatico()
                            
                        elif comando.startswith("/"):
                            self.processar_comando_telegram(comando)
                            
                except Exception as e:
                    self.logger.error(f"Erro ao processar mensagem: {e}")
                    continue
                    
        except Exception as e:
            self.logger.error(f"Erro ao processar comandos Telegram: {e}")

    def processar_comando_telegram(self, comando: str):
        """Processa comandos específicos do Telegram"""
        try:
            partes = comando.split()
            cmd = partes[0].lower()
            args = partes[1:] if len(partes) > 1 else None
            
            comandos = {
                '/status': self.verificar_status,
                '/registrar': self.registrar_ponto_automatico,
                '/relatorio': self.gerar_relatorio,
                '/pausar': self.pausar_sistema,
                '/retomar': self.retomar_sistema,
                '/manutencao': self.ativar_modo_manutencao,
                '/encerrar': self.solicitar_confirmacao_encerramento
            }
            
            if cmd in comandos:
                if args:
                    comandos[cmd](args)
                else:
                    comandos[cmd]()
            else:
                self.telegram.enviar_mensagem("❌ Comando não reconhecido")
                
        except Exception as e:
            self.logger.error(f"Erro ao processar comando Telegram: {e}")
            self.telegram.enviar_mensagem(f"❌ Erro ao processar comando: {e}")

    def processar_folha_mensal(self):
        """Processa folha mensal"""
        try:
            hoje = datetime.now()
            if hoje.day == 20:  # Processa folha no dia 20
                if not self.processador_folha or not self.gerador_relatorios:
                    self.logger.warning("Processamento de folha desabilitado (banco de dados indisponível)")
                    return
                    
                mes_anterior = hoje.month - 1 if hoje.month > 1 else 12
                ano = hoje.year if hoje.month > 1 else hoje.year - 1
                
                self.logger.info(f"Processando folha mensal: {mes_anterior}/{ano}")
                self.telegram.enviar_mensagem(f"🔄 Iniciando processamento da folha {mes_anterior}/{ano}")
                
                resultado = self.processador_folha.processar_periodo(mes_anterior, ano)
                if resultado:
                    relatorio = self.gerador_relatorios.gerar_relatorio_mensal(mes_anterior, ano, 'pdf')
                    if relatorio:
                        self.telegram.enviar_documento(relatorio, f"Relatório Mensal - {mes_anterior}/{ano}")
                        self.telegram.enviar_mensagem("✅ Folha processada com sucesso")
                    else:
                        self.telegram.enviar_mensagem("⚠️ Erro ao gerar relatório")
                else:
                    self.telegram.enviar_mensagem("❌ Erro ao processar folha")
                
        except Exception as e:
            self.logger.error(f"Erro ao processar folha mensal: {e}")
            self.telegram.enviar_mensagem(f"❌ Erro ao processar folha mensal: {e}")

    def gerar_relatorio(self, args=None):
        """Gera relatório mensal ou anual"""
        try:
            if not args or len(args) < 1:
                self.telegram.enviar_mensagem("❌ Formato: /relatorio [mensal/anual] [mes] [ano]")
                return
                
            tipo = args[0].lower()
            
            if not self.gerador_relatorios:
                self.telegram.enviar_mensagem("❌ Relatórios indisponíveis (banco de dados não conectado)")
                return
                
            if tipo == "mensal" and len(args) == 3:
                mes = int(args[1])
                ano = int(args[2])
                relatorio = self.gerador_relatorios.gerar_relatorio_mensal(mes, ano, 'pdf')
                
            elif tipo == "anual" and len(args) == 2:
                ano = int(args[1])
                relatorio = self.gerador_relatorios.gerar_relatorio_anual(ano, 'pdf')
                
            else:
                self.telegram.enviar_mensagem("❌ Argumentos inválidos")
                return
                
            if relatorio:
                self.telegram.enviar_documento(relatorio, f"Relatório {tipo.title()} - {ano}")
                self.telegram.enviar_mensagem("✅ Relatório gerado com sucesso")
            else:
                self.telegram.enviar_mensagem("❌ Erro ao gerar relatório")
                
        except Exception as e:
            self.logger.error(f"Erro ao gerar relatório: {e}")
            self.telegram.enviar_mensagem(f"❌ Erro ao gerar relatório: {e}")
            
    def pausar_sistema(self, args=None):
        """Pausa o sistema"""
        try:
            if self.sistema_ativo:
                self.sistema_ativo = False
                # Salva estado no banco para persistir entre execuções
                if self.db:
                    self.db.registrar_configuracao('sistema_pausado', 'true')
                self.logger.info("Sistema pausado")
                self.telegram.enviar_mensagem("⏸️ Sistema pausado")
            else:
                self.telegram.enviar_mensagem("ℹ️ Sistema já está pausado")
        except Exception as e:
            self.logger.error(f"Erro ao pausar sistema: {e}")
            self.telegram.enviar_mensagem(f"❌ Erro ao pausar sistema: {e}")

    def retomar_sistema(self, args=None):
        """Retoma o sistema"""
        try:
            if not self.sistema_ativo:
                self.sistema_ativo = True
                # Salva estado no banco para persistir entre execuções
                if self.db:
                    self.db.registrar_configuracao('sistema_pausado', 'false')
                self.logger.info("Sistema retomado")
                self.telegram.enviar_mensagem("▶️ Sistema retomado")
            else:
                self.telegram.enviar_mensagem("ℹ️ Sistema já está ativo")
        except Exception as e:
            self.logger.error(f"Erro ao retomar sistema: {e}")
            self.telegram.enviar_mensagem(f"❌ Erro ao retomar sistema: {e}")

    def ativar_modo_manutencao(self, args=None):
        """Ativa modo manutenção"""
        try:
            self.modo_manutencao = True
            self.logger.info("Modo manutenção ativado")
            self.telegram.enviar_mensagem("🔧 Sistema entrou em modo manutenção")
        except Exception as e:
            self.logger.error(f"Erro ao ativar modo manutenção: {e}")
            self.telegram.enviar_mensagem(f"❌ Erro ao ativar modo manutenção: {e}")

    def desativar_modo_manutencao(self, args=None):
        """Desativa modo manutenção"""
        try:
            self.modo_manutencao = False
            self.logger.info("Modo manutenção desativado")
            self.telegram.enviar_mensagem("✅ Sistema saiu do modo manutenção")
        except Exception as e:
            self.logger.error(f"Erro ao desativar modo manutenção: {e}")
            self.telegram.enviar_mensagem(f"❌ Erro ao desativar modo manutenção: {e}")

    def solicitar_confirmacao_encerramento(self, args=None):
        """Solicita confirmação antes de encerrar o sistema"""
        try:
            self.telegram.enviar_mensagem(
                "⚠️ Tem certeza que deseja encerrar o sistema?\n"
                "Digite 'CONFIRMAR' para encerrar ou qualquer outra tecla para cancelar"
            )
            self.telegram.aguardando_confirmacao = True
        except Exception as e:
            self.logger.error(f"Erro ao solicitar confirmação: {e}")
            self.telegram.enviar_mensagem(f"❌ Erro ao solicitar confirmação: {e}")

    def handle_shutdown(self, signum, frame):
        """Manipula sinais de encerramento"""
        self.logger.info(f"Recebido sinal de encerramento: {signum}")
        self.encerrar_sistema()
        sys.exit(0)

    def encerrar_sistema(self):
        """Encerra o sistema de forma segura"""
        try:
            self.logger.info("Iniciando encerramento do sistema")
            self.sistema_ativo = False
            
            # Backup final
            try:
                self.backup_manager.criar_backup('encerramento')
                self.logger.info("Backup de encerramento criado")
            except Exception as backup_error:
                self.logger.error(f"Erro no backup de encerramento: {backup_error}")
            
            # Encerra automação
            try:
                if hasattr(self, 'automacao'):
                    self.automacao.encerrar()
                    self.logger.info("Automação encerrada")
            except Exception as automacao_error:
                self.logger.error(f"Erro ao encerrar automação: {automacao_error}")
            
            # Notifica encerramento
            if hasattr(self, 'telegram'):
                self.telegram.enviar_mensagem("🔴 Sistema sendo encerrado")
                time_module.sleep(1)  # Aguarda envio da mensagem
            
            self.logger.info("Sistema encerrado com sucesso")
            
        except Exception as e:
            self.logger.critical(f"Erro crítico durante encerramento: {e}")
        finally:
            logging.shutdown()

    def executar(self):
        """Método principal de execução do sistema"""
        try:
            # Inicializa worker thread
            worker = threading.Thread(target=self.worker_thread, daemon=True)
            worker.start()
            
            # Notificação inicial
            self.telegram.enviar_mensagem("🟢 Sistema iniciado")
            self.telegram.mostrar_menu()
            
            # Configura agendamentos
            schedule.every().day.at(str(self.config.HORARIO_ENTRADA)).do(self.registrar_ponto_automatico)
            schedule.every().day.at(str(self.config.HORARIO_SAIDA)).do(self.registrar_ponto_automatico)
            schedule.every(5).seconds.do(self.processar_comandos_telegram)
            schedule.every(5).minutes.do(self.verificar_sistema)
            schedule.every().day.at("23:50").do(self.processar_folha_mensal)
            schedule.every(1).minutes.do(self.verificar_status)
            schedule.every().day.at("00:00").do(self.backup_manager.criar_backup, 'diario')
            schedule.every().sunday.at("00:00").do(self.backup_manager.criar_backup, 'semanal')
            schedule.every().day.at("01:00").do(self.backup_manager.limpar_backups_antigos)
            schedule.every(15).minutes.do(self.health_check)
            
            self.logger.info("Sistema iniciado e aguardando comandos")
            
            # Loop principal
            while True:
                if self.modo_manutencao:
                    self.logger.info("Sistema em modo manutenção")
                    time_module.sleep(60)
                    continue
                    
                if not self.sistema_ativo:
                    self.logger.info("Sistema pausado")
                    time_module.sleep(5)
                    continue
                
                try:
                    schedule.run_pending()
                    time_module.sleep(1)
                except Exception as e:
                    self.logger.error(f"Erro no loop principal: {e}")
                    time_module.sleep(5)
                    
        except Exception as e:
            self.logger.critical(f"Erro fatal na execução: {e}")
            self.telegram.enviar_mensagem(f"🔴 Erro crítico: {e}")
            self.encerrar_sistema()
            raise
        
def main():
    """Função principal do programa"""
    sistema = None
    try:
        # Carrega variáveis de ambiente
        load_dotenv()
        
        # Inicializa o sistema
        sistema = SistemaPonto()
        
        # Configura sinais
        signal.signal(signal.SIGINT, sistema.handle_shutdown)
        signal.signal(signal.SIGTERM, sistema.handle_shutdown)
        
        # Log de configurações importantes
        config = Config.get_instance()
        print(f"Horário de entrada: {config.HORARIO_ENTRADA}")
        print(f"Horário de saída: {config.HORARIO_SAIDA}")
        
        # Executa o sistema
        sistema.executar()
        
    except KeyboardInterrupt:
        print("\nInterrupção pelo usuário detectada")
        if sistema:
            sistema.telegram.enviar_mensagem("🔴 Sistema sendo encerrado por interrupção do usuário")
            time_module.sleep(1)
            sistema.encerrar_sistema()
            
    except Exception as e:
        print(f"Erro fatal: {e}", file=sys.stderr)
        if sistema:
            sistema.telegram.enviar_mensagem(f"🔴 Erro fatal: {e}")
            time_module.sleep(1)
            sistema.encerrar_sistema()
        sys.exit(1)
        
    finally:
        if sistema:
            try:
                sistema.encerrar_sistema()
            except:
                pass
        sys.exit(0)

if __name__ == "__main__":
    pid_file = "sistema_ponto.pid"
    try:
        # Verifica se já existe uma instância rodando
        if os.path.exists(pid_file):
            with open(pid_file, 'r') as f:
                old_pid = int(f.read())
                if psutil.pid_exists(old_pid):
                    print(f"Sistema já está rodando (PID: {old_pid})")
                    sys.exit(1)
        
        # Cria arquivo PID
        with open(pid_file, 'w') as f:
            f.write(str(os.getpid()))
        
        main()
        
    except Exception as e:
        print(f"Erro fatal na inicialização: {e}", file=sys.stderr)
        sys.exit(1)
        
    finally:
        # Remove arquivo PID ao encerrar
        try:
            if os.path.exists(pid_file):
                os.remove(pid_file)
        except:
            pass