#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import time
import signal
import logging
import holidays
import schedule
import threading
import queue
import psutil
import platform
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv
from typing import Optional, Dict, Any

# Configuração de diretórios
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

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

class SistemaPonto:
    def __init__(self):
        self.logger = setup_logger('SistemaPonto')
        self.logger.info("Iniciando Sistema de Ponto")
        self.startup_time = datetime.now()
        self.ultimo_heartbeat = datetime.now()
        self.last_health_check = datetime.now()
        self.monitor = SystemMonitor(self.logger)

        try:
            self.config = Config.get_instance()
            self.logger.debug(f"Config instance: SALARIO_BASE={self.config.SALARIO_BASE}")
            self.db = Database()
            self.calculadora = CalculosTrabalhistas(self.config.SALARIO_BASE)  # Passa o salário base
            self.processador_folha = ProcessadorFolha(self.db, self.calculadora)
            self.gerador_relatorios = GeradorRelatorios(self.db, self.calculadora)
            self.backup_manager = BackupManager(self.config)
            
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
                self.telegram
            )
            
            self.feriados_br = holidays.BR()
            self.sistema_ativo = True
            self.modo_manutencao = False
            self.command_queue = queue.Queue()
            
            signal.signal(signal.SIGINT, self.handle_shutdown)
            signal.signal(signal.SIGTERM, self.handle_shutdown)
            
            self._setup_directories()
            
        except Exception as e:
            self.logger.critical(f"Erro fatal na inicialização: {e}")
            sys.exit(1)

    def verificar_status(self):
        """Verifica status do sistema e envia heartbeat"""
        try:
            status = self.automacao.verificar_status()
            if not status:
                self.telegram.enviar_mensagem("⚠️ Sistema apresentando instabilidade")
                
            agora = datetime.now()
            if (agora - self.ultimo_heartbeat).total_seconds() > 1800:  # 30 minutos
                self.telegram.enviar_mensagem(
                    "💓 Sistema online\nÚltimo status: {agora.strftime('%H:%M:%S')}"
                )
                self.ultimo_heartbeat = agora
                
        except Exception as e:
            self.logger.error(f"Erro na verificação do sistema: {e}")

    def _setup_directories(self):
        """Cria estrutura de diretórios necessária"""
        directories = ['logs', 'backups', 'relatorios', 'temp', 'database']
        for dir_name in directories:
            Path(dir_name).mkdir(exist_ok=True)

    def health_check(self) -> bool:
        """Verifica saúde do sistema"""
        try:
            system_info = self.monitor.get_system_info()
            
            if system_info['cpu_percent'] > 90 or system_info['memory_percent'] > 90 or system_info['disk_percent'] > 90:
                self.telegram.enviar_mensagem(
                    "⚠️ Alerta de recursos do sistema:\n" +
                    f"CPU: {system_info['cpu_percent']}%\n" +
                    f"Memória: {system_info['memory_percent']}%\n" +
                    f"Disco: {system_info['disk_percent']}%"
                )
                return False
                
            if not self.automacao.verificar_conexao():
                self.telegram.enviar_mensagem("⚠️ Sistema de ponto inacessível")
                return False
                
            self.last_health_check = datetime.now()
            return True
            
        except Exception as e:
            self.logger.error(f"Erro no health check: {e}")
            return False

    def processar_comando_async(self, comando: str, *args):
        """Processa comandos de forma assíncrona"""
        self.command_queue.put((comando, args))

    def worker_thread(self):
        """Thread worker para processar comandos"""
        while self.sistema_ativo:
            try:
                comando, args = self.command_queue.get(timeout=1)
                if hasattr(self, comando):
                    getattr(self, comando)(*args)
                self.command_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"Erro no worker thread: {e}")

    def executar(self):
        """Método principal de execução do sistema"""
        try:
            worker = threading.Thread(target=self.worker_thread, daemon=True)
            worker.start()
            
            self.telegram.enviar_mensagem("🟢 Sistema iniciado")
            self.telegram.mostrar_menu()
            
            # Usar a instância do Config para horários
            config = self.config  # Já inicializado como instância
            self.logger.debug(f"Usando horários: Entrada={config.HORARIO_ENTRADA}, Saída={config.HORARIO_SAIDA}")
            
            schedule.every().day.at(config.HORARIO_ENTRADA).do(self.registrar_ponto_automatico)
            schedule.every().day.at(config.HORARIO_SAIDA).do(self.registrar_ponto_automatico)
            schedule.every(5).seconds.do(self.processar_comandos_telegram)
            schedule.every(5).minutes.do(self.verificar_sistema)
            schedule.every().day.at("23:50").do(self.processar_folha_mensal)
            schedule.every(1).minutes.do(self.verificar_status)
            
            schedule.every().day.at("00:00").do(self.backup_manager.criar_backup, 'diario')
            schedule.every().sunday.at("00:00").do(self.backup_manager.criar_backup, 'semanal')
            schedule.every().day.at("01:00").do(self.backup_manager.limpar_backups_antigos)
            
            schedule.every(15).minutes.do(self.health_check)
            
            self.logger.info("Sistema iniciado e aguardando comandos")
            
            while True:
                if self.modo_manutencao:
                    self.logger.info("Sistema em modo manutenção")
                    time.sleep(60)
                    continue
                    
                if not self.sistema_ativo:
                    self.logger.info("Sistema pausado")
                    time.sleep(5)
                    continue
                
                try:
                    schedule.run_pending()
                    time.sleep(1)
                except Exception as e:
                    self.logger.error(f"Erro no loop principal: {e}")
                    time.sleep(5)
                    
        except Exception as e:
            self.logger.critical(f"Erro fatal na execução: {e}")
            self.telegram.enviar_mensagem(f"🔴 Erro crítico: {e}")
            self.encerrar_sistema()
            sys.exit(1)

    def verificar_dia_util(self) -> tuple[bool, str]:
        """Verifica se é dia útil"""
        hoje = datetime.now()
        
        if hoje.weekday() >= 5:
            return False, "Hoje é fim de semana"
        
        if hoje in self.feriados_br:
            return False, f"Hoje é feriado: {self.feriados_br[hoje]}"
            
        return True, "Dia útil"

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

            if not self.automacao.verificar_disponibilidade():
                self.logger.error("Sistema indisponível para registro")
                return

            self.automacao.registrar_ponto_com_retry()
            
        except Exception as e:
            self.logger.error(f"Erro no registro automático: {e}")
            self.telegram.enviar_mensagem(f"❌ Erro no registro automático: {e}")

    def processar_comandos_telegram(self):
        try:
            updates = self.telegram.get_updates()
            for update in updates:
                try:
                    if "message" in update:
                        self.logger.info(f"Comando recebido: {update['message'].get('text', 'Sem texto')}")
                        self.telegram.processar_mensagem(update["message"])
                except Exception as e:
                    self.logger.error(f"Erro ao processar mensagem individual: {e}")
                    continue
        except Exception as e:
            self.logger.error(f"Erro ao processar comandos Telegram: {e}")

    def processar_folha_mensal(self):
        """Processa folha mensal"""
        try:
            hoje = datetime.now()
            if hoje.day == 20:  # Processa folha no dia 20
                mes_anterior = hoje.month - 1 if hoje.month > 1 else 12
                ano = hoje.year if hoje.month > 1 else hoje.year - 1
                
                self.logger.info(f"Processando folha mensal: {mes_anterior}/{ano}")
                self.telegram.enviar_mensagem(f"🔄 Iniciando processamento da folha {mes_anterior}/{ano}")
                
                resultado = self.processador_folha.processar_periodo(mes_anterior, ano)
                if resultado:
                    relatorio = self.gerador_relatorios.gerar_relatorio_mensal(mes_anterior, ano, 'pdf')
                    if relatorio:
                        self.telegram.enviar_documento(relatorio, f"Relatório Mensal - {mes_anterior}/{ano}")
                
        except Exception as e:
            self.logger.error(f"Erro ao processar folha mensal: {e}")
            self.telegram.enviar_mensagem(f"❌ Erro ao processar folha mensal: {e}")

    def verificar_sistema(self):
        """Verifica status do sistema"""
        try:
            status = self.automacao.verificar_status()
            if not status:
                self.telegram.enviar_mensagem("⚠️ Sistema apresentando instabilidade")
                
            if (datetime.now() - self.last_health_check).total_seconds() > 900:  # 15 min
                self.health_check()
                
        except Exception as e:
            self.logger.error(f"Erro na verificação do sistema: {e}")

    def ativar_modo_manutencao(self, args=None):
        """Ativa modo manutenção"""
        self.modo_manutencao = True
        self.telegram.enviar_mensagem("🔧 Sistema entrou em modo manutenção")
        
    def desativar_modo_manutencao(self, args=None):
        """Desativa modo manutenção"""
        self.modo_manutencao = False
        self.telegram.enviar_mensagem("✅ Sistema saiu do modo manutenção")

    def handle_shutdown(self, signum, frame):
        """Manipula sinais de encerramento"""
        self.logger.info("Recebido sinal de encerramento")
        self.encerrar_sistema()
        sys.exit(0)

    def encerrar_sistema(self):
        """Encerra o sistema graciosamente"""
        try:
            self.sistema_ativo = False
            
            if hasattr(self, 'command_queue'):
                self.command_queue.join()
            
            self.backup_manager.criar_backup('encerramento')
            self.automacao.encerrar()
            self.telegram.enviar_mensagem("🔴 Sistema sendo encerrado")
            self.logger.info("Sistema encerrado com sucesso")
            
        except Exception as e:
            self.logger.error(f"Erro ao encerrar sistema: {e}")

def main():
    sistema = None
    try:
        load_dotenv()
        sistema = SistemaPonto()
        
        signal.signal(signal.SIGINT, sistema.handle_shutdown)
        signal.signal(signal.SIGTERM, sistema.handle_shutdown)
        
        config = Config.get_instance()
        print(f"Horário de entrada: {config.HORARIO_ENTRADA}")
        print(f"Horário de saída: {config.HORARIO_SAIDA}")
        print(f"Salário base: {config.SALARIO_BASE}")

        sistema.executar()
    except KeyboardInterrupt:
        if sistema:
            sistema.telegram.enviar_mensagem("🔴 Sistema sendo encerrado por interrupção do usuário")
            time.sleep(1)
            sistema.encerrar_sistema()
    except Exception as e:
        print(f"Erro fatal: {e}", file=sys.stderr)
        if sistema:
            sistema.telegram.enviar_mensagem(f"🔴 Erro fatal: {e}")
            time.sleep(1)
            sistema.encerrar_sistema()
        sys.exit(1)

if __name__ == "__main__":
    main()