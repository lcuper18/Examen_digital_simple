"""
Examenes routes - Get exam by code.
"""
import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

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


@router.get("/examen/{codigo}")
async def get_examen(codigo: str) -> JSONResponse:
    """
    Obtiene las preguntas de un examen por su código.

    Args:
        codigo: Código del examen (CCS01, EMP01, ADM01, RED01, PER01).

    Returns:
        JSONResponse: Datos del examen.

    Raises:
        HTTPException: Si el código no existe o el archivo no se encuentra.
    """
    # Cargar mapeo de códigos
    codigos = load_codigos()

    if codigo not in codigos:
        raise HTTPException(status_code=404, detail=f"Código de examen '{codigo}' no encontrado")

    examen_info = codigos[codigo]

    # Cargar datos del examen
    examen_data = load_examen_data(examen_info["archivo"])

    # Extraer preguntas
    preguntas = examen_data["examen"]["preguntas"]

    # Construir respuesta
    response_data = {
        "titulo": examen_data["examen"]["titulo"],
        "institucion": examen_data["examen"].get("institucion", ""),
        "nivel": examen_data["examen"].get("nivel", ""),
        "especialidad": examen_data["examen"].get("especialidad", ""),
        "profesor": examen_data["examen"].get("profesor", ""),
        "instrucciones": examen_data["examen"].get("instrucciones", ""),
        "total_preguntas": len(preguntas),
        "duracion_minutos": examen_info.get("duracion_minutos", 60),
        "preguntas": preguntas,
    }

    return JSONResponse(content={
        "ok": True,
        "examen": response_data
    })
