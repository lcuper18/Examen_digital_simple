"""
Backend de Lectiva, plataforma de gestión educativa.
"""
from . import database
from .routes import auth_router, examenes_router, intentos_router

__all__ = ["database", "auth_router", "examenes_router", "intentos_router"]
