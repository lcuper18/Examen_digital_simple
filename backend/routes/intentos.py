"""
Intentos routes - Resultados y control de intentos (solo docente).
"""
import csv
import io
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from backend import barajado, bitacora, database, security
from backend.routes.examenes import _get_examen, _now, calificar, cerrar_con_parciales

router = APIRouter(
    prefix="/api/docente", tags=["intentos"], dependencies=[Depends(security.require_docente)]
)

_SELECT_LISTA = (
    "SELECT i.id, i.estudiante_id, i.codigo_examen, i.puntuacion, i.total, i.fecha_inicio, i.fecha_fin, "
    "i.incidencias, i.anulado, i.sospechoso, i.nota_docente, i.minutos_extra, "
    "e.nombre, e.apellido1, e.apellido2, e.seccion "
    "FROM intentos i JOIN estudiantes e ON e.id = i.estudiante_id "
)


def _nombre(fila) -> str:
    return f"{fila['nombre']} {fila['apellido1']} {fila['apellido2'] or ''}".strip()


def _intento(conn, intento_id: int):
    fila = conn.execute(_SELECT_LISTA + "WHERE i.id = ?", (intento_id,)).fetchone()
    if fila is None:
        raise HTTPException(status_code=404, detail="Intento no encontrado")
    return fila


@router.get("/intentos")
def listar_intentos() -> dict[str, Any]:
    """Lista todos los intentos con el estudiante y la nota (los no enviados llevan fecha_fin nula)."""
    with database.get_db_context() as conn:
        rows = conn.execute(_SELECT_LISTA + "ORDER BY i.fecha_inicio DESC").fetchall()
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
    respuestas = json.loads(row["respuestas_json"] if row["fecha_fin"] else (row["respuestas_parciales_json"] or "{}"))
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
            "anulado": bool(row["anulado"]),
            "sospechoso": bool(row["sospechoso"]),
            "nota_docente": row["nota_docente"],
            "minutos_extra": row["minutos_extra"],
            "estudiante": {
                "nombre": row["nombre"],
                "apellido1": row["apellido1"],
                "apellido2": row["apellido2"],
                "seccion": row["seccion"],
            },
            "respuestas": respuestas,
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
        fila = _intento(conn, intento_id)
        conn.execute("DELETE FROM intentos WHERE id = ?", (intento_id,))
        bitacora.registrar(conn, "reiniciar_intento", f"{_nombre(fila)} · {fila['codigo_examen']}")
        conn.commit()
    return {"ok": True}


class TiempoExtra(BaseModel):
    minutos: int = Field(ge=1, le=240)


@router.post("/intentos/{intento_id}/tiempo-extra")
def tiempo_extra(intento_id: int, request: TiempoExtra) -> dict[str, Any]:
    """Suma minutos al tiempo del intento (el estudiante lo recibe en su siguiente guardado)."""
    with database.get_db_context() as conn:
        fila = _intento(conn, intento_id)
        if fila["fecha_fin"] is not None or fila["anulado"]:
            raise HTTPException(status_code=409, detail="Solo se puede dar tiempo extra a un intento abierto")
        conn.execute(
            "UPDATE intentos SET minutos_extra = minutos_extra + ? WHERE id = ?", (request.minutos, intento_id)
        )
        bitacora.registrar(
            conn, "tiempo_extra", f"{_nombre(fila)} · {fila['codigo_examen']} · +{request.minutos} min"
        )
        conn.commit()
    return {"ok": True, "minutos_extra": fila["minutos_extra"] + request.minutos}


class Anular(BaseModel):
    anulado: bool = True
    motivo: str = ""


@router.post("/intentos/{intento_id}/anular")
def anular_intento(intento_id: int, request: Anular) -> dict[str, Any]:
    """Anula (o restaura) un intento: deja de contar en notas y reportes."""
    with database.get_db_context() as conn:
        fila = _intento(conn, intento_id)
        conn.execute("UPDATE intentos SET anulado = ? WHERE id = ?", (int(request.anulado), intento_id))
        bitacora.registrar(
            conn, "anular_intento" if request.anulado else "restaurar_intento",
            f"{_nombre(fila)} · {fila['codigo_examen']}" + (f" · {request.motivo}" if request.motivo else ""),
        )
        conn.commit()
    return {"ok": True}


class Sospechoso(BaseModel):
    sospechoso: bool = True
    nota: str = ""


@router.post("/intentos/{intento_id}/sospechoso")
def marcar_sospechoso(intento_id: int, request: Sospechoso) -> dict[str, Any]:
    with database.get_db_context() as conn:
        fila = _intento(conn, intento_id)
        conn.execute(
            "UPDATE intentos SET sospechoso = ?, nota_docente = ? WHERE id = ?",
            (int(request.sospechoso), request.nota or None, intento_id),
        )
        bitacora.registrar(
            conn, "marcar_sospechoso" if request.sospechoso else "quitar_sospechoso",
            f"{_nombre(fila)} · {fila['codigo_examen']}" + (f" · {request.nota}" if request.nota else ""),
        )
        conn.commit()
    return {"ok": True}


@router.post("/intentos/{intento_id}/cerrar")
def cerrar_intento(intento_id: int) -> dict[str, Any]:
    """Cierra un intento abierto y lo califica con las respuestas guardadas hasta el momento."""
    with database.get_db_context() as conn:
        fila = conn.execute(
            "SELECT i.*, e.nombre, e.apellido1, e.apellido2 FROM intentos i "
            "JOIN estudiantes e ON e.id = i.estudiante_id WHERE i.id = ?", (intento_id,)
        ).fetchone()
        if fila is None:
            raise HTTPException(status_code=404, detail="Intento no encontrado")
        if fila["fecha_fin"] is not None:
            raise HTTPException(status_code=409, detail="El intento ya está cerrado")
        _, examen = _get_examen(fila["codigo_examen"])
        puntuacion = cerrar_con_parciales(conn, fila, examen["preguntas"])
        bitacora.registrar(
            conn, "cerrar_intento",
            f"{_nombre(fila)} · {fila['codigo_examen']} · {puntuacion}/{len(examen['preguntas'])}",
        )
        conn.commit()
    return {"ok": True, "puntuacion": puntuacion, "total": len(examen["preguntas"])}


@router.get("/intentos-exportar")
def exportar_intentos() -> Response:
    """Todos los intentos en CSV."""
    datos = listar_intentos()["intentos"]
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Apellido 1", "Apellido 2", "Nombre", "Sección", "Examen", "Puntuación", "Total",
                     "Nota (0-100)", "Inicio", "Fin", "Salidas de pestaña", "Estado", "Sospechoso", "Nota del docente"])
    for i in datos:
        enviado = i["fecha_fin"] is not None
        estado = "anulado" if i["anulado"] else ("enviado" if enviado else "sin enviar")
        writer.writerow([
            i["apellido1"], i["apellido2"], i["nombre"], i["seccion"], i["codigo_examen"],
            i["puntuacion"] if enviado else "", i["total"],
            round(i["puntuacion"] / i["total"] * 100, 1) if enviado and i["total"] else "",
            i["fecha_inicio"], i["fecha_fin"] or "", i["incidencias"], estado,
            "sí" if i["sospechoso"] else "", i["nota_docente"] or "",
        ])
    return Response(
        content="﻿" + buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="intentos.csv"'},
    )
