"""
Auth routes - Login and teacher password verification.
"""
import os
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel

from backend import database, ratelimit, security

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


@router.post("/login", response_model=LoginResponse)
def login(request: LoginRequest, http: Request) -> LoginResponse:
    """
    Endpoint para autenticación de estudiantes.

    Args:
        request: Credenciales del estudiante (username y password).

    Returns:
        LoginResponse: Resultado del login con datos del estudiante o error.
    """
    ip = http.client.host if http.client else "?"
    clave = f"login:{ip}:{request.username.lower()}"
    ratelimit.verificar(clave)

    with database.get_db_context() as conn:
        cursor = conn.cursor()

        # Buscar estudiante por username
        cursor.execute(
            "SELECT id, cedula, nombre, apellido1, apellido2, seccion, username, password_hash "
            "FROM estudiantes WHERE username = ?",
            (request.username,)
        )
        row = cursor.fetchone()

        if row is None or not database.verify_password(request.password, row["password_hash"]):
            ratelimit.registrar_fallo(clave)
            return LoginResponse(ok=False, error="Credenciales inválidas")

        ratelimit.limpiar(clave)

        # Migrar hashes SHA-256 antiguos a bcrypt de forma transparente
        if database.is_legacy_hash(row["password_hash"]):
            cursor.execute(
                "UPDATE estudiantes SET password_hash = ? WHERE id = ?",
                (database.hash_password(request.password), row["id"]),
            )
            conn.commit()

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
def verificar_docente(request: VerificarDocenteRequest, http: Request) -> VerificarDocenteResponse:
    """
    Endpoint para verificar la contraseña del docente.

    Args:
        request: Contraseña del docente en texto plano.

    Returns:
        VerificarDocenteResponse: Resultado de la verificación.
    """
    clave = f"docente:{http.client.host if http.client else '?'}"
    ratelimit.verificar(clave)
    if database.verify_password(request.password, TEACHER_PASSWORD_HASH):
        ratelimit.limpiar(clave)
        token = security.create_token("docente", security.ROLE_DOCENTE, security.TOKEN_TTL_DOCENTE)
        return VerificarDocenteResponse(ok=True, token=token)
    ratelimit.registrar_fallo(clave, maximo=10)
    return VerificarDocenteResponse(ok=False, error="Contraseña incorrecta")
