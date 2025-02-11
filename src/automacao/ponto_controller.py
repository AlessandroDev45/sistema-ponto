# automacao/ponto_controller.py
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from datetime import datetime, timedelta
import time
import logging
import os

class AutomacaoPonto:
    def __init__(self, url, login, senha, database, telegram=None):
        self.url = url
        self.login = login
        self.senha = senha
        self.db = database
        self.telegram = telegram
        self.driver = None
        self.sistema_ativo = True
        self.ultimo_registro = None
        self.logger = logging.getLogger('AutomacaoPonto')
        self._configurar_driver()

    def _configurar_driver(self):
        try:
            chrome_options = Options()
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--log-level=3')
            chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
            
            service = Service(log_path=os.devnull)
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.maximize_window()
            self.logger.info("Driver do Chrome configurado com sucesso")
        except Exception as e:
            self.logger.error(f"Erro ao configurar driver: {e}")
            self._notificar_erro("configuração do driver", str(e))
            raise

    def _notificar_erro(self, tipo, mensagem):
        erro = f"❌ Erro de {tipo}: {mensagem}"
        self.logger.error(erro)
        if self.telegram:
            self.telegram.enviar_mensagem(erro)
        self.db.registrar_falha(tipo, mensagem)

    def _notificar_sucesso(self, mensagem):
        self.logger.info(mensagem)
        if self.telegram:
            self.telegram.enviar_mensagem(mensagem)

    def fazer_login(self):
        try:
            self.logger.info("Iniciando processo de login")
            self.driver.get(self.url)
            time.sleep(2)
            
            campo_login = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, 
                '/html/body/app-root/div/div/app-login/div[1]/div[1]/form/po-input/po-field-container/div/div[2]/input'))
            )
            campo_login.send_keys(self.login)
            
            campo_senha = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, 
                '/html/body/app-root/div/div/app-login/div[1]/div[1]/form/po-password/po-field-container/div/div[2]/input'))
            )
            campo_senha.send_keys(self.senha)
            campo_senha.send_keys(Keys.RETURN)
            time.sleep(2)
            
            self._notificar_sucesso("✅ Login realizado com sucesso")
            return True
            
        except Exception as e:
            self._notificar_erro("login", str(e))
            return False

    def navegar_para_ponto(self):
        try:
            self.logger.info("Navegando para página de ponto")
            menu1 = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, 
                '/html/body/app-root/div/div/div[2]/po-menu/div[2]/nav/div/div/div[3]/po-menu-item/div/div[1]/div'))
            )
            menu1.click()
            time.sleep(1)

            menu2 = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, 
                '/html/body/app-root/div/div/div[2]/po-menu/div[2]/nav/div/div/div[3]/po-menu-item/div/div[2]/div[3]/po-menu-item/a/div/div'))
            )
            menu2.click()
            time.sleep(1)

            try:
                botao_modal = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, 
                    '//*[@id="news-modal"]/div/div/div/div/div/div[2]/div/button'))
                )
                botao_modal.click()
                self.logger.info("Modal fechado")
            except:
                self.logger.info("Sem modal para fechar")

            return True

        except Exception as e:
            self._notificar_erro("navegação", str(e))
            return False

    def registrar_ponto(self, force=False):
        try:
            if not force and not self.verificar_horario():
                return False

            if not self.sistema_ativo:
                self._notificar_erro("registro", "Sistema está pausado")
                return False

            self.logger.info("Iniciando registro de ponto")
            if not self.fazer_login():
                return False

            if not self.navegar_para_ponto():
                return False

            botao_ponto = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, '//*[@id="div-swipeButtonText"]'))
            )
            
            self.logger.info("Registrando ponto")
            botao_ponto.click()
            time.sleep(1)
            botao_ponto.click()
            time.sleep(1)
            
            agora = datetime.now()
            self.ultimo_registro = agora
            
            self.db.registrar_ponto(
                agora,
                "AUTOMATICO" if not force else "MANUAL",
                "SUCESSO"
            )
            
            msg = (
                f"✅ Ponto registrado com sucesso!\n"
                f"Data: {agora.strftime('%d/%m/%Y')}\n"
                f"Hora: {agora.strftime('%H:%M:%S')}\n"
                f"Tipo: {'Automático' if not force else 'Manual'}"
            )
            self._notificar_sucesso(msg)
            return True

        except Exception as e:
            self._notificar_erro("registro de ponto", str(e))
            return False
        finally:
            try:
                self.driver.quit()
                self._configurar_driver()
            except:
                pass

    def verificar_horario(self):
        try:
            from config.config import Config
            hora_atual = datetime.now().strftime('%H:%M')
            
            if hora_atual not in [Config.HORARIO_ENTRADA, Config.HORARIO_SAIDA]:
                self.logger.info(f"Fora do horário de registro: {hora_atual}")
                return False

            if self.ultimo_registro:
                minutos_desde_ultimo = (datetime.now() - self.ultimo_registro).total_seconds() / 60
                if minutos_desde_ultimo < Config.INTERVALO_MINIMO:
                    self._notificar_erro(
                        "verificação",
                        f"Intervalo mínimo não respeitado: {minutos_desde_ultimo:.0f} minutos"
                    )
                    return False

            return True

        except Exception as e:
            self._notificar_erro("verificação de horário", str(e))
            return False

    def verificar_status(self):
        try:
            status = {
                'sistema_ativo': self.sistema_ativo,
                'ultimo_registro': self.ultimo_registro,
                'proximo_horario': self._calcular_proximo_horario()
            }
            return status
        except Exception as e:
            self._notificar_erro("verificação de status", str(e))
            return None

    def _calcular_proximo_horario(self):
        from config.config import Config
        agora = datetime.now()
        hora_atual = agora.strftime('%H:%M')
        
        if hora_atual < Config.HORARIO_ENTRADA:
            return Config.HORARIO_ENTRADA
        elif hora_atual < Config.HORARIO_SAIDA:
            return Config.HORARIO_SAIDA
        else:
            amanha = agora + timedelta(days=1)
            return f"{Config.HORARIO_ENTRADA} (amanhã)"

    def pausar_sistema(self):
        self.sistema_ativo = False
        self._notificar_sucesso("Sistema pausado")

    def retomar_sistema(self):
        self.sistema_ativo = True
        self._notificar_sucesso("Sistema retomado")

    def encerrar(self):
        try:
            if self.driver:
                self.driver.quit()
            self._notificar_sucesso("Sistema encerrado")
        except Exception as e:
            self._notificar_erro("encerramento", str(e))