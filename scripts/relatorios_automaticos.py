#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para envio automático de relatórios e verificação de faltas.
- Relatório semanal: toda segunda-feira
- Relatório mensal: dia 1 de cada mês
- Relatório anual: dia 1 de janeiro
- Verificação de faltas: diariamente às 22h
"""

import os
import sys
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Garante que o root esteja no path
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
sys.path.append(root_dir)


class RelatoriosAutomaticos:
    def __init__(self):
        load_dotenv(override=True)
        self.token = os.environ.get('TELEGRAM_TOKEN')
        self.chat_id = os.environ.get('TELEGRAM_CHAT_ID', '').strip()
        self.db = None
        
        # Conecta ao banco
        try:
            from src.utils.database import Database
            self.db = Database()
            print("✅ Banco de dados conectado")
        except Exception as e:
            print(f"❌ Erro ao conectar banco: {e}")
            raise

    def enviar_mensagem(self, texto):
        """Envia mensagem para o Telegram"""
        try:
            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            response = requests.post(url, json={
                'chat_id': self.chat_id,
                'text': texto,
                'parse_mode': 'HTML'
            }, timeout=10)
            return response.status_code == 200
        except Exception as e:
            print(f"Erro ao enviar mensagem: {e}")
            return False

    def verificar_faltas_dia(self, data):
        """Verifica se houve falta em um dia específico"""
        try:
            if self.db is None:
                print("Banco de dados não conectado")
                return None
            registros = self.db.obter_registros_dia(data)
            
            # Conta entradas e saídas
            entradas = sum(1 for r in registros if r[2].lower() == 'entrada')
            saidas = sum(1 for r in registros if r[2].lower() == 'saida')
            
            if entradas == 0 and saidas == 0:
                return 'falta_total'
            elif entradas > saidas:
                return 'falta_saida'
            elif saidas > entradas:
                return 'falta_entrada'
            
            return None  # Dia completo
        except Exception as e:
            print(f"Erro ao verificar faltas: {e}")
            return None

    def enviar_alerta_faltas(self):
        """Verifica e envia alerta de faltas do dia"""
        hoje = datetime.now().date()
        dia_semana = hoje.weekday()
        
        # Só verifica dias úteis (seg-sex)
        if dia_semana >= 5:
            print("Fim de semana - não verifica faltas")
            return
        
        # Verifica se está pausado
        if self.db is None:
            print("Banco de dados não conectado")
            return
        estado = self.db.obter_configuracao('sistema_pausado')
        if estado == 'true':
            print("Sistema pausado - não verifica faltas")
            return
        
        falta = self.verificar_faltas_dia(hoje)
        
        if falta == 'falta_total':
            msg = (
                f"⚠️ <b>ALERTA DE FALTA</b>\n\n"
                f"📅 Data: {hoje.strftime('%d/%m/%Y')}\n"
                f"❌ Nenhum registro de ponto hoje!\n\n"
                f"Use /registrar para registrar manualmente."
            )
            self.enviar_mensagem(msg)
            print(f"Alerta enviado: falta total em {hoje}")
            
        elif falta == 'falta_saida':
            msg = (
                f"⚠️ <b>ALERTA DE REGISTRO INCOMPLETO</b>\n\n"
                f"📅 Data: {hoje.strftime('%d/%m/%Y')}\n"
                f"❌ Falta registro de SAÍDA!\n\n"
                f"Use /registrar para registrar a saída."
            )
            self.enviar_mensagem(msg)
            print(f"Alerta enviado: falta saída em {hoje}")
            
        elif falta == 'falta_entrada':
            msg = (
                f"⚠️ <b>ALERTA DE REGISTRO INCOMPLETO</b>\n\n"
                f"📅 Data: {hoje.strftime('%d/%m/%Y')}\n"
                f"❌ Falta registro de ENTRADA!\n\n"
                f"Verifique os registros do dia."
            )
            self.enviar_mensagem(msg)
            print(f"Alerta enviado: falta entrada em {hoje}")
        else:
            print(f"Dia {hoje} completo - sem alertas")

    def gerar_relatorio_semanal(self):
        """Gera e envia relatório semanal (últimos 7 dias)"""
        if self.db is None:
            print("Banco de dados não conectado")
            return
        
        hoje = datetime.now().date()
        inicio = hoje - timedelta(days=7)
        
        registros = self.db.obter_registros_periodo(inicio, hoje)
        
        # Agrupa por dia
        dias = {}
        for reg in registros:
            data_str = reg[1]
            if isinstance(data_str, str):
                dt = datetime.strptime(data_str.split('.')[0], '%Y-%m-%d %H:%M:%S')
            else:
                dt = data_str
            dia = dt.date()
            if dia not in dias:
                dias[dia] = {'entradas': [], 'saidas': []}
            if reg[2].lower() == 'entrada':
                dias[dia]['entradas'].append(dt)
            else:
                dias[dia]['saidas'].append(dt)
        
        # Calcula totais
        total_minutos = 0
        dias_trabalhados = 0
        faltas = []
        
        # Verifica cada dia útil da semana
        for i in range(7):
            data = inicio + timedelta(days=i)
            if data.weekday() >= 5:  # Fim de semana
                continue
            
            if data in dias:
                dias_trabalhados += 1
                entradas = dias[data]['entradas']
                saidas = dias[data]['saidas']
                pares = min(len(entradas), len(saidas))
                for j in range(pares):
                    delta = saidas[j] - entradas[j]
                    total_minutos += delta.total_seconds() / 60
            else:
                faltas.append(data)
        
        horas = int(total_minutos // 60)
        minutos = int(total_minutos % 60)
        
        msg = (
            f"📊 <b>RELATÓRIO SEMANAL</b>\n"
            f"📅 {inicio.strftime('%d/%m')} a {hoje.strftime('%d/%m/%Y')}\n\n"
            f"📈 Dias trabalhados: {dias_trabalhados}\n"
            f"⏰ Total de horas: {horas}h{minutos:02d}min\n"
        )
        
        if faltas:
            msg += f"\n❌ Faltas ({len(faltas)}):\n"
            for f in faltas:
                msg += f"  • {f.strftime('%d/%m (%a)')}\n"
        else:
            msg += "\n✅ Nenhuma falta na semana!"
        
        self.enviar_mensagem(msg)
        print("Relatório semanal enviado")

    def gerar_relatorio_mensal(self):
        """Gera e envia relatório do mês anterior"""
        hoje = datetime.now().date()
        
        # Mês anterior
        if hoje.month == 1:
            mes = 12
            ano = hoje.year - 1
        else:
            mes = hoje.month - 1
            ano = hoje.year
        
        # Primeiro e último dia do mês
        inicio = datetime(ano, mes, 1).date()
        if mes == 12:
            fim = datetime(ano + 1, 1, 1).date() - timedelta(days=1)
        else:
            fim = datetime(ano, mes + 1, 1).date() - timedelta(days=1)
        
        if self.db is None:
            print("Banco de dados não conectado")
            return
        
        registros = self.db.obter_registros_periodo(inicio, fim)
        
        # Conta dias trabalhados
        dias = set()
        for reg in registros:
            data_str = reg[1]
            if isinstance(data_str, str):
                dt = datetime.strptime(data_str.split('.')[0], '%Y-%m-%d %H:%M:%S')
            else:
                dt = data_str
            dias.add(dt.date())
        
        # Conta dias úteis do mês
        dias_uteis = 0
        data = inicio
        while data <= fim:
            if data.weekday() < 5:
                dias_uteis += 1
            data += timedelta(days=1)
        
        faltas = dias_uteis - len(dias)
        
        meses = ['', 'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
                 'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']
        
        msg = (
            f"📄 <b>RELATÓRIO MENSAL</b>\n"
            f"📅 {meses[mes]}/{ano}\n\n"
            f"📈 Dias úteis: {dias_uteis}\n"
            f"✅ Dias trabalhados: {len(dias)}\n"
            f"❌ Faltas: {faltas}\n"
            f"📝 Total de registros: {len(registros)}\n"
        )
        
        self.enviar_mensagem(msg)
        print("Relatório mensal enviado")

    def gerar_relatorio_anual(self):
        """Gera e envia relatório do ano anterior"""
        if self.db is None:
            print("Banco de dados não conectado")
            return
        
        ano = datetime.now().year - 1
        inicio = datetime(ano, 1, 1).date()
        fim = datetime(ano, 12, 31).date()
        
        registros = self.db.obter_registros_periodo(inicio, fim)
        
        # Conta dias trabalhados por mês
        meses_dados = {}
        for reg in registros:
            data_str = reg[1]
            if isinstance(data_str, str):
                dt = datetime.strptime(data_str.split('.')[0], '%Y-%m-%d %H:%M:%S')
            else:
                dt = data_str
            mes = dt.month
            if mes not in meses_dados:
                meses_dados[mes] = set()
            meses_dados[mes].add(dt.date())
        
        meses = ['', 'Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun',
                 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']
        
        msg = (
            f"📋 <b>RELATÓRIO ANUAL</b>\n"
            f"📅 Ano: {ano}\n\n"
            f"<b>Dias trabalhados por mês:</b>\n"
        )
        
        total_dias = 0
        for m in range(1, 13):
            dias = len(meses_dados.get(m, set()))
            total_dias += dias
            msg += f"  {meses[m]}: {dias} dias\n"
        
        msg += f"\n📈 <b>Total: {total_dias} dias</b>"
        
        self.enviar_mensagem(msg)
        print("Relatório anual enviado")


def main():
    load_dotenv(override=True)
    
    tipo = os.environ.get('TIPO_RELATORIO', 'faltas')
    
    print(f"🔄 Executando: {tipo}")
    
    relatorios = RelatoriosAutomaticos()
    
    if tipo == 'semanal':
        relatorios.gerar_relatorio_semanal()
    elif tipo == 'mensal':
        relatorios.gerar_relatorio_mensal()
    elif tipo == 'anual':
        relatorios.gerar_relatorio_anual()
    elif tipo == 'faltas':
        relatorios.enviar_alerta_faltas()
    else:
        print(f"Tipo desconhecido: {tipo}")


if __name__ == "__main__":
    main()
