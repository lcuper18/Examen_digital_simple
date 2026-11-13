"""
Lectiva - Backend FastAPI
Plataforma de gestión educativa: exámenes, asistencia, actividades, notas, reportes e informes.
"""
import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from backend import database, respaldo_externo
from backend.version import VERSION
from backend.routes import (
    auth_router, bitacora_router, estudiantes_router, examenes_docente_router,
    examenes_router, intentos_router, notas_router, reportes_router,
    actividades_router, ajustes_router, informes_router, portal_router, seguimiento_router, asistencia_router, config_router,
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
        try:
            # Copia externa (si el docente eligió una carpeta): cada hora, para que incluya el trabajo del día
            externo = await asyncio.to_thread(respaldo_externo.respaldar_externo)
            if externo.get("motivo") == "error":
                print(f"[AVISO] Copia de respaldo externa: {externo['error']}")
        except Exception as error:
            print(f"[AVISO] Copia de respaldo externa: {error}")
        await asyncio.sleep(3600)


# Crear aplicación FastAPI (el frontend se sirve desde el mismo origen: no se requiere CORS)
app = FastAPI(
    title="Lectiva",
    description="API de Lectiva, plataforma de gestión educativa",
    version=VERSION,
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

LIMITE_CUERPO = 10 * 1024 * 1024  # ninguna petición de Lectiva necesita más: las listas y hojas pesan unos KB


@app.middleware("http")
async def limitar_tamano(request, call_next):
    """Rechaza de entrada (413) las peticiones con un cuerpo enorme, antes de leerlas o interpretarlas."""
    declarado = request.headers.get("content-length")
    if declarado and declarado.isdigit() and int(declarado) > LIMITE_CUERPO:
        return JSONResponse(status_code=413, content={"detail": "La solicitud es demasiado grande (máximo 10 MB)"})
    return await call_next(request)


@app.middleware("http")
async def revalidar_interfaz(request, call_next):
    """El navegador revalida CSS, JS y páginas en cada carga (usa ETag, no descarga si no cambió).
    Sin esto un CSS viejo en caché se combina con HTML/JS nuevos y la interfaz sale sin estilos."""
    respuesta = await call_next(request)
    ruta = request.url.path
    if ruta in ("/", "/docente") or ruta.startswith(("/css/", "/js/")):
        respuesta.headers["Cache-Control"] = "no-cache"
    return respuesta


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
app.include_router(actividades_router)
app.include_router(informes_router)
app.include_router(portal_router)
app.include_router(seguimiento_router)
app.include_router(config_router)


@app.get("/manifest.webmanifest")
async def manifiesto():
    """Manifiesto para añadir Lectiva a la pantalla de inicio del celular (tiene que estar en la raíz para cubrir toda la app)."""
    return FileResponse(str(STATIC_DIR / "manifest.webmanifest"), media_type="application/manifest+json")


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

    uvicorn.run("backend.main:app", host="0.0.0.0", port=int(os.environ.get("PORT", "8090")))
