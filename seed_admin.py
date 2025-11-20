# seed_admin.py
"""
Criar utilizador principal (seed) para o Check Insurance Risk
"""

from database import execute_query
from auth import get_password_hash


def seed_default_user():
    """
    Garante que existe pelo menos um utilizador principal.

    Login:
      - Email:    nicolauabel.consult@gmail.com
      - Username: nicolauabel
      - Password: Qwerty080397
    """

    email = "nicolauabel.consult@gmail.com"
    username = "nicolauabel"
    plain_password = "Qwerty080397"

    hashed_password = get_password_hash(plain_password)

    query = """
        INSERT INTO users (username, email, password_hash, role, is_active)
        SELECT %s, %s, %s, 'ADMIN', true
        WHERE NOT EXISTS (
            SELECT 1 FROM users WHERE email = %s
        )
        RETURNING id
    """

    result = execute_query(
        query,
        (username, email, hashed_password, email),
    )

    if result:
        print(f"[seed_admin] Utilizador principal criado: {email}")
    else:
        print(f"[seed_admin] Utilizador já existia: {email}")
