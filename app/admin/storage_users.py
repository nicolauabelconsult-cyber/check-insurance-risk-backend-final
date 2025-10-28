from typing import Optional, List

_users = [
    {
        "name": "Administrador",
        "email": "admin@checkrisk.com",
        "password": "123456",
        "role": "admin"
    },
    {
        "name": "Analista",
        "email": "analyst@checkrisk.com",
        "password": "123456",
        "role": "analyst"
    }
]

def get_user_by_email(email: str) -> Optional[dict]:
    for u in _users:
        if u["email"].lower() == email.lower():
            return u
    return None

def get_user_by_email_no_pwd(email: str) -> Optional[dict]:
    u = get_user_by_email(email)
    if not u:
        return None
    return {"name": u["name"], "email": u["email"], "role": u["role"]}

def validate_login(email: str, password: str) -> Optional[dict]:
    u = get_user_by_email(email)
    if u and u["password"] == password:
        return u
    return None

def create_user(name: str, email: str, password: str, role: str) -> dict:
    u = {
        "name": name,
        "email": email,
        "password": password,
        "role": role
    }
    _users.append(u)
    return {"ok": True}

def list_users() -> List[dict]:
    return [{"name":u["name"], "email":u["email"], "role":u["role"]} for u in _users]
