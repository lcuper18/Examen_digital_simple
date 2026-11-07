"""
Asistencia routes - Control de asistencia por lección y cálculo del porcentaje de asistencia (solo docente).

Regla (Reglamento de Evaluación, art. 37): el porcentaje de ausencias injustificadas sobre el total de
lecciones impartidas en el período define los puntos de asistencia. Cada llegada tardía injustificada
menor de diez minutos cuenta como media ausencia; mayor de diez minutos, como una ausencia.
"""
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from backend import bitacora, database, security
from backend.routes.notas import _materia
from backend.routes.reportes import _xlsx

router = APIRouter(
    prefix="/api/docente/asistencia", tags=["asistencia"], dependencies=[Depends(security.require_docente)]
)

ESTADOS = {
    "P": "Presente",
    "A": "Ausente",
    "T": "Tardía (menos de 10 min)",
    "TM": "Tardía (más de 10 min)",
    "AJ": "Ausencia justificada",
    "TJ": "Tardía justificada",
}

# (límite exclusivo del % de ausencias injustificadas, puntos de los 5 de asistencia)
TABLA_ASISTENCIA = [(10, 5), (20, 4), (30, 3), (40, 2), (50, 1)]
PUNTOS_MAXIMOS = 5


def puntos_asistencia(porcentaje_ausencias: float) -> int:
    for limite, puntos in TABLA_ASISTENCIA:
        if porcentaje_ausencias < limite:
            return puntos
    return 0


def _ausencias_injustificadas(estado: str, lecciones: int) -> float:
    return {"A": float(lecciones), "TM": 1.0, "T": 0.5}.get(estado, 0.0)


def _resumen(conn, materia) -> dict[str, Any]:
    sesiones = conn.execute(
        "SELECT id, fecha, lecciones, tema FROM sesiones WHERE materia_id = ? ORDER BY fecha", (materia["id"],)
    ).fetchall()
    lecciones = {s["id"]: s["lecciones"] for s in sesiones}
    fechas = {s["id"]: s["fecha"] for s in sesiones}
    total = sum(lecciones.values())
    estudiantes = conn.execute(
        "SELECT id, nombre, apellido1, apellido2 FROM estudiantes WHERE seccion = ? "
        "ORDER BY apellido1, apellido2, nombre", (materia["seccion"],)
    ).fetchall()
    por_estudiante: dict[int, dict[str, Any]] = {
        e["id"]: {
            "estudiante_id": e["id"], "nombre": e["nombre"], "apellido1": e["apellido1"], "apellido2": e["apellido2"],
            "ausencias": 0, "tardias": 0, "justificadas": 0, "injustificadas": 0.0, "detalle": [],
        } for e in estudiantes
    }
    registros = conn.execute(
        "SELECT a.* FROM asistencia a JOIN sesiones s ON s.id = a.sesion_id WHERE s.materia_id = ?", (materia["id"],)
    ).fetchall()
    for r in registros:
        e = por_estudiante.get(r["estudiante_id"])
        if e is None or r["estado"] == "P":
            continue
        e["injustificadas"] += _ausencias_injustificadas(r["estado"], lecciones[r["sesion_id"]])
        if r["estado"] in ("A", "AJ"):
            e["ausencias"] += lecciones[r["sesion_id"]]
        else:
            e["tardias"] += 1
        if r["estado"] in ("AJ", "TJ"):
            e["justificadas"] += 1
        e["detalle"].append({"fecha": fechas[r["sesion_id"]], "estado": r["estado"], "observacion": r["observacion"]})
    filas = list(por_estudiante.values())
    for e in filas:
        e["detalle"].sort(key=lambda d: d["fecha"])
        e["porcentaje_ausencias"] = round(e["injustificadas"] / total * 100, 1) if total else 0.0
        e["puntos"] = puntos_asistencia(e["porcentaje_ausencias"]) if total else None
    return {
        "ok": True, "materia": dict(materia), "lecciones_totales": total, "sesiones": [dict(s) for s in sesiones],
        "estudiantes": filas, "estados": ESTADOS, "puntos_maximos": PUNTOS_MAXIMOS,
    }


def _aplicar_a_notas(conn, materia) -> None:
    """Escribe los puntos de asistencia en el componente `asistencia` (0-100) de las notas."""
    resumen = _resumen(conn, materia)
    if not resumen["lecciones_totales"]:
        return
    for e in resumen["estudiantes"]:
        conn.execute(
            "INSERT INTO notas (estudiante_id, materia_id, asistencia) VALUES (?, ?, ?) "
            "ON CONFLICT (estudiante_id, materia_id) DO UPDATE SET asistencia = excluded.asistencia",
            (e["estudiante_id"], materia["id"], e["puntos"] / PUNTOS_MAXIMOS * 100),
        )


@router.get("/resumen")
def resumen_asistencia(materia_id: int) -> dict[str, Any]:
    with database.get_db_context() as conn:
        return _resumen(conn, _materia(conn, materia_id))


@router.get("/sesion")
def obtener_sesion(materia_id: int, fecha: str) -> dict[str, Any]:
    """Lista de la fecha: lo guardado, o a todos presentes si la sesión aún no existe."""
    try:
        date.fromisoformat(fecha)
    except ValueError:
        raise HTTPException(status_code=400, detail="Fecha no válida")
    with database.get_db_context() as conn:
        materia = _materia(conn, materia_id)
        sesion = conn.execute(
            "SELECT * FROM sesiones WHERE materia_id = ? AND fecha = ?", (materia_id, fecha)).fetchone()
        guardados = {
            r["estudiante_id"]: r for r in conn.execute(
                "SELECT * FROM asistencia WHERE sesion_id = ?", (sesion["id"],))
        } if sesion else {}
        estudiantes = conn.execute(
            "SELECT id, nombre, apellido1, apellido2 FROM estudiantes WHERE seccion = ? "
            "ORDER BY apellido1, apellido2, nombre", (materia["seccion"],)
        ).fetchall()
    return {
        "ok": True, "existe": sesion is not None,
        "lecciones": sesion["lecciones"] if sesion else 2, "tema": (sesion["tema"] if sesion else "") or "",
        "registros": [
            {
                "estudiante_id": e["id"], "nombre": e["nombre"], "apellido1": e["apellido1"], "apellido2": e["apellido2"],
                "estado": guardados[e["id"]]["estado"] if e["id"] in guardados else "P",
                "observacion": (guardados[e["id"]]["observacion"] if e["id"] in guardados else "") or "",
            } for e in estudiantes
        ],
    }


class Registro(BaseModel):
    estudiante_id: int
    estado: str
    observacion: str = Field(default="", max_length=200)


class GuardarSesion(BaseModel):
    materia_id: int
    fecha: str
    lecciones: int = Field(ge=1, le=12)
    tema: str = Field(default="", max_length=200)
    registros: list[Registro]


@router.put("/sesion")
def guardar_sesion(request: GuardarSesion) -> dict[str, Any]:
    try:
        date.fromisoformat(request.fecha)
    except ValueError:
        raise HTTPException(status_code=400, detail="Fecha no válida")
    if any(r.estado not in ESTADOS for r in request.registros):
        raise HTTPException(status_code=400, detail="Estado de asistencia no válido")
    with database.get_db_context() as conn:
        materia = _materia(conn, request.materia_id)
        validos = {r["id"] for r in conn.execute("SELECT id FROM estudiantes WHERE seccion = ?", (materia["seccion"],))}
        if any(r.estudiante_id not in validos for r in request.registros):
            raise HTTPException(status_code=400, detail=f"Hay estudiantes que no son de la sección {materia['seccion']}")
        conn.execute(
            "INSERT INTO sesiones (materia_id, fecha, lecciones, tema) VALUES (?, ?, ?, ?) "
            "ON CONFLICT (materia_id, fecha) DO UPDATE SET lecciones = excluded.lecciones, tema = excluded.tema",
            (materia["id"], request.fecha, request.lecciones, request.tema.strip()),
        )
        sesion_id = conn.execute(
            "SELECT id FROM sesiones WHERE materia_id = ? AND fecha = ?", (materia["id"], request.fecha)).fetchone()["id"]
        conn.executemany(
            "INSERT INTO asistencia (sesion_id, estudiante_id, estado, observacion) VALUES (?, ?, ?, ?) "
            "ON CONFLICT (sesion_id, estudiante_id) DO UPDATE SET estado = excluded.estado, observacion = excluded.observacion",
            [(sesion_id, r.estudiante_id, r.estado, r.observacion.strip()) for r in request.registros],
        )
        _aplicar_a_notas(conn, materia)
        ausentes = sum(r.estado != "P" for r in request.registros)
        bitacora.registrar(
            conn, "pasar_lista",
            f"{materia['seccion']} · P{materia['periodo']} · {materia['nombre']} · {request.fecha} "
            f"({request.lecciones} lecc., {ausentes} con novedad)",
        )
        conn.commit()
    return {"ok": True, "sesion_id": sesion_id}


@router.delete("/sesion/{sesion_id}")
def eliminar_sesion(sesion_id: int) -> dict[str, Any]:
    with database.get_db_context() as conn:
        sesion = conn.execute("SELECT * FROM sesiones WHERE id = ?", (sesion_id,)).fetchone()
        if sesion is None:
            raise HTTPException(status_code=404, detail="Sesión no encontrada")
        materia = _materia(conn, sesion["materia_id"])
        conn.execute("DELETE FROM asistencia WHERE sesion_id = ?", (sesion_id,))
        conn.execute("DELETE FROM sesiones WHERE id = ?", (sesion_id,))
        _aplicar_a_notas(conn, materia)
        bitacora.registrar(conn, "eliminar_lista", f"{materia['nombre']} · {sesion['fecha']}")
        conn.commit()
    return {"ok": True}


@router.get("/excel")
def excel_asistencia(materia_id: int) -> Response:
    with database.get_db_context() as conn:
        materia = _materia(conn, materia_id)
        d = _resumen(conn, materia)
    nombre = lambda e: f"{e['apellido1']} {e['apellido2'] or ''}, {e['nombre']}".replace("  ", " ").strip()
    return _xlsx(f"asistencia_{materia['seccion']}_P{materia['periodo']}_{materia['id']}.xlsx", {
        "Resumen": [["Estudiante", "Lecciones del período", "Ausencias", "Tardías", "Justificadas",
                     "Ausencias injustificadas (equiv.)", "% ausencias", f"Puntos (de {PUNTOS_MAXIMOS})"]] + [
            [nombre(e), d["lecciones_totales"], e["ausencias"], e["tardias"], e["justificadas"],
             e["injustificadas"], e["porcentaje_ausencias"], "" if e["puntos"] is None else e["puntos"]]
            for e in d["estudiantes"]],
        "Detalle": [["Fecha", "Estudiante", "Estado", "Observación"]] + [
            [x["fecha"], nombre(e), ESTADOS[x["estado"]], x["observacion"] or ""]
            for e in d["estudiantes"] for x in e["detalle"]],
    })
