
from auth import get_password_hash
from database import execute_query


def run():
    username = "nicolauabel"
    email = "nicolauabel.consult@gmail.com"
    password = "Qwerty080397"
    role = "admin"

    password_hash = get_password_hash(password)

    existing = execute_query(
        "SELECT id FROM users WHERE username = %s OR email = %s",
        (username, email),
    )
    if existing:
        print("Utilizador já existe, nada a fazer.")
        return

    execute_query(
        '''
        INSERT INTO users (username, email, password_hash, role, is_active, created_at)
        VALUES (%s, %s, %s, %s, true, NOW())
        ''',
        (username, email, password_hash, role),
    )
    print("Utilizador admin criado com sucesso.")


if __name__ == "__main__":
    run()
