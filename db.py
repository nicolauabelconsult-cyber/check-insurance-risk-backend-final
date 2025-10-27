import sqlite3
from datetime import datetime

DB_PATH = "cir.db"

def hash_password(raw: str) -> str:
    import hashlib
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    cur = conn.cursor()

    # tabela utilizadores
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL,
        active INTEGER NOT NULL DEFAULT 1
    )
    """)

    # tabela base de risco
    cur.execute("""
    CREATE TABLE IF NOT EXISTS risk_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        identifier TEXT NOT NULL,
        identifier_type TEXT NOT NULL,
        score_final INTEGER NOT NULL,
        justificacao TEXT NOT NULL,
        pep_alert INTEGER NOT NULL,
        sanctions_alert INTEGER NOT NULL,
        updated_at TEXT NOT NULL
    )
    """)

    # tabela auditoria
    cur.execute("""
    CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        consulta_id TEXT NOT NULL,
        identifier TEXT NOT NULL,
        decisao TEXT NOT NULL,
        score_final INTEGER NOT NULL,
        requested_by TEXT NOT NULL,
        timestamp TEXT NOT NULL
    )
    """)

    # tabela fontes de informação
    cur.execute("""
    CREATE TABLE IF NOT EXISTS info_sources (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        url TEXT,
        directory TEXT,
        filename TEXT,
        uploaded_at TEXT NOT NULL
    )
    """)

    # criar admin inicial se não existir
    cur.execute("SELECT id FROM users WHERE email = ?", ("admin@checkrisk.com",))
    if cur.fetchone() is None:
        cur.execute(
            "INSERT INTO users (email, name, password_hash, role, active) VALUES (?, ?, ?, ?, 1)",
            (
                "admin@checkrisk.com",
                "Administrador",
                hash_password("123456"),
                "admin",
            )
        )
        conn.commit()

    conn.commit()
    conn.close()
