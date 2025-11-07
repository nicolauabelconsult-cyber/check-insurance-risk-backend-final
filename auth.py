from datetime import datetime, timedelta
from jose import jwt, JWTError
from passlib.hash import bcrypt, bcrypt_sha256

# usar bcrypt_sha256 por omissão (suporta >72 bytes)
def hash_pw(password: str) -> str:
    return bcrypt_sha256.hash(password)

# verificador compatível com hashes antigos (bcrypt) e novos (bcrypt_sha256)
def verify_pw(password: str, hashed: str) -> bool:
    try:
        # se for hash do tipo bcrypt_sha256
        if bcrypt_sha256.identify(hashed):
            return bcrypt_sha256.verify(password, hashed)
        # se for hash antigo do tipo bcrypt
        if bcrypt.identify(hashed):
            return bcrypt.verify(password, hashed)
    except Exception:
        pass
    # tentativa final (tolerante)
    try:
        return bcrypt_sha256.verify(password, hashed) or bcrypt.verify(password, hashed)
    except Exception:
        return False
