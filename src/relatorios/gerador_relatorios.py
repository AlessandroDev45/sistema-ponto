# relatorios/gerador_relatorios.py
from datetime import datetime, timedelta
import calendar
import logging
import os
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
import csv
import json
from config.config import Config

class GeradorRelatorios:
    def __init__(self, database, calculadora):
        self.db = database
        self.calculadora = calculadora
        self.config = Config.get_instance()  # Adicionado
        self.logger = logging.getLogger('GeradorRelatorios')
        self.styles = getSampleStyleSheet()

    def gerar_relatorio_mensal(self, mes, ano, formato='pdf'):
        try:
            # Use self.config para caminhos, se necessário
            output_dir = self.config.RELATORIOS_DIR if hasattr(self.config, 'RELATORIOS_DIR') else 'relatorios'
            os.makedirs(output_dir, exist_ok=True)

            inicio = datetime(ano, mes, 21)
            if mes == 12:
                fim = datetime(ano + 1, 1, 20)
            else:
                fim = datetime(ano, mes + 1, 20)

            dados = {
                'registros': self.db.obter_registros_periodo(inicio, fim),
                'horas': self.db.obter_horas_trabalhadas_periodo(inicio, fim),
                'falhas': self.db.obter_falhas_periodo(inicio, fim),
                'calculos': self.db.obter_calculo_mensal(mes, ano)
            }

            if formato == 'pdf':
                filename = os.path.join(output_dir, f"relatorio_mensal_{mes}_{ano}.pdf")
                return self.gerar_pdf_mensal(dados, mes, ano, filename)
            elif formato == 'csv':
                filename = os.path.join(output_dir, f"relatorio_mensal_{mes}_{ano}.csv")
                return self.gerar_csv_mensal(dados, mes, ano, filename)
            elif formato == 'json':
                filename = os.path.join(output_dir, f"relatorio_mensal_{mes}_{ano}.json")
                return self.gerar_json_mensal(dados, mes, ano, filename)
            else:
                raise ValueError(f"Formato inválido: {formato}")

        except Exception as e:
            self.logger.error(f"Erro ao gerar relatório mensal: {e}")
            return None

    def gerar_pdf_mensal(self, dados, mes, ano):
       try:
           filename = f"relatorio_mensal_{mes}_{ano}.pdf"
           doc = SimpleDocTemplate(
               filename,
               pagesize=landscape(letter),
               rightMargin=72,
               leftMargin=72,
               topMargin=72,
               bottomMargin=72
           )

           elements = []

           # Cabeçalho
           title_style = ParagraphStyle(
               'CustomTitle',
               parent=self.styles['Heading1'],
               fontSize=16,
               spaceAfter=30
           )
           title = Paragraph(
               f"Relatório Mensal - Período de 21/{mes}/{ano} a "
               f"20/{mes+1 if mes < 12 else 1}/{ano if mes < 12 else ano+1}",
               title_style
           )
           elements.append(title)

           # Tabela de Registros
           elements.append(Paragraph("Registros de Ponto", self.styles['Heading2']))
           registros_table = self.criar_tabela_registros(dados['registros'])
           elements.append(registros_table)

           # Tabela de Horas
           elements.append(Paragraph("Horas Trabalhadas", self.styles['Heading2']))
           horas_table = self.criar_tabela_horas(dados['horas'])
           elements.append(horas_table)

           # Resumo Financeiro
           elements.append(Paragraph("Resumo Financeiro", self.styles['Heading2']))
           financeiro_table = self.criar_tabela_financeiro(dados['calculos'])
           elements.append(financeiro_table)

           # Falhas
           if dados['falhas']:
               elements.append(Paragraph("Registro de Falhas", self.styles['Heading2']))
               falhas_table = self.criar_tabela_falhas(dados['falhas'])
               elements.append(falhas_table)

           doc.build(elements)
           return filename

       except Exception as e:
           self.logger.error(f"Erro ao gerar PDF: {e}")
           return None

    def criar_tabela_registros(self, registros):
       data = [['Data', 'Hora', 'Tipo', 'Status', 'Motivo']]
       for reg in registros:
           dt = datetime.strptime(reg[1], '%Y-%m-%d %H:%M:%S')
           data.append([
               dt.strftime('%d/%m/%Y'),
               dt.strftime('%H:%M:%S'),
               reg[2],
               reg[3],
               reg[4] or ''
           ])
       
       return self.formatar_tabela(data)

    def criar_tabela_horas(self, horas):
       data = [[
           'Data', 'Normais', 'HE 60%', 'HE 65%', 
           'HE 75%', 'HE 100%', 'HE 150%', 'Noturnas'
       ]]
       
       for h in horas:
           data.append([
               datetime.strptime(h[1], '%Y-%m-%d').strftime('%d/%m/%Y'),
               f"{h[4]:.2f}",
               f"{h[5]:.2f}",
               f"{h[6]:.2f}",
               f"{h[7]:.2f}",
               f"{h[8]:.2f}",
               f"{h[9]:.2f}",
               f"{h[10]:.2f}"
           ])
       
       return self.formatar_tabela(data)

    def criar_tabela_financeiro(self, calculos):
       if not calculos:
           return Table([['Dados financeiros não disponíveis']])
           
       data = [
           ['Descrição', 'Valor'],
           ['Salário Base', f"R$ {calculos[3]:.2f}"],
           ['Periculosidade', f"R$ {calculos[4]:.2f}"],
           ['Adicional Noturno', f"R$ {calculos[5]:.2f}"],
           ['Horas Extras', f"R$ {calculos[6]:.2f}"],
           ['DSR', f"R$ {calculos[7]:.2f}"],
           ['Total Proventos', f"R$ {calculos[8]:.2f}"],
           ['INSS', f"R$ {calculos[9]:.2f}"],
           ['IRRF', f"R$ {calculos[10]:.2f}"],
           ['Outros Descontos', f"R$ {calculos[11]:.2f}"],
           ['Total Descontos', f"R$ {calculos[12]:.2f}"],
           ['Líquido', f"R$ {calculos[13]:.2f}"],
           ['Base FGTS', f"R$ {calculos[14]:.2f}"],
           ['FGTS', f"R$ {calculos[15]:.2f}"]
       ]
       
       return self.formatar_tabela(data)

    def criar_tabela_falhas(self, falhas):
       data = [['Data/Hora', 'Tipo', 'Erro', 'Detalhes']]
       for f in falhas:
           dt = datetime.strptime(f[1], '%Y-%m-%d %H:%M:%S')
           data.append([
               dt.strftime('%d/%m/%Y %H:%M:%S'),
               f[2],
               f[3],
               f[4] or ''
           ])
       
       return self.formatar_tabela(data)

    def formatar_tabela(self, data):
       table = Table(data)
       table.setStyle(TableStyle([
           ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
           ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
           ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
           ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
           ('FONTSIZE', (0, 0), (-1, 0), 12),
           ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
           ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
           ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
           ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
           ('FONTSIZE', (0, 1), (-1, -1), 10),
           ('GRID', (0, 0), (-1, -1), 1, colors.black),
           ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
           ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
           ('GRID', (0, 0), (-1, -1), 1, colors.black)
       ]))
       return table

    def gerar_csv_mensal(self, dados, mes, ano):
       try:
           filename = f"relatorio_mensal_{mes}_{ano}.csv"
           with open(filename, 'w', newline='') as csvfile:
               writer = csv.writer(csvfile)
               
               writer.writerow(['RELATÓRIO MENSAL'])
               writer.writerow([f'Período: 21/{mes}/{ano} a 20/{mes+1 if mes < 12 else 1}/{ano if mes < 12 else ano+1}'])
               writer.writerow([])
               
               # Registros
               writer.writerow(['REGISTROS DE PONTO'])
               writer.writerow(['Data', 'Hora', 'Tipo', 'Status', 'Motivo'])
               for reg in dados['registros']:
                   dt = datetime.strptime(reg[1], '%Y-%m-%d %H:%M:%S')
                   writer.writerow([
                       dt.strftime('%d/%m/%Y'),
                       dt.strftime('%H:%M:%S'),
                       reg[2], reg[3], reg[4] or ''
                   ])
               writer.writerow([])
               
               # Horas
               writer.writerow(['HORAS TRABALHADAS'])
               writer.writerow([
                   'Data', 'Normais', 'HE 60%', 'HE 65%', 
                   'HE 75%', 'HE 100%', 'HE 150%', 'Noturnas'
               ])
               for h in dados['horas']:
                   writer.writerow([
                       datetime.strptime(h[1], '%Y-%m-%d').strftime('%d/%m/%Y'),
                       f"{h[4]:.2f}", f"{h[5]:.2f}", f"{h[6]:.2f}",
                       f"{h[7]:.2f}", f"{h[8]:.2f}", f"{h[9]:.2f}",
                       f"{h[10]:.2f}"
                   ])
               
           return filename
       except Exception as e:
           self.logger.error(f"Erro ao gerar CSV: {e}")
           return None

    def gerar_json_mensal(self, dados, mes, ano):
       try:
           filename = f"relatorio_mensal_{mes}_{ano}.json"
           
           json_data = {
               'periodo': {
                   'inicio': f"21/{mes}/{ano}",
                   'fim': f"20/{mes+1 if mes < 12 else 1}/{ano if mes < 12 else ano+1}"
               },
               'registros': [],
               'horas': [],
               'calculos': {},
               'falhas': []
           }

           for reg in dados['registros']:
               dt = datetime.strptime(reg[1], '%Y-%m-%d %H:%M:%S')
               json_data['registros'].append({
                   'data': dt.strftime('%d/%m/%Y'),
                   'hora': dt.strftime('%H:%M:%S'),
                   'tipo': reg[2],
                   'status': reg[3],
                   'motivo': reg[4]
               })

           for h in dados['horas']:
               json_data['horas'].append({
                   'data': datetime.strptime(h[1], '%Y-%m-%d').strftime('%d/%m/%Y'),
                   'horas_normais': h[4],
                   'he_60': h[5],
                   'he_65': h[6],
                   'he_75': h[7],
                   'he_100': h[8],
                   'he_150': h[9],
                   'noturnas': h[10]
               })

           if dados['calculos']:
               json_data['calculos'] = {
                   'salario_base': dados['calculos'][3],
                   'periculosidade': dados['calculos'][4],
                   'adicional_noturno': dados['calculos'][5],
                   'horas_extras': dados['calculos'][6],
                   'dsr': dados['calculos'][7],
                   'total_proventos': dados['calculos'][8],
                   'inss': dados['calculos'][9],
                   'irrf': dados['calculos'][10],
                   'outros_descontos': dados['calculos'][11],
                   'total_descontos': dados['calculos'][12],
                   'liquido': dados['calculos'][13],
                   'base_fgts': dados['calculos'][14],
                   'fgts': dados['calculos'][15]
               }

           with open(filename, 'w') as jsonfile:
               json.dump(json_data, jsonfile, indent=4)

           return filename

       except Exception as e:
           self.logger.error(f"Erro ao gerar JSON: {e}")
           return None