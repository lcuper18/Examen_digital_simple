"""
Examen Digital Simple v2 - Backend FastAPI
Plataforma de examen digital con login de estudiantes y registro de intentos.
"""
import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend import database
from backend.routes import (
    auth_router, bitacora_router, estudiantes_router, examenes_docente_router,
    examenes_router, intentos_router, notas_router, reportes_router,
    ajustes_router, asistencia_router, config_router,
)

# Ruta base del proyecto
PROJECT_ROOT = Path(__file__).parent.parent

@asynccontextmanager
async def lifespan(_: FastAPI):
    """Inicializa la base de datos al arrancar el servidor."""
    inserted = database.init_db()
    if inserted > 0:
        print(f"[INFO] Base de datos poblada con {inserted} estudiantes")
    tarea = asyncio.create_task(_respaldo_diario())
    yield
    tarea.cancel()


async def _respaldo_diario() -> None:
    """Un respaldo por día (al arrancar y cada hora mientras el servidor siga encendido)."""
    while True:
        try:
            archivo = await asyncio.to_thread(database.respaldar)
            if archivo:
                print(f"[INFO] Respaldo creado: {archivo.name}")
        except Exception as error:  # un respaldo fallido no debe tumbar el servidor
            print(f"[AVISO] No se pudo respaldar la base de datos: {error}")
        await asyncio.sleep(3600)


# Crear aplicación FastAPI (el frontend se sirve desde el mismo origen: no se requiere CORS)
app = FastAPI(
    title="Examen Digital Simple v2",
    description="API para plataforma de examen digital",
    version="2.0.0",
    lifespan=lifespan,
)

# Montar archivos estáticos desde frontend/
FRONTEND_DIR = PROJECT_ROOT / "frontend"
STATIC_DIR = FRONTEND_DIR / "static"
FONTS_DIR = FRONTEND_DIR / "fonts"
JS_DIR = FRONTEND_DIR / "js"
CSS_DIR = FRONTEND_DIR / "css"

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/fonts", StaticFiles(directory=str(FONTS_DIR)), name="fonts")
app.mount("/js", StaticFiles(directory=str(JS_DIR)), name="js")
app.mount("/css", StaticFiles(directory=str(CSS_DIR)), name="css")

# Incluir routers
app.include_router(auth_router)
app.include_router(examenes_router)
app.include_router(intentos_router)
app.include_router(notas_router)
app.include_router(estudiantes_router)
app.include_router(bitacora_router)
app.include_router(examenes_docente_router)
app.include_router(reportes_router)
app.include_router(ajustes_router)
app.include_router(asistencia_router)
app.include_router(config_router)


@app.get("/docente")
async def panel_docente():
    """Sirve el panel del docente (resultados y notas)."""
    return FileResponse(str(FRONTEND_DIR / "docente.html"))


@app.get("/")
async def root():
    """Sirve el archivo index.html principal."""
    return FileResponse(str(FRONTEND_DIR / "index.html"))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="0.0.0.0", port=int(os.environ.get("PORT", "8001")))
