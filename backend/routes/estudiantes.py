"""
Estudiantes routes - Gestión de estudiantes y contraseñas (solo docente).
"""
import csv
import io
import sqlite3
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend import bitacora, database, ratelimit, security

router = APIRouter(
    prefix="/api/docente/estudiantes", tags=["estudiantes"],
    dependencies=[Depends(security.require_docente)],
)


def _sufijo(username: str) -> str:
    return f":{username.lower()}"


def _estudiante(conn, estudiante_id: int):
    fila = conn.execute("SELECT * FROM estudiantes WHERE id = ?", (estudiante_id,)).fetchone()
    if fila is None:
        raise HTTPException(status_code=404, detail="Estudiante no encontrado")
    return fila


def _nombre(fila) -> str:
    return f"{fila['nombre']} {fila['apellido1']} {fila['apellido2'] or ''}".strip()


@router.get("")
def listar_estudiantes(seccion: str | None = None, q: str | None = None) -> dict[str, Any]:
    with database.get_db_context() as conn:
        filas = conn.execute(
            "SELECT e.id, e.cedula, e.nombre, e.apellido1, e.apellido2, e.seccion, e.username, "
            "e.activo, e.debe_cambiar_password, e.ultimo_acceso, "
            "(SELECT COUNT(*) FROM intentos i WHERE i.estudiante_id = e.id "
            " AND i.fecha_fin IS NOT NULL AND i.anulado = 0) AS enviados "
            "FROM estudiantes e ORDER BY e.seccion, e.apellido1, e.apellido2, e.nombre"
        ).fetchall()
    estudiantes = []
    for f in filas:
        d = dict(f)
        if seccion and d["seccion"] != seccion:
            continue
        if q and q.lower() not in f"{_nombre(f)} {d['username']} {d['cedula']}".lower():
            continue
        d["bloqueado"] = ratelimit.bloqueada_con_sufijo(_sufijo(d["username"]))
        estudiantes.append(d)
    return {"ok": True, "estudiantes": estudiantes}


@router.post("/{estudiante_id}/reiniciar-password")
def reiniciar_password(estudiante_id: int) -> dict[str, Any]:
    """Genera una contraseña temporal (se muestra una sola vez) y obliga a cambiarla."""
    with database.get_db_context() as conn:
        fila = _estudiante(conn, estudiante_id)
        temporal = database.generar_password_temporal()
        conn.execute(
            "UPDATE estudiantes SET password_hash = ?, debe_cambiar_password = 1 WHERE id = ?",
            (database.hash_password(temporal), estudiante_id),
        )
        bitacora.registrar(conn, "reiniciar_password", _nombre(fila))
        conn.commit()
    ratelimit.limpiar_con_sufijo(_sufijo(fila["username"]))
    return {"ok": True, "username": fila["username"], "password_temporal": temporal}


@router.post("/{estudiante_id}/desbloquear")
def desbloquear(estudiante_id: int) -> dict[str, Any]:
    with database.get_db_context() as conn:
        fila = _estudiante(conn, estudiante_id)
        bitacora.registrar(conn, "desbloquear_login", _nombre(fila))
        conn.commit()
    ratelimit.limpiar_con_sufijo(_sufijo(fila["username"]))
    return {"ok": True}


class ActualizarEstudiante(BaseModel):
    activo: bool | None = None
    seccion: str | None = Field(default=None, min_length=1, max_length=20)


@router.patch("/{estudiante_id}")
def actualizar_estudiante(estudiante_id: int, request: ActualizarEstudiante) -> dict[str, Any]:
    with database.get_db_context() as conn:
        fila = _estudiante(conn, estudiante_id)
        if request.activo is not None:
            conn.execute("UPDATE estudiantes SET activo = ? WHERE id = ?", (int(request.activo), estudiante_id))
            bitacora.registrar(conn, "activar_cuenta" if request.activo else "desactivar_cuenta", _nombre(fila))
        if request.seccion is not None and request.seccion != fila["seccion"]:
            conn.execute("UPDATE estudiantes SET seccion = ? WHERE id = ?", (request.seccion, estudiante_id))
            bitacora.registrar(
                conn, "cambiar_seccion", f"{_nombre(fila)}: {fila['seccion']} → {request.seccion}"
            )
        conn.commit()
    return {"ok": True}


class NuevoEstudiante(BaseModel):
    cedula: str = Field(min_length=1)
    nombre: str = Field(min_length=1)
    apellido1: str = Field(min_length=1)
    apellido2: str = ""
    seccion: str = Field(min_length=1, max_length=20)


@router.post("")
def crear_estudiante(request: NuevoEstudiante) -> dict[str, Any]:
    """Alta de un estudiante con contraseña temporal."""
    with database.get_db_context() as conn:
        try:
            nuevo_id, username, temporal = database.crear_estudiante(
                conn, request.cedula.strip(), request.nombre.strip().upper(),
                request.apellido1.strip().upper(), request.apellido2.strip().upper(),
                request.seccion.strip(),
            )
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409, detail="Ya existe un estudiante con esa cédula o usuario")
        bitacora.registrar(conn, "crear_estudiante", f"{request.nombre} {request.apellido1} ({request.seccion})")
        conn.commit()
    return {"ok": True, "id": nuevo_id, "username": username, "password_temporal": temporal}


@router.delete("/{estudiante_id}")
def eliminar_estudiante(estudiante_id: int) -> dict[str, Any]:
    """Elimina un estudiante sin intentos; si ya presentó exámenes, hay que desactivarlo."""
    with database.get_db_context() as conn:
        fila = _estudiante(conn, estudiante_id)
        if conn.execute("SELECT 1 FROM intentos WHERE estudiante_id = ?", (estudiante_id,)).fetchone():
            raise HTTPException(
                status_code=409,
                detail="El estudiante tiene intentos registrados; desactiva la cuenta en su lugar",
            )
        conn.execute("DELETE FROM notas WHERE estudiante_id = ?", (estudiante_id,))
        conn.execute("DELETE FROM estudiantes WHERE id = ?", (estudiante_id,))
        bitacora.registrar(conn, "eliminar_estudiante", _nombre(fila))
        conn.commit()
    return {"ok": True}


class ImportarCsv(BaseModel):
    csv: str  # encabezado: cedula,nombre,apellido1,apellido2,seccion


@router.post("/importar")
def importar_csv(request: ImportarCsv) -> dict[str, Any]:
    """Importa estudiantes desde texto CSV; devuelve las credenciales temporales de los creados."""
    lector = csv.DictReader(io.StringIO(request.csv.lstrip("﻿")))
    requeridas = {"cedula", "nombre", "apellido1", "seccion"}
    if not lector.fieldnames or not requeridas <= set(lector.fieldnames):
        raise HTTPException(status_code=400, detail="El CSV debe tener: cedula,nombre,apellido1,apellido2,seccion")
    creados, omitidos = [], []
    with database.get_db_context() as conn:
        for r in lector:
            try:
                _, username, temporal = database.crear_estudiante(
                    conn, r["cedula"].strip(), r["nombre"].strip().upper(), r["apellido1"].strip().upper(),
                    (r.get("apellido2") or "").strip().upper(), r["seccion"].strip(),
                )
                creados.append({
                    "username": username, "password_temporal": temporal,
                    "nombre": f"{r['nombre']} {r['apellido1']}", "seccion": r["seccion"].strip(),
                })
            except sqlite3.IntegrityError:
                omitidos.append(r["cedula"])
        bitacora.registrar(conn, "importar_estudiantes", f"{len(creados)} creados, {len(omitidos)} omitidos")
        conn.commit()
    return {"ok": True, "creados": creados, "omitidos": omitidos}


class ReiniciarSeccion(BaseModel):
    seccion: str


@router.post("/exigir-cambio-seccion")
def exigir_cambio_seccion(request: ReiniciarSeccion) -> dict[str, Any]:
    """
    Obliga a cada estudiante activo de la sección a crear su propia contraseña la próxima vez que entre,
    sin cambiarle la actual. Las claves iniciales se deducen del nombre y la cédula, así que conviene hacerlo.
    """
    with database.get_db_context() as conn:
        cantidad = conn.execute(
            "UPDATE estudiantes SET debe_cambiar_password = 1 WHERE seccion = ? AND activo = 1", (request.seccion,)
        ).rowcount
        bitacora.registrar(conn, "exigir_cambio_clave", f"{request.seccion}: {cantidad} estudiantes")
        conn.commit()
    return {"ok": True, "seccion": request.seccion, "estudiantes": cantidad}


@router.post("/reiniciar-seccion")
def reiniciar_seccion(request: ReiniciarSeccion) -> dict[str, Any]:
    """Genera contraseñas temporales para toda una sección (hoja de credenciales)."""
    credenciales = []
    with database.get_db_context() as conn:
        filas = conn.execute(
            "SELECT * FROM estudiantes WHERE seccion = ? AND activo = 1 "
            "ORDER BY apellido1, apellido2, nombre", (request.seccion,)
        ).fetchall()
        for f in filas:
            temporal = database.generar_password_temporal()
            conn.execute(
                "UPDATE estudiantes SET password_hash = ?, debe_cambiar_password = 1 WHERE id = ?",
                (database.hash_password(temporal), f["id"]),
            )
            credenciales.append({"nombre": _nombre(f), "username": f["username"], "password_temporal": temporal})
            ratelimit.limpiar_con_sufijo(_sufijo(f["username"]))
        bitacora.registrar(conn, "reiniciar_seccion", f"{request.seccion}: {len(filas)} estudiantes")
        conn.commit()
    return {"ok": True, "seccion": request.seccion, "credenciales": credenciales}
