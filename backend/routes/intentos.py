"""
Intentos routes - Consulta de resultados (solo docente).
"""
import csv
import io
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response

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
            "preguntas": [
                {k: p[k] for k in ("numero", "tema", "pregunta", "opciones")}
                for p in barajado.barajar(examen["preguntas"], row["semilla"])
            ],
            # Letras tal como las vio el estudiante (con el barajado de su intento)
            "respuestas_correctas": {
                str(p["numero"]): barajado.letra_correcta_mostrada(p)
                for p in barajado.barajar(examen["preguntas"], row["semilla"])
            },
        },
    }


@router.delete("/intentos/{intento_id}")
def reiniciar_intento(intento_id: int) -> dict[str, Any]:
    """Elimina un intento para que el estudiante pueda volver a presentar el examen."""
    with database.get_db_context() as conn:
        cursor = conn.execute("DELETE FROM intentos WHERE id = ?", (intento_id,))
        conn.commit()
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Intento no encontrado")
    return {"ok": True}


@router.get("/intentos-exportar")
def exportar_intentos() -> Response:
    """Todos los intentos en CSV."""
    datos = listar_intentos()["intentos"]
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Apellido 1", "Apellido 2", "Nombre", "Sección", "Examen", "Puntuación",
                     "Total", "Nota (0-100)", "Inicio", "Fin", "Salidas de pestaña"])
    for i in datos:
        enviado = i["fecha_fin"] is not None
        writer.writerow([
            i["apellido1"], i["apellido2"], i["nombre"], i["seccion"], i["codigo_examen"],
            i["puntuacion"] if enviado else "", i["total"],
            round(i["puntuacion"] / i["total"] * 100, 1) if enviado and i["total"] else "",
            i["fecha_inicio"], i["fecha_fin"] or "", i["incidencias"],
        ])
    return Response(
        content="\ufeff" + buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="intentos.csv"'},
    )
