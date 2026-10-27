"""
Tokens de sesión firmados (HMAC-SHA256) y dependencias de autorización.
"""
import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path
from typing import Any

from fastapi import Header, HTTPException

PROJECT_ROOT = Path(__file__).parent.parent
SECRET_FILE = PROJECT_ROOT / ".secret_key"

ROLE_ESTUDIANTE = "estudiante"
ROLE_DOCENTE = "docente"

TOKEN_TTL_ESTUDIANTE = 12 * 3600
TOKEN_TTL_DOCENTE = 2 * 3600


def _load_secret() -> bytes:
    """Clave de firma: variable EXAMEN_SECRET_KEY o archivo .secret_key (se crea si falta)."""
    env_key = os.environ.get("EXAMEN_SECRET_KEY")
    if env_key:
        return env_key.encode()
    if SECRET_FILE.exists():
        return SECRET_FILE.read_text().strip().encode()
    key = secrets.token_hex(32)
    SECRET_FILE.write_text(key)
    SECRET_FILE.chmod(0o600)
    return key.encode()


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(payload_b64: str) -> str:
    return _b64(hmac.new(_load_secret(), payload_b64.encode(), hashlib.sha256).digest())


def create_token(sub: str, role: str, ttl: int) -> str:
    """Crea un token firmado con sujeto, rol y expiración."""
    payload = _b64(json.dumps({"sub": sub, "role": role, "exp": int(time.time()) + ttl}).encode())
    return f"{payload}.{_sign(payload)}"


def verify_token(token: str) -> dict[str, Any] | None:
    """Devuelve el payload si la firma es válida y no expiró; si no, None."""
    try:
        payload_b64, signature = token.split(".", 1)
        if not hmac.compare_digest(signature, _sign(payload_b64)):
            return None
        payload = json.loads(_unb64(payload_b64))
    except (ValueError, TypeError):
        return None
    if payload.get("exp", 0) < time.time():
        return None
    return payload


def _payload_from_header(authorization: str | None, role: str) -> dict[str, Any]:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Sesión requerida")
    payload = verify_token(authorization[7:])
    if payload is None or payload.get("role") != role:
        raise HTTPException(status_code=401, detail="Sesión inválida o expirada")
    return payload


def estudiante_actual(authorization: str | None = Header(default=None)) -> int:
    """Dependencia FastAPI: devuelve el id del estudiante autenticado."""
    return int(_payload_from_header(authorization, ROLE_ESTUDIANTE)["sub"])


def require_docente(authorization: str | None = Header(default=None)) -> None:
    """Dependencia FastAPI: exige un token de docente válido."""
    _payload_from_header(authorization, ROLE_DOCENTE)
