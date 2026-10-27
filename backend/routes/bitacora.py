"""
Bitácora routes - Consulta del registro de acciones del docente.
"""
from typing import Any

from fastapi import APIRouter, Depends

from backend import database, security

router = APIRouter(
    prefix="/api/docente", tags=["bitacora"], dependencies=[Depends(security.require_docente)]
)


@router.get("/bitacora")
def listar_bitacora(limite: int = 200) -> dict[str, Any]:
    with database.get_db_context() as conn:
        filas = conn.execute(
            "SELECT id, fecha, accion, detalle FROM bitacora ORDER BY id DESC LIMIT ?",
            (min(max(limite, 1), 1000),),
        ).fetchall()
    return {"ok": True, "entradas": [dict(f) for f in filas]}
