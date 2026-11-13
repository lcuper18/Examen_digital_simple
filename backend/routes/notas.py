"""
Notas routes - Módulo de notas del docente (solo docente).
"""
import csv
import io
from typing import Any

import re

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from backend import bitacora, database, security
from backend.hojas import a_numero, emparejar, leer_filas, sin_tildes

router = APIRouter(
    prefix="/api/docente", tags=["notas"], dependencies=[Depends(security.require_docente)]
)

COMPONENTES = ["trabajo_cotidiano", "tareas", "prueba01", "prueba02", "proyecto", "asistencia"]
ETIQUETAS = {
    "trabajo_cotidiano": "Trabajo cotidiano", "tareas": "Tareas", "prueba01": "Prueba 1",
    "prueba02": "Prueba 2", "proyecto": "Proyecto", "asistencia": "Asistencia",
}

# Componente -> puntos de la nota final por defecto (suman 100). Cada materia puede tener los suyos.
PONDERACIONES = {
    "trabajo_cotidiano": 25,
    "tareas": 10,
    "prueba01": 22.5,
    "prueba02": 22.5,
    "proyecto": 15,
    "asistencia": 5,
}


def nota_minima(conn=None) -> float:
    """Nota mínima de aprobación (0-100), tomada de los ajustes."""
    if conn is None:
        with database.get_db_context() as c:
            return nota_minima(c)
    return float(database.leer_ajustes(conn)["nota_minima"])


def pesos_de(conn, materia_id: int) -> dict[str, float]:
    """Ponderaciones de una materia: las guardadas sobre las de por defecto."""
    pesos = dict(PONDERACIONES)
    pesos.update({
        r["componente"]: r["peso"] for r in conn.execute(
            "SELECT componente, peso FROM ponderaciones WHERE materia_id = ?", (materia_id,))
    })
    return pesos


def nota_final(notas: dict[str, float | None], pesos: dict[str, float] | None = None) -> float:
    """Nota ponderada (0-100). Un componente sin nota cuenta como 0."""
    pesos = pesos or PONDERACIONES
    total = sum((notas.get(c) or 0) * peso / 100 for c, peso in pesos.items())
    return round(total, 1)


def _materia(conn, materia_id: int):
    row = conn.execute("SELECT * FROM materias WHERE id = ?", (materia_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Materia no encontrada")
    return row


def _filas(conn, materia) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT e.id AS estudiante_id, e.nombre, e.apellido1, e.apellido2, "
        "n.trabajo_cotidiano, n.tareas, n.prueba01, n.prueba02, n.proyecto, n.asistencia "
        "FROM estudiantes e LEFT JOIN notas n "
        "ON n.estudiante_id = e.id AND n.materia_id = ? "
        "WHERE e.seccion = ? ORDER BY e.apellido1, e.apellido2, e.nombre",
        (materia["id"], materia["seccion"]),
    ).fetchall()
    pesos = pesos_de(conn, materia["id"])
    filas = []
    for r in rows:
        fila = dict(r)
        fila["completa"] = all(fila[c] is not None for c in COMPONENTES)
        fila["nota_final"] = nota_final(fila, pesos)
        filas.append(fila)
    return filas


@router.get("/materias")
def listar_materias() -> dict[str, Any]:
    with database.get_db_context() as conn:
        rows = conn.execute(
            "SELECT id, seccion, nombre, periodo FROM materias ORDER BY seccion, periodo, nombre"
        ).fetchall()
        materias = [{**dict(r), "ponderaciones": pesos_de(conn, r["id"])} for r in rows]
        minima = nota_minima(conn)
    return {
        "ok": True, "materias": materias, "componentes": COMPONENTES, "etiquetas": ETIQUETAS,
        "ponderaciones": PONDERACIONES, "nota_minima": minima,
    }


@router.get("/notas")
def obtener_notas(materia_id: int) -> dict[str, Any]:
    """Notas de todos los estudiantes de la sección de la materia, con nota final y resumen."""
    with database.get_db_context() as conn:
        materia = _materia(conn, materia_id)
        filas = _filas(conn, materia)
        pesos = pesos_de(conn, materia_id)
        minima = nota_minima(conn)
        publicada = conn.execute(
            "SELECT publicado FROM publicaciones WHERE materia_id = ?", (materia_id,)).fetchone()
    finales = [f["nota_final"] for f in filas if f["completa"]]
    resumen = {
        "estudiantes": len(filas),
        "completas": len(finales),
        "promedio": round(sum(finales) / len(finales), 1) if finales else None,
        "maxima": max(finales) if finales else None,
        "minima": min(finales) if finales else None,
    }
    return {
        "ok": True, "materia": dict(materia), "notas": filas, "resumen": resumen,
        "ponderaciones": pesos, "nota_minima": minima, "publicado": bool(publicada and publicada["publicado"]),
    }


class Publicacion(BaseModel):
    publicado: bool


@router.put("/materias/{materia_id}/publicacion")
def publicar_materia(materia_id: int, request: Publicacion) -> dict[str, Any]:
    """Muestra u oculta a los estudiantes las notas, la asistencia y las actividades de una materia."""
    from datetime import datetime, timezone

    with database.get_db_context() as conn:
        materia = _materia(conn, materia_id)
        conn.execute(
            "INSERT INTO publicaciones (materia_id, publicado, fecha) VALUES (?, ?, ?) "
            "ON CONFLICT (materia_id) DO UPDATE SET publicado = excluded.publicado, fecha = excluded.fecha",
            (materia_id, int(request.publicado), datetime.now(timezone.utc).isoformat()),
        )
        bitacora.registrar(
            conn, "publicar_notas" if request.publicado else "ocultar_notas",
            f"{materia['seccion']} · P{materia['periodo']} · {materia['nombre']}",
        )
        conn.commit()
    return {"ok": True, "publicado": request.publicado}


class Ponderaciones(BaseModel):
    ponderaciones: dict[str, float]


@router.put("/materias/{materia_id}/ponderaciones")
def guardar_ponderaciones(materia_id: int, request: Ponderaciones) -> dict[str, Any]:
    """Define cuántos puntos de la nota final vale cada componente en una materia (deben sumar 100)."""
    pesos = request.ponderaciones
    if set(pesos) != set(COMPONENTES):
        raise HTTPException(status_code=400, detail="Deben venir los seis componentes")
    if any(p < 0 or p > 100 for p in pesos.values()):
        raise HTTPException(status_code=400, detail="Cada peso debe estar entre 0 y 100")
    if abs(sum(pesos.values()) - 100) > 0.001:
        raise HTTPException(status_code=400, detail=f"Los pesos deben sumar 100 (suman {sum(pesos.values()):g})")
    with database.get_db_context() as conn:
        materia = _materia(conn, materia_id)
        conn.executemany(
            "INSERT INTO ponderaciones (materia_id, componente, peso) VALUES (?, ?, ?) "
            "ON CONFLICT (materia_id, componente) DO UPDATE SET peso = excluded.peso",
            [(materia_id, c, pesos[c]) for c in COMPONENTES],
        )
        bitacora.registrar(
            conn, "guardar_ponderaciones",
            f"{materia['seccion']} · P{materia['periodo']} · {materia['nombre']}: "
            + " / ".join(f"{pesos[c]:g}" for c in COMPONENTES),
        )
        conn.commit()
    return {"ok": True, "ponderaciones": pesos}


class NotaEstudiante(BaseModel):
    estudiante_id: int
    trabajo_cotidiano: float | None = Field(default=None, ge=0, le=100)
    tareas: float | None = Field(default=None, ge=0, le=100)
    prueba01: float | None = Field(default=None, ge=0, le=100)
    prueba02: float | None = Field(default=None, ge=0, le=100)
    proyecto: float | None = Field(default=None, ge=0, le=100)
    asistencia: float | None = Field(default=None, ge=0, le=100)


class GuardarNotas(BaseModel):
    materia_id: int
    notas: list[NotaEstudiante]


def _guardar(conn, materia, notas: list[NotaEstudiante]) -> None:
    validos = {
        r["id"] for r in conn.execute(
            "SELECT id FROM estudiantes WHERE seccion = ?", (materia["seccion"],)
        )
    }
    for n in notas:
        if n.estudiante_id not in validos:
            raise HTTPException(
                status_code=400,
                detail=f"El estudiante {n.estudiante_id} no pertenece a la sección {materia['seccion']}",
            )
    columnas = COMPONENTES
    for n in notas:
        conn.execute(
            f"INSERT INTO notas (estudiante_id, materia_id, {', '.join(columnas)}) "
            f"VALUES (?, ?, {', '.join('?' for _ in columnas)}) "
            f"ON CONFLICT (estudiante_id, materia_id) DO UPDATE SET "
            f"{', '.join(f'{c} = excluded.{c}' for c in columnas)}",
            (n.estudiante_id, materia["id"], *[getattr(n, c) for c in columnas]),
        )
    conn.commit()


@router.put("/notas")
def guardar_notas(request: GuardarNotas) -> dict[str, Any]:
    """Guarda en bloque las notas de una materia (reemplaza los valores enviados)."""
    with database.get_db_context() as conn:
        materia = _materia(conn, request.materia_id)
        _guardar(conn, materia, request.notas)
        bitacora.registrar(
            conn, "guardar_notas",
            f"{materia['seccion']} · P{materia['periodo']} · {materia['nombre']} ({len(request.notas)} estudiantes)",
        )
        conn.commit()
    return {"ok": True, "guardadas": len(request.notas)}


class ImportarPrueba(BaseModel):
    materia_id: int
    componente: str | None = None  # "prueba01" | "prueba02"; vacío = según los exámenes vinculados
    codigo_examen: str | None = None


def _importar(conn, materia, componente: str, codigo: str) -> int:
    """Copia a `componente` la nota (0-100) de los intentos enviados y no anulados de un examen."""
    rows = conn.execute(
        "SELECT i.estudiante_id, i.puntuacion, i.total FROM intentos i "
        "JOIN estudiantes e ON e.id = i.estudiante_id "
        "WHERE i.codigo_examen = ? AND i.fecha_fin IS NOT NULL AND i.anulado = 0 AND e.seccion = ?",
        (codigo, materia["seccion"]),
    ).fetchall()
    for r in rows:
        nota = round(r["puntuacion"] / r["total"] * 100, 4) if r["total"] else 0
        conn.execute(
            f"INSERT INTO notas (estudiante_id, materia_id, {componente}) "
            f"VALUES (?, ?, ?) ON CONFLICT (estudiante_id, materia_id) "
            f"DO UPDATE SET {componente} = excluded.{componente}",
            (r["estudiante_id"], materia["id"], nota),
        )
    bitacora.registrar(
        conn, "importar_prueba",
        f"{materia['seccion']} · {materia['nombre']} · {componente} desde {codigo} ({len(rows)})",
    )
    return len(rows)


@router.post("/notas/importar-prueba")
def importar_prueba(request: ImportarPrueba) -> dict[str, Any]:
    """
    Copia a prueba01/prueba02 la nota de un examen. Con `codigo_examen` y `componente` importa ese
    examen; sin ellos, importa todos los exámenes vinculados a la materia (pestaña Exámenes).
    """
    with database.get_db_context() as conn:
        materia = _materia(conn, request.materia_id)
        if request.codigo_examen:
            if request.componente not in ("prueba01", "prueba02"):
                raise HTTPException(status_code=400, detail="componente debe ser prueba01 o prueba02")
            pares = [(request.componente, request.codigo_examen.upper())]
        else:
            pares = [
                (r["componente"], r["codigo"]) for r in conn.execute(
                    "SELECT codigo, componente FROM examen_vinculos "
                    "WHERE materia_id = ? AND componente IN ('prueba01', 'prueba02')", (materia["id"],))
                if request.componente in (None, r["componente"])
            ]
            if not pares:
                raise HTTPException(status_code=400, detail="Esta materia no tiene exámenes vinculados. Vincúlalos en la pestaña Exámenes (Configurar…)")
        importadas = sum(_importar(conn, materia, comp, codigo) for comp, codigo in pares)
        conn.commit()
    return {"ok": True, "importadas": importadas, "examenes": [c for _, c in pares]}


ALIAS_COMPONENTES = {
    "tc": "trabajo_cotidiano", "trabajocotidiano": "trabajo_cotidiano",
    "tarea": "tareas", "tareas": "tareas",
    "prueba1": "prueba01", "prueba01": "prueba01", "p1": "prueba01",
    "prueba2": "prueba02", "prueba02": "prueba02", "p2": "prueba02",
    "proyecto": "proyecto", "asistencia": "asistencia",
}


@router.post("/notas/importar-hoja")
async def importar_hoja(request: Request, materia_id: int) -> dict[str, Any]:
    """
    Carga las notas de una hoja del docente (CSV con ';' o xlsx) en puntos, p. ej. las de
    `Notas/Periodo02/<sección>/*.csv`: columnas Id (cédula sin guiones) o Nombre, y los componentes
    (Trabajo cotidiano, Tareas, Prueba1, Prueba2, Proyecto, Asistencia). Las celdas vacías no cambian nada.
    """
    filas = leer_filas(await request.body())
    cab = next((i for i, f in enumerate(filas) if any(
        re.sub(r"\W", "", sin_tildes(str(c or "")).lower()) in ALIAS_COMPONENTES for c in f)), None)
    if cab is None:
        raise HTTPException(status_code=400, detail="No encontré columnas de componentes (TC, Tareas, Prueba1...)")
    enc = [re.sub(r"\W", "", sin_tildes(str(c or "")).lower()) for c in filas[cab]]
    c_id = next((i for i, t in enumerate(enc) if t in ("id", "cedula", "identificacion")), None)
    c_nombre = next((i for i, t in enumerate(enc) if t in ("nombre", "estudiante")), None)
    columnas = {i: ALIAS_COMPONENTES[t] for i, t in enumerate(enc) if t in ALIAS_COMPONENTES}
    if c_id is None and c_nombre is None:
        raise HTTPException(status_code=400, detail="Falta la columna Id o Nombre")

    with database.get_db_context() as conn:
        materia = _materia(conn, materia_id)
        pesos = pesos_de(conn, materia_id)
        buscar = emparejar(conn.execute(
            "SELECT id, cedula, nombre, apellido1, apellido2 FROM estudiantes WHERE seccion = ?",
            (materia["seccion"],)).fetchall())
        importados, sin_pareja, avisos = 0, [], []
        for f in filas[cab + 1:]:
            celda = lambda i: (f[i] if i is not None and i < len(f) else None)
            ident, nombre = celda(c_id), celda(c_nombre)
            if not str(ident or "").strip() and not str(nombre or "").strip():
                continue
            eid = buscar(cedula=a_numero(ident) if a_numero(ident) is not None else ident, nombre=nombre)
            if eid is None:
                sin_pareja.append(str(nombre or ident).strip())
                continue
            valores = {}
            for i, comp in columnas.items():
                puntos = a_numero(celda(i))
                if puntos is None:
                    continue
                if puntos < 0 or puntos > pesos[comp] + 1e-9:
                    avisos.append(f"{nombre or ident}: {ETIQUETAS[comp]} {puntos:g} supera {pesos[comp]:g}")
                    continue
                valores[comp] = round(puntos / pesos[comp] * 100, 4) if pesos[comp] else 0.0
            if not valores:
                continue
            conn.execute(
                f"INSERT INTO notas (estudiante_id, materia_id, {', '.join(valores)}) "
                f"VALUES (?, ?, {', '.join('?' for _ in valores)}) ON CONFLICT (estudiante_id, materia_id) "
                f"DO UPDATE SET {', '.join(f'{c} = excluded.{c}' for c in valores)}",
                (eid, materia_id, *valores.values()))
            importados += 1
        bitacora.registrar(
            conn, "importar_hoja",
            f"{materia['seccion']} · P{materia['periodo']} · {materia['nombre']} ({importados} estudiantes)")
        conn.commit()
    return {"ok": True, "importados": importados, "sin_pareja": sin_pareja, "avisos": avisos}


def _csv_response(nombre: str, encabezado: list[str], filas: list[list[Any]]) -> Response:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(encabezado)
    writer.writerows(filas)
    return Response(
        content="\ufeff" + buffer.getvalue(),  # BOM para que Excel lea las tildes
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )


@router.get("/notas/exportar")
def exportar_notas(materia_id: int) -> Response:
    with database.get_db_context() as conn:
        materia = _materia(conn, materia_id)
        filas = _filas(conn, materia)
    columnas = COMPONENTES
    return _csv_response(
        f"notas_{materia['seccion']}_P{materia['periodo']}_{materia['id']}.csv",
        ["Apellido 1", "Apellido 2", "Nombre", *columnas, "nota_final"],
        [
            [f["apellido1"], f["apellido2"], f["nombre"],
             *["" if f[c] is None else f[c] for c in columnas], f["nota_final"]]
            for f in filas
        ],
    )
