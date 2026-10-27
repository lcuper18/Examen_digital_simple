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

from backend import barajado, database, security

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


def _remaining_seconds(fecha_inicio: str, duracion_minutos: int) -> int:
    inicio = datetime.fromisoformat(fecha_inicio)
    fin = inicio + timedelta(minutes=duracion_minutos)
    return int((fin - _now()).total_seconds())


@router.post("/examen/{codigo}/iniciar")
def iniciar_examen(codigo: str, estudiante_id: int = Depends(security.estudiante_actual)) -> JSONResponse:
    """
    Inicia (o retoma) el intento del estudiante autenticado. Devuelve las preguntas
    SIN la respuesta correcta y el tiempo restante calculado por el servidor.
    """
    codigo = codigo.upper()
    info, examen = _get_examen(codigo)
    duracion = info.get("duracion_minutos", 60)
    preguntas = examen["preguntas"]

    with database.get_db_context() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, fecha_inicio, fecha_fin, semilla FROM intentos "
            "WHERE estudiante_id = ? AND codigo_examen = ?",
            (estudiante_id, codigo),
        )
        intento = cursor.fetchone()

        if intento is None:
            fecha_inicio = _now().isoformat()
            semilla = secrets.randbits(31) + 1
            cursor.execute(
                "INSERT INTO intentos (estudiante_id, codigo_examen, respuestas_json, "
                "puntuacion, total, fecha_inicio, semilla) VALUES (?, ?, '{}', 0, ?, ?, ?)",
                (estudiante_id, codigo, len(preguntas), fecha_inicio, semilla),
            )
            conn.commit()
        elif intento["fecha_fin"] is not None:
            raise HTTPException(status_code=409, detail="Ya enviaste este examen")
        else:
            fecha_inicio = intento["fecha_inicio"]
            semilla = intento["semilla"]

    restante = _remaining_seconds(fecha_inicio, duracion)
    if restante <= -GRACE_SECONDS:
        raise HTTPException(status_code=403, detail="El tiempo del examen se agotó")

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
            "duracion_minutos": duracion,
            "segundos_restantes": max(restante, 0),
            "preguntas": [
                {k: p[k] for k in ("numero", "tema", "pregunta", "opciones")}
                for p in barajado.barajar(preguntas, semilla)
            ],
        },
    })


@router.post("/examen/{codigo}/enviar")
def enviar_examen(
    codigo: str,
    request: EnviarRequest,
    estudiante_id: int = Depends(security.estudiante_actual),
) -> JSONResponse:
    """Califica en el servidor y cierra el intento. No devuelve nota ni respuestas correctas."""
    codigo = codigo.upper()
    info, examen = _get_examen(codigo)
    duracion = info.get("duracion_minutos", 60)
    preguntas = examen["preguntas"]

    with database.get_db_context() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, fecha_inicio, fecha_fin, semilla FROM intentos "
            "WHERE estudiante_id = ? AND codigo_examen = ?",
            (estudiante_id, codigo),
        )
        intento = cursor.fetchone()
        if intento is None:
            raise HTTPException(status_code=404, detail="No has iniciado este examen")
        if intento["fecha_fin"] is not None:
            raise HTTPException(status_code=409, detail="Ya enviaste este examen")
        if _remaining_seconds(intento["fecha_inicio"], duracion) <= -GRACE_SECONDS:
            raise HTTPException(status_code=403, detail="El tiempo del examen se agotó")

        barajadas = {
            str(p["numero"]): p for p in barajado.barajar(preguntas, intento["semilla"])
        }
        respuestas = {
            n: letra.lower() for n, letra in request.respuestas.items()
            if n in barajadas and letra.lower() in barajadas[n]["opciones"]
        }
        puntuacion = sum(
            1 for n, letra in respuestas.items()
            if letra == barajado.letra_correcta_mostrada(barajadas[n])
        )

        cursor.execute(
            "UPDATE intentos SET respuestas_json = ?, puntuacion = ?, total = ?, fecha_fin = ?, "
            "incidencias = ? WHERE id = ?",
            (json.dumps(respuestas), puntuacion, len(preguntas), _now().isoformat(),
             max(request.incidencias, 0), intento["id"]),
        )
        conn.commit()

    return JSONResponse(content={"ok": True, "intento_id": intento["id"]})
