import sys
import os
from pathlib import Path

# Adiciona o diretório raiz ao Python Path
current_dir = Path(__file__).resolve().parent
root_dir = current_dir
sys.path.append(str(root_dir))

import schedule
import time
from datetime import datetime, timedelta
import holidays
import logging
import signal
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
            # Garantir existência dos diretórios
            os.makedirs("logs_teste", exist_ok=True)
            os.makedirs("relatorios", exist_ok=True)
            os.makedirs("backups", exist_ok=True)
            os.makedirs("database", exist_ok=True)
            
            self.config = Config.get_instance()  # Usando get_instance
            self.db = Database(os.path.join('database', 'teste_ponto.db'))
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
        
        if logger.handlers:  # Evita handlers duplicados
            return logger
            
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

            self.db.registrar_ponto(agora, "TESTE", "SUCESSO", "Registro simulado")
            msg = (
                f"[TESTE] ✅ Ponto simulado com sucesso!\n"
                f"Data: {agora.strftime('%d/%m/%Y')}\n"
                f"Hora: {agora.strftime('%H:%M:%S')}"
            )
            self.telegram.enviar_mensagem(msg)
            
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
            
            comandos_teste = [
                '/menu',
                '/status',
                '/registrar',
                '/relatorio',
                '/configuracoes',
                '/ajuda',
                '🕒 Registrar Ponto',
                '📊 Status'
            ]
            
            for comando in comandos_teste:
                self.logger.info(f"[TESTE] Testando comando: {comando}")
                self.telegram.processar_mensagem({
                    "message_id": 1, 
                    "chat": {"id": self.config.TELEGRAM_CHAT_ID},
                    "text": comando
                })
                time.sleep(2)
                
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
            
            self.testar_comandos_telegram()
            
            for _ in range(3):
                self.simular_registro_ponto()
                time.sleep(5)
            
            self.testar_processamento_folha()
            
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