"""
Intentos routes - Consulta de resultados (solo docente).
"""
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from backend import barajado, database, security
from backend.routes.examenes import _get_examen

router = APIRouter(
    prefix="/api/docente", tags=["intentos"], dependencies=[Depends(security.require_docente)]
)


@router.get("/intentos")
def listar_intentos() -> dict[str, Any]:
    """Lista todos los intentos con el estudiante y la nota (los no enviados llevan fecha_fin nula)."""
    with database.get_db_context() as conn:
        rows = conn.execute(
            "SELECT i.id, i.codigo_examen, i.puntuacion, i.total, i.fecha_inicio, i.fecha_fin, i.incidencias, "
            "e.nombre, e.apellido1, e.apellido2, e.seccion "
            "FROM intentos i JOIN estudiantes e ON e.id = i.estudiante_id "
            "ORDER BY i.fecha_inicio DESC"
        ).fetchall()
    return {"ok": True, "intentos": [dict(r) for r in rows]}


@router.get("/intentos/{intento_id}")
def detalle_intento(intento_id: int) -> dict[str, Any]:
    """Detalle de un intento con las respuestas del estudiante y las correctas."""
    with database.get_db_context() as conn:
        row = conn.execute(
            "SELECT i.*, e.nombre, e.apellido1, e.apellido2, e.seccion "
            "FROM intentos i JOIN estudiantes e ON e.id = i.estudiante_id WHERE i.id = ?",
            (intento_id,),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Intento no encontrado")

    _, examen = _get_examen(row["codigo_examen"])
    return {
        "ok": True,
        "intento": {
            "id": row["id"],
            "codigo_examen": row["codigo_examen"],
            "puntuacion": row["puntuacion"],
            "total": row["total"],
            "fecha_inicio": row["fecha_inicio"],
            "fecha_fin": row["fecha_fin"],
            "incidencias": row["incidencias"],
            "estudiante": {
                "nombre": row["nombre"],
                "apellido1": row["apellido1"],
                "apellido2": row["apellido2"],
                "seccion": row["seccion"],
            },
            "respuestas": json.loads(row["respuestas_json"]),
            # Letras tal como las vio el estudiante (con el barajado de su intento)
            "respuestas_correctas": {
                str(p["numero"]): barajado.letra_correcta_mostrada(p)
                for p in barajado.barajar(examen["preguntas"], row["semilla"])
            },
        },
    }
