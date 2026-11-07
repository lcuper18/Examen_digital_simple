"""
Ajustes routes - Datos institucionales, nota mínima y datos de red del servidor (docente).
"""
import socket
import subprocess
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from backend import bitacora, database, security

router = APIRouter(
    prefix="/api/docente", tags=["ajustes"], dependencies=[Depends(security.require_docente)]
)
publico = APIRouter(prefix="/api", tags=["config"])


@publico.get("/config")
def config_publica() -> dict[str, Any]:
    """Datos institucionales para mostrar en pantalla y PDF (no son sensibles)."""
    with database.get_db_context() as conn:
        a = database.leer_ajustes(conn)
    return {"ok": True, "institucion": a["institucion"], "curso_lectivo": a["curso_lectivo"]}


@router.get("/ajustes")
def obtener_ajustes() -> dict[str, Any]:
    with database.get_db_context() as conn:
        return {"ok": True, "ajustes": database.leer_ajustes(conn)}


class GuardarAjustes(BaseModel):
    ajustes: dict[str, str]


@router.put("/ajustes")
def guardar_ajustes(request: GuardarAjustes) -> dict[str, Any]:
    desconocidas = set(request.ajustes) - set(database.AJUSTES_DEFAULT)
    if desconocidas:
        raise HTTPException(status_code=400, detail=f"Ajuste desconocido: {', '.join(sorted(desconocidas))}")
    valores = {k: v.strip() for k, v in request.ajustes.items()}
    if any(not v for v in valores.values()):
        raise HTTPException(status_code=400, detail="Ningún ajuste puede quedar vacío")
    if "nota_minima" in valores:
        try:
            if not 0 <= float(valores["nota_minima"]) <= 100:
                raise ValueError
        except ValueError:
            raise HTTPException(status_code=400, detail="La nota mínima debe estar entre 0 y 100")
    with database.get_db_context() as conn:
        conn.executemany(
            "INSERT INTO ajustes (clave, valor) VALUES (?, ?) "
            "ON CONFLICT (clave) DO UPDATE SET valor = excluded.valor",
            list(valores.items()),
        )
        bitacora.registrar(conn, "guardar_ajustes", ", ".join(sorted(valores)))
        conn.commit()
        return {"ok": True, "ajustes": database.leer_ajustes(conn)}


def _ip_local() -> str | None:
    """IP de la Mac en la red (no envía tráfico: solo consulta la ruta por defecto)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return None
    finally:
        s.close()


def _nombre_local() -> str | None:
    """Nombre Bonjour de la Mac (el que permite entrar con http://nombre.local, aunque cambie la IP)."""
    try:
        nombre = subprocess.run(
            ["scutil", "--get", "LocalHostName"], capture_output=True, text=True, timeout=2, check=True,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        nombre = socket.gethostname().split(".")[0]
    return f"{nombre}.local" if nombre and not nombre.replace(".", "").isdigit() else None


@router.get("/red")
def datos_de_red(request: Request) -> dict[str, Any]:
    """Direcciones para que los estudiantes entren (la IP puede cambiar; el nombre .local no)."""
    puerto = request.url.port or 80
    ip, nombre = _ip_local(), _nombre_local()
    return {
        "ok": True, "ip": ip, "nombre": nombre,
        "url_ip": f"http://{ip}:{puerto}" if ip else None,
        "url_nombre": f"http://{nombre}:{puerto}" if nombre else None,
    }
