import sys
import os
from pathlib import Path

# Adiciona o diretório raiz ao Python Path
current_dir = Path(__file__).resolve().parent
root_dir = current_dir.parent.parent
sys.path.append(str(root_dir))

import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from datetime import date, datetime, timedelta
import time
import tempfile
import logging

from config.config import Config

class AutomacaoPonto:
    def __init__(self, url, login, senha, database, telegram=None, headless=True, incognito=True):
        self.url = url
        self.login = login
        self.senha = senha
        self.db = database
        self.telegram = telegram
        self.driver = None
        self.logger = logging.getLogger('AutomacaoPonto')
        self.config = Config.get_instance()
        self.headless = headless
        self.incognito = incognito
        self._setup_driver()
        
    def _setup_driver(self):
        try:
            if self.driver:
                return True

            self.logger.info("Iniciando configuração do Chrome...")
            
            chrome_options = Options()
            
            # Modo headless para CI
            if self.headless:
                chrome_options.add_argument('--headless=new')
            
            # Argumentos ESSENCIAIS para GitHub Actions / CI
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--disable-software-rasterizer')
            chrome_options.add_argument('--disable-extensions')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--remote-allow-origins=*')
            
            # Detecta o binário do Chrome - prioriza variável de ambiente
            chrome_bin = os.environ.get('CHROME_BIN')
            
            if chrome_bin and os.path.exists(chrome_bin):
                self.logger.info(f"Chrome via CHROME_BIN: {chrome_bin}")
                chrome_options.binary_location = chrome_bin
            
            # Selenium 4.6+ tem Selenium Manager embutido que detecta Chrome/ChromeDriver automaticamente
            self.logger.info("Iniciando Chrome com Selenium Manager...")
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.implicitly_wait(10)
            self.logger.info("Chrome WebDriver inicializado com sucesso")
            return True
            
        except Exception as e:
            self.logger.error(f"Erro ao configurar driver: {e}")
            if self.telegram:
                self.telegram.enviar_mensagem(f"❌ Erro ao configurar driver: {e}")
            raise

    def abrir_e_navegar_sem_registro(self, espera_segundos=10):
        """Abre o sistema e navega até a tela de ponto sem registrar."""
        try:
            if not self._setup_driver():
                raise Exception("Falha ao inicializar driver")

            if not self.fazer_login():
                raise Exception("Falha no login")

            if not self.navegar_para_ponto(registrar=False):
                raise Exception("Falha ao navegar até a tela de ponto")

            self.logger.info("Tela de ponto aberta (sem registro)")
            time.sleep(espera_segundos)
            return True

        except Exception as e:
            self.logger.error(f"Erro ao abrir/navegar sem registro: {e}")
            self._notificar_erro("navegação", str(e))
            return False
        finally:
            self._cleanup_driver()

    def registrar_ponto(self, force=False):
        try:
            if not force:
                status = self.verificar_horario()
                if not status['valido']:
                    return status

            if not self._setup_driver():
                raise Exception("Falha ao inicializar driver")

            if not self.fazer_login():
                raise Exception("Falha no login")

            sucesso = self.navegar_para_ponto(registrar=True)
            
            if sucesso:
                agora = datetime.now()
                self.db.registrar_ponto(
                    agora,
                    "MANUAL" if force else "AUTOMATICO",
                    "SUCESSO"
                )
                self._notificar_sucesso(agora)
                return {'sucesso': True, 'mensagem': 'Ponto registrado com sucesso'}
            
            return {'sucesso': False, 'mensagem': 'Falha ao registrar ponto'}

        except Exception as e:
            self.logger.error(f"Erro ao registrar ponto: {e}")
            self._notificar_erro("registro", str(e))
            return {'sucesso': False, 'mensagem': str(e)}
            
        finally:
            self._cleanup_driver()

    def _notificar_erro(self, tipo, mensagem):
        """Notifica erro via logger e Telegram"""
        erro = f"❌ Erro de {tipo}: {mensagem}"
        self.logger.error(erro)
        if self.telegram:
            self.telegram.enviar_mensagem(erro)
        self.db.registrar_falha(tipo, mensagem)

    def _notificar_sucesso(self, mensagem):
        """Notifica sucesso via logger e Telegram"""
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

    def _wait_loading_screen(self, timeout=20):
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.invisibility_of_element_located((By.CLASS_NAME, 'loading-screen'))
            )
        except Exception:
            pass

    def _safe_click(self, xpath, timeout=20):
        elemento = WebDriverWait(self.driver, timeout).until(
            EC.element_to_be_clickable((By.XPATH, xpath))
        )
        try:
            elemento.click()
        except Exception:
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", elemento)
            self.driver.execute_script("arguments[0].click();", elemento)

    def navegar_para_ponto(self, registrar=False):
        try:
            self.logger.info("Navegando para página de ponto")
            self._wait_loading_screen()
            self._safe_click('/html/body/app-root/div/div/div[2]/po-menu/div/div[2]/div/div[2]/div/div/nav/ul/li[3]/po-menu-item/div/div[1]', timeout=20)
            time.sleep(1)

            self._wait_loading_screen()
            self._safe_click('/html/body/app-root/div/div/div[2]/po-menu/div/div[2]/div/div[2]/div/div/nav/ul/li[3]/po-menu-item/div/div[2]/ul/li[1]/po-menu-item/a/div/span', timeout=20)
            time.sleep(1)

            if registrar:
                self._wait_loading_screen()
                self.logger.info("Registrando ponto")
                self._safe_click('//*[@id="btn-app-swipe-clocking-register"]/div/div/div/div', timeout=20)
                time.sleep(1)

            return True

        except Exception as e:
            self._notificar_erro("navegação", str(e))
            return False

    
        
    def verificar_horario(self):
        """Verifica se o horário atual está dentro da janela permitida"""
        try:
            agora = datetime.now().time()
            
            # Converte as strings de configuração para objetos time
            if isinstance(self.config.HORARIO_ENTRADA, str):
                entrada = datetime.strptime(self.config.HORARIO_ENTRADA, '%H:%M:%S').time()
            else:
                entrada = self.config.HORARIO_ENTRADA

            if isinstance(self.config.HORARIO_SAIDA, str):
                saida = datetime.strptime(self.config.HORARIO_SAIDA, '%H:%M:%S').time()
            else:
                saida = self.config.HORARIO_SAIDA

            # Calcula as diferenças em minutos
            def minutes_between(t1, t2):
                d1 = datetime.combine(datetime.today(), t1)
                d2 = datetime.combine(datetime.today(), t2)
                return abs((d2 - d1).total_seconds() / 60)

            # Verifica proximidade com horário de entrada
            diff_entrada = minutes_between(agora, entrada)
            if diff_entrada <= self.config.TOLERANCIA_MINUTOS:
                return {
                    'valido': True,
                    'tipo': 'entrada',
                    'hora_atual': agora.strftime('%H:%M'),
                    'diferenca_minutos': diff_entrada,
                    'mensagem': 'Horário válido para entrada'
                }
            
            # Verifica proximidade com horário de saída
            diff_saida = minutes_between(agora, saida)
            if diff_saida <= self.config.TOLERANCIA_MINUTOS:
                return {
                    'valido': True,
                    'tipo': 'saida',
                    'hora_atual': agora.strftime('%H:%M'),
                    'diferenca_minutos': diff_saida,
                    'mensagem': 'Horário válido para saída'
                }
            
            # Fora da janela permitida
            return {
                'valido': False,
                'hora_atual': agora.strftime('%H:%M'),
                'diferenca_minutos': min(diff_entrada, diff_saida),
                'mensagem': f"Fora da janela permitida (Entrada: {entrada.strftime('%H:%M')}, Saída: {saida.strftime('%H:%M')})"
            }
                
        except Exception as e:
            self.logger.error(f"Erro na verificação de horário: {str(e)}")
            return {
                'valido': False,
                'hora_atual': datetime.now().strftime('%H:%M'),
                'diferenca_minutos': 0,
                'mensagem': f'Erro na verificação: {str(e)}'
            }

    def verificar_status(self):
        """Verifica status do sistema"""
        try:
            horario_atual = datetime.now().strftime('%H:%M')
            
            status_msg = (
                "🕒 Status do Sistema\n\n"
                f"Horário Atual: {horario_atual}\n"
                f"Próximo Registro: {self._calcular_proximo_horario()}\n"
                f"Sistema: {'🟢 Ativo' if self.sistema_ativo else '🔴 Pausado'}\n"
            )

            # Adiciona último registro se existir
            if self.ultimo_registro:
                status_msg += f"Último Registro: {self.ultimo_registro}\n"

            return {'mensagem': status_msg, 'sucesso': True}

        except Exception as e:
            erro_msg = f"Erro ao verificar status: {str(e)}"
            self.logger.error(erro_msg)
            return {'mensagem': erro_msg, 'sucesso': False}
        
    def _calcular_proximo_horario(self):
        """Calcula o próximo horário de registro"""
        try:
            agora = datetime.now().time()
            entrada = self.config.HORARIO_ENTRADA
            saida = self.config.HORARIO_SAIDA

            # Converte para datetime.time se necessário
            if isinstance(entrada, str):
                h, m, s = map(int, entrada.split(':'))
                entrada = datetime.time(h, m, s)
            if isinstance(saida, str):
                h, m, s = map(int, saida.split(':'))
                saida = datetime.time(h, m, s)

            if agora < entrada:
                return entrada.strftime('%H:%M')
            elif agora < saida:
                return saida.strftime('%H:%M')
            else:
                return f"{entrada.strftime('%H:%M')} (amanhã)"

        except Exception as e:
            self.logger.error(f"Erro ao calcular próximo horário: {e}")
            return "Erro ao calcular próximo horário"

    def pausar_sistema(self):
        self.sistema_ativo = False
        self._notificar_sucesso("Sistema pausado")

    def retomar_sistema(self):
        self.sistema_ativo = True
        self._notificar_sucesso("Sistema retomado")

    def _cleanup_driver(self):
        self.encerrar()

    def encerrar(self):
        """Fecha recursos do navegador"""
        try:
            if self.driver:
                self.driver.quit()
                self.logger.info("Navegador fechado com sucesso")
                
        except Exception as e:
            self.logger.error(f"Erro ao fechar navegador: {str(e)}")
            
        finally:
            self.driver = None
            
    def registrar_ponto_com_retry(self, max_tentativas=3):
        for tentativa in range(1, max_tentativas+1):
            try:
                self.logger.info(f"Tentativa {tentativa}/{max_tentativas}")
                if self.registrar_ponto():
                    return True
                
                # Backoff exponencial
                delay = 2 ** tentativa
                self.logger.info(f"Esperando {delay} segundos para retentativa...")
                time.sleep(delay)
                
            except Exception as e:
                self.logger.error(f"Erro na tentativa {tentativa}: {str(e)}")
                if tentativa == max_tentativas:
                    self._notificar_erro("registro", f"Falha após {max_tentativas} tentativas")
                    return False

    def verificar_conexao(self):
        try:
            response = requests.get(self.url, timeout=5)
            return response.status_code == 200
        except:
            return False

    def verificar_disponibilidade(self):
        try:
            if not self.verificar_conexao():
                self._notificar_erro("conexão", "Sistema indisponível")
                return False
                
            if not self.fazer_login():
                self._notificar_erro("login", "Não foi possível autenticar")
                return False
                
            return True
        except Exception as e:
            self._notificar_erro("verificação", str(e))
            return False
        
        
    def calcular_e_notificar_horas(self, momento_registro):
        try:
            # Busca registros do dia
            inicio_dia = datetime.combine(momento_registro.date(), datetime.min.time())
            fim_dia = datetime.combine(momento_registro.date(), datetime.max.time())
            
            registros = self.db.obter_registros_periodo(inicio_dia, fim_dia)
            
            if len(registros) % 2 == 0:  # Par de registros (entrada/saída)
                ultimo_par = registros[-2:]  # Pega últimos dois registros
                entrada = datetime.strptime(ultimo_par[0][1], '%Y-%m-%d %H:%M:%S')
                saida = datetime.strptime(ultimo_par[1][1], '%Y-%m-%d %H:%M:%S')
                
                # Calcula horas trabalhadas
                delta = saida - entrada
                horas_total = delta.total_seconds() / 3600
                
                # Analisa extras ou faltas
                config = Config.get_instance()
                jornada_normal = 8  # horas
                
                msg = (
                    f"✅ Registro realizado com sucesso!\n"
                    f"Entrada: {entrada.strftime('%H:%M')}\n"
                    f"Saída: {saida.strftime('%H:%M')}\n"
                    f"Total: {horas_total:.2f}h\n"
                )
                
                if horas_total > jornada_normal:
                    extras = horas_total - jornada_normal
                    msg += f"Horas Extras: {extras:.2f}h"
                elif horas_total < jornada_normal:
                    falta = jornada_normal - horas_total
                    msg += f"Horas Faltantes: {falta:.2f}h"
                    
                self.telegram.enviar_mensagem(msg)
                
        except Exception as e:
            self.logger.error(f"Erro ao calcular horas: {e}")