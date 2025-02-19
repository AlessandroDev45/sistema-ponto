import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from datetime import date, datetime, timedelta
import config
from config.config import Config  # Import corretamente para usar get_instance
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
        self.config = Config.get_instance()  # Inicializa a instância Singleton aqui
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
            if not force:
                status_horario = self.verificar_horario()
                if not status_horario['valido']:
                    # Solicita confirmação via Telegram
                    msg = (
                        f"⚠️ Registro fora do horário programado!\n"
                        f"Horário atual: {status_horario['hora_atual']}\n"
                        f"Diferença: {status_horario['diferenca_minutos']} minutos\n"
                        f"{status_horario['mensagem']}\n\n"
                        "Deseja registrar mesmo assim? Digite CONFIRMAR"
                    )
                    self.telegram.enviar_mensagem(msg)
                    return {'aguardando_confirmacao': True, 'status': status_horario}

            # Processo de registro no sistema
            if not self.fazer_login():
                raise Exception("Falha no login")

            if not self.navegar_para_ponto():
                raise Exception("Falha ao acessar página de ponto")

            self.registrar_no_sistema()
            
            # Registra no banco e calcula horas
            agora = datetime.now()
            registro = self.db.registrar_ponto(
                agora,
                "MANUAL" if force else "AUTOMATICO",
                "SUCESSO"
            )

            if registro:
                self.calcular_e_notificar_horas(agora)
                return {'sucesso': True, 'mensagem': 'Ponto registrado com sucesso'}
            
            return {'sucesso': False, 'mensagem': 'Falha ao registrar ponto'}

        except Exception as e:
            self.logger.error(f"Erro ao registrar ponto: {e}")
            return {'sucesso': False, 'mensagem': str(e)}

    def verificar_horario(self):
        try:
            agora = datetime.now().time()
            entrada = datetime.strptime(self.config.HORARIO_ENTRADA, '%H:%M').time()
            saida = datetime.strptime(self.config.HORARIO_SAIDA, '%H:%M').time()

        # Calcular diferenças corretamente
            diff_entrada = (datetime.combine(date.today(), agora) - 
                      datetime.combine(date.today(), entrada)).total_seconds() / 60
            diff_saida = (datetime.combine(date.today(), agora) - 
                   datetime.combine(date.today(), saida)).total_seconds() / 60




            diff_entrada = abs(datetime.combine(datetime.now().date(), agora) - 
                            datetime.combine(datetime.now().date(), entrada))
            diff_saida = abs(datetime.combine(datetime.now().date(), agora) - 
                            datetime.combine(datetime.now().date(), saida))
            
            minutos_diff = min(diff_entrada, diff_saida).total_seconds() / 60
            
            if minutos_diff <= config.TOLERANCIA_MINUTOS:
                return {
                    'valido': True,
                    'hora_atual': agora,
                    'diferenca_minutos': 0,
                    'mensagem': 'Horário dentro da tolerância'
                }
            
            # Determina se é atraso ou hora extra
            if diff_entrada < diff_saida:
                tipo = "Atraso" if agora > entrada else "Antecipação"
                horario_ref = entrada
            else:
                tipo = "Hora Extra" if agora > saida else "Saída Antecipada"
                horario_ref = saida
                
            return {
                'valido': False,
                'hora_atual': agora,
                'diferenca_minutos': int(minutos_diff),
                'mensagem': f"{tipo} detectado em relação ao horário {horario_ref.strftime('%H:%M')}"
            }
                
        except Exception as e:
            self.logger.error(f"Erro ao verificar horário: {e}")
            return {
                'valido': False,
                'mensagem': f"Erro ao verificar horário: {e}"
            }


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
        # Usa a instância do Config armazenada
        agora = datetime.now()
        hora_atual = agora.strftime('%H:%M')
        
        horario_entrada = self.config.HORARIO_ENTRADA
        horario_saida = self.config.HORARIO_SAIDA

        if hora_atual < horario_entrada:
            return horario_entrada
        elif hora_atual < horario_saida:
            return horario_saida
        else:
            amanha = agora + timedelta(days=1)
            return f"{horario_entrada} (amanhã)"

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