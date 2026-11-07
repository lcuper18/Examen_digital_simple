"""
Informes routes - Acta de calificaciones, informe para encargados y registro de notas (solo docente).
"""
import csv
import io
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response

from backend import database, security
from backend.routes.actividades import ESTADOS as ESTADOS_ACTIVIDAD
from backend.routes.asistencia import _resumen
from backend.routes.notas import COMPONENTES, ETIQUETAS, _filas, _materia, nota_minima, pesos_de
from backend.routes.reportes import _xlsx

router = APIRouter(
    prefix="/api/docente/informes", tags=["informes"], dependencies=[Depends(security.require_docente)]
)

NIVELES = {10: "DÉCIMO AÑO", 11: "UNDÉCIMO AÑO", 12: "DUODÉCIMO AÑO"}


def nivel_y_seccion(seccion: str) -> tuple[str, str]:
    """'11-2' -> ('UNDÉCIMO AÑO', 'UNDÉCIMO AÑO-2'). Si el formato es otro, se devuelve tal cual."""
    try:
        grado, grupo = seccion.split("-", 1)
        nivel = NIVELES[int(grado)]
        return nivel, f"{nivel}-{grupo}"
    except (ValueError, KeyError):
        return seccion, seccion


def redondear_entero(valor: float) -> int:
    """Redondeo escolar (0.5 sube), no el 'bancario' de round()."""
    return int(valor + 0.5)


def _nombre_acta(f) -> str:
    return f"{f['apellido1']} {f['apellido2'] or ''} {f['nombre']}".replace("  ", " ").strip().upper()


def _cedulas(conn, seccion: str) -> dict[int, str]:
    return {r["id"]: r["cedula"].replace("-", "") for r in conn.execute(
        "SELECT id, cedula FROM estudiantes WHERE seccion = ?", (seccion,))}


def _encabezado(conn, materia) -> dict[str, Any]:
    a = database.leer_ajustes(conn)
    nivel, seccion = nivel_y_seccion(materia["seccion"])
    return {
        "direccion_regional": a["direccion_regional"], "circuito": a["circuito"], "institucion": a["institucion"],
        "curso_lectivo": a["curso_lectivo"], "docente": a["docente"], "asignatura": materia["nombre"],
        "nivel": nivel, "seccion": seccion, "periodo": materia["periodo"],
    }


# ---------- Acta de calificaciones ----------

def _datos_acta(materia_id: int) -> dict[str, Any]:
    with database.get_db_context() as conn:
        materia = _materia(conn, materia_id)
        cedulas = _cedulas(conn, materia["seccion"])
        filas = _filas(conn, materia)
        encabezado = _encabezado(conn, materia)
        minima = nota_minima(conn)
    return {
        "ok": True, "encabezado": encabezado, "nota_minima": minima,
        "estudiantes": [{
            "estudiante_id": f["estudiante_id"], "cedula": cedulas[f["estudiante_id"]], "nombre": _nombre_acta(f),
            "nota": redondear_entero(f["nota_final"]), "nota_decimal": f["nota_final"], "completa": f["completa"],
        } for f in filas],
    }


@router.get("/acta")
def acta(materia_id: int) -> dict[str, Any]:
    return _datos_acta(materia_id)


@router.get("/acta/excel")
def acta_excel(materia_id: int) -> Response:
    d = _datos_acta(materia_id)
    e = d["encabezado"]
    return _xlsx(f"acta_P{e['periodo']}_{materia_id}.xlsx", {
        "Acta": [
            ["Dirección Regional de Educación", e["direccion_regional"]], ["Circuito escolar", e["circuito"]],
            ["Centro educativo", e["institucion"]], ["Curso lectivo", e["curso_lectivo"]], ["Docente", e["docente"]],
            ["Asignatura", e["asignatura"]], ["Nivel", e["nivel"]], ["Sección", e["seccion"]], ["Período", f"{e['periodo']}° período"],
            [],
            ["Id", "Nombre", "Nota"],
            *[[x["cedula"], x["nombre"], x["nota"]] for x in d["estudiantes"]],
        ],
    })


# ---------- Registro de notas (formato de las hojas del docente) ----------

def _datos_registro(materia_id: int) -> tuple[Any, list[list[Any]]]:
    with database.get_db_context() as conn:
        materia = _materia(conn, materia_id)
        cedulas = _cedulas(conn, materia["seccion"])
        pesos = pesos_de(conn, materia_id)
        filas = _filas(conn, materia)
    salida = []
    for f in filas:
        puntos = [None if f[c] is None else round(f[c] * pesos[c] / 100, 2) for c in COMPONENTES]
        salida.append([cedulas[f["estudiante_id"]], _nombre_acta(f), *puntos, f["nota_final"]])
    return materia, salida


@router.get("/registro")
def registro_csv(materia_id: int) -> Response:
    """CSV con ';' y coma decimal, igual a `Notas/Periodo0X/<sección>/*.csv` (puntos por componente)."""
    materia, filas = _datos_registro(materia_id)
    buffer = io.StringIO()
    escritor = csv.writer(buffer, delimiter=";", lineterminator="\n")
    escritor.writerow(["Id", "Nombre", "Trabajo cotidiano", "Tareas", "Prueba1", "Prueba2", "Proyecto", "Asistencia"])
    for f in filas:
        escritor.writerow([f[0], f[1], *["" if v is None else f"{v:g}".replace(".", ",") for v in f[2:-1]]])
    return Response(
        content="﻿" + buffer.getvalue(), media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="registro_{materia["seccion"]}_P{materia["periodo"]}_{materia_id}.csv"'},
    )


@router.get("/registro/excel")
def registro_excel(materia_id: int) -> Response:
    materia, filas = _datos_registro(materia_id)
    return _xlsx(f"registro_{materia['seccion']}_P{materia['periodo']}_{materia_id}.xlsx", {
        "Notas": [["Id", "Nombre", *[ETIQUETAS[c] for c in COMPONENTES], "Nota"]] + filas,
    })


# ---------- Informe para encargados ----------

@router.get("/encargados")
def informe_encargados(seccion: str, periodo: int, estudiante_id: int | None = None) -> dict[str, Any]:
    """
    Por estudiante y materia del periodo: componentes en puntos, nota final, actividades (sin la nota interna)
    y resumen de asistencia. Con `estudiante_id` solo trae a ese estudiante.
    """
    with database.get_db_context() as conn:
        materias = conn.execute(
            "SELECT * FROM materias WHERE seccion = ? AND periodo = ? ORDER BY nombre", (seccion, periodo)).fetchall()
        if not materias:
            raise HTTPException(status_code=404, detail="No hay materias para esa sección y periodo")
        estudiantes = {
            r["id"]: r for r in conn.execute(
                "SELECT id, cedula, nombre, apellido1, apellido2 FROM estudiantes "
                "WHERE seccion = ? AND activo = 1 ORDER BY apellido1, apellido2, nombre", (seccion,))
        }
        if estudiante_id is not None:
            if estudiante_id not in estudiantes:
                raise HTTPException(status_code=404, detail="Estudiante no encontrado en esa sección")
            estudiantes = {estudiante_id: estudiantes[estudiante_id]}
        minima = nota_minima(conn)
        institucion = _encabezado(conn, materias[0])
        informes: dict[int, dict[str, Any]] = {
            eid: {"estudiante": {"id": eid, "cedula": e["cedula"], "nombre": _nombre_acta(e)}, "materias": []}
            for eid, e in estudiantes.items()
        }
        for m in materias:
            pesos = pesos_de(conn, m["id"])
            filas = {f["estudiante_id"]: f for f in _filas(conn, m)}
            asist = _resumen(conn, m)
            asist_por = {e["estudiante_id"]: e for e in asist["estudiantes"]}
            actividades = conn.execute("SELECT * FROM actividades WHERE materia_id = ? ORDER BY componente, id", (m["id"],)).fetchall()
            cals = {
                (c["actividad_id"], c["estudiante_id"]): c for c in conn.execute(
                    "SELECT c.* FROM calificaciones c JOIN actividades a ON a.id = c.actividad_id WHERE a.materia_id = ?",
                    (m["id"],))
            }
            for eid in estudiantes:
                f = filas[eid]
                a = asist_por.get(eid)
                informes[eid]["materias"].append({
                    "materia": m["nombre"], "periodo": m["periodo"],
                    "componentes": [{
                        "clave": c, "etiqueta": ETIQUETAS[c], "peso": pesos[c],
                        "puntos": None if f[c] is None else round(f[c] * pesos[c] / 100, 2),
                    } for c in COMPONENTES],
                    "nota_final": f["nota_final"], "completa": f["completa"], "aprobado": f["nota_final"] >= minima,
                    "actividades": [{
                        "nombre": act["nombre"], "componente": ETIQUETAS[act["componente"]],
                        "estado": c["estado"], "estado_texto": ESTADOS_ACTIVIDAD[c["estado"]],
                        "puntos": c["puntos"], "puntos_max": act["puntos_max"], "observacion": c["observacion"] or "",
                    } for act in actividades if (c := cals.get((act["id"], eid))) and c["estado"] != "revision"],
                    "asistencia": None if not asist["lecciones_totales"] else {
                        "lecciones": asist["lecciones_totales"], "ausencias": a["ausencias"], "tardias": a["tardias"],
                        "justificadas": a["justificadas"], "injustificadas": a["injustificadas"],
                        "porcentaje": a["porcentaje_ausencias"], "puntos": a["puntos"], "maximo": asist["puntos_maximos"],
                        "detalle": a["detalle"],
                    },
                })
    return {
        "ok": True, "encabezado": institucion, "nota_minima": minima, "seccion": seccion, "periodo": periodo,
        "informes": list(informes.values()),
    }
