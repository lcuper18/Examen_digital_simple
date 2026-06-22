"""
Intentos routes - Create exam attempts.
"""
import json
from typing import Any, List

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend import database

router = APIRouter(prefix="/api", tags=["intentos"])


class IntentoRequest(BaseModel):
    """Modelo para registro de intento de examen."""
    estudiante_id: int
    codigo_examen: str
    respuestas: List[Any] = []
    puntuacion: int
    total: int
    fecha_inicio: str | None = None
    fecha_fin: str | None = None


@router.post("/intentos")
async def crear_intento(request: IntentoRequest) -> JSONResponse:
    """
    Registra un intento de examen en la base de datos.

    Args:
        request: Datos del intento (estudiante_id, codigo_examen, respuestas, etc.).

    Returns:
        JSONResponse: Confirmación con el ID del intento creado.
    """
    with database.get_db_context() as conn:
        cursor = conn.cursor()

        # Verificar que el estudiante existe
        cursor.execute("SELECT id FROM estudiantes WHERE id = ?", (request.estudiante_id,))
        if cursor.fetchone() is None:
            raise HTTPException(
                status_code=404,
                detail=f"Estudiante con ID {request.estudiante_id} no encontrado"
            )

        # Insertar intento
        respuestas_json = json.dumps(request.__dict__.get('respuestas', []), ensure_ascii=False)
        cursor.execute(
            """
            INSERT INTO intentos
            (estudiante_id, codigo_examen, respuestas_json, puntuacion, total, fecha_inicio, fecha_fin)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                request.estudiante_id,
                request.codigo_examen,
                respuestas_json,
                request.puntuacion,
                request.total,
                request.fecha_inicio,
                request.fecha_fin,
            )
        )
        conn.commit()

        intento_id = cursor.lastrowid

    return JSONResponse(content={"ok": True, "id": intento_id})
