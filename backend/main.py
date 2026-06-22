"""
Examen Digital Simple v2 - Backend FastAPI
Plataforma de examen digital con login de estudiantes y registro de intentos.
"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend import database
from backend.routes import auth_router, examenes_router, intentos_router

# Ruta base del proyecto
PROJECT_ROOT = Path(__file__).parent.parent

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


@app.get("/")
async def root():
    """Sirve el archivo index.html principal."""
    return FileResponse(str(FRONTEND_DIR / "index.html"))


@app.on_event("startup")
async def startup_event():
    """Inicializa la base de datos al arrancar el servidor."""
    inserted = database.init_db()
    if inserted > 0:
        print(f"[INFO] Base de datos poblada con {inserted} estudiantes")


if __name__ == "__main__":
    import uvicorn

    # Inicializar BD antes de iniciar servidor
    inserted = database.init_db()
    if inserted > 0:
        print(f"[INFO] Base de datos poblada con {inserted} estudiantes")

    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
