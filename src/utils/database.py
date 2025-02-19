# database/schema.py
import sqlite3
from datetime import datetime
import logging

class Database:
    def __init__(self, db_file='registro_ponto.db'):
        self.db_file = db_file
        self.logger = logging.getLogger('Database')
        self.init_database()

    def init_database(self):
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS registros (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    data_hora DATETIME NOT NULL,
                    tipo TEXT NOT NULL,
                    status TEXT NOT NULL,
                    motivo TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS horas_trabalhadas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    data DATE NOT NULL,
                    entrada DATETIME,
                    saida DATETIME,
                    horas_normais REAL,
                    horas_extras_60 REAL DEFAULT 0,
                    horas_extras_65 REAL DEFAULT 0,
                    horas_extras_75 REAL DEFAULT 0,
                    horas_extras_100 REAL DEFAULT 0,
                    horas_extras_150 REAL DEFAULT 0,
                    horas_noturnas REAL DEFAULT 0,
                    status TEXT NOT NULL,
                    observacao TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS falhas_registro (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    data_hora DATETIME NOT NULL,
                    tipo TEXT NOT NULL,
                    erro TEXT NOT NULL,
                    detalhes TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS calculadas_mensais (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mes INTEGER NOT NULL,
                    ano INTEGER NOT NULL,
                    salario_base REAL NOT NULL,
                    periculosidade REAL DEFAULT 0,
                    adicional_noturno REAL DEFAULT 0,
                    horas_extras REAL DEFAULT 0,
                    dsr REAL DEFAULT 0,
                    total_proventos REAL NOT NULL,
                    inss REAL NOT NULL,
                    irrf REAL NOT NULL,
                    outros_descontos REAL DEFAULT 0,
                    total_descontos REAL NOT NULL,
                    liquido REAL NOT NULL,
                    base_fgts REAL NOT NULL,
                    fgts REAL NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(mes, ano)
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS configuracoes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chave TEXT UNIQUE NOT NULL,
                    valor TEXT NOT NULL,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()

    def registrar_ponto(self, data_hora, tipo, status, motivo=None):
        try:
            data_formatada = data_hora.strftime('%Y-%m-%d %H:%M:%S')
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO registros (data_hora, tipo, status, motivo)
                    VALUES (?, ?, ?, ?)
                ''', (data_formatada, tipo, status, motivo))
                conn.commit()
                self.logger.info(f"Registro de ponto salvo: {data_formatada} - {tipo} - {status}")
                return True
        except Exception as e:
            self.logger.error(f"Erro ao registrar ponto: {e}")
            self.registrar_falha("registro_ponto", str(e))
            return False

    def registrar_horas_trabalhadas(self, data, entrada, saida, horas_normais, 
                                  horas_extras, horas_noturnas, status, observacao=None):
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO horas_trabalhadas (
                        data, entrada, saida, horas_normais,
                        horas_extras_60, horas_extras_65, horas_extras_75,
                        horas_extras_100, horas_extras_150,
                        horas_noturnas, status, observacao
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    data, entrada, saida, horas_normais,
                    horas_extras.get('60', 0), horas_extras.get('65', 0),
                    horas_extras.get('75', 0), horas_extras.get('100', 0),
                    horas_extras.get('150', 0), horas_noturnas,
                    status, observacao
                ))
                conn.commit()
                self.logger.info(f"Horas trabalhadas registradas: {data}")
                return True
        except Exception as e:
            self.logger.error(f"Erro ao registrar horas trabalhadas: {e}")
            self.registrar_falha("registro_horas", str(e))
            return False

    def registrar_falha(self, tipo, erro, detalhes=None):
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO falhas_registro (data_hora, tipo, erro, detalhes)
                    VALUES (?, ?, ?, ?)
                ''', (datetime.now(), tipo, erro, detalhes))
                conn.commit()
                self.logger.error(f"Falha registrada: {tipo} - {erro}")
        except Exception as e:
            self.logger.critical(f"Erro ao registrar falha: {e}")

    def salvar_calculo_mensal(self, dados):
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO calculadas_mensais (
                        mes, ano, salario_base, periculosidade,
                        adicional_noturno, horas_extras, dsr,
                        total_proventos, inss, irrf,
                        outros_descontos, total_descontos,
                        liquido, base_fgts, fgts
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    dados['mes'], dados['ano'], dados['salario_base'],
                    dados['periculosidade'], dados['adicional_noturno'],
                    dados['horas_extras'], dados['dsr'], dados['total_proventos'],
                    dados['inss'], dados['irrf'], dados['outros_descontos'],
                    dados['total_descontos'], dados['liquido'],
                    dados['base_fgts'], dados['fgts']
                ))
                conn.commit()
                self.logger.info(f"Cálculo mensal salvo: {dados['mes']}/{dados['ano']}")
                return True
        except Exception as e:
            self.logger.error(f"Erro ao salvar cálculo mensal: {e}")
            self.registrar_falha("calculo_mensal", str(e))
            return False

    def obter_registros_periodo(self, data_inicio, data_fim):
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, 
                        strftime('%Y-%m-%d %H:%M:%S', data_hora) as data_hora,
                        tipo, status, motivo, created_at
                    FROM registros
                    WHERE data_hora BETWEEN ? AND ?
                    ORDER BY data_hora
                ''', (data_inicio, data_fim))
                return cursor.fetchall()
        except Exception as e:
            self.logger.error(f"Erro ao obter registros do período: {e}")
            return []

    def obter_horas_trabalhadas_periodo(self, data_inicio, data_fim):
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM horas_trabalhadas
                    WHERE data BETWEEN ? AND ?
                    ORDER BY data
                ''', (data_inicio, data_fim))
                return cursor.fetchall()
        except Exception as e:
            self.logger.error(f"Erro ao obter horas trabalhadas do período: {e}")
            return []

    def obter_falhas_periodo(self, data_inicio, data_fim):
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM falhas_registro
                    WHERE data_hora BETWEEN ? AND ?
                    ORDER BY data_hora
                ''', (data_inicio, data_fim))
                return cursor.fetchall()
        except Exception as e:
            self.logger.error(f"Erro ao obter falhas do período: {e}")
            return []

    def obter_calculo_mensal(self, mes, ano):
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM calculadas_mensais
                    WHERE mes = ? AND ano = ?
                ''', (mes, ano))
                return cursor.fetchone()
        except Exception as e:
            self.logger.error(f"Erro ao obter cálculo mensal: {e}")
            return None
        
    def obter_ultimo_registro(self):
        """Obtém o último registro de ponto do sistema"""
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, data_hora, tipo, status, motivo 
                    FROM registros 
                    ORDER BY data_hora DESC 
                    LIMIT 1
                ''')
                return cursor.fetchone()
        except Exception as e:
            self.logger.error(f"Erro ao obter último registro: {e}")
            return None

    def obter_registros_dia(self, data):
        """Obtém todos os registros de um dia específico"""
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, data_hora, tipo, status, motivo 
                    FROM registros 
                    WHERE DATE(data_hora) = DATE(?)
                    ORDER BY data_hora
                ''', (data,))
                return cursor.fetchall()
        except Exception as e:
            self.logger.error(f"Erro ao obter registros do dia: {e}")
            return []

    def calcular_horas_trabalhadas_dia(self, data):
        """Calcula as horas trabalhadas em um dia específico"""
        try:
            registros = self.obter_registros_dia(data)
            if len(registros) % 2 != 0:
                return None  # Número ímpar de registros

            total_horas = {
                'normais': 0,
                'extras_60': 0,
                'extras_65': 0,
                'extras_75': 0,
                'extras_100': 0,
                'extras_150': 0,
                'noturnas': 0
            }

            for i in range(0, len(registros), 2):
                entrada = datetime.strptime(registros[i][1], '%Y-%m-%d %H:%M:%S')
                saida = datetime.strptime(registros[i+1][1], '%Y-%m-%d %H:%M:%S')
                
                # Calcula diferença em horas
                delta = saida - entrada
                horas = delta.total_seconds() / 3600

                # Distribuição das horas
                if horas <= 8:
                    total_horas['normais'] += horas
                else:
                    total_horas['normais'] += 8
                    total_horas['extras_60'] += (horas - 8)

                # Verifica horas noturnas (22h às 5h)
                if entrada.hour >= 22 or saida.hour < 5:
                    total_horas['noturnas'] += horas

            return total_horas

        except Exception as e:
            self.logger.error(f"Erro ao calcular horas trabalhadas: {e}")
            return None

    def salvar_horas_trabalhadas_dia(self, data, horas):
        """Salva o cálculo de horas trabalhadas do dia"""
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                
                # Verifica se já existe registro para o dia
                cursor.execute('''
                    SELECT id FROM horas_trabalhadas 
                    WHERE DATE(data) = DATE(?)
                ''', (data,))
                
                existe = cursor.fetchone()
                
                if existe:
                    cursor.execute('''
                        UPDATE horas_trabalhadas 
                        SET horas_normais = ?,
                            horas_extras_60 = ?,
                            horas_extras_65 = ?,
                            horas_extras_75 = ?,
                            horas_extras_100 = ?,
                            horas_extras_150 = ?,
                            horas_noturnas = ?,
                            status = ?,
                            observacao = ?
                        WHERE DATE(data) = DATE(?)
                    ''', (
                        horas['normais'],
                        horas['extras_60'],
                        horas['extras_65'],
                        horas['extras_75'],
                        horas['extras_100'],
                        horas['extras_150'],
                        horas['noturnas'],
                        'ATUALIZADO',
                        'Cálculo atualizado',
                        data
                    ))
                else:
                    cursor.execute('''
                        INSERT INTO horas_trabalhadas (
                            data, horas_normais, horas_extras_60,
                            horas_extras_65, horas_extras_75,
                            horas_extras_100, horas_extras_150,
                            horas_noturnas, status, observacao
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        data,
                        horas['normais'],
                        horas['extras_60'],
                        horas['extras_65'],
                        horas['extras_75'],
                        horas['extras_100'],
                        horas['extras_150'],
                        horas['noturnas'],
                        'CALCULADO',
                        'Cálculo inicial'
                    ))
                
                conn.commit()
                return True
                
        except Exception as e:
            self.logger.error(f"Erro ao salvar horas trabalhadas: {e}")
            self.registrar_falha("salvar_horas", str(e))
            return False

    def obter_saldo_banco_horas(self, data_ref=None):
        """Obtém o saldo do banco de horas até uma data"""
        if not data_ref:
            data_ref = datetime.now()

        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT 
                        SUM(horas_extras_60 + horas_extras_65 + 
                            horas_extras_75 + horas_extras_100 + 
                            horas_extras_150) as total_extras,
                        SUM(CASE 
                            WHEN horas_normais < 8 
                            THEN 8 - horas_normais 
                            ELSE 0 
                        END) as total_debitos
                    FROM horas_trabalhadas
                    WHERE data <= ?
                ''', (data_ref.strftime('%Y-%m-%d'),))
                
                resultado = cursor.fetchone()
                if resultado:
                    return {
                        'saldo': resultado[0] - resultado[1],
                        'extras': resultado[0],
                        'debitos': resultado[1]
                    }
                return {'saldo': 0, 'extras': 0, 'debitos': 0}
                
        except Exception as e:
            self.logger.error(f"Erro ao obter saldo do banco de horas: {e}")
            return None

    def registrar_configuracao(self, chave, valor):
        """Registra ou atualiza uma configuração"""
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO configuracoes (chave, valor)
                    VALUES (?, ?)
                ''', (chave, valor))
                conn.commit()
                return True
        except Exception as e:
            self.logger.error(f"Erro ao registrar configuração: {e}")
            return False

    def obter_configuracao(self, chave):
        """Obtém uma configuração específica"""
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT valor FROM configuracoes
                    WHERE chave = ?
                ''', (chave,))
                resultado = cursor.fetchone()
                return resultado[0] if resultado else None
        except Exception as e:
            self.logger.error(f"Erro ao obter configuração: {e}")
            return None