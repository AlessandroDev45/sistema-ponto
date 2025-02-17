# main.py
import schedule
import time
from datetime import datetime, timedelta
import holidays
import logging
from pathlib import Path
import sys
import signal
import os
from dotenv import load_dotenv
load_dotenv(encoding='latin1')


import src
from src.telegram_controller import TelegramController
from src.utils.database import Database

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

# Imports do sistema
from src.calculos.processor import ProcessadorDados
from src.calculos.trabalhista import CalculosTrabalhistas, ProcessadorFolha
from src.relatorios.gerador_relatorios import GeradorRelatorios
from src.automacao.ponto_controller import AutomacaoPonto
from src.utils.database import Database
from config.config import Config

class SistemaPonto:
    def __init__(self):
        self.logger = self.configurar_logging()
        self.logger.info("Iniciando Sistema de Ponto")
        
        try:
            self.config = Config()  # Instância única do Config
            
            self.db = Database()
            self.calculadora = CalculosTrabalhistas(self.config.SALARIO_BASE)
            self.processador_folha = ProcessadorFolha(self.db, self.calculadora)
            self.gerador_relatorios = GeradorRelatorios(self.db, self.calculadora)
            
            self.telegram = TelegramController(
                self.config.TELEGRAM_TOKEN,
                self.config.TELEGRAM_CHAT_ID,
                self.db,
                self.gerador_relatorios
            )
            
            self.automacao = AutomacaoPonto(
                self.config.URL_SISTEMA,
                self.config.LOGIN,
                self.config.SENHA,
                self.db,
                self.telegram
            )
            
            self.feriados_br = holidays.BR()
            self.sistema_ativo = True
            
            signal.signal(signal.SIGINT, self.handle_shutdown)
            signal.signal(signal.SIGTERM, self.handle_shutdown)
            
        except Exception as e:
            self.logger.critical(f"Erro fatal na inicialização: {e}")
            sys.exit(1)

    def configurar_logging(self):
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        logger = logging.getLogger('SistemaPonto')
        logger.setLevel(logging.INFO)
        
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        file_handler = logging.FileHandler(
            log_dir / f"sistema_ponto_{datetime.now().strftime('%Y%m%d')}.log"
        )
        file_handler.setFormatter(formatter)
        
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        return logger

    def verificar_dia_util(self):
        hoje = datetime.now()
        
        if hoje.weekday() >= 5:
            return False, "Hoje é fim de semana"
        
        if hoje in self.feriados_br:
            return False, f"Hoje é feriado: {self.feriados_br[hoje]}"
            
        return True, "Dia útil"

    def registrar_ponto_automatico(self):
        try:
            if not self.sistema_ativo:
                self.logger.info("Sistema pausado, registro automático ignorado")
                return

            eh_dia_util, motivo = self.verificar_dia_util()
            if not eh_dia_util:
                self.logger.info(f"Registro ignorado: {motivo}")
                self.telegram.enviar_mensagem(f"ℹ️ {motivo}")
                return

            self.automacao.registrar_ponto()
            
        except Exception as e:
            self.logger.error(f"Erro no registro automático: {e}")
            self.telegram.enviar_mensagem(f"❌ Erro no registro automático: {e}")

    def processar_comandos_telegram(self):
        try:
            updates = self.telegram.get_updates()
            for update in updates:
                if "message" in update:
                    self.telegram.processar_mensagem(update["message"])
        except Exception as e:
            self.logger.error(f"Erro ao processar comandos Telegram: {e}")

    def processar_folha_mensal(self):
        try:
            hoje = datetime.now()
            if hoje.day == 20:  # Processa folha no dia 20
                mes_anterior = hoje.month - 1 if hoje.month > 1 else 12
                ano = hoje.year if hoje.month > 1 else hoje.year - 1
                
                self.logger.info(f"Processando folha mensal: {mes_anterior}/{ano}")
                self.telegram.enviar_mensagem(
                    f"🔄 Iniciando processamento da folha {mes_anterior}/{ano}"
                )
                
                resultado = self.processador_folha.processar_periodo(mes_anterior, ano)
                if resultado:
                    relatorio = self.gerador_relatorios.gerar_relatorio_mensal(
                        mes_anterior, ano, 'pdf'
                    )
                    if relatorio:
                        self.telegram.enviar_documento(
                            relatorio,
                            f"Relatório Mensal - {mes_anterior}/{ano}"
                        )
                
        except Exception as e:
            self.logger.error(f"Erro ao processar folha mensal: {e}")
            self.telegram.enviar_mensagem(f"❌ Erro ao processar folha mensal: {e}")

    def verificar_sistema(self):
        try:
            status = self.automacao.verificar_status()
            if not status:
                self.telegram.enviar_mensagem("⚠️ Sistema apresentando instabilidade")
        except Exception as e:
            self.logger.error(f"Erro na verificação do sistema: {e}")

    def handle_shutdown(self, signum, frame):
        self.logger.info("Recebido sinal de encerramento")
        self.encerrar_sistema()
        sys.exit(0)

    def encerrar_sistema(self):
        try:
            self.sistema_ativo = False
            self.automacao.encerrar()
            self.telegram.enviar_mensagem("🔴 Sistema sendo encerrado")
            self.logger.info("Sistema encerrado com sucesso")
        except Exception as e:
            self.logger.error(f"Erro ao encerrar sistema: {e}")

    def executar(self):
        try:
           
            self.telegram.enviar_mensagem("🟢 Sistema iniciado")
            self.telegram.mostrar_menu()
            signal.signal(signal.SIGINT, self.handle_shutdown)
            signal.signal(signal.SIGTERM, self.handle_shutdown)
            self.sistema_ativo = True
            self.logger.info("Sistema iniciado")
            
            
            # Agendamentos
            schedule.every().day.at(self.config.HORARIO_ENTRADA).do(
            self.registrar_ponto_automatico
        )
            schedule.every().day.at(self.config.HORARIO_SAIDA).do(
            self.registrar_ponto_automatico
        )
            schedule.every(30).seconds.do(self.processar_comandos_telegram)
            schedule.every(5).minutes.do(self.verificar_sistema)
            schedule.every().day.at("23:50").do(self.processar_folha_mensal)
            
            self.logger.info("Sistema iniciado e aguardando")
            
            while self.sistema_ativo:
                schedule.run_pending()
                time.sleep(1)
                
        except Exception as e:
            self.logger.critical(f"Erro fatal na execução: {e}")
            self.telegram.enviar_mensagem(f"🔴 Erro crítico: {e}")
            self.encerrar_sistema()
            sys.exit(1)

if __name__ == "__main__":
    load_dotenv()
    
    sistema = SistemaPonto()
    sistema.executar()