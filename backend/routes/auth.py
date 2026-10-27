"""
Auth routes - Login and teacher password verification.
"""
import hashlib
import hmac
import os
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from backend import database, security

router = APIRouter(prefix="/api", tags=["auth"])

# Hash SHA-256 de la contraseña del docente (sobrescribible con DOCENTE_PASSWORD_HASH)
TEACHER_PASSWORD_HASH = os.environ.get(
    "DOCENTE_PASSWORD_HASH",
    "849018898d5676cde9c6723b4604bd196d65e33c25304ec6e71fd7cc56af9a98",
)


class LoginRequest(BaseModel):
    """Modelo para solicitud de login."""
    username: str
    password: str


class LoginResponse(BaseModel):
    """Modelo para respuesta de login."""
    ok: bool
    estudiante: dict[str, Any] | None = None
    token: str | None = None
    error: str | None = None


class VerificarDocenteRequest(BaseModel):
    """Modelo para solicitud de verificación de contraseña de docente."""
    password: str


class VerificarDocenteResponse(BaseModel):
    """Modelo para respuesta de verificación de docente."""
    ok: bool
    token: str | None = None
    error: str | None = None


def hash_password(password: str) -> str:
    """Genera hash SHA-256 de una contraseña."""
    return hashlib.sha256(password.encode()).hexdigest()


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest) -> LoginResponse:
    """
    Endpoint para autenticación de estudiantes.

    Args:
        request: Credenciales del estudiante (username y password).

    Returns:
        LoginResponse: Resultado del login con datos del estudiante o error.
    """
    with database.get_db_context() as conn:
        cursor = conn.cursor()

        # Buscar estudiante por username
        cursor.execute(
            "SELECT id, cedula, nombre, apellido1, apellido2, seccion, username, password_hash "
            "FROM estudiantes WHERE username = ?",
            (request.username,)
        )
        row = cursor.fetchone()

        if row is None:
            return LoginResponse(ok=False, error="Credenciales inválidas")

        # Verificar password hasheado
        password_hash = hash_password(request.password)
        if not hmac.compare_digest(password_hash, row["password_hash"]):
            return LoginResponse(ok=False, error="Credenciales inválidas")

        # Login exitoso - devolver datos del estudiante (sin password)
        estudiante = {
            "id": row["id"],
            "nombre": row["nombre"],
            "apellido1": row["apellido1"],
            "apellido2": row["apellido2"],
            "username": row["username"],
            "seccion": row["seccion"],
        }
        token = security.create_token(
            str(row["id"]), security.ROLE_ESTUDIANTE, security.TOKEN_TTL_ESTUDIANTE
        )
        return LoginResponse(ok=True, estudiante=estudiante, token=token)


@router.post("/verificar-docente", response_model=VerificarDocenteResponse)
async def verificar_docente(request: VerificarDocenteRequest) -> VerificarDocenteResponse:
    """
    Endpoint para verificar la contraseña del docente.

    Args:
        request: Contraseña del docente en texto plano.

    Returns:
        VerificarDocenteResponse: Resultado de la verificación.
    """
    hash_input = hashlib.sha256(request.password.encode()).hexdigest()
    if hmac.compare_digest(hash_input, TEACHER_PASSWORD_HASH):
        token = security.create_token("docente", security.ROLE_DOCENTE, security.TOKEN_TTL_DOCENTE)
        return VerificarDocenteResponse(ok=True, token=token)
    return VerificarDocenteResponse(ok=False, error="Contraseña incorrecta")
