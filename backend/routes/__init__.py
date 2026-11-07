"""
Routes package - API route modules.
"""
from .auth import router as auth_router
from .examenes import docente_router as examenes_docente_router
from .examenes import router as examenes_router
from .intentos import router as intentos_router
from .notas import router as notas_router
from .reportes import router as reportes_router
from .estudiantes import router as estudiantes_router
from .bitacora import router as bitacora_router
from .ajustes import router as ajustes_router
from .asistencia import router as asistencia_router
from .actividades import router as actividades_router
from .ajustes import publico as config_router

__all__ = ["auth_router", "examenes_router", "intentos_router", "notas_router",
           "estudiantes_router", "bitacora_router", "examenes_docente_router",
           "reportes_router", "ajustes_router", "config_router", "asistencia_router", "actividades_router"]
