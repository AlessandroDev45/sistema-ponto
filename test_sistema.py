# test_sistema.py
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

from src.telegram_controller import TelegramController
from src.utils.database import Database
from src.calculos.processor import ProcessadorDados
from src.calculos.trabalhista import CalculosTrabalhistas, ProcessadorFolha
from src.relatorios.gerador_relatorios import GeradorRelatorios
from config.config import Config

class TestSistemaPonto:
    def __init__(self):
        self.logger = self.configurar_logging()
        self.logger.info("[TESTE] Iniciando Sistema de Ponto em modo teste")
        
        try:
            self.config = Config()
            self.db = Database('teste_ponto.db')  # Banco de dados específico para testes
            self.calculadora = CalculosTrabalhistas(self.config.SALARIO_BASE)
            self.processador_folha = ProcessadorFolha(self.db, self.calculadora)
            self.gerador_relatorios = GeradorRelatorios(self.db, self.calculadora)
            
            self.telegram = TelegramController(
                self.config.TELEGRAM_TOKEN,
                self.config.TELEGRAM_CHAT_ID,
                self.db,
                self.gerador_relatorios
            )
            
            self.feriados_br = holidays.BR()
            self.sistema_ativo = True
            
            # Registrar handlers apenas para teste
            signal.signal(signal.SIGINT, self.handle_shutdown)
            signal.signal(signal.SIGTERM, self.handle_shutdown)
            
        except Exception as e:
            self.logger.critical(f"[TESTE] Erro fatal na inicialização: {e}")
            sys.exit(1)

    def configurar_logging(self):
        log_dir = Path("logs_teste")
        log_dir.mkdir(exist_ok=True)
        
        logger = logging.getLogger('TestSistemaPonto')
        logger.setLevel(logging.DEBUG)
        
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - [TESTE] %(message)s'
        )
        
        file_handler = logging.FileHandler(
            log_dir / f"teste_sistema_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        return logger

    def simular_registro_ponto(self):
        try:
            self.logger.info("[TESTE] Simulando registro de ponto")
            agora = datetime.now()
            
            eh_dia_util, motivo = self.verificar_dia_util()
            if not eh_dia_util:
                self.logger.info(f"[TESTE] Registro ignorado: {motivo}")
                self.telegram.enviar_mensagem(f"[TESTE] ℹ️ {motivo}")
                return

            # Simula registro sem acessar o sistema real
            self.db.registrar_ponto(agora, "TESTE", "SUCESSO", "Registro simulado")
            self.telegram.enviar_mensagem(
                f"[TESTE] ✅ Ponto simulado com sucesso!\n"
                f"Data: {agora.strftime('%d/%m/%Y')}\n"
                f"Hora: {agora.strftime('%H:%M:%S')}"
            )
            
        except Exception as e:
            self.logger.error(f"[TESTE] Erro no registro simulado: {e}")
            self.telegram.enviar_mensagem(f"[TESTE] ❌ Erro no registro simulado: {e}")

    def verificar_dia_util(self):
        hoje = datetime.now()
        
        if hoje.weekday() >= 5:
            return False, "Hoje é fim de semana"
        
        if hoje in self.feriados_br:
            return False, f"Hoje é feriado: {self.feriados_br[hoje]}"
            
        return True, "Dia útil"

    def testar_comandos_telegram(self):
        try:
            self.logger.info("[TESTE] Testando comandos do Telegram")
            
            # Testa cada comando disponível
            comandos_teste = [
                '/menu',
                '/status',
                '/registrar',
                '/horas 7',
                '/falhas 7',
                '/configuracoes',
                '/ajuda',
                '🕒 Registrar Ponto',
                '📊 Status'
            ]
            
            for comando in comandos_teste:
                self.logger.info(f"[TESTE] Testando comando: {comando}")
                self.telegram.processar_mensagem({"message_id": 1, "text": comando})
                time.sleep(2)  # Aguarda entre comandos
                
        except Exception as e:
            self.logger.error(f"[TESTE] Erro ao testar comandos Telegram: {e}")

    def testar_processamento_folha(self):
        try:
            self.logger.info("[TESTE] Testando processamento de folha")
            
            mes_atual = datetime.now().month
            ano_atual = datetime.now().year
            
            valores_teste = {
                'mes': mes_atual,
                'ano': ano_atual,
                'horas_normais': 160,
                'horas_extras': {
                    '60': 10, '65': 0, '75': 0,
                    '100': 0, '150': 0
                },
                'horas_noturnas': 0,
                'dias_uteis': 20,
                'domingos_feriados': 8
            }
            
            resultado = self.processador_folha.calcular_valores(valores_teste)
            if resultado:
                relatorio = self.gerador_relatorios.gerar_relatorio_mensal(
                    mes_atual, ano_atual, 'pdf'
                )
                if relatorio:
                    self.telegram.enviar_documento(
                        relatorio,
                        f"[TESTE] Relatório Mensal - {mes_atual}/{ano_atual}"
                    )
                
        except Exception as e:
            self.logger.error(f"[TESTE] Erro ao testar processamento de folha: {e}")

    def handle_shutdown(self, signum, frame):
        self.logger.info("[TESTE] Recebido sinal de encerramento")
        self.encerrar_teste()
        sys.exit(0)

    def encerrar_teste(self):
        try:
            self.sistema_ativo = False
            self.telegram.enviar_mensagem("[TESTE] 🔴 Sistema de teste sendo encerrado")
            self.logger.info("[TESTE] Sistema de teste encerrado com sucesso")
        except Exception as e:
            self.logger.error(f"[TESTE] Erro ao encerrar sistema de teste: {e}")

    def executar_testes(self):
        try:
            self.logger.info("[TESTE] Iniciando bateria de testes")
            self.telegram.enviar_mensagem("[TESTE] 🟢 Sistema de teste iniciado")
            self.telegram.mostrar_menu()
            
            # Testa menu e interação básica
            self.testar_comandos_telegram()
            
            # Simula alguns registros de ponto
            for _ in range(3):
                self.simular_registro_ponto()
                time.sleep(5)
            
            # Testa processamento de folha
            self.testar_processamento_folha()
            
            # Mantém sistema ativo por um tempo para testar interações
            tempo_teste = 300  # 5 minutos
            self.logger.info(f"[TESTE] Sistema ficará ativo por {tempo_teste} segundos")
            
            inicio = time.time()
            while self.sistema_ativo and (time.time() - inicio) < tempo_teste:
                schedule.run_pending()
                time.sleep(1)
            
            self.encerrar_teste()
                
        except Exception as e:
            self.logger.critical(f"[TESTE] Erro fatal nos testes: {e}")
            self.telegram.enviar_mensagem(f"[TESTE] 🔴 Erro crítico: {e}")
            self.encerrar_teste()
            sys.exit(1)

if __name__ == "__main__":
    load_dotenv()
    
    sistema_teste = TestSistemaPonto()
    sistema_teste.executar_testes()