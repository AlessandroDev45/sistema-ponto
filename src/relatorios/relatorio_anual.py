# relatorios/relatorio_anual.py
from datetime import datetime, date
import calendar
import logging
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from fpdf import FPDF
import json

class RelatorioAnual:
   def __init__(self, database, calculadora):
       self.db = database
       self.calculadora = calculadora
       self.logger = logging.getLogger('RelatorioAnual')

   def gerar_relatorio_anual(self, ano, formato='pdf'):
       try:
           dados = self._coletar_dados_anuais(ano)
           resumo = self._calcular_resumo_anual(dados)
           
           if formato == 'pdf':
               return self._gerar_pdf(ano, dados, resumo)
           elif formato == 'excel':
               return self._gerar_excel(ano, dados, resumo)
           elif formato == 'json':
               return self._gerar_json(ano, dados, resumo)
           else:
               raise ValueError(f"Formato inválido: {formato}")
       
       except Exception as e:
           self.logger.error(f"Erro ao gerar relatório anual {ano}: {e}")
           return None

   def _coletar_dados_anuais(self, ano):
       dados = {
           'registros': [],
           'horas': [],
           'calculos': [],
           'falhas': []
       }
       
       inicio = date(ano, 1, 1)
       fim = date(ano, 12, 31)
       
       # Coleta todos os dados do ano
       dados['registros'] = self.db.obter_registros_periodo(inicio, fim)
       dados['horas'] = self.db.obter_horas_trabalhadas_periodo(inicio, fim)
       
       # Coleta cálculos mensais
       for mes in range(1, 13):
           calculo = self.db.obter_calculo_mensal(mes, ano)
           if calculo:
               dados['calculos'].append(calculo)
               
       dados['falhas'] = self.db.obter_falhas_periodo(inicio, fim)
       
       return dados

   def _calcular_resumo_anual(self, dados):
       resumo = {
           'financeiro': {
               'total_proventos': 0,
               'total_descontos': 0,
               'total_liquido': 0,
               'total_fgts': 0,
               'total_inss': 0,
               'total_irrf': 0
           },
           'horas': {
               'normais': 0,
               'extras_60': 0,
               'extras_65': 0,
               'extras_75': 0,
               'extras_100': 0,
               'extras_150': 0,
               'noturnas': 0
           },
           'indicadores': {
               'dias_trabalhados': 0,
               'dias_faltados': 0,
               'media_he_mes': 0,
               'custo_hora_medio': 0
           }
       }
       
       # Processa dados financeiros
       for calc in dados['calculos']:
           resumo['financeiro']['total_proventos'] += calc[8]  # total_proventos
           resumo['financeiro']['total_descontos'] += calc[12] # total_descontos
           resumo['financeiro']['total_liquido'] += calc[13]   # liquido
           resumo['financeiro']['total_fgts'] += calc[15]      # fgts
           resumo['financeiro']['total_inss'] += calc[9]       # inss
           resumo['financeiro']['total_irrf'] += calc[10]      # irrf
           
       # Processa horas
       for hora in dados['horas']:
           resumo['horas']['normais'] += hora[4]
           resumo['horas']['extras_60'] += hora[5]
           resumo['horas']['extras_65'] += hora[6]
           resumo['horas']['extras_75'] += hora[7]
           resumo['horas']['extras_100'] += hora[8]
           resumo['horas']['extras_150'] += hora[9]
           resumo['horas']['noturnas'] += hora[10]
           
       # Calcula indicadores
       total_dias = len(set(r[1].split()[0] for r in dados['registros']))
       resumo['indicadores']['dias_trabalhados'] = total_dias
       
       total_he = sum([
           resumo['horas']['extras_60'],
           resumo['horas']['extras_65'],
           resumo['horas']['extras_75'],
           resumo['horas']['extras_100'],
           resumo['horas']['extras_150']
       ])
       
       meses_trabalhados = len(dados['calculos'])
       if meses_trabalhados > 0:
           resumo['indicadores']['media_he_mes'] = total_he / meses_trabalhados
           
       if resumo['horas']['normais'] > 0:
           resumo['indicadores']['custo_hora_medio'] = (
               resumo['financeiro']['total_proventos'] / 
               resumo['horas']['normais']
           )
           
       return resumo

   def _gerar_graficos(self, dados, ano):
       # Cria DataFrame com dados mensais
       df_mensal = pd.DataFrame([
           {
               'Mês': calendar.month_name[calc[1]],
               'Proventos': calc[8],
               'Horas Extras': sum([
                   dados['horas'][i][5:10] 
                   for i in range(len(dados['horas']))
                   if dados['horas'][i][1].startswith(f"{ano}-{calc[1]:02d}")
               ])
           }
           for calc in dados['calculos']
       ])
       
       # Gráfico de evolução mensal
       plt.figure(figsize=(12, 6))
       sns.lineplot(data=df_mensal, x='Mês', y='Proventos')
       plt.title('Evolução dos Proventos Mensais')
       plt.xticks(rotation=45)
       plt.tight_layout()
       plt.savefig('graficos/evolucao_mensal.png')
       plt.close()
       
       # Gráfico de horas extras
       plt.figure(figsize=(12, 6))
       sns.barplot(data=df_mensal, x='Mês', y='Horas Extras')
       plt.title('Horas Extras por Mês')
       plt.xticks(rotation=45)
       plt.tight_layout()
       plt.savefig('graficos/horas_extras.png')
       plt.close()

   def _gerar_pdf(self, ano, dados, resumo):
       try:
           filename = f"relatorio_anual_{ano}.pdf"
           pdf = FPDF()
           
           # Capa
           pdf.add_page()
           pdf.set_font('Arial', 'B', 16)
           pdf.cell(0, 10, f'Relatório Anual {ano}', 0, 1, 'C')
           pdf.ln(20)
           
           # Resumo Financeiro
           pdf.set_font('Arial', 'B', 14)
           pdf.cell(0, 10, 'Resumo Financeiro', 0, 1, 'L')
           pdf.set_font('Arial', '', 12)
           
           itens_financeiros = [
               ('Total Proventos', resumo['financeiro']['total_proventos']),
               ('Total Descontos', resumo['financeiro']['total_descontos']),
               ('Total Líquido', resumo['financeiro']['total_liquido']),
               ('FGTS Acumulado', resumo['financeiro']['total_fgts']),
               ('INSS Recolhido', resumo['financeiro']['total_inss']),
               ('IRRF Recolhido', resumo['financeiro']['total_irrf'])
           ]
           
           for item, valor in itens_financeiros:
               pdf.cell(0, 10, f'{item}: R$ {valor:,.2f}', 0, 1)
           
           # Horas Trabalhadas
           pdf.add_page()
           pdf.set_font('Arial', 'B', 14)
           pdf.cell(0, 10, 'Horas Trabalhadas', 0, 1, 'L')
           pdf.set_font('Arial', '', 12)
           
           itens_horas = [
               ('Horas Normais', resumo['horas']['normais']),
               ('Horas Extras 60%', resumo['horas']['extras_60']),
               ('Horas Extras 65%', resumo['horas']['extras_65']),
               ('Horas Extras 75%', resumo['horas']['extras_75']),
               ('Horas Extras 100%', resumo['horas']['extras_100']),
               ('Horas Extras 150%', resumo['horas']['extras_150']),
               ('Horas Noturnas', resumo['horas']['noturnas'])
           ]
           
           for item, valor in itens_horas:
               pdf.cell(0, 10, f'{item}: {valor:.2f}h', 0, 1)
           
           # Indicadores
           pdf.add_page()
           pdf.set_font('Arial', 'B', 14)
           pdf.cell(0, 10, 'Indicadores', 0, 1, 'L')
           pdf.set_font('Arial', '', 12)
           
           itens_indicadores = [
               ('Dias Trabalhados', resumo['indicadores']['dias_trabalhados']),
               ('Média de Horas Extras/Mês', resumo['indicadores']['media_he_mes']),
               ('Custo Médio por Hora', resumo['indicadores']['custo_hora_medio'])
           ]
           
           for item, valor in itens_indicadores:
               if 'Custo' in item:
                   pdf.cell(0, 10, f'{item}: R$ {valor:,.2f}', 0, 1)
               else:
                   pdf.cell(0, 10, f'{item}: {valor:.2f}', 0, 1)
           
           # Gráficos
           self._gerar_graficos(dados, ano)
           pdf.add_page()
           pdf.image('graficos/evolucao_mensal.png', x=10, w=190)
           pdf.add_page()
           pdf.image('graficos/horas_extras.png', x=10, w=190)
           
           pdf.output(filename)
           return filename
           
       except Exception as e:
           self.logger.error(f"Erro ao gerar PDF: {e}")
           return None

   def _gerar_excel(self, ano, dados, resumo):
       try:
           filename = f"relatorio_anual_{ano}.xlsx"
           
           # Cria Excel writer
           writer = pd.ExcelWriter(filename, engine='xlsxwriter')
           
           # DataFrame Resumo Financeiro
           df_financeiro = pd.DataFrame([
               {'Item': k, 'Valor': v}
               for k, v in resumo['financeiro'].items()
           ])
           df_financeiro.to_excel(writer, sheet_name='Resumo Financeiro', index=False)
           
           # DataFrame Horas
           df_horas = pd.DataFrame([
               {'Tipo': k, 'Horas': v}
               for k, v in resumo['horas'].items()
           ])
           df_horas.to_excel(writer, sheet_name='Horas Trabalhadas', index=False)
           
           # DataFrame Indicadores
           df_indicadores = pd.DataFrame([
               {'Indicador': k, 'Valor': v}
               for k, v in resumo['indicadores'].items()
           ])
           df_indicadores.to_excel(writer, sheet_name='Indicadores', index=False)
           
           # Dados Mensais Detalhados
           df_mensal = pd.DataFrame(dados['calculos'])
           df_mensal.to_excel(writer, sheet_name='Dados Mensais', index=False)
           
           writer.save()
           return filename
           
       except Exception as e:
           self.logger.error(f"Erro ao gerar Excel: {e}")
           return None

   def _gerar_json(self, ano, dados, resumo):
       try:
           filename = f"relatorio_anual_{ano}.json"
           
           dados_json = {
               'ano': ano,
               'resumo': resumo,
               'dados_mensais': [
                   {
                       'mes': calc[1],
                       'proventos': calc[8],
                       'descontos': calc[12],
                       'liquido': calc[13]
                   }
                   for calc in dados['calculos']
               ]
           }
           
           with open(filename, 'w') as f:
               json.dump(dados_json, f, indent=4)
               
           return filename
           
       except Exception as e:
           self.logger.error(f"Erro ao gerar JSON: {e}")
           return None
   def gerar_relatorio_anual(self, ano, formato='pdf'):
        try:
            inicio = datetime(ano, 1, 1)
            fim = datetime(ano, 12, 31)
            
            dados = {
                'registros': self.db.obter_registros_periodo(inicio, fim),
                'horas': self.db.obter_horas_trabalhadas_periodo(inicio, fim),
                'falhas': self.db.obter_falhas_periodo(inicio, fim),
                'calculos': []
            }
            
            # Coleta cálculos de todos os meses
            for mes in range(1, 13):
                calculo = self.db.obter_calculo_mensal(mes, ano)
                if calculo:
                    dados['calculos'].append(calculo)
            
            if formato == 'pdf':
                return self.gerar_pdf_anual(dados, ano)
            elif formato == 'csv':
                return self.gerar_csv_anual(dados, ano)
            else:
                raise ValueError(f"Formato inválido: {formato}")
                
        except Exception as e:
            self.logger.error(f"Erro ao gerar relatório anual: {e}")
            return None