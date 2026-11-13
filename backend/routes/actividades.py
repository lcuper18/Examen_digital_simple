"""
Actividades routes - Tareas, proyectos y otras actividades evaluativas con rúbrica (solo docente).

El componente de la nota (tareas, proyecto, trabajo cotidiano...) se calcula con la suma de puntos
obtenidos entre la suma de puntos posibles de las actividades ya calificadas, y se guarda en `notas`.
"""
import json
import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from backend import bitacora, database, security
from backend.hojas import a_numero, emparejar, leer_cuerpo, leer_filas
from backend.routes.notas import _materia

router = APIRouter(
    prefix="/api/docente/actividades", tags=["actividades"], dependencies=[Depends(security.require_docente)]
)

COMPONENTES_ACTIVIDAD = ["trabajo_cotidiano", "tareas", "prueba01", "prueba02", "proyecto"]
ESTADOS = {
    "entregado": "Entregado",
    "tardio": "Entrega tardía",
    "sin_entrega": "Sin entrega (cuenta 0)",
    "revision": "En revisión (aún no cuenta)",
    "exonerado": "Exonerado (no cuenta)",
}
CUENTAN = ("entregado", "tardio", "sin_entrega")


class Criterio(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    puntos: float = Field(gt=0, le=1000)


class ActividadIn(BaseModel):
    materia_id: int
    componente: str
    nombre: str = Field(min_length=1, max_length=150)
    fecha_entrega: str | None = None
    puntos_max: float | None = Field(default=None, gt=0, le=1000)
    criterios: list[Criterio] = []


def _actividad(conn, actividad_id: int):
    fila = conn.execute("SELECT * FROM actividades WHERE id = ?", (actividad_id,)).fetchone()
    if fila is None:
        raise HTTPException(status_code=404, detail="Actividad no encontrada")
    return fila


def _salida(a, calificadas: int = 0) -> dict[str, Any]:
    return {
        "id": a["id"], "materia_id": a["materia_id"], "componente": a["componente"], "nombre": a["nombre"],
        "fecha_entrega": a["fecha_entrega"], "puntos_max": a["puntos_max"],
        "criterios": json.loads(a["criterios_json"]), "calificadas": calificadas,
    }


def _valores(datos: ActividadIn) -> tuple[float, str]:
    if datos.componente not in COMPONENTES_ACTIVIDAD:
        raise HTTPException(status_code=400, detail="Componente no válido")
    if datos.criterios:
        return round(sum(c.puntos for c in datos.criterios), 4), json.dumps([c.model_dump() for c in datos.criterios])
    if datos.puntos_max is None:
        raise HTTPException(status_code=400, detail="Indica los puntos de la actividad o sus criterios")
    return datos.puntos_max, "[]"


def recalcular_componente(conn, materia, componente: str) -> None:
    """Actualiza notas.<componente> de la sección con las actividades ya calificadas de ese componente."""
    actividades = conn.execute(
        "SELECT * FROM actividades WHERE materia_id = ? AND componente = ?", (materia["id"], componente)
    ).fetchall()
    num: dict[int, float] = {}
    den: dict[int, float] = {}
    algun = False
    estudiantes = [r["id"] for r in conn.execute("SELECT id FROM estudiantes WHERE seccion = ?", (materia["seccion"],))]
    for a in actividades:
        cals = {r["estudiante_id"]: r for r in conn.execute(
            "SELECT * FROM calificaciones WHERE actividad_id = ?", (a["id"],))}
        if not any(c["estado"] in CUENTAN for c in cals.values()):
            continue  # actividad aún sin calificar
        algun = True
        for eid in estudiantes:
            c = cals.get(eid)
            estado = c["estado"] if c else "sin_entrega"
            if estado not in CUENTAN:
                continue
            den[eid] = den.get(eid, 0) + a["puntos_max"]
            if estado != "sin_entrega":
                num[eid] = num.get(eid, 0) + (c["puntos"] or 0)
    if not algun:
        return
    for eid, total in den.items():
        conn.execute(
            f"INSERT INTO notas (estudiante_id, materia_id, {componente}) VALUES (?, ?, ?) "
            f"ON CONFLICT (estudiante_id, materia_id) DO UPDATE SET {componente} = excluded.{componente}",
            (eid, materia["id"], round(num.get(eid, 0) / total * 100, 4)),
        )


@router.get("")
def listar(materia_id: int) -> dict[str, Any]:
    with database.get_db_context() as conn:
        _materia(conn, materia_id)
        conteos = {r["actividad_id"]: r["n"] for r in conn.execute(
            "SELECT actividad_id, COUNT(*) AS n FROM calificaciones WHERE estado IN ('entregado','tardio','sin_entrega') "
            "GROUP BY actividad_id")}
        filas = conn.execute(
            "SELECT * FROM actividades WHERE materia_id = ? ORDER BY componente, COALESCE(fecha_entrega, ''), id",
            (materia_id,)).fetchall()
    return {"ok": True, "actividades": [_salida(a, conteos.get(a["id"], 0)) for a in filas],
            "componentes": COMPONENTES_ACTIVIDAD, "estados": ESTADOS}


@router.post("")
def crear(datos: ActividadIn) -> dict[str, Any]:
    puntos, criterios = _valores(datos)
    with database.get_db_context() as conn:
        materia = _materia(conn, datos.materia_id)
        try:
            cursor = conn.execute(
                "INSERT INTO actividades (materia_id, componente, nombre, fecha_entrega, puntos_max, criterios_json) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (materia["id"], datos.componente, datos.nombre.strip(), datos.fecha_entrega or None, puntos, criterios))
        except database.sqlite3.IntegrityError:
            raise HTTPException(status_code=409, detail="Ya existe una actividad con ese nombre en el componente")
        bitacora.registrar(conn, "crear_actividad", f"{materia['seccion']} · {materia['nombre']} · {datos.nombre}")
        conn.commit()
    return {"ok": True, "id": cursor.lastrowid}


@router.put("/{actividad_id}")
def editar(actividad_id: int, datos: ActividadIn) -> dict[str, Any]:
    puntos, criterios = _valores(datos)
    with database.get_db_context() as conn:
        actual = _actividad(conn, actividad_id)
        materia = _materia(conn, actual["materia_id"])
        try:
            conn.execute(
                "UPDATE actividades SET componente = ?, nombre = ?, fecha_entrega = ?, puntos_max = ?, criterios_json = ? "
                "WHERE id = ?",
                (datos.componente, datos.nombre.strip(), datos.fecha_entrega or None, puntos, criterios, actividad_id))
        except database.sqlite3.IntegrityError:
            raise HTTPException(status_code=409, detail="Ya existe una actividad con ese nombre en el componente")
        n_actual = len(json.loads(actual["criterios_json"]))
        if n_actual != len(datos.criterios):  # cambió la rúbrica: los puntos por criterio ya no aplican
            conn.execute("UPDATE calificaciones SET criterios_json = '[]' WHERE actividad_id = ?", (actividad_id,))
        for comp in {actual["componente"], datos.componente}:
            recalcular_componente(conn, materia, comp)
        bitacora.registrar(conn, "editar_actividad", f"{materia['nombre']} · {datos.nombre}")
        conn.commit()
    return {"ok": True}


@router.delete("/{actividad_id}")
def eliminar(actividad_id: int) -> dict[str, Any]:
    with database.get_db_context() as conn:
        actual = _actividad(conn, actividad_id)
        materia = _materia(conn, actual["materia_id"])
        conn.execute("DELETE FROM calificaciones WHERE actividad_id = ?", (actividad_id,))
        conn.execute("DELETE FROM actividades WHERE id = ?", (actividad_id,))
        recalcular_componente(conn, materia, actual["componente"])
        bitacora.registrar(conn, "eliminar_actividad", f"{materia['nombre']} · {actual['nombre']}")
        conn.commit()
    return {"ok": True}


@router.get("/{actividad_id}/calificaciones")
def obtener_calificaciones(actividad_id: int) -> dict[str, Any]:
    with database.get_db_context() as conn:
        actividad = _actividad(conn, actividad_id)
        materia = _materia(conn, actividad["materia_id"])
        guardadas = {r["estudiante_id"]: r for r in conn.execute(
            "SELECT * FROM calificaciones WHERE actividad_id = ?", (actividad_id,))}
        estudiantes = conn.execute(
            "SELECT id, nombre, apellido1, apellido2 FROM estudiantes WHERE seccion = ? "
            "ORDER BY apellido1, apellido2, nombre", (materia["seccion"],)).fetchall()
    filas = []
    for e in estudiantes:
        g = guardadas.get(e["id"])
        filas.append({
            "estudiante_id": e["id"], "nombre": e["nombre"], "apellido1": e["apellido1"], "apellido2": e["apellido2"],
            "estado": g["estado"] if g else "revision", "puntos": g["puntos"] if g else None,
            "criterios": json.loads(g["criterios_json"]) if g else [],
            "observacion": (g["observacion"] if g else "") or "", "nota_interna": (g["nota_interna"] if g else "") or "",
        })
    return {"ok": True, "actividad": _salida(actividad), "estados": ESTADOS, "calificaciones": filas}


class CalificacionIn(BaseModel):
    estudiante_id: int
    estado: str
    puntos: float | None = Field(default=None, ge=0)
    criterios: list[float | None] = []
    observacion: str = Field(default="", max_length=2000)
    nota_interna: str = Field(default="", max_length=2000)


class GuardarCalificaciones(BaseModel):
    calificaciones: list[CalificacionIn]


def _puntos_de(actividad, c: CalificacionIn) -> tuple[float | None, list[float | None]]:
    """Valida contra la rúbrica (o el máximo) y devuelve (puntos, puntos por criterio)."""
    criterios = json.loads(actividad["criterios_json"])
    if c.estado == "sin_entrega":
        return 0.0, []
    if criterios:
        if not c.criterios and c.puntos is None:
            return None, []
        if len(c.criterios) != len(criterios):
            raise HTTPException(status_code=400, detail="Faltan puntos de algún criterio")
        for valor, criterio in zip(c.criterios, criterios):
            if valor is not None and not 0 <= valor <= criterio["puntos"]:
                raise HTTPException(status_code=400, detail=f"«{criterio['nombre']}» vale como máximo {criterio['puntos']:g}")
        return round(sum(v or 0 for v in c.criterios), 4), list(c.criterios)
    if c.puntos is not None and c.puntos > actividad["puntos_max"]:
        raise HTTPException(status_code=400, detail=f"La actividad vale como máximo {actividad['puntos_max']:g} puntos")
    return c.puntos, []


@router.put("/{actividad_id}/calificaciones")
def guardar_calificaciones(actividad_id: int, request: GuardarCalificaciones) -> dict[str, Any]:
    if any(c.estado not in ESTADOS for c in request.calificaciones):
        raise HTTPException(status_code=400, detail="Estado no válido")
    with database.get_db_context() as conn:
        actividad = _actividad(conn, actividad_id)
        materia = _materia(conn, actividad["materia_id"])
        validos = {r["id"] for r in conn.execute("SELECT id FROM estudiantes WHERE seccion = ?", (materia["seccion"],))}
        if any(c.estudiante_id not in validos for c in request.calificaciones):
            raise HTTPException(status_code=400, detail=f"Hay estudiantes que no son de la sección {materia['seccion']}")
        for c in request.calificaciones:
            puntos, por_criterio = _puntos_de(actividad, c)
            if c.estado in ("entregado", "tardio") and puntos is None:
                raise HTTPException(status_code=400, detail="Falta la nota de un estudiante entregado")
            _guardar_calificacion(conn, actividad_id, c.estudiante_id, c.estado, puntos, por_criterio,
                                  c.observacion.strip(), c.nota_interna.strip())
        recalcular_componente(conn, materia, actividad["componente"])
        bitacora.registrar(
            conn, "calificar_actividad",
            f"{materia['seccion']} · {materia['nombre']} · {actividad['nombre']} ({len(request.calificaciones)})")
        conn.commit()
    return {"ok": True}


def _guardar_calificacion(conn, actividad_id, estudiante_id, estado, puntos, criterios, observacion, nota_interna) -> None:
    conn.execute(
        "INSERT INTO calificaciones (actividad_id, estudiante_id, estado, puntos, criterios_json, observacion, nota_interna) "
        "VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT (actividad_id, estudiante_id) DO UPDATE SET "
        "estado = excluded.estado, puntos = excluded.puntos, criterios_json = excluded.criterios_json, "
        "observacion = excluded.observacion, nota_interna = excluded.nota_interna",
        (actividad_id, estudiante_id, estado, puntos, json.dumps(criterios), observacion, nota_interna))


# ---------- Importar una hoja de calificación (xlsx) ----------

def _estado_de_hoja(texto: str) -> str:
    t = (texto or "").strip().lower()
    if t.startswith("sin entrega"):
        return "sin_entrega"
    if t.startswith("calificado"):
        return "entregado"
    if "tard" in t:
        return "tardio"
    if "exoner" in t:
        return "exonerado"
    return "revision"  # propuesta, pendiente de verificación...: no cuenta hasta que lo confirmes


@router.post("/importar")
async def importar_hoja(request: Request, materia_id: int, componente: str, nombre: str,
                        fecha_entrega: str | None = None) -> dict[str, Any]:
    """
    Crea (o reemplaza) una actividad desde una hoja como las de `Calificacion_*.xlsx`: una fila por estudiante,
    columnas de criterios con sus puntos entre paréntesis (p. ej. «E1 Inventario (4)»), «Estado»,
    «Observaciones para el estudiante» y «Notas internas».
    """
    if componente not in COMPONENTES_ACTIVIDAD:
        raise HTTPException(status_code=400, detail="Componente no válido")
    filas = leer_filas(await leer_cuerpo(request))
    cab = next((i for i, f in enumerate(filas) if any(str(c or "").strip().lower() == "estudiante" for c in f)), None)
    if cab is None:
        raise HTTPException(status_code=400, detail="No encontré la columna «Estudiante»")
    enc = [str(c or "").strip() for c in filas[cab]]
    col = lambda clave: next((i for i, t in enumerate(enc) if t.lower().startswith(clave)), None)
    c_est, c_estado = col("estudiante"), col("estado")
    c_obs, c_int = col("observaciones"), col("notas internas")
    primero_criterio = c_est + 1
    criterios_cols = []
    for i, t in enumerate(enc):
        m = re.search(r"\((\d+(?:[.,]\d+)?)\)\s*$", t)
        if i >= primero_criterio and m and not t.lower().startswith(("total", "nota", "sec")):
            criterios_cols.append((i, re.sub(r"\s*\(.*\)\s*$", "", t), float(m.group(1).replace(",", "."))))
    if not criterios_cols:
        raise HTTPException(status_code=400, detail="No encontré columnas de criterios con sus puntos entre paréntesis")

    with database.get_db_context() as conn:
        materia = _materia(conn, materia_id)
        buscar = emparejar(conn.execute(
            "SELECT id, cedula, nombre, apellido1, apellido2 FROM estudiantes WHERE seccion = ?", (materia["seccion"],)).fetchall())
        criterios = [{"nombre": n, "puntos": p} for _, n, p in criterios_cols]
        puntos_max = round(sum(p for _, _, p in criterios_cols), 4)
        existente = conn.execute(
            "SELECT id FROM actividades WHERE materia_id = ? AND componente = ? AND nombre = ?",
            (materia_id, componente, nombre.strip())).fetchone()
        if existente:
            actividad_id = existente["id"]
            conn.execute("UPDATE actividades SET fecha_entrega = ?, puntos_max = ?, criterios_json = ? WHERE id = ?",
                         (fecha_entrega or None, puntos_max, json.dumps(criterios), actividad_id))
            conn.execute("DELETE FROM calificaciones WHERE actividad_id = ?", (actividad_id,))
        else:
            actividad_id = conn.execute(
                "INSERT INTO actividades (materia_id, componente, nombre, fecha_entrega, puntos_max, criterios_json) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (materia_id, componente, nombre.strip(), fecha_entrega or None, puntos_max, json.dumps(criterios))).lastrowid
        importadas, sin_pareja = 0, []
        for f in filas[cab + 1:]:
            celda = lambda i: (f[i] if i is not None and i < len(f) else None)
            if not str(celda(c_est) or "").strip():
                continue
            if all(a_numero(celda(i)) is None for i, _, _ in criterios_cols) and not str(celda(c_estado) or "").strip():
                continue  # fila de notas o aclaraciones al pie de la hoja, no de un estudiante
            eid = buscar(nombre=celda(c_est))
            if eid is None:
                sin_pareja.append(str(celda(c_est)).strip())
                continue
            puntos_c = [a_numero(celda(i)) or 0.0 for i, _, _ in criterios_cols]
            if any(p > m for p, (_, _, m) in zip(puntos_c, criterios_cols)):
                raise HTTPException(status_code=400, detail=f"Un criterio de «{celda(c_est)}» supera sus puntos")
            estado_texto = str(celda(c_estado) or "")
            estado = _estado_de_hoja(estado_texto)
            interna = str(celda(c_int) or "").strip()
            if estado == "revision" and estado_texto.strip():
                interna = f"[Estado en la hoja: {estado_texto.strip()}] {interna}".strip()
            _guardar_calificacion(
                conn, actividad_id, eid, estado, 0.0 if estado == "sin_entrega" else round(sum(puntos_c), 4),
                [] if estado == "sin_entrega" else puntos_c, str(celda(c_obs) or "").strip(), interna)
            importadas += 1
        recalcular_componente(conn, materia, componente)
        bitacora.registrar(conn, "importar_actividad", f"{materia['seccion']} · {materia['nombre']} · {nombre} ({importadas})")
        conn.commit()
    return {"ok": True, "actividad_id": actividad_id, "importadas": importadas, "sin_pareja": sin_pareja,
            "criterios": len(criterios), "puntos_max": puntos_max}
