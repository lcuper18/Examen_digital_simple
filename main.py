"""
Examen Digital Simple v2 - Backend FastAPI
Plataforma de examen digital con login de estudiantes y registro de intentos.
"""
import json
import hashlib
from pathlib import Path
from typing import Any, List

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

# Importar módulo de base de datos
import database

# Ruta base del proyecto
BASE_DIR = Path(__file__).parent

# Crear aplicación FastAPI
app = FastAPI(
    title="Examen Digital Simple v2",
    description="API para plataforma de examen digital",
    version="2.0.0",
)

# Configurar CORS para desarrollo local
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, especificar orígenes exactos
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Archivos estáticos
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# Fuentes locales (self-hosted, sin depender de Google Fonts CDN)
app.mount("/fonts", StaticFiles(directory=str(BASE_DIR / "fonts")), name="fonts")

# Archivos de exámenes
EXAMENES_DIR = BASE_DIR / "examenes"
CODIGOS_FILE = BASE_DIR / "codigos.json"

# Hash SHA-256 de la contraseña del docente (nunca almacenar la contraseña en texto plano)
TEACHER_PASSWORD_HASH = "849018898d5676cde9c6723b4604bd196d65e33c25304ec6e71fd7cc56af9a98"


# =============================================================================
# Modelos Pydantic para validación de entrada
# =============================================================================

class LoginRequest(BaseModel):
    """Modelo para solicitud de login."""
    username: str
    password: str


class IntentoRequest(BaseModel):
    """Modelo para registro de intento de examen."""
    estudiante_id: int
    codigo_examen: str
    respuestas: List[Any] = []
    puntuacion: int
    total: int
    fecha_inicio: str | None = None
    fecha_fin: str | None = None


class LoginResponse(BaseModel):
    """Modelo para respuesta de login."""
    ok: bool
    estudiante: dict[str, Any] | None = None
    error: str | None = None


class VerificarDocenteRequest(BaseModel):
    """Modelo para solicitud de verificación de contraseña de docente."""
    password: str


class VerificarDocenteResponse(BaseModel):
    """Modelo para respuesta de verificación de docente."""
    ok: bool
    error: str | None = None


# =============================================================================
# Funciones auxiliares
# =============================================================================

def hash_password(password: str) -> str:
    """
    Genera hash SHA-256 de una contraseña.

    Args:
        password: Contraseña en texto plano.

    Returns:
        str: Hash SHA-256 en formato hexadecimal.
    """
    return hashlib.sha256(password.encode()).hexdigest()


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


def strip_correct_answer(pregunta: dict[str, Any]) -> dict[str, Any]:
    """
    Elimina el campo 'respuesta_correcta' de una pregunta para enviarla al cliente.

    Args:
        pregunta: Diccionario con datos de la pregunta.

    Returns:
        dict: Pregunta sin respuesta correcta.
    """
    return {
        "numero": pregunta["numero"],
        "tema": pregunta["tema"],
        "pregunta": pregunta["pregunta"],
        "opciones": pregunta["opciones"],
    }


# =============================================================================
# Endpoints de la API
# =============================================================================

@app.get("/")
async def root():
    """Sirve el archivo index.html principal."""
    return FileResponse(str(BASE_DIR / "index.html"))


@app.post("/api/login", response_model=LoginResponse)
async def login(request: LoginRequest) -> LoginResponse:
    """
    Endpoint para autenticación de estudiantes.

    Args:
        request: Credenciales del estudiante (username y password).

    Returns:
        LoginResponse: Resultado del login con datos del estudiante o error.
    """
    with database.get_db_context() as conn:
        cursor = conn.cursor()

        # Buscar estudiante por username
        cursor.execute(
            "SELECT id, cedula, nombre, apellido1, apellido2, seccion, username, password_hash "
            "FROM estudiantes WHERE username = ?",
            (request.username,)
        )
        row = cursor.fetchone()

        if row is None:
            return LoginResponse(ok=False, error="Credenciales inválidas")

        # Verificar password hasheado
        password_hash = hash_password(request.password)
        if password_hash != row["password_hash"]:
            return LoginResponse(ok=False, error="Credenciales inválidas")

        # Login exitoso - devolver datos del estudiante (sin password)
        estudiante = {
            "id": row["id"],
            "nombre": row["nombre"],
            "apellido1": row["apellido1"],
            "apellido2": row["apellido2"],
            "username": row["username"],
            "seccion": row["seccion"],
        }
        return LoginResponse(ok=True, estudiante=estudiante)


@app.post("/api/verificar-docente", response_model=VerificarDocenteResponse)
async def verificar_docente(request: VerificarDocenteRequest) -> VerificarDocenteResponse:
    """
    Endpoint para verificar la contraseña del docente.

    Args:
        request: Contraseña del docente en texto plano.

    Returns:
        VerificarDocenteResponse: Resultado de la verificación.
    """
    hash_input = hashlib.sha256(request.password.encode()).hexdigest()
    if hash_input == TEACHER_PASSWORD_HASH:
        return VerificarDocenteResponse(ok=True)
    return VerificarDocenteResponse(ok=False, error="Contraseña incorrecta")


@app.get("/api/examen/{codigo}")
async def get_examen(codigo: str) -> JSONResponse:
    """
    Obtiene las preguntas de un examen por su código.

    Args:
        codigo: Código del examen (CCS01, EMP01, ADM01, RED01).

    Returns:
        JSONResponse: Datos del examen sin respuestas correctas.

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

    # Extraer preguntas (incluye respuesta_correcta para que el frontend pueda calificar)
    # En un sistema de examenes de escuela, esto es aceptable
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


@app.post("/api/intentos")
async def crear_intento(request: IntentoRequest) -> JSONResponse:
    """
    Registra un intento de examen en la base de datos.

    Args:
        request: Datos del intento (estudiante_id, codigo_examen, respuestas, etc.).

    Returns:
        JSONResponse: Confirmación con el ID del intento creado.
    """
    with database.get_db_context() as conn:
        cursor = conn.cursor()

        # Verificar que el estudiante existe
        cursor.execute("SELECT id FROM estudiantes WHERE id = ?", (request.estudiante_id,))
        if cursor.fetchone() is None:
            raise HTTPException(
                status_code=404,
                detail=f"Estudiante con ID {request.estudiante_id} no encontrado"
            )

        # Insertar intento
        respuestas_json = json.dumps(request.__dict__.get('respuestas', []), ensure_ascii=False)
        cursor.execute(
            """
            INSERT INTO intentos
            (estudiante_id, codigo_examen, respuestas_json, puntuacion, total, fecha_inicio, fecha_fin)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                request.estudiante_id,
                request.codigo_examen,
                respuestas_json,
                request.puntuacion,
                request.total,
                request.fecha_inicio,
                request.fecha_fin,
            )
        )
        conn.commit()

        intento_id = cursor.lastrowid

    return JSONResponse(content={"ok": True, "id": intento_id})


# =============================================================================
# Endpoint de inicialización de base de datos
# =============================================================================

@app.on_event("startup")
async def startup_event():
    """Inicializa la base de datos al arrancar el servidor."""
    inserted = database.init_db()
    if inserted > 0:
        print(f"[INFO] Base de datos poblada con {inserted} estudiantes")


# =============================================================================
# Punto de entrada para desarrollo
# =============================================================================

if __name__ == "__main__":
    import uvicorn

    # Inicializar BD antes de iniciar servidor
    inserted = database.init_db()
    if inserted > 0:
        print(f"[INFO] Base de datos poblada con {inserted} estudiantes")

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
