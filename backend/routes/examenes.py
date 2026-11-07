"""
Examenes routes - Iniciar un examen (sin respuestas correctas) y enviarlo para calificar.
"""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import secrets

from backend import barajado, bitacora, database, security

router = APIRouter(prefix="/api", tags=["examenes"])

# Rutas de datos - desde la raíz del proyecto
PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
EXAMENES_DIR = DATA_DIR / "examenes"
CODIGOS_FILE = DATA_DIR / "codigos.json"


def load_codigos() -> dict[str, dict[str, str]]:
    """
    Carga el archivo codigos.json con el mapeo de códigos a exámenes.

    Returns:
        dict: Mapeo de código -> {nombre, archivo, duracion_minutos}
    """
    if not CODIGOS_FILE.exists():
        raise FileNotFoundError(
            f"Archivo codigos.json no encontrado en {CODIGOS_FILE}"
        )
    with open(CODIGOS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def load_examen_data(archivo: str) -> dict[str, Any]:
    """
    Carga los datos de un archivo de examen JSON.

    Args:
        archivo: Nombre del archivo JSON del examen.

    Returns:
        dict: Datos del examen procesados.
    """
    examen_path = EXAMENES_DIR / archivo
    if not examen_path.exists():
        raise FileNotFoundError(f"Archivo de examen no encontrado: {archivo}")

    with open(examen_path, "r", encoding="utf-8") as f:
        return json.load(f)


# Tolerancia (segundos) para envíos que llegan justo al vencer el tiempo
GRACE_SECONDS = 120


class EnviarRequest(BaseModel):
    """Respuestas del estudiante: número de pregunta -> letra elegida (a, b, c)."""
    respuestas: dict[str, str] = {}
    incidencias: int = 0  # veces que el estudiante salió de la pestaña del examen


def _get_examen(codigo: str) -> tuple[dict[str, str], dict[str, Any]]:
    codigos = load_codigos()
    if codigo not in codigos:
        raise HTTPException(status_code=404, detail=f"Código de examen '{codigo}' no encontrado")
    info = codigos[codigo]
    return info, load_examen_data(info["archivo"])["examen"]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def parse_fecha(texto: str) -> datetime:
    """Interpreta una fecha ISO (acepta 'Z'); sin zona horaria se asume UTC."""
    fecha = datetime.fromisoformat(texto.replace("Z", "+00:00"))
    return fecha if fecha.tzinfo else fecha.replace(tzinfo=timezone.utc)


def _remaining_seconds(fecha_inicio: str, duracion_minutos: int) -> int:
    fin = parse_fecha(fecha_inicio) + timedelta(minutes=duracion_minutos)
    return int((fin - _now()).total_seconds())


def minutos_totales(info: dict[str, Any], intento) -> int:
    """Duración del examen más el tiempo extra concedido por el docente a este intento."""
    return info.get("duracion_minutos", 60) + (intento["minutos_extra"] or 0)


def filtrar_respuestas(preguntas: list[dict[str, Any]], semilla: int, respuestas: dict[str, str]):
    """Descarta respuestas de preguntas o letras inexistentes. Devuelve (válidas, barajadas por número)."""
    barajadas = {str(p["numero"]): p for p in barajado.barajar(preguntas, semilla)}
    validas = {
        str(n): str(letra).lower() for n, letra in respuestas.items()
        if str(n) in barajadas and str(letra).lower() in barajadas[str(n)]["opciones"]
    }
    return validas, barajadas


def calificar(preguntas: list[dict[str, Any]], semilla: int, respuestas: dict[str, str]) -> tuple[dict[str, str], int]:
    """Califica respuestas (letras tal como las vio el estudiante). Devuelve (respuestas válidas, aciertos)."""
    validas, barajadas = filtrar_respuestas(preguntas, semilla, respuestas)
    aciertos = sum(
        1 for n, letra in validas.items() if letra == barajado.letra_correcta_mostrada(barajadas[n])
    )
    return validas, aciertos


def _config(conn, codigo: str):
    return conn.execute("SELECT * FROM examenes_config WHERE codigo = ?", (codigo,)).fetchone()


def verificar_disponibilidad(conn, codigo: str, seccion: str) -> None:
    """Lanza 403 si el examen no está habilitado para iniciar ahora o para esta sección."""
    config = _config(conn, codigo)
    if config is None:
        return
    if not config["habilitado"]:
        raise HTTPException(status_code=403, detail="Este examen no está habilitado")
    ahora = _now()
    if config["desde"] and ahora < parse_fecha(config["desde"]):
        raise HTTPException(status_code=403, detail="Este examen aún no está disponible")
    if config["hasta"] and ahora > parse_fecha(config["hasta"]):
        raise HTTPException(status_code=403, detail="El plazo para iniciar este examen terminó")
    secciones = [x.strip() for x in (config["secciones"] or "").split(",") if x.strip()]
    if secciones and seccion not in secciones:
        raise HTTPException(status_code=403, detail="Este examen no está habilitado para tu sección")


def _intento(cursor, estudiante_id: int, codigo: str):
    return cursor.execute(
        "SELECT id, fecha_inicio, fecha_fin, semilla, anulado, minutos_extra, respuestas_parciales_json "
        "FROM intentos WHERE estudiante_id = ? AND codigo_examen = ?",
        (estudiante_id, codigo),
    ).fetchone()


def _verificar_abierto(intento, info: dict[str, Any]) -> None:
    if intento["anulado"]:
        raise HTTPException(status_code=409, detail="Tu intento fue anulado por el docente")
    if intento["fecha_fin"] is not None:
        raise HTTPException(status_code=409, detail="Ya enviaste este examen")
    if _remaining_seconds(intento["fecha_inicio"], minutos_totales(info, intento)) <= -GRACE_SECONDS:
        raise HTTPException(status_code=403, detail="El tiempo del examen se agotó")


@router.post("/examen/{codigo}/iniciar")
def iniciar_examen(codigo: str, estudiante_id: int = Depends(security.estudiante_actual)) -> JSONResponse:
    """
    Inicia (o retoma) el intento del estudiante autenticado. Devuelve las preguntas
    SIN la respuesta correcta, el tiempo restante calculado por el servidor y las
    respuestas guardadas si retoma un intento.
    """
    codigo = codigo.upper()
    info, examen = _get_examen(codigo)
    preguntas = examen["preguntas"]

    with database.get_db_context() as conn:
        cursor = conn.cursor()
        intento = _intento(cursor, estudiante_id, codigo)

        if intento is None:
            seccion = conn.execute("SELECT seccion FROM estudiantes WHERE id = ?", (estudiante_id,)).fetchone()[0]
            verificar_disponibilidad(conn, codigo, seccion)
            fecha_inicio = _now().isoformat()
            semilla = secrets.randbits(31) + 1
            cursor.execute(
                "INSERT INTO intentos (estudiante_id, codigo_examen, respuestas_json, "
                "puntuacion, total, fecha_inicio, semilla) VALUES (?, ?, '{}', 0, ?, ?, ?)",
                (estudiante_id, codigo, len(preguntas), fecha_inicio, semilla),
            )
            conn.commit()
            minutos = info.get("duracion_minutos", 60)
            guardadas = {}
        else:
            _verificar_abierto(intento, info)
            fecha_inicio, semilla = intento["fecha_inicio"], intento["semilla"]
            minutos = minutos_totales(info, intento)
            guardadas = json.loads(intento["respuestas_parciales_json"] or "{}")

    restante = _remaining_seconds(fecha_inicio, minutos)
    return JSONResponse(content={
        "ok": True,
        "examen": {
            "titulo": examen["titulo"],
            "institucion": examen.get("institucion", ""),
            "nivel": examen.get("nivel", ""),
            "especialidad": examen.get("especialidad", ""),
            "profesor": examen.get("profesor", ""),
            "instrucciones": examen.get("instrucciones", ""),
            "total_preguntas": len(preguntas),
            "duracion_minutos": info.get("duracion_minutos", 60),
            "segundos_restantes": max(restante, 0),
            "respuestas_guardadas": guardadas,
            "preguntas": [
                {k: p[k] for k in ("numero", "tema", "pregunta", "opciones")}
                for p in barajado.barajar(preguntas, semilla)
            ],
        },
    })


@router.put("/examen/{codigo}/progreso")
def guardar_progreso(
    codigo: str,
    request: EnviarRequest,
    estudiante_id: int = Depends(security.estudiante_actual),
) -> JSONResponse:
    """Guarda las respuestas parciales y devuelve el tiempo restante (incluye tiempo extra)."""
    codigo = codigo.upper()
    info, examen = _get_examen(codigo)

    with database.get_db_context() as conn:
        cursor = conn.cursor()
        intento = _intento(cursor, estudiante_id, codigo)
        if intento is None:
            raise HTTPException(status_code=404, detail="No has iniciado este examen")
        _verificar_abierto(intento, info)
        validas, _ = filtrar_respuestas(examen["preguntas"], intento["semilla"], request.respuestas)
        cursor.execute(
            "UPDATE intentos SET respuestas_parciales_json = ?, incidencias = MAX(incidencias, ?) WHERE id = ?",
            (json.dumps(validas), max(request.incidencias, 0), intento["id"]),
        )
        conn.commit()
        restante = _remaining_seconds(intento["fecha_inicio"], minutos_totales(info, intento))

    return JSONResponse(content={"ok": True, "segundos_restantes": max(restante, 0)})


@router.post("/examen/{codigo}/enviar")
def enviar_examen(
    codigo: str,
    request: EnviarRequest,
    estudiante_id: int = Depends(security.estudiante_actual),
) -> JSONResponse:
    """Califica en el servidor y cierra el intento. No devuelve nota ni respuestas correctas."""
    codigo = codigo.upper()
    info, examen = _get_examen(codigo)
    preguntas = examen["preguntas"]

    with database.get_db_context() as conn:
        cursor = conn.cursor()
        intento = _intento(cursor, estudiante_id, codigo)
        if intento is None:
            raise HTTPException(status_code=404, detail="No has iniciado este examen")
        _verificar_abierto(intento, info)

        respuestas, puntuacion = calificar(preguntas, intento["semilla"], request.respuestas)
        cursor.execute(
            "UPDATE intentos SET respuestas_json = ?, puntuacion = ?, total = ?, fecha_fin = ?, "
            "incidencias = MAX(incidencias, ?) WHERE id = ?",
            (json.dumps(respuestas), puntuacion, len(preguntas), _now().isoformat(),
             max(request.incidencias, 0), intento["id"]),
        )
        conn.commit()

    return JSONResponse(content={"ok": True, "intento_id": intento["id"]})


# ---------- Configuración de exámenes (docente) ----------

docente_router = APIRouter(
    prefix="/api/docente", tags=["examenes-docente"], dependencies=[Depends(security.require_docente)]
)


@docente_router.get("/examenes")
def listar_examenes() -> dict[str, Any]:
    """Catálogo de exámenes con su configuración y conteo de intentos."""
    codigos = load_codigos()
    with database.get_db_context() as conn:
        configs = {r["codigo"]: r for r in conn.execute("SELECT * FROM examenes_config")}
        conteos = {
            r["codigo_examen"]: r for r in conn.execute(
                "SELECT codigo_examen, "
                "SUM(fecha_fin IS NOT NULL AND anulado = 0) AS enviados, "
                "SUM(fecha_fin IS NULL AND anulado = 0) AS en_curso, "
                "SUM(anulado) AS anulados FROM intentos GROUP BY codigo_examen"
            )
        }
    examenes = []
    for codigo, info in codigos.items():
        c, n = configs.get(codigo), conteos.get(codigo)
        examenes.append({
            "codigo": codigo,
            "nombre": info["nombre"],
            "duracion_minutos": info.get("duracion_minutos", 60),
            "habilitado": bool(c["habilitado"]) if c else True,
            "desde": c["desde"] if c else None,
            "hasta": c["hasta"] if c else None,
            "secciones": [x for x in (c["secciones"] or "").split(",") if x] if c else [],
            "materia_id": c["materia_id"] if c else None,
            "componente": c["componente"] if c else None,
            "enviados": (n["enviados"] or 0) if n else 0,
            "en_curso": (n["en_curso"] or 0) if n else 0,
            "anulados": (n["anulados"] or 0) if n else 0,
        })
    return {"ok": True, "examenes": examenes}


class ConfigExamen(BaseModel):
    habilitado: bool = True
    desde: str | None = None
    hasta: str | None = None
    secciones: list[str] = []
    materia_id: int | None = None      # materia donde se importa la nota de este examen
    componente: str | None = None      # "prueba01" | "prueba02"


@docente_router.put("/examenes/{codigo}")
def configurar_examen(codigo: str, request: ConfigExamen) -> dict[str, Any]:
    codigo = codigo.upper()
    if codigo not in load_codigos():
        raise HTTPException(status_code=404, detail="Código de examen no encontrado")
    try:
        desde = parse_fecha(request.desde) if request.desde else None
        hasta = parse_fecha(request.hasta) if request.hasta else None
    except ValueError:
        raise HTTPException(status_code=400, detail="Fecha no válida")
    if desde and hasta and hasta <= desde:
        raise HTTPException(status_code=400, detail="La fecha final debe ser posterior a la inicial")
    if (request.materia_id is None) != (request.componente is None):
        raise HTTPException(status_code=400, detail="Indica la materia y el componente, o ninguno")
    if request.componente not in (None, "prueba01", "prueba02"):
        raise HTTPException(status_code=400, detail="componente debe ser prueba01 o prueba02")
    with database.get_db_context() as conn:
        if request.materia_id is not None and not conn.execute(
                "SELECT 1 FROM materias WHERE id = ?", (request.materia_id,)).fetchone():
            raise HTTPException(status_code=404, detail="Materia no encontrada")
        conn.execute(
            "INSERT INTO examenes_config (codigo, habilitado, desde, hasta, secciones, materia_id, componente) "
            "VALUES (?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT (codigo) DO UPDATE SET habilitado = excluded.habilitado, desde = excluded.desde, "
            "hasta = excluded.hasta, secciones = excluded.secciones, "
            "materia_id = excluded.materia_id, componente = excluded.componente",
            (codigo, int(request.habilitado), desde.isoformat() if desde else None,
             hasta.isoformat() if hasta else None, ",".join(s.strip() for s in request.secciones if s.strip()),
             request.materia_id, request.componente),
        )
        bitacora.registrar(
            conn, "configurar_examen",
            f"{codigo}: {'habilitado' if request.habilitado else 'deshabilitado'}"
            + (f", secciones {','.join(request.secciones)}" if request.secciones else ""),
        )
        conn.commit()
    return {"ok": True}
