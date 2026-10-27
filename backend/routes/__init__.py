"""
Routes package - API route modules.
"""
from .auth import router as auth_router
from .examenes import router as examenes_router
from .intentos import router as intentos_router
from .notas import router as notas_router

__all__ = ["auth_router", "examenes_router", "intentos_router", "notas_router"]
