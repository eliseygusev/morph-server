from starlette.authentication import AuthenticationBackend, AuthCredentials, SimpleUser, AuthenticationError
from starlette.requests import HTTPConnection
from starlette.middleware.authentication import AuthenticationMiddleware
import jwt
from typing import Optional, Tuple
import os

class JWTAuthBackend(AuthenticationBackend):
    def __init__(self, secret_key: Optional[str] = None, algorithm: str = "HS256"):
        self.secret_key = secret_key or os.environ.get("JWT_SECRET_KEY", "your-secret-key")
        self.algorithm = algorithm
    
    async def authenticate(self, conn: HTTPConnection) -> Optional[Tuple[AuthCredentials, SimpleUser]]:
        if "Authorization" not in conn.headers:
            return None
        
        auth_header = conn.headers["Authorization"]
        
        try:
            scheme, token = auth_header.split()
            if scheme.lower() != "bearer":
                return None
        except ValueError:
            return None
        
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            user_id = payload.get("sub", "user")
            return AuthCredentials(["authenticated"]), SimpleUser(user_id)
        except jwt.ExpiredSignatureError:
            raise AuthenticationError("Token has expired")
        except jwt.InvalidTokenError:
            raise AuthenticationError("Invalid token")

def get_auth_middleware(app, secret_key: Optional[str] = None):
    return AuthenticationMiddleware(app, backend=JWTAuthBackend(secret_key))