# src/web_controller.py
import sys
import os
from pathlib import Path

# Adiciona o diretório raiz ao Python Path
current_dir = Path(__file__).resolve().parent
root_dir = current_dir.parent
sys.path.append(str(root_dir))

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from datetime import datetime
import time

from src.utils.logger import setup_logger, log_exception 

class WebController:
    def __init__(self, config, database):
        self.config = config
        self.db = database
        self.driver = None
        self.logger = setup_logger('WebController')
        
    

    def _inicializar_driver(self):
        try:
            chrome_options = Options()
            chrome_options.add_argument('--headless=new')  # Nova sintaxe
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--disable-gpu')
            
            service = Service(service_args=['--verbose'], log_path='logs/chromedriver.log')
            
            self.driver = webdriver.Chrome(
                service=service,
                options=chrome_options
            )
            self.driver.implicitly_wait(10)
            return True
        except Exception as e:
            self.logger.error(f"Falha ao iniciar driver: {str(e)}")
            return False

    def fazer_login(self):
        try:
            if not self.driver:
                if not self._inicializar_driver():
                    return False

            self.driver.get(self.config.URL_SISTEMA)
            time.sleep(2)
            
            campo_login = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, 
                '/html/body/app-root/div/div/app-login/div[1]/div[1]/form/po-input/po-field-container/div/div[2]/input'))
            )
            campo_login.send_keys(self.config.LOGIN)
            
            campo_senha = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, 
                '/html/body/app-root/div/div/app-login/div[1]/div[1]/form/po-password/po-field-container/div/div[2]/input'))
            )
            campo_senha.send_keys(self.config.SENHA)
            campo_senha.send_keys(Keys.RETURN)
            time.sleep(2)
            
            self.logger.info("Login realizado com sucesso")
            return True
            
        except Exception as e:
            log_exception(self.logger, e, "Erro no login:")
            return False

    def registrar_ponto(self):
        try:
            if not self.fazer_login():
                return False

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

            botao_ponto = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, '//*[@id="div-swipeButtonText"]'))
            )
            
            self.logger.info("Registrando ponto")
            botao_ponto.click()
            time.sleep(1)
            botao_ponto.click()
            time.sleep(1)
            
            agora = datetime.now()
            self.db.registrar_ponto(agora, "AUTOMATICO", "SUCESSO")
            
            self.logger.info(f"Ponto registrado com sucesso às {agora.strftime('%H:%M:%S')}")
            return True

        except Exception as e:
            log_exception(self.logger, e, "Erro ao registrar ponto:")
            self.db.registrar_falha("registro_ponto", str(e))
            return False
            
        finally:
            if self.driver:
                self.driver.quit()
                self.driver = None

    def verificar_status(self):
        try:
            if not self.fazer_login():
                return False, "Erro no login"
                
            self.logger.info("Sistema web acessível")
            return True, "Sistema online"
            
        except Exception as e:
            log_exception(self.logger, e, "Erro ao verificar status:")
            return False, str(e)
            
        finally:
            if self.driver:
                self.driver.quit()
                self.driver = None