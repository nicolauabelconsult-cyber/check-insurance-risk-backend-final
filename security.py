"""
Módulo de segurança
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from auth import verify_token
from database import execute_query
from models import UserInfo, RoleEnum

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> UserInfo:
    """Obter usuário atual do token"""
    try:
        token = credentials.credentials
        payload = verify_token(token)
        
        # Buscar usuário no banco
        query = """
            SELECT id, username, email, role, is_active, last_login, created_at
            FROM users WHERE id = %s AND is_active = true
        """
        users = execute_query(query, (payload['id'],))
        
        if not users:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuário não encontrado"
            )
        
        user = users[0]
        return UserInfo(
            id=user['id'],
            username=user['username'],
            email=user['email'],
            role=user['role'],
            last_login=user['last_login'],
            created_at=user['created_at']
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido"
        )

async def get_admin_user(
    current_user: UserInfo = Depends(get_current_user)
) -> UserInfo:
    """Verificar se usuário é admin"""
    if current_user.role != RoleEnum.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado: permissões de administrador necessárias"
        )
    return current_user

def create_jwt(data: dict) -> str:
    """Criar JWT token (alias para create_access_token)"""
    from auth import create_access_token
    return create_access_token(data)

def verify_jwt(token: str) -> dict:
    """Verificar JWT token (alias para verify_token)"""
    from auth import verify_token
    return verify_token(token)

def hash_password(password: str) -> str:
    """Hash de senha (alias para get_password_hash)"""
    from auth import get_password_hash
    return get_password_hash(password)

def check_password(plain_password: str, hashed_password: str) -> bool:
    """Verificar senha (alias para verify_password)"""
    from auth import verify_password
    return verify_password(plain_password, hashed_password)

class RateLimiter:
    """Rate limiting simples"""
    def __init__(self, max_requests: int = 100, window: int = 3600):
        self.max_requests = max_requests
        self.window = window
        self.requests = {}
    
    def is_allowed(self, key: str) -> bool:
        """Verificar se requisição é permitida"""
        import time
        now = time.time()
        
        if key not in self.requests:
            self.requests[key] = []
        
        # Remove requisições antigas
        self.requests[key] = [
            req_time for req_time in self.requests[key] 
            if now - req_time < self.window
        ]
        
        # Verifica limite
        if len(self.requests[key]) >= self.max_requests:
            return False
        
        # Adiciona requisição atual
        self.requests[key].append(now)
        return True

# Instância global do rate limiter
rate_limiter = RateLimiter()
