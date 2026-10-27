"""
Bitácora routes - Consulta del registro de acciones del docente.
"""
from typing import Any

from fastapi import APIRouter, Depends

from backend import database, security

router = APIRouter(
    prefix="/api/docente", tags=["bitacora"], dependencies=[Depends(security.require_docente)]
)


@router.get("/bitacora")
def listar_bitacora(limite: int = 200) -> dict[str, Any]:
    with database.get_db_context() as conn:
        filas = conn.execute(
            "SELECT id, fecha, accion, detalle FROM bitacora ORDER BY id DESC LIMIT ?",
            (min(max(limite, 1), 1000),),
        ).fetchall()
    return {"ok": True, "entradas": [dict(f) for f in filas]}


@router.get("/resumen")
def resumen() -> dict[str, Any]:
    """Datos del tablero: totales, alertas que requieren atención y actividad reciente."""
    from backend import ratelimit
    from backend.routes.examenes import GRACE_SECONDS, _remaining_seconds, load_codigos, minutos_totales

    codigos = load_codigos()
    with database.get_db_context() as conn:
        est = conn.execute(
            "SELECT COUNT(*) AS total, SUM(activo) AS activos, SUM(debe_cambiar_password) AS temporales FROM estudiantes"
        ).fetchone()
        secciones = [dict(r) for r in conn.execute(
            "SELECT seccion, COUNT(*) AS estudiantes FROM estudiantes WHERE activo = 1 GROUP BY seccion ORDER BY seccion")]
        stats = conn.execute(
            "SELECT COALESCE(SUM(fecha_fin IS NOT NULL AND anulado = 0), 0) AS enviados, "
            "COALESCE(SUM(fecha_fin IS NULL AND anulado = 0), 0) AS en_curso, COALESCE(SUM(anulado), 0) AS anulados, "
            "COALESCE(SUM(sospechoso), 0) AS sospechosos, "
            "AVG(CASE WHEN fecha_fin IS NOT NULL AND anulado = 0 AND total > 0 THEN puntuacion * 100.0 / total END) AS promedio "
            "FROM intentos"
        ).fetchone()
        abiertos = conn.execute(
            "SELECT i.id, i.codigo_examen, i.fecha_inicio, i.minutos_extra, i.incidencias, "
            "e.nombre, e.apellido1, e.apellido2, e.seccion "
            "FROM intentos i JOIN estudiantes e ON e.id = i.estudiante_id "
            "WHERE i.fecha_fin IS NULL AND i.anulado = 0 ORDER BY i.fecha_inicio"
        ).fetchall()
        deshabilitados = conn.execute("SELECT COUNT(*) FROM examenes_config WHERE habilitado = 0").fetchone()[0]
        usernames = [r["username"] for r in conn.execute("SELECT username FROM estudiantes")]
        reciente = [dict(r) for r in conn.execute(
            "SELECT fecha, accion, detalle FROM bitacora ORDER BY id DESC LIMIT 6")]

    en_curso, alertas = [], []
    for a in abiertos:
        info = codigos.get(a["codigo_examen"], {})
        restante = _remaining_seconds(a["fecha_inicio"], minutos_totales(info, a)) if info else 0
        nombre = f"{a['nombre']} {a['apellido1']}"
        en_curso.append({
            "id": a["id"], "estudiante": nombre, "seccion": a["seccion"], "codigo": a["codigo_examen"],
            "minutos_restantes": max(restante // 60, 0), "incidencias": a["incidencias"], "vencido": restante <= -GRACE_SECONDS,
        })
        if restante <= -GRACE_SECONDS:
            alertas.append({"tipo": "vencido", "texto": f"{nombre} ({a['codigo_examen']}) no envió y se agotó su tiempo", "ir": "resultados"})
        elif a["incidencias"] >= 3:
            alertas.append({"tipo": "salidas", "texto": f"{nombre} salió {a['incidencias']} veces de la pestaña en {a['codigo_examen']}", "ir": "resultados"})
    bloqueados = [u for u in usernames if ratelimit.bloqueada_con_sufijo(f":{u.lower()}")]
    if bloqueados:
        alertas.append({"tipo": "bloqueados", "texto": f"{len(bloqueados)} estudiante(s) con el login bloqueado por intentos fallidos", "ir": "estudiantes"})
    if est["temporales"]:
        alertas.append({"tipo": "temporales", "texto": f"{est['temporales']} estudiante(s) aún no han cambiado su clave temporal", "ir": "estudiantes"})
    if stats["sospechosos"]:
        alertas.append({"tipo": "sospechosos", "texto": f"{stats['sospechosos']} intento(s) marcado(s) como sospechoso", "ir": "resultados"})

    return {
        "ok": True,
        "estudiantes": {"total": est["total"], "activos": est["activos"] or 0, "secciones": secciones},
        "intentos": {
            "enviados": stats["enviados"], "en_curso": stats["en_curso"], "anulados": stats["anulados"],
            "sospechosos": stats["sospechosos"], "promedio": round(stats["promedio"], 1) if stats["promedio"] is not None else None,
        },
        "examenes": {"total": len(codigos), "deshabilitados": deshabilitados},
        "en_curso": en_curso, "alertas": alertas, "reciente": reciente,
    }
