import sys
import os
from pathlib import Path

# Adiciona o diretório raiz ao Python Path
current_dir = Path(__file__).resolve().parent
root_dir = current_dir.parent.parent
sys.path.append(str(root_dir))

from datetime import datetime, timedelta
import calendar
import logging

from config.config import Config

class CalculosTrabalhistas:
    def __init__(self, salario_base):
        self.config = Config.get_instance()
        self.salario_base = salario_base  # Agora aceita o salário base como parâmetro
        self.valor_hora = self.salario_base / 220
        self.logger = logging.getLogger('CalculosTrabalhistas')
        
        self.percentuais = {
            'periculosidade': self.config.PERICULOSIDADE,
            'adicional_noturno': self.config.ADICIONAL_NOTURNO,
            'he_60': self.config.HORAS_EXTRAS['60'],
            'he_65': self.config.HORAS_EXTRAS['65'],
            'he_75': self.config.HORAS_EXTRAS['75'],
            'he_100': self.config.HORAS_EXTRAS['100'],
            'he_150': self.config.HORAS_EXTRAS['150'],
            'fgts': 0.08
        }
        
        self.tabela_inss = [
            (1412.00, 0.075),
            (2666.68, 0.09),
            (4000.03, 0.12),
            (float('inf'), 0.14)
        ]
        
        self.tabela_irrf = [
            (2112.00, 0.00, 0.00),
            (2826.65, 0.075, 158.40),
            (3751.05, 0.15, 370.40),
            (4664.68, 0.225, 651.73),
            (float('inf'), 0.275, 884.96)
        ]

    def calcular_valor_hora(self, horas, tipo='normal'):
        try:
            if tipo == 'normal':
                return horas * self.valor_hora
            elif tipo.startswith('he_'):
                percentual = self.percentuais.get(tipo, 0)
                return horas * self.valor_hora * (1 + percentual)
            elif tipo == 'noturno':
                return horas * self.valor_hora * (1 + self.percentuais['adicional_noturno'])
            else:
                raise ValueError(f"Tipo de hora inválido: {tipo}")
        except Exception as e:
            self.logger.error(f"Erro ao calcular valor hora: {e}")
            return 0

    def calcular_periculosidade(self):
        return self.salario_base * self.percentuais['periculosidade']

    def calcular_dsr(self, total_variaveis, dias_uteis, domingos_feriados):
        try:
            if dias_uteis == 0:
                return 0
            return (total_variaveis / dias_uteis) * domingos_feriados
        except Exception as e:
            self.logger.error(f"Erro ao calcular DSR: {e}")
            return 0

    def calcular_inss(self, base_calculo):
        try:
            for limite, aliquota in self.tabela_inss:
                if base_calculo <= limite:
                    return base_calculo * aliquota
            return base_calculo * self.tabela_inss[-1][1]
        except Exception as e:
            self.logger.error(f"Erro ao calcular INSS: {e}")
            return 0

    def calcular_irrf(self, base_calculo):
        try:
            for limite, aliquota, deducao in self.tabela_irrf:
                if base_calculo <= limite:
                    return (base_calculo * aliquota) - deducao
            return (base_calculo * self.tabela_irrf[-1][1]) - self.tabela_irrf[-1][2]
        except Exception as e:
            self.logger.error(f"Erro ao calcular IRRF: {e}")
            return 0

    def calcular_fgts(self, base_calculo):
        return base_calculo * self.percentuais['fgts']

class ProcessadorFolha:
    def __init__(self, database, calculadora):
        self.db = database
        self.calculadora = calculadora
        self.logger = logging.getLogger('ProcessadorFolha')

    def processar_periodo(self, mes, ano):
        try:
            inicio_periodo = datetime(ano, mes, 21)
            if mes == 12:
                fim_periodo = datetime(ano + 1, 1, 20)
            else:
                fim_periodo = datetime(ano, mes + 1, 20)

            registros = self.db.obter_registros_periodo(inicio_periodo, fim_periodo)
            horas_trabalhadas = self.db.obter_horas_trabalhadas_periodo(inicio_periodo, fim_periodo)
            
            totais = {
                'mes': mes,
                'ano': ano,
                'horas_normais': 0,
                'horas_extras': {'60': 0, '65': 0, '75': 0, '100': 0, '150': 0},
                'horas_noturnas': 0,
                'dias_uteis': self.contar_dias_uteis(inicio_periodo, fim_periodo),
                'domingos_feriados': self.contar_domingos_feriados(inicio_periodo, fim_periodo)
            }

            for registro in horas_trabalhadas:
                self.acumular_horas(registro, totais)

            valores = self.calcular_valores(totais)
            self.db.salvar_calculo_mensal(valores)
            
            return valores

        except Exception as e:
            self.logger.error(f"Erro ao processar período {mes}/{ano}: {e}")
            return None

    def acumular_horas(self, registro, totais):
        totais['horas_normais'] += registro[4]
        for idx, tipo in enumerate(['60', '65', '75', '100', '150']):
            totais['horas_extras'][tipo] += registro[5 + idx]
        totais['horas_noturnas'] += registro[10]

    def calcular_valores(self, totais):
        try:
            valores = {
                'mes': totais['mes'],
                'ano': totais['ano'],
                'salario_base': self.calculadora.salario_base,
                'periculosidade': self.calculadora.calcular_periculosidade(),
                'horas_normais': self.calculadora.calcular_valor_hora(totais['horas_normais']),
                'horas_extras': sum(self.calculadora.calcular_valor_hora(horas, f'he_{tipo}') for tipo, horas in totais['horas_extras'].items()),
                'adicional_noturno': self.calculadora.calcular_valor_hora(totais['horas_noturnas'], 'noturno')
            }

            valores['subtotal'] = sum(v for k, v in valores.items() if k not in ['mes', 'ano'])  # Exclui chaves não numéricas
            valores['dsr'] = self.calculadora.calcular_dsr(valores['subtotal'] - valores['salario_base'], totais['dias_uteis'], totais['domingos_feriados'])
            
            valores['total_proventos'] = valores['subtotal'] + valores['dsr']
            valores['inss'] = self.calculadora.calcular_inss(valores['total_proventos'])
            valores['irrf'] = self.calculadora.calcular_irrf(valores['total_proventos'] - valores['inss'])
            valores['fgts'] = self.calculadora.calcular_fgts(valores['total_proventos'])
            valores['total_descontos'] = valores['inss'] + valores['irrf']
            valores['liquido'] = valores['total_proventos'] - valores['total_descontos']
            valores['base_fgts'] = valores['total_proventos']

            return valores
            
        except Exception as e:
            self.logger.error(f"Erro ao calcular valores: {str(e)}")
            raise

    def contar_dias_uteis(self, inicio, fim):
        dias = 0
        data_atual = inicio
        while data_atual <= fim:
            if data_atual.weekday() < 5:
                dias += 1
            data_atual += timedelta(days=1)
        return dias

    def contar_domingos_feriados(self, inicio, fim):
        dias = 0
        data_atual = inicio
        while data_atual <= fim:
            if data_atual.weekday() == 6:
                dias += 1
            data_atual += timedelta(days=1)
        return dias