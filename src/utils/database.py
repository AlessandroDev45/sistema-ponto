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
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO registros (data_hora, tipo, status, motivo)
                    VALUES (?, ?, ?, ?)
                ''', (data_hora, tipo, status, motivo))
                conn.commit()
                self.logger.info(f"Registro de ponto salvo: {data_hora} - {tipo} - {status}")
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
                    SELECT * FROM registros
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