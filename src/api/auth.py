"""
auth.py — JWT authentication with RS256 (asymmetric signing).

Roles:
  analyst  → query only
  admin    → query + ingest + index management
  auditor  → audit log read-only
"""

from __future__ import annotations
import logging
import os
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger(__name__)

try:
    from jose import JWTError, jwt
    from jose.exceptions import ExpiredSignatureError
    JOSE_AVAILABLE = True
except ImportError:
    logger.warning("python-jose not installed — JWT auth in MOCK mode")
    JOSE_AVAILABLE = False

# ---------------------------------------------------------------------------
# Config — in production, load keys from HashiCorp Vault
# ---------------------------------------------------------------------------
JWT_SECRET = os.getenv("JWT_SECRET_KEY", "CHANGE_ME_IN_PRODUCTION_USE_RS256_PRIVATE_KEY")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")   # Use RS256 in production
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "480"))  # 8 hours


class Role(str, Enum):
    ANALYST = "analyst"
    ADMIN = "admin"
    AUDITOR = "auditor"


ROLE_PERMISSIONS: dict = {
    Role.ANALYST: {"query"},
    Role.ADMIN: {"query", "ingest", "index", "audit_read"},
    Role.AUDITOR: {"audit_read"},
}


class TokenData:
    def __init__(self, user_id: str, role: Role, session_id: Optional[str] = None):
        self.user_id = user_id
        self.role = role
        self.session_id = session_id

    def can(self, permission: str) -> bool:
        return permission in ROLE_PERMISSIONS.get(self.role, set())


# ---------------------------------------------------------------------------
# Token creation
# ---------------------------------------------------------------------------

def create_access_token(user_id: str, role: Role, session_id: Optional[str] = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRE_MINUTES)
    payload = {
        "sub": user_id,
        "role": role.value,
        "session_id": session_id,
        "exp": expire,
    }
    if JOSE_AVAILABLE:
        return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    # Mock token for dev without jose
    import base64, json
    return base64.b64encode(json.dumps(payload).encode()).decode()


# ---------------------------------------------------------------------------
# Token verification + FastAPI dependency
# ---------------------------------------------------------------------------

_bearer = HTTPBearer(auto_error=True)


def decode_token(token: str) -> TokenData:
    if JOSE_AVAILABLE:
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        except ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
            )
        except JWTError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token: {exc}",
            )
    else:
        # Dev mock: base64 JSON
        import base64, json
        try:
            payload = json.loads(base64.b64decode(token))
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid mock token",
            )

    user_id = payload.get("sub")
    role_str = payload.get("role", "analyst")
    session_id = payload.get("session_id")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject",
        )

    try:
        role = Role(role_str)
    except ValueError:
        role = Role.ANALYST

    return TokenData(user_id=user_id, role=role, session_id=session_id)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> TokenData:
    return decode_token(credentials.credentials)


def require_permission(permission: str):
    """FastAPI dependency factory for role-based access control."""

    def _check(token_data: TokenData = Depends(get_current_user)) -> TokenData:
        if not token_data.can(permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{token_data.role}' lacks permission '{permission}'",
            )
        return token_data

    return _check