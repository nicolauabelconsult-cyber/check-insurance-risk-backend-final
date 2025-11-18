"""
Módulo de conexão com banco de dados
"""
import psycopg2
from psycopg2.extras import RealDictCursor
import os

DATABASE_URL = os.getenv("DATABASE_URL")

def get_db_connection():
    """Obter conexão com banco"""
    try:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        return conn
    except Exception as e:
        print(f"Erro ao conectar com o banco: {e}")
        raise

def execute_query(query: str, params=None):
    """Executar query no banco"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(query, params)
        
        if query.strip().upper().startswith('SELECT'):
            result = cursor.fetchall()
        else:
            conn.commit()
            if 'RETURNING' in query.upper():
                result = cursor.fetchall()
            else:
                result = cursor.rowcount
            
        return result
    except Exception as e:
        conn.rollback()
        print(f"Erro na query: {e}")
        raise
    finally:
        conn.close()

def execute_transaction(queries: list):
    """Executar múltiplas queries em transação"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        results = []
        
        for query, params in queries:
            cursor.execute(query, params)
            
            if query.strip().upper().startswith('SELECT'):
                results.append(cursor.fetchall())
            else:
                if 'RETURNING' in query.upper():
                    results.append(cursor.fetchall())
                else:
                    results.append(cursor.rowcount)
        
        conn.commit()
        return results
    except Exception as e:
        conn.rollback()
        print(f"Erro na transação: {e}")
        raise
    finally:
        conn.close()
