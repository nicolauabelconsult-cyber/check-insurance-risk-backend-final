# database.py
"""
Ligação à base de dados PostgreSQL no Railway.
Usa primeiro DATABASE_URL (se existir) ou então DB_HOST, DB_NAME, DB_USER, DB_PASSWORD, DB_PORT.
"""

import os
from typing import Any, List, Tuple, Optional

import psycopg2
from psycopg2.extras import RealDictCursor

# 1) Se o Railway fornecer DATABASE_URL, usamos diretamente
DATABASE_URL = os.getenv("DATABASE_URL")

# 2) Caso contrário, usamos as variáveis que tu configuraste:
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "railway")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_PORT = int(os.getenv("DB_PORT", "5432"))


def get_connection():
    """
    Cria uma ligação nova ao PostgreSQL.
    """
    try:
        if DATABASE_URL:
            # Formato típico: postgres://user:pass@host:port/dbname
            conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        else:
            conn = psycopg2.connect(
                host=DB_HOST,
                dbname=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD,
                port=DB_PORT,
                cursor_factory=RealDictCursor,
            )
        return conn
    except Exception as e:
        # Isto vai aparecer nos Deploy Logs do Railway
        print(
            f"[DB] Erro ao conectar com o banco: "
            f"host={DB_HOST} db={DB_NAME} user={DB_USER} erro={e}"
        )
        raise


def execute_query(sql: str, params: Optional[Tuple[Any, ...]] = None) -> List[dict]:
    """
    Executa uma query simples.
    - Para SELECT: devolve lista de dicionários.
    - Para INSERT/UPDATE/DELETE: faz commit e devolve [] ou rows se houver RETURNING.
    """
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(sql, params or ())
        rows: List[dict] = []
        # Se houver resultados (SELECT ou RETURNING), lê
        if cur.description is not None:
            rows = cur.fetchall()
        conn.commit()
        return rows
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"[DB] Erro em execute_query: {e} | SQL={sql} | params={params}")
        raise
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def execute_transaction(queries: List[Tuple[str, Tuple[Any, ...]]]) -> None:
    """
    Executa várias queries numa única transacção.
    `queries` = lista de (sql, params).
    """
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        for sql, params in queries:
            cur.execute(sql, params or ())
        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"[DB] Erro em execute_transaction: {e}")
        raise
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()
