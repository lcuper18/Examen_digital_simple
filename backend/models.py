"""
Models package - Pydantic models for request/response validation.
"""
from .auth import LoginRequest, LoginResponse, VerificarDocenteRequest, VerificarDocenteResponse
from .intentos import IntentoRequest

__all__ = [
    "LoginRequest",
    "LoginResponse",
    "VerificarDocenteRequest",
    "VerificarDocenteResponse",
    "IntentoRequest",
]
