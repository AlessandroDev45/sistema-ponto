# src/calculos/processor.py
from datetime import datetime, date
import logging
from ..utils.logger import setup_logger

class ProcessadorDados:
    def __init__(self, database):
        self.db = database
        self.logger = setup_logger('ProcessadorDados')

    def processar_registros_diarios(self, data=None):
        if not data:
            data = date.today()
        
        try:
            registros = self.db.obter_registros_periodo(
                datetime.combine(data, datetime.min.time()),
                datetime.combine(data, datetime.max.time())
            )
            
            if not registros:
                return None

            entradas = []
            saidas = []
            
            for registro in registros:
                if registro[2] == 'ENTRADA':
                    entradas.append(datetime.strptime(registro[1], '%Y-%m-%d %H:%M:%S'))
                else:
                    saidas.append(datetime.strptime(registro[1], '%Y-%m-%d %H:%M:%S'))

            horas_normais = 0
            horas_extras = {
                '60': 0, '65': 0, '75': 0,
                '100': 0, '150': 0
            }
            horas_noturnas = 0

            for entrada, saida in zip(entradas, saidas):
                diferenca = (saida - entrada).total_seconds() / 3600
                
                if diferenca <= 8:
                    horas_normais += diferenca
                else:
                    horas_normais += 8
                    horas_extras['60'] += diferenca - 8

                # Calcula horas noturnas (22h às 5h)
                if entrada.hour >= 22 or saida.hour < 5:
                    horas_noturnas += diferenca

            return {
                'data': data,
                'horas_normais': horas_normais,
                'horas_extras': horas_extras,
                'horas_noturnas': horas_noturnas
            }

        except Exception as e:
            self.logger.error(f"Erro ao processar registros diários: {e}")
            return None