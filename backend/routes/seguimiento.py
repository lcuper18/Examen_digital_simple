"""
Seguimiento routes - Ficha del estudiante, observaciones, alertas de riesgo y cierre del curso lectivo (solo docente).
"""
import io
import re
from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from openpyxl import Workbook
from pydantic import BaseModel, Field

from backend import bitacora, database, security
from backend.hojas import a_numero, leer_hojas, sin_tildes
from backend.routes.asistencia import _resumen
from backend.routes.informes import _nombre_acta, agregar_materias
from backend.routes.notas import COMPONENTES, ETIQUETAS, _filas, nota_minima, pesos_de

router = APIRouter(prefix="/api/docente", tags=["seguimiento"], dependencies=[Depends(security.require_docente)])

TIPOS_OBSERVACION = {
    "anecdotico": "Registro anecdótico", "logro": "Logro o avance", "conducta": "Conducta",
    "familia": "Comunicación con la familia", "apoyo": "Apoyo o adecuación",
}


def _estudiante(conn, estudiante_id: int):
    fila = conn.execute("SELECT * FROM estudiantes WHERE id = ?", (estudiante_id,)).fetchone()
    if fila is None:
        raise HTTPException(status_code=404, detail="Estudiante no encontrado")
    return fila


# ---------- Ficha ----------

class FichaIn(BaseModel):
    telefono: str = Field(default="", max_length=40)
    encargado_nombre: str = Field(default="", max_length=120)
    encargado_cedula: str = Field(default="", max_length=30)
    encargado_telefono: str = Field(default="", max_length=40)
    encargado_telefono2: str = Field(default="", max_length=40)
    direccion: str = Field(default="", max_length=300)
    adecuacion: bool = False
    adecuacion_detalle: str = Field(default="", max_length=500)


CAMPOS_FICHA = ["telefono", "encargado_nombre", "encargado_cedula", "encargado_telefono", "encargado_telefono2",
                "direccion", "adecuacion_detalle"]


@router.get("/estudiantes/{estudiante_id}/ficha")
def obtener_ficha(estudiante_id: int) -> dict[str, Any]:
    with database.get_db_context() as conn:
        e = _estudiante(conn, estudiante_id)
        materias = conn.execute("SELECT * FROM materias WHERE seccion = ? ORDER BY periodo, nombre", (e["seccion"],)).fetchall()
        informes = {estudiante_id: {"materias": []}}
        agregar_materias(conn, materias, informes, nota_minima(conn))
        observaciones = [dict(r) for r in conn.execute(
            "SELECT o.*, m.nombre AS materia FROM observaciones o LEFT JOIN materias m ON m.id = o.materia_id "
            "WHERE o.estudiante_id = ? ORDER BY o.fecha DESC, o.id DESC", (estudiante_id,))]
        examenes = [dict(r) for r in conn.execute(
            "SELECT codigo_examen AS codigo, puntuacion, total, fecha_fin FROM intentos "
            "WHERE estudiante_id = ? AND fecha_fin IS NOT NULL AND anulado = 0 ORDER BY fecha_fin", (estudiante_id,))]
        alertas = calcular_alertas(conn, estudiante_id=estudiante_id)
    return {
        "ok": True,
        "estudiante": {
            "id": e["id"], "nombre": _nombre_acta(e), "cedula": e["cedula"], "seccion": e["seccion"], "activo": bool(e["activo"]),
            "adecuacion": bool(e["adecuacion"]), **{c: e[c] or "" for c in CAMPOS_FICHA},
        },
        "tipos": TIPOS_OBSERVACION, "observaciones": observaciones, "materias": informes[estudiante_id]["materias"],
        "examenes": examenes, "alertas": alertas[0]["alertas"] if alertas else [],
    }


@router.put("/estudiantes/{estudiante_id}/ficha")
def guardar_ficha(estudiante_id: int, datos: FichaIn) -> dict[str, Any]:
    with database.get_db_context() as conn:
        e = _estudiante(conn, estudiante_id)
        valores = {c: getattr(datos, c).strip() for c in CAMPOS_FICHA}
        conn.execute(
            f"UPDATE estudiantes SET {', '.join(f'{c} = ?' for c in valores)}, adecuacion = ? WHERE id = ?",
            (*valores.values(), int(datos.adecuacion), estudiante_id))
        bitacora.registrar(conn, "guardar_ficha", f"{e['seccion']} · {_nombre_acta(e)}")
        conn.commit()
    return {"ok": True}


class ObservacionIn(BaseModel):
    fecha: str
    tipo: str
    texto: str = Field(min_length=1, max_length=2000)
    materia_id: int | None = None


@router.post("/estudiantes/{estudiante_id}/observaciones")
def agregar_observacion(estudiante_id: int, datos: ObservacionIn) -> dict[str, Any]:
    try:
        date.fromisoformat(datos.fecha)
    except ValueError:
        raise HTTPException(status_code=400, detail="Fecha no válida")
    if datos.tipo not in TIPOS_OBSERVACION:
        raise HTTPException(status_code=400, detail="Tipo de observación no válido")
    with database.get_db_context() as conn:
        e = _estudiante(conn, estudiante_id)
        if datos.materia_id is not None and not conn.execute(
                "SELECT 1 FROM materias WHERE id = ?", (datos.materia_id,)).fetchone():
            raise HTTPException(status_code=404, detail="Materia no encontrada")
        cursor = conn.execute(
            "INSERT INTO observaciones (estudiante_id, fecha, tipo, texto, materia_id) VALUES (?, ?, ?, ?, ?)",
            (estudiante_id, datos.fecha, datos.tipo, datos.texto.strip(), datos.materia_id))
        bitacora.registrar(conn, "agregar_observacion", f"{e['seccion']} · {_nombre_acta(e)} · {TIPOS_OBSERVACION[datos.tipo]}")
        conn.commit()
    return {"ok": True, "id": cursor.lastrowid}


@router.delete("/observaciones/{observacion_id}")
def eliminar_observacion(observacion_id: int) -> dict[str, Any]:
    with database.get_db_context() as conn:
        if not conn.execute("DELETE FROM observaciones WHERE id = ?", (observacion_id,)).rowcount:
            raise HTTPException(status_code=404, detail="Observación no encontrada")
        bitacora.registrar(conn, "eliminar_observacion", str(observacion_id))
        conn.commit()
    return {"ok": True}


# ---------- Importar datos de encargados desde Lista_Alumnos.xlsx ----------

def _clave(texto: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", sin_tildes(str(texto or "")).lower()).strip()


def _sin_adecuacion(texto: str) -> bool:
    """«», «No», «NO posee», «Ninguna», «Sin adecuación», «N/A» y similares significan que no hay adecuación."""
    c = _clave(texto)
    return not c or c in ("no", "ninguna", "ninguno", "n a", "0", "nulo") or c.startswith(("no ", "sin "))


@router.post("/estudiantes/importar-encargados")
async def importar_encargados(request: Request) -> dict[str, Any]:
    """
    Carga teléfono, encargado, dirección y adecuación desde una hoja como `Lista_Alumnos.xlsx`
    (una hoja por sección con encabezados «Cédula», «Cédula del encargado», «ADECUACIÓN»...). Empareja por cédula.
    """
    hojas = leer_hojas(await request.body())
    with database.get_db_context() as conn:
        por_cedula = {re.sub(r"\D", "", r["cedula"]): r["id"] for r in conn.execute("SELECT id, cedula FROM estudiantes")}
        actualizados, sin_pareja, hojas_usadas = 0, [], 0
        for nombre, filas in hojas:
            cab = next((i for i, f in enumerate(filas) if any(_clave(c) == "cedula del encargado" for c in f)), None)
            if cab is None:
                continue
            hojas_usadas += 1
            enc = [_clave(c) for c in filas[cab]]
            col = lambda *claves: next((i for i, t in enumerate(enc) if t in claves), None)
            c_ced = col("cedula")
            c_tel = col("telefono estudiante")
            c_enc = next((i for i, t in enumerate(enc) if t.startswith("apellidos") and "nombre" in t), None)
            c_encced, c_t1, c_t2 = col("cedula del encargado"), col("telefono 1 de contacto"), col("telefono 2 de contacto")
            c_dir, c_ad = col("direccion domicilio"), col("adecuacion")
            for f in filas[cab + 1:]:
                celda = lambda i: (f[i] if i is not None and i < len(f) else None)
                texto = lambda i: ("" if celda(i) is None else str(int(celda(i)) if isinstance(celda(i), float) and celda(i).is_integer() else celda(i))).strip()
                if not texto(c_ced):
                    continue
                eid = por_cedula.get(re.sub(r"\D", "", texto(c_ced)))
                if eid is None:
                    sin_pareja.append(texto(c_ced))
                    continue
                ad = texto(c_ad)
                tiene_ad = not _sin_adecuacion(ad)
                conn.execute(
                    "UPDATE estudiantes SET telefono = ?, encargado_nombre = ?, encargado_cedula = ?, encargado_telefono = ?, "
                    "encargado_telefono2 = ?, direccion = ?, adecuacion = ?, adecuacion_detalle = ? WHERE id = ?",
                    (texto(c_tel), texto(c_enc), texto(c_encced), texto(c_t1), texto(c_t2), texto(c_dir),
                     int(tiene_ad), ad if tiene_ad else "", eid))
                actualizados += 1
        if not hojas_usadas:
            raise HTTPException(status_code=400, detail="No encontré hojas con la columna «Cédula del encargado»")
        bitacora.registrar(conn, "importar_encargados", f"{actualizados} estudiantes")
        conn.commit()
    return {"ok": True, "actualizados": actualizados, "sin_pareja": sin_pareja}


# ---------- Alertas ----------

def calcular_alertas(conn, seccion: str | None = None, estudiante_id: int | None = None) -> list[dict[str, Any]]:
    """
    Estudiantes que requieren atención en las materias del período actual (ajustes):
    riesgo de reprobar (nota proyectada con lo calificado), ausencias sobre el umbral,
    actividades sin entrega y exámenes vinculados sin presentar.
    """
    ajustes = database.leer_ajustes(conn)
    periodo, umbral, minima = int(ajustes["periodo_actual"]), float(ajustes["umbral_ausencias"]), nota_minima(conn)
    sql, params = "SELECT * FROM materias WHERE periodo = ?", [periodo]
    if seccion:
        sql += " AND seccion = ?"
        params.append(seccion)
    materias = conn.execute(sql + " ORDER BY seccion, nombre", params).fetchall()
    estudiantes = {r["id"]: r for r in conn.execute(
        "SELECT id, nombre, apellido1, apellido2, seccion, adecuacion FROM estudiantes WHERE activo = 1"
        + (" AND id = ?" if estudiante_id else ""), [estudiante_id] if estudiante_id else [])}
    alertas: dict[int, list[dict[str, Any]]] = {}

    def agregar(eid, tipo, severidad, materia, detalle):
        alertas.setdefault(eid, []).append({"tipo": tipo, "severidad": severidad, "materia": materia, "detalle": detalle})

    for m in materias:
        pesos = pesos_de(conn, m["id"])
        asist = {a["estudiante_id"]: a for a in _resumen(conn, m)["estudiantes"]}
        lecciones = _resumen(conn, m)["lecciones_totales"]
        sin_entrega = {r["estudiante_id"]: r["n"] for r in conn.execute(
            "SELECT c.estudiante_id, COUNT(*) AS n FROM calificaciones c JOIN actividades a ON a.id = c.actividad_id "
            "WHERE a.materia_id = ? AND c.estado = 'sin_entrega' GROUP BY c.estudiante_id", (m["id"],))}
        examenes = [r["codigo"] for r in conn.execute(
            "SELECT v.codigo FROM examen_vinculos v LEFT JOIN examenes_config c ON c.codigo = v.codigo "
            "WHERE v.materia_id = ? AND COALESCE(c.habilitado, 1) = 1", (m["id"],))]
        presentados = {(r["estudiante_id"], r["codigo_examen"]) for r in conn.execute(
            "SELECT estudiante_id, codigo_examen FROM intentos WHERE fecha_fin IS NOT NULL AND anulado = 0")}
        for f in _filas(conn, m):
            eid = f["estudiante_id"]
            if eid not in estudiantes:
                continue
            calificados = [c for c in COMPONENTES if f[c] is not None]
            if calificados:
                posible = sum(pesos[c] for c in calificados)
                proyectada = sum(f[c] * pesos[c] / 100 for c in calificados) / posible * 100 if posible else 0
                if proyectada < minima:
                    agregar(eid, "riesgo", "alta" if f["completa"] else "media", m["nombre"],
                            f"Proyección {proyectada:.1f} (nota actual {f['nota_final']}); mínima {minima:g}")
            a = asist.get(eid)
            if lecciones and a and a["porcentaje_ausencias"] >= umbral:
                agregar(eid, "asistencia", "media", m["nombre"],
                        f"{a['porcentaje_ausencias']:.1f} % de ausencias injustificadas ({a['puntos']} de 5 puntos)")
            if sin_entrega.get(eid):
                agregar(eid, "pendientes", "media", m["nombre"], f"{sin_entrega[eid]} actividad(es) sin entrega")
            for codigo in examenes:
                if (eid, codigo) not in presentados:
                    agregar(eid, "examen", "media", m["nombre"], f"No ha presentado el examen {codigo}")
    orden = {"alta": 0, "media": 1}
    salida = [{
        "estudiante_id": eid, "nombre": _nombre_acta(estudiantes[eid]), "seccion": estudiantes[eid]["seccion"],
        "adecuacion": bool(estudiantes[eid]["adecuacion"]),
        "alertas": sorted(lista, key=lambda a: orden[a["severidad"]]),
    } for eid, lista in alertas.items()]
    return sorted(salida, key=lambda x: (min(orden[a["severidad"]] for a in x["alertas"]), -len(x["alertas"]), x["nombre"]))


@router.get("/alertas")
def listar_alertas(seccion: str | None = None) -> dict[str, Any]:
    with database.get_db_context() as conn:
        ajustes = database.leer_ajustes(conn)
        return {"ok": True, "periodo": int(ajustes["periodo_actual"]), "estudiantes": calcular_alertas(conn, seccion)}


# ---------- Cierre del curso lectivo ----------

class CierreIn(BaseModel):
    confirmacion: str
    nuevo_curso: str = Field(min_length=4, max_length=9)
    desactivar_secciones: list[str] = []


def _libro_cierre(conn) -> bytes:
    """Excel con las notas finales de todas las materias del curso que se cierra."""
    libro = Workbook()
    hoja = libro.active
    hoja.title = "Notas finales"
    hoja.append(["Sección", "Período", "Materia", "Id", "Nombre", *[ETIQUETAS[c] for c in COMPONENTES], "Nota final"])
    for m in conn.execute("SELECT * FROM materias ORDER BY seccion, periodo, nombre"):
        pesos = pesos_de(conn, m["id"])
        cedulas = {r["id"]: r["cedula"].replace("-", "") for r in conn.execute("SELECT id, cedula FROM estudiantes")}
        for f in _filas(conn, m):
            hoja.append([m["seccion"], m["periodo"], m["nombre"], cedulas[f["estudiante_id"]], _nombre_acta(f),
                         *[None if f[c] is None else round(f[c] * pesos[c] / 100, 2) for c in COMPONENTES], f["nota_final"]])
    salida = io.BytesIO()
    libro.save(salida)
    return salida.getvalue()


@router.get("/cierre/archivos")
def archivos_de_cierre() -> dict[str, Any]:
    carpeta = database.RESPALDOS_DIR
    archivos = sorted(p.name for p in carpeta.glob("cierre_*")) if carpeta.exists() else []
    return {"ok": True, "archivos": archivos, "carpeta": str(carpeta)}


@router.post("/cierre")
def cerrar_curso(datos: CierreIn) -> dict[str, Any]:
    """
    Cierra el curso lectivo: guarda una copia completa de la base y un Excel de notas finales en `respaldos/`
    y deja listo el siguiente curso (sin notas, asistencia, actividades, intentos ni observaciones).
    Los estudiantes se conservan; las secciones indicadas se desactivan (por ejemplo, las que egresan).
    """
    if datos.confirmacion.strip().upper() != "CERRAR":
        raise HTTPException(status_code=400, detail="Escribe CERRAR para confirmar")
    with database.get_db_context() as conn:
        curso = database.leer_ajustes(conn)["curso_lectivo"]
        if datos.nuevo_curso.strip() == curso:
            raise HTTPException(status_code=400, detail="El nuevo curso lectivo debe ser distinto del actual")
        carpeta = database.RESPALDOS_DIR
        carpeta.mkdir(parents=True, exist_ok=True)
        marca = datetime.now().strftime("%Y%m%d_%H%M%S")
        base = carpeta / f"cierre_{curso}_{marca}.sqlite"
        excel = carpeta / f"cierre_{curso}_{marca}_notas.xlsx"
        database.copiar_base(base)
        excel.write_bytes(_libro_cierre(conn))
        for tabla in ("calificaciones", "actividades", "asistencia", "sesiones", "notas", "publicaciones",
                      "observaciones", "intentos"):
            conn.execute(f"DELETE FROM {tabla}")
        desactivados = 0
        for seccion in datos.desactivar_secciones:
            desactivados += conn.execute("UPDATE estudiantes SET activo = 0 WHERE seccion = ?", (seccion,)).rowcount
        conn.executemany(
            "INSERT INTO ajustes (clave, valor) VALUES (?, ?) ON CONFLICT (clave) DO UPDATE SET valor = excluded.valor",
            [("curso_lectivo", datos.nuevo_curso.strip()), ("periodo_actual", "1")])
        bitacora.registrar(conn, "cierre_curso", f"{curso} -> {datos.nuevo_curso.strip()} · copia {base.name}")
        conn.commit()
    return {"ok": True, "copia": base.name, "excel": excel.name, "desactivados": desactivados, "carpeta": str(carpeta)}
