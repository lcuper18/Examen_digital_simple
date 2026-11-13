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


def create_token(sub: str, role: str, ttl: int, version: int | None = None) -> str:
    """
    Crea un token firmado con sujeto, rol y expiración. `version` (solo estudiantes) es la versión de sesión de la
    cuenta: si el docente reinicia la contraseña, la versión sube y los tokens anteriores dejan de servir.
    """
    datos: dict[str, Any] = {"sub": sub, "role": role, "exp": int(time.time()) + ttl}
    if version is not None:
        datos["sv"] = version
    payload = _b64(json.dumps(datos).encode())
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


def estudiante_autenticado(authorization: str | None = Header(default=None)) -> int:
    """Dependencia FastAPI: id del estudiante según el token (sin consultar la cuenta)."""
    return int(_payload_from_header(authorization, ROLE_ESTUDIANTE)["sub"])


def estudiante_actual(authorization: str | None = Header(default=None)) -> int:
    """
    Dependencia FastAPI: id del estudiante autenticado, con cuenta activa y sin
    cambio de contraseña pendiente.
    """
    from backend import database  # import diferido: database no depende de security

    payload = _payload_from_header(authorization, ROLE_ESTUDIANTE)
    estudiante_id = int(payload["sub"])
    with database.get_db_context() as conn:
        fila = conn.execute(
            "SELECT activo, debe_cambiar_password, sesion_version FROM estudiantes WHERE id = ?", (estudiante_id,)
        ).fetchone()
    if fila is None or not fila["activo"]:
        raise HTTPException(status_code=401, detail="Cuenta desactivada o inexistente")
    if payload.get("sv", 0) != fila["sesion_version"]:
        # El docente reinició la contraseña (o ella misma la cambió) después de que se creó este token
        raise HTTPException(status_code=401, detail="Tu sesión terminó. Vuelve a entrar con tu contraseña.")
    if fila["debe_cambiar_password"]:
        raise HTTPException(status_code=403, detail="Debes cambiar tu contraseña antes de continuar")
    return estudiante_id


def require_docente(authorization: str | None = Header(default=None)) -> None:
    """Dependencia FastAPI: exige un token de docente válido."""
    _payload_from_header(authorization, ROLE_DOCENTE)
