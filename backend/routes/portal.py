"""
Portal routes - "Mis notas": cada estudiante ve solo lo suyo y solo lo que el docente publicó.
"""
from typing import Any

from fastapi import APIRouter, Depends

from backend import database, security
from backend.routes.informes import _encabezado, _nombre_acta, agregar_materias
from backend.routes.notas import nota_minima

router = APIRouter(prefix="/api", tags=["portal"])


@router.get("/mis-notas")
def mis_notas(estudiante_id: int = Depends(security.estudiante_actual)) -> dict[str, Any]:
    """
    Notas por componente, asistencia y actividades (con la observación para el estudiante, nunca la nota
    interna) de las materias publicadas de la sección del estudiante autenticado.
    """
    with database.get_db_context() as conn:
        est = conn.execute(
            "SELECT id, cedula, nombre, apellido1, apellido2, seccion FROM estudiantes WHERE id = ?",
            (estudiante_id,)).fetchone()
        materias = conn.execute(
            "SELECT m.* FROM materias m JOIN publicaciones p ON p.materia_id = m.id "
            "WHERE m.seccion = ? AND p.publicado = 1 ORDER BY m.periodo, m.nombre", (est["seccion"],)).fetchall()
        informes = {estudiante_id: {"estudiante": {"id": estudiante_id, "nombre": _nombre_acta(est)}, "materias": []}}
        minima = nota_minima(conn)
        agregar_materias(conn, materias, informes, minima)
        encabezado = _encabezado(conn, materias[0]) if materias else database.leer_ajustes(conn)
    return {
        "ok": True, "nombre": informes[estudiante_id]["estudiante"]["nombre"], "seccion": est["seccion"],
        "institucion": encabezado["institucion"], "curso_lectivo": encabezado["curso_lectivo"],
        "nota_minima": minima, "materias": informes[estudiante_id]["materias"],
    }
