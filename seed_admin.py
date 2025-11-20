from auth import get_password_hash
from database import execute_query


def run():
    """
    Cria ou actualiza o utilizador inicial definitivo
    e desactiva o admin antigo, se existir.
    """

    username = "nicolauabel"
    email = "nicolauabel.consult@gmail.com"
    password = "Qwerty080397"
    role = "admin"

    # Gerar hash da palavra-passe
    password_hash = get_password_hash(password)

    # Verificar se já existe utilizador com este e-mail ou username
    existing = execute_query(
        """
        SELECT id
        FROM users
        WHERE email = %s OR username = %s
        """,
        (email, username),
    )

    if existing:
        user_id = existing[0]["id"]

        # Actualizar dados + reactivar
        execute_query(
            """
            UPDATE users
            SET username = %s,
                email = %s,
                password_hash = %s,
                role = %s,
                is_active = true
            WHERE id = %s
            """,
            (username, email, password_hash, role, user_id),
        )
        print("Utilizador inicial actualizado com sucesso.")
    else:
        # Criar novo utilizador
        execute_query(
            """
            INSERT INTO users (
                username,
                email,
                password_hash,
                role,
                is_active,
                created_at
            )
            VALUES (%s, %s, %s, %s, true, NOW())
            """,
            (username, email, password_hash, role),
        )
        print("Utilizador inicial criado com sucesso.")

    # Desactivar admin antigo (admin/admin123 ou similar)
    execute_query(
        """
        UPDATE users
        SET is_active = false
        WHERE username = 'admin'
          AND email <> %s
        """,
        (email,),
    )
    print("Admin antigo desactivado (se existia).")


if __name__ == "__main__":
    run()
