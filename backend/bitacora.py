"""
Bitácora de acciones del docente.
"""
import sqlite3
from datetime import datetime, timezone


def registrar(conn: sqlite3.Connection, accion: str, detalle: str = "") -> None:
    """Agrega una entrada a la bitácora (el commit lo hace quien llama)."""
    conn.execute(
        "INSERT INTO bitacora (fecha, accion, detalle) VALUES (?, ?, ?)",
        (datetime.now(timezone.utc).isoformat(), accion, detalle),
    )
